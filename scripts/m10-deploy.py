#!/usr/bin/env python3
"""Push files to the M10 and (re)start a GUI/daemon script there.

    ./m10-deploy.py app.py
    ./m10-deploy.py app.py --dest-dir /root/app
    ./m10-deploy.py app.py --run "python3 app.py --flag" --name app
    ./m10-deploy.py --stop --name app
    ./m10-deploy.py app.py --no-run --wait 0
    ./m10-deploy.py app.py --name app --unit app   # supervised by a user unit

"Deploy" means: syntax-check locally, SFTP push, kill the stale instance,
launch in the background with DISPLAY=:0 and PYTHONUNBUFFERED=1, then show the
first lines of stdout/stderr and confirm exactly one process is running.

**If the app is autostarted** (a systemd user unit started from
/root/.xsessionrc, references/autostart.md), do not pkill it: systemd would
restart it and the launch below would produce a second copy drawing over the
first. Pass `--unit <name>` and the restart is delegated to systemd.

Why the shape: a foreground `exec_command` blocks until the client timeout
(PipeTimeout) and `pkill -f` matches its own shell unless you use the bracket
trick. Both are handled here. See references/paramiko.md.

Env: M10_HOST, M10_USER, M10_PASS.
"""
import argparse
import os
import sys

try:
    import paramiko
except ImportError:
    sys.exit("paramiko is required: pip install paramiko")

HOST = os.environ.get("M10_HOST", "10.1.2.3")
USER = os.environ.get("M10_USER", "root")
PASS = os.environ.get("M10_PASS", "dfrobot")


def client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=10)
    return c


def run(c, cmd, t=20):
    _, so, se = c.exec_command(cmd, timeout=t)
    return (so.read() + se.read()).decode(errors="replace")


def bracket(name):
    """'[a]pp.py' — stops pkill/pgrep matching their own command line."""
    return "[" + name[0] + "]" + name[1:]


def main():
    ap = argparse.ArgumentParser(
        epilog="Env: M10_HOST, M10_USER, M10_PASS")
    ap.add_argument("files", nargs="*", help="local files to push")
    ap.add_argument("--dest-dir", default="/root/g-buddy")
    ap.add_argument("--name", help="process/pkill name (default: first file's basename)")
    ap.add_argument("--run", help="command to launch (default: python3 <name>.py)")
    ap.add_argument("--stop", action="store_true", help="stop the process and exit")
    ap.add_argument("--unit", help="systemd user unit that runs the app: restart "
                                   "it instead of pkill + launch (autostart.md)")
    ap.add_argument("--no-run", action="store_true", help="push only")
    ap.add_argument("--wait", type=float, default=4.0,
                    help="seconds to wait before reading logs (default 4)")
    ap.add_argument("--no-compile", action="store_true",
                    help="skip the local py_compile check")
    args = ap.parse_args()

    if not args.files and not args.stop:
        ap.error("give at least one file, or --stop")

    name = args.name
    if not name and args.files:
        name = os.path.basename(args.files[0]).replace(".py", "")
    if args.stop and not name:
        ap.error("--stop needs --name")

    run_cmd = args.run or ("python3 %s.py" % name)
    out = "/tmp/%s.out" % name
    err = "/tmp/%s.err" % name

    if not args.no_compile:
        import py_compile
        for path in args.files:
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as exc:
                sys.exit("local syntax error in %s:\n%s" % (path, exc))
        if args.files:
            print("local py_compile: OK")

    c = client()
    try:
        if args.files:
            run(c, "mkdir -p %s" % args.dest_dir)
            sftp = c.open_sftp()
            for path in args.files:
                remote = args.dest_dir.rstrip("/") + "/" + os.path.basename(path)
                sftp.put(path, remote)
                print("put %-50s -> %s" % (path, remote))
            sftp.close()

        if args.unit:
            # systemd owns the process: killing it would be undone by
            # Restart=on-failure and then collide with our own launch.
            uenv = "XDG_RUNTIME_DIR=/run/user/0"
            if args.stop or args.no_run:
                print(run(c, "%s systemctl --user stop %s" % (uenv, args.unit), 30).strip()
                      or "stopped %s" % args.unit)
                return
            print(run(c, "%s systemctl --user restart %s" % (uenv, args.unit), 30).strip()
                  or "restarted %s" % args.unit)
        else:
            # stop the stale instance (SIGINT first: the unihiker exit handler
            # releases the framebuffer/GPIO; SIGKILL as the fallback)
            run(c, "pkill -INT -f '%s'; sleep 1; pkill -KILL -f '%s'" % (bracket(name), bracket(name)), 10)
            print("stopped old '%s' (if any)" % name)

        if args.stop or args.no_run:
            return

        if args.unit:
            if args.wait:
                import time
                time.sleep(args.wait)
            print("\n-- unit --")
            print(run(c, "XDG_RUNTIME_DIR=/run/user/0 systemctl --user show -p "
                         "ActiveState -p MainPID -p NRestarts %s" % args.unit, 20).strip())
            print("\n-- journal --")
            print(run(c, "XDG_RUNTIME_DIR=/run/user/0 journalctl --user -u %s "
                         "-n 40 --no-pager 2>/dev/null | tail -40" % args.unit, 30).rstrip()
                  or "(no journal entries)")
            if run(c, "test -s %s && echo y" % err):
                print("\n-- stderr (%s) --" % err)
                print(run(c, "tail -40 %s" % err).rstrip())
            pids = run(c, "pgrep -af '%s' | grep -v pgrep" % bracket(name)).strip()
            lines = [ln for ln in pids.splitlines() if ln.strip()]
            print("\nrunning (%d instance%s)%s" % (
                len(lines), "" if len(lines) == 1 else "s",
                ": " + lines[0] if lines else " — NOT RUNNING"))
            return

        # `export` is required, not cosmetic: an assignment prefix cannot
        # precede a subshell, so `VAR=x (cmd &)` is a bash syntax error and the
        # launch dies silently. Surface it -- the failure was invisible before.
        launch = ("cd %s && export DISPLAY=:0 PYTHONUNBUFFERED=1 && "
                  "(%s > %s 2> %s &)" % (args.dest_dir, run_cmd, out, err))
        out_launch = run(c, launch, 5).strip()
        if out_launch:
            print("launch failed: %s" % out_launch)
        print("launched:", run_cmd)
        if args.wait:
            import time
            time.sleep(args.wait)
            print("\n-- stdout --")
            print(run(c, "cat %s 2>/dev/null | tail -40" % out).rstrip() or "(empty)")
            print("\n-- stderr --")
            print(run(c, "cat %s 2>/dev/null | tail -40" % err).rstrip() or "(empty)")

        pids = run(c, "pgrep -af '%s' | grep -v pgrep" % bracket(name)).strip()
        lines = [ln for ln in pids.splitlines() if ln.strip()]
        if len(lines) == 1:
            print("\nrunning (1 instance):", lines[0])
        elif not lines:
            print("\nNOT RUNNING — check %s and %s" % (err, out))
        else:
            print("\nWARNING: %d instances — duplicates draw on top of each other:" % len(lines))
            for ln in lines:
                print("  ", ln)
    finally:
        c.close()


if __name__ == "__main__":
    main()
