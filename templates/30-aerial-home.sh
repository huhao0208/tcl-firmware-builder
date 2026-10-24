#!/system/bin/sh
# TCL T800T11. Wait for framework readiness, finish user 0 startup, then
# dispatch the user's resolved default HOME. No launcher package whitelist.
umask 077
exec > /data/adb/aerial-native-boot.log 2>&1
echo "Native HOME bootstrap v5"
cat /proc/sys/kernel/random/boot_id
cat /proc/uptime
BB=/data/adb/magisk/busybox
attempt=0
ready=0
while [ "$attempt" -lt 90 ]; do
    policy=$("$BB" timeout 5 /system/bin/dumpsys window policy 2>/dev/null)
    case "$policy" in
        *mSystemReady=true*) ready=1; break ;;
    esac
    attempt=$((attempt + 1))
    sleep 1
done
[ "$ready" = 1 ] || { echo "Window policy not ready; no user startup"; exit 1; }
echo "window_policy_ready"
cat /proc/uptime
attempt=0
while [ "$attempt" -lt 3 ]; do
    state=$("$BB" timeout 5 /system/bin/am get-started-user-state 0 2>/dev/null)
    echo "user_state=$state"
    [ "$state" = RUNNING_UNLOCKED ] && break
    if [ "$state" = BOOTING ]; then
        start_result=$("$BB" timeout 20 /system/bin/am start-user -w 0 2>&1)
        echo "$start_result"
    fi
    attempt=$((attempt + 1))
    sleep 1
done
state=$("$BB" timeout 5 /system/bin/am get-started-user-state 0 2>/dev/null)
[ "$state" = RUNNING_UNLOCKED ] || { echo "User not unlocked; no launcher dispatch"; exit 2; }
home=$("$BB" timeout 8 /system/bin/cmd package resolve-activity --components --user 0 -a android.intent.action.MAIN -c android.intent.category.HOME 2>/dev/null)
echo "$home"
# A chooser or fallback is not a selected launcher. Query enabled HOME handlers
# as well, so diagnostics/errors can never pass for a resolved component.
case "$home" in
    ""|android/*|*/com.android.internal.app.*|*/.FallbackHome|*/com.android.settings.FallbackHome)
        echo "No concrete default HOME; no forced takeover"; exit 3 ;;
    */*) ;;
    *) echo "Invalid HOME resolution; no forced takeover"; exit 3 ;;
esac
handlers=$("$BB" timeout 8 /system/bin/cmd package query-activities --components --user 0 -a android.intent.action.MAIN -c android.intent.category.HOME 2>/dev/null)
printf '%s\n' "$handlers" | "$BB" grep -Fxq -- "$home" || {
    echo "Resolved HOME is not an enabled launcher; no forced takeover"; exit 3;
}
dispatch=$("$BB" timeout 10 /system/bin/am start --user 0 -a android.intent.action.MAIN -c android.intent.category.HOME 2>&1)
result=$?
echo "$dispatch"
echo "home_dispatch_exit=$result"
cat /proc/uptime
exit "$result"
