#!/usr/bin/env python3
"""
generate.py - 生成 pudate 差异更新包 (.pud)

用法:
python generate.py \
    --old "PCbuild/amd64;Lib" \
    --new "PCbuild/amd64;Lib" \
    --old-base ./cpython_base \
    --new-base ./cpython_target \
    --from 3.10.11 \
    --to 3.10.21 \
    --output 3.10/pudate_3.10.21.pud
"""

import argparse
import hashlib
import json
import os
import struct
import zlib


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def walk_files(directory):
    result = {}
    for root, dirs, files in os.walk(directory):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, directory)
            result[rel.replace("\\", "/")] = full
    return result


def collect_paths(roots, base):
    result = {}
    for r in roots.split(";"):
        r = r.strip()
        if not r:
            continue
        d = os.path.join(base, r)
        result.update(walk_files(d))
    return result


def generate_pud(old_arg, new_arg, old_base, new_base, from_ver, to_ver, output):
    old_files = collect_paths(old_arg, old_base)
    new_files = collect_paths(new_arg, new_base)

    print(f"基准文件数: {len(old_files)}")
    print(f"目标文件数: {len(new_files)}")

    added = {}
    modified = {}
    deleted = []

    for rel, new_path in new_files.items():
        new_hash = file_hash(new_path)
        if rel not in old_files:
            with open(new_path, 'rb') as f:
                data = f.read()
            added[rel] = {'hash': new_hash, 'size': len(data), 'data': data}
        else:
            old_hash = file_hash(old_files[rel])
            if old_hash != new_hash:
                with open(new_path, 'rb') as f:
                    data = f.read()
                modified[rel] = {'hash': new_hash, 'size': len(data), 'data': data}

    for rel in old_files:
        if rel not in new_files:
            deleted.append(rel)

    pud = {
        'from': from_ver,
        'to': to_ver,
        'added': {},
        'modified': {},
        'deleted': deleted,
    }

    for rel, info in added.items():
        pud['added'][rel] = {
            'hash': info['hash'],
            'size': info['size'],
            'data': zlib.compress(info['data']),
        }

    for rel, info in modified.items():
        pud['modified'][rel] = {
            'hash': info['hash'],
            'size': info['size'],
            'data': zlib.compress(info['data']),
        }

    os.makedirs(os.path.dirname(output) or '.', exist_ok=True)

    with open(output, 'wb') as f:
        payload = json.dumps(pud, separators=(',', ':')).encode('utf-8')
        compressed = zlib.compress(payload)
        header = struct.pack('<4sBII', b'PUD\x00', 1, len(compressed), len(payload))
        f.write(header)
        f.write(compressed)

    total = len(added) + len(modified) + len(deleted)
    size_kb = os.path.getsize(output) / 1024
    print(f"✅ 生成完成: {output}")
    print(f"   新增: {len(added)}  修改: {len(modified)}  删除: {len(deleted)}")
    print(f"   总变更: {total}  文件大小: {size_kb:.1f} KB")


def main():
    parser = argparse.ArgumentParser(description='生成 pudate 差异更新包')
    parser.add_argument('--old', required=True, help='基准版本目录，多个用 ; 分隔')
    parser.add_argument('--new', required=True, help='目标版本目录，多个用 ; 分隔')
    parser.add_argument('--old-base', default='.', help='基准版本根目录')
    parser.add_argument('--new-base', default='.', help='目标版本根目录')
    parser.add_argument('--from', dest='from_ver', required=True)
    parser.add_argument('--to', dest='to_ver', required=True)
    parser.add_argument('--output', required=True)

    args = parser.parse_args()
    generate_pud(
        args.old,
        args.new,
        args.old_base,
        args.new_base,
        args.from_ver,
        args.to_ver,
        args.output
    )


if __name__ == '__main__':
    main()