# 9. Flashing firmware (the only upgrade path)

Everything on the M10 outside `/root/` and
`/usr/local/lib/python3.7/dist-packages/` belongs to DFRobot's image. There is
**no OTA, no `apt upgrade`, and no partial firmware update** — moving the kernel,
the coprocessor firmware, or DFRobot's own libraries forward means **reflashing
the whole eMMC**. See `system.md` for the firmware ladder (what each version
brings) and the "Never touch these" table (why `apt` cannot do it).

Reach for this reference when: the board is on an old firmware and you need a
newer Python/pyenv, `apt` is unusable, or you must recover a board that will not
boot. A board in **maskrom is always recoverable** — that is the safety net.

## What a flash destroys

A flash is a **reimage, not an upgrade**. This is the part that bites:

| Lost | Notes |
|---|---|
| `/root/` entirely | your scripts, pip installs, **`/root/speech-models/`** (Vosk models *and* the Debian 11 `libstdc++` preload `speech.md` needs), SSH keys |
| `/etc/NetworkManager/system-connections/` | **all Wi-Fi profiles** |
| `/etc/X11/xorg.conf.d/20-modesetting.conf` | **the landscape `Rotate` option is gone** → the board comes back **portrait 240×320** (`m10-api.md` §7) |
| SSH host keys | regenerated → clients warn about a changed host key |
| `/opt/unihiker/*`, `pyboard-*`, GD32 firmware | replaced / reburned at first boot |
| site-packages | rebuilt under the new Python version's directory |

> **Back up before entering flash mode.** Once the board is in maskrom the
> filesystem is unreachable and it is too late. Use SFTP/`scp` — **not** the
> Samba share, which silently skips dotfiles (`.ssh`, `.config`, `.bashrc`).

```bash
mkdir -p ~/m10-backup && cd ~/m10-backup
scp -r root@10.1.2.3:/root                                 ~/m10-backup/root
scp    root@10.1.2.3:/etc/NetworkManager/system-connections ~/m10-backup/wifi
scp    root@10.1.2.3:/etc/X11/xorg.conf.d/20-modesetting.conf ~/m10-backup/
```

The Xorg conf is worth grabbing explicitly: losing landscape rotation is easy to
forget about until two of your examples render clipped (`verify-gui.md`).

## The burner kit

Three pieces: a **loader `.bin`** (RK3308-specific), a **tool**, and the **image**.

### 1. `rkdeveloptool` + the RK3308 loader

DFRobot bundles both, per platform, with their own `burner.sh`. Grab the matching
one and **verify the MD5**:

| Platform | URL | MD5 |
|---|---|---|
| Ubuntu/Omarchy (amd64) | `https://dfimg.dfrobot.com/64228321aa9508d63a42c28b/wiki/1cb234325cca25ec876cd0ff70850217.7z` | `844413f0581c0b4ba906f540d4115807` |
| Debian arm64 | `https://dfimg.dfrobot.com/64228321aa9508d63a42c28b/wiki/522d9307c8d8ef6dcb9a77156b260eed.zip` | `6ab4abfe40dd037e0079142f71c06cd4` |
| macOS arm64 | `https://dfimg.dfrobot.com/64228321aa9508d63a42c28b/wikien/e3053945dcf6a62e1c7c38555ce3ac1b.7z` | `6d10d7ddd0f233030c67c99a676585ad` |
| Windows | `https://dfimg.dfrobot.com/64228321aa9508d63a42c28b/wiki/b4ab152645022f4cf66d4f392e1d5a92.7z` | `24d9ab6b5608b43e39eb130563f5b9d8` |

```bash
7z x burner_linux_amd64.7z                 # 7z/7za already on Omarchy
chmod +x burner_linux_amd64/{rkdeveloptool,burner.sh}
```

```
burner_linux_amd64/
├── burner.sh                                                     # DFRobot's whole procedure
├── rk3308_bs_loader_uart0_m0_emmc_port_support_sd_20220516.bin    # 275 KB loader
└── rkdeveloptool                                                  # their build
```

`burner.sh` *is* the procedure — read it, it is 8 lines:

