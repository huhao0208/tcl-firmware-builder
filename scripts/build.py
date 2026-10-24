#!/usr/bin/env python3
"""Reproducible, pinned build of a full USB IMG; never touches a television."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile

from config import APPS, LICENSE_FILES, build_id, canonical, is_custom, parse, recipe_digest
from firmware import BOOT_SHA, FLASH_NAME, ROOT_SHA, SIZE, STOCK_SHA, digest, records, replace_boot, require, verify_overlay

ROOT = Path(__file__).resolve().parents[1]
INPUT_BASE = 'https://github.com/huhao0208/tcl-firmware-builder/releases/download/inputs-v1/'


def download(item, directory):
    name = item['file']
    require(Path(name).name == name and '/' not in name and '\\' not in name, '非法输入文件名')
    target = directory/name
    if target.exists() and target.stat().st_size == item['bytes'] and digest(target) == item['sha256']:
        return target
    part = target.with_name(name + '.partial')
    request = urllib.request.Request(INPUT_BASE+name, headers={'User-Agent': 'TCL-Firmware-Builder/1'})
    try:
        with urllib.request.urlopen(request, timeout=90) as response, part.open('wb') as output:
            count, hash_value = 0, hashlib.sha256()
            while True:
                data = response.read(1024*1024)
                if not data:
                    break
                count += len(data)
                require(count <= item['bytes'], '输入下载超过固定大小')
                hash_value.update(data)
                output.write(data)
        require(count == item['bytes'] and hash_value.hexdigest() == item['sha256'], '输入下载校验失败：'+name)
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)
    return target


def stock_image(catalog, inputs):
    target = inputs/'stock.img'
    if target.exists() and digest(target) == STOCK_SHA and target.stat().st_size == SIZE:
        return target
    pieces = [download(item, inputs) for item in catalog['stock']['parts']]
    with target.open('wb') as output:
        for piece in pieces:
            with piece.open('rb') as source:
                shutil.copyfileobj(source, output, 1024*1024)
    require(target.stat().st_size == SIZE and digest(target) == STOCK_SHA, '原包分片重组校验失败')
    return target


def policy_scripts():
    policies = json.loads((ROOT/'components/install-policies.json').read_text())
    vendor = policies['vendor']
    temporary = json.loads(json.dumps(vendor))
    temporary[0]['strategies'][3]['packages'] = ['app.hzf.aerial']
    temporary[0]['strategies'][5]['enable'] = 'false'
    values = dict(VENDOR=vendor, HOME=policies['home'], HOME_ADB=policies['home_adb'], TEMPORARY=temporary)
    source = (ROOT/'templates/policy-common.sh').read_text()
    for key, value in values.items():
        source = source.replace('@@'+key+'@@', json.dumps(value, separators=(',', ':')))
    return source.encode(), policies


def payload(config, key, catalog, inputs, work):
    files = {}
    names = ['magisk']
    grants = []
    if config['launcher'] == 'aerial':
        names.append('aerial')
        grants.append('app.hzf.aerial')
    if config['ads']:
        names.append('castguard')
        grants.append('app.hzf.castguard')
    if config['remote_key']:
        names.append('bridge')
    for name in names:
        path = download(catalog['components'][name], inputs)
        files['apps/'+name+'.apk'] = (path.read_bytes(), 0o600)
    with zipfile.ZipFile(inputs/catalog['components']['magisk']['file']) as archive:
        files['busybox'] = (archive.read('lib/armeabi-v7a/libbusybox.so'), 0o755)
        host = work/'magiskboot'
        host.write_bytes(archive.read('lib/x86_64/libmagiskboot.so'))
        host.chmod(0o755)
    for name in ['30-aerial-home.sh', 'install-apk.sh']:
        files[name] = ((ROOT/'templates'/name).read_bytes(), 0o700)
    common, policies = policy_scripts()
    files['policy-common.sh'] = (common, 0o700)
    if config['ads']:
        for path in sorted((ROOT/'components/castguard').iterdir()):
            files['module/'+path.name] = (path.read_bytes(), 0o755 if path.suffix == '.sh' else 0o644)
    if config['install_policy'] != 'vendor':
        text = (ROOT/'templates/install-policy.sh').read_text().replace('@@WANTED@@', json.dumps(policies[config['install_policy']], separators=(',', ':')))
        files['install-policy.sh'] = (text.encode(), 0o700)
    files['configuration.json'] = (canonical(config).encode(), 0o600)
    sums = ''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name, (data, mode) in sorted(files.items()))
    files['SHA256SUMS'] = (sums.encode(), 0o600)
    target = work/'fw-payload.tgz'
    with target.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as zipped, tarfile.open(fileobj=zipped, mode='w|') as archive:
        for name, (data, mode) in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.uid, info.gid, info.mtime = len(data), mode, 0, 0, 0
            archive.addfile(info, io.BytesIO(data))
    home = ''
    if config['launcher'] == 'aerial':
        home = '''android_cmd am broadcast -a app.hzf.aerial.CONFIG -n app.hzf.aerial/app.orchard.tv.guard.ConfigReceiver --ez root_tcl_backlight true
android_cmd cmd package set-home-activity app.hzf.aerial/app.orchard.tv.MainActivity
resolved=$(android_cmd cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME)
case "$resolved" in *app.hzf.aerial/app.orchard.tv.MainActivity*) ;; *) exit 6;; esac
android_cmd settings put secure screensaver_components app.hzf.aerial/app.orchard.tv.dream.AerialDream
android_cmd pm disable-user --user 0 com.tcl.cyberui/com.tcl.cyberui.MainActivity || true
android_cmd pm disable-user --user 0 com.tcl.cyberui/com.tcl.cyberui.DeskSwitchActivityAlias || true'''
    ads = ''
    if config['ads']:
        ads = '''if [ ! -e /data/adb/modules/tcl_cast_ads ]; then
    mkdir -p /data/adb/modules
    rm -rf /data/adb/fw-bundle/module-staging
    cp -R module /data/adb/fw-bundle/module-staging
    mv /data/adb/fw-bundle/module-staging /data/adb/modules/tcl_cast_ads
    chown -R 0:0 /data/adb/modules/tcl_cast_ads
    /data/adb/magisk/busybox find /data/adb/modules/tcl_cast_ads -type d -exec chmod 0755 '{}' ';'
    /data/adb/magisk/busybox find /data/adb/modules/tcl_cast_ads -type f -exec chmod 0644 '{}' ';'
    chmod 0755 /data/adb/modules/tcl_cast_ads/*.sh
fi'''
    policy = ''
    if config['install_policy'] != 'vendor':
        policy = '''printf '#!/system/bin/sh\\nsh /data/adb/fw-bundle/install-policy.sh >> /data/adb/fw-policy.log 2>&1\\n' > /data/adb/service.d/25-tcl-user-install-policy.sh
chmod 0755 /data/adb/service.d/25-tcl-user-install-policy.sh
sh /data/adb/fw-bundle/install-policy.sh'''
    script = (ROOT/'templates/fw-firstboot.sh').read_text()
    values = dict(ID=key, APKS=' '.join(names), ROOT_PACKAGES=' '.join(grants), HOME_SETUP=home, ADS_SETUP=ads,
                  REMOVE_PACKAGES=' '.join(APPS[name][1] for name in config['remove_apps']), POLICY_SETUP=policy,
                  ADS_APPLY='sh /data/adb/modules/tcl_cast_ads/service.sh' if config['ads'] else '')
    for name, value in values.items():
        script = script.replace('@@'+name+'@@', value)
    require('@@' not in script, '首次启动模板未完成')
    firstboot = work/'fw-firstboot.sh'
    firstboot.write_text(script)
    subprocess.run(['sh', '-n', str(firstboot)], check=True)
    for name in ['policy-common.sh', 'install-apk.sh', 'install-policy.sh']:
        if name in files:
            check = work/name
            check.write_bytes(files[name][0])
            subprocess.run(['sh', '-n', str(check)], check=True)
    return host, target, firstboot


def package(image, metadata, output):
    guide = '''仅供 TCL T800T11 / tc8000_ay30a2 / V178。请先核对主板和底包。
这是 U 盘完整镜像包，不是 Recovery update.zip。
1. 解压 ZIP，核对 SHA256SUMS；将唯一的完整 IMG 放在 U 盘根目录，文件名必须保持：
   V8-T800T11-LF1V178.001228_notfull.img
2. 另存原救砖包，不覆盖唯一备份。原厂刷机配置可能清空应用、账号和设置。
3. 电视断电，按住机身电源键再通电；出现升级进度后松开，等待完成。
自定义组合尚未实刷验证；构建校验通过不代表电视一定能启动。
预装应用精简仅为 user 0 移除，原系统分区 APK 保留；安装策略在开机应用，厂商云控可能重新覆盖。
'''
    path = output/('TCL-T800T11-V178-'+metadata['build_id']+'.zip')
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        info = zipfile.ZipInfo(FLASH_NAME, date_time=(2026, 10, 24, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        with archive.open(info, 'w', force_zip64=True) as target, image.open('rb') as source:
            shutil.copyfileobj(source, target, 1024*1024)
        for name, data in [('BUILD.json', json.dumps(metadata, ensure_ascii=False, indent=2)),
                           ('SHA256SUMS', metadata['firmware_sha256']+'  '+FLASH_NAME+'\n'),
                           ('README-刷机说明.txt', guide)]:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 24, 0, 0, 0))
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o100644 << 16
            archive.writestr(info, data.encode('utf-8'))
        for name in LICENSE_FILES:
            info = zipfile.ZipInfo('licenses/'+name, date_time=(2026, 10, 24, 0, 0, 0))
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o100644 << 16
            archive.writestr(info, (ROOT/name).read_bytes())
    require(path.stat().st_size < 2*1024**3, '压缩包超过 GitHub 单附件限制')
    metadata = dict(metadata, zip_file=path.name, zip_bytes=path.stat().st_size, zip_sha256=digest(path))
    (output/'build.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
    (output/(path.name+'.sha256')).write_text(metadata['zip_sha256']+'  '+path.name+'\n')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = parse(args.config.read_text())
    catalog = json.loads((ROOT/'catalog/inputs.json').read_text())
    recipe = recipe_digest(ROOT)
    key = build_id(config, recipe)
    args.work.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    inputs = args.work/'inputs'
    inputs.mkdir(exist_ok=True)
    print('阶段：下载与校验固定输入', flush=True)
    stock = stock_image(catalog, inputs)
    items = records(stock)
    image = args.work/FLASH_NAME
    checks = dict(reference_image=True)
    if config['root']:
        base = download(catalog['components']['root_boot'], inputs)
        require(digest(base) == BOOT_SHA, 'Root boot 校验失败')
        new_boot = base
        if is_custom(config):
            print('阶段：生成选配组件与首次启动镜像', flush=True)
            boot_work = args.work/'boot'
            boot_work.mkdir(exist_ok=True)
            host, archive, script = payload(config, key, catalog, inputs, boot_work)
            rc = ROOT/'templates/fw-builder.rc'
            subprocess.run([str(host.resolve()), 'unpack', '-h', str(base.resolve())], cwd=boot_work, check=True)
            for name, mode, path in [('overlay.d/fw-builder.rc', '0644', rc),
                                     ('overlay.d/sbin/fw-firstboot.sh', '0755', script),
                                     ('overlay.d/sbin/fw-payload.tgz', '0644', archive)]:
                subprocess.run([str(host.resolve()), 'cpio', 'ramdisk.cpio', f'add {mode} {name} {path.resolve()}'], cwd=boot_work, check=True)
            new_boot = boot_work/'new-boot.img'
            subprocess.run([str(host.resolve()), 'repack', str(base.resolve()), str(new_boot.resolve())], cwd=boot_work, check=True)
            expected = {'overlay.d/fw-builder.rc': (0o100644, 0, 0, rc.read_bytes()),
                        'overlay.d/sbin/fw-firstboot.sh': (0o100755, 0, 0, script.read_bytes()),
                        'overlay.d/sbin/fw-payload.tgz': (0o100644, 0, 0, archive.read_bytes())}
            verify_overlay(base, new_boot, expected)
        print('阶段：重建固件并验证全部分区', flush=True)
        checks = replace_boot(stock, new_boot, image, items)
        if not is_custom(config):
            require(digest(image) == ROOT_SHA, '基础 Root 镜像不符合已验证记录')
    else:
        shutil.copyfile(stock, image)
    metadata = dict(schema=1, build_id=key, recipe_sha256=recipe, configuration=config,
                    source_commit=os.environ.get('GITHUB_SHA', 'local'), firmware_file=FLASH_NAME,
                    firmware_bytes=image.stat().st_size, firmware_sha256=digest(image),
                    hardware_validation='unbooted_candidate' if is_custom(config) else 'reference_image',
                    baseline_validation_scope='maintainer_single_device_only', device_flashed=False, checks=checks)
    print('阶段：压缩可下载 ZIP', flush=True)
    result = package(image, metadata, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
