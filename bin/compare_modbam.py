#!/usr/bin/env python3
"""Disk-backed check that alignment preserves every primary read's modifications."""
import argparse
import hashlib
import json
import sqlite3
import pysam


def signature(read):
    mods = read.modified_bases_forward
    if mods is None and (read.has_tag('MM') or read.has_tag('ML')):
        raise ValueError(f'{read.query_name}: invalid modification tags')
    normalized = sorted((str(key), sorted(values)) for key, values in (mods or {}).items())
    data = [read.get_forward_sequence(), normalized, read.get_tag('RG') if read.has_tag('RG') else None]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def compare(before, after, database):
    db = sqlite3.connect(database)
    try:
        db.execute('CREATE TABLE reads (id TEXT PRIMARY KEY, signature TEXT, seen INTEGER DEFAULT 0)')
        with pysam.AlignmentFile(before, 'rb', check_sq=False) as source:
            for read in source.fetch(until_eof=True):
                if read.is_secondary or read.is_supplementary: continue
                try: db.execute('INSERT INTO reads(id,signature) VALUES (?,?)', (read.query_name, signature(read)))
                except sqlite3.IntegrityError: raise ValueError(f'Duplicate input read ID: {read.query_name}')
        with pysam.AlignmentFile(after, 'rb', check_sq=False) as aligned:
            for read in aligned.fetch(until_eof=True):
                if read.is_secondary or read.is_supplementary: continue
                row = db.execute('SELECT signature,seen FROM reads WHERE id=?', (read.query_name,)).fetchone()
                if not row or row[1] or row[0] != signature(read):
                    raise ValueError(f'Alignment changed, duplicated, or introduced read: {read.query_name}')
                db.execute('UPDATE reads SET seen=1 WHERE id=?', (read.query_name,))
        missing = db.execute('SELECT COUNT(*) FROM reads WHERE seen=0').fetchone()[0]
        if missing: raise ValueError(f'Alignment lost {missing} reads')
    finally: db.close()

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('before'); p.add_argument('after'); p.add_argument('--database', default='modifications.sqlite')
    a = p.parse_args()
    compare(a.before, a.after, a.database)
