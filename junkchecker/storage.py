"""Settings, scan cache, text log and machine-readable history (JSON lines)."""
import hashlib, json, logging, logging.handlers, os, time

from . import APP

DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP)
SETTINGS = os.path.join(DATA_DIR, "settings.json")
USER_RULES = os.path.join(DATA_DIR, "rules.json")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
LOG_DIR = os.path.join(DATA_DIR, "logs")
HISTORY = os.path.join(DATA_DIR, "history.jsonl")

DEFAULTS = {
    "lang": None, "theme": "light", "last_root": None, "keep_n": 3, "big_mb": 100,
    "excludes": [], "disabled_profiles": [], "action": "recycle", "archive_dest": "",
    "skip_network": True, "protect_open": True, "dupe_min_mb": 1,
}


def load_settings():
    data = dict(DEFAULTS)
    try:
        with open(SETTINGS, encoding="utf-8") as fh:
            data.update(json.load(fh))
    except Exception:
        pass
    return data


def save_settings(data):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = SETTINGS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        os.replace(tmp, SETTINGS)
    except Exception as e:  # noqa
        get_logger().warning("settings write failed: %s", e)


def get_logger():
    log = logging.getLogger(APP)
    if not log.handlers:
        os.makedirs(LOG_DIR, exist_ok=True)
        h = logging.handlers.RotatingFileHandler(os.path.join(LOG_DIR, "junkchecker.log"), maxBytes=2_000_000,
                                                 backupCount=5, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    return log


# ------------------------------------------------------------------ scan cache
def _cache_path(root):
    key = hashlib.sha1(os.path.normcase(os.path.abspath(root)).encode("utf-8")).hexdigest()[:16]
    return os.path.join(CACHE_DIR, key + ".json")


def save_cache(root, hits, keep):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_cache_path(root), "w", encoding="utf-8") as fh:
            json.dump({"root": root, "time": time.time(), "keep": keep, "hits": hits}, fh)
    except Exception as e:  # noqa
        get_logger().warning("cache write failed: %s", e)


def load_cache(root):
    try:
        with open(_cache_path(root), encoding="utf-8") as fh:
            data = json.load(fh)
        data["hits"] = [h for h in data["hits"] if os.path.exists(h["path"])]
        return data
    except Exception:
        return None


# ------------------------------------------------------------------ history (for stats / restore)
def append_history(event):
    """event: dict with at least 'type'. A timestamp is added."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        event = dict(event)
        event.setdefault("time", time.time())
        with open(HISTORY, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa
        get_logger().warning("history write failed: %s", e)


def read_history():
    out = []
    try:
        with open(HISTORY, encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except FileNotFoundError:
        pass
    return out


def stats():
    """Aggregate reclaimed bytes from history."""
    hist = read_history()
    restored = {e.get("ref") for e in hist if e.get("type") == "restore"}
    ev = [e for e in hist if e.get("type") == "clean" and e.get("id") not in restored]
    now = time.time()
    by_month = {}
    for e in ev:
        m = time.strftime("%Y-%m", time.localtime(e["time"]))
        b = by_month.setdefault(m, [0, 0, 0])
        b[0] += e.get("bytes", 0); b[1] += e.get("files", 0); b[2] += 1
    return {
        "total_bytes": sum(e.get("bytes", 0) for e in ev),
        "total_files": sum(e.get("files", 0) for e in ev),
        "operations": len(ev),
        "last30_bytes": sum(e.get("bytes", 0) for e in ev if now - e["time"] < 30 * 86400),
        "by_month": dict(sorted(by_month.items(), reverse=True)),
        "scans": sum(1 for e in hist if e.get("type") == "scan"),
    }
