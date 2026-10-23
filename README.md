# m10-dev

A skill for developing Python on the **DFRobot UNIHIKER M10** from an **Omarchy** host.

The M10 is a Debian 10 SBC with a fixed USB-C ethernet gadget at `10.1.2.3`, a
2.8" 240×320 touchscreen, an on-board mic, buttons, buzzer, and GPIO via
`pinpong`. You author Python on the PC (Omarchy — Arch + Hyprland) and push it
to the board over paramiko. Nothing is on the board until you push it.

This repo is packaged as an agent skill: an `SKILL.md` entry point the agent
reads on trigger, self-contained references it reads on demand, and the scripts
and templates it needs to act.

Current version: **0.8.0** (`CHANGELOG.md`).

## Layout

```
SKILL.md                    # entry point — orientation, triage, red lines, non-negotiables
references/
  health-check.md           # 0  is it healthy? versions, definition of done, precedence
  board-link.md             # 1  get the board at 10.1.2.3; repair a dead USB gadget link
  wifi.md                   # 2  put the board on Wi-Fi (additive; USB link stays up)
  paramiko.md               # 3  SSH/SFTP, deploy, background exec, screenshots, SSH keys
  m10-api.md                # 4a unihiker GUI/audio + pinpong GPIO/sensors/buttons/buzzer
  gui-drawing.md            # 4b full drawing API, emoji sprites, animation + app patterns
  system.md                 # 5  Debian 10 EOL, apt fix, offline installs, services, disk/time
  speech.md                 # 6  STT/TTS: Vosk offline, Azure cloud
  azure-speech.md           # 7  Azure Speech real-time STT + neural TTS
  verify-gui.md             # 8  grab /dev/fb0 as a PNG and read it (PIL can't decode RGB565)
  flash-firmware.md         # 9  rkdeveloptool reflash (destructive — wipes the board)
  recovery.md               # 10 X/app/audio wedged, safe reboot, when to reflash
  glossary.md               # 11 jargon: br0, RNDIS, NS2009, tslib, maskrom, …
scripts/
  m10-smoke.py              # connectivity, versions, coprocessor, mic, display, snapshot
  m10-deploy.py             # push + restart a script, duplicate check, logs
  m10-snapshot.py           # RGB565 framebuffer -> PNG on the PC
  m10-net-setup.sh          # durable 10.1.2.2/24 on the USB gadget NIC
  m10-trim-services.py      # disable DFRobot's daemons, free ~55 MB
  m10-offline-install.py    # manifest-driven offline wheels/debs/models + checks
  check-docs.py             # validate file/section/anchor references (dev tool)
templates/
  hello_gui.py              # minimal screen
  animated_face.py          # config()-driven character (blink, gaze, moods)
  push_to_talk.py           # mic thread + queue + Vosk UI skeleton
  offline-manifest.example.json  # complete manifest for m10-offline-install.py
```

## Install

Drop this directory under your skills root. The agent auto-loads
`SKILL.md` when a trigger matches:

```
~/.agents/skills/m10-dev/        # general agent convention
~/.pi/agent/skills/m10-dev/      # pi
```

Symlinks work fine — keep a single canonical checkout and link it into each
skills root.

## How it works

`SKILL.md` is the only file the agent reads unconditionally; it carries the
orientation table, a triage table, the red lines, the numbered
**non-negotiables** (the foot-guns that break M10 work), and the tool inventory.
Each task links to one reference file, so the agent pulls in only what's needed
instead of loading the whole skill up front.

## Checks

```bash
scripts/check-docs.py                       # file refs, `§N` targets, anchors, frontmatter
scripts/m10-offline-install.py --manifest templates/offline-manifest.example.json \
  --dry-run --allow-missing                 # manifest schema
python3 -m py_compile scripts/*.py templates/*.py
bash -n scripts/*.sh
```

CI runs the same three on every push (`.github/workflows/check.yml`). The docs
check exists because section refs drift: it caught five dead paths the first
time it ran.

## Host assumptions

Written and tested on an **Omarchy** host (Arch + Hyprland). Two host facts the
flashing reference depends on, with fallbacks if your host differs:

- `pkexec` works passwordless — Omarchy ships a polkit rule for `wheel`, so
  `rkdeveloptool` flashing doesn't stall on a TTY password prompt. On other
  hosts, run it as root instead (`references/flash-firmware.md`).
- `7z` is already installed for unpacking the RK dev pack; `lsusb` may be
  absent and `dmesg` may be restricted — the flashing reference works around
  both with `sysfs` and `journalctl -k`.

The board itself is stock DFRobot firmware (v0.4.2), Debian 10, and EOL — so
`apt` is repointed to `archive.debian.org` before anything is installed
(`references/system.md`).

## Related

The `g-buddy` repo (`AGENTS.md`, `examples/`) is the reference
implementation: the six runnable demos and how to run them
(`examples/README.md`), plus the instance facts for one particular board. The
skill is self-contained — the repo is where a specific board's instance lives,
not a second copy of this material.
