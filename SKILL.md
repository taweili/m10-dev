---
name: m10-dev
description: "Develop and deploy Python for the DFRobot UNIHIKER M10 (RK3308, Debian 10 SBC) over USB-C: reach and repair 10.1.2.3, Wi-Fi, paramiko SSH/SFTP, deploy and background-run scripts, framebuffer screenshots, unihiker GUI/animation, pinpong GPIO/sensors/buttons/buzzer/LED, touch, mic/audio, landscape, packages/services, offline and cloud STT/TTS, and rkdeveloptool firmware flashing. Triggers: UNIHIKER, M10, K10, pinpong, unihiker, dfrobot, 10.1.2.3, \"the board\", board deploy, framebuffer, touchscreen, Vosk, Azure Speech, reflash, rkdeveloptool, maskrom, bluetooth speaker, A2DP, bluetoothctl."
---

# M10 dev

Work with a DFRobot **UNIHIKER M10** — a Debian 10 Linux SBC with a 2.8" screen,
an on-board RISC-V coprocessor for GPIO, and a fixed IP of **10.1.2.3** on its
USB-C link. You edit code on the PC; the board runs it. Nothing you write here
is on the board until you push it.

## Orientation (30 seconds)

| Thing | Value |
|---|---|
| Board IP / link | `10.1.2.3` on USB-C RNDIS (`br0` on the board, `10.1.2.3/24`) |
| Login | user `root`, password `dfrobot` |
| Python | **3.7.3** (Debian 10) — `pip install` needs Wi-Fi first |
| SoC / RAM / disk | RK3308 4-core ARM @1.2 GHz / 512 MB / 16 GB eMMC |
| Screen | 2.8" touch LCD, **240×320 portrait** (or 320×240 in landscape) |
| Hardware | Home/A/B buttons, **onboard mic**, passive buzzer, blue LED (`P25`), light sensor, 6-axis IMU |
| Audio out | **no onboard speaker** — needs a USB speaker in the USB-A port |
| GPIO library | `pinpong` 0.6.1 (coprocessor is a GD32VF103 RISC-V) |
| Boot / autostart | lightdm autologins **root** on `:0`; `/root/.xsessionrc` runs `systemctl --user start <unit>` |
| Transport | **paramiko** (pure Python) — no `sshpass`/`expect` needed |
| Firmware | **v0.4.2** (ships as v0.4.0); Debian 10 is **EOL** → `apt` needs `archive.debian.org` |

**Precedence when sources disagree:** live board > shipped source (`GUI.py`) >
this skill > DFRobot wiki. Verify the board's versions before trusting any
snippet — `scripts/m10-smoke.py` does it in one run (`references/health-check.md`).

## Reference map

Read the reference that matches the task; each is self-contained.

| Task | Reference |
|---|---|
| **Is the board healthy? Which versions are on it?** What "done" means | `references/health-check.md` |
| Get the board reachable at `10.1.2.3`; fix a dead USB link | `references/board-link.md` |
| Put the board on Wi-Fi | `references/wifi.md` |
| Dev environment: paramiko, deploy, run, stop, screenshots | `references/paramiko.md` |
| Use M10 functions: GUI, buttons, sensors, buzzer, audio, mic, framebuffer, landscape | `references/m10-api.md` |
| Draw and animate: full GUI API, `config()` options, emoji sprites, easing | `references/gui-drawing.md` |
| OS, packages, `apt`/EOL fix, firmware ladder, services, storage, time | `references/system.md` |
| Speech in and out: STT/TTS options, models, pipelines | `references/speech.md` |
| Official Python Starter Kit (KIT0194) + USB speaker/camera usage | `references/starter-kit.md` |
| Azure Speech (real-time STT + neural TTS) | `references/azure-speech.md` |
| Prove a GUI rendered, from `/dev/fb0` | `references/verify-gui.md` |
| **X/app/audio wedged, board unresponsive, how to reboot** | `references/recovery.md` |
| **Flash/reflash firmware** from Linux with `rkdeveloptool` — destructive, read first | `references/flash-firmware.md` |
| Pair a Bluetooth A2DP speaker / Classic RFCOMM; the PulseAudio un-mask A2DP needs | `references/bluetooth.md` |
| **Make an app start at boot, replace the home menu** | `references/autostart.md` |
| Decode the jargon (`br0`, RNDIS, NS2009, tslib, maskrom, …) | `references/glossary.md` |

## Triage: it's broken, where do I look?

