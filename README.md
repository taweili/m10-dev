# m10-dev

A skill for developing Python on the **DFRobot UNIHIKER M10** from an **Omarchy** host.

The M10 is a Debian 10 SBC with a fixed USB-C ethernet gadget at `10.1.2.3`, a
2.8" 240×320 touchscreen, an on-board mic, buttons, buzzer, and GPIO via
`pinpong`. You author Python on the PC (Omarchy — Arch + Hyprland) and push it
to the board over paramiko. Nothing is on the board until you push it.

This repo is packaged as an agent skill: an `SKILL.md` entry point the agent
reads on trigger, plus self-contained references it reads on demand.

## Layout

```
SKILL.md                    # entry point — orientation table, non-negotiables, quick start
references/
  board-link.md             # 1  get the board at 10.1.2.3; repair a dead USB gadget link
  wifi.md                   # 2  put the board on Wi-Fi (additive; USB link stays up)
  paramiko.md               # 3  SSH/SFTP, deploy, background exec, screenshots
  m10-api.md                # 4a unihiker GUI/audio + pinpong GPIO/sensors/buttons/buzzer
  examples.md               # 4b runnable examples and the patterns they teach
  system.md                 # 5  Debian 10 EOL, apt fix, services to disable
  speech.md                 # 6  STT/TTS: Vosk offline, Azure cloud
  azure-speech.md           # 7  Azure Speech real-time STT + neural TTS
  verify-gui.md             # 8  prove a GUI rendered from /dev/fb0 (PIL can't decode RGB565)
  flash-firmware.md         # 9  rkdeveloptool reflash from Omarchy (destructive — wipe)
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
orientation table, the numbered **non-negotiables** (the foot-guns that break
M10 work), and a copy-paste paramiko quick start. Each section of
`SKILL.md` links to one reference file for the matching task, so the agent
pulls in only what's needed instead of loading ten thousand tokens up front.

## Host assumptions

The skill assumes an **Omarchy** host for two Omarchy-specific facts that
otherwise need workarounds:

- `pkexec` works passwordless — Omarchy ships a polkit rule, so
  `rkdeveloptool` flashing doesn't stall on a TTY password prompt
  (`references/flash-firmware.md`).
- `7z` is already installed for unpacking the RK dev pack; `lsusb` is not
  installed and `dmesg` is locked down — the flashing reference works around
  both.

The board itself is stock DFRobot firmware (v0.4.2), Debian 10, and EOL — so
`apt` is repointed to `archive.debian.org` before anything is installed
(`references/system.md`).

## Related

The worked examples this skill distils live in the `g-buddy` repo
(`AGENT.md`, `examples/`, `notes/`, `scripts/m10-network-setup.sh`). This
skill is self-contained, but that repo is the source of the raw research logs
and the runnable scripts.
