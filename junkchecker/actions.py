"""Clean actions (Recycle Bin / move to archive folder / zip archive) and undo of the last action.

Every successful action is written to history.jsonl so it can be restored later:
    {"type": "clean", "id": ..., "mode": "recycle|move|zip", "root": ..., "files": n, "bytes": n,
     "items": [{"src": original path, "dst": archive path or zip member, "size": n}], "archive": zip/folder}
"""
import ctypes, os, shutil, struct, time, uuid, zipfile
from ctypes import wintypes

from . import storage

MODES = ("recycle", "move", "zip")


# ------------------------------------------------------------------ helpers
def _arcname(path):
    """C:\\a\\b.txt -> C/a/b.txt ; \\\\srv\\share\\x -> UNC/srv/share/x (keeps archives collision free)."""
    p = os.path.abspath(path)
    drive, rest = os.path.splitdrive(p)
    if drive.startswith("\\\\"):
        head = "UNC/" + drive.strip("\\").replace("\\", "/")
    else:
        head = drive.rstrip(":") or "_"
    return head + "/" + rest.strip("\\/").replace("\\", "/")


def _stamp():
    return time.strftime("%Y%m%d-%H%M%S")


def _gone(items):
    return [it for it in items if not os.path.exists(it["src"])]


# ------------------------------------------------------------------ recycle bin
class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]


def recycle(paths):
    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 3, 4, 0x10, 0x40, 0x400
    paths = [os.path.abspath(p) for p in paths]
    for i in range(0, len(paths), 200):
        chunk = paths[i:i + 200]
        op = _SHFILEOPSTRUCTW(wFunc=FO_DELETE, pFrom="\0".join(chunk) + "\0\0",
                              fFlags=FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI)
        rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if rc not in (0, 0x78):  # 0x78: some files could not be processed; caller checks what is gone
            raise OSError(f"SHFileOperation failed with code 0x{rc:X}")


def parse_recycle_info(data):
    """Parse a Recycle Bin $I file. Returns (original_path, size, deleted_unix_time)."""
    version, size, ft = struct.unpack_from("<qqq", data, 0)
    if version == 2:
        n = struct.unpack_from("<i", data, 24)[0]
        path = data[28:28 + n * 2].decode("utf-16-le")
    elif version == 1:
        path = data[24:24 + 520].decode("utf-16-le")
    else:
        raise ValueError(f"unknown $I version {version}")
    return path.split("\0", 1)[0], size, ft / 1e7 - 11644473600


def recycle_bin_entries(drives):
    """Yield (orig_path, deleted_time, $I path, $R path) for the current user's bins on the given drives."""
    for d in drives:
        base = os.path.join(d + "\\", "$Recycle.Bin")
        try:
            sids = os.listdir(base)
        except OSError:
            continue
        for sid in sids:
            folder = os.path.join(base, sid)
            try:
                names = os.listdir(folder)
            except OSError:
                continue
            for n in names:
                if not n.startswith("$I"):
                    continue
                ipath = os.path.join(folder, n)
                try:
                    with open(ipath, "rb") as fh:
                        orig, _, t = parse_recycle_info(fh.read())
                except (OSError, ValueError, struct.error, UnicodeDecodeError):
                    continue
                yield orig, t, ipath, os.path.join(folder, "$R" + n[2:])


