#!/system/bin/sh
# User data is validated as plain rules; no downloaded shell is executed.
set -eu
umask 077
cast_moddir=${0%/*}
cast_data=/data/adb/tcl_cast_ads
cast_bb=/data/adb/magisk/busybox
cast_config="$cast_data/config"
cast_boot=$(cat /proc/sys/kernel/random/boot_id)
cast_op=${1:-status}
fail() { echo "ERR $1"; exit 1; }
[ "$(id -u)" = 0 ] || fail ROOT_REQUIRED
[ -x "$cast_bb" ] || fail BUSYBOX_MISSING
# Android mksh closes this lock descriptor across external commands.
# Execute the controller in Magisk's ash, which preserves the held descriptor.
if [ "${CAST_CTL_SHELL:-}" != ash ]; then
  export CAST_CTL_SHELL=ash
  exec "$cast_bb" ash "$0" "$@"
fi
mkdir -p "$cast_data"
chmod 700 "$cast_data"
exec 9> "$cast_data/lock"
"$cast_bb" flock -n 9 || fail BUSY
validate_rules() {
  [ -f "$1" ] && [ ! -L "$1" ] || return 1
  [ "$(wc -c < "$1")" -le 2097152 ] || return 1
  "$cast_bb" awk '
    NF != 2 || ($1 != "0" && $1 != "1") { bad=1; exit }
    {
      d=$2
      if (length(d)>253 || d !~ /^[a-z0-9.-]+$/ || d ~ /^[0-9.]+$/ || seen[d]++) { bad=1; exit }
      n=split(d,a,"[.]")
      if(n<2 || d=="localhost.localdomain") { bad=1; exit }
      for(i=1;i<=n;i++) if(length(a[i])<1 || length(a[i])>63 || a[i] !~ /^[a-z0-9]/ || a[i] !~ /[a-z0-9]$/) { bad=1; exit }
      count++
      if(count>20000) { bad=1; exit }
    }
    END { if(bad) exit 1 }
  ' "$1"
}
defaults() {
  echo '1 adeng.hpplay.cn'
  echo '1 adeng.lebo.com.cn'
  echo '1 adcdn.hpplay.cn'
}
write_config() {
  {
    echo 'version 1'
    echo "revision $1"
    echo "enabled $2"
    echo "updated $(date +%s)"
    "$cast_bb" awk '{ print "rule " $1 " " $2 }' "$3"
  } > "$cast_config.next"
  chmod 600 "$cast_config.next"
}
if [ ! -f "$cast_config" ]; then
  defaults > "$cast_data/default.rules"
  write_config 0 1 "$cast_data/default.rules"
  mv "$cast_config.next" "$cast_config"
fi
field() { "$cast_bb" awk -v key="$1" '$1==key {print $2; exit}' "$cast_config"; }
get_rules() { "$cast_bb" awk '$1=="rule" {print $2 " " $3}' "$cast_config"; }
mount_root() { "$cast_bb" awk '$5=="/system/etc/hosts" {r=$4} END {print r}' /proc/1/mountinfo; }
is_ours() { case "$1" in */adb/modules/tcl_cast_ads/hosts.current) return 0;; *) return 1;; esac; }
cast_rev=$(field revision)
cast_enabled=$(field enabled)
case "$cast_rev" in ''|*[!0-9]*) fail CONFIG_INVALID;; esac
case "$cast_enabled" in 0|1) ;; *) fail CONFIG_INVALID;; esac
get_rules > "$cast_data/current.rules"
validate_rules "$cast_data/current.rules" || fail CONFIG_INVALID
apply_config() {
  cast_top=$(mount_root)
  if [ -f "$cast_data/active.boot" ] && [ "$(cat "$cast_data/active.boot")" = "$cast_boot" ] && ! is_ours "$cast_top"; then
    echo 'ERR HOSTS_CONFLICT'
    return 1
  fi
  case "$cast_top" in */local/tmp/cast-ads-test-20261024/*) echo 'ERR TEST_OVERLAY_ACTIVE'; return 1;; esac
  if is_ours "$cast_top"; then
    nsenter -t 1 -m -- umount /system/etc/hosts || return 1
  fi
  rm -f "$cast_data/active.boot"
  cast_apply_enabled=$(field enabled)
  cast_active_count=$("$cast_bb" awk '$1=="rule" && $2=="1" {n++} END {print n+0}' "$cast_config")
  [ "$cast_apply_enabled" = 1 ] && [ "$cast_active_count" -gt 0 ] || return 0
  [ ! -e "$cast_moddir/disable" ] && [ ! -e "$cast_moddir/remove" ] || { echo 'ERR MODULE_DISABLED'; return 1; }
  nsenter -t 1 -m -- cat /system/etc/hosts > "$cast_data/base.next" || return 1
  grep -q localhost "$cast_data/base.next" || return 1
  "$cast_bb" awk '
    /^# BEGIN TCL_CAST_ADS/ {skip=1; next}
    /^# END TCL_CAST_ADS/ {skip=0; next}
    !skip {print}
  ' "$cast_data/base.next" > "$cast_moddir/hosts.next" || return 1
  {
    echo ''
    echo '# BEGIN TCL_CAST_ADS - user-managed exact domains'
    "$cast_bb" awk '$1=="rule" && $2=="1" {print "127.0.0.1 " $3; print "::1 " $3}' "$cast_config"
    echo '# END TCL_CAST_ADS'
  } >> "$cast_moddir/hosts.next"
  chown root:root "$cast_moddir/hosts.next" || return 1
  chmod 644 "$cast_moddir/hosts.next" || return 1
  chcon u:object_r:system_file:s0 "$cast_moddir/hosts.next" || return 1
  mv "$cast_moddir/hosts.next" "$cast_moddir/hosts.current" || return 1
  nsenter -t 1 -m -- mount --bind "$cast_moddir/hosts.current" /system/etc/hosts || return 1
  echo "$cast_boot" > "$cast_data/active.boot"
  date > "$cast_moddir/last-applied.txt"
}
status() {
  echo OK
  echo "revision $(field revision)"
  echo "enabled $(field enabled)"
  echo "updated $(field updated)"
  if is_ours "$(mount_root)"; then echo 'runtime active'; else echo 'runtime inactive'; fi
  if [ -e "$cast_moddir/disable" ] || [ -e "$cast_moddir/remove" ]; then echo 'module disabled'; else echo 'module enabled'; fi
  if [ -f "$cast_config.previous" ]; then echo 'undo 1'; else echo 'undo 0'; fi
  "$cast_bb" awk '$1=="rule" {print}' "$cast_config"
}
case "$cast_op" in
  status) status; exit 0;;
  check)
    [ $# -eq 2 ] || fail ARGUMENT
    validate_rules "$2" || fail INVALID_RULE
    echo OK; exit 0;;
  apply) apply_config || fail APPLY_FAILED; status; exit 0;;
  rules|enabled|reset|undo) ;;
  *) fail ARGUMENT;;
esac
[ $# -ge 2 ] || fail ARGUMENT
[ "$2" = "$cast_rev" ] || fail CONFLICT
cast_new_enabled=$cast_enabled
case "$cast_op" in
  rules)
    [ $# -eq 3 ] || fail ARGUMENT
    case "$3" in /data/user/0/app.hzf.castguard/files/pending.rules|/data/local/tmp/cast-ads-test-20261024/test.rules) ;; *) fail INPUT_PATH;; esac
    validate_rules "$3" || fail INVALID_RULE
    cp "$3" "$cast_data/next.rules"
    ;;
  enabled)
    [ $# -eq 3 ] || fail ARGUMENT
    case "$3" in 0|1) cast_new_enabled=$3;; *) fail ARGUMENT;; esac
    get_rules > "$cast_data/next.rules"
    ;;
  reset) defaults > "$cast_data/next.rules"; cast_new_enabled=1;;
  undo)
    [ -f "$cast_config.previous" ] || fail NO_UNDO
    "$cast_bb" awk '$1=="rule" {print $2 " " $3}' "$cast_config.previous" > "$cast_data/next.rules"
    cast_new_enabled=$("$cast_bb" awk '$1=="enabled" {print $2;exit}' "$cast_config.previous")
    ;;
esac
validate_rules "$cast_data/next.rules" || fail INVALID_RULE
case "$cast_new_enabled" in 0|1) ;; *) fail CONFIG_INVALID;; esac
write_config "$((cast_rev + 1))" "$cast_new_enabled" "$cast_data/next.rules"
cp "$cast_config" "$cast_config.before"
mv "$cast_config.next" "$cast_config"
if apply_config; then
  mv "$cast_config.before" "$cast_config.previous"
  status
else
  mv "$cast_config.before" "$cast_config"
  apply_config > /dev/null 2>&1 || true
  fail APPLY_FAILED
fi