| Symptom | First move |
|---|---|
| Nothing on `10.1.2.3` (no ping) | `scripts/m10-net-setup.sh --status` → `board-link.md` |
| SSH works, screen dark or blank | `recovery.md` §2 — `DISPLAY=:0`, lightdm, blanking (already off here) |
| GUI script exits immediately | read `/tmp/app.err` (`paramiko.md`); check `DISPLAY=:0` |
| Two windows / nonsense screenshot | duplicate instances — kill all, deploy one (`recovery.md` §3) |
| Content clipped on the right | board is portrait; re-apply `Rotate` (`m10-api.md` §7) |
| `pinpong` calls silently do nothing | `Board().begin()` missing, or GD32 never burned (`system.md`) |
| Touch lands in the wrong place | no `/etc/pointercal` — fit one (`m10-api.md` §9) |
| Mic silent / picks the wrong device | `m10-api.md` §5 — skip `Loopback`, use `hw:1,0` |
| No sound / USB speaker silent | `recovery.md` §4 — `lsusb` first (is it detected?), then PulseAudio, then the silent-success trap (`recovery.md` §4) |
| `apt` 404s | Debian 10 EOL → archive sources (`system.md`) |
| App is not running after a reboot | nothing supervises it — set up autostart (`autostart.md` §3) |
| Autostarted app black-panels or double-draws | `autostart.md` §6 — one panel, one owner (home menu off) |
| Board boots but is empty / portrait / offline | that is a fresh flash — post-flash checklist (`flash-firmware.md`) |
| Anything else | `scripts/m10-smoke.py` first, then the table in `health-check.md` |

## Red lines

These need an explicit **yes** from the user; they destroy state, change the
**host machine**, or hide the evidence:

- **Changing the host PC's network state** — addresses, routes, links, DNS,
  interfaces, NetworkManager profiles, VPN/TUN config. This is a hard stop:
  get approval for **each specific command**, and never infer it from approval
  of a previous one. `pkexec`/`sudo` is not itself permission. Read-only
  diagnosis (`--status`, `ip addr show`, `ip route get`, `ip neigh`, `ping`,
  `lsusb`) is always fine. `board-link.md` §"Host network changes".
- **Reflashing the board** — wipes `/root/`, Wi-Fi profiles, landscape config.
  `flash-firmware.md`.
- **`apt upgrade`** — the image already has Buster's EOL patches; a blanket
  upgrade can demand downgrades and move the held kernel. Install selectively.
- **Killing a running app** — "deploy" means leave it running. Stop it only on
  request, and prefer SIGINT (releases GPIO/framebuffer).
- **Pulling power** instead of `poweroff`/`reboot` — corrupts the eMMC.
- **`ip addr add` for the USB link** — works until re-enumeration, then hides the
  failure. Use the NetworkManager profile; the only exception is an on-demand
  bench with NetworkManager inactive (`board-link.md`) — and even then it is a
  **host network change**, so ask first.
- **`pkill -f 'app.py'`** without the bracket trick (`'[a]pp.py'`) — matches the
  killing shell itself.

## Non-negotiables

1. **Never touch the host PC's network without explicit, per-command
   approval.** Drivers, addresses, routes, NM profiles, VPN exclusions — all of
   it. Diagnose read-only and present the exact command; the user runs it or
   says yes. The board's own config over SSH is *not* covered by this rule (it
   is the normal workflow; it has its own red lines above) →
   `references/board-link.md`.
2. **`Board().begin()` before any pinpong object.** Otherwise `button_a`,
   `buzzer`, `light`, … exist as globals but every call no-ops or raises.
3. **Don't fix the USB link with `ip addr add`.** It silently disappears when
   the gadget re-enumerates → `references/board-link.md`. The one exception is
   an on-demand bench with NetworkManager inactive.
4. **Launch GUI/`while True:` scripts in the background** with `DISPLAY=:0`.
   A foreground `exec_command` blocks until timeout (`PipeTimeout`) →
   `references/paramiko.md`.
5. **`buzzer.pitch(freq, beat)` takes an integer beat count, not milliseconds,
   and blocks** while it sounds. Use `buzzer.pitch(freq)` for a non-blocking
   tone → `references/m10-api.md`.
6. **`fill_rect` has no radius.** Use `fill_round_rect(...)`, which does take
   `r=`, for anything round; `fill_circle` takes its x,y as the **centre** →
   `references/gui-drawing.md`.
7. **`apt` is broken on this image** (Debian 10 EOL, 404s). Repoint to
   `archive.debian.org` before installing anything → `references/system.md`.
8. **No onboard speaker, but there *is* an onboard mic.** Skip ALSA devices
   named `Loopback` → `references/m10-api.md`.
9. **Mic capture is silent at factory gain.** The preamp ships at 0 dB; set
   `amixer -c 1 cset numid=1 3` (20 dB) or every clip peaks ~96 and ASR hears
   nothing. It does not survive a reboot → `references/speech.md`. Related:
   capture the acodec **stereo and take the left** (a mono downmix halves it),
   and accumulate short reads — an unbuffered child pipe's `read(n)` does not
   return `n` bytes, which breaks any fixed-frame protocol.
