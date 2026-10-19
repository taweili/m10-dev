# Changelog

The skill is installed by symlink, so the version matters: bump the minor
version for new references or tools, the patch version for corrections.

## 0.3.0 — 2026-10-19

Consolidation pass: the skill is now self-contained and checkable.

- **New `references/health-check.md`** — 30-second health check, version /
  firmware compatibility matrix, definition of done, source precedence.
- **New `references/recovery.md`** — X/lightdm, blanking, wedged scripts,
  audio, safe reboot, when recovery ends and flashing begins.
- **New `references/glossary.md`** — hardware/Linux/display/audio/speech terms.
- **New `scripts/`** — `m10-smoke.py`, `m10-deploy.py`, `m10-snapshot.py`,
  `m10-net-setup.sh`, `m10-trim-services.py`, plus `check-docs.py`.
- **New `templates/`** — hello-world GUI, config()-driven animated face,
  push-to-talk STT skeleton.
- **SKILL.md** — triage table, red lines, precedence rule, shortened
  description, tools table; reference map now covers health/recovery/glossary.
- **`gui-drawing.md`** — full source-verified GUI API, emoji sprites, animation
  and app patterns (from the repo's drawing notes).
- **`m10-api.md`** — corrected §1 (rounded rects, `origin=` scope,
  `on_key_click`/`start_thread` signatures); new §9 touch input and §10
  expansion/camera/comms; audio gain and 3.3 V warnings; framebuffer decode
  deduplicated into `verify-gui.md`.
- **`system.md`** — offline wheel/deb installs, projects/venv, disk/tmpfs,
  time/NTP.
- **`speech.md`** — canonical Vosk decode loop.
- **`board-link.md`** — skill-hosted setup script, `nmcli` equivalent, access
  methods.
- **`verify-gui.md` / `paramiko.md`** — snapshot tooling, SSH keys, env config.
- Dropped `references/examples.md`; the demo inventory lives with the demos
  (`g-buddy/examples/README.md`).

## 0.2.0 — 2026-10-16

- Add `references/flash-firmware.md` (rkdeveloptool, maskrom, post-flash).
- Add `README.md`.
- Renumber the STT example to 04.

## 0.1.0 — 2026-10-16

- Initial skill: orientation, board link, Wi-Fi, paramiko, M10 API, examples,
  system, speech, Azure Speech, GUI verification.
