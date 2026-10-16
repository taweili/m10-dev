# 1. Getting the board at 10.1.2.3 (USB link)

The M10's USB-C port presents a **USB ethernet gadget** to the PC. The board
sits at a fixed `10.1.2.3/24` on its `br0` bridge, so the PC needs an address in
`10.1.2.0/24` on that NIC.

| | |
|---|---|
| USB product id | `0525:a4a2` (host-side MAC `00:e0:4c:…`) |
| Kernel driver | `rndis_host` (also `cdc_ether`/`cdc_ncm` on some hosts) |
| PC side address | `10.1.2.2/24` (static, recommended) |
| Board side | `10.1.2.3/24`, SSH on 22, web UI on 80, Jupyter on 8888 |

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

## The fix: `m10-network-setup.sh`

Writes the address into the **NetworkManager profile, keyed to the board's MAC**,
so it survives renaming and re-enumeration. Lives in the `g-buddy` repo at
`scripts/m10-network-setup.sh`.

```bash
./m10-network-setup.sh              # static 10.1.2.2/24 (recommended)
./m10-network-setup.sh --dhcp       # board's isc-dhcp-server → ~10.1.2.101
./m10-network-setup.sh --status     # diagnose only, changes nothing
./m10-network-setup.sh --fix-tun    # also exclude 10.1.2.0/24 from Clash Verge TUN
./m10-network-setup.sh --dhcp --fix-tun
```

It is idempotent; re-run it whenever the link breaks. `--status` is safe to run
any time and prints: NIC description, address/route, ARP table, ping, the
kernel's chosen path, and the matching NM profile.

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

### Manual fallback (temporary only)

If you must hand-configure and cannot run the script:

```bash
grep -i product /sys/class/net/*/device/../uevent   # find the NIC
ip addr add 10.1.2.2/24 dev <nic>
ip route get 10.1.2.3
```

Remember: this is exactly what disappears. Re-run the script to make it stick.

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
| `ip route get` says `dev Mihomo` | Clash Verge TUN is intercepting → `./m10-network-setup.sh --fix-tun` (appends `tun.route-exclude-address: [10.1.2.0/24]` to Merge.yaml; re-apply the profile in Clash Verge). |
| Was working, now dark | Gadget re-enumerated → just re-run the script. |
| SSH works, GUI scripts don't show | Set `DISPLAY=:0` when launching over SSH (see `paramiko.md`). |

Once up: `http://10.1.2.3` (local web page), `http://10.1.2.3:8888` (Jupyter,
enable the service first), `\\10.1.2.3\root` (SMB share).

## Note: Wi-Fi is additive

Joining Wi-Fi does **not** tear down `br0`. Keep using `10.1.2.3` for
SSH/SFTP regardless of Wi-Fi state — see `wifi.md`.
