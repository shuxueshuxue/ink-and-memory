#!/usr/bin/env python3
"""Verify every t('chat.*') key used in components exists in BOTH en and zh blocks of i18n.ts."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / 'src' / 'i18n.ts'

text = I18N.read_text(encoding='utf-8')

def extract_chat_keys(block_text: str) -> set:
    """Parse keys line-by-line using indentation to build dot paths (lines are single-line entries)."""
    keys = set()
    stack = []  # list of (indent, key) for open objects
    for line in block_text.splitlines():
        m = re.match(r'^(\s*)(\w+):\s*(\{)?', line)
        if not m:
            continue
        indent = len(m.group(1))
        key = m.group(2)
        is_obj = bool(m.group(3))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if is_obj:
            stack.append((indent, key))
        else:
            keys.add('chat.' + '.'.join([k for _, k in stack] + [key]))
    return keys

def slice_block(src: str, anchor: str) -> str:
    start = src.index(anchor)
    i = src.index('{', start + len(anchor) - 1)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == '{':
            depth += 1
        elif src[j] == '}':
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    raise ValueError('unbalanced')

en_m = re.search(r"en:\s*\{\s*translation:\s*\{", text)
zh_m = re.search(r"zh:\s*\{\s*translation:\s*\{", text)
en_block = slice_block(text[en_m.end():], '\n      chat:')
zh_block = slice_block(text[zh_m.end():], '\n      chat:')
en_keys = extract_chat_keys(en_block)
zh_keys = extract_chat_keys(zh_block)

def strip_plural(keys: set) -> set:
    return {re.sub(r'_(one|other)$', '', k) for k in keys}

en_base, zh_base = strip_plural(en_keys), strip_plural(zh_keys)
parity_issues = []
for k in sorted(en_base - zh_base):
    parity_issues.append(f'zh missing: {k}')
for k in sorted(zh_base - en_base):
    parity_issues.append(f'en missing: {k}')

# keys used in source
used = set()
for path in list((ROOT / 'src' / 'components' / 'chat').glob('*.tsx')) + list((ROOT / 'src' / 'hooks').glob('useFileUpload.ts')):
    src = path.read_text(encoding='utf-8')
    for m in re.finditer(r"\bt\(\s*'(chat\.[A-Za-z0-9_.]+)'", src):
        used.add(m.group(1))

usage_issues = []
for k in sorted(used):
    if k not in en_base:
        usage_issues.append(f'en missing used key: {k}')
    if k not in zh_base:
        usage_issues.append(f'zh missing used key: {k}')

print(f'en chat keys (base): {len(en_base)}, zh chat keys (base): {len(zh_base)}')
print(f'chat keys used in source: {len(used)}')
if parity_issues or usage_issues:
    print('ISSUES:')
    for line in parity_issues + usage_issues:
        print(' -', line)
    sys.exit(1)
print('OK: all used chat.* keys exist in both en and zh; en/zh key sets are identical.')
