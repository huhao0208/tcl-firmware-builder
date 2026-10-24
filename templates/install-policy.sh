#!/system/bin/sh
# Bounded boot-time policy application. No background polling daemon.
set -eu
. /data/adb/fw-bundle/policy-common.sh
wanted='@@WANTED@@'
known_policy "$wanted" || exit 2
attempt=0
until read_policy; do
    attempt=$((attempt+1)); [ "$attempt" -lt 90 ] || exit 3; sleep 2
done
[ "$fw_current" = "$wanted" ] || write_policy "$wanted"
[ "$(query_policy)" = "Row: 0 config_content=$wanted" ]