10. **PIL 9.0.1 here cannot decode RGB565.** Decode `/dev/fb0` by hand →
   `references/verify-gui.md`.
11. **Vosk (and only Vosk) needs the Debian 11 `libstdc++` preload** →
   `references/speech.md`.
12. **A flash is a reimage, not an upgrade.** It wipes `/root/`, the Wi-Fi
    profiles, and the landscape `Rotate` config (the board returns portrait
    240×320), so back up — and re-apply landscape — every time →
    `references/flash-firmware.md`.
13. **Touch arrives as raw, uncalibrated 12-bit ADC.** There is no
    `/etc/pointercal` on the image, so the X/tslib path is dead until you fit
    one; evdev + your own affine works out of the box →
    `references/m10-api.md` §9.
14. **The panel has one owner.** The home menu (`PyboardUI`) and your app both
    draw to the framebuffer, so autostart *replaces* the
    `systemctl --user start PyboardUI` line in `/root/.xsessionrc` — never
    `rc.local` or a system unit, which get none of the session
    (`DISPLAY`/`XAUTHORITY`/`XDG_RUNTIME_DIR`) → `references/autostart.md`.

## Conventions

- **`python3 -m py_compile` before an SSH round trip** catches a syntax error
  or truncated SFTP write cheaply; `scripts/m10-deploy.py` does it for you.
- **Leave the board clean** — one instance at a time (`pgrep -af '[a]pp.py'`
  before trusting a screenshot; the bracket stops grep matching itself), no
  stray test files in `/root/`. Finish a deploy with `m10-deploy.py` + a
  snapshot.
- **"Deploy" = push + launch in the background + leave running.** GUI scripts
  never exit on their own; stop one only on request, SIGINT first (it
  releases GPIO/framebuffer) — this is also a red line.
- **A reboot ends a deploy.** Nothing restarts a hand-launched app; if the
  bench must survive power cycles, supervise it as a user unit →
  `references/autostart.md`.


## Quick start

The fast path is three scripts (all take `M10_HOST/USER/PASS` from the env and
default to `10.1.2.3` / `root` / `dfrobot`):

```bash
scripts/m10-smoke.py                       # is it healthy? versions? screen?
scripts/m10-deploy.py app.py               # push, kill stale, run in background, logs
scripts/m10-snapshot.py --rotate 90        # pull the framebuffer, landscape
```

Under the hood that is paramiko. Write it yourself when you need something
custom:

```python
import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.1.2.3", username="root", password="dfrobot", timeout=10)

def run(cmd, t=20):                      # exec + capture both streams
    _, so, se = c.exec_command(cmd, timeout=t)
    return so.read().decode(errors="replace") + se.read().decode(errors="replace")

c.open_sftp().put("app.py", "/root/app.py")
run("pkill -KILL -f '[a]pp.py'; sleep 1", 5)
run("cd /root && export DISPLAY=:0 && (python3 app.py > /tmp/app.out 2> /tmp/app.err &)", 5)
```

Then verify with a framebuffer snapshot (`references/verify-gui.md`) or by
reading the logs (`references/paramiko.md`). If `10.1.2.3` does not answer,
start with `references/board-link.md`.

## Tools in this skill

| Script | Purpose |
|---|---|
| `scripts/m10-smoke.py` | connectivity, versions, coprocessor, mic, display, snapshot |
| `scripts/m10-deploy.py` | push + restart one script, check for duplicates, show logs |
| `scripts/m10-snapshot.py` | RGB565 framebuffer → PNG on the PC (`--rotate`, `--census`) |
| `scripts/m10-net-setup.sh` | durable `10.1.2.2/24` on the USB gadget NIC. **Host network change — needs explicit approval; `--status` is read-only** |
| `scripts/m10-clash-exclude.sh` | keep `10.1.2.0/24` out of a Clash Verge TUN. **Host config change — needs explicit approval; `--status` is read-only** |
| `scripts/m10-trim-services.py` | disable DFRobot's daemons, free ~55 MB |
| `scripts/m10-offline-install.py` | manifest-driven offline wheels/debs/models + import/ABI checks |
| `scripts/check-docs.py` | validate this skill's file/section references (dev tool) |

Templates (copy, rename, deploy):

| Template | Starting point for |
|---|---|
| `templates/hello_gui.py` | any screen: background + text + 30 FPS loop |
| `templates/animated_face.py` | a `config()`-driven character: moods, blink, gaze |
| `templates/push_to_talk.py` | mic thread + queue + Vosk + one state machine |

## Related material

`SKILL.md` and `references/` are the canonical how-to. The `g-buddy` repo
(`AGENTS.md`, `gbuddy.py`, `scripts/`) is the board-specific instance: instance
facts, board wiring, the capstone program, the USB-link repair script, and
host-specific deploy helpers. Read the skill first — the repo is where the
board-specific instance lives, not a parallel copy of this material.
