#!/usr/bin/env python3
"""One-shot health check for the M10: link, versions, session, coprocessor, mic, screen.

    ./m10-smoke.py                 # full check, pulls a framebuffer snapshot
    ./m10-smoke.py --no-snapshot   # everything except the display check

Prints PASS / WARN / FAIL per check and exits non-zero if anything FAILs. The
`session` check answers "what is drawing the panel?" — autologin user, the
autostart lines in /root/.xsessionrc, the home menu, and the app process.
This is the "definition of done" for a board session — run it before believing
any other result, and again after a deploy.

Env: M10_HOST, M10_USER, M10_PASS.
See references/health-check.md for the manual equivalents and the version
compatibility matrix.
"""
import argparse
import os
import subprocess
import sys
import tempfile

try:
    import paramiko
except ImportError:
    sys.exit("paramiko is required: pip install paramiko")

HOST = os.environ.get("M10_HOST", "10.1.2.3")
USER = os.environ.get("M10_USER", "root")
PASS = os.environ.get("M10_PASS", "dfrobot")

results = []


def record(status, label, detail=""):
    results.append((status, label))
    print("%-4s  %-28s %s" % (status, label, detail))


def run(c, cmd, t=45):
    """Run a shell command on the board, capturing stdout+stderr.

    The default is generous because a cold-boot board is slow at everything
    (`python3` start-up, GD32 handshake). OSError covers socket.timeout (which
    is what PipeTimeout re-raises as); swallowing it lets one hung command
    degrade to a WARN/FAIL on its own check instead of aborting the script.
    """
    try:
        _, so, se = c.exec_command(cmd, timeout=t)
        return (so.read() + se.read()).decode(errors="replace").strip()
    except (OSError, paramiko.ssh_exception.SSHException):
        return ""


def check_versions(c):
    """Versions read from dist-info, not `pip3 show`.

    `pip3 show unihiker` takes >25 s on this board (`pip3 list` 13 s, `pip3
    --version` 6 s), which used to blow the channel timeout; the dist-info
    directory name carries the same version and answers instantly.
    """
    fw = run(c, "cat /opt/unihiker/Version 2>/dev/null") or "?"
    deb = run(c, "cat /etc/debian_version 2>/dev/null") or "?"
    py = run(c, "/usr/bin/python3 --version 2>&1") or "?"
    # `python3` on PATH is the pyenv shim on v0.4.1+; a switched global silently
    # loses unihiker/pinpong, so report it when it disagrees with /usr/bin.
    path_py = run(c, "python3 --version 2>&1") or "?"
    dist = run(c, "ls -d /usr/local/lib/python3.7/dist-packages/*.dist-info "
                  "2>/dev/null | sed 's#.*/##; s/\\.dist-info$//' "
                  "| grep -E '^(unihiker|pinpong)-'")
    vers = {}
    for line in dist.splitlines():
        name, _, ver = line.partition("-")
        vers[name] = ver
    uni = vers.get("unihiker", "?")
    ping = vers.get("pinpong", "?")
    pil = run(c, "/usr/bin/python3 -c 'import PIL; print(PIL.__version__)' 2>/dev/null") or "?"
    detail = "fw %s | debian %s | %s | unihiker %s | pinpong %s | PIL %s" % (
        fw, deb, py, uni, ping, pil)
    status = "PASS"
    if fw == "?" or py == "?":
        status = "WARN"
    elif not py.startswith("Python 3"):
        status = "FAIL"
    record(status, "versions", detail)
    # The board can legitimately be newer than the skill's notes; never fail on
    # a version alone, but make drift visible.
    if py and not py.startswith("Python 3.7") and fw in ("v0.4.0", "v0.4.1", "v0.4.2"):
        record("WARN", "python mismatch", "expected 3.7.x on this firmware")
    if path_py and path_py != py:
        record("WARN", "python3 on PATH", "%s (pyenv shim) vs %s — scripts that "
               "import unihiker/pinpong need /usr/bin/python3" % (path_py, py))
    return fw, py, uni


def check_session(c):
    """Lightdm autologin, what ~/.xsessionrc starts, and who owns the panel.

    The cheap answer to "why is my app not on screen?": two GUI owners draw over
    each other, and no owner at all is the black-panel state. `systemctl --user`
    needs root's runtime dir, which an SSH shell does not have.
    """
    autologin = run(c, "sed -n 's/^autologin-user=//p' /etc/lightdm/lightdm.conf") or "?"
    xs = run(c, "test -f /root/.xsessionrc && grep -hvE "
                "'^[[:space:]]*(#|$|echo|export)' /root/.xsessionrc "
                "| tr '\n' ';'")
    menu = bool(run(c, "pgrep -f '[p]yboardgui'"))
    apps = run(c, "pgrep -af '[p]ython3' | grep -vE '[p]yboardgui|systemd' "
                  "| awk '{print $1\":\"($3 ? $3 : $2)}' | tr '\n' ' '")
    owners = len(apps.split())
    parts = ["autologin %s" % autologin]
    if xs:
        line = xs.strip().rstrip(";")
        if len(line) > 70:
            line = line[:67] + "..."
        parts.append("xsessionrc: " + line)
    parts.append("menu " + ("RUNNING" if menu else "off"))
    parts.append("apps " + (apps.strip() or "none"))
    detail = " | ".join(parts)

    if menu and owners:
        record("FAIL", "session", detail + "  (two panel owners — stop one)")
    elif owners:
        record("PASS", "session", detail)
    else:
        record("WARN", "session",
               detail + "  (nothing drawing the panel; a crashed app leaves it "
               "black — autostart.md)")


