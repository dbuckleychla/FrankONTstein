#!/usr/bin/env python3
"""Name published copies, preserving directory structure and local report links.

Never rewrite scientific tables, VCFs, archives or logs. Only report documents
(HTML, JSON, CSS, Markdown) and the Classy artifact audit contain rewritten links.
"""
import argparse
import os
from pathlib import Path
import re
from urllib.parse import quote


def rename_artifacts(root, sample):
    root = Path(root)
    files = sorted(p for p in root.rglob('*') if p.is_file())
    mapping = {p: p.with_name(p.name if sample in p.name else sample + '.' + p.name) for p in files}
    destinations = list(mapping.values())
    if len(set(destinations)) != len(destinations):
        raise ValueError('Sample-prefixed artifact filenames collide')
    for source, target in mapping.items():
        if source.suffix.lower() not in {'.html', '.json', '.css', '.md'} and source.name != 'artifact_audit.txt':
            continue
        # Recognize paths relative to the document, publication root, and its
        # parent (Classy JSON uses classy/... references). Longest match wins.
        links = {}
        for old, new in mapping.items():
            if old == new:
                continue
            for anchor in (source.parent, root, root.parent):
                a, b = os.path.relpath(old, anchor), os.path.relpath(new, anchor)
                links[a] = b
                links[quote(a)] = quote(b)
        if links:
            pattern = r'(?<![\w./-])(?:' + '|'.join(re.escape(s) for s in sorted(links, key=len, reverse=True)) + r')(?![\w./-])'
            text = source.read_text()
            source.write_text(re.sub(pattern, lambda m: links[m.group()], text))
    for source, target in mapping.items():
        if source != target:
            source.rename(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    parser.add_argument('sample')
    args = parser.parse_args()
    rename_artifacts(args.directory, args.sample)
