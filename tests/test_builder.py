import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import build
import config
import firmware


class ConfigurationTests(unittest.TestCase):
    def test_default_and_canonical_order(self):
        value = copy.deepcopy(config.DEFAULT)
        reverse = dict(value, remove_apps=list(reversed(value['remove_apps'])))
        self.assertEqual(config.canonical(value), config.canonical(reverse))
        self.assertEqual(len(config.build_id(value, 'a'*64)), 16)
        self.assertNotEqual(config.build_id(value, 'a'*64), config.build_id(value, 'b'*64))

    def test_untrusted_input_is_rejected(self):
        for field, value in [('schema', True), ('device', 'other'), ('root', 'true'),
                             ('ads', 1), ('launcher', '$(curl example)'), ('install_policy', 'unsafe'),
                             ('remove_apps', ['weather', 'weather']), ('remove_apps', ['../../x']),
                             ('remove_apps', [{}])]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                config.validate(dict(config.DEFAULT, **{field: value}))
        for value in [None, [], {}, dict(config.DEFAULT, shell='id')]:
            with self.assertRaises(ValueError): config.validate(value)
        text = json.dumps(config.DEFAULT)
        with self.assertRaises(ValueError): config.parse(text[:-1] + ',"root":true}')
        with self.assertRaises(ValueError): config.parse(' '*4097)

    def test_dependencies_and_issue_contract(self):
        with self.assertRaises(ValueError): config.validate(dict(config.DEFAULT, root=False))
        with self.assertRaises(ValueError): config.validate(dict(config.DEFAULT, launcher='stock'))
        body = config.MARKER + '\n```json\n' + config.canonical(config.DEFAULT) + '\n```'
        self.assertEqual(config.from_issue(body), config.validate(config.DEFAULT))
        for malformed in [None, body*2, body.replace(config.MARKER, ''), body+'\n```json\n{}\n```', body+' '*8192]:
            with self.assertRaises(ValueError): config.from_issue(malformed)
        stock = dict(config.DEFAULT, root=False, launcher='stock', ads=False, remote_key=False, remove_apps=[], install_policy='vendor')
        self.assertFalse(config.is_custom(config.validate(stock)))
        self.assertFalse(config.is_custom(config.validate(dict(stock, root=True))))


class RenderTests(unittest.TestCase):
    def test_selected_payloads_and_shell_syntax(self):
        # Fixed local fixtures only. Never run Android commands or need network/credentials.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            magisk = root/'magisk.apk'
            with zipfile.ZipFile(magisk, 'w') as archive:
                archive.writestr('lib/armeabi-v7a/libbusybox.so', b'fixture-arm')
                archive.writestr('lib/x86_64/libmagiskboot.so', b'fixture-host')
            apk = root/'fixture.apk'; apk.write_bytes(b'fixture-apk')
            catalog = {'components': {name: {'file': 'magisk.apk' if name == 'magisk' else 'fixture.apk'} for name in ['magisk','aerial','castguard','bridge']}}
            choices = [copy.deepcopy(config.DEFAULT)]
            for launcher in ['stock', 'aerial']:
                for policy in ['vendor', 'home', 'home_adb']:
                    choices.append(dict(config.DEFAULT, launcher=launcher, ads=False, remote_key=False, remove_apps=[], install_policy=policy))
            choices.append(dict(config.DEFAULT, launcher='stock', remote_key=False))
            for index, value in enumerate(choices):
                with self.subTest(value=value):
                    work = root/str(index); work.mkdir()
                    with patch.object(build, 'download', side_effect=lambda item, inputs: inputs/item['file']):
                        host, payload, script = build.payload(config.validate(value), 'a'*16, catalog, root, work)
                    self.assertTrue(host.exists())
                    self.assertNotIn('@@', script.read_text())
                    with tarfile.open(payload) as archive:
                        members = {member.name: member for member in archive.getmembers()}
                        self.assertEqual('apps/aerial.apk' in members, value['launcher']=='aerial')
                        self.assertEqual('apps/castguard.apk' in members, value['ads'])
                        self.assertEqual('apps/bridge.apk' in members, value['remote_key'])
                        sums = archive.extractfile('SHA256SUMS').read().decode()
                        for line in sums.splitlines():
                            expected, name = line.split('  ')
                            self.assertEqual(hashlib.sha256(archive.extractfile(name).read()).hexdigest(), expected)
                        self.assertEqual(members['busybox'].mode, 0o755)
                        self.assertTrue(all(member.uid == 0 and member.mtime == 0 for member in members.values()))
                    if value['launcher'] != 'aerial':
                        self.assertNotIn('pm disable-user', script.read_text())
                    for app in config.APPS:
                        self.assertEqual(config.APPS[app][1] in script.read_text(), app in value['remove_apps'])


class ArchiveTests(unittest.TestCase):
    def entry(self, name, content=b''):
        fields = [1,0o100644,0,0,1,0,len(content),0,0,0,0,len(name.encode())+1,0]
        data = b'070701' + ''.join(f'{value:08x}' for value in fields).encode() + name.encode() + b'\0'
        data += b'\0' * (-len(data)%4)
        data += content
        return data+b'\0'*(-len(content)%4)

    def test_cpio_content_permissions_duplicates_and_bounds(self):
        end = self.entry('TRAILER!!!')
        data = self.entry('hello', b'world')
        self.assertEqual(firmware.cpio(data+end), {'hello': (0o100644,0,0,b'world')})
        for value in [data, data[:-1], b'bad'+end, data+data+end, data[:54]+b'ffffffff'+data[62:]+end]:
            with self.assertRaises(ValueError): firmware.cpio(value)

    def test_package_keeps_flash_filename_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root/'small.img'; image.write_bytes(b'fixture-image')
            metadata = {'build_id':'a'*16, 'firmware_sha256':firmware.digest(image)}
            result = build.package(image, metadata, root)
            self.assertEqual(result['zip_sha256'], firmware.digest(root/result['zip_file']))
            with zipfile.ZipFile(root/result['zip_file']) as archive:
                self.assertEqual(set(archive.namelist()), {firmware.FLASH_NAME,'BUILD.json','SHA256SUMS','README-刷机说明.txt'})
                self.assertEqual(archive.read(firmware.FLASH_NAME), image.read_bytes())
                self.assertIn(metadata['firmware_sha256'], archive.read('SHA256SUMS').decode())
            with self.assertRaises(FileExistsError): build.package(image, metadata, root)

    def test_unknown_original_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'bad.img'; path.write_bytes(b'not-firmware')
            with self.assertRaises(ValueError): firmware.records(path)
            with self.assertRaises(ValueError): firmware.boot(path)


if __name__ == '__main__': unittest.main()
