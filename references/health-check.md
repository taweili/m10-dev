# 0. Health check, versions, and what "working" means

> Reviewed 2026-10-19. This file is the version arbiter; the other references state their version assumptions at the top.

Read this first when you pick up a board you did not just configure. It answers
three questions in one run: **is it reachable, is the hardware alive, and which
software is actually on it** (the skill's notes assume a particular firmware and
`unihiker` wheel — both drift).

## The 30-second check

```bash
scripts/m10-smoke.py                 # full check, pulls a framebuffer snapshot
scripts/m10-smoke.py --no-snapshot   # skip the display check
```

It prints `PASS` / `WARN` / `FAIL` per check and exits non-zero if anything
failed:

| Check | What it proves |
|---|---|
| `connect` | SSH reachable (`references/board-link.md` if not) |
| `versions` | firmware marker, Debian, Python, `unihiker`, `pinpong`, PIL |
| `resources` | RAM headroom (512 MB total) and `/root` free space |
| `X display` | X is up on `:0`, and at which dimensions (portrait vs landscape) |
| `framebuffer` | `/dev/fb0` readable and 153 600 bytes |
| `coprocessor (GD32)` | `Board().begin()`, `light.read()`, `button_a.value()` |
| `microphone` | `Audio().sound_dBFS()` returns a level (noise floor ≈ −51) |
| `snapshot` | the full GUI → framebuffer → PC path, with a colour census |

`WARN` is not failure: a firmware newer than these notes, or PIL missing on the
PC, is expected drift. `FAIL` means stop and fix before drawing conclusions.

## Manual equivalent

When paramiko or the scripts are unavailable, the same checks by hand:

```bash
ssh root@10.1.2.3

cat /opt/unihiker/Version; cat /etc/debian_version; python3 --version
pip3 show unihiker pinpong | grep -E '^(Name|Version)'
python3 -c 'import PIL; print(PIL.__version__)'
free -m; df -h /root
DISPLAY=:0 xdpyinfo | grep dimensions
stat -c %s /dev/fb0                      # expect 153600

python3 - <<'PY'
from pinpong.board import Board
Board().begin()
from pinpong.extension.unihiker import light, button_a
print("GD32 OK | light=%s button_a=%s" % (light.read(), button_a.value()))
PY

python3 -c 'from unihiker import Audio; a=Audio(); print(a.sound_dBFS(), a.sound_level())'
```

## Version matrix — what the board actually is

The M10 shipped at **v0.4.0**; the skill's default assumptions are **v0.4.2**.
Check before relying on a feature.

| | v0.4.0 (as shipped) | v0.4.1 | v0.4.2 (latest official) | v0.4.5 (CDN only) |
|---|---|---|---|---|
| Debian | 10.11 Buster | 10.11 | 10.11 | 10.11 |
| Python | **3.7.3 only** | 3.7.3 + pyenv 3.8.5 / 3.12.7 | + 3.12.7 fixes | **default 3.12.7**, `uv` |
| `unihiker` | 0.0.27 | 0.0.28 | 0.0.28.5 | newer |
| `pinpong` | 0.6.1 | 0.6.x | 0.6.x | newer |
| `apt` sources | **broken (Buster EOL)** | archive.debian.org | archive.debian.org | archive |

`unihiker` has no `__version__` attribute — use `pip3 show unihiker`. The wheel
on PyPI can be newer than the board's; `gui-drawing.md` was read from
**0.0.29.0**, so if the board is on 0.0.27, check before using an extra
(`load_font`, `UNIConfig.set_brightness`, `add_text_box`) — the core drawing API
in that file is stable across both.

## Definition of done for a deploy

A deployed script is not "done" when the push succeeds:

1. `pgrep -af '[a]pp.py'` → **exactly one** process.
2. `/tmp/app.err` empty (or only known noise); `/tmp/app.out` has the expected
   first lines. Remember stdout is block-buffered — launch with
   `PYTHONUNBUFFERED=1`.
3. The framebuffer shows the expected state (`m10-snapshot.py --census`, or the
   colour census in `verify-gui.md`).
4. No regressions on the next health check.

`scripts/m10-deploy.py` does 1–2 for you (and prints both logs).

## When a check fails

| Failed check | Go to |
|---|---|
| `connect` | `board-link.md` — run `scripts/m10-net-setup.sh --status` |
| `X display` | `recovery.md` — X/lightdm restart, `DISPLAY` |
| `framebuffer` / `snapshot` | `verify-gui.md` — RGB565 decode, colours, tearing |
| `coprocessor` | `system.md` (firmware/`firstRun.sh`) and `m10-api.md` §1 |
| `microphone` | `m10-api.md` §5 — `Loopback` trap, gain |
| `resources` | `system.md` — trim services (`scripts/m10-trim-services.py`) |
| versions unexpected | `system.md` — firmware ladder; `flash-firmware.md` to move |

## Precedence when sources disagree

**Live board > shipped source > this skill > DFRobot wiki.** If a snippet fails
on the board, the board wins: record the firmware/`unihiker` version in the fix.
If the skill contradicts `unihiker/src/unihiker/GUI.py`, `gui-drawing.md` wins.
The wiki is the least reliable — it lags the wheel by years in places.
