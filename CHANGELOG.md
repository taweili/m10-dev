# Changelog

The skill is installed by symlink, so the version matters: bump the minor
version for new references or tools, the patch version for corrections.

## 0.9.0 — 2026-10-23

- **New reference `references/autostart.md` — run a GUI app at boot.** The
  measured chain, with boot timestamps: `graphical.target` → `lightdm` (autologin
  `root`) → Xorg on `:0` → **`/root/.xsessionrc`** → `systemctl --user start
  <unit>`. So a *user* systemd unit in `/etc/systemd/user/`, started from the
  same file DFRobot uses for its home menu, is the supported hook; `rc.local`
  (measured: it runs *after* lightdm here but inherits no session env at all),
  system units (no session bus/`/run/user/0`), XDG autostart (no DE reads it)
  and `cron @reboot` are documented as the wrong answers, with reasons. Ships a template unit (env, `Restart=on-failure`, `KillSignal=SIGINT`,
  file: logs, explicit `/usr/bin/python3`), the `XDG_RUNTIME_DIR=/run/user/0`
  tax on every `systemctl --user` over SSH, one-panel-one-owner, cold-boot
  failure modes, an acceptance test that is a **reboot** (not a `start`), and
  undo. Wired into `SKILL.md` (map, orientation, triage ×2, non-negotiable 13,
  a convention) and cross-referenced from `system.md`, `recovery.md`,
  `paramiko.md`, `health-check.md`, `m10-api.md`.
- **Fixed: the user-session services were described wrongly.** `PyboardUI`,
  `PyboardWeb`, `SIoT`, `FileShare`, `ScreenShare` and `Jupyter` are **static**
  units in `/usr/lib/systemd/user/` launched by a line in `/root/.xsessionrc`,
  so `systemctl --user disable` is a no-op and `stop` lasts until the next
  login. The durable switch is that file — `system.md` now says so, and
  `scripts/m10-trim-services.py` comments the line out (with a `.bak`),
  `--keep-home-menu` to opt out. Also: Pulse is a **user** unit enabled in
  root's `default.target`, so `systemctl restart pulseaudio` fails; `recovery.md`
  §4.2 now drives it with `systemctl --user` (+ runtime dir) and explains that
  a missing `XDG_RUNTIME_DIR` looks exactly like a dead daemon.
- **Fixed: `m10-smoke.py`'s framebuffer check was vacuous.** `/dev/fb0` is a
  *character* device, so `stat -c %s` always answers 0 — the check had been
  WARNing on every board. It now sizes the panel from
  `/sys/class/graphics/fb0/{virtual_size,bits_per_pixel}` (240×320 @ 16 bpp =
  153600 B) and proves a full read with `dd`. `health-check.md`'s manual
  equivalent was the same bad command; both corrected.
- **New `session` check in `m10-smoke.py`:** lightdm autologin user, the
  non-comment `.xsessionrc` autostart lines, home menu on/off, and which app is
  drawing the panel — `FAIL` on two owners, `WARN` when nothing draws (the
  black-panel state). Documented in `health-check.md`.
- **Versions without `pip3`.** Measured: `pip3 --version` 6 s, `pip3 list` 13 s,
  `pip3 show unihiker` **>25 s** at full CPU. Everything now reads the dist-info
  directory name instead (`unihiker-0.0.28.5`, `pinpong-0.6.1`) — smoke,
  `health-check.md`, `system.md`, `flash-firmware.md`, `gui-drawing.md` — and
  smoke WARNs when `python3` on `PATH` (the pyenv shim on v0.4.1+) disagrees
  with `/usr/bin/python3`.
- **`m10-deploy.py --unit`:** with an autostarted app, the old kill-then-launch
  would be undone by `Restart=on-failure` and end with two panel owners. The new
  flag delegates to `systemctl --user restart` and reports
  `ActiveState`/`MainPID`/`NRestarts` plus `journalctl --user`. Verified on the
  bench (one instance, `NRestarts=0`).
