"""Git helper: untrack junk that was committed by mistake and suggest .gitignore lines."""
import os

from .rules import KEEP


def repo_of(path, repos):
    best = None
    p = os.path.normcase(os.path.abspath(path))
    for r in repos:
        rn = os.path.normcase(os.path.abspath(r))
        if p.startswith(rn.rstrip("\\/") + os.sep) and (best is None or len(r) > len(best)):
            best = r
    return best


def existing_ignores(repo):
    try:
        with open(os.path.join(repo, ".gitignore"), encoding="utf-8", errors="replace") as fh:
            return {ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")}
    except OSError:
        return set()


def plan(hits, repos, rules):
    """Return {repo: {'untrack': [relative paths], 'ignore': [patterns not yet in .gitignore]}}."""
    out = {}
    for h in hits:
        if h["status"] == KEEP:
            continue
        repo = repo_of(h["path"], repos)
        if not repo:
            continue
        entry = out.setdefault(repo, {"untrack": [], "ignore": set()})
        if h.get("tracked"):
            entry["untrack"].append(os.path.relpath(h["path"], repo).replace("\\", "/"))
        r = rules.by_category.get(h["cat"])
        if r:
            entry["ignore"].update(r.gitignore)
    for repo, entry in out.items():
        have = existing_ignores(repo)
        entry["ignore"] = sorted(p for p in entry["ignore"] if p not in have)
        entry["untrack"].sort()
    return {r: e for r, e in out.items() if e["untrack"] or e["ignore"]}


def _q(p):
    return '"' + p.replace('"', '\\"') + '"'


def commands(repo, entry):
    """Shell commands the user can run (we never run git write commands ourselves)."""
    lines = [f"cd /d {_q(repo)}"]
    files = entry["untrack"]
    for i in range(0, len(files), 50):
        lines.append("git rm --cached -- " + " ".join(_q(f) for f in files[i:i + 50]))
    if entry["ignore"]:
        lines.append("rem add these lines to .gitignore:")
        lines += ["rem   " + p for p in entry["ignore"]]
    return "\n".join(lines)


def append_gitignore(repo, patterns):
    path = os.path.join(repo, ".gitignore")
    prefix = ""
    if os.path.exists(path):
        with open(path, "rb") as fh:
            data = fh.read()
        if data and not data.endswith(b"\n"):
            prefix = "\n"
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(prefix + "\n# added by JunkChecker\n" + "\n".join(patterns) + "\n")
