"""Scanner: walks a folder, classifies files with the rule set, applies keep-N and protections."""
import collections, fnmatch, os, subprocess, time

from .rules import KEEP, SAFE, UNKNOWN, load_rules
from . import platform_win as pw

SKIP_DIRS = {".git", ".svn", ".hg", "node_modules", "$recycle.bin", "system volume information"}
ARCHIVE_EXT = (".zip", ".rar", ".7z")


class Cancelled(Exception):
    pass


def excluded(path, excludes):
    """excludes: absolute folder paths or glob patterns (matched case-insensitively on the full path)."""
    p = os.path.normcase(os.path.abspath(path))
    for e in excludes:
        e = e.strip()
        if not e:
            continue
        if any(ch in e for ch in "*?["):
            if fnmatch.fnmatch(p, os.path.normcase(e)):
                return True
        else:
            ep = os.path.normcase(os.path.abspath(e))
            if p == ep or p.startswith(ep.rstrip("\\/") + os.sep):
                return True
    return False


def git_tracked(root):
    tracked, repos = set(), []
    for dp, dn, fn in os.walk(root):
        if ".git" in dn:
            repos.append(dp)
            try:
                out = subprocess.run(["git", "-C", dp, "ls-files", "-z"], capture_output=True, check=True,
                                     creationflags=pw.NO_WINDOW, timeout=60).stdout
                for rel in out.decode("utf-8", "replace").split("\0"):
                    if rel:
                        tracked.add(os.path.normcase(os.path.abspath(os.path.join(dp, rel))))
            except Exception:
                pass
        dn[:] = [d for d in dn if d.lower() not in SKIP_DIRS]
    return tracked, repos


def walk(root, excludes=(), skip_network=True, cancel=None, progress=None):
    """Yield (dirpath, relative parts, DirEntry) for files; skips excluded/system dirs and reparse points."""
    stack, n = [root], 0
    while stack:
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        d = stack.pop()
        if excluded(d, excludes):
            continue
        try:
            with os.scandir(d) as it:
                entries = list(it)
        except OSError:
            continue
        rel = os.path.relpath(d, root)
        parts = [] if rel == "." else rel.split(os.sep)
        for e in entries:
            if e.is_dir(follow_symlinks=False):
                if e.name.lower() in SKIP_DIRS or pw.is_reparse_point(e):
                    continue
                if skip_network and pw.is_network_path(e.path) and not pw.is_network_path(root):
                    continue
                stack.append(e.path)
            elif e.is_file(follow_symlinks=False):
                n += 1
                if progress and n % 500 == 0:
                    progress(n)
                yield d, parts, e


def scan(root, rules=None, big_archive_mb=100, keep_history=3, excludes=(), skip_network=True,
         protect_open=True, cancel=None, progress=None):
    """Return list of hit dicts: path, cat, size, mtime, tracked, status, reason_key."""
    root = os.path.abspath(root)
    rules = rules or load_rules()
    t0, hits = time.time(), []
    for d, parts, e in walk(root, excludes, skip_network, cancel, progress):
        try:
            st = e.stat(follow_symlinks=False)
        except OSError:
            continue
        parts_lower = [p.lower() for p in parts]
        r = rules.classify(parts_lower, e.name)
        if r:
            hits.append(dict(path=e.path, cat=r.category, size=st.st_size, mtime=st.st_mtime, status=r.status))
        elif e.name.lower().endswith(ARCHIVE_EXT) and st.st_size >= big_archive_mb * 1e6:
            hits.append(dict(path=e.path, cat="big-archive", size=st.st_size, mtime=st.st_mtime, status=UNKNOWN))
    if cancel is not None and cancel.is_set():
        raise Cancelled()
    tracked, _ = git_tracked(root)
    for h in hits:
        h["tracked"] = os.path.normcase(os.path.abspath(h["path"])) in tracked
        h["note"] = ""
        if h["tracked"] and h["status"] == SAFE:
            h["status"], h["note"] = UNKNOWN, "tracked"
    if keep_history > 0:
        apply_keep(hits, rules, keep_history)
    if protect_open:
        protect_open_projects(hits)
    return hits


def apply_keep(hits, rules, keep):
    groups = collections.defaultdict(list)
    for h in hits:
        r = rules.by_category.get(h["cat"])
        if not r or not r.keep_group or h["status"] == UNKNOWN:
            continue
        folder = os.path.dirname(h["path"]).lower()
        name = os.path.basename(h["path"])
        if r.keep_group == "regex" and r.keep_regex:
            m = r.keep_regex.match(name)
            doc = (m.group("doc") + "." + m.group("ext")).lower() if m else name.lower()
            order = int(m.group("n")) if m and "n" in m.groupdict() else 0
            key = (folder, h["cat"], doc)
        else:
            key, order = (folder, h["cat"]), 0
        groups[key].append((order, h["mtime"], h))
    for lst in groups.values():
        lst.sort(key=lambda t: (t[0], t[1]), reverse=True)
        for i, (_, _, h) in enumerate(lst):
            if i < keep:
                h["status"], h["note"] = KEEP, "newest"


def protect_open_projects(hits):
    """If an EDA tool keeps project files locked, keep the history/backups of that project."""
    checked = {}
    for h in hits:
        if h["status"] != SAFE:
            continue
        folder = os.path.dirname(h["path"])
        proj = os.path.dirname(folder)  # e.g. Proj/AD for Proj/AD/History
        if proj not in checked:
            locked = False
            try:
                for name in os.listdir(proj):
                    if name.lower().endswith((".prjpcb", ".pcbdoc", ".schdoc", ".kicad_pro", ".kicad_pcb", ".fcstd")):
                        if pw.is_locked(os.path.join(proj, name)):
                            locked = True
                            break
            except OSError:
                pass
            checked[proj] = locked
        if checked[proj]:
            h["status"], h["note"] = KEEP, "open"


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def totals(hits):
    t = {s: [0, 0] for s in (SAFE, UNKNOWN, KEEP)}
    for h in hits:
        t[h["status"]][0] += 1
        t[h["status"]][1] += h["size"]
    return t