- **`bluetooth.md`:** folded in the pending note that the sink appears 1–3 s
  *after* `Connected: yes`, so poll (~10 s) instead of testing once — with the
  repo-specific pointer replaced by the board-generic rule.
- **Corrections and measurements:** blanking is already off (`xserver-command=X
  -s 0 -dpms` in `lightdm.conf`), so a black panel is usually the app, not the
  backlight; `python3` is the pyenv shim on v0.4.1+ (`pyenv global` = `system`
  on v0.4.2, so it resolves to 3.7.3 *by luck*); idle memory measured 111 MB
  used / 299 MB available as shipped; `StandardOutput=file:` truncates per start
  on systemd 241 (and `journalctl --user` can report "No entries" here);
  restarting an app that holds an ALSA capture device can log one
  `[Errno -9999]` while the old instance releases `hw:1,0`; `m10-snapshot.py
  --census` no longer triggers Pillow's `Image.getdata` DeprecationWarning (it
  is on by default in smoke's snapshot detail). The "phantom input
  at boot" is documented as **observed but not isolated** — two turns inside the
  first 100 s of one boot, not reproduced on restarts — with "ignore contacts
  for the first ~2-3 s" as cheap insurance rather than as a driver fact.

## 0.8.2 — 2026-10-23

- **Recorded what Piper costs next to Vosk in one process** (`references/speech.md`,
  "Piper next to Vosk"): the two coexist on the 512 MB board (peak 308 MB used of
  the 423 MB `free` reports, no OOM), but a "listen, then answer out loud" turn
  costs 15-25 s — 10-14 s of piper for a 2-4 s utterance (RTF 4.5-6.9 including
  the ~5 s one-shot voice load) plus playback. The guidance that follows: speak
  after the text is on screen, on a worker thread, cancellable. Measured while
  adding voice-out to `gbuddy.py` on the bench.

## 0.8.1 — 2026-10-23

- **Dropped every repo-specific `examples/` reference.** The skill is meant to
  be self-contained board-generic how-to; pointing at the g-buddy repo's demo
  scripts (`examples/03`, `04`, `05`, `08`) and its `examples/README.md` entangled
  the two repos. The three `examples/04_push_to_talk_stt.py` references now point
  at the skill's own `templates/push_to_talk.py` (same mic-thread + queues +
  `--file` architecture). The two scripts with no template — the touch playground
  and the TTS hello-world — had their idioms inlined instead: the touch section
  now describes the `evdev` + Tk shape to copy, and the TTS section states the
  `pactl`-dispatch idiom directly. Also: `paramiko.md`'s SFTP example uses a
  generic `app.py`, `system.md` drops the "keep the repo's `examples/` flat"
  aside, `m10-deploy.py`'s usage line uses `app.py`, and the "Related" sections
  in `README.md` / `SKILL.md` point at `AGENTS.md` + `gbuddy.py`. DFRobot wiki
  links, the on-board `/opt/unihiker/examples` directory, the
  `offline-manifest.example.json` template, and this changelog's own history are
  untouched. `scripts/check-docs.py` 16 files, 0 errors, 0 warnings; `py_compile`
  clean on the touched script.

## 0.8.0 — 2026-10-23

- **New hard rule: never change the host PC's network without explicit,
  per-command approval.** Written up in three places so it is met before the
  command, not after: `SKILL.md` red lines (new first bullet) and
  non-negotiable 1, `board-link.md` §"Host network changes need explicit
  approval" (what counts — addresses, routes, links, DNS, NM profiles, driver
  rebinds/`modprobe -r`, `rfkill`, VPN/TUN config — what is safe read-only, and
  that a re-enumeration means asking again rather than re-running), plus a
  header warning in `m10-net-setup.sh` and `m10-clash-exclude.sh`. Every
  call site that said "just run `m10-net-setup.sh`" now says ask first.
  Triggered by a `pkexec ip addr add` that was run on the strength of a
  general "use pkexec".
