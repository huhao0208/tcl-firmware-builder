#!/usr/bin/env python3
"""GitHub request/status bridge. All credentials are job-local GITHUB_TOKEN only."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request

from config import build_id, canonical, from_issue, recipe_digest
from firmware import digest, require

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = Path('work/request.json')
STATUS_MARKER = '<!-- TVFW_STATUS:1 -->'


def repository():
    value = os.environ['GITHUB_REPOSITORY']
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value), 'Invalid repository')
    return value


def api(path, method='GET', value=None):
    request = urllib.request.Request('https://api.github.com/repos/'+repository()+'/'+path,
        data=None if value is None else json.dumps(value).encode(), method=method,
        headers={'Authorization': 'Bearer '+os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json',
                 'Content-Type': 'application/json', 'User-Agent': 'TCL-Firmware-Builder/1'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def status(phase, message, metadata=None):
    if not CONTEXT.exists():
        return
    context = json.loads(CONTEXT.read_text())
    number = context['issue_number']
    run_id = os.environ['GITHUB_RUN_ID']
    require(re.fullmatch(r'[0-9]+', run_id), 'Invalid run ID')
    data = dict(schema=1, phase=phase, message=message, build_id=context.get('build_id'),
                run_url='https://github.com/'+repository()+'/actions/runs/'+run_id,
                release_url=None, configuration=context.get('configuration'))
    if metadata:
        data.update(release_url='https://github.com/'+repository()+'/releases/tag/build-'+metadata['build_id'],
                    zip_file=metadata['zip_file'], zip_sha256=metadata['zip_sha256'],
                    firmware_sha256=metadata['firmware_sha256'], hardware_validation=metadata['hardware_validation'])
    body = STATUS_MARKER+'\n```json\n'+json.dumps(data, ensure_ascii=False, indent=2)+'\n```\n\n'+message
    if metadata:
        body += '\n\n[下载刷机包]('+data['release_url']+') · 完整 IMG 文件名保持不变。自定义组合尚未实刷。'
    body += '\n\n[在构建器查看状态](https://huhao0208.github.io/tcl-firmware-builder/#task='+str(number)+')'
    comment = context.get('comment_id')
    if comment:
        api('issues/comments/'+str(comment), 'PATCH', {'body': body})
    else:
        response = api('issues/'+str(number)+'/comments', 'POST', {'body': body})
        context['comment_id'] = response['id']
        CONTEXT.write_text(json.dumps(context)+'\n')
    with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as summary:
        summary.write('### '+message+'\n\n'+data['run_url']+'\n\n')


def cached(key, recipe, config):
    try:
        release = api('releases/tags/build-'+key)
    except urllib.error.HTTPError as failure:
        if failure.code == 404:
            return None
        raise
    if release['draft']:
        return None
    assets = {item['name']: item for item in release['assets']}
    if 'build.json' not in assets:
        return None
    url = 'https://github.com/'+repository()+'/releases/download/build-'+key+'/build.json'
    with urllib.request.urlopen(url, timeout=30) as response:
        content = response.read(32769)
    require(len(content) <= 32768, 'Cached build manifest too large')
    data = json.loads(content)
    require(data['build_id'] == key and data['recipe_sha256'] == recipe and canonical(data['configuration']) == canonical(config), 'Cached recipe mismatch')
    asset = assets.get(data['zip_file'])
    require(asset and asset['state'] == 'uploaded' and asset['size'] == data['zip_bytes'] and asset.get('digest') == 'sha256:'+data['zip_sha256'], 'Cached artifact mismatch')
    return data


def prepare():
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    number = event.get('issue', {}).get('number') or os.environ.get('INPUT_ISSUE_NUMBER', '')
    require(re.fullmatch(r'[1-9][0-9]{0,7}', str(number)), 'Invalid build request number')
    number = int(number)
    issue = event.get('issue') or api('issues/'+str(number))
    require(not issue.get('pull_request') and issue.get('user', {}).get('type') == 'User', 'Only human issue requests are supported')
    Path('work').mkdir(exist_ok=True)
    CONTEXT.write_text(json.dumps(dict(issue_number=number))+'\n')
    try:
        config = from_issue(issue.get('body'))
        recipe = recipe_digest(ROOT)
        key = build_id(config, recipe)
        CONTEXT.write_text(json.dumps(dict(issue_number=number, build_id=key, configuration=config))+'\n')
        Path('work/config.json').write_text(canonical(config)+'\n')
        existing = cached(key, recipe, config)
        status('ready' if existing else 'queued', '相同配置已构建，直接使用已校验成品。' if existing else '配置已受理，等待构建。', existing)
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
            output.write('cached='+('true' if existing else 'false')+'\n')
            output.write('build_id='+key+'\n')
    except (ValueError, KeyError, json.JSONDecodeError) as failure:
        status('failed', '配置未通过校验：'+str(failure))
        raise


def publish():
    data = json.loads(Path('dist/build.json').read_text())
    context = json.loads(CONTEXT.read_text())
    require(data['build_id'] == context['build_id'], 'Output build ID mismatch')
    archive = Path('dist')/data['zip_file']
    require(archive.is_file() and digest(archive) == data['zip_sha256'], 'Output ZIP hash mismatch')
    tag = 'build-'+data['build_id']
    notes = Path('work/release-notes.md')
    notes.write_text('''# TCL T800T11 V178 选配刷机包

构建校验通过不代表硬件实刷成功。自定义组合为未实刷候选；参考原包 / Root 包仅引用维护者单台同板电视的历史记录。

下载 ZIP 后解压，按内附说明核对 IMG 摘要并准备 U 盘。不要把 ZIP 改名为 IMG，不要通过未经验证的 Recovery ZIP 路径刷入。

配置与来源见 build.json。IMG SHA-256：`'''+data['firmware_sha256']+'`\n\nZIP SHA-256：`'+data['zip_sha256']+'`\n')
    repo = repository()
    assets = [str(archive), str(Path('dist')/(archive.name+'.sha256')), 'dist/build.json']
    found = subprocess.run(['gh', 'release', 'view', tag, '--repo', repo, '--json', 'isDraft'], capture_output=True, text=True)
    if found.returncode == 0:
        current = json.loads(found.stdout)
        if current['isDraft']:
            subprocess.run(['gh', 'release', 'upload', tag, *assets, '--repo', repo, '--clobber'], check=True)
        else:
            existing = cached(data['build_id'], data['recipe_sha256'], data['configuration'])
            require(existing is not None, 'Published artifact incomplete')
            status('ready', '构建已完成，可下载完整刷机包。', existing)
            return
    else:
        subprocess.run(['gh', 'release', 'create', tag, *assets, '--repo', repo, '--draft', '--prerelease', '--target', os.environ['GITHUB_SHA'],
                        '--title', 'TCL V178 · '+data['build_id'], '--notes-file', str(notes)], check=True)
    subprocess.run(['gh', 'release', 'edit', tag, '--repo', repo, '--draft=false', '--prerelease', '--latest=false', '--notes-file', str(notes)], check=True)
    verified = None
    for attempt in range(4):
        try:
            verified = cached(data['build_id'], data['recipe_sha256'], data['configuration'])
            if verified:
                break
        except urllib.error.HTTPError as failure:
            if failure.code not in (404, 502, 503):
                raise
        if attempt < 3:
            time.sleep(5 * (attempt + 1))
    require(verified is not None, 'Published artifact verification failed')
    status('ready', '构建已完成，可下载完整刷机包。', verified)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'building', 'publish', 'failed'])
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    elif args.action == 'building':
        status('building', '正在下载、组装和校验镜像；完成后生成下载包。')
    elif args.action == 'publish':
        publish()
    else:
        status('failed', '本次构建未完成。请查看运行日志；原有配置和下载不受影响。')


if __name__ == '__main__':
    main()
