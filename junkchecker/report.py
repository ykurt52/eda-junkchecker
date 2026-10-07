"""Export scan results as CSV or a self-contained HTML report."""
import csv, datetime, html, os

from . import __version__
from .core import human, totals
from .rules import KEEP, SAFE, UNKNOWN


def _ts(t):
    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")


def export_csv(path, hits, root, label=lambda h: h["cat"]):
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["status", "category", "reason", "size_bytes", "modified", "git_tracked", "relative_path", "path"])
        for h in sorted(hits, key=lambda h: (h["status"], -h["size"])):
            w.writerow([h["status"], h["cat"], label(h), h["size"], _ts(h["mtime"]), int(bool(h.get("tracked"))),
                        os.path.relpath(h["path"], root), h["path"]])


def export_html(path, hits, root, label=lambda h: h["cat"], names=None):
    names = names or {SAFE: "Safe to delete", UNKNOWN: "Unknown", KEEP: "Kept"}
    color = {SAFE: "#15803D", UNKNOWN: "#B45309", KEEP: "#6B7280"}
    tot = totals(hits)
    by_cat = {}
    for h in hits:
        c = by_cat.setdefault((h["status"], label(h)), [0, 0])
        c[0] += 1
        c[1] += h["size"]
    e = html.escape
    tiles = "".join(f'<div class="t" style="border-left-color:{color[s]}"><b>{e(names[s])}</b>'
                    f'<span>{human(b)}</span><small>{n} files</small></div>' for s, (n, b) in tot.items())
    cats = "".join(f'<tr><td style="color:{color[s]}">{e(names[s])}</td><td>{e(lab)}</td><td class="r">{n}</td>'
                   f'<td class="r">{human(b)}</td></tr>'
                   for (s, lab), (n, b) in sorted(by_cat.items(), key=lambda kv: -kv[1][1]))
    rows = "".join(f'<tr><td style="color:{color[h["status"]]}">{e(names[h["status"]])}</td>'
                   f'<td class="r">{human(h["size"])}</td><td>{_ts(h["mtime"])}</td><td>{e(label(h))}</td>'
                   f'<td class="p">{e(os.path.relpath(h["path"], root))}</td></tr>'
                   for h in sorted(hits, key=lambda h: -h["size"]))
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>JunkChecker report</title>
<style>
body{{font:14px/1.45 "Segoe UI",system-ui,sans-serif;margin:0;background:#F3F4F6;color:#111827}}
header{{background:#0F1115;color:#F9FAFB;padding:18px 28px}} header small{{color:#9CA3AF;display:block}}
main{{padding:20px 28px}} .tiles{{display:flex;gap:12px;margin-bottom:18px}}
.t{{flex:1;background:#fff;border:1px solid #D1D5DB;border-left:4px solid;padding:10px 14px}}
.t b{{display:block;font-size:11px;color:#6B7280;text-transform:uppercase}} .t span{{font-size:22px;font-weight:700;display:block}}
.t small{{color:#6B7280}} table{{border-collapse:collapse;width:100%;background:#fff;border:1px solid #D1D5DB;margin-bottom:18px}}
th,td{{padding:5px 10px;border-bottom:1px solid #E5E7EB;text-align:left;vertical-align:top}}
th{{font-size:11px;color:#6B7280;text-transform:uppercase;background:#F9FAFB}} .r{{text-align:right;white-space:nowrap}}
.p{{font-family:Consolas,monospace;font-size:12px;word-break:break-all}} h2{{font-size:13px;text-transform:uppercase;color:#6B7280}}
</style></head><body>
<header><b>JunkChecker report</b><small>{e(root)} · {datetime.datetime.now():%Y-%m-%d %H:%M} · v{__version__}</small></header>
<main><div class="tiles">{tiles}</div>
<h2>By category</h2><table><tr><th>Status</th><th>Category</th><th class="r">Files</th><th class="r">Size</th></tr>{cats}</table>
<h2>Files</h2><table><tr><th>Status</th><th class="r">Size</th><th>Modified</th><th>Reason</th><th>Path</th></tr>{rows}</table>
</main></body></html>"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)


def export(path, hits, root, **kw):
    if path.lower().endswith(".csv"):
        export_csv(path, hits, root, kw.get("label", lambda h: h["cat"]))
    else:
        export_html(path, hits, root, **kw)