```bash
./rkdeveloptool ld
./rkdeveloptool db rk3308_bs_loader_uart0_m0_emmc_port_support_sd_20220516.bin
sleep 3
./rkdeveloptool wl 0 *.img
sleep 3
./rkdeveloptool rd
```

Prefer the four commands by hand over `burner.sh`: the `wl 0 *.img` glob silently
picks an arbitrary image if the directory holds more than one, and running the
steps individually keeps every failure attributable.

### 2. The OS image

Images: `https://download3.dfrobot.com.cn/unihiker/img/` → extract `.7z` → `.img`.

**Do not rename the file.** The trailing 32 hex characters are the MD5, and the
burner/batch tool verifies the name against the content:

```bash
md5sum unihiker_v0.4.2.md5.fa3055d3b6b8eb72490d2210f3110bee.img
#        fa3055d3b6b8eb72490d2210f3110bee     <- must equal the name, else the file is damaged
```

Place it inside the `burner_*` directory, next to `burner.sh`.

## Privileges: `pkexec`, not `sudo`

`rkdeveloptool` needs raw USB access, and `/dev/bus/usb/001/0NN` is root-owned
`crw-rw-r--` with no ACL for your user.

- `sudo` wants a password, and a session with no polkit agent cannot prompt.
- On this machine **`pkexec` works passwordless** — Omarchy ships a polkit rule
  for `wheel`, and `pkexec id` returns `uid=0(root)`. Note this works *despite*
  **no polkit agent being installed** (only `polkitd`), so that rule is
  load-bearing: don't "clean up" the polkit config, or `pkexec` will begin
  failing with no way to authenticate.

`pkexec` does not inherit `$PATH` and resets the environment, so use **absolute
paths** throughout:

```bash
PK=/home/david/Downloads/m10-burner/burner_linux_amd64/rkdeveloptool
pkexec $PK ld
```

## Entering flash mode (physical)

1. Unplug the board's USB-C.
2. **Hold the Home button** (on pre-V1.0.0 boards, the small button under the USB
   port on the back).
3. Plug USB-C in **while still holding Home**.
4. Screen goes **solid white** → the RK3308 boot ROM is running.
5. Release Home once the tool reports the device.

Only one board can be flashed at a time this way.

## The four commands

| Step | Command | What it does |
|---|---|---|
| 1 | `rkdeveloptool ld` | list devices — must print `Maskrom` |
| 2 | `rkdeveloptool db <loader>.bin` | download loader into RAM → chip leaves boot ROM (~1 s) |
| 3 | `rkdeveloptool wl 0 <image>.img` | write the whole image from LBA 0 (the long one) |
| 4 | `rkdeveloptool rd` | reset → board boots and self-installs |

`rkdeveloptool` also offers `td` (test device — proves comms), `rci` (chip info),
`rid`/`rfi` (flash id/info), `ef` (erase), `cs` (change storage).

## Reading the USB state — the best diagnostic

The board's USB identity tells you exactly which phase it is in. There are three
states, and the **string descriptor indices** distinguish the first two:

| `idProduct` | product | strings | State |
|---|---|---|---|
| `2207:330e` | *(none)* | `Mfr=0 Product=0 SN=0` | maskrom boot ROM, waiting for `db` |
| `2207:330e` | `USB-MSC` | `Mfr=1 Product=2 SN=3`, `RockChip`/`rockchip` | **loader resident** — `db` succeeded |
| `0525:a4a2` | `unihiker` | `dfrobot`/`dfrobot20200928` | **booted into the OS** (RNDIS gadget) |

The bare boot ROM exposes **no** string descriptors; the moment `db` lands, the
device disconnects, re-enumerates, and grows a full descriptor set. That
re-enumeration is the `db` success signal.

**The board stays `USB-MSC` until a successful `rd`.** So "device is still there
as `USB-MSC`" means the reset did not take — go back to `rd`, the loader is still
running and happy to be re-asked.

`lsusb` is **not installed on Omarchy**, and `dmesg` is blocked
(`kernel.dmesg_restrict=1` → *Operation not permitted*). Two ways in:

```bash
# 1. sysfs — current state only
for d in /sys/bus/usb/devices/*/; do
  [ -f "$d/idVendor" ] || continue
  [ "$(cat "$d/idVendor")" = 2207 ] && \
    echo "$(basename "$d") $(cat "$d/idProduct") $(cat "$d/product" 2>/dev/null)"
done

# 2. the host kernel log — the full state history (works unprivileged)
journalctl -k --since "30 min ago" --no-pager | grep -E 'usb 1-[0-9]+|Product:'
```

