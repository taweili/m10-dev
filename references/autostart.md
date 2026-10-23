# 12. Start a GUI app at boot (autostart)

> Reviewed 2026-10-23, measured on firmware v0.4.2, `unihiker` 0.0.28.5,
> `pinpong` 0.6.1. The chain in §1 was traced on a real `systemctl reboot`,
> timestamps included.

A deploy leaves one process running; a **reboot ends it and nothing restarts
it**. This file is the supported way to make a GUI app come back by itself —
and the reason the answer is a *user* systemd unit started from
`~/.xsessionrc`, not `rc.local` and not `systemctl enable`.

## 1. The measured boot chain

```
systemd (system)  →  graphical.target  →  lightdm.service
                                            │  autologin root (lightdm.conf)
                                            ▼
                        Xorg :0              (17:40:23)
                        lightdm --session-child
                        systemd --user   ← pam_systemd at session creation (17:40:25)
                          pulseaudio.service  (17:40:26)
                        /etc/X11/Xsession
                          … Xsession.d/40x11-common_xsessionrc → /root/.xsessionrc
                            systemctl --user start <your unit>   (17:40:27)
```

Two facts fall out of it:

- **X is already up** when `~/.xsessionrc` is sourced, and the session
  environment exists (display, authority, bus, runtime dir).
- **The user manager starts at login**, not at boot: `systemctl --user` only
  exists while root is logged in. That is why a *system* unit cannot see the
  session, and why `enable`-ing a user unit still starts it after Xorg here.

`/etc/lightdm/lightdm.conf` (the hook for both facts):

```ini
[Seat:*]
xserver-command=X -s 0 -dpms -dpi 100     # screensaver off, DPMS off → no blanking
autologin-user=root
autologin-user-timeout=0
```

`/root/.xsessionrc` is DFRobot's own autostart file — it ships with the image
(so a reflash restores it) and, as shipped, contains:

```bash
echo 20 > /sys/class/gpio/export
echo out > /sys/class/gpio/gpio20/direction
echo 1 > /sys/class/gpio/gpio20/value
systemctl --user start PyboardUI      # the home menu
```

That last line is the menu you see on a stock board. It is also the thing that
fights your app for the panel (§6).

## 2. What does *not* work (and why)

| Candidate | Verdict |
|---|---|
| `/etc/rc.local` | **No session environment.** Measured on this image it is *not* early — `rc-local.service` went active at 17:40:36, 19 s **after** lightdm (17:40:17), because it waits for `network-online` — but it inherits none of the session (`DISPLAY`, `XAUTHORITY`, `XDG_RUNTIME_DIR`, session bus), so a Tk GUI and anything Pulse-shaped fail. It is also DFRobot's (mounts `/boot`, burns the GD32 via `anaysis.py`) — do not add to it. |
| system unit + `After=display-manager.service` | Workable but fragile: system services do not get the session bus, `XAUTHORITY` or `XDG_RUNTIME_DIR=/run/user/0`, so Pulse/Piper/`paplay` and any DBus call need them hand-faked. |
| `systemctl --user enable` in `default.target` | Starts at login — which happens *after* Xorg here, so it can work, but it races the session setup and is not what DFRobot uses. `.xsessionrc` is the verified path; pick one, not both. |
| `~/.config/autostart/*.desktop` | Inert: no desktop environment reads it on this image (`/etc/xdg/autostart` is only honoured because DFRobot's own units are started by hand). |
| `cron @reboot` | Same "too early" problem as `rc.local`, plus a root `crontab` you will forget. |

## 3. The user unit (copy this)

Own units go in **`/etc/systemd/user/`** (the load path for the user manager);
never edit `/usr/lib/systemd/user/`, which is the image's (`PyboardUI`,
`PyboardWeb`, `SIoT`, `pulseaudio`, …).

