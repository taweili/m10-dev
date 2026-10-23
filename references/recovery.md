# 10. Recovery: when the board, X, or a script is wedged

> Reviewed 2026-10-19. Assumes firmware v0.4.2, `unihiker` 0.0.27+ and `pinpong` 0.6.1; version-specific claims are flagged inline.

Flash is the last resort, not the first. Work down this ladder; each step is
cheaper and less destructive than the next.

## 1. Is the board alive at all?

```bash
ping -c2 10.1.2.3
timeout 3 bash -c 'exec 3<>/dev/tcp/10.1.2.3/22' && echo SSH open
ssh root@10.1.2.3 'uptime; free -m'
```

- **No ping / no SSH** → `board-link.md`. The USB gadget re-enumerated, the NIC
  renamed, or the board is still booting. Press Home, wait 10 s, re-plug; then
  `scripts/m10-net-setup.sh --status`.
- **SSH works, screen dark** → you are in the right place: §2.
- **SSH and screen work but the app is wrong** → §3.

## 2. Display / X recovery

```bash
ssh root@10.1.2.3

pgrep -a Xorg; pgrep -a lightdm; ls -l /dev/fb0
DISPLAY=:0 xdpyinfo | grep dimensions       # expect 240x320 or 320x240
```

**Nothing on `:0` / "cannot open display"** — X is down. Restarting lightdm
also kills every GUI app, so expect to relaunch yours:

```bash
systemctl restart lightdm
sleep 3
DISPLAY=:0 xdpyinfo | grep dimensions
```

**X runs but the screen is blank/black**:

```bash
DISPLAY=:0 xset q | grep -A2 'Screen Saver\|DPMS'   # is blanking even on?
DISPLAY=:0 xset s off; DISPLAY=:0 xset -dpms; DISPLAY=:0 xset s noblank
```

On this image **blanking is already off**: `lightdm.conf` starts
`Xorg -s 0 -dpms` (screensaver timeout 0, DPMS disabled), so a black panel is
usually *your app*, not the backlight — check `pgrep -af '[y]our_app.py'` and
`/tmp/*.err` first. If you do need a different policy, edit `xserver-command=`
in `/etc/lightdm/lightdm.conf` and restart lightdm, rather than racing `xset`
from inside the app.

**Content is clipped on the right / sideways** — the board is in portrait while
the script assumes landscape. Fix `Rotate` in `m10-api.md` §7,
restart lightdm, and relaunch.

**Snapshot is black but the app is "running"** — the app is drawing to a
different display, or it drew once and died. Check its stderr
(`references/paramiko.md`, buffering trap) before blaming X.

**The app crashed and no home menu is running** — on a board where the menu was
replaced (trimmed, or an app autostarted in its place — `autostart.md`), a
crashed app leaves the panel **black** instead of returning to the home screen.
That is what `Restart=on-failure` is for: with the app supervised a crash is a
3 s pause, not a dead bench — `systemctl --user status <unit>` and its
`NRestarts=` tell you it happened. Unsupervised, read `/tmp/app.err` for the
traceback and relaunch.

## 3. Script recovery

```bash
pgrep -af '[a]pp.py'                 # exactly one line expected
pkill -INT  -f '[a]pp.py'            # graceful: unihiker's exit_handler frees GPIO
sleep 1
pkill -KILL -f '[a]pp.py'            # only if SIGINT did not work
```

- **Two instances** → they draw on top of each other and the screenshot becomes
  nonsense. Kill all, launch one (`scripts/m10-deploy.py` checks this).
- **A tone keeps sounding** → the buzzer uses PWM; `buzzer.stop()` in the app, or
  let the process die. A wedged PWM survives a kill only in the coprocessor — a
  reboot clears it.
- **Buttons stop responding** → the app owns the polling loop; if it is stuck
  (blocked on `pitch(freq, beat)`, a network call, or a dead mic read), it never
  reads them. Kill and relaunch; look for blocking calls in the loop.
- **Script exits instantly when launched over SSH** → missing `DISPLAY=:0`, or a
  crash before the Tk loop. Read `/tmp/app.err` first; stderr is unbuffered.

## 4. Audio recovery

The M10 has **no onboard speaker** — the only audio output that always works
is the **buzzer** (piezo, PWM). For real audio you need a USB speaker in the
USB-A port, but a USB speaker that isn't detected is a hardware problem, not
a software one. Work down this ladder.

### 4.1 Is the USB speaker detected at all?

```bash
lsusb                                 # must list the speaker here, not just hubs
lsusb -t                               # topology — which bus/port
lsmod | grep snd_usb_audio             # the driver loads on detection
aplay -l                               # a new ALSA card appears (e.g. card 2)
```

The USB-A port maps to **Bus 02** (EHCI, `ff440000.usb`) and **Bus 03**
(OHCI, `ff450000.usb`); the USB-C gadget link is Bus 01 (DWC OTG,
`ff400000.usb`). If `lsusb` shows only `Linux Foundation … root hub` on all
three buses, the speaker is not being electrically seen — no amount of
software will fix that.

