#!/usr/bin/env bash
#
# m10-clash-exclude.sh — keep the M10 USB link out of Clash Verge's TUN.
#
# Host-side helper, for PCs that run a TUN-mode proxy. The M10 lives at 10.1.2.3 on a USB ethernet gadget;
# a TUN-mode proxy can capture 10.0.0.0/8 before the direct route applies, so
# the board looks dark even though the NIC and NetworkManager profile are fine.
#
# This appends
#
#     tun:
#       route-exclude-address:
#         - 10.1.2.0/24
#
# to Clash Verge's Merge.yaml (backing it up first) and reports whether mihomo
# already routes 10.0.0.0/8 DIRECT.
#
# The link itself is configured by the skill:
#   ~/.agents/skills/m10-dev/scripts/m10-net-setup.sh
# See the skill's references/board-link.md for the durable NetworkManager fix.
#
# Usage:
#   scripts/m10-clash-exclude.sh            apply the exclusion (idempotent)
#   scripts/m10-clash-exclude.sh --status   report only, change nothing
#
set -uo pipefail

BOARD="10.1.2.3"
VERGE_PROFILES="$HOME/.local/share/io.github.clash-verge-rev.clash-verge-rev/profiles"
MERGE_YAML="$VERGE_PROFILES/Merge.yaml"
MIHOMO_SOCK="/run/clash-verge-service/users/$(id -u)/verge-mihomo.sock"

DO_STATUS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --status) DO_STATUS=1 ;;
    -h|--help) sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ -t 1 ]; then
  C_G=$'\033[32m'; C_Y=$'\033[33m'; C_R=$'\033[31m'; C_0=$'\033[0m'
else
  C_G=; C_Y=; C_R=; C_0=
fi
ok()   { printf '%sOK%s  %s\n'   "$C_G" "$C_0" "$*"; }
warn() { printf '%sWARN%s %s\n'  "$C_Y" "$C_0" "$*"; }
die()  { printf '%sFAIL%s %s\n'  "$C_R" "$C_0" "$*" >&2; exit 1; }

# ------------------------------------------------------------- route check ---
echo "route to $BOARD:"
ip route get "$BOARD" 2>&1 | sed 's/^/  /'
NIC=$(ip route get "$BOARD" 2>/dev/null | sed -n 's/.* dev \([^ ]*\).*/\1/p' | head -1)
if [ -n "$NIC" ] && [ "$NIC" != "Mihomo" ] && ! printf '%s' "$NIC" | grep -qi tun; then
  ok "direct via $NIC — the TUN is not intercepting"
else
  warn "the TUN is intercepting $BOARD (dev ${NIC:-unknown})"
fi

# ---------------------------------------------------------- mihomo rules -----
if curl -s --unix-socket "$MIHOMO_SOCK" http://localhost/configs >/dev/null 2>&1; then
  RULES=$(curl -s --unix-socket "$MIHOMO_SOCK" http://localhost/rules 2>/dev/null)
  if printf '%s' "$RULES" | grep -q '"payload":"10\.0\.0\.0/8","proxy":"DIRECT"'; then
    ok "mihomo routes 10.0.0.0/8 DIRECT"
  else
    warn "mihomo has no 10.0.0.0/8 DIRECT rule"
  fi
else
  warn "mihomo API not reachable at $MIHOMO_SOCK"
fi

[ "$DO_STATUS" -eq 1 ] && exit 0

# ------------------------------------------------------------- Merge.yaml ----
if [ ! -f "$MERGE_YAML" ]; then
  warn "$MERGE_YAML not found"
  echo "Set this by hand in Clash Verge -> Settings -> Tun Mode"
  echo "  Route Exclude Address: 10.1.2.0/24"
  exit 0
fi

if grep -q '10\.1\.2\.0/24' "$MERGE_YAML"; then
  ok "$MERGE_YAML already excludes 10.1.2.0/24"
  exit 0
fi

BACKUP="$MERGE_YAML.bak-$(date +%Y%m%d-%H%M%S)"
cp -p "$MERGE_YAML" "$BACKUP" || die "could not back up $MERGE_YAML"
cat >> "$MERGE_YAML" <<'YAML'

tun:
  route-exclude-address:
    - 10.1.2.0/24
YAML
ok "appended tun.route-exclude-address (backup: ${BACKUP##*/})"
warn "re-apply the profile for it to take effect:"
warn "  Clash Verge -> Profiles -> click the active profile (or restart the app)"