```ini
# /etc/systemd/user/g-buddy.service
[Unit]
Description=g-buddy voice buddy (UNIHIKER M10 bench)
After=pulseaudio.service
Wants=pulseaudio.service
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/root/g-buddy
# The session exports most of this itself; spell it out so the unit also works
# when started by hand over SSH, where none of it is set.
Environment=DISPLAY=:0
Environment=XAUTHORITY=/root/.Xauthority
Environment=XDG_RUNTIME_DIR=/run/user/0
Environment=PYTHONUNBUFFERED=1
# /usr/bin/python3 is 3.7.3 — unihiker/pinpong live in python3.7/dist-packages.
ExecStart=/usr/bin/python3 /root/g-buddy/gbuddy.py
# Crash → restart. A deliberate quit (exit 0) stays quit until next boot.
Restart=on-failure
RestartSec=3
# SIGINT first: unihiker's exit_handler releases the framebuffer and GPIO.
KillSignal=SIGINT
TimeoutStopSec=15
StandardOutput=file:/tmp/gbuddy.out
StandardError=file:/tmp/gbuddy.err
```

Notes that matter:

- **`/usr/bin/python3`, not `python3`.** On v0.4.1+ `python3` on `PATH` is the
  pyenv shim; `pyenv global` happens to be `system` on v0.4.2, so it resolves to
  3.7.3 today — but the day someone runs `pyenv global 3.12.7`, a bare
  `python3` loses `unihiker`/`pinpong`. Be explicit in anything that starts at
  boot.
- **`Environment=DISPLAY=:0`** is belt and braces — `systemctl --user
  show-environment` already carries `DISPLAY=:0`, `XDG_RUNTIME_DIR=/run/user/0`
  and `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus`, but not
  `XAUTHORITY`.
- **`Restart=on-failure` vs `always`**: `on-failure` keeps "press A to quit"
  meaningful; `always` makes the app unkillable (useful for a kiosk, maddening
  while developing).
- **`KillSignal=SIGINT`** so `systemctl --user stop` is the documented graceful
  stop (`recovery.md` §3) instead of a `SIGTERM` the DFRobot stack ignores.
- `StandardOutput=file:` truncates on each start, `append:` accumulates
  (verified on systemd 241: a restart leaves a log holding only the new run).
  Do not rely on the journal for user units here — `journalctl --user` can
  report "No entries" on this image — `/tmp/*.err` is what the rest of this
  skill greps.
