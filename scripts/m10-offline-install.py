#!/usr/bin/env python3
"""Install an offline bundle on the M10 from a JSON manifest.

    ./m10-offline-install.py --manifest offline/manifest.json
    ./m10-offline-install.py --manifest offline/manifest.json --dry-run
    ./m10-offline-install.py --manifest offline/manifest.json --allow-missing --dry-run

The skill owns the mechanics (recursive SFTP, dpkg extraction, index-free pip,
import/ABI verification); the manifest owns the pins (versions, model, paths).
See references/system.md ("Installing packages without Wi-Fi") and
references/speech.md (the Vosk libstdc++ ABI fix).

Manifest: version 1, paths relative to the manifest file.
  board_dirs  remote dirs to create
  files       [{src, dst}]   dst ending in / keeps the basename
  trees       [{src, dst}]   recursive push
  debs        [{src, extract}]
  pip         {find_links, packages, no_deps}
  checks      module names to import on the board
  abi         {preload, expr}  expr may use {model}
  pycompile   remote dirs whose *.py are syntax-checked

Exit: 0 ok, 1 a step failed, 2 invalid manifest.
"""
import argparse
import json
import os
import posixpath
import re
import sys
import time

try:
    import paramiko
except ImportError:
    sys.exit("paramiko is required: pip install paramiko")

HOST = os.environ.get("M10_HOST", "10.1.2.3")
USER = os.environ.get("M10_USER", "root")
PASS = os.environ.get("M10_PASS", "dfrobot")

ALLOWED = {"version", "board_dirs", "files", "trees", "debs", "pip",
           "checks", "abi", "pycompile"}
MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


class BadManifest(Exception):
    pass


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % n
        n /= 1024.0


def resolve_local(base, src):
    if not isinstance(src, str) or not src:
        raise BadManifest("src must be a non-empty string")
    real = os.path.realpath(os.path.join(base, src))
    if os.path.commonpath([base, real]) != base:
        raise BadManifest("src escapes the manifest directory: %s" % src)
    return real


def remote_path(value, field):
    if not isinstance(value, str) or not value.startswith("/"):
        raise BadManifest("%s must be an absolute board path: %r" % (field, value))
    norm = posixpath.normpath(value)
    if ".." in norm.split("/"):
        raise BadManifest("%s is not normalised: %r" % (field, value))
    return value


def load(path, allow_missing):
    base = os.path.dirname(os.path.abspath(path))
    try:
        with open(path, encoding="utf-8") as fh:
            m = json.load(fh)
    except (OSError, ValueError) as exc:
        raise BadManifest("cannot read %s: %s" % (path, exc))

    unknown = set(m) - ALLOWED
    if unknown:
        raise BadManifest("unknown keys: %s (allowed: %s)" %
                          (", ".join(sorted(unknown)), ", ".join(sorted(ALLOWED))))
    if m.get("version") != 1:
        raise BadManifest("version must be 1")

    out = {"board_dirs": [], "files": [], "trees": [], "debs": [],
           "pip": None, "checks": [], "abi": None, "pycompile": []}

    for d in m.get("board_dirs", []):
        out["board_dirs"].append(remote_path(d, "board_dirs"))

    dsts = set()
    for entry in ("files", "trees"):
        for item in m.get(entry, []):
            if not isinstance(item, dict) or set(item) != {"src", "dst"}:
                raise BadManifest("%s entries need exactly src and dst" % entry)
            src = resolve_local(base, item["src"])
            dst = remote_path(item["dst"], entry + ".dst")
            if not allow_missing and not os.path.exists(src):
                raise BadManifest("missing local artifact: %s" % item["src"])
            key = posixpath.normpath(dst if not dst.endswith("/")
                                     else dst + os.path.basename(src))
            if key in dsts:
                raise BadManifest("two entries write to %s" % key)
            dsts.add(key)
            if os.path.exists(src) and os.path.isdir(src) != (entry == "trees"):
                raise BadManifest("%s: %s is %s" %
                                  (entry, item["src"],
                                   "a directory" if os.path.isdir(src) else "a file"))
            out[entry].append({"src": src, "dst": dst})

    for item in m.get("debs", []):
        if not isinstance(item, dict) or set(item) != {"src", "extract"}:
            raise BadManifest("debs entries need exactly src and extract")
        src = resolve_local(base, item["src"])
        if not allow_missing and not os.path.isfile(src):
            raise BadManifest("missing local artifact: %s" % item["src"])
        out["debs"].append({"src": src,
                            "extract": remote_path(item["extract"], "debs.extract")})

    pip = m.get("pip")
    if pip is not None:
        if not isinstance(pip, dict):
            raise BadManifest("pip must be an object")
        if set(pip) - {"find_links", "packages", "no_deps"}:
            raise BadManifest("pip has unknown keys")
        if not pip.get("packages"):
            raise BadManifest("pip.packages is empty")
        if not isinstance(pip.get("no_deps", False), bool):
            raise BadManifest("pip.no_deps must be true/false")
        if pip.get("find_links"):
            remote_path(pip["find_links"], "pip.find_links")
        out["pip"] = {"find_links": pip.get("find_links"),
                      "packages": list(pip["packages"]),
                      "no_deps": bool(pip.get("no_deps", False))}

    for mod in m.get("checks", []):
        if not isinstance(mod, str) or not MODULE_RE.match(mod):
            raise BadManifest("bad module name in checks: %r" % mod)
        out["checks"].append(mod)

    abi = m.get("abi")
    if abi is not None:
        if set(abi) - {"preload", "expr"} or "preload" not in abi or "expr" not in abi:
            raise BadManifest("abi needs preload and expr")
        remote_path(abi["preload"], "abi.preload")
        out["abi"] = {"preload": abi["preload"], "expr": abi["expr"]}

    for d in m.get("pycompile", []):
        out["pycompile"].append(remote_path(d, "pycompile"))

    return out


