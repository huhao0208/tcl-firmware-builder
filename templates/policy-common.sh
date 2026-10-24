#!/system/bin/sh
fw_uri=content://com.tcl.providers.config/InstallConfig
fw_where="project_id='InstallConfig'"
fw_bb=/data/adb/magisk/busybox
fw_vendor='@@VENDOR@@'
fw_home='@@HOME@@'
fw_home_adb='@@HOME_ADB@@'
fw_temporary='@@TEMPORARY@@'
android_cmd() {
    if output=$("$@" 2>&1); then printf '%s\n' "$output";
    else code=$?; printf '%s\n' "$output"; return "$code"; fi
}
query_policy() { android_cmd "$fw_bb" timeout 10 content query --uri "$fw_uri" --projection config_content --where "$fw_where"; }
write_policy() {
    android_cmd "$fw_bb" timeout 10 content update --uri "$fw_uri" --bind "config_content:s:$(printf '%s' "$1" | sed 's/:/\\:/g')" --where "$fw_where"
    android_cmd am force-stop com.android.packageinstaller
}
known_policy() { case "$1" in "$fw_vendor"|"$fw_home"|"$fw_home_adb") return 0;; *) return 1;; esac; }
read_policy() {
    row=$(query_policy) || return 1
    case "$row" in 'Row: 0 config_content='*) fw_current=${row#'Row: 0 config_content='};; *) return 1;; esac
    known_policy "$fw_current"
}
