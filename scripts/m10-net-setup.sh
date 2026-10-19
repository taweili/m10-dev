#!/usr/bin/env bash
#
# m10-net-setup.sh — make the UNIHIKER M10 reachable at 10.1.2.3 over USB-C.
#
# The M10's USB-C port presents a USB ethernet gadget (RNDIS) to the PC. The
# board's br0 is fixed at 10.1.2.3/24, so the PC needs an address in
# 10.1.2.0/24 on that NIC.
#
# Doing it once with `sudo ip addr add` works until the gadget re-enumerates
# (board reboot, cable wiggle, hub reset). Then the NIC is destroyed and
# recreated — often under a new name — and the hand-added address is gone.
# This script puts the address in the NetworkManager profile instead, keyed to
# the board's MAC, so it survives renaming and re-enumeration.
#
#   ./m10-net-setup.sh              static 10.1.2.2/24 (recommended)
#   ./m10-net-setup.sh --dhcp       address from the board's DHCP server
#   ./m10-net-setup.sh --status     diagnose only, change nothing
#   ./m10-net-setup.sh --remove     delete the profile this script created
#
# Generic version. A host with extra packaging (e.g. a TUN-mode VPN that
# captures 10.0.0.0/8) needs an extra route exclusion — see
# references/board-link.md.
#
set -uo pipefail

ADDR="10.1.2.2"
PREFIX=24
BOARD="10.1.2.3"
MODE="static"
DO_STATUS=0
DO_REMOVE=0
PROFILE_NAME="M10 USB link"

usage() {
  cat <<'EOF'
Make the UNIHIKER M10 reachable at 10.1.2.3 over its USB-C RNDIS link.

Usage:
  ./m10-net-setup.sh                 static 10.1.2.2/24 (recommended)
  ./m10-net-setup.sh --dhcp          let the board's DHCP server assign
  ./m10-net-setup.sh --status        diagnose only, change nothing
  ./m10-net-setup.sh --remove        delete the created NM profile
  -h, --help                         this text

Requires: NetworkManager (nmcli), root or pkexec.
EOF
}

if [ -t 1 ]; then
  C_R=$'\033[31m'; C_G=$'\033[32m'; C_Y=$'\033[33m'; C_B=$'\033[1m'; C_0=$'\033[0m'
else
  C_R=; C_G=; C_Y=; C_B=; C_0=
fi
info() { printf '%s\n' "$*"; }
ok()   { printf '%sOK%s  %s\n'  "$C_G" "$C_0" "$*"; }
warn() { printf '%sWARN%s %s\n' "$C_Y" "$C_0" "$*"; }
die()  { printf '%sFAIL%s %s\n' "$C_R" "$C_0" "$*" >&2; exit 1; }
hdr()  { printf '\n%s== %s ==%s\n' "$C_B" "$*" "$C_0"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dhcp)    MODE="dhcp" ;;
    --static)  MODE="static" ;;
    --status)  DO_STATUS=1 ;;
    --remove)  DO_REMOVE=1 ;;
    -h|--help) usage; exit 0 ;;
    *)         usage >&2; die "unknown option: $1" ;;
  esac
  shift
done

command -v nmcli >/dev/null || die "nmcli not found — this script needs NetworkManager"

if [ "${EUID:-$(id -u)}" -eq 0 ]; then
  SUDO=()
else
  command -v pkexec >/dev/null || command -v sudo >/dev/null \
    || die "need root (or pkexec/sudo) to configure networking"
  if command -v pkexec >/dev/null; then SUDO=(pkexec); else SUDO=(sudo); fi
fi

# ------------------------------------------------------------- nmcli help ----
nmget()      { nmcli -t con show "$1" 2>/dev/null | sed -n "s/^$2://p" | head -1; }
nmprofiles() { nmcli -t -f UUID,NAME,DEVICE con show 2>/dev/null; }