def plan(m):
    print("manifest plan")
    for d in m["board_dirs"]:
        print("  mkdir        %s" % d)
    for it in m["files"]:
        print("  file         %-60s -> %s  (%s)" %
              (os.path.basename(it["src"]), it["dst"],
               human(os.path.getsize(it["src"])) if os.path.exists(it["src"]) else "?"))
    for it in m["trees"]:
        count, size = tree_size(it["src"])
        print("  tree         %-60s -> %s  (%d files, %s)" %
              (os.path.basename(it["src"]), it["dst"], count, human(size)))
    for it in m["debs"]:
        print("  deb extract  %-60s -> %s" % (os.path.basename(it["src"]), it["extract"]))
    if m["pip"]:
        print("  pip          %s%s (find-links %s)" %
              (" ".join(m["pip"]["packages"]),
               " --no-deps" if m["pip"]["no_deps"] else "",
               m["pip"]["find_links"] or "-"))
    if m["checks"]:
        print("  import       %s" % ", ".join(m["checks"]))
    if m["abi"]:
        print("  ABI          LD_PRELOAD=%s" % m["abi"]["preload"])
    for d in m["pycompile"]:
        print("  py_compile   %s/*.py" % d)


def tree_size(path):
    count = size = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            count += 1
            try:
                size += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return count, size


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)
    return c


def run(c, cmd, t=120):
    _, so, se = c.exec_command(cmd, timeout=t)
    out = (so.read() + se.read()).decode(errors="replace")
    return so.channel.recv_exit_status(), out


def sftp_mkdir_p(sftp, path):
    cur = ""
    for part in [p for p in path.split("/") if p]:
        cur += "/" + part
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)


def push_file(sftp, local, remote, label=None):
    t0 = time.time()
    sftp.put(local, remote)
    print("    put %-58s %8s  %5.1fs" %
          (label or os.path.basename(local),
           human(os.path.getsize(local)), time.time() - t0))


def push_tree(sftp, local, remote):
    count = 0
    for root, _dirs, files in os.walk(local):
        rel = os.path.relpath(root, local)
        rdir = remote if rel == "." else posixpath.join(remote, rel.replace(os.sep, "/"))
        sftp_mkdir_p(sftp, rdir)
        for name in files:
            push_file(sftp, os.path.join(root, name), rdir + "/" + name)
            count += 1
    print("    %d files" % count)


