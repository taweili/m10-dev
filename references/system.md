# 5. Board OS, packages and services

> Reviewed 2026-10-19. Assumes firmware v0.4.2, `unihiker` 0.0.27+ and `pinpong` 0.6.1; version-specific claims are flagged inline.

The M10 is a **throwaway-appliance** Debian box: everything outside `/root/` and
`/usr/local/lib/python3.7/dist-packages/` is DFRobot's image, and the *only* way
to move the kernel, coprocessor firmware or DFRobot's own libraries forward is a
**reflash** — see `flash-firmware.md`.

## What's on the box (as-shipped, v0.4.0)

| Layer | Value |
|---|---|
| Firmware marker | `/opt/unihiker/Version` → `v0.4.0` |
| Debian | **10.11 Buster**, `arm64`, ~829 dpkg packages |
| Kernel | `4.4.143-67-rockchip-g01bbbc5d1312` (2023-02-23, Rock Pi S lineage) |
| Boot config | `/boot/uEnv.txt` — overlays `rk3308-pwm1 spi-spidev uart0 amic kbd i2c2 dis-u2-otg i2c1 uart3` |
| Python | **3.7.3** (`/usr/bin/python3`), pip 22.0.3 |
| Site packages | `/usr/local/lib/python3.7/dist-packages/` (`unihiker`, `pinpong`, `siot`, …) |
| DFRobot apps | `/opt/unihiker/` (`pyboardUI`, `pyboardWeb`, `SIoT`, `examples`) |
| First run | `/opt/unihiker/firstRun.sh` — sets `machine-id`, enables NM, **burns the GD32 coprocessor firmware**, registers `anaysis.py` in `rc.local` |

Everything is a **snapshot from ~Feb 2023**. Debian 10 hit EOL **2024-06-30**,
so a plain `apt-get update` returns **404** for every repo.

## Firmware ladder (which version has what)

| Version | Notes |
|---|---|
| **v0.4.0** | this board — pinpong 0.6.1, unihiker 0.0.27, Python 3.7 only, **broken apt sources** |
| v0.4.1 | **apt sources fixed for Buster EOL**; pyenv + Python 3.8.5 & 3.12.7; unihiker 0.0.28 |
| v0.4.2 | officially "latest" (Python 3.12.7 fixes) |
| **v0.4.5** | CDN-only, docs not updated: default Python → 3.12.7, built-in `uv` |