def check_resources(c):
    mem = run(c, "free -m | awk 'NR==2 {printf \"%d MB used / %d MB total, %d MB available\", $3, $2, $7}'")
    disk = run(c, "df -h /root | awk 'NR==2 {print $4\" free on /root (\"$5\" used)\"}'")
    record("PASS" if mem else "WARN", "resources", (mem + " | " + disk).strip(" |"))


def check_display(c):
    dims = run(c, "DISPLAY=:0 xdpyinfo 2>/dev/null | sed -n 's/^  dimensions: *//p' | head -1")
    if dims:
        note = "landscape" if dims.startswith("320x240") else (
            "portrait" if dims.startswith("240x320") else "unexpected")
        record("PASS", "X display", "%s (%s)" % (dims, note))
    else:
        record("FAIL", "X display", "no X server on :0 — GUI scripts will do nothing")
    # /dev/fb0 is a *character* device, so `stat -c %s` always answers 0 —
    # size it from sysfs and prove it reads back that many bytes instead.
    vs = run(c, "cat /sys/class/graphics/fb0/virtual_size 2>/dev/null").strip()
    bpp = run(c, "cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null").strip()
    size = None
    try:
        w, h = [int(v) for v in vs.split(",")]
        size = w * h * int(bpp) // 8
    except ValueError:
        pass
    if size:
        got = run(c, "dd if=/dev/fb0 bs=%d count=1 2>/dev/null | wc -c" % size, 30)
        if got.strip() == str(size):
            record("PASS", "framebuffer",
                   "/dev/fb0 reads %d bytes (%dx%d @ %s bpp)" % (size, w, h, bpp))
        else:
            record("FAIL", "framebuffer",
                   "/dev/fb0 short read: %r of %d bytes" % (got.strip(), size))
    else:
        record("WARN", "framebuffer", "no /sys/class/graphics/fb0 to size the panel")


def check_coprocessor(c):
    code = (
        "from pinpong.board import Board\n"
        "Board().begin()\n"
        "from pinpong.extension.unihiker import light, button_a\n"
        "print('light=%s button_a=%s' % (light.read(), button_a.value()))\n"
    )
    out = run(c, "python3 -c \"%s\"" % code.replace('"', '\\"'), 45)
    if "light=" in out:
        detail = [ln for ln in out.splitlines() if "light=" in ln][-1]
        record("PASS", "coprocessor (GD32)", detail)
    else:
        tail = " | ".join(out.splitlines()[-3:])
        record("FAIL", "coprocessor (GD32)", tail or "no output — firstRun.sh / pinpong?")


def check_mic(c):
    code = ("from unihiker import Audio\n"
            "a = Audio()\n"
            "print('dBFS=%.1f level=%s' % (a.sound_dBFS(), a.sound_level()))\n")
    out = run(c, "python3 -c \"%s\"" % code.replace('"', '\\"'), 45)
    if "dBFS=" in out:
        detail = [ln for ln in out.splitlines() if "dBFS=" in ln][-1]
        # noise floor on this board is about -51 dBFS
        record("PASS", "microphone", detail)
    else:
        tail = " | ".join(out.splitlines()[-3:])
        record("WARN", "microphone", tail or "Audio() did not report levels")


def check_snapshot(c, host):
    here = os.path.dirname(os.path.abspath(__file__))
    snap = os.path.join(here, "m10-snapshot.py")
    if not os.path.isfile(snap):
        record("WARN", "snapshot", "m10-snapshot.py not next to this script — skipped")
        return
    out = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    out.close()
    proc = subprocess.run([sys.executable, snap, "--out", out.name, "--census",
                           "--host", host],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = proc.stdout.decode(errors="replace").strip()
    if proc.returncode == 0 and os.path.getsize(out.name) > 1024:
        detail = "\n        ".join(text.splitlines())
        record("PASS", "snapshot", detail)
        print("        frame: %s" % out.name)
    else:
        record("FAIL", "snapshot", " ".join(text.splitlines()[-3:]) or "capture failed")
        os.unlink(out.name)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-snapshot", action="store_true")
    ap.add_argument("--host", default=HOST)
    args = ap.parse_args()

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(args.host, username=USER, password=PASS, timeout=10)
    except Exception as exc:
        record("FAIL", "connect", "%s: %s" % (args.host, exc))
        print("\n  → references/board-link.md (run scripts/m10-net-setup.sh --status)")
        sys.exit(1)

    try:
        record("PASS", "connect", "%s over SSH" % args.host)
        fw, py, uni = check_versions(c)
        check_resources(c)
        check_display(c)
        check_session(c)
        check_coprocessor(c)
        check_mic(c)
        if not args.no_snapshot:
            check_snapshot(c, args.host)
    finally:
        c.close()

    fails = [lbl for st, lbl in results if st == "FAIL"]
    print("\n%d checks, %d failed" % (len(results), len(fails)))
    if fails:
        print("failed: " + ", ".join(fails))
        print("triage: references/health-check.md#when-a-check-fails")
        sys.exit(1)


if __name__ == "__main__":
    main()