def step(ok, label, detail=""):
    print("%-4s  %s%s" % ("OK" if ok else "FAIL", label,
                          ("  " + detail.strip().splitlines()[-1]) if detail.strip() else ""))
    return ok


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="validate and print the plan; do not connect")
    ap.add_argument("--allow-missing", action="store_true",
                    help="do not require local artifacts to exist (planning/CI)")
    ap.add_argument("--no-checks", action="store_true", help="skip import checks")
    ap.add_argument("--no-abi", action="store_true", help="skip the ABI load test")
    ap.add_argument("--no-pycompile", action="store_true", help="skip py_compile")
    ap.add_argument("--timeout", type=int, default=120, help="per-command timeout")
    args = ap.parse_args()

    try:
        m = load(args.manifest, args.allow_missing)
    except BadManifest as exc:
        print("invalid manifest: %s" % exc, file=sys.stderr)
        return 2

    plan(m)
    if args.dry_run:
        print("\ndry run: manifest is valid")
        return 0

    c = connect()
    sftp = c.open_sftp()
    try:
        for d in m["board_dirs"]:
            sftp_mkdir_p(sftp, d)
        step(True, "board dirs", "%d ensured" % len(m["board_dirs"]))

        for it in m["files"]:
            dst = it["dst"] if not it["dst"].endswith("/") else \
                it["dst"] + os.path.basename(it["src"])
            sftp_mkdir_p(sftp, posixpath.dirname(dst) or "/")
            push_file(sftp, it["src"], dst)
        step(True, "files", "%d pushed" % len(m["files"]))

        for it in m["trees"]:
            print("  tree -> %s" % it["dst"])
            push_tree(sftp, it["src"], it["dst"])
        step(True, "trees", "%d pushed" % len(m["trees"]))

        for it in m["debs"]:
            rc, out = run(c, "dpkg-deb -x %s %s" % (it["src"], it["extract"]),
                          args.timeout)
            if not step(rc == 0, "deb extract", os.path.basename(it["src"])):
                print(out)
                return 1
            rc, out = run(c, "ls %s" % it["extract"], args.timeout)
            if not step(rc == 0, "deb contents", it["extract"]):
                return 1

        if m["pip"]:
            pip = m["pip"]
            cmd = "pip3 install --no-index"
            if pip["find_links"]:
                cmd += " --find-links %s" % pip["find_links"]
            if pip["no_deps"]:
                cmd += " --no-deps"
            cmd += " " + " ".join(pip["packages"])
            rc, out = run(c, cmd, max(args.timeout, 600))
            if not step(rc == 0, "pip install", " ".join(pip["packages"])):
                print(out)
                return 1

        if m["checks"] and not args.no_checks:
            for mod in m["checks"]:
                rc, out = run(
                    c, "python3 -c 'import %s; print(getattr(%s, \"__version__\", \"\"))'"
                       % (mod, mod), args.timeout)
                if not step(rc == 0, "import " + mod, out):
                    return 1

        if m["abi"] and not args.no_abi:
            script = m["abi"]["expr"] + "\nprint('ABI OK')\n"
            with sftp.file("/tmp/m10-abi-check.py", "w") as fh:
                fh.write(script)
            rc, out = run(c, "test -f %s" % m["abi"]["preload"], args.timeout)
            if not step(rc == 0, "ABI preload exists", m["abi"]["preload"]):
                return 1
            rc, out = run(c, "LD_PRELOAD=%s python3 /tmp/m10-abi-check.py"
                          % m["abi"]["preload"], max(args.timeout, 300))
            if not step(rc == 0, "ABI load test", out):
                print(out)
                return 1
            run(c, "rm -f /tmp/m10-abi-check.py", 10)

        if m["pycompile"] and not args.no_pycompile:
            for d in m["pycompile"]:
                rc, out = run(
                    c, "cd %s && for f in *.py; do [ -e \"$f\" ] || continue; "
                       "python3 -m py_compile \"$f\" || exit 1; done" % d,
                    args.timeout)
                if not step(rc == 0, "py_compile", d):
                    print(out)
                    return 1
    finally:
        sftp.close()
        c.close()

    print("\nDONE  %s" % args.manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
