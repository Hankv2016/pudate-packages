#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate.py - 生成 .pud 增量更新包
"""

import sys
import io
import os
import json
import hashlib
import base64
import argparse
import zlib

# 强制 stdout/stderr 用 UTF-8，避免 Windows CI 上 cp1252 编码炸
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def collect_files(base_dir, paths):
    """
    从 base_dir 中收集 paths 指定的文件列表。
    paths: 分号分隔的目录或文件路径，如 "PCbuild/amd64;Lib"
    返回: {相对路径: 绝对路径}
    """
    files = {}
    for p in paths.split(';'):
        p = p.strip()
        full = os.path.join(base_dir, p)
        if os.path.isfile(full):
            rel = os.path.relpath(full, base_dir).replace(os.sep, '/')
            files[rel] = full
        elif os.path.isdir(full):
            for root, dirs, filenames in os.walk(full):
                # 跳过 __pycache__ 等
                dirs[:] = [d for d in dirs if d != '__pycache__']
                for fname in filenames:
                    # 跳过 .pyc
                    if fname.endswith('.pyc'):
                        continue
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, base_dir).replace(os.sep, '/')
                    files[rel] = fpath
    return files


def file_hash(data):
    """计算文件内容的 sha256 hex"""
    return hashlib.sha256(data).hexdigest()


def generate_pud(old_base, new_base, old_paths, new_paths, from_ver, to_ver):
    """
    生成 .pud 差异包数据结构
    """
    print(f"Collecting base files from: {old_base}")
    old_files = collect_files(old_base, old_paths)
    print(f"Base files: {len(old_files)}")

    print(f"Collecting target files from: {new_base}")
    new_files = collect_files(new_base, new_paths)
    print(f"Target files: {len(new_files)}")

    added = {}
    modified = {}
    deleted = []

    # 检查新增和修改
    for rel, new_path in new_files.items():
        with open(new_path, 'rb') as f:
            content = f.read()

        if rel not in old_files:
            # 新增文件
            added[rel] = {
                'hash': file_hash(content),
                'size': len(content),
                'content': base64.b64encode(content).decode('ascii'),
            }
        else:
            # 对比 hash
            with open(old_files[rel], 'rb') as f:
                old_content = f.read()
            if file_hash(old_content) != file_hash(content):
                # 修改的文件
                modified[rel] = {
                    'hash': file_hash(content),
                    'size': len(content),
                    'content': base64.b64encode(content).decode('ascii'),
                }

    # 检查删除
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
    parser.add_argument('--old', required=True, help='Old version file paths (semicolon separated)')
    parser.add_argument('--new', required=True, help='New version file paths (semicolon separated)')
    parser.add_argument('--old-base', required=True, help='Base directory for old version')
    parser.add_argument('--new-base', required=True, help='Base directory for new version')
    parser.add_argument('--from', dest='from_ver', required=True, help='Source version')
    parser.add_argument('--to', dest='to_ver', required=True, help='Target version')
    parser.add_argument('--output', required=True, help='Output .pud file path')

    args = parser.parse_args()

    pud = generate_pud(
        old_base=args.old_base,
        new_base=args.new_base,
        old_paths=args.old,
        new_paths=args.new,
        from_ver=args.from_ver,
        to_ver=args.to_ver,
    )

    # 序列化：先转成 JSON 字符串，再编码为 bytes
    json_str = json.dumps(pud, separators=(',', ':'))
    payload = json_str.encode('utf-8')

    # 可选：zlib 压缩
    compressed = zlib.compress(payload)

    # 写入文件：格式为 [4字节原始大小][压缩数据]
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
    with open(args.output, 'wb') as f:
        f.write(len(payload).to_bytes(4, 'little'))
        f.write(compressed)

    print(f"PUD written to: {args.output}")
    print(f"Uncompressed size: {len(payload)} bytes")
    print(f"Compressed size: {len(compressed)} bytes")


if __name__ == '__main__':
    main()