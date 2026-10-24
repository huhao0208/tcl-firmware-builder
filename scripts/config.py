"""Finite public build contract. Untrusted request text is never executed."""
import hashlib
import json
import re
import os

OPTIONS = json.loads((__import__('pathlib').Path(__file__).resolve().parents[1]/'web/catalog.json').read_text())
DEVICE = OPTIONS['device']['id']
APPS = {app['id']: (app['label'], app['package']) for app in OPTIONS['apps']}
DEFAULT = OPTIONS['defaults']
FIELDS = set(DEFAULT)
MARKER = '<!-- TVFW:1 -->'


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('重复配置字段')
        result[key] = value
    return result


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError('配置字段缺失或包含未知字段')
    if type(value['schema']) is not int or value['schema'] != 1 or value['device'] != DEVICE:
        raise ValueError('仅支持 TCL T800T11 / V178 配置格式 v1')
    for key in ['root', 'ads', 'remote_key']:
        if type(value[key]) is not bool:
            raise ValueError(key + ' 必须为布尔值')
    if value['launcher'] not in ('stock', 'aerial'):
        raise ValueError('不支持的桌面')
    if value['install_policy'] not in ('vendor', 'home', 'home_adb'):
        raise ValueError('不支持的安装策略')
    apps = value['remove_apps']
    if not isinstance(apps, list) or len(apps) > len(APPS) or any(type(x) is not str or x not in APPS for x in apps):
        raise ValueError('仅支持列出的七项预装应用')
    if len(set(apps)) != len(apps):
        raise ValueError('精简应用列表不能重复')
    if value['remote_key'] and value['launcher'] != 'aerial':
        raise ValueError('购物键配置需要 Aerial 桌面')
    if not value['root'] and (value['launcher'] != 'stock' or value['ads'] or value['remote_key'] or apps or value['install_policy'] != 'vendor'):
        raise ValueError('扩展功能需要 Magisk 底包；原包模式不包含扩展')
    return dict(value, remove_apps=sorted(apps))


def parse(text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > 4096:
        raise ValueError('配置过长')
    return validate(json.loads(text, object_pairs_hook=unique_object))


def from_issue(body):
    if not isinstance(body, str) or len(body.encode('utf-8')) > 8192 or body.count(MARKER) != 1:
        raise ValueError('请使用配置网页提交有效构建请求')
    matches = re.findall(r'```json\s*\n(.*?)\n```', body, re.S)
    if len(matches) != 1:
        raise ValueError('请求中必须有一份 JSON 配置')
    return parse(matches[0])


def canonical(value):
    return json.dumps(validate(value), sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def is_custom(value):
    return value['root'] and (value['launcher'] != 'stock' or value['ads'] or value['remote_key'] or
                              value['remove_apps'] or value['install_policy'] != 'vendor')


def recipe_digest(root):
    paths = [root/'catalog/inputs.json', root/'web/catalog.json']
    for folder in ['scripts', 'templates', 'components']:
        paths += [p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode() + b'\0' + path.read_bytes() + b'\0')
    digest.update(os.environ.get('GITHUB_SHA', 'local').encode())
    return digest.hexdigest()


def build_id(value, recipe):
    return hashlib.sha256((canonical(value) + '\n' + recipe).encode()).hexdigest()[:16]
