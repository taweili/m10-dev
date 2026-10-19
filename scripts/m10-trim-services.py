#!/usr/bin/env python3
"""Disable DFRobot's stock bloat on a 512 MB M10 and report the memory freed.

    ./m10-trim-services.py            # stop + disable + kill respawners
    ./m10-trim-services.py --dry-run  # show what would be stopped

Two layers matter here: **system** systemd units and **root's user session**.
DFRobot's app daemons are user services, and several are launched from
/etc/init.d and re-spawned by a keepalive loop — so `systemctl disable` alone
does not keep them down; the spawner must be killed too.

Keeps sshd, NetworkManager, isc-dhcp-server, wpa_supplicant, dbus, systemd-*,
lightdm, Xorg, pulseaudio, udev and gettys. Read references/system.md before
changing the lists: Xorg and PulseAudio are required for GUI/audio.

Env: M10_HOST, M10_USER, M10_PASS.
"""
import argparse
import os
import sys
import time

DRY = False

try:
    import paramiko
except ImportError:
    sys.exit("paramiko is required: pip install paramiko")

HOST = os.environ.get("M10_HOST", "10.1.2.3")
USER = os.environ.get("M10_USER", "root")
PASS = os.environ.get("M10_PASS", "dfrobot")

SYSTEMD_UNITS = ["smbd", "nmbd", "samba-ad-dc", "bluetooth", "exim4", "cron",
                 "xrdp", "xrdp-sesman", "x0vncserver", "pyboardgui"]

# root's user session (DFKRobot respawners) — needs XDG_RUNTIME_DIR + DBUS
USER_UNITS = ["FileShare.service", "PyboardUI.service", "PyboardWeb.service",
              "ScreenShare.service", "SIoT.service"]
USER_ENV = ("XDG_RUNTIME_DIR=/run/user/0 "
            "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus")

KILL_PATTERNS = ["pyboardgui", "pyboardWeb", "x0vncserver", "xrdp",
                 "SIoT_unihiker", "/opt/unihiker/SIoT",
                 "systemctl start smbd", "smbd", "nmbd"]


def client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=10)
    return c


def run(c, cmd, t=20):
    if DRY:
        print("  would run:", cmd)
        return ""
    _, so, se = c.exec_command(cmd, timeout=t)
    return (so.read() + se.read()).decode(errors="replace")


def mem(c):
    return run(c, "free -m | awk 'NR==2 {printf \"%dm used / %dm total (avail %dm)\", $3, $2, $7}'").strip()


def main():
    global DRY
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    DRY = args.dry_run

    c = client()
    try:
        print("BEFORE ", mem(c))

        print("\n-- systemd units --")
        for unit in SYSTEMD_UNITS:
            exists = run(c, "systemctl list-unit-files %s.service 2>/dev/null | grep -c '%s.service'" % (unit, unit)).strip()
            if exists == "0":
                print("  %-24s (no unit)" % unit)
                continue
            run(c, "systemctl stop %s 2>&1" % unit)
            run(c, "systemctl disable %s 2>&1" % unit)
            print("  %-24s stopped + disabled" % unit)

        print("\n-- user units (DFKRobot respawners) --")
        for unit in USER_UNITS:
            run(c, "%s systemctl --user stop %s 2>&1" % (USER_ENV, unit))
            run(c, "%s systemctl --user disable %s 2>&1" % (USER_ENV, unit))
            print("  %-24s stopped + disabled" % unit)

        print("\n-- kill respawners --")
        # the keepalive wrapper re-launches smbd, so it dies first
        run(c, "pkill -f 'systemctl start smbd'; sleep 1", 5)
        for pat in KILL_PATTERNS:
            run(c, "pkill -9 -f '%s'; sleep 0.3" % pat, 5)
        time.sleep(2)

        print("\n-- verify --")
        print(run(c, "pgrep -af 'pyboard|x0vnc|xrdp|smbd|nmbd|SIoT|bluetoothd' "
                     "2>/dev/null | grep -v pgrep || echo '  (none)'").strip())
        print("\nAFTER  ", mem(c))
        print("\ntop RSS:")
        print(run(c, "ps -eo comm,rss --sort=-rss | head -12 | "
                     "awk '{printf \"  %-24s %s KB\\n\", $1, $2}'"))
    finally:
        c.close()


if __name__ == "__main__":
    main()
