# Changelog

The skill is installed by symlink, so the version matters: bump the minor
version for new references or tools, the patch version for corrections.

## 0.6.0 — 2026-10-20

- **GUI verification is now "grab the framebuffer and look at the PNG".**
  `verify-gui.md` was built around an ASCII-art downsample as "the single most
  useful trick" — a workaround for not being able to see the image. That
  approximation is gone. The reference now leads with
  `scripts/m10-snapshot.py --rotate 90` plus a five-step reading order
  (is it our app at all → orientation/clipping → layout → colour → text →
  state), and keeps the RGB565 decode, palette and colour census as the
  numeric follow-ups they are.
- **`scripts/m10-snapshot.py --crop X,Y,W,H --zoom N`.** Nearest-neighbour
  upscale (and optional crop after rotation) so a 12 px legend row or a single
  widget can be *read* in the image instead of being described in ASCII. The
  crop clamps to the frame rather than raising, because a hand-typed box is
  normally approximate.
- `paramiko.md`, `gui-drawing.md`, `m10-api.md` and `README.md`: dropped their
  "ASCII render" phrasing in favour of the PNG grab.
- `verify-gui.md`: new first gotcha — **a dead app looks like a rendering bug**.
  A stock `pyboardgui` launcher screen means the process exited; check
  `/tmp/<app>.err` before theorising about layout.

## 0.5.1 — 2026-10-19

- **`scripts/m10-deploy.py` actually launches now.** The launch line was
  `cd <dir> && DISPLAY=:0 PYTHONUNBUFFERED=1 (cmd > out 2> err &)` — an
  assignment prefix cannot precede a subshell, so bash rejected the whole
  command and the app never started. The script printed `launched:` anyway
  and only later reported `NOT RUNNING`, with empty logs, so it looked like
  a silent app crash. It now uses `export DISPLAY=:0 PYTHONUNBUFFERED=1 &&`
  and prints `launch failed:` when the shell returns anything at all, so a
  broken launch is loud at the point it happens.
- `README.md`: current version was still 0.4.1 after the 0.5.0 release.

## 0.5.0 — 2026-10-19

- **New `scripts/m10-clash-exclude.sh`** (from the `g-buddy` repo's `scripts/`):
  appends `10.1.2.0/24` to Clash Verge's `Merge.yaml` and reports whether
  mihomo already routes `10.0.0.0/8` DIRECT; `--status` is diagnose-only.
- `board-link.md` now points at it instead of the repo-local copy.

## 0.4.1 — 2026-10-19

- `board-link.md`: the Clash Verge TUN exclusion now points at the repo's
  `clash-m10-exclude.sh`; the host variant of the network script was retired.

## 0.4.0 — 2026-10-19

- **New `scripts/m10-offline-install.py`** — manifest-driven offline install:
  recursive SFTP, `dpkg-deb -x`, index-free pip, import checks, `LD_PRELOAD`
  ABI load test, `py_compile`; `--dry-run`, `--allow-missing`, strict schema.
- **New `templates/offline-manifest.example.json`**; CI validates the schema.
- `system.md` and `speech.md` now use the tool instead of ad-hoc snippets.
- Retires the repo-local `deploy-offline.py` in favour of a pinned
  `offline/manifest.json` plus this tool.

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
