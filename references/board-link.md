# 1. Getting the board at 10.1.2.3 (USB link)

> Reviewed 2026-10-19. Assumes firmware v0.4.2, `unihiker` 0.0.27+ and `pinpong` 0.6.1; version-specific claims are flagged inline.

The M10's USB-C port presents a **USB ethernet gadget** to the PC. The board
sits at a fixed `10.1.2.3/24` on its `br0` bridge, so the PC needs an address in
`10.1.2.0/24` on that NIC.

| | |
|---|---|
| USB product id | `0525:a4a2` (host-side MAC `00:e0:4c:…`) |
| Kernel driver | `rndis_host` (also `cdc_ether`/`cdc_ncm` on some hosts) |
| PC side address | `10.1.2.2/24` (static, recommended) |
| Board side | `10.1.2.3/24`, SSH on 22, web UI on 80, Jupyter on 8888 |

## Host network changes need explicit approval

The fixes in this file change **the PC you are working on**, not the board,
and sit behind a hard rule (`SKILL.md` red lines, non-negotiable 1):

- **Never run** an address/route/link change, an NM profile change, a driver
  rebind or module unload, `rfkill`, a DNS edit, or a VPN/TUN config edit
  without an explicit **yes for that exact command**. Approval of a previous
  command — or a general "fix the link" — is **not** approval for the next one.
  `sudo`/`pkexec` succeeding is not permission either; it is only escalation.
- **Measurements are not implied by approval.** Re-enumeration wipes a session
  address, so the *second* run of the same command needs asking again.
- **Diagnose read-only first, then present one command.** `scripts/m10-net-setup.sh
  --status`, `ip -br addr`, `ip route get 10.1.2.3`, `ip neigh show dev <nic>`,
  `ping`, `lsusb`, `lsusb -t`, `/sys/class/net/*/…` reads, and `dmesg` are all
  safe and answer most questions without touching anything.
- **Host-side things that count as network changes** (all seen on real
  benches): `ip addr add|del`, `ip route`, `ip link set`, `nmcli con …`,
  `systemctl restart NetworkManager`, `modprobe -r <usbnet driver>`,
  `/sys/bus/usb/drivers/<drv>/{bind,unbind}`, `rfkill unblock`, edits to
  `/etc/network/`, `/etc/NetworkManager/`, `/etc/resolv.conf`, and applying a
  TUN/proxy exclusion (`m10-clash-exclude.sh` **without** `--status`).
- **Not covered by this rule:** anything changed *on the board* over SSH. That
  is the normal workflow and has its own red lines (reflash, `apt upgrade`,
  killing an app).

State the command, what it changes, and why — then wait.

## Do not use `ip addr add`

```bash
sudo ip addr add 10.1.2.2/24 dev <nic>     # ← works, then silently dies
```

This appears to work, then stops the moment the gadget re-enumerates (board
reboot, cable wiggle, hub reset). The NIC is destroyed and recreated — often
under a **new name** (`eth0` → `enp2s0f0u4c2`) — and the hand-added address is
gone. If the stored NetworkManager profile for that NIC is `Link-Local Only`, NM
comes back with `169.254.x.x`, there is no route to `10.1.2.0/24`, and the board
is dark.

### Exception: on-demand boards, NetworkManager inactive

The rule above assumes NetworkManager is running and the board is permanently
connected. On a bench where the board is plugged in only when needed and
NetworkManager is disabled (or absent), `nmcli` cannot create a profile and a
`.network` unit is the wrong shape for a device that isn't always here. In that
case a per-session

```bash
sudo ip addr add 10.1.2.2/24 dev <current USB-ethernet NIC>
```

is the pragmatic fallback. It does not survive re-enumeration — re-run it after
each plug-in. To find the NIC name (it changes every time: `usb0`, `usb1`,
…), run `scripts/m10-net-setup.sh --status`, which detects the gadget via sysfs
(`/sys/class/net/*/device/../uevent`) and works even when NM is inactive.

## The fix: `m10-net-setup.sh`

Writes the address into the **NetworkManager profile, keyed to the board's MAC**,
so it survives renaming and re-enumeration. Ships with this skill at
`scripts/m10-net-setup.sh`.

```bash
scripts/m10-net-setup.sh              # static 10.1.2.2/24 (recommended; host change — ask first)
scripts/m10-net-setup.sh --dhcp       # board's isc-dhcp-server → ~10.1.2.101
scripts/m10-net-setup.sh --status     # diagnose only, changes nothing
scripts/m10-net-setup.sh --remove     # delete the profile it created
```

It is idempotent; re-run it whenever the link breaks. `--status` is safe to run
any time and prints: NIC description, address/route, ARP table, ping, TCP 22,
the kernel's chosen path, and the matching NM profile.