`journalctl -k` is the better tool: it shows the *whole* progression with
timestamps, including the `db` transition, so you can tell "never entered flash
mode" apart from "`db` worked but `rd` did not take".

> **A successful `db` still leaves `ld` reporting `Maskrom`.** Normal for this
> loader — do **not** retry `db`. Check the product string / journal instead
> (empty → `USB-MSC`).

## Worked example (real timings, verified from the host kernel log)

v0.4.0 → v0.4.2, 7.6 GB image, USB 2.0 port:

| Host time | Event |
|---|---|
| 10:49:31 | board plugged in — `2207:330e`, `Mfr=0 Product=0 SN=0` → maskrom |
| 10:51:03 | **`db`** → re-enumerates as `2207:330e` **`USB-MSC`** / `RockChip` / `rockchip` |
| 10:51:18 | `wl 0` started |
| 11:00:46 | `wl 0` finished — 100%, zero errors (**9m28s** for 7.6 GB) |
| 11:00:50 | `rd` #1 — hung; **no effect**, board stayed `USB-MSC` |
| 11:07:11 | `rd` #2 → `Reset Device OK` → USB disconnect |
| 11:07:18 | board boots — `0525:a4a2` `unihiker` / `dfrobot`, RNDIS `enp2s0f0u4c2` |
| 11:07:32 | disconnect → reboot (the installer's second pass) |
| 11:07:40 | up again — final boot; SSH ready once the link is fixed up |

The ~6 min between `wl` finishing and the successful `rd` was entirely my retry
loop. A working `rd` boots the board within seconds, and the install itself is
under a minute.

```bash
PK=/path/to/burner_linux_amd64/rkdeveloptool
LD=/path/to/burner_linux_amd64/rk3308_bs_loader_uart0_m0_emmc_port_support_sd_20220516.bin
IMG=/path/to/burner_linux_amd64/unihiker_v0.4.2.md5.fa3055d3b6b8eb72490d2210f3110bee.img

pkexec $PK ld                                       # expect: Maskrom
pkexec $PK db $LD                                   # ~1 s
pkexec $PK wl 0 "$IMG"                              # ~10 min; log it, grep for errors
pkexec $PK rd                                       # may hang — see gotcha 1
```

`wl` progress arrives as a huge stream of `\r`-terminated lines. Capture it and
reduce:

```bash
pkexec $PK wl 0 "$IMG" > /tmp/m10-burn.log 2>&1
tr '\r' '\n' < /tmp/m10-burn.log | grep -iE 'error|fail|retry' | sort -u   # expect nothing
tr '\r' '\n' < /tmp/m10-burn.log | grep -oE '\([0-9]+%\)' | tr -d '()%' | sort -n | tail -1   # expect 100
```

## Gotchas that cost time

1. **`rd` can hang.** The reset handshake sometimes never returns, so a bare
   `pkexec $PK rd` blocks forever even though nothing is wrong. Wrap it:
   `timeout 25 pkexec $PK rd`. If the device is *still* enumerated as `USB-MSC`
   afterwards, the reset did not take — just run it again; the second attempt
   succeeded where the first hung. Wrap `db`/`rd` in timeouts generally; only
   `wl` legitimately needs a long one.
2. **`wl 0 *.img` picks arbitrarily.** DFRobot's `burner.sh` globs the image; with
   two `.img` files present you cannot tell which was written. Pass the filename
   explicitly.
3. **Cable and port matter.** 7.6 GB over a marginal cable will drop mid-write.
   Go straight into the PC — no hub or dock — and prefer USB 2.0/3.x directly on
   the motherboard.
4. **Do not touch anything during `wl` or the install.** The board reboots twice
   on its own after `rd`; power-cycling or unplugging mid-install means reflashing
   from scratch. Wait for the language-selection screen.
5. **Don't skip `firstRun.sh`.** It burns the GD32 coprocessor firmware; if it
   doesn't run, every `pinpong` call silently no-ops (`SKILL.md` non-negotiable 1).
6. **Failed `wl` is not fatal** — maskrom is always re-enterable. If it dies at
   the *same* byte every time, suspect the eMMC rather than the cable.

## After the flash

The board comes back at portrait, offline, and empty. Work through this in order:

1. **Language picker** on the first-boot UI (A/B + Home).
2. **Calibrate the touch screen** — long-press Home → *Calibrate touch screen*.
   Required after **every** flash; without it touches land in the wrong place,
   with no way to recover except recalibrating.
3. **Let `firstRun.sh` finish** (GD32 burn). Don't pre-seed `/etc/machine-id`.
4. **Restore the USB link** — a flash resets the NM profile to
   `ipv4.method=link-local`, so the board shows up at `169.254.x.x` under a
   **new interface name**. Run `scripts/m10-network-setup.sh`
   (`board-link.md`); do not hand-add the address.
5. **Rejoin Wi-Fi** — profiles were wiped (`wifi.md`).
6. **Re-apply landscape** if you want it — `m10-api.md` §7. Check with
   `xdpyinfo | grep dimensions` → expect `240x320` (portrait) or `320x240`.
7. **Disable the bloat** — a fresh image idles at ~139 MB of 423 MB;
   `scripts/m10-disable-bloat.py` (`system.md`) brings it to ~74 MB.
8. **Re-deploy your code and models** — `/root` is empty, including any Vosk
   model (`speech.md`).

## Verify the flash worked

```bash
cat /opt/unihiker/Version              # expect v0.4.2
pip3 show unihiker                     # 0.0.28.5 for v0.4.1+ (was 0.0.27 on v0.4.0)
pyenv versions                         # v0.4.1+ only: 3.7.3 / 3.8.5 / 3.12.7
which uv                               # v0.4.5 only
grep -h '^deb' /etc/apt/sources.list   # v0.4.1+: archive.debian.org
```

The strongest signal is a **functional coprocessor test**, which proves
`firstRun.sh` completed:

```python
python3 - <<'PY'
from pinpong.board import Board
Board().begin()
from pinpong.extension.unihiker import light, button_a
print("GD32 link: OK")
print("light:", light.read(), "button_a:", button_a.value())
PY
```

Then confirm the display (`verify-gui.md`) — deploy a GUI script and read
`/dev/fb0` back. Expect the rendered content to be **clipped on the right** while
the board is in portrait: `GUI(w=320, h=240)` on a 240-wide screen.

`unihiker` exposes no `__version__`; use `pip3 show unihiker`.

## Failure modes

| Symptom | Cause / fix |
|---|---|
| `ld` prints nothing | not in flash mode → repeat unplug / hold-Home / plug-in. Verify with the sysfs loop above. |
| `ld` says `Maskrom` after a successful `db` | **normal** — proceed to `wl` |
| `db` errors or hangs | wrong/absent loader for the SoC; check USB port and cable |
| `wl` fails partway | cable/port; retry. Same byte every time → eMMC suspect |
| `rd` hangs / device stays `USB-MSC` | reset did not take — run it again under `timeout` (gotcha 1) |
| Board dark after `rd` | write was interrupted; re-enter maskrom and re-flash |
| Boots but touch is offset | touch not calibrated — long-press Home → Calibrate |
| Boots, but pinpong does nothing | `firstRun.sh` (GD32 burn) never ran |
| `169.254.x.x`, board unreachable | NM profile left at link-local → `m10-network-setup.sh` |
| Text/UI clipped on the right | board is portrait; re-apply `Rotate` (`m10-api.md` §7) |
| `apt-get update` DNS failures | no internet — join Wi-Fi first; sources are already correct on v0.4.1+ |

## Alternatives

- **Batch Tool** (GUI, **Windows only**, up to 10 boards at once):
  `UNIHIKER_Batch_Tool_V2.3_2023.4_en.zip` from
  `https://download3.dfrobot.com.cn/unihiker/Burner/`. Verifies the image MD5 on
  load (30 s – 5 min).
- **Build `rkdeveloptool` from source** if no bundle matches your platform:
  `https://github.com/rockchip-linux/rkdeveloptool`, then take the `.bin` from
  any bundle above.
- **One M10 flashing another** — DFRobot publishes an arm64 bundle for this.
