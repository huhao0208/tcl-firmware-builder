#!/system/bin/sh
# First-boot provisioning for this exact board. Not a live migration script.
set -eu
umask 077
fw_tmp=${0%/*}
fw_data=/data/adb/fw-bundle
fw_marker=/data/adb/fw-bundle.done
fw_id=@@ID@@
android_cmd() {
    if output=$("$@" 2>&1); then printf '%s\n' "$output";
    else code=$?; printf '%s\n' "$output"; return "$code"; fi
}
[ "$(id -u)" = 0 ] && [ "$(getprop ro.product.device)" = tc8000_ay30a2 ] || exit 2
if [ -f "$fw_marker" ] && [ "$(cat "$fw_marker")" = "$fw_id" ]; then
    rm -f "$fw_tmp/fw-payload.tgz"
    exit 0
fi
attempt=0
until [ -d /data/adb ]; do
    attempt=$((attempt+1)); [ "$attempt" -lt 120 ] || exit 3; sleep 2
done
exec >>/data/adb/fw-provision.log 2>&1
mkdir -p "$fw_data"
tar -xzf "$fw_tmp/fw-payload.tgz" -C "$fw_data"
cd "$fw_data"
sha256sum -c SHA256SUMS
mkdir -p /data/adb/magisk
if [ ! -x /data/adb/magisk/busybox ]; then
    cp busybox /data/adb/magisk/busybox
    chmod 0755 /data/adb/magisk/busybox
fi
attempt=0
until [ -n "$(cmd package path android 2>/dev/null)" ]; do
    attempt=$((attempt+1)); [ "$attempt" -lt 120 ] || exit 4; sleep 2
done
mkdir -p /data/adb/service.d
cp 30-aerial-home.sh /data/adb/service.d/30-aerial-home.sh
chmod 0755 /data/adb/service.d/30-aerial-home.sh
sh /data/adb/service.d/30-aerial-home.sh || true
for apk in @@APKS@@; do sh install-apk.sh "$fw_data/apps/$apk.apk"; done
for package in @@ROOT_PACKAGES@@; do
    uid=$(android_cmd cmd package list packages -U "$package" | sed -n 's/.*uid:\([0-9]*\).*/\1/p')
    case "$uid" in ''|*[!0-9]*) exit 5;; esac
    [ "$uid" -ge 10000 ] || exit 5
    "$fw_tmp/magisk" --sqlite "INSERT OR REPLACE INTO policies (uid,policy,until,logging,notification) VALUES($uid,2,0,1,1);"
done
@@HOME_SETUP@@
@@ADS_SETUP@@
for package in @@REMOVE_PACKAGES@@; do android_cmd pm uninstall -k --user 0 "$package" || true; done
@@POLICY_SETUP@@
android_cmd am start --user 0 -a android.intent.action.MAIN -c android.intent.category.HOME
@@ADS_APPLY@@
printf '%s\n' "$fw_id" > "$fw_marker.next"
mv "$fw_marker.next" "$fw_marker"
rm -f "$fw_tmp/fw-payload.tgz"
rm -rf "$fw_data/apps"
echo 'First-boot provisioning complete'