# -- detect the M10 NIC --------------------------------------------------------
find_m10_nic() {
  local dev target uevent driver mac

  # 1. the USB gadget product id the UNIHIKER (and other g_ether boards) use
  for dev in /sys/class/net/*; do
    [ -r "$dev/device/../uevent" ] || continue
    uevent=$(cat "$dev/device/../uevent" 2>/dev/null) || continue
    case "$uevent" in *PRODUCT=525/a4a2*) basename "$dev"; return 0 ;; esac
  done

  # 2. any USB-attached ethernet gadget driver
  for dev in /sys/class/net/*; do
    target=$(readlink -f "$dev/device" 2>/dev/null) || continue
    case "$target" in *usb*) ;; *) continue ;; esac
    driver=$(basename "$(readlink -f "$dev/device/driver" 2>/dev/null)" 2>/dev/null)
    case "$driver" in
      rndis_host|cdc_ether|cdc_subset|cdc_ncm) basename "$dev"; return 0 ;;
    esac
  done

  # 3. last resort: the OUI the gadget uses for its host-side MAC
  for dev in /sys/class/net/*; do
    target=$(readlink -f "$dev/device" 2>/dev/null) || continue
    case "$target" in *usb*) ;; *) continue ;; esac
    mac=$(cat "$dev/address" 2>/dev/null) || continue
    case "$mac" in 00:e0:4c:*) basename "$dev"; return 0 ;; esac
  done
  return 1
}

describe_nic() {
  local nic="$1" uevent
  uevent=$(cat "/sys/class/net/$nic/device/../uevent" 2>/dev/null || true)
  printf '%s\n' "$uevent" | sed -n 's/^PRODUCT=/  usb product : /p'
  info "  driver      : $(basename "$(readlink -f "/sys/class/net/$nic/device/driver" 2>/dev/null)" 2>/dev/null)"
  info "  interface   : $nic"
  info "  MAC         : $(cat "/sys/class/net/$nic/address" 2>/dev/null)"
  info "  carrier     : $(cat "/sys/class/net/$nic/carrier" 2>/dev/null)"
}

print_status() {
  local nic="$1" uuid

  hdr "M10 USB link"
  describe_nic "$nic"
  [ "$(cat "/sys/class/net/$nic/carrier" 2>/dev/null || echo 0)" = "1" ] \
    || warn "no carrier on $nic — link down, the board may still be booting"

  hdr "Address / route"
  ip -4 -br addr show "$nic" | sed 's/^/  /'
  if ip route show | grep -q "${ADDR%.*}\."; then
    ip route show | grep "${ADDR%.*}\." | sed 's/^/  /'
  else
    warn "no route to $(echo "$ADDR" | cut -d. -f1-3).0/24 — this is the failure"
  fi
  info "  default routes:"
  ip route show default 2>/dev/null | sed 's/^/    /'

  hdr "Neighbour table (has the board answered ARP?)"
  ip neigh show dev "$nic" | sed 's/^/  /'
  if ip neigh show dev "$nic" | grep -q "^$BOARD "; then
    ok "$BOARD is in the ARP table"
  else
    warn "$BOARD not in the ARP table — board off/asleep, or a different NIC"
  fi

  hdr "Reachability"
  ping -c1 -W2 "$BOARD" >/dev/null 2>&1 && ok "$BOARD responds to ping" \
    || warn "$BOARD does not respond to ping"
  timeout 3 bash -c "exec 3<>/dev/tcp/$BOARD/22" 2>/dev/null \
    && ok "TCP 22 is open — SSH ready" || warn "TCP 22 not reachable"

  hdr "Kernel's chosen path to $BOARD"
  ip route get "$BOARD" 2>&1 | sed 's/^/  /'
  if ! ip route get "$BOARD" 2>/dev/null | head -1 | grep -q "dev $nic"; then
    warn "kernel is NOT routing $BOARD via $nic"
    info "  if the first line names a TUN/VPN device, exclude 10.1.2.0/24 from it"
  fi

  hdr "NetworkManager profile for $nic"
  uuid=$(nmprofiles | awk -F: -v d="$nic" '$3==d{print $1; exit}')
  if [ -z "$uuid" ]; then
    uuid=$(nmprofiles | while IFS=: read -r u _n _d; do
             [ "$(nmget "$u" '802-3-ethernet.mac-address')" = "$(cat "/sys/class/net/$nic/address")" ] \
               && { echo "$u"; break; }
           done)
  fi
  if [ -n "$uuid" ]; then
    nmcli -t con show "$uuid" 2>/dev/null | grep -E \
      '^(connection.id|connection.interface-name|802-3-ethernet.mac-address|ipv4.method|ipv4.addresses|ipv6.method):' \
      | sed 's/^/  /'
    case "$(nmget "$uuid" ipv4.method)" in
      link-local) warn "ipv4.method=link-local is why you only get 169.254.x.x" ;;
      "")         warn "could not read ipv4.method" ;;
    esac
  else
    warn "no NM profile bound to $nic"
  fi
}

# ------------------------------------------------------------------ main -----
if ! NIC=$(find_m10_nic); then
  die "no USB ethernet gadget found.
   Checks: cable in the board's USB-C port, straight into the PC (no hub/dock),
   board powered on and booted. Then look for:
     grep -i product /sys/class/net/*/device/../uevent
     lsmod | grep -E 'rndis|cdc_ether|usbnet'"
fi
MAC=$(cat "/sys/class/net/$NIC/address")

if [ "$DO_STATUS" -eq 1 ]; then
  print_status "$NIC"
  exit 0
fi

ok "found $NIC"
describe_nic "$NIC"
[ "$(cat "/sys/class/net/$NIC/carrier" 2>/dev/null || echo 0)" = "1" ] \
  || warn "no carrier on $NIC — the board may still be booting"

# find or create the profile, matched on MAC so it survives interface renames
UUID=""; NAME=""
while IFS=: read -r u n d; do
  [ -z "${u:-}" ] && continue
  if [ "$d" = "$NIC" ] \
     || [ "$(nmget "$u" '802-3-ethernet.mac-address')" = "$MAC" ] \
     || [ "$(nmget "$u" 'connection.interface-name')" = "$NIC" ]; then
    UUID="$u"; NAME="$n"; break
  fi
done < <(nmprofiles)

if [ "$DO_REMOVE" -eq 1 ]; then
  [ -n "$UUID" ] || { warn "no matching profile to remove"; exit 0; }
  "${SUDO[@]}" nmcli con delete "$UUID" && ok "deleted profile '$NAME'"
  exit 0
fi

if [ -z "$UUID" ]; then
  NAME="$PROFILE_NAME"
  info "creating profile '$NAME'"
  "${SUDO[@]}" nmcli con add type ethernet con-name "$NAME" \
    802-3-ethernet.mac-address "$MAC" >/dev/null || die "nmcli con add failed"
  UUID=$(nmprofiles | awk -F: -v n="$NAME" '$2==n{print $1; exit}')
  [ -n "$UUID" ] || die "could not read the new profile's UUID"
else
  info "using existing profile: $NAME ($UUID)"
fi

"${SUDO[@]}" nmcli con mod "$UUID" \
  connection.interface-name "" \
  802-3-ethernet.mac-address "$MAC" \
  ipv4.never-default yes \
  ipv4.ignore-auto-routes yes \
  ipv4.dns "" \
  ipv6.method ignore \
  connection.autoconnect yes \
  || die "nmcli con mod failed"

if [ "$MODE" = "dhcp" ]; then
  info "mode: DHCP (board's isc-dhcp-server, typically ~10.1.2.101)"
  "${SUDO[@]}" nmcli con mod "$UUID" \
    ipv4.method auto ipv4.addresses "" ipv4.gateway "" \
    || die "nmcli con mod (dhcp) failed"
else
  info "mode: static ${ADDR}/${PREFIX} (never the default route)"
  "${SUDO[@]}" nmcli con mod "$UUID" \
    ipv4.method manual ipv4.addresses "${ADDR}/${PREFIX}" ipv4.gateway "" \
    || die "nmcli con mod (static) failed"
fi

if nmcli -t -f DEVICE,STATE dev status 2>/dev/null | grep -q "^$NIC:unmanaged$"; then
  warn "$NIC is unmanaged by NetworkManager; taking it over"
  "${SUDO[@]}" nmcli dev set "$NIC" managed yes || true
  sleep 2
fi

"${SUDO[@]}" nmcli con up "$UUID" >/dev/null 2>&1 \
  || { warn "con up failed; trying 'dev reapply'"
       "${SUDO[@]}" nmcli dev reapply "$NIC" >/dev/null 2>&1 \
         || warn "activate by hand: nmcli con up '$NAME'"; }

got=""
for _ in $(seq 1 20); do
  got=$(ip -4 -o addr show "$NIC" scope global 2>/dev/null | awk '{print $4}' | head -1)
  [ -n "$got" ] && break
  sleep 0.5
done
[ -n "$got" ] && ok "$NIC has $got" || warn "$NIC still has no global IPv4 address"

if ip -4 -o addr show "$NIC" | grep -q '169\.254\.'; then
  warn "leftover 169.254.x.x on $NIC (harmless; if routing confuses:"
  warn "  ip addr flush dev $NIC && nmcli con up '$NAME')"
fi

hdr "Verifying"
if ip route get "$BOARD" 2>/dev/null | head -1 | grep -q "dev $NIC"; then
  ok "kernel routes $BOARD via $NIC"
else
  ip route get "$BOARD" 2>&1 | sed 's/^/  /'
  warn "kernel is NOT routing $BOARD via $NIC"
fi
ping -c2 -W2 "$BOARD" >/dev/null 2>&1 \
  && ok "$BOARD responds to ping" \
  || warn "$BOARD does not answer ping yet — board booted? replug USB-C"
timeout 3 bash -c "exec 3<>/dev/tcp/$BOARD/22" 2>/dev/null \
  && ok "TCP 22 open — SSH ready" || warn "TCP 22 not reachable"

hdr "Done"
cat <<EOF
  ssh root@$BOARD                     # password: dfrobot
  http://$BOARD                       # local web page
  http://$BOARD:8888                  # Jupyter (enable the service first)

Stored in NetworkManager as profile '$NAME', keyed to MAC $MAC, so it
survives the board's USB re-enumeration. Do NOT fix this with 'ip addr add'.
EOF