Images: `https://download3.dfrobot.com.cn/unihiker/img/`. Burners: Batch Tool
(GUI, **Windows only**, up to 10 boards), or `rkdeveloptool` (CLI, all
platforms, Rockchip's tool — see `flash-firmware.md`).

## `apt` is broken — the fix

`/etc/apt/sources.list` still points at Buster's live repos, which moved to
`archive.debian.org` in 2024-08. Repoint it (this is what v0.4.1 does):

```bash
sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak
sudo sed -i \
  -e 's|httpredir.debian.org/debian-security|archive.debian.org/debian-security|g' \
  -e 's|httpredir.debian.org/debian|archive.debian.org/debian|g' \
  -e 's|security.debian.org/ buster/updates|archive.debian.org/debian-security/ buster/updates|g' \
  /etc/apt/sources.list

# archive.debian.org is unsigned for old apt; silence the noise
cat | sudo tee /etc/apt/sources.list.d/archive-pin.conf >/dev/null <<'EOF'
APT::Get::List-Cleanup 0;
Acquire::http::Pipeline-Depth 0;
Acquire::Retries "3";
EOF

sudo apt-get update
apt list --upgradable | head -40        # look before you leap
```

⚠️ **Do not blindly `apt upgrade`.** The DFRobot image already ships the Buster
EOL security patches, and the archive copy of some packages (notably `openssl`)
is *older* than what's installed — a blanket upgrade will demand a downgrade.
Install selectively with `--allow-downgrades`, e.g.
`apt-get install --allow-downgrades base-files git curl dbus`.

Note the archive has **no new** security updates either — it's frozen at the EOL
snapshot. `apt` on this board is best treated as "restore the tools I need", not
"keep me patched".

## Python versions

Python 3.7 reached EOL in **2023-10**, so many current wheels refuse to install
(`Requires-Python >=3.8`: PyTorch ≥2.0, transformers ≥4.41, langchain, scipy
≥1.12, numpy ≥2.0, …). Either pin older versions, or use pyenv — which only
exists on **firmware ≥v0.4.1**:

```bash
pyenv versions
pyenv global 3.12.7
```

On v0.4.0 there is no pyenv, no 3.8+, and no conda (DFRobot discourages
conda/miniforge — too much disk on a 16 GB eMMC). Caveat: pyenv changes only the
*python* on PATH; the DFRobot stack (`unihiker`, `pinpong`) lives in
`/usr/local/lib/python3.7/`, so scripts that import them must run under 3.7.

## Projects, Python versions and disk

**One interpreter matters.** `unihiker` and `pinpong` live in
`/usr/local/lib/python3.7/dist-packages/`, so only `python3` (3.7.3) can import
them. On firmware ≥v0.4.1 pyenv installs other Pythons, but a script that
imports the DFRobot stack must still run under 3.7. `python3 -m venv` works and
is worth it for third-party pins, but it does not change that.

Pin dependencies in a `requirements.txt` and install with the offline
procedure below when Wi-Fi is unavailable. Keep the repo's `examples/` flat:
image files must sit next to the running `.py`.

**Disk:** `/root` is the eMMC (16 GB, shared with the OS); `/tmp` is **tmpfs**,
so large models or recordings there consume the 512 MB of RAM.

```bash
df -h /root; df -h /tmp; du -sh /root/* 2>/dev/null | sort -h | tail
```

Put speech models under `/root/speech-models/` (eMMC), not `/tmp`. SD cards and
USB sticks mount under `/media/` — `umount` before removing one, and never write
to a card that was yanked.

**Time:** TLS and logs depend on a sane clock. Check `timedatectl`; with Wi-Fi
up, `sudo timedatectl set-ntp true` (and `set-timezone`) fixes drift. A board
that boots at 1970 will fail certificate checks in cloud SDKs.

Shutdown properly — `sync && systemctl poweroff` — see `recovery.md` §5. Yanking
USB-C during writes risks the filesystem.

## Installing packages without Wi-Fi

`pip3 install` needs the internet, and the board is offline until it is on
Wi-Fi (`wifi.md`). When it cannot be, download on the PC, list the artifacts in
a **manifest**, and let the skill's installer do the push/install/verify:

```bash
# on the PC — fetch for arm64 / cp37
pip3 download --only-binary=:all: --platform manylinux2014_aarch64 \
  --python-version 37 --implementation cp --abi cp37m -d offline/wheels vosk srt

# validate the plan, then execute it
scripts/m10-offline-install.py --manifest offline/manifest.json --dry-run
scripts/m10-offline-install.py --manifest offline/manifest.json
```

A manifest (`version: 1`, paths relative to the file) declares: `board_dirs`,
`files` and `trees` to push, `debs` to extract (not install), `pip` packages
to install with `--no-index --find-links`, `checks` modules to import, an `abi`
`LD_PRELOAD` load test, and `pycompile` dirs. Unknown keys are rejected, and
local paths may not escape the manifest directory.

```json
{
  "version": 1,
  "board_dirs": ["/tmp/offline/wheels"],
  "files": [{"src": "wheels/foo-1.0-...whl", "dst": "/tmp/offline/wheels/"}],
  "debs": [{"src": "debs/libstdc++6_...deb", "extract": "/root/speech-models/extracted_libstdc++"}],
  "pip": {"find_links": "/tmp/offline/wheels", "packages": ["foo"], "no_deps": true},
  "checks": ["foo"],
  "pycompile": ["/root/g-buddy"]
}
```

`templates/offline-manifest.example.json` is a complete example. `no_deps` is
explicit on purpose — `--no-deps` silently installs broken wheels, so the
`checks` block has to prove the import actually works.

`.deb` files are usually wanted **only for one shared library** (the Vosk
`libstdc++` case, `speech.md`) — `dpkg-deb -x` extracts instead of installing,
so nothing in the DFRobot image moves. The installer derives the `.so` from the
`abi` block and runs a real model load under `LD_PRELOAD`; a wheel can install
cleanly and still fail to load, which no import check alone catches.

Then `python3 -m py_compile` every deployed script on the board — the manifest's
`pycompile` step does this in ~1 s and catches a truncated SFTP write.

## Never touch these

| Thing | Why |
|---|---|
| `linux-4.4-rock-pi-s-latest` | **held** (`hi`) local dpkg with DFRobot patches; apt must never move it. Removing it breaks boot. No `apt.radxa.com` source exists in the image, so a newer kernel is **reflash-only**. (Radxa's `buster-stable` tops out at `4.4.143-66`, *behind* this board's `-67`.) |
| `pyboard-*` dpkg packages | DFRobot-only, in no public repo → reflash |
| `/opt/unihiker/*` | home menu, web UI, SIoT, examples — not dpkg-managed → reflash |
| GD32 coprocessor firmware | burned by `pinpong/base/gd32/burn.sh` at first run; new firmware needs new pinpong → reflash |
| `/boot/uEnv.txt` overlays | hand-tuned; break it and the board won't boot (reflash) |

## Services: what to disable on a 512 MB board

Two levels of systemd here — **system** (`systemctl`) and **root's user
session** (`systemctl --user`). DFRobot's app daemons are *user* services and
respawn if you only kill the processes; you must `stop` **and** `disable` them.

As shipped the board idles at **~210 MB used of 423 MB** (~50 %). Biggest
consumers: pyboard web UI ~54 MB, SMB ~25 MB, Xorg ~20 MB, PulseAudio ~13 MB,
xrdp ~8 MB, SiOt ~6 MB, VNC ~3 MB, plus NetworkManager, lightdm, gettys and the
systemd daemons.

**System-level:**

```bash
sudo systemctl disable --now pyboardgui          # web pyboard UI   ~54 MB
sudo systemctl disable --now smbd nmbd           # SMB              ~25 MB
sudo systemctl disable --now xrdp xrdp-sesman    # remote desktop    ~8 MB
sudo systemctl disable --now x0vncserver         # VNC               ~3 MB
sudo systemctl disable --now bluetooth           # BT                ~3 MB
sudo systemctl disable --now dhclient-wlan0      # Wi-Fi DHCP        ~4 MB
sudo systemctl disable --now exim4               # MTA               ~2 MB
sudo systemctl disable --now cron                # cron              ~1 MB
sudo systemctl disable --now SiOt_unihiker       # DFRobot IoT       ~6 MB
```

**User-level (root's session):**

```bash
systemctl --user disable --now PyboardUI.service
systemctl --user disable --now PyboardWeb.service
systemctl --user disable --now ScreenShare.service
systemctl --user disable --now SIoT.service
systemctl --user disable --now FileShare.service
pkill -9 -f 'pyboardgui|pyboardWeb|x0vncserver|SiOt|smbd|nmbd'
```

Result: **~129 MB → ~74 MB used** (17 % of 423 MB), i.e. ~55 MB freed —
meaningful when Vosk wants ~300 MB resident.

⚠️ Several of these are actually launched from `/etc/init.d` scripts (not
systemd units) and are re-spawned by a keepalive bash loop, so
`systemctl disable` alone may not keep them down — kill the spawner too. The
skill script `scripts/m10-trim-services.py` handles that case.

**Do NOT disable:** `Xorg`, `PulseAudio` (the `Audio` API needs it), `lightdm`,
`NetworkManager`, `sshd`, `systemd-*`, `isc-dhcp-server` (the board's own DHCP
for the USB link in `--dhcp` mode), `unclutter` (hides the cursor for touch).
`wpa_supplicant` must come back if you want Wi-Fi.

Helper: `scripts/m10-trim-services.py` (ships with this skill).

## Reflash (the only real upgrade path)

**Full procedure: `flash-firmware.md`.** Read it before starting — the ordering
matters.

A flash is a **reimage, not an upgrade**. It empties `/root/` (files, pip
installs, Vosk models), wipes the Wi-Fi profiles, drops the landscape `Rotate`
config (the board returns portrait 240×320), replaces `/opt/unihiker/*`,
regenerates SSH host keys, and rebuilds site-packages under the new Python
version's directory.

So: **back up first** (SFTP/`scp`, *not* Samba — it skips dotfiles), then
`flash-firmware.md` for the burner kit, maskrom entry, `rkdeveloptool` commands
and the post-flash checklist.

## Quick status checks

```bash
cat /opt/unihiker/Version        # firmware
cat /etc/debian_version          # 10.11
uname -a                         # kernel
python3 --version; pip3 --version
dpkg -l linux-4.4-rock-pi-s-latest    # expect 'hi' (hold)
apt-get update 2>&1 | grep -E 'Err|404'   # expect nothing after the fix
free -m                          # RAM headroom (512 MB total)
systemctl list-units --type=service --state=running --no-pager
systemctl --user list-units --type=service --no-pager
pgrep -af 'pyboard|x0vnc|SiOt|smbd'
```
