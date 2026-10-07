"""Rule engine: profiles of rules loaded from default_rules.json plus an optional user rules file."""
import fnmatch, json, os, re

DEFAULT_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_rules.json")
SAFE, UNKNOWN, KEEP = "safe", "unknown", "keep"


class Rule:
    def __init__(self, d, profile_id):
        self.profile = profile_id
        self.category = d["category"]
        self.status = d.get("status", UNKNOWN)
        if self.status not in (SAFE, UNKNOWN):
            raise ValueError(f"rule {self.category}: status must be safe or unknown")
        self.label = d.get("label", {})
        self.dirs = {x.lower() for x in d.get("dirs", [])}
        self.dir_prefixes = [x.lower() for x in d.get("dir_prefixes", [])]
        self.dir_suffixes = [x.lower() for x in d.get("dir_suffixes", [])]
        self.names = [x.lower() for x in d.get("names", [])]
        self.regex = re.compile(d["regex"], re.I) if d.get("regex") else None
        self.require_all = bool(d.get("require_all"))  # folder AND name must match
        keep = d.get("keep")
        self.keep_group = keep.get("group") if keep else None
        self.keep_regex = re.compile(keep["keep_regex"], re.I) if keep and keep.get("keep_regex") else None
        self.gitignore = d.get("gitignore", [])

    def _dir_match(self, parts_lower):
        for p in parts_lower:
            if p in self.dirs or any(p.startswith(x) for x in self.dir_prefixes) \
                    or any(p.endswith(x) for x in self.dir_suffixes):
                return True
        return False

    def _name_match(self, name_lower, name):
        return any(fnmatch.fnmatchcase(name_lower, pat) for pat in self.names) or bool(self.regex and self.regex.search(name))

    def matches(self, parts_lower, name):
        nl = name.lower()
        has_dir = bool(self.dirs or self.dir_prefixes or self.dir_suffixes)
        has_name = bool(self.names or self.regex)
        if self.require_all:
            return (not has_dir or self._dir_match(parts_lower)) and (not has_name or self._name_match(nl, name))
        return (has_dir and self._dir_match(parts_lower)) or (has_name and self._name_match(nl, name))

    def text(self, lang):
        return self.label.get(lang) or self.label.get("en") or self.category


class RuleSet:
    def __init__(self, profiles, disabled=()):
        self.profiles = profiles                      # list of dict(id, name, enabled, rules=[Rule])
        self.disabled = set(disabled)
        self.rules = [r for p in profiles if p["enabled"] and p["id"] not in self.disabled for r in p["rules"]]
        self.by_category = {}
        for p in profiles:
            for r in p["rules"]:
                self.by_category.setdefault(r.category, r)

    def classify(self, parts_lower, name):
        for r in self.rules:
            if r.matches(parts_lower, name):
                return r
        return None

    def label(self, category, lang):
        r = self.by_category.get(category)
        return r.text(lang) if r else category


def _load_file(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_rules(user_rules_path=None, disabled=()):
    """Built-in profiles, then user profiles (same id replaces, new id is appended)."""
    data = _load_file(DEFAULT_RULES)
    profiles = {p["id"]: p for p in data["profiles"]}
    order = [p["id"] for p in data["profiles"]]
    errors = []
    if user_rules_path and os.path.exists(user_rules_path):
        try:
            for p in _load_file(user_rules_path).get("profiles", []):
                if p["id"] not in profiles:
                    order.append(p["id"])
                profiles[p["id"]] = p
        except Exception as e:  # noqa
            errors.append(f"{user_rules_path}: {e}")
    out = []
    for pid in order:
        p = profiles[pid]
        try:
            out.append(dict(id=pid, name=p.get("name", pid), enabled=p.get("enabled", True),
                            rules=[Rule(r, pid) for r in p.get("rules", [])]))
        except Exception as e:  # noqa
            errors.append(f"profile {pid}: {e}")
    rs = RuleSet(out, disabled)
    rs.errors = errors
    return rs
