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
DISPLAY=:0 xset s off; DISPLAY=:0 xset -dpms; DISPLAY=:0 xset s noblank
```

X blanking and DPMS can blank the panel after minutes of no touch input — the
app is fine, the backlight is off. Good practice for any long-running GUI:
disable blanking at start-up, or re-enable it deliberately.

**Content is clipped on the right / sideways** — the board is in portrait while
the script assumes landscape. Fix `Rotate` in `m10-api.md` §7,
restart lightdm, and relaunch.

**Snapshot is black but the app is "running"** — the app is drawing to a
different display, or it drew once and died. Check its stderr
(`references/paramiko.md`, buffering trap) before blaming X.

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

```bash
aplay -l                             # is the USB speaker enumerated?
pactl info | head -3                 # PulseAudio alive?
systemctl restart pulseaudio
alsactl restore                      # re-apply the saved mixer state
```

No speaker in `aplay -l` → reseat the USB-A speaker; the M10 has **no onboard
speaker**. Mic silent → `m10-api.md` §5 (Loopback trap,
capture gain, `hw:1,0`).

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
4. Relaunch your app (deploy is push + background launch; a reboot does not
   restart it — there is no supervision).

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
| Screen blank after idle | `xset s off -dpms` |
| Wrong orientation / clipped | re-apply `Rotate`, restart lightdm |
| App hung / duplicated | `pkill` bracket trick, relaunch one |
| Buzzer/GPIO wedged | kill, then reboot if it persists |
| Audio gone | `aplay -l`, `systemctl restart pulseaudio`, `alsactl restore` |
| Filesystem errors / boot loop | reflash (`flash-firmware.md`) |