- **Restarting an app that holds an ALSA capture device can race the old
  instance's release**: one restart logged `mic read error: [Errno -9999]
  Unanticipated host error` from the new process while the dying one still had
  `hw:1,0` open, then recovered. `systemctl --user stop; sleep 1; start` is the
  reliable order; a bare `restart` is fine only if the app closes its stream on
  SIGINT (`KillSignal=SIGINT` means it can).
- **No `[Install]` section is needed** for the `.xsessionrc` path. If you add
  `WantedBy=default.target` and `enable` it *instead*, remove the
  `.xsessionrc` line — two triggers for one GUI is how you get two windows.

## 4. Wire it into the session

```bash
# from the PC — create the dir first, then push the unit
python3 - <<'PY'
import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.1.2.3", username="root", password="dfrobot", timeout=10)
c.exec_command("mkdir -p /etc/systemd/user")[1].channel.recv_exit_status()
c.open_sftp().put("myapp.service", "/etc/systemd/user/myapp.service")
print(c.exec_command("cat /etc/systemd/user/myapp.service")[1].read().decode())
PY
```

Then edit the session hook **on the board** (back it up first):

```bash
cp /root/.xsessionrc /root/.xsessionrc.bak        # keep the original
# drop the PyboardUI line, add yours:
#   systemctl --user start PyboardUI   →   # systemctl --user start PyboardUI
#                                          systemctl --user start myapp
XDG_RUNTIME_DIR=/run/user/0 systemctl --user daemon-reload
```

Use SFTP `put`, not a heredoc, and **re-read the file afterwards** — a truncated
unit fails `daemon-reload` with a parse error that is easy to miss over SSH.

## 5. Driving it from a deploy shell

Every `systemctl --user` call over SSH needs the runtime dir, or it fails with
`Failed to connect to bus: No such file or directory`:

```bash
export XDG_RUNTIME_DIR=/run/user/0          # root's session
systemctl --user daemon-reload
systemctl --user start   g-buddy
systemctl --user status  g-buddy            # ActiveState, MainPID, NRestarts
systemctl --user stop    g-buddy            # SIGINT (KillSignal above)
systemctl --user restart g-buddy
journalctl --user -u g-buddy -n 50          # if you kept the journal, not file:
```

`NRestarts=` is the cheap crash-loop detector: it counts restarts caused by
`Restart=`, so `NRestarts=0` on a boot old enough to have drawn something means
it never crashed. `ExecMainStartTimestamp=` tells you how long it has been up.

## 6. One panel, one owner

The home menu (`PyboardUI`, `pyboardgui`) and your app both draw to the same
framebuffer. Run both and you get overlapping windows and nonsense screenshots,
so an autostarted app must replace the menu line in `~/.xsessionrc` — do not
just add to it.

Consequences worth knowing:

- With the menu gone, **a crashed app leaves a black panel** — there is no home
  screen to fall back to. `Restart=on-failure` is what replaces the old safety
  net, so a supervised app is *more* recoverable than a hand-launched one.
- `scripts/m10-trim-services.py` stops the menu's user unit *and* comments that
  `.xsessionrc` line — the comment is the part that makes the trim survive a
  reboot (stopping a static unit lasts only until the next login).
- Getting the menu back: restore `/root/.xsessionrc.bak`, or swap the line back
  to `systemctl --user start PyboardUI`.

## 7. Cold boot is not a warm start

The first row is what actually bit this bench; the rest are the ordinary costs
of a cold start. A program that assumes "the user just asked" misbehaves in the
first minute after a boot.

| Symptom on a fresh boot | Why | Handle it by |
|---|---|---|
| Turns / presses nobody made, in the first minute | **observed once** on a first boot (two turns inside 100 s, panel untouched; not reproduced on later restarts, 70 s idle) — a stray evdev contact while the session comes up is the likely cause, but it was not isolated | ignoring contacts for the first ~2-3 s and requiring a real down-edge (`m10-api.md` §9) — cheap either way |
| No network, TLS errors, wrong year | no RTC; `timedatectl` syncs only once Wi-Fi is up | warn, retry, do not crash |
| First answer is slow | Vosk model load ≈ 5.5 s, Piper voice ≈ 5 s per call | do it on a worker thread, show the face first |
| `mic read error: [Errno -9999]` from the new instance | a *restart* opens `hw:1,0` while the dying instance still holds it (seen once, self-healing) | `stop; sleep 1; start` rather than `restart` (see §3) |
| Speaker silent | the A2DP link idle-disconnects, so it is usually *not* connected at boot | connect + route before speaking (`bluetooth.md` §2) |

## 8. Acceptance test

Autostart is only proven by a reboot — not by `systemctl --user start`:

```bash
ssh root@10.1.2.3 'sync; systemctl reboot'      # ~35 s to SSH on this bench
# then, once it answers:
export XDG_RUNTIME_DIR=/run/user/0
systemctl --user show -p ActiveState -p MainPID -p NRestarts g-buddy
pgrep -af '[y]our_app.py'                       # exactly one
pgrep -af '[p]yboardgui'                        # nothing — the menu must be gone
tail -20 /tmp/<name>.err                        # "ready:" and no traceback
scripts/m10-snapshot.py --rotate 90             # the image is the proof
```

A snapshot taken right after SSH returns can still be the previous frame: give
the app ~10-15 s (model loads) before trusting it.

## 9. Undo

```bash
export XDG_RUNTIME_DIR=/run/user/0
systemctl --user stop g-buddy
systemctl --user disable g-buddy 2>/dev/null   # only if you enabled it
rm /etc/systemd/user/g-buddy.service
systemctl --user daemon-reload
cp /root/.xsessionrc.bak /root/.xsessionrc     # menu back
```
