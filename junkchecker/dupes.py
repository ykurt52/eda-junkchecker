"""Duplicate file finder: group by size, then by a 64 KB head hash, then by full BLAKE2b hash."""
import collections, hashlib, os

from .core import Cancelled, walk

CHUNK = 1 << 20


def _hash(path, limit=None, cancel=None):
    h = hashlib.blake2b(digest_size=20)
    left = limit
    with open(path, "rb") as fh:
        while True:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            n = CHUNK if left is None else min(CHUNK, left)
            if n <= 0:
                break
            b = fh.read(n)
            if not b:
                break
            h.update(b)
            if left is not None:
                left -= len(b)
    return h.hexdigest()


def find_duplicates(root, min_size=1 << 20, excludes=(), skip_network=True, cancel=None, progress=None):
    """Return [{'size': n, 'hash': h, 'paths': [...], 'mtimes': [...]}] sorted by wasted bytes."""
    by_size = collections.defaultdict(list)
    for _, _, e in walk(root, excludes, skip_network, cancel, progress):
        try:
            st = e.stat(follow_symlinks=False)
        except OSError:
            continue
        if st.st_size >= min_size:
            by_size[st.st_size].append((e.path, st.st_mtime))
    groups = []
    for size, files in by_size.items():
        if len(files) < 2:
            continue
        by_head = collections.defaultdict(list)
        for p, m in files:
            try:
                by_head[_hash(p, 65536, cancel)].append((p, m))
            except OSError:
                pass
        for cand in by_head.values():
            if len(cand) < 2:
                continue
            if size <= 65536:
                full = {"": cand}
            else:
                full = collections.defaultdict(list)
                for p, m in cand:
                    try:
                        full[_hash(p, None, cancel)].append((p, m))
                    except OSError:
                        pass
            for h, same in full.items():
                if len(same) >= 2:
                    same.sort(key=lambda t: t[1])  # oldest first = the "original"
                    groups.append(dict(size=size, hash=h, paths=[p for p, _ in same], mtimes=[m for _, m in same]))
    groups.sort(key=lambda g: -g["size"] * (len(g["paths"]) - 1))
    return groups


def wasted(groups):
    return sum(g["size"] * (len(g["paths"]) - 1) for g in groups)