- **`m10-offline-install.py`: new `untar` manifest key** — pushes a `.tar.gz`
  and extracts it on the board, so a prebuilt ARM bundle keeps its exec bits,
  symlinks and internal layout (SFTP `put` gives 0644 and follows symlinks,
  which quietly breaks Piper). Also fixed `debs`: it was handing the manifest's
  *local* path to `dpkg-deb` on the board; the `.deb` is now staged under
  `/tmp/offline/debs/` first. Documented in `system.md`.
- **`speech.md`: Piper section rewritten from measured facts.** v1.2.0 bundle
  needs no `libstdc++` preload (`GLIBC_2.25`/`GLIBCXX_3.4.21` vs buster's
  2.28/3.4.25) and finds its bundled `.so`s via `RUNPATH=$ORIGIN`; text goes on
  **stdin** (positional text is 1.3.0+); `--espeak_data` should be explicit.
  Speed is **not** what the Pi 4 numbers suggest: on the RK3308 the voice loads
  in 4.2–5.8 s per invocation and inference runs at RTF ≈ 1.97, so a short
  sentence is ~8 s. Added a playback-by-output-device table (A2DP `paplay`,
  USB `aplay -D hw:N,0`, `unihiker.Audio()` when Pulse is the right layer).
- **`bluetooth.md`: "connected but no sink".** `bluetoothctl` can report
  `Connected: yes` while `pactl` has no `bluez_sink` and has fallen back to the
  silent `acodec` card; cycling disconnect/connect **with Pulse running** makes
  `module-bluez5-device` recreate the card (the card index changes — that is
  the proof). Recorded as a new gotcha.
- **`m10-smoke.py`: timeouts.** Default `run()` 20 s → 45 s (a cold-boot
  `pip3 show` blew the channel timeout and killed the whole run with a
  `PipeTimeout` traceback), and `OSError`/`SSHException` now degrade to a
  `WARN`/`FAIL` on that one check instead of aborting the script.

## 0.7.2 — 2026-10-23

- **`recovery.md` §4 (Audio recovery) rewritten.** The old section was four
  lines (`aplay -l`, `pactl info`, `systemctl restart pulseaudio`,
  `alsactl restore`) and a single "reseat the speaker" sentence. It missed
  every failure mode we actually hit while trying to use a USB speaker:
  - **§4.1 Is the USB speaker detected at all?** — the critical first step:
    `lsusb` must list the speaker, not just root hubs. Documents the USB-A
    port → bus mapping (Bus 02 EHCI / Bus 03 OHCI; USB-C gadget is Bus 01),
    the `snd-usb-audio` module load failure (`Exec format error` → reflash),
    and the powered-hub / data-cable / current-limit causes.
  - **§4.2 PulseAudio** — on a trimmed bench the `pulseaudio.service` unit is
    masked, so `systemctl restart` fails with "Unit file does not exist".
    Documents `pulseaudio --start` as the ad-hoc workaround (runs as a user
    daemon under `/run/user/0/pulse/`).
  - **§4.3 The silent-success trap** — `aplay`/`paplay`/`Audio.play()` all
    return exit 0 even when no speaker is wired to the DAC. The onboard codec
    (`card 1`, `rk3308-acodec`) has no physical output, so audio routed there
    goes nowhere audible. Documents how to tell a real sink from the codec
    and confirms the buzzer as the always-works fallback.
  - Escalation table row updated from "aplay -l, restart pulseaudio" to the
    new three-step ladder.

- **`m10-api.md` §5**: added a callout pointing to `recovery.md` §4 for USB
  speaker detection issues, with the USB-A port → bus mapping inline.

- **`SKILL.md` triage**: the "No sound" row now points to the §4 ladder
  instead of the old one-liner.

## 0.7.1 — 2026-10-23

- **`recovery.md` §2**: added the "app crashed + home menu disabled" case.
  When a trimmed board (`scripts/m10-trim-services.py`) has no `pyboardgui`
  running, a crashed app leaves the panel black instead of returning to the
  home screen. Previously undocumented — the recovery ladder assumed the home
  menu was always present. Added to the escalation table as well.