> A host with a **TUN-mode VPN** (Clash/Mihomo and friends) can capture
> `10.0.0.0/8` before the direct route applies. Exclude `10.1.2.0/24` in the VPN
> client. `scripts/m10-clash-exclude.sh` appends the exclusion to Clash Verge's
> `Merge.yaml` and reports whether mihomo already routes `10.0.0.0/8` DIRECT.

### What it does under the hood

1. Finds the M10 NIC by USB product id, then by gadget driver, then by the
   `00:e0:4c:*` host MAC.
2. Creates or reuses an NM profile named `M10 USB link`, set to match on **MAC
   only** (`connection.interface-name ""`) so a rename does not orphan it.
3. Sets `ipv4.method manual`, `ipv4.addresses 10.1.2.2/24`, `ipv4.gateway ""`,
   `ipv4.never-default yes`, `ipv4.ignore-auto-routes yes`, `ipv6.method ignore`
   — the link must **never** become the default route (Wi-Fi/internet is
   separate).
4. Activates it, waits for a global IPv4 address, then verifies routing, ping,
   and TCP 22.

### Manual equivalent (no script)

The durable fix is four `nmcli` calls. `MAC` is the gadget NIC's address
(`cat /sys/class/net/<nic>/address`), stable across re-enumeration:

```bash
MAC=$(cat /sys/class/net/<nic>/address)

nmcli con add type ethernet con-name "M10 USB link" \
  802-3-ethernet.mac-address "$MAC"
UUID=$(nmcli -t -f UUID,NAME con show | awk -F: '/M10 USB link/{print $1}')

nmcli con mod "$UUID" \
  802-3-ethernet.mac-address "$MAC" \
  connection.interface-name "" \
  ipv4.method manual ipv4.addresses 10.1.2.2/24 ipv4.gateway "" \
  ipv4.never-default yes ipv4.ignore-auto-routes yes ipv4.dns "" \
  ipv6.method ignore connection.autoconnect yes

nmcli con up "$UUID"
```

For DHCP-from-the-board instead, swap the address line for
`ipv4.method auto ipv4.addresses "" ipv4.gateway ""` (the board's
`isc-dhcp-server` hands out ~`10.1.2.101`). If NM refuses because the NIC is
`unmanaged`: `sudo nmcli dev set <nic> managed yes`.

`sudo ip addr add 10.1.2.2/24 dev <nic>` is a **temporary** diagnostic only —
it is exactly what disappears on re-enumeration. Never leave it as the fix.

## Verify

```bash
ping -c1 -W2 10.1.2.3                      # responds?
ip neigh show dev <nic>                    # has the board answered ARP?
ip -4 -br addr show <nic>                  # 10.1.2.2/24, no 169.254.x.x
ip route get 10.1.2.3                      # must say "dev <nic>"
timeout 3 bash -c 'exec 3<>/dev/tcp/10.1.2.3/22' && echo "SSH ready"
ssh root@10.1.2.3                          # password: dfrobot
```

## Failure modes

| Symptom | Cause / fix |
|---|---|
| No NIC found at all | Board off/booting, or cable in a **hub/dock** — plug it straight into the PC. |
| `169.254.x.x` only | NM profile is `IPv4 Link-Local Only` → run the script (it sets `manual`). |
| Board never answers ARP | Board asleep/off, or wrong NIC. Press the Home button; wait ~10 s; re-plug. |
| `ip route get` says `dev Mihomo` (or another TUN) | A TUN-mode VPN is intercepting → exclude `10.1.2.0/24` in the VPN client. `scripts/m10-clash-exclude.sh --status` diagnoses; *applying* it is a host config change — ask first. |
| Was working, now dark | Gadget re-enumerated → re-run the script (or re-run `ip addr add` on an on-demand bench). |
| SSH works, GUI scripts don't show | Set `DISPLAY=:0` when launching over SSH (see `paramiko.md`). |

Once up: `http://10.1.2.3` (local web page), `http://10.1.2.3:8888` (Jupyter,
enable the service first), `\\10.1.2.3\root` (SMB share).

### Other ways in (and when not to use them)

| Entry point | How | Verdict |
|---|---|---|
| **SSH + paramiko** | `10.1.2.3:22`, `root`/`dfrobot` | the default; everything else is a fallback |
| Jupyter | pre-installed; enable under *Application Services*, browse `:8888`, *New → Python 3* | good for poking at the API, poor for files/deploys |
| SMB share | `\\10.1.2.3\root` in Windows/`smbclient`; IDLE *File → Save As* to the same path | convenient but **not dotfile-safe** — never use it for backups |
| VS Code Remote-SSH / Thonny | same SSH endpoint | works; extra RAM on the board, so not for the 512 MB budget |
| local web page `:80` | DFRobot's home UI | needs `pyboardWeb`, which is the first thing you disable (`system.md`) |

## Note: Wi-Fi is additive

Joining Wi-Fi does **not** tear down `br0`. Keep using `10.1.2.3` for
SSH/SFTP regardless of Wi-Fi state — see `wifi.md`.