| Symptom | Cause / fix |
|---|---|
| Speaker not in `lsusb` at all | reseat in the USB-A port; try a **powered USB hub** (the M10's port may not supply enough current); try a **data-capable** cable (some ship charge-only); test the speaker on a PC |
| Speaker in `lsusb` but no ALSA card | `modprobe snd-usb-audio`; if it fails with `Exec format error` the module is built for a different kernel — reflash is the only fix |
| `snd-usb-audio` not in `lsmod` | the module is available at `/lib/modules/…/kernel/sound/usb/snd-usb-audio.ko` but only loads when a device appears — detection failed (see above) |
| Works on a hub, not alone | the port's current limit — use a powered hub permanently |

### 4.2 PulseAudio

Pulse is a **user** unit here (`/usr/lib/systemd/user/pulseaudio.service`,
enabled in root's `default.target`), *not* a system service — so
`systemctl restart pulseaudio` fails with "Unit pulseaudio.service not found".
Drive it inside root's session:

```bash
export XDG_RUNTIME_DIR=/run/user/0     # required from an SSH shell
pactl info | head -3                   # is a daemon answering?
systemctl --user status pulseaudio
systemctl --user restart pulseaudio
pactl list short sinks                 # the speaker appears as a sink
pactl set-default-sink <sink-name>     # route Audio.play() to it
alsactl restore                        # re-apply the saved mixer state
```

Without `XDG_RUNTIME_DIR`, `pactl` looks for a socket that is not there and
reports "Connection refused" — which reads like a dead daemon and is not. If
the unit is masked (trimmed bench, `system.md`), start the daemon directly with
`pulseaudio --start` for ad-hoc testing; it then runs as a user daemon under
`/run/user/0/pulse/`.

### 4.3 The silent-success trap

`aplay`, `paplay` and `unihiker.Audio.play()` all **return exit 0** even when
there is no speaker wired to the DAC. The onboard codec (`card 1`,
`rk3308-acodec`) has no physical output — audio routed there goes nowhere
audible. If playback "succeeds" but you hear nothing:

1. Check `pactl list short sinks` — if only `alsa_output.platform-acodec-sound`
   is listed, the USB speaker is not a sink (not detected, §4.1).
2. Confirm the buzzer works (it always does): `python3 -c "from
   pinpong.board import Board; Board().begin(); from
   pinpong.extension.unihiker import buzzer; buzzer.pitch(880)"`.

Mic silent → `m10-api.md` §5 (Loopback trap, capture gain, `hw:1,0`).

## 5. Reboot — do it properly

```bash
sync
systemctl poweroff                   # or: reboot
```

Wait for the screen to go dark and the activity LED to stop before pulling
power. Yanking USB-C during writes risks the eMMC filesystem; if a boot then
fails, reflashing is the only repair.

**Hard reset** (board unresponsive, no SSH): unplug USB-C, wait 5 s, plug it
back in. The board boots on power. Nothing is lost that was on disk; unsaved
in-memory state is.

After any reboot:

1. `scripts/m10-smoke.py --no-snapshot` — link, versions, coprocessor.
2. Check orientation (`xdpyinfo`) and re-apply landscape if needed.
3. Confirm the trimmed service list is still down (`pgrep -af 'pyboard|smbd|SIoT'`).
4. Relaunch your app (deploy is push + background launch). A **hand-launched**
   app does not come back — there is no supervision. If it is a user unit
   started from `~/.xsessionrc` (`autostart.md`), it is already up: check
   `systemctl --user status <unit>` (with `XDG_RUNTIME_DIR=/run/user/0`) instead
   of launching a second copy.

## 6. Filesystem or boot damage

Symptoms: boot loops, `EXT4-fs error` on the console, or `read-only file system`
after a bad power loss. A read-only remount is the kernel protecting data; a
reboot may clear it, but repeated occurrences mean the eMMC is unhappy.

```bash
mount | grep ' / '                   # look for (ro, ...)
dmesg | grep -iE 'ext4|i/o error'    # dmesg may be restricted on the host, not the board
```

This is the point where recovery stops: reflash (`flash-firmware.md`). It wipes
`/root/` — back up first if the board still boots far enough to SFTP.

## Escalation summary

| Situation | Action |
|---|---|
| No ping / no SSH | `board-link.md` — NIC/NM/route, then replug |
| SSH, no X | `systemctl restart lightdm` |
| App crashed, panel black | trimmed board → no home menu; read `/tmp/app.err` |
| Screen blank after idle | usually the app, not the backlight — `xset q`, then `/tmp/*.err` (§2) |
| App gone after a reboot | nothing supervises a hand launch — `autostart.md` |
| Wrong orientation / clipped | re-apply `Rotate`, restart lightdm |
| App hung / duplicated | `pkill` bracket trick, relaunch one |
| Buzzer/GPIO wedged | kill, then reboot if it persists |
| Audio gone | §4 — `lsusb` first (is the speaker seen?), then PulseAudio, then the silent-success trap |
| Filesystem errors / boot loop | reflash (`flash-firmware.md`) |
