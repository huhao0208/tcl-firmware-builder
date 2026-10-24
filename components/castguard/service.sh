#!/system/bin/sh
# No daemon: apply once, only after Android finished booting.
set -eu
umask 022
cast_moddir=${0%/*}
cast_attempt=0
while [ "$(getprop sys.boot_completed)" != "1" ]; do
  [ -e "$cast_moddir/disable" ] && exit 0
  [ -e "$cast_moddir/remove" ] && exit 0
  cast_attempt=$((cast_attempt + 1))
  [ "$cast_attempt" -ge 90 ] && exit 0
  sleep 2
done
[ -e "$cast_moddir/disable" ] && exit 0
[ -e "$cast_moddir/remove" ] && exit 0

/system/bin/sh "$cast_moddir/ctl.sh" apply
