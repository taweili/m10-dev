---
name: m10-dev
description: Develop and deploy Python for the DFRobot UNIHIKER M10 (RK3308 Linux SBC). Use when working with an M10 over its USB-C link — reaching it at 10.1.2.3, repairing a broken USB link, joining Wi-Fi, SSH/SFTP via paramiko, deploying and running scripts, capturing framebuffer screenshots, or using the on-board hardware: unihiker GUI/Audio, pinpong GPIO/sensors/buttons/buzzer/LED, the onboard microphone, landscape rotation, Debian package/service maintenance, and offline or cloud speech-to-text and text-to-speech. Triggers: UNIHIKER, M10, K10, pinpong, unihiker, dfrobot, 10.1.2.3, "the board", board deploy, M10 mic/buzzer/buttons/screen, Vosk, Azure Speech.
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
| Transport | **paramiko only** — no `sshpass`/`expect` on the PC |
| Firmware | v0.4.0 snapshot from ~Feb 2023; Debian 10 is **EOL** → `apt` is broken out of the box |

## Reference map

Read the reference that matches the task; each is self-contained.

| Task | Reference |
|---|---|
| Get the board reachable at `10.1.2.3`; fix a dead USB link | `references/board-link.md` |
| Put the board on Wi-Fi | `references/wifi.md` |
| Dev environment: paramiko, deploy, run, stop, screenshots | `references/paramiko.md` |
| Use M10 functions: GUI, buttons, sensors, buzzer, audio, mic, framebuffer, landscape | `references/m10-api.md` |
| Runnable examples and the code patterns they teach | `references/examples.md` |
| OS, packages, `apt`/EOL fix, services to disable, reflash | `references/system.md` |
| Speech in and out: STT/TTS options, models, pipelines | `references/speech.md` |
| Azure Speech (real-time STT + neural TTS) | `references/azure-speech.md` |
| Prove a GUI rendered, from `/dev/fb0` | `references/verify-gui.md` |

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
5. **`apt` is broken on this image** (Debian 10 EOL, 404s). Repoint to
   `archive.debian.org` before installing anything → `references/system.md`.
6. **No onboard speaker, but there *is* an onboard mic.** Skip ALSA devices
   named `Loopback` → `references/m10-api.md`.
7. **PIL 9.0.1 here cannot decode RGB565.** Decode `/dev/fb0` by hand →
   `references/verify-gui.md`.
8. **Vosk (and only Vosk) needs the Debian 11 `libstdc++` preload** →
   `references/speech.md`.

## Quick start

```python
import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.1.2.3", username="root", password="dfrobot", timeout=10)

def run(cmd, t=20):                      # exec + capture both streams
    _, so, se = c.exec_command(cmd, timeout=t)
    return so.read().decode(errors="replace") + se.read().decode(errors="replace")

c.open_sftp().put("app.py", "/root/app.py")
run("pkill -KILL -f 'python app.py'; sleep 1", 5)
run("cd /root && export DISPLAY=:0 && (python app.py > /tmp/app.out 2> /tmp/app.err &)", 5)
```

Then verify with a framebuffer snapshot (`references/verify-gui.md`) or by
reading the logs (`references/paramiko.md`). If `10.1.2.3` does not answer,
start with `references/board-link.md`.

## Related material

A reference implementation of all of this lives in the `g-buddy` repo
(`AGENT.md`, `examples/`, `notes/`, `scripts/m10-network-setup.sh`). This skill
is self-contained and distils those notes; the repo remains the source of the
worked examples and the raw research logs.
