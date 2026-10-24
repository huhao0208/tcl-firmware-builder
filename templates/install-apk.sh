#!/system/bin/sh
set -eu
umask 077
. /data/adb/fw-bundle/policy-common.sh
apk=${1:?Missing verified APK}
case "$apk" in /data/adb/fw-bundle/apps/magisk.apk|/data/adb/fw-bundle/apps/aerial.apk|/data/adb/fw-bundle/apps/castguard.apk|/data/adb/fw-bundle/apps/bridge.apk) ;; *) exit 10;; esac
[ -f "$apk" ] && [ ! -L "$apk" ] || exit 11
pending=/data/adb/fw-install.pending
baseline=/data/adb/fw-install.baseline
restore() {
    original=$(cat "$baseline") || return 1
    known_policy "$original" || return 1
    row=$(query_policy) || return 1
    if [ "$row" = "Row: 0 config_content=$fw_temporary" ]; then write_policy "$original" || return 1; fi
    [ "$(query_policy)" = "Row: 0 config_content=$original" ] || return 1
    rm -f "$pending"
}
[ ! -e "$pending" ] || restore
read_policy || exit 12
printf '%s\n' "$fw_current" > "$baseline.next"
mv "$baseline.next" "$baseline"
touch "$pending"
trap restore EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
write_policy "$fw_temporary"
[ "$(query_policy)" = "Row: 0 config_content=$fw_temporary" ] || exit 13
cat "$apk" | android_cmd "$fw_bb" timeout 90 pm install --user 0 -r -S "$(stat -c %s "$apk")" -- -
