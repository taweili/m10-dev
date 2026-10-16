# 2. Putting the M10 on Wi-Fi

Only needed for `pip install`, `apt`, cloud APIs, or SSH from elsewhere. **The
USB link at `10.1.2.3` keeps working the whole time** — Wi-Fi is additive.

## Board state going in

| Thing | State |
|---|---|
| Chip | Realtek **RTL8723DS**, 2.4 GHz only. Driver is **built into the kernel** (no `modinfo`). |
| Interfaces | `wlan0` (client), `p2p0` (P2P/hotspot — same radio), `br0` (USB, 10.1.2.3) |
| Daemons | `wpa_supplicant.service` enabled+running, `NetworkManager` running |
| Profiles | A factory placeholder `wifi` (`ssid=test`, `psk=12345678`) — unused |
| CLI tools | `nmcli`, `nmtui`, `wpa_supplicant`, `wpa_cli`, `dhclient`. **`iw` is not installed.** |
| Missing | `/etc/wpa_supplicant/wpa_supplicant.conf`, `/etc/network/interfaces` |

So Wi-Fi is disabled only because nothing ever told it what to join.

## Constraints (check before debugging anything else)

- **2.4 GHz only.** A 5 GHz-only SSID is invisible. Set a phone hotspot to
  "2.4 GHz / compatibility".
- **ASCII SSID** (`[A-Za-z0-9._-]+`). The factory web UI rejects specials.
- **WPA/WPA2-PSK only** via the UI — no WEP, open, WPS, 802.1X, or captive portal.
- `nmcli dev wifi list` on this board uses newer field names: use `SECURITY`,
  `WPA-FLAGS`, `RSN-FLAGS`, `BARS` (not `WPA`/`RSN`/`STATE`).

## Recommended path — `nmcli`

```bash
# 1. scan
nmcli dev wifi rescan; sleep 2
nmcli -t -f SSID,SIGNAL,CHAN,SECURITY,MODE dev wifi list | head

# 2. connect (creates the profile, handshakes, runs dhclient)
nmcli device wifi connect MY_SSID password MY_PASSWORD

# 3. verify
nmcli -t -f DEVICE,TYPE,STATE dev status     # wlan0 → connected
ip -br addr show wlan0                       # 192.168.x.x/24
ping -c3 8.8.8.8
cat /etc/resolv.conf
```

Explicit/reusable form:

```bash
nmcli connection add type wifi con-name "Home Wi-Fi" ifname wlan0 \
    ssid MY_SSID wifi-sec.key-mgmt wpa-psk wifi-sec.psk 'MY_PASSWORD'
nmcli connection up "Home Wi-Fi"
```

Autoconnect is on by default; confirm with
`nmcli -t -f NAME,AUTOCONNECT con show`, or set
`nmcli con mod "Home Wi-Fi" connection.autoconnect yes`.

Password storage: `wifi-sec.psk 'literal'` stores plaintext (root-only file,
`0600`). Or store the derived hash:
`wifi-sec.psk "$(wpa_passphrase MY_SSID MY_PW | sed -n 's/^psk=//p')"`.

### The `p2p0` quirk — read before scripting

`nmcli device wifi connect` on this board often activates the connection on
**`p2p0`, not `wlan0`** (old wpa_supplicant + RTL8723DS treat `p2p0` as a valid
STA vif and NM picks whichever vif it was scanning on). Consequences:

- **Don't hardcode `wlan0`** without checking which vif is up:
  `ip -br addr | grep -E 'inet ' | grep -v lo`.
- The live connection stays on `p2p0` until the next down/up or reboot. To force
  `wlan0`: `nmcli con down "Home Wi-Fi" && nmcli con up "Home Wi-Fi"`.
- SSH at `10.1.2.3` is unaffected (`br0`).

## Alternate paths

**Raw `wpa_supplicant` + `dhclient`** (if NM is misbehaving):

```bash
sudo tee /etc/wpa_supplicant/wpa_supplicant.conf >/dev/null <<'EOF'
country=US
ctrl_interface=/var/run/wpa_supplicant
update_config=1
network={
    ssid="MY_SSID"
    psk="MY_PASSWORD"
}
EOF
sudo nmcli device disconnect wlan0
sudo systemctl stop NetworkManager          # optional, quieter
sudo ip link set wlan0 up
sudo wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf
sudo dhclient -v wlan0                      # wpa_supplicant alone gives no IP
wpa_cli -i wlan0 status
```

**Factory web UI** (no SSH): browse `http://10.1.2.3/` → *Network Settings* →
pick SSID → password → *Connect*. ASCII + WPA2-PSK + 2.4 GHz only.

**`nmtui`**: interactive TUI — *Connect to a wireless network* → SSID → password.

**Hotspot mode** (board *is* the AP, `192.168.123.1`, **no internet uplink** —
a config bridge, not connectivity *for* the board):

```bash
nmcli connection add type wifi con-name "M10 Hotspot" ifname p2p0 \
    ssid "M10-AP-<mac suffix>" wifi.mode ap wifi.pwd '12345678' ipv4.method shared
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `nmcli dev wifi list` empty | `nmcli dev wifi on`; check `nmcli dev status` isn't `unmanaged`; 5 GHz-only AP → move to a 2.4 GHz SSID. Regional: `wpa_cli -i wlan0 set_country US`. |
| Connects, no IP | `nmcli dev reapply wlan0`, or `dhclient -r wlan0 && dhclient -v wlan0`. |
| IP but no internet | `cat /etc/resolv.conf`; suspect router client-isolation on guest SSIDs. |
| "Device or resource busy" | `sudo fuser -v /sys/class/net/wlan0`; `sudo pkill wpa_supplicant; sudo systemctl restart NetworkManager`. |
| `nmcli con up wifi` hangs | Expected — the factory `wifi` profile points at the invisible `ssid=test`. Create a real connection; optionally `nmcli con del wifi`. |
| USB link drops after joining Wi-Fi | Shouldn't happen; if it does, re-run `m10-network-setup.sh` (`board-link.md`). |
