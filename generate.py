#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate.py - 生成 .pud 增量更新包 (msgpack + zstd)
"""

import sys
import io
import os
import hashlib
import argparse
import zstd
import msgpack

# 强制 stdout/stderr 用 UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def collect_files(base_dir, paths):
    files = {}
    for p in paths.split(';'):
        p = p.strip()
        full = os.path.join(base_dir, p)
        if os.path.isfile(full):
            rel = os.path.relpath(full, base_dir).replace(os.sep, '/')
            files[rel] = full
        elif os.path.isdir(full):
            for root, dirs, filenames in os.walk(full):
                dirs[:] = [d for d in dirs if d != '__pycache__']
                for fname in filenames:
                    if fname.endswith('.pyc'):
                        continue
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, base_dir).replace(os.sep, '/')
                    files[rel] = fpath
    return files


def file_hash(data):
    return hashlib.sha256(data).hexdigest()


def generate_pud(old_base, new_base, old_paths, new_paths, from_ver, to_ver):
    print(f"Collecting base files from: {old_base}")
    old_files = collect_files(old_base, old_paths)
    print(f"Base files: {len(old_files)}")

    print(f"Collecting target files from: {new_base}")
    new_files = collect_files(new_base, new_paths)
    print(f"Target files: {len(new_files)}")

    added = {}
    modified = {}
    deleted = []

    for rel, new_path in new_files.items():
        with open(new_path, 'rb') as f:
            content = f.read()

        if rel not in old_files:
            added[rel] = {
                'hash': file_hash(content),
                'size': len(content),
                'content': content,
            }
        else:
            with open(old_files[rel], 'rb') as f:
                old_content = f.read()
            if file_hash(old_content) != file_hash(content):
                modified[rel] = {
                    'hash': file_hash(content),
                    'size': len(content),
                    'content': content,
                }

    for rel in old_files:
        if rel not in new_files:
            deleted.append(rel)

    pud = {
        'from': from_ver,
        'to': to_ver,
        'added': added,
        'modified': modified,
        'deleted': deleted,
    }

    print(f"Added: {len(added)}")
    print(f"Modified: {len(modified)}")
    print(f"Deleted: {len(deleted)}")

    return pud


def main():
    parser = argparse.ArgumentParser(description='Generate .pud incremental update package')
    parser.add_argument('--old', required=True)
    parser.add_argument('--new', required=True)
    parser.add_argument('--old-base', required=True)
    parser.add_argument('--new-base', required=True)
    parser.add_argument('--from', dest='from_ver', required=True)
    parser.add_argument('--to', dest='to_ver', required=True)
    parser.add_argument('--output', required=True)

    args = parser.parse_args()

    pud = generate_pud(
        old_base=args.old_base,
        new_base=args.new_base,
        old_paths=args.old,
        new_paths=args.new,
        from_ver=args.from_ver,
        to_ver=args.to_ver,
    )

    payload = msgpack.packb(pud, use_bin_type=True)
    compressed = zstd.compress(payload, 20)

    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
    with open(args.output, 'wb') as f:
        f.write(len(payload).to_bytes(4, 'little'))
        f.write(compressed)

    print(f"PUD written to: {args.output}")
    print(f"Uncompressed: {len(payload)} bytes")
    print(f"Compressed (zstd 20): {len(compressed)} bytes")


if __name__ == '__main__':
    main()