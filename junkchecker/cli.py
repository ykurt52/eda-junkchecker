"""Command line interface.

    python -m junkchecker scan  <folder> [--report out.html|out.csv] [--json]
    python -m junkchecker clean <folder> [--mode recycle|move|zip] [--dest DIR] [--include-unknown] [--yes]
    python -m junkchecker dupes <folder> [--min-mb 1]
    python -m junkchecker restore-last [--yes]
    python -m junkchecker stats
    python -m junkchecker gui [folder]
"""
import argparse, json, os, sys, time

from . import __version__, actions, dupes, report, storage
from .core import human, scan, totals
from .rules import KEEP, SAFE, UNKNOWN, load_rules
from . import platform_win as pw


def _scan(args, st):
    rules = load_rules(storage.USER_RULES, st["disabled_profiles"])
    for e in rules.errors:
        print("rules:", e, file=sys.stderr)
    hits = scan(args.folder, rules, big_archive_mb=args.big_mb or st["big_mb"],
                keep_history=st["keep_n"] if args.keep is None else args.keep, excludes=st["excludes"],
                skip_network=st["skip_network"], protect_open=st["protect_open"],
                progress=None if args.quiet else lambda n: print(f"\r  {n} files…", end="", file=sys.stderr))
    if not args.quiet:
        print("\r", end="", file=sys.stderr)
    storage.append_history(dict(type="scan", root=os.path.abspath(args.folder), hits=len(hits),
                                safe_bytes=totals(hits)[SAFE][1]))
    storage.get_logger().info("CLI SCAN root=%s hits=%d", args.folder, len(hits))
    return hits, rules


def _summary(hits):
    for s, (n, b) in totals(hits).items():
        print(f"  {s:8} {n:7d} files  {human(b):>10}")


def cmd_scan(args, st):
    hits, rules = _scan(args, st)
    if args.json:
        json.dump(hits, sys.stdout, indent=1)
        return 0
    _summary(hits)
    if args.report:
        report.export(args.report, hits, os.path.abspath(args.folder), label=lambda h: rules.label(h["cat"], "en"))
        print("report:", args.report)
    return 0


def cmd_clean(args, st):
    tools = pw.running_eda_tools()
    if tools:
        print("warning:", ", ".join(sorted(tools)), "is running; files of open projects are kept.", file=sys.stderr)
    hits, _ = _scan(args, st)
    want = {SAFE, UNKNOWN} if args.include_unknown else {SAFE}
    files = [h for h in hits if h["status"] in want]
    mode = args.mode or st["action"]
    dest = args.dest or st["archive_dest"]
    _summary(hits)
    if not files:
        print("nothing to clean.")
        return 0
    print(f"{len(files)} files, {human(sum(f['size'] for f in files))} -> {mode}" + (f" ({dest})" if mode != "recycle" else ""))
    if not args.yes:
        if sys.stdin is None or not sys.stdin.isatty() or input("proceed? [y/N] ").strip().lower() not in ("y", "yes", "e", "evet"):
            print("aborted (use --yes for unattended runs).")
            return 1
    ev, failed = actions.clean(files, mode, dest, root=os.path.abspath(args.folder))
    print(f"cleaned {ev['files']} files ({human(ev['bytes'])}), {len(failed)} failed.")
    return 0 if not failed else 2


def cmd_dupes(args, st):
    groups = dupes.find_duplicates(args.folder, int(args.min_mb * 1e6), st["excludes"], st["skip_network"])
    for g in groups[:args.top]:
        print(f"{human(g['size']):>10} x{len(g['paths'])}")
        for p in g["paths"]:
            print("    ", p)
    print(f"{len(groups)} groups, {human(dupes.wasted(groups))} wasted.")
    return 0


def cmd_restore(args, st):
    ev = actions.last_clean()
    if not ev:
        print("nothing to restore.")
        return 0
    print(f"last clean: {time.strftime('%Y-%m-%d %H:%M', time.localtime(ev['time']))}  {ev['mode']}  {ev['files']} files")
    if not args.yes and (sys.stdin is None or not sys.stdin.isatty() or input("restore? [y/N] ").strip().lower() not in ("y", "yes", "e", "evet")):
        return 1
    ok, failed = actions.restore(ev)
    print(f"restored {len(ok)}, failed {len(failed)}")
    return 0 if not failed else 2


def cmd_stats(args, st):
    s = storage.stats()
    print(f"reclaimed: {human(s['total_bytes'])} in {s['total_files']} files, {s['operations']} operations, {s['scans']} scans")
    print(f"last 30 days: {human(s['last30_bytes'])}")
    for m, (b, n, ops) in s["by_month"].items():
        print(f"  {m}  {human(b):>10}  {n:6d} files  {ops} ops")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="junkchecker", description="Find and clean junk files in EDA / CAD projects.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")

    def common(sp):
        sp.add_argument("folder")
        sp.add_argument("--keep", type=int, help="newest backups to keep (default: settings)")
        sp.add_argument("--big-mb", type=int, help="large archive threshold in MB")
        sp.add_argument("-q", "--quiet", action="store_true")
    s = sub.add_parser("scan", help="scan and print a summary"); common(s)
    s.add_argument("--report", help="write .html or .csv report"); s.add_argument("--json", action="store_true")
    c = sub.add_parser("clean", help="scan and clean safe files"); common(c)
    c.add_argument("--mode", choices=actions.MODES); c.add_argument("--dest", help="archive folder for move/zip")
    c.add_argument("--include-unknown", action="store_true"); c.add_argument("-y", "--yes", action="store_true")
    d = sub.add_parser("dupes", help="find duplicate files"); d.add_argument("folder")
    d.add_argument("--min-mb", type=float, default=1); d.add_argument("--top", type=int, default=20)
    r = sub.add_parser("restore-last", help="undo the last clean"); r.add_argument("-y", "--yes", action="store_true")
    sub.add_parser("stats", help="show reclaimed space statistics")
    g = sub.add_parser("gui", help="open the window"); g.add_argument("folder", nargs="?")
    args = p.parse_args(argv)
    if args.cmd in (None, "gui"):
        from .ui.app import run
        return run(getattr(args, "folder", None))
    st = storage.load_settings()
    return {"scan": cmd_scan, "clean": cmd_clean, "dupes": cmd_dupes, "restore-last": cmd_restore,
            "stats": cmd_stats}[args.cmd](args, st)
