---
name: m10-dev
description: "Develop and deploy Python for the DFRobot UNIHIKER M10 (RK3308, Debian 10 SBC) over USB-C: reach and repair 10.1.2.3, Wi-Fi, paramiko SSH/SFTP, deploy and background-run scripts, framebuffer screenshots, unihiker GUI/animation, pinpong GPIO/sensors/buttons/buzzer/LED, touch, mic/audio, landscape, packages/services, offline and cloud STT/TTS, and rkdeveloptool firmware flashing. Triggers: UNIHIKER, M10, K10, pinpong, unihiker, dfrobot, 10.1.2.3, \"the board\", board deploy, framebuffer, touchscreen, Vosk, Azure Speech, reflash, rkdeveloptool, maskrom."
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
| Azure Speech (real-time STT + neural TTS) | `references/azure-speech.md` |
| Prove a GUI rendered, from `/dev/fb0` | `references/verify-gui.md` |
| **X/app/audio wedged, board unresponsive, how to reboot** | `references/recovery.md` |
| **Flash/reflash firmware** from Linux with `rkdeveloptool` — destructive, read first | `references/flash-firmware.md` |
| Decode the jargon (`br0`, RNDIS, NS2009, tslib, maskrom, …) | `references/glossary.md` |

## Triage: it's broken, where do I look?

| Symptom | First move |
|---|---|
| Nothing on `10.1.2.3` (no ping) | `scripts/m10-net-setup.sh --status` → `board-link.md` |
| SSH works, screen dark or blank | `recovery.md` §2 — `DISPLAY=:0`, lightdm, `xset` blanking |
| GUI script exits immediately | read `/tmp/app.err` (`paramiko.md`); check `DISPLAY=:0` |
| Two windows / nonsense screenshot | duplicate instances — kill all, deploy one (`recovery.md` §3) |
| Content clipped on the right | board is portrait; re-apply `Rotate` (`m10-api.md` §7) |
| `pinpong` calls silently do nothing | `Board().begin()` missing, or GD32 never burned (`system.md`) |
| Touch lands in the wrong place | no `/etc/pointercal` — fit one (`m10-api.md` §9) |
| Mic silent / picks the wrong device | `m10-api.md` §5 — skip `Loopback`, use `hw:1,0` |
| No sound | no onboard speaker; USB speaker + `pulseaudio` (`recovery.md` §4) |
| `apt` 404s | Debian 10 EOL → archive sources (`system.md`) |
| Board boots but is empty / portrait / offline | that is a fresh flash — post-flash checklist (`flash-firmware.md`) |
| Anything else | `scripts/m10-smoke.py` first, then the table in `health-check.md` |

## Red lines

These need an explicit **yes** from the user; they destroy state or hide the
evidence:

- **Reflashing the board** — wipes `/root/`, Wi-Fi profiles, landscape config.
  `flash-firmware.md`.
- **`apt upgrade`** — the image already has Buster's EOL patches; a blanket
  upgrade can demand downgrades and move the held kernel. Install selectively.
- **Killing a running app** — "deploy" means leave it running. Stop it only on
  request, and prefer SIGINT (releases GPIO/framebuffer).
- **Pulling power** instead of `poweroff`/`reboot` — corrupts the eMMC.
- **`ip addr add` for the USB link** — works until re-enumeration, then hides the
  failure. Use the NetworkManager profile.
- **`pkill -f 'app.py'`** without the bracket trick (`'[a]pp.py'`) — matches the
  killing shell itself.

## Non-negotiables

1. **`Board().begin()` before any pinpong object.** Otherwise `button_a`,
   `buzzer`, `light`, … exist as globals but every call no-ops or raises.
2. **Never fix the USB link with `ip addr add`.** It silently disappears when
   the gadget re-enumerates → `references/board-link.md`.
3. **Launch GUI/`while True:` scripts in the background** with `DISPLAY=:0`.
   A foreground `exec_command` blocks until timeout (`PipeTimeout`) →
   `references/paramiko.md`.
4. **`buzzer.pitch(freq, beat)` takes an integer beat count, not milliseconds,
   and blocks** while it sounds. Use `buzzer.pitch(freq)` for a non-blocking
   tone → `references/m10-api.md`.
5. **`fill_rect` has no radius.** Use `fill_round_rect(...)`, which does take
   `r=`, for anything round; `fill_circle` takes its x,y as the **centre** →
   `references/gui-drawing.md`.
6. **`apt` is broken on this image** (Debian 10 EOL, 404s). Repoint to
   `archive.debian.org` before installing anything → `references/system.md`.
7. **No onboard speaker, but there *is* an onboard mic.** Skip ALSA devices
   named `Loopback` → `references/m10-api.md`.
8. **PIL 9.0.1 here cannot decode RGB565.** Decode `/dev/fb0` by hand →
   `references/verify-gui.md`.
9. **Vosk (and only Vosk) needs the Debian 11 `libstdc++` preload** →
   `references/speech.md`.
10. **A flash is a reimage, not an upgrade.** It wipes `/root/`, the Wi-Fi
    profiles, and the landscape `Rotate` config (the board returns portrait
    240×320), so back up — and re-apply landscape — every time →
    `references/flash-firmware.md`.
11. **Touch arrives as raw, uncalibrated 12-bit ADC.** There is no
    `/etc/pointercal` on the image, so the X/tslib path is dead until you fit
    one; evdev + your own affine works out of the box →
    `references/m10-api.md` §9.

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
| `scripts/m10-net-setup.sh` | durable `10.1.2.2/24` on the USB gadget NIC |
| `scripts/m10-trim-services.py` | disable DFRobot's daemons, free ~55 MB |
| `scripts/check-docs.py` | validate this skill's file/section references (dev tool) |

Templates (copy, rename, deploy):

| Template | Starting point for |
|---|---|
| `templates/hello_gui.py` | any screen: background + text + 30 FPS loop |
| `templates/animated_face.py` | a `config()`-driven character: moods, blink, gaze |
| `templates/push_to_talk.py` | mic thread + queue + Vosk + one state machine |

## Related material

`SKILL.md` and `references/` are the canonical how-to. The `g-buddy` repo
(`AGENTS.md`, `examples/README.md`, `scripts/`) is the reference implementation:
runnable demos, the USB-link repair script, and host-specific deploy helpers.
Read the skill first — the repo is where the board-specific instance lives, not
a parallel copy of this material.
