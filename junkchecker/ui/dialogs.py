"""Settings and Git helper dialogs."""
import os, shutil, tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .. import gitutil, storage
from ..rules import DEFAULT_RULES, load_rules
from .theme import FONT, MONO


class _Dialog(tk.Toplevel):
    def __init__(self, app, title, size):
        super().__init__(app)
        self.app, self.C = app, app.C
        self.title(title)
        self.geometry(size)
        self.configure(bg=self.C["surface"])
        self.transient(app)
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())

    def t(self, key, **kw):
        return self.app.t(key, **kw)

    def caption(self, parent, key):
        ttk.Label(parent, text=self.app.upper(self.t(key)), style="SurfCap.TLabel").pack(anchor="w", pady=(14, 4))

    def listbox(self, parent, height):
        C = self.C
        return tk.Listbox(parent, height=height, bg=C["surface"], fg=C["text"], selectbackground=C["sel"],
                          selectforeground=C["text"], highlightthickness=1, highlightbackground=C["border"],
                          highlightcolor=C["accent"], relief="flat", borderwidth=0, font=(FONT, 10), activestyle="none")


class SettingsDialog(_Dialog):
    def __init__(self, app, on_save):
        super().__init__(app, app.t("settings"), "640x720")
        self.on_save = on_save
        st = app.settings
        body = ttk.Frame(self, style="Surface.TFrame")
        body.pack(fill="both", expand=True, padx=22, pady=(4, 0))

        # profiles
        self.caption(body, "s_profiles")
        prof = ttk.Frame(body, style="Surface.TFrame")
        prof.pack(fill="x")
        self.prof_vars = {}
        rules = load_rules(storage.USER_RULES)
        for i, p in enumerate(rules.profiles):
            v = tk.BooleanVar(value=p["id"] not in st["disabled_profiles"])
            ttk.Checkbutton(prof, text=f"{p['name']}  ({len(p['rules'])})", variable=v).grid(
                row=i // 2, column=i % 2, sticky="w", padx=(0, 24))
            self.prof_vars[p["id"]] = v
        ttk.Button(body, text=self.t("s_edit_rules"), style="Ghost.TButton", command=self.edit_rules).pack(anchor="w", pady=(6, 0))
        if rules.errors:
            ttk.Label(body, text="\n".join(rules.errors), foreground=self.C["danger"], style="Surface.TLabel",
                      wraplength=580).pack(anchor="w")

        # excludes
        self.caption(body, "s_excludes")
        exr = ttk.Frame(body, style="Surface.TFrame")
        exr.pack(fill="x")
        self.ex = self.listbox(exr, 5)
        self.ex.pack(side="left", fill="x", expand=True)
        for e in st["excludes"]:
            self.ex.insert("end", e)
        col = ttk.Frame(exr, style="Surface.TFrame")
        col.pack(side="left", padx=(8, 0), anchor="n")
        for key, fn in (("s_add", self.add_folder), ("s_add_pat", self.add_pattern), ("s_remove", self.remove_ex)):
            ttk.Button(col, text=self.t(key), style="Ghost.TButton", command=fn).pack(fill="x", pady=(0, 6))

        # clean action
        self.caption(body, "s_action")
        self.mode = tk.StringVar(value=st["action"])
        mr = ttk.Frame(body, style="Surface.TFrame")
        mr.pack(fill="x")
        for m in ("recycle", "move", "zip"):
            ttk.Radiobutton(mr, text=self.t("mode_" + m).capitalize(), value=m, variable=self.mode).pack(side="left", padx=(0, 18))
        dr = ttk.Frame(body, style="Surface.TFrame")
        dr.pack(fill="x", pady=(6, 0))
        ttk.Label(dr, text=self.t("s_dest"), style="Surface.TLabel").pack(side="left")
        self.dest = tk.StringVar(value=st["archive_dest"])
        ttk.Entry(dr, textvariable=self.dest).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(dr, text=self.t("browse"), style="Ghost.TButton", command=self.pick_dest).pack(side="left")

        # options
        self.caption(body, "s_options")
        self.skip_net = tk.BooleanVar(value=st["skip_network"])
        self.protect = tk.BooleanVar(value=st["protect_open"])
        ttk.Checkbutton(body, text=self.t("s_skip_net"), variable=self.skip_net).pack(anchor="w")
        ttk.Checkbutton(body, text=self.t("s_protect"), variable=self.protect).pack(anchor="w")
        orow = ttk.Frame(body, style="Surface.TFrame")
        orow.pack(fill="x", pady=(6, 0))
        ttk.Label(orow, text=self.t("s_dupe_min"), style="Surface.TLabel").pack(side="left")
        self.dupe_min = tk.DoubleVar(value=st["dupe_min_mb"])
        ttk.Spinbox(orow, from_=0, to=100000, increment=1, width=7, textvariable=self.dupe_min).pack(side="left", padx=8)
        trow = ttk.Frame(body, style="Surface.TFrame")
        trow.pack(fill="x", pady=(8, 0))
        ttk.Label(trow, text=self.t("s_theme"), style="Surface.TLabel").pack(side="left")
        self.theme = tk.StringVar(value=st["theme"])
        for th in ("light", "dark"):
            ttk.Radiobutton(trow, text=self.t(th), value=th, variable=self.theme).pack(side="left", padx=(12, 0))

        bar = ttk.Frame(self, style="Surface.TFrame")
        bar.pack(fill="x", padx=22, pady=18, side="bottom")
        ttk.Button(bar, text=self.t("save"), style="Accent.TButton", command=self.save).pack(side="right")
        ttk.Button(bar, text=self.t("close"), style="Ghost.TButton", command=self.destroy).pack(side="right", padx=8)

    def edit_rules(self):
        if not os.path.exists(storage.USER_RULES):
            os.makedirs(storage.DATA_DIR, exist_ok=True)
            shutil.copyfile(DEFAULT_RULES, storage.USER_RULES)
        os.startfile(storage.USER_RULES)

    def add_folder(self):
        d = filedialog.askdirectory(parent=self, initialdir=self.app.root_dir.get())
        if d:
            self.ex.insert("end", os.path.normpath(d))

    def add_pattern(self):
        p = simpledialog.askstring(self.t("s_add_pat"), self.t("s_pattern_q"), parent=self)
        if p and p.strip():
            self.ex.insert("end", p.strip())

    def remove_ex(self):
        for i in reversed(self.ex.curselection()):
            self.ex.delete(i)

    def pick_dest(self):
        d = filedialog.askdirectory(parent=self)
        if d:
            self.dest.set(os.path.normpath(d))

    def save(self):
        if self.mode.get() != "recycle" and not os.path.isdir(self.dest.get().strip()):
            messagebox.showwarning(self.t("settings"), self.t("s_dest_req"), parent=self)
            return
        st = self.app.settings
        st.update(disabled_profiles=[k for k, v in self.prof_vars.items() if not v.get()],
                  excludes=list(self.ex.get(0, "end")), action=self.mode.get(), archive_dest=self.dest.get().strip(),
                  skip_network=self.skip_net.get(), protect_open=self.protect.get(),
                  dupe_min_mb=max(0.0, float(self.dupe_min.get() or 0)))
        theme_changed = st["theme"] != self.theme.get()
        st["theme"] = self.theme.get()
        storage.save_settings(st)
        storage.get_logger().info("SETTINGS saved: action=%s excludes=%d disabled=%s", st["action"],
                                  len(st["excludes"]), st["disabled_profiles"])
        self.destroy()
        self.on_save(theme_changed)


class GitDialog(_Dialog):
    def __init__(self, app, plan):
        super().__init__(app, app.t("git_title"), "820x560")
        C = self.C
        body = ttk.Frame(self, style="Surface.TFrame")
        body.pack(fill="both", expand=True, padx=22, pady=16)
        ttk.Label(body, text=self.t("git_info"), style="Surface.TLabel", wraplength=760).pack(anchor="w")
        txt = tk.Text(body, bg=C["bg"], fg=C["text"], insertbackground=C["text"], relief="flat", font=(MONO, 9),
                      highlightthickness=1, highlightbackground=C["border"], wrap="none")
        txt.pack(fill="both", expand=True, pady=10)
        self.plan, self.text = plan, txt
        txt.insert("end", "\n\n".join(f"rem {repo}\nrem   {self.t('git_untrack', n=len(e['untrack']))}, "
                                      f"{self.t('git_ignore', n=len(e['ignore']))}\n" + gitutil.commands(repo, e)
                                      for repo, e in plan.items()))
        bar = ttk.Frame(body, style="Surface.TFrame")
        bar.pack(fill="x")
        ttk.Button(bar, text=self.t("git_copy"), style="Accent.TButton", command=self.copy).pack(side="left")
        for repo, e in plan.items():
            if e["ignore"]:
                ttk.Button(bar, text=f"{self.t('git_append')}: {os.path.basename(repo)}", style="Ghost.TButton",
                           command=lambda r=repo, p=e["ignore"]: self.append(r, p)).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text=self.t("close"), style="Ghost.TButton", command=self.destroy).pack(side="right")

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end").strip())
        self.app.set_status("copied")

    def append(self, repo, patterns):
        gitutil.append_gitignore(repo, patterns)
        storage.get_logger().info("GITIGNORE appended %d patterns to %s", len(patterns), repo)
        self.plan[repo]["ignore"] = []
        messagebox.showinfo(self.t("git_title"), self.t("git_appended", p=os.path.join(repo, ".gitignore")), parent=self)