# ------------------------------------------------------------------ actions
def clean(files, mode="recycle", dest=None, root=None, progress=None):
    """files: list of hit dicts (path, size). Returns (event dict, list of failed paths)."""
    if mode not in MODES:
        raise ValueError(mode)
    if mode != "recycle" and not dest:
        raise ValueError("archive destination folder is required for move/zip")
    log = storage.get_logger()
    dest = os.path.abspath(dest) if dest else dest
    items = [dict(src=os.path.abspath(f["path"]), size=f.get("size", 0), dst=None) for f in files]
    archive = None
    if mode == "recycle":
        recycle([it["src"] for it in items])
    elif mode == "move":
        archive = os.path.join(dest, f"JunkChecker-{_stamp()}")
        for i, it in enumerate(items):
            target = os.path.join(archive, *_arcname(it["src"]).split("/"))
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.move(it["src"], target)
                it["dst"] = target
            except OSError as e:
                log.warning("MOVE failed %s: %s", it["src"], e)
            if progress:
                progress(i + 1, len(items))
    else:
        os.makedirs(dest, exist_ok=True)
        archive = os.path.join(dest, f"JunkChecker-{_stamp()}.zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for i, it in enumerate(items):
                try:
                    z.write(it["src"], _arcname(it["src"]))
                    it["dst"] = _arcname(it["src"])
                except OSError as e:
                    log.warning("ZIP failed %s: %s", it["src"], e)
                if progress:
                    progress(i + 1, len(items))
        with zipfile.ZipFile(archive) as z:  # verify before removing originals
            bad = z.testzip()
            if bad:
                raise OSError(f"archive verification failed at {bad}; originals kept")
        for it in items:
            if it["dst"]:
                try:
                    os.remove(it["src"])
                except OSError as e:
                    log.warning("REMOVE after zip failed %s: %s", it["src"], e)
    done = _gone(items)
    failed = [it["src"] for it in items if it not in done]
    event = dict(type="clean", id=uuid.uuid4().hex[:12], time=time.time(), mode=mode, root=root, archive=archive,
                 files=len(done), bytes=sum(it["size"] for it in done), items=done)
    if done:
        storage.append_history(event)
    for it in done:
        log.info("%-8s %10d  %s%s", mode.upper(), it["size"], it["src"], f"  ->  {it['dst']}" if it["dst"] else "")
    for p in failed:
        log.warning("NOT REMOVED %s", p)
    log.info("CLEAN done mode=%s  %d removed, %d failed", mode, len(done), len(failed))
    return event, failed


def last_clean():
    """Most recent clean event that has not been restored yet."""
    hist = storage.read_history()
    restored = {e.get("ref") for e in hist if e.get("type") == "restore"}
    for e in reversed(hist):
        if e.get("type") == "clean" and e.get("id") not in restored:
            return e
    return None


def restore(event):
    """Undo a clean event. Returns (restored paths, failed paths)."""
    log = storage.get_logger()
    ok, failed = [], []
    items = event.get("items", [])
    mode = event.get("mode")
    if mode == "recycle":
        wanted = {os.path.normcase(it["src"]): it for it in items}
        drives = {os.path.splitdrive(it["src"])[0] for it in items if os.path.splitdrive(it["src"])[0][1:2] == ":"}
        best = {}
        for orig, t, ipath, rpath in recycle_bin_entries(sorted(drives)):
            key = os.path.normcase(orig)
            if key in wanted and t >= event["time"] - 120 and (key not in best or t > best[key][0]):
                best[key] = (t, ipath, rpath)
        for key, it in wanted.items():
            if key not in best:
                failed.append(it["src"]); continue
            _, ipath, rpath = best[key]
            try:
                if os.path.exists(it["src"]):
                    raise FileExistsError(it["src"])
                os.makedirs(os.path.dirname(it["src"]), exist_ok=True)
                shutil.move(rpath, it["src"])
                try:
                    os.remove(ipath)
                except OSError:
                    pass
                ok.append(it["src"])
            except OSError as e:
                log.warning("RESTORE failed %s: %s", it["src"], e); failed.append(it["src"])
    elif mode == "move":
        for it in items:
            try:
                if os.path.exists(it["src"]):
                    raise FileExistsError(it["src"])
                os.makedirs(os.path.dirname(it["src"]), exist_ok=True)
                shutil.move(it["dst"], it["src"])
                ok.append(it["src"])
            except (OSError, TypeError) as e:
                log.warning("RESTORE failed %s: %s", it["src"], e); failed.append(it["src"])
    elif mode == "zip":
        try:
            with zipfile.ZipFile(event["archive"]) as z:
                for it in items:
                    try:
                        if os.path.exists(it["src"]):
                            raise FileExistsError(it["src"])
                        os.makedirs(os.path.dirname(it["src"]), exist_ok=True)
                        with z.open(it["dst"]) as s, open(it["src"], "wb") as d:
                            shutil.copyfileobj(s, d)
                        ok.append(it["src"])
                    except (OSError, KeyError) as e:
                        log.warning("RESTORE failed %s: %s", it["src"], e); failed.append(it["src"])
        except OSError as e:
            log.error("RESTORE cannot open archive %s: %s", event.get("archive"), e)
            failed = [it["src"] for it in items]
    for p in ok:
        log.info("RESTORED %s", p)
    log.info("RESTORE done id=%s  %d restored, %d failed", event.get("id"), len(ok), len(failed))
    storage.append_history(dict(type="restore", ref=event.get("id"), files=len(ok), failed=len(failed)))
    return ok, failed
