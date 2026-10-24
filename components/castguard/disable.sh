#!/system/bin/sh
# Disable this module for subsequent boots and undo only its own current mount.
set -eu
cast_moddir=${0%/*}
cast_busybox=/data/adb/magisk/busybox
touch "$cast_moddir/disable"
cast_mount_root=$("$cast_busybox" awk '$5 == "/system/etc/hosts" { root = $4 } END { print root }' /proc/1/mountinfo)
case "$cast_mount_root" in
  */adb/modules/tcl_cast_ads/hosts.current)
    nsenter -t 1 -m -- umount /system/etc/hosts
    rm -f /data/adb/tcl_cast_ads/active.boot
    echo 'TCL cast ad hosts disabled and its current mount removed.'
    ;;
  *)
    echo 'TCL cast ad hosts disabled. No active mount owned by this module was removed.'
    ;;
esac
