"""Pinned V178 container reader and minimal boot-only replacement verifier."""
import gzip
import hashlib
from pathlib import Path
import shutil
import struct
import zlib

CHUNK = 8 * 1024 * 1024
FLASH_NAME = 'V8-T800T11-LF1V178.001228_notfull.img'
STOCK_SHA = 'd152d88de136280996b375df6e50ab5dc5210783a4a81ac156324fd6591664e7'
ROOT_SHA = '8f72558a49a680f8776a6f449ff2da17672ac3a00eec4d374706a903291517ae'
BOOT_SHA = '11baa5296226ead14dbf49ec0ef948f04706664d10f4801ad770c5888a388895'
SIZE = 2913239064


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path, kind='sha256'):
    result = hashlib.new(kind)
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(CHUNK), b''):
            result.update(data)
    return result.hexdigest()


def crc(path):
    value = 0
    with Path(path).open('rb') as stream:
        stream.seek(4)
        for data in iter(lambda: stream.read(CHUNK), b''):
            value = zlib.crc32(data, value)
    return value ^ 0xffffffff


def records(path):
    require(path.stat().st_size == SIZE and digest(path) == STOCK_SHA, '原包大小或摘要错误')
    with path.open('rb') as stream:
        header = stream.read(64)
        stored, version, magic, size, alignment, count = struct.unpack_from('<IIIQII', header)
        require(version == 2 and magic == 0x27b51956 and count == 39 and size == SIZE, '不支持的固件容器')
        table = stream.read(count * 576)
    require(crc(path) == stored, '原包 CRC 错误')
    result = []
    for index in range(count):
        row = table[index*576:(index+1)*576]
        ident, kind, current, offset, length = struct.unpack_from('<IIQQQ', row)
        require(ident == index and offset + length <= size, '固件记录越界')
        result.append(dict(main=row[32:288].split(b'\0')[0].decode(), sub=row[288:544].split(b'\0')[0].decode(),
                           offset=offset, size=length))
    return result


def cpio(data):
    entries = {}
    position = 0
    while position + 110 <= len(data):
        header = data[position:position+110]
        require(header[:6] in (b'070701', b'070702'), '不支持的 ramdisk 格式')
        fields = [int(header[i:i+8], 16) for i in range(6, 110, 8)]
        size, name_size = fields[6], fields[11]
        position += 110
        require(0 < name_size <= 4096 and position + name_size <= len(data), 'ramdisk 文件名越界')
        name = data[position:position+name_size-1].decode()
        position = (position + name_size + 3) // 4 * 4
        require(position + size <= len(data), 'ramdisk 内容越界')
        content = data[position:position+size]
        position = (position + size + 3) // 4 * 4
        if name == 'TRAILER!!!':
            return entries
        require(name not in entries, '重复 ramdisk 路径')
        entries[name] = (fields[1], fields[2], fields[3], content)
    raise ValueError('ramdisk 缺少结束记录')


def boot(path):
    data = path.read_bytes()
    require(len(data) == 67108864 and data[:8] == b'ANDROID!', 'boot 大小或格式错误')
    require(struct.unpack_from('<I', data, 40)[0] == 3, '仅支持 boot header v3')
    kernel, ramdisk = struct.unpack_from('<II', data, 8)
    start = 4096 + (kernel + 4095) // 4096 * 4096
    require(start + ramdisk <= len(data)-64, 'boot 内容越界')
    return data, data[4096:4096+kernel], cpio(gzip.decompress(data[start:start+ramdisk]))


def verify_overlay(base, new, expected):
    require(digest(base) == BOOT_SHA, 'Root boot 摘要错误')
    old, kernel, entries = boot(base)
    data, new_kernel, new_entries = boot(new)
    require(kernel == new_kernel, '内核意外变化')
    require(old[:12] == data[:12] and old[16:4096] == data[16:4096], 'boot header 意外变化')
    require(set(new_entries) == set(entries) | set(expected), 'ramdisk 文件清单意外变化')
    require(all(new_entries[name] == value for name, value in entries.items()), '原 ramdisk 文件变化')
    require(all(new_entries[name] == value for name, value in expected.items()), '新增 ramdisk 内容或权限不符')
    require(data[-64:-60] == b'AVBf', 'AVB footer 缺失')
    old_offset, old_size = struct.unpack_from('>QQ', old, -44)
    new_offset, new_size = struct.unpack_from('>QQ', data, -44)
    require(data[new_offset:new_offset+new_size] == old[old_offset:old_offset+old_size], 'boot AVB 元数据变化')


def replace_boot(stock, new_boot, output, items):
    part = next(x for x in items if x['main'] == 'PARTITION' and x['sub'] == 'boot_a')
    verify = next(x for x in items if x['main'] == 'VERIFY' and x['sub'] == 'boot_a')
    require(new_boot.stat().st_size == part['size'] == 67108864 and verify['size'] == 48, 'boot 分区大小错误')
    require(not output.exists(), '拒绝覆盖已有输出')
    shutil.copyfile(stock, output)
    with output.open('r+b') as target:
        target.seek(part['offset'])
        target.write(new_boot.read_bytes())
        target.seek(verify['offset'])
        target.write(('sha1sum ' + digest(new_boot, 'sha1')).encode())
    value = crc(output)
    with output.open('r+b') as target:
        target.write(struct.pack('<I', value))
    allowed = sorted([(0, 4), (part['offset'], part['offset']+part['size']),
                      (verify['offset'], verify['offset']+verify['size'])])
    with stock.open('rb') as source, output.open('rb') as target:
        start = 0
        for low, high in allowed + [(SIZE, SIZE)]:
            source.seek(start)
            target.seek(start)
            remaining = low - start
            while remaining:
                length = min(CHUNK, remaining)
                require(source.read(length) == target.read(length), '允许范围外存在变化')
                remaining -= length
            start = high
    checked = []
    with output.open('rb') as stream:
        for entry in items:
            if entry['main'] != 'VERIFY':
                continue
            part = next(x for x in items if x['main'] == 'PARTITION' and x['sub'] == entry['sub'])
            stream.seek(entry['offset'])
            wanted = stream.read(entry['size']).decode()
            stream.seek(part['offset'])
            remaining, hash_value = part['size'], hashlib.sha1()
            while remaining:
                data = stream.read(min(CHUNK, remaining))
                require(bool(data), '分区数据截断')
                hash_value.update(data)
                remaining -= len(data)
            require(wanted == 'sha1sum ' + hash_value.hexdigest(), '分区校验失败：' + entry['sub'])
            checked.append(entry['sub'])
    require(output.stat().st_size == SIZE and crc(output) == value, '输出 CRC 错误')
    return dict(aml_crc32=f'{value:08x}', partition_sha1_verified=checked,
                other_container_bytes_unchanged=True, kernel_unchanged=True)
