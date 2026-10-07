"""Unit tests (python -m unittest discover -s tests). They only touch temporary folders."""
import json, os, shutil, struct, sys, tempfile, threading, time, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from junkchecker import actions, core, dupes, gitutil, report, rules, storage  # noqa: E402
from junkchecker.rules import KEEP, SAFE, UNKNOWN  # noqa: E402


def read(path, enc="utf-8"):
    with open(path, encoding=enc) as fh:
        return fh.read()


def touch(path, data=b"x", mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    if mtime:
        os.utime(path, (mtime, mtime))
    return path


class TempCase(unittest.TestCase):
    """Each test gets its own folder tree and its own app-data folder."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jc-test-")
        self.root = os.path.join(self.tmp, "proj")
        data = os.path.join(self.tmp, "appdata")
        self._saved = {k: getattr(storage, k) for k in ("DATA_DIR", "SETTINGS", "USER_RULES", "CACHE_DIR", "LOG_DIR", "HISTORY")}
        storage.DATA_DIR = data
        storage.SETTINGS = os.path.join(data, "settings.json")
        storage.USER_RULES = os.path.join(data, "rules.json")
        storage.CACHE_DIR = os.path.join(data, "cache")
        storage.LOG_DIR = os.path.join(data, "logs")
        storage.HISTORY = os.path.join(data, "history.jsonl")
        for h in list(storage.get_logger().handlers):
            storage.get_logger().removeHandler(h)
            h.close()

    def tearDown(self):
        for h in list(storage.get_logger().handlers):
            storage.get_logger().removeHandler(h)
            h.close()
        for k, v in self._saved.items():
            setattr(storage, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def p(self, *parts):
        return os.path.join(self.root, *parts)


class RulesTest(TempCase):
    def setUp(self):
        super().setUp()
        self.rs = rules.load_rules()

    def cls(self, rel):
        parts = rel.split("/")
        r = self.rs.classify([x.lower() for x in parts[:-1]], parts[-1])
        return r.category if r else None

    def test_builtin(self):
        self.assertEqual(self.cls("AD/History/Board.~(3).PcbDoc.Zip"), "history")
        self.assertEqual(self.cls("AD/__Previews/x.SchDocPreview"), "previews")
        self.assertEqual(self.cls("AD/Project Logs for X/a.LOG"), "logs")
        self.assertEqual(self.cls("AD/Board.PrjPCBStructure"), "altium-cache")
        self.assertEqual(self.cls("AD/Project Outputs for X/gerber.GTL"), "altium-outputs")
        self.assertEqual(self.cls("kicad/proj-backups/proj-2024.zip"), "kicad-backups")
        self.assertIsNone(self.cls("kicad/proj-backups/readme.txt"))     # require_all
        self.assertEqual(self.cls("doc/~$report.docx"), "office-temp")
        self.assertEqual(self.cls("x/Thumbs.db"), "os-junk")
        self.assertEqual(self.cls("cad/case.FCBak"), "freecad-backup")
        self.assertIsNone(self.cls("AD/Board.PcbDoc"))
        self.assertIsNone(self.cls("AD/Board.SchDoc"))

    def test_user_override_and_disable(self):
        os.makedirs(storage.DATA_DIR, exist_ok=True)
        with open(storage.USER_RULES, "w", encoding="utf-8") as fh:
            json.dump({"profiles": [
                {"id": "generic", "name": "Mine", "rules": [{"category": "mine", "status": "unknown", "names": ["*.junk"]}]},
                {"id": "extra", "name": "Extra", "rules": [{"category": "logs2", "status": "safe", "names": ["*.log2"]}]}]}, fh)
        rs = rules.load_rules(storage.USER_RULES)
        self.assertEqual(rs.errors, [])
        r = rs.classify([], "a.junk")
        self.assertEqual((r.category, r.status), ("mine", UNKNOWN))
        self.assertIsNone(rs.classify([], "a.bak"))             # generic profile was replaced
        self.assertEqual(rs.classify([], "x.log2").category, "logs2")
        rs = rules.load_rules(storage.USER_RULES, disabled=["altium", "circuitstudio"])
        self.assertIsNone(rs.classify(["history"], "B.~(1).PcbDoc.Zip"))

    def test_bad_status_reported(self):
        os.makedirs(storage.DATA_DIR, exist_ok=True)
        with open(storage.USER_RULES, "w", encoding="utf-8") as fh:
            json.dump({"profiles": [{"id": "bad", "rules": [{"category": "x", "status": "delete"}]}]}, fh)
        self.assertTrue(rules.load_rules(storage.USER_RULES).errors)


class ScanTest(TempCase):
    def build(self):
        now = time.time()
        for n in range(1, 7):
            touch(self.p("AD", "History", f"Board.~({n}).PcbDoc.Zip"), mtime=now - 1000 + n)
            touch(self.p("AD", "History", f"Main.~({n}).SchDoc.Zip"), mtime=now - 1000 + n)
        touch(self.p("AD", "Board.PcbDoc"), b"real design")
        touch(self.p("AD", "__Previews", "Main.SchDocPreview"))
        touch(self.p("AD", "big.zip"), b"0" * 2_000_000)
        touch(self.p("lib", "Thumbs.db"))
        for i in range(5):
            touch(self.p("kicad", "p-backups", f"p-{i}.zip"), mtime=now - 100 + i)

    def test_scan_keep_and_status(self):
        self.build()
        hits = core.scan(self.root, big_archive_mb=1, keep_history=3, protect_open=False)
        by = {os.path.relpath(h["path"], self.root).replace("\\", "/"): h for h in hits}
        self.assertNotIn("AD/Board.PcbDoc", by)
        for n in (4, 5, 6):
            self.assertEqual(by[f"AD/History/Board.~({n}).PcbDoc.Zip"]["status"], KEEP)
            self.assertEqual(by[f"AD/History/Main.~({n}).SchDoc.Zip"]["status"], KEEP)
        for n in (1, 2, 3):
            self.assertEqual(by[f"AD/History/Board.~({n}).PcbDoc.Zip"]["status"], SAFE)
        self.assertEqual(by["AD/big.zip"]["status"], UNKNOWN)
        self.assertEqual(by["lib/Thumbs.db"]["status"], SAFE)
        kept = sorted(k for k, h in by.items() if k.startswith("kicad") and h["status"] == KEEP)
        self.assertEqual(kept, ["kicad/p-backups/p-2.zip", "kicad/p-backups/p-3.zip", "kicad/p-backups/p-4.zip"])

    def test_keep_zero_marks_all_safe(self):
        self.build()
        hits = core.scan(self.root, keep_history=0, protect_open=False)
        self.assertFalse([h for h in hits if h["status"] == KEEP])

    def test_excludes(self):
        self.build()
        hits = core.scan(self.root, excludes=[self.p("AD")], protect_open=False)
        self.assertTrue(hits)
        self.assertFalse([h for h in hits if os.sep + "AD" + os.sep in h["path"]])
        hits = core.scan(self.root, excludes=["*\\kicad\\*"], protect_open=False)
        self.assertFalse([h for h in hits if "kicad" in h["path"]])

    def test_excluded_helper(self):
        self.assertTrue(core.excluded(r"C:\a\b\c.txt", [r"C:\a\b"]))
        self.assertFalse(core.excluded(r"C:\a\bc\c.txt", [r"C:\a\b"]))
        self.assertTrue(core.excluded(r"C:\x\Libraries\y", [r"*\libraries\*"]))
        self.assertFalse(core.excluded(r"C:\x", ["", "  "]))

    def test_cancel(self):
        self.build()
        ev = threading.Event()
        ev.set()
        with self.assertRaises(core.Cancelled):
            core.scan(self.root, cancel=ev)

    def test_totals_human(self):
        self.assertEqual(core.human(512), "512 B")
        self.assertEqual(core.human(1536), "1.5 KB")
        t = core.totals([dict(status=SAFE, size=10), dict(status=SAFE, size=5), dict(status=KEEP, size=1)])
        self.assertEqual(t[SAFE], [2, 15])


class DupesTest(TempCase):
    def test_find(self):
        a = b"A" * 100_000
        touch(self.p("1", "a.bin"), a, mtime=1000)
        touch(self.p("2", "a-copy.bin"), a, mtime=2000)
        touch(self.p("3", "a-copy2.bin"), a, mtime=3000)
        touch(self.p("x.bin"), a[:-1] + b"B")             # same size, different tail
        touch(self.p("small1"), b"s"), touch(self.p("small2"), b"s")
        g = dupes.find_duplicates(self.root, min_size=1000)
        self.assertEqual(len(g), 1)
        self.assertEqual(len(g[0]["paths"]), 3)
        self.assertTrue(g[0]["paths"][0].endswith("a.bin"))  # oldest first
        self.assertEqual(dupes.wasted(g), 200_000)


class RecycleInfoTest(unittest.TestCase):
    def test_v2(self):
        path = r"E:\work\x.txt"
        ft = int((1_700_000_000 + 11644473600) * 1e7)
        data = struct.pack("<qqqi", 2, 123, ft, len(path) + 1) + (path + "\0").encode("utf-16-le")
        p, size, t = actions.parse_recycle_info(data)
        self.assertEqual((p, size), (path, 123))
        self.assertAlmostEqual(t, 1_700_000_000, delta=1)

    def test_v1(self):
        path = r"C:\a.txt"
        data = struct.pack("<qqq", 1, 5, 0) + (path + "\0").encode("utf-16-le").ljust(520, b"\0")
        self.assertEqual(actions.parse_recycle_info(data)[0], path)

    def test_bad(self):
        with self.assertRaises(ValueError):
            actions.parse_recycle_info(struct.pack("<qqq", 9, 0, 0))


class ActionsTest(TempCase):
    def files(self):
        out = []
        for i in range(3):
            p = touch(self.p("History", f"d.~({i}).PcbDoc.Zip"), b"data%d" % i)
            out.append(dict(path=p, size=os.path.getsize(p)))
        return out

    def roundtrip(self, mode):
        files = self.files()
        dest = os.path.join(self.tmp, "archive")
        ev, failed = actions.clean(files, mode, dest, root=self.root)
        self.assertEqual(failed, [])
        self.assertEqual(ev["files"], 3)
        self.assertFalse(any(os.path.exists(f["path"]) for f in files))
        last = actions.last_clean()
        self.assertEqual(last["id"], ev["id"])
        ok, failed = actions.restore(last)
        self.assertEqual((len(ok), failed), (3, []))
        for i, f in enumerate(files):
            with open(f["path"], "rb") as fh:
                self.assertEqual(fh.read(), b"data%d" % i)
        self.assertIsNone(actions.last_clean())             # restored events are not offered again
        s = storage.stats()
        self.assertEqual((s["operations"], s["total_files"]), (0, 0))   # undone cleans do not count

    def test_move(self):
        self.roundtrip("move")

    def test_zip(self):
        self.roundtrip("zip")

    @unittest.skipUnless(os.environ.get("JUNKCHECKER_TEST_RECYCLE") == "1", "set JUNKCHECKER_TEST_RECYCLE=1 to use the real Recycle Bin")
    def test_recycle(self):
        self.roundtrip("recycle")

    def test_requires_dest(self):
        with self.assertRaises(ValueError):
            actions.clean(self.files(), "zip", None)

    def test_restore_does_not_overwrite(self):
        files = self.files()
        ev, _ = actions.clean(files, "move", os.path.join(self.tmp, "a"))
        touch(files[0]["path"], b"new")
        ok, failed = actions.restore(ev)
        self.assertEqual(failed, [files[0]["path"]])
        with open(files[0]["path"], "rb") as fh:
            self.assertEqual(fh.read(), b"new")


class ReportGitTest(TempCase):
    def hits(self):
        p = touch(self.p("AD", "Board.PrjPCBStructure"))
        return [dict(path=p, cat="altium-cache", size=1, mtime=time.time(), status=SAFE, tracked=True, note="")]

    def test_reports(self):
        h = self.hits()
        out = os.path.join(self.tmp, "r.html")
        report.export(out, h, self.root)
        self.assertIn("Board.PrjPCBStructure", read(out))
        out = os.path.join(self.tmp, "r.csv")
        report.export(out, h, self.root)
        lines = read(out, "utf-8-sig").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("status,category"))

    def test_git_plan(self):
        h = self.hits()
        touch(self.p(".gitignore"), b"*.bak\n")
        plan = gitutil.plan(h, [self.root], rules.load_rules())
        e = plan[self.root]
        self.assertEqual(e["untrack"], ["AD/Board.PrjPCBStructure"])
        self.assertEqual(e["ignore"], ["*.PrjPCBStructure"])
        self.assertIn("git rm --cached", gitutil.commands(self.root, e))
        gitutil.append_gitignore(self.root, e["ignore"])
        self.assertIn("*.PrjPCBStructure", gitutil.existing_ignores(self.root))
        self.assertIn("*.bak", gitutil.existing_ignores(self.root))


class StorageTest(TempCase):
    def test_settings_and_cache(self):
        st = storage.load_settings()
        self.assertEqual(st["action"], "recycle")
        st["last_root"] = self.root
        storage.save_settings(st)
        self.assertEqual(storage.load_settings()["last_root"], self.root)
        p = touch(self.p("a.bak"))
        storage.save_cache(self.root, [dict(path=p), dict(path=self.p("gone.bak"))], 3)
        self.assertEqual(len(storage.load_cache(self.root)["hits"]), 1)


class TreemapTest(unittest.TestCase):
    def test_squarify_area(self):
        from junkchecker.ui.treemap import squarify
        items = [(v, i) for i, v in enumerate([60, 30, 20, 10, 5, 1])]
        rects = squarify(items, 0, 0, 400, 300)
        self.assertEqual(len(rects), 6)
        self.assertAlmostEqual(sum(w * h for _, _, w, h, _ in rects), 400 * 300, delta=1)
        for x, y, w, h, _ in rects:
            self.assertTrue(-1e-6 <= x and x + w <= 400 + 1e-6 and -1e-6 <= y and y + h <= 300 + 1e-6)


class I18nTest(unittest.TestCase):
    def test_same_keys(self):
        from junkchecker.i18n import STRINGS, upper
        self.assertEqual(set(STRINGS["en"]), set(STRINGS["tr"]))
        self.assertEqual(upper("ağaç haritası", "tr"), "AĞAÇ HARİTASI")


if __name__ == "__main__":
    unittest.main()