- **`board-link.md`**: new "Exception: on-demand boards, NetworkManager
  inactive" subsection. The "Do not use `ip addr add`" rule assumed NM was
  running; on a bench where the board is plugged in only when needed and NM is
  disabled, a per-session `ip addr add` is the only pragmatic option. The
  reference now documents the exception, points to
  `scripts/m10-net-setup.sh --status` (which detects the NIC via sysfs and
  works without NM), and adds a failure-mode row.

- **`SKILL.md` red line**: softened the absolute "never `ip addr add`" to
  acknowledge the on-demand exception, with a cross-reference to
  `board-link.md`.

- **AGENTS.md**: removed the generic content that moved to the skill (black
  screen consequence, `ip addr add` rationale); kept only instance-specific
  facts.

## 0.7.0 — 2026-10-20

- **`references/azure-speech.md` rewritten for the M10's real constraints.**
  The reference had three factual problems and one structural gap:
  - **Version was wrong.** It said "1.11+" as if anything recent would work;
    the current PyPI release is 1.52.0, and 1.38.0+ links against
    `GLIBC_2.29`, which the M10's Debian 10 glibc 2.28 rejects at
    `import` (`OSError: version 'GLIBC_2.29' not found`). 1.34.0 is the
    newest that actually loads — now pinned explicitly, with a note that
    1.30.0 and 1.25.0 also work if you need to go back further.
  - **API drift undocumented.** SDK 1.43 added `SpeechConfig.from_endpoint()`;
    1.34.0 doesn't have it. Everything in the file used the newer form,
    which would `AttributeError` on this board. All examples now use
    `SpeechConfig(subscription=KEY, endpoint=URL)` and the file has an
    explicit drift table (`Translator` → `translation.TranslationRecognizer`, etc.).
  - **No M10-integration specifics.** The old reference was generic Azure
    Speech material that duplicated the SDK quickstart. The rewrite adds
    what's specific to running this on the M10:
    - push-stream STT pattern wired to pyaudio (mirrors `g-buddy`'s `03`
      mic thread) — because the M10's default mic path is unreliable when
      pulseaudio is masked
    - raw-PCM TTS (`Raw24Khz16BitMonoPcm`) → pyaudio playback — avoids both
      the WAV-header-parsing dance and the PulseAudio dependency
    - word-boundary callbacks with the tick→sample conversion
    - F0 quota math including the practical 20-tx/60-s throttle
    - round-trip latency budget (3–8 s end to end)
    - M10-specific troubleshooting table (stale clock → TLS failure, etc.)
    - offline-install path (the Azure wheel added to `g-buddy`'s
      `offline/manifest.json`; version-pinned `pip install ==1.34.0`)
  - **No numbered sections.** Added `§7.1`–`§7.8` so the file matches the
    `§N` cross-reference convention the rest of the skill uses.

- `README.md`: current version → 0.7.0.

## 0.6.2 — 2026-10-20

- **`SKILL.md`: new "Conventions" section** consolidating the generic workflow
  rules that used to live in the `g-buddy` repo's `AGENTS.md` (py_compile
  before an SSH round trip; leave the board clean — one instance at a time,
  no stray test files, finish a deploy with deploy + snapshot; deploy = push
  + launch + leave running). The bench file now records only instance facts
  and points at the skill for board how-to instead of duplicating its
  reference map, triage table, red lines and quick-start path.

## 0.6.1 — 2026-10-20

- `references/system.md`: clarified the "Do NOT disable PulseAudio" rule. The
  `unihiker` **`Audio` API** needs it, but a script that records/plays via
  `pyaudio`/`arecord` on the ALSA device directly does **not** — so a bench
  whose apps all use `pyaudio` (like `g-buddy`'s 03) can mask pulse. The
  default keep-list is unchanged; this just stops the rule from reading as
  "pulse is always required".

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
