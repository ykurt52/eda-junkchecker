"""JunkChecker main window."""
import datetime, os, queue, subprocess, sys, threading, time, tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import APP, __version__, actions, core, dupes, gitutil, report, storage
from ..i18n import LANGS, default_lang, tr, upper
from ..rules import KEEP, SAFE, UNKNOWN, load_rules
from .. import platform_win as pw
from . import theme
from .dialogs import GitDialog, SettingsDialog
from .theme import FONT
from .treemap import Treemap

DEFAULT_ROOT = "C:\\"
STATUSES = (SAFE, UNKNOWN, KEEP)


def _ts(t, fmt="%Y-%m-%d %H:%M"):
    return datetime.datetime.fromtimestamp(t).strftime(fmt)


class App(tk.Tk):
    def __init__(self, folder=None):
        super().__init__()
        self.settings = storage.load_settings()
        self.lang = self.settings.get("lang") or default_lang()
        self.log = storage.get_logger()
        self.title(f"{APP} {__version__}")
        self.geometry("1240x780")
        self.minsize(980, 600)
        self.q = queue.Queue()
        self.cancel_ev = None
        self.is_busy = False
        self.hits, self.scanned_root, self.keep_used, self.node_files = [], None, 3, {}
        self.dupe_groups, self.dupe_root, self.dupe_nodes = [], None, {}
        self.eda_tools = set()
        self.rules = load_rules(storage.USER_RULES, self.settings["disabled_profiles"])
        last = self.settings.get("last_root")
        start = folder if folder and os.path.isdir(folder) else (last if last and os.path.isdir(last) else DEFAULT_ROOT)
        self.root_dir = tk.StringVar(value=os.path.normpath(start))
        self.keep_n = tk.IntVar(value=int(self.settings["keep_n"]))
        self.big_mb = tk.IntVar(value=int(self.settings["big_mb"]))
        self.view = tk.StringVar(value="all")
        self.tab = tk.StringVar(value="junk")
        self.status_msg = tk.StringVar()
        self._status = ("ready", {})
        self.rebuild()
        self.restore_cache()
        self.check_eda()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if folder and os.path.isdir(folder):
            self.after(300, self.start_scan)

    # ---------------------------------------------------------------- plumbing
    def post(self, fn, *args):
        """Worker threads never touch Tk directly."""
        self.q.put((fn, args))

    def _poll(self):
        try:
            while True:
                fn, args = self.q.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def t(self, key, **kw):
        return tr(self.lang, key, **kw)

    def upper(self, text):
        return upper(text, self.lang)

    def set_status(self, key, **kw):
        self._status = (key, kw)
        self.status_msg.set(self.t(key, **kw))

    def reason(self, h):
        note = h.get("note")
        if h["status"] == KEEP:
            return self.t("r_open") if note == "open" else self.t("r_keep", n=self.keep_used)
        if h["cat"] == "big-archive":
            return self.t("r_big-archive")
        return self.rules.label(h["cat"], self.lang) + (self.t("r_tracked") if h.get("tracked") else "")

    def on_close(self):
        if self.cancel_ev:
            self.cancel_ev.set()
        self.remember(self.root_dir.get())
        self.destroy()

    # ---------------------------------------------------------------- build / theme
    def rebuild(self):
        for w in self.winfo_children():
            w.destroy()
        self.C = theme.PALETTES.get(self.settings["theme"], theme.PALETTES["light"])
        self.configure(bg=self.C["bg"])
        theme.apply(self, self.C)
        self._build()
        self.apply_lang()

    def _build(self):
        C = self.C
        # header
        head = tk.Frame(self, bg=C["head"], height=58)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text=APP, bg=C["head"], fg=C["head_text"], font=(FONT, 15, "bold")).pack(side="left", padx=(20, 10))
        self.l_sub = tk.Label(head, bg=C["head"], fg=C["head_muted"], font=(FONT, 10))
        self.l_sub.pack(side="left")
        right = tk.Frame(head, bg=C["head"])
        right.pack(side="right", padx=20)
        self.b_settings = ttk.Button(right, style="Head.TButton", command=self.open_settings, takefocus=False)
        self.b_settings.pack(side="left", padx=(0, 14))
        self.b_theme = ttk.Button(right, style="Head.TButton", command=self.toggle_theme, takefocus=False, width=3)
        self.b_theme.pack(side="left", padx=(0, 14))
        self.lang_btns = {}
        for code in LANGS:
            b = ttk.Button(right, text=code.upper(), command=lambda c=code: self.set_lang(c), takefocus=False)
            b.pack(side="left", padx=(0, 6))
            self.lang_btns[code] = b

        # status bar (packed before the body so it stays visible)
        sb = tk.Frame(self, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        sb.pack(fill="x", side="bottom")
        self.pb = ttk.Progressbar(sb, style="Thin.Horizontal.TProgressbar", mode="determinate", value=0, length=180)
        self.pb.pack(side="right", padx=20, pady=9)
        self.b_data = tk.Label(sb, bg=C["surface"], fg=C["accent"], font=(FONT, 9, "underline"), cursor="hand2")
        self.b_data.pack(side="right", padx=(0, 4))
        self.b_data.bind("<Button-1>", lambda e: self.open_data_dir())
        tk.Label(sb, textvariable=self.status_msg, bg=C["surface"], fg=C["muted"], font=(FONT, 9),
                 anchor="w").pack(side="left", padx=20, pady=6, fill="x", expand=True)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=20, pady=(14, 14))

        # folder row
        self.l_folder = ttk.Label(body, style="Cap.TLabel")
        self.l_folder.pack(anchor="w")
        row = ttk.Frame(body)
        row.pack(fill="x", pady=(4, 8))
        self.e_root = ttk.Entry(row, textvariable=self.root_dir, font=(FONT, 10))
        self.e_root.pack(side="left", fill="x", expand=True)
        self.e_root.bind("<Return>", lambda e: self.start_scan())
        self.b_browse = ttk.Button(row, style="Ghost.TButton", command=self.browse)
        self.b_browse.pack(side="left", padx=(8, 0))
        self.b_scan = ttk.Button(row, style="Accent.TButton", command=self.start_scan)
        self.b_scan.pack(side="left", padx=(8, 0))
        self.b_cancel = ttk.Button(row, style="Ghost.TButton", command=self.cancel)
        self.b_cancel.state(["disabled"])
        self.b_cancel.pack(side="left", padx=(8, 0))

        # warning banner (EDA tool running)
        self.banner = tk.Label(body, bg=C["warn_bg"], fg=C["warn_fg"], font=(FONT, 9, "bold"), anchor="w", padx=12, pady=7)

        # tab bar
        tabs = ttk.Frame(body)
        tabs.pack(fill="x", pady=(4, 0))
        self.tab_btns, self.tab_lines = {}, {}
        for k in ("junk", "dupes", "overview"):
            f = ttk.Frame(tabs)
            f.pack(side="left")
            b = ttk.Button(f, command=lambda k=k: self.show_tab(k), takefocus=False)
            b.pack()
            line = tk.Frame(f, height=2, bg=C["bg"])
            line.pack(fill="x")
            self.tab_btns[k], self.tab_lines[k] = b, line
        tk.Frame(body, height=1, bg=C["border"]).pack(fill="x", pady=(0, 12))
        self.tab_holder = ttk.Frame(body)
        self.tab_holder.pack(fill="both", expand=True)
        self.frames = {"junk": self._build_junk(self.tab_holder), "dupes": self._build_dupes(self.tab_holder),
                       "overview": self._build_overview(self.tab_holder)}
        self.show_tab(self.tab.get())

    def _tree(self, parent, cols):
        C = self.C
        box = tk.Frame(parent, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        box.pack(fill="both", expand=True)
        tree = ttk.Treeview(box, columns=[c[0] for c in cols[1:]], selectmode="extended")
        for c, w, a, st in cols:
            tree.column(c, width=w, anchor=a, stretch=st)
        for k in STATUSES + ("mixed",):
            tree.tag_configure(k, foreground=C[k] if k != "mixed" else C["text"])
        tree.tag_configure("dir", font=(FONT, 10, "bold"))
        ys = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=ys.set)
        tree.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        return tree

    def _tiles(self, parent, keys, colors):
        C = self.C
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(0, 12))
        out = {}
        for i, k in enumerate(keys):
            card = tk.Frame(frame, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            frame.columnconfigure(i, weight=1)
            tk.Frame(card, bg=colors[i], width=4).pack(side="left", fill="y")
            inner = tk.Frame(card, bg=C["surface"])
            inner.pack(side="left", fill="both", expand=True, padx=14, pady=10)
            name = tk.Label(inner, bg=C["surface"], fg=C["muted"], font=(FONT, 9, "bold"), anchor="w")
            name.pack(fill="x")
            size = tk.Label(inner, text="—", bg=C["surface"], fg=C["text"], font=(FONT, 18, "bold"), anchor="w")
            size.pack(fill="x")
            cnt = tk.Label(inner, text="", bg=C["surface"], fg=C["muted"], font=(FONT, 9), anchor="w")
            cnt.pack(fill="x")
            out[k] = (name, size, cnt)
        return out

    def _build_junk(self, parent):
        f = ttk.Frame(parent)
        opt = ttk.Frame(f)
        opt.pack(fill="x", pady=(0, 12))
        self.l_keep = ttk.Label(opt, style="Muted.TLabel")
        self.l_keep.pack(side="left")
        ttk.Spinbox(opt, from_=0, to=99, width=4, textvariable=self.keep_n).pack(side="left", padx=(6, 18))
        self.l_big = ttk.Label(opt, style="Muted.TLabel")
        self.l_big.pack(side="left")
        ttk.Spinbox(opt, from_=10, to=100000, increment=10, width=7, textvariable=self.big_mb).pack(side="left", padx=(6, 0))
        seg = ttk.Frame(opt)
        seg.pack(side="right")
        self.l_show = ttk.Label(opt, style="Cap.TLabel")
        self.l_show.pack(side="right", padx=(0, 8))
        self.seg_btns = {}
        for key in ("all",) + STATUSES:
            b = ttk.Button(seg, command=lambda k=key: self.set_view(k), takefocus=False)
            b.pack(side="left")
            self.seg_btns[key] = b
        self.tiles = self._tiles(f, STATUSES, [self.C[s] for s in STATUSES])
        self.tree = self._tree(f, (("#0", 420, "w", True), ("status", 150, "w", False), ("size", 90, "e", False),
                                   ("count", 60, "e", False), ("reason", 330, "w", True), ("mtime", 130, "w", False)))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_sel())
        self.tree.bind("<Double-1>", lambda e: self.open_location())
        self.tree.bind("<Button-3>", self.tree_menu)
        act = ttk.Frame(f)
        act.pack(fill="x", pady=(12, 0))
        self.b_selsafe = ttk.Button(act, style="Ghost.TButton", command=self.select_safe)
        self.b_clear = ttk.Button(act, style="Ghost.TButton", command=lambda: self.tree.selection_remove(self.tree.selection()))
        self.b_open = ttk.Button(act, style="Ghost.TButton", command=self.open_location)
        self.b_export = ttk.Button(act, style="Ghost.TButton", command=self.export_report)
        self.b_git = ttk.Button(act, style="Ghost.TButton", command=self.git_helper)
        self.b_restore = ttk.Button(act, style="Ghost.TButton", command=self.restore_last)
        for i, b in enumerate((self.b_selsafe, self.b_clear, self.b_open, self.b_export, self.b_git, self.b_restore)):
            b.pack(side="left", padx=(0 if i == 0 else 8, 0))
        self.b_delete = ttk.Button(act, style="Danger.TButton", command=self.clean_selected)
        self.b_delete.pack(side="right")
        self.l_sel = ttk.Label(act, style="Muted.TLabel")
        self.l_sel.pack(side="right", padx=16)
        return f

    def _build_dupes(self, parent):
        f = ttk.Frame(parent)
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 12))
        self.b_dscan = ttk.Button(top, style="Accent.TButton", command=self.start_dupes)
        self.b_dscan.pack(side="left")
        self.l_dsum = ttk.Label(top, font=(FONT, 11, "bold"))
        self.l_dsum.pack(side="left", padx=16)
        self.l_dhint = ttk.Label(top, style="Muted.TLabel")
        self.l_dhint.pack(side="right")
        self.dtree = self._tree(f, (("#0", 560, "w", True), ("copies", 80, "e", False), ("size", 100, "e", False),
                                    ("wasted", 100, "e", False), ("mtime", 140, "w", False)))
        self.dtree.bind("<<TreeviewSelect>>", lambda e: self.update_dsel())
        self.dtree.bind("<Double-1>", lambda e: self.open_dupe())
        act = ttk.Frame(f)
        act.pack(fill="x", pady=(12, 0))
        self.b_dsel = ttk.Button(act, style="Ghost.TButton", command=self.select_copies)
        self.b_dsel.pack(side="left")
        self.b_dopen = ttk.Button(act, style="Ghost.TButton", command=self.open_dupe)
        self.b_dopen.pack(side="left", padx=(8, 0))
        self.b_ddelete = ttk.Button(act, style="Danger.TButton", command=self.clean_dupes)
        self.b_ddelete.pack(side="right")
        self.l_dsel = ttk.Label(act, style="Muted.TLabel")
        self.l_dsel.pack(side="right", padx=16)
        return f

    def _build_overview(self, parent):
        C = self.C
        f = ttk.Frame(parent)
        self.otiles = self._tiles(f, ("reclaim", "total", "last30", "ops"), [C["safe"], C["accent"], C["mixed"], C["muted"]])
        split = ttk.Frame(f)
        split.pack(fill="both", expand=True)
        left = ttk.Frame(split)
        left.pack(side="left", fill="both", expand=True)
        self.l_tm = ttk.Label(left, style="Cap.TLabel")
        self.l_tm.pack(anchor="w", pady=(0, 4))
        box = tk.Frame(left, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        box.pack(fill="both", expand=True)
        self.treemap = Treemap(box, C, on_status=lambda s: self.status_msg.set(s or self.t(*self._status[:1], **self._status[1])))
        self.treemap.pack(fill="both", expand=True, padx=1, pady=1)
        right = ttk.Frame(split, width=300)
        right.pack(side="left", fill="y", padx=(12, 0))
        right.pack_propagate(False)
        self.l_month = ttk.Label(right, style="Cap.TLabel")
        self.l_month.pack(anchor="w", pady=(0, 4))
        self.mtree = self._tree(right, (("#0", 90, "w", False), ("size", 100, "e", True), ("count", 70, "e", False)))
        return f

    def show_tab(self, k):
        self.tab.set(k)
        for key, fr in self.frames.items():
            fr.pack_forget()
            self.tab_btns[key].configure(style="TabOn.TButton" if key == k else "Tab.TButton")
            self.tab_lines[key].configure(bg=self.C["accent"] if key == k else self.C["bg"])
        self.frames[k].pack(fill="both", expand=True)
        if k == "overview":
            self.refresh_overview()

    # ---------------------------------------------------------------- texts
    def apply_lang(self):
        t = self.t
        self.l_sub.config(text=t("app_sub"))
        for code, b in self.lang_btns.items():
            b.configure(style="HeadOn.TButton" if code == self.lang else "Head.TButton")
        self.b_settings.config(text=t("settings"))
        self.b_theme.config(text="☾" if self.settings["theme"] == "light" else "☀")
        self.l_folder.config(text=t("folder"))
        self.b_browse.config(text=t("browse"))
        self.b_scan.config(text=t("scan"))
        self.b_cancel.config(text=t("cancel"))
        for k, b in self.tab_btns.items():
            b.config(text=self.upper(t("tab_" + k)))
        self.l_keep.config(text=t("keep_hist"))
        self.l_big.config(text=t("big_arch"))
        self.l_show.config(text=t("show"))
        for k, b in self.seg_btns.items():
            b.config(text=t(k))
        self.set_view(self.view.get(), repopulate=False)
        for st, (name, _, _) in self.tiles.items():
            name.config(text=self.upper(t(st)))
        for c, key in (("#0", "col_name"), ("status", "col_status"), ("size", "col_size"), ("count", "col_count"),
                       ("reason", "col_reason"), ("mtime", "col_mtime")):
            self.tree.heading(c, text=t(key), anchor="e" if c in ("size", "count") else "w")
        for b, key in ((self.b_selsafe, "select_safe"), (self.b_clear, "clear"), (self.b_open, "open"),
                       (self.b_export, "export"), (self.b_git, "git"), (self.b_restore, "restore"),
                       (self.b_delete, "delete"), (self.b_dscan, "d_scan"), (self.b_dsel, "d_select"),
                       (self.b_dopen, "open"), (self.b_ddelete, "delete")):
            b.config(text=t(key))
        self.l_dhint.config(text=t("d_hint"))
        for c, key in (("#0", "col_name"), ("copies", "d_col_copies"), ("size", "col_size"),
                       ("wasted", "d_col_wasted"), ("mtime", "col_mtime")):
            self.dtree.heading(c, text=t(key), anchor="w" if c in ("#0", "mtime") else "e")
        for k, key in (("reclaim", "o_reclaim"), ("total", "o_total"), ("last30", "o_30"), ("ops", "o_ops")):
            self.otiles[k][0].config(text=t(key))
        self.l_tm.config(text=self.upper(t("o_treemap")))
        self.l_month.config(text=self.upper(t("o_month")))
        for c, key in (("#0", "o_col_month"), ("size", "col_size"), ("count", "col_count")):
            self.mtree.heading(c, text=t(key), anchor="w" if c == "#0" else "e")
        self.treemap.empty_text = t("o_empty")
        self.b_data.config(text=t("open_data"))
        self.update_banner()
        key, kw = self._status
        self.status_msg.set(t(key, **kw))
        self.populate()
        self.populate_dupes()
        if self.tab.get() == "overview":
            self.refresh_overview()

    def set_lang(self, lang):
        self.lang = self.settings["lang"] = lang
        storage.save_settings(self.settings)
        self.apply_lang()

    def toggle_theme(self):
        self.settings["theme"] = "dark" if self.settings["theme"] == "light" else "light"
        storage.save_settings(self.settings)
        self.rebuild()
        self.set_busy(self.is_busy)

    def set_view(self, key, repopulate=True):
        self.view.set(key)
        for k, b in self.seg_btns.items():
            b.configure(style="SegOn.TButton" if k == key else "Seg.TButton")
        if repopulate:
            self.populate()

    # ---------------------------------------------------------------- EDA tool warning
    def check_eda(self):
        def work():
            tools = pw.running_eda_tools()
            self.post(self._eda_result, tools)
        threading.Thread(target=work, daemon=True).start()

    def _eda_result(self, tools):
        self.eda_tools = tools
        self.update_banner()

    def update_banner(self):
        if self.eda_tools:
            self.banner.config(text=self.t("eda_running", tools=", ".join(sorted(self.eda_tools))))
            self.banner.pack(fill="x", pady=(0, 8), after=self.e_root.master)
        else:
            self.banner.pack_forget()

    # ---------------------------------------------------------------- folder / cache
    def open_data_dir(self):
        os.makedirs(storage.LOG_DIR, exist_ok=True)
        subprocess.Popen(["explorer", os.path.normpath(storage.DATA_DIR)])

    def remember(self, root):
        try:
            keep, big = self.keep_n.get(), self.big_mb.get()
        except tk.TclError:
            keep, big = self.settings["keep_n"], self.settings["big_mb"]
        self.settings.update(last_root=root, keep_n=keep, big_mb=big)
        storage.save_settings(self.settings)

    def browse(self):
        start = self.root_dir.get() if os.path.isdir(self.root_dir.get()) else DEFAULT_ROOT
        d = filedialog.askdirectory(initialdir=start, title=self.t("choose_title"))
        if d:
            self.root_dir.set(os.path.normpath(d))
            self.remember(os.path.normpath(d))
            data = storage.load_cache(self.root_dir.get())
            if data:
                self.show_cache(data)

    def show_cache(self, data):
        self.scanned_root, self.hits, self.keep_used = data["root"], data["hits"], data.get("keep", 3)
        for h in self.hits:
            h.setdefault("note", "")
        self.populate()
        self.set_status("cached", t=_ts(data["time"]))

    def restore_cache(self):
        root = self.root_dir.get()
        data = storage.load_cache(root) if os.path.isdir(root) else None
        if data and data.get("hits") is not None:
            self.show_cache(data)
        else:
            self.set_status("ready")

    def open_settings(self):
        def saved(theme_changed):
            self.rules = load_rules(storage.USER_RULES, self.settings["disabled_profiles"])
            if theme_changed:
                self.rebuild()
            else:
                self.populate()
        SettingsDialog(self, saved)

    # ---------------------------------------------------------------- background jobs
    def set_busy(self, on, msg=None):
        self.is_busy = on
        for b in (self.b_scan, self.b_delete, self.b_browse, self.b_dscan, self.b_ddelete, self.b_restore):
            b.state(["disabled"] if on else ["!disabled"])
        self.b_cancel.state(["!disabled"] if on and self.cancel_ev else ["disabled"])
        if on:
            self.pb.configure(mode="indeterminate")
            self.pb.start(12)
        else:
            self.pb.stop()
            self.pb.configure(mode="determinate", value=0)
        if msg:
            self.set_status(msg)

    def run_job(self, msg, work, done, cancellable=False):
        """work(cancel_event) runs in a thread; done(result, error) runs on the Tk thread."""
        self.cancel_ev = threading.Event() if cancellable else None
        self.set_busy(True, msg)
        ev = self.cancel_ev

        def runner():
            try:
                res = work(ev)
                self.post(self._job_end, done, res, None)
            except Exception as e:  # noqa
                self.post(self._job_end, done, None, e)
        threading.Thread(target=runner, daemon=True).start()

    def _job_end(self, done, res, err):
        self.cancel_ev = None
        self.set_busy(False)
        if isinstance(err, core.Cancelled):
            self.log.info("cancelled")
            self.set_status("cancelled")
            return
        done(res, err)

    def cancel(self):
        if self.cancel_ev:
            self.cancel_ev.set()

    # ---------------------------------------------------------------- junk scan
    def _settings_kw(self):
        st = self.settings
        return dict(excludes=st["excludes"], skip_network=st["skip_network"])

    def start_scan(self):
        if self.is_busy:
            return
        root = self.root_dir.get().strip()
        if not os.path.isdir(root):
            messagebox.showerror(self.t("no_folder_t"), self.t("no_folder_m", p=root))
            return
        root = os.path.abspath(root)
        try:
            keep, big = self.keep_n.get(), self.big_mb.get()
        except tk.TclError:
            keep, big = self.settings["keep_n"], self.settings["big_mb"]
        self.remember(root)
        self.rules = load_rules(storage.USER_RULES, self.settings["disabled_profiles"])
        self.check_eda()
        self.log.info("SCAN start  root=%s keep=%d big_mb=%d excludes=%d profiles_off=%s", root, keep, big,
                      len(self.settings["excludes"]), self.settings["disabled_profiles"])
        t0 = time.time()

        def work(ev):
            return core.scan(root, self.rules, big_archive_mb=big, keep_history=keep,
                             protect_open=self.settings["protect_open"], cancel=ev,
                             progress=lambda n: self.post(lambda: self.set_status("scanning_n", n=n)),
                             **self._settings_kw())

        def done(hits, err):
            if err:
                self.log.error("SCAN failed root=%s: %s", root, err)
                messagebox.showerror(self.t("scan_err_t"), str(err))
                return
            self.scanned_root, self.hits, self.keep_used = root, hits, keep
            tot = core.totals(hits)
            self.log.info("SCAN done   root=%s in %.1fs  %s", root, time.time() - t0,
                          "  ".join(f"{s}={n} files/{core.human(b)}" for s, (n, b) in tot.items()))
            storage.save_cache(root, hits, keep)
            storage.append_history(dict(type="scan", root=root, hits=len(hits), safe_bytes=tot[SAFE][1]))
            self.populate()
            if self.tab.get() == "overview":
                self.refresh_overview()
            self.set_status("scan_done" if hits else "no_results", t=_ts(time.time(), "%H:%M:%S"))
        self.run_job("scanning", work, done, cancellable=True)

    def populate(self):
        tree = self.tree
        tree.delete(*tree.get_children())
        self.node_files.clear()
        tot = core.totals(self.hits)
        for st, (_, size, cnt) in self.tiles.items():
            n, b = tot[st]
            size.config(text=core.human(b) if self.hits else "—")
            cnt.config(text=f"{n} {self.t('files')}" if self.hits else "")
        if not self.hits:
            self.update_sel()
            return
        root, view = self.scanned_root, self.view.get()
        shown = [h for h in self.hits if view == "all" or h["status"] == view]
        nodes, dirs = {}, set()

        def node_for(rel):
            if rel in nodes:
                return nodes[rel]
            if rel == "":
                iid = tree.insert("", "end", text=root, open=True, tags=("dir",))
            else:
                iid = tree.insert(node_for(os.path.dirname(rel)), "end", text=os.path.basename(rel), tags=("dir",))
            nodes[rel] = iid
            dirs.add(iid)
            self.node_files[iid] = []
            return iid

        for h in sorted(shown, key=lambda h: h["path"].lower()):
            rel = os.path.relpath(os.path.dirname(h["path"]), root)
            parent = node_for("" if rel == "." else rel)
            iid = tree.insert(parent, "end", text=os.path.basename(h["path"]), tags=(h["status"],),
                              values=("■ " + self.t(h["status"]), core.human(h["size"]), 1, self.reason(h), _ts(h["mtime"])))
            self.node_files[iid] = [h]
            p = parent
            while p:
                self.node_files[p].append(h)
                p = tree.parent(p)
        for iid in dirs:
            files = self.node_files[iid]
            sts = {f["status"] for f in files}
            st = sts.pop() if len(sts) == 1 else "mixed"
            tree.item(iid, values=("■ " + self.t(st), core.human(sum(f["size"] for f in files)), len(files), "", ""),
                      tags=("dir", st))

        size_of = {iid: sum(f["size"] for f in fs) for iid, fs in self.node_files.items()}

        def sort_kids(item):
            kids = sorted(tree.get_children(item), key=lambda k: -size_of.get(k, 0))
            for i, k in enumerate(kids):
                tree.move(k, item, i)
                if k in dirs:
                    sort_kids(k)
        for top in tree.get_children(""):
            sort_kids(top)
        self.dirs = dirs
        self.update_sel()

    def selected_files(self):
        seen, out = set(), []
        for iid in self.tree.selection():
            for h in self.node_files.get(iid, []):
                if h["path"] not in seen:
                    seen.add(h["path"])
                    out.append(h)
        return out

    def update_sel(self):
        files = [f for f in self.selected_files() if f["status"] != KEEP]
        self.l_sel.config(text=self.t("selected", n=len(files), size=core.human(sum(f["size"] for f in files))) if files else "")

    def select_safe(self):
        items = [iid for iid, fs in self.node_files.items()
                 if iid not in getattr(self, "dirs", ()) and fs and fs[0]["status"] == SAFE]
        self.tree.selection_set(items)
        self.update_sel()

    def _explore(self, files, is_file):
        if not files:
            return
        if is_file:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(files[0])])
        else:
            subprocess.Popen(["explorer", os.path.normpath(os.path.commonpath([os.path.dirname(f) for f in files]))])

    def open_location(self):
        sel = self.tree.selection()
        if sel:
            fs = [h["path"] for h in self.node_files.get(sel[0], [])]
            self._explore(fs, sel[0] not in self.dirs)

    def tree_menu(self, e):
        iid = self.tree.identify_row(e.y)
        if not iid:
            return
        if iid not in self.tree.selection():
            self.tree.selection_set(iid)
        fs = self.node_files.get(iid, [])
        if not fs:
            return
        folder = os.path.commonpath([os.path.dirname(h["path"]) for h in fs]) if iid in self.dirs else os.path.dirname(fs[0]["path"])
        m = tk.Menu(self, tearoff=0)
        m.add_command(label=self.t("open"), command=self.open_location)
        m.add_command(label=f"{self.t('exclude_this')}: {folder}", command=lambda: self.exclude_folder(folder))
        m.tk_popup(e.x_root, e.y_root)

    def exclude_folder(self, folder):
        if folder not in self.settings["excludes"]:
            self.settings["excludes"].append(folder)
            storage.save_settings(self.settings)
        self.log.info("EXCLUDE %s", folder)
        self.hits = [h for h in self.hits if not core.excluded(h["path"], [folder])]
        if self.scanned_root:
            storage.save_cache(self.scanned_root, self.hits, self.keep_used)
        self.populate()
        self.set_status("excluded_m", p=folder)

    # ---------------------------------------------------------------- clean / restore
    def _confirm_clean(self, files):
        mode, dest = self.settings["action"], self.settings["archive_dest"]
        if mode != "recycle" and not os.path.isdir(dest):
            messagebox.showwarning(self.t("settings"), self.t("s_dest_req"))
            self.open_settings()
            return None
        size = core.human(sum(f["size"] for f in files))
        msg = self.t("confirm_" + mode, n=len(files), size=size, dest=dest)
        unknown = [f for f in files if f["status"] == UNKNOWN]
        if unknown:
            base = self.scanned_root or ""
            names = "\n".join("  • " + (os.path.relpath(f["path"], base) if base else f["path"]) for f in unknown[:8])
            more = self.t("and_more", n=len(unknown) - 8) if len(unknown) > 8 else ""
            msg += self.t("unknown_w", n=len(unknown), names=names, more=more)
        tools = pw.running_eda_tools()
        if tools:
            self._eda_result(tools)
            msg = self.t("eda_running", tools=", ".join(sorted(tools))) + "\n\n" + msg
        if not messagebox.askyesno(self.t("confirm_t"), msg, icon="warning" if unknown or tools else "question"):
            return None
        return mode, dest

    def _do_clean(self, files, after):
        ok = self._confirm_clean(files)
        if not ok:
            return
        mode, dest = ok
        self.log.info("CLEAN start mode=%s root=%s  %d files", mode, self.scanned_root, len(files))

        def work(ev):
            return actions.clean(files, mode, dest, root=self.scanned_root)

        def done(res, err):
            if err:
                self.log.error("CLEAN error: %s", err)
                messagebox.showerror(self.t("del_err_t"), str(err))
            gone = {f["path"] for f in files if not os.path.exists(f["path"])}
            after(gone)
            self.set_status("deleted", n=len(gone), size=core.human(sum(f["size"] for f in files if f["path"] in gone)),
                            mode=self.t("mode_" + mode))
        self.run_job("deleting", work, done)

    def clean_selected(self):
        files = [f for f in self.selected_files() if f["status"] != KEEP]
        if not files:
            messagebox.showinfo(self.t("nothing_t"), self.t("nothing_m"))
            return

        def after(gone):
            self.hits = [h for h in self.hits if h["path"] not in gone]
            if self.scanned_root:
                storage.save_cache(self.scanned_root, self.hits, self.keep_used)
            self.populate()
        self._do_clean(files, after)

    def restore_last(self):
        ev = actions.last_clean()
        if not ev:
            messagebox.showinfo(self.t("restore"), self.t("restore_none"))
            return
        if not messagebox.askyesno(self.t("restore"), self.t("restore_q", n=ev["files"], t=_ts(ev["time"]),
                                                             mode=self.t("mode_" + ev["mode"]))):
            return

        def done(res, err):
            if err:
                messagebox.showerror(self.t("del_err_t"), str(err))
                return
            ok, failed = res
            messagebox.showinfo(self.t("restore"), self.t("restore_done", ok=len(ok), fail=len(failed)))
            if self.scanned_root and os.path.isdir(self.scanned_root):
                self.start_scan()
        self.run_job("deleting", lambda e: actions.restore(ev), done)

    # ---------------------------------------------------------------- export / git
    def export_report(self):
        if not self.hits:
            messagebox.showinfo(self.t("nothing_t"), self.t("no_results"))
            return
        name = f"junkchecker-{os.path.basename(self.scanned_root.rstrip(chr(92))) or 'drive'}-{time.strftime('%Y%m%d-%H%M')}"
        p = filedialog.asksaveasfilename(title=self.t("export_title"), initialfile=name, defaultextension=".html",
                                         filetypes=[("HTML", "*.html"), ("CSV", "*.csv")])
        if not p:
            return
        report.export(p, self.hits, self.scanned_root, label=self.reason,
                      names={s: self.t(s) for s in STATUSES})
        self.log.info("EXPORT %s", p)
        self.set_status("exported", p=p)
        if p.lower().endswith((".html", ".htm")):
            os.startfile(p)

    def git_helper(self):
        if not self.hits:
            messagebox.showinfo(self.t("git_title"), self.t("git_none"))
            return

        def work(ev):
            _, repos = core.git_tracked(self.scanned_root)
            # also repos that contain the scanned folder
            d = self.scanned_root
            while True:
                if os.path.isdir(os.path.join(d, ".git")) and d not in repos:
                    repos.append(d)
                parent = os.path.dirname(d)
                if parent == d:
                    break
                d = parent
            return gitutil.plan(self.hits, repos, self.rules)

        def done(plan, err):
            if err or not plan:
                messagebox.showinfo(self.t("git_title"), str(err) if err else self.t("git_none"))
                return
            GitDialog(self, plan)
        self.run_job("scanning", work, done)

    # ---------------------------------------------------------------- duplicates
    def start_dupes(self):
        if self.is_busy:
            return
        root = self.root_dir.get().strip()
        if not os.path.isdir(root):
            messagebox.showerror(self.t("no_folder_t"), self.t("no_folder_m", p=root))
            return
        root = os.path.abspath(root)
        self.remember(root)
        min_size = int(float(self.settings["dupe_min_mb"]) * 1e6)
        self.log.info("DUPES start root=%s min=%d", root, min_size)

        def work(ev):
            return dupes.find_duplicates(root, min_size, cancel=ev,
                                         progress=lambda n: self.post(lambda n=n: self.set_status("scanning_n", n=n)),
                                         **self._settings_kw())

        def done(groups, err):
            if err:
                messagebox.showerror(self.t("scan_err_t"), str(err))
                return
            self.dupe_groups, self.dupe_root = groups, root
            self.log.info("DUPES done  %d groups, %s wasted", len(groups), core.human(dupes.wasted(groups)))
            self.populate_dupes()
            self.set_status("scan_done" if groups else "no_results", t=_ts(time.time(), "%H:%M:%S"))
        self.run_job("scanning", work, done, cancellable=True)

    def populate_dupes(self):
        t = self.dtree
        t.delete(*t.get_children())
        self.dupe_nodes.clear()
        g = self.dupe_groups
        self.l_dsum.config(text=self.t("d_groups", g=len(g), size=core.human(dupes.wasted(g))) if self.dupe_root else "")
        for gi, grp in enumerate(g):
            parent = t.insert("", "end", text=os.path.basename(grp["paths"][0]), open=False, tags=("dir", UNKNOWN),
                              values=(len(grp["paths"]), core.human(grp["size"]),
                                      core.human(grp["size"] * (len(grp["paths"]) - 1)), ""))
            self.dupe_nodes[parent] = ("group", gi)
            for pi, (p, m) in enumerate(zip(grp["paths"], grp["mtimes"])):
                iid = t.insert(parent, "end", text=p, values=("", core.human(grp["size"]), "", _ts(m)),
                               tags=(KEEP if pi == 0 else UNKNOWN,))
                self.dupe_nodes[iid] = ("file", gi, pi)
        self.update_dsel()

    def selected_dupes(self):
        out, seen = [], set()
        for iid in self.dtree.selection():
            n = self.dupe_nodes.get(iid)
            if not n or n[0] != "file":
                continue
            grp = self.dupe_groups[n[1]]
            p = grp["paths"][n[2]]
            if p not in seen:
                seen.add(p)
                out.append(dict(path=p, size=grp["size"], status=UNKNOWN, group=n[1]))
        return out

    def update_dsel(self):
        f = self.selected_dupes()
        self.l_dsel.config(text=self.t("selected", n=len(f), size=core.human(sum(x["size"] for x in f))) if f else "")

    def select_copies(self):
        items = [iid for iid, n in self.dupe_nodes.items() if n[0] == "file" and n[2] > 0]
        for iid, n in self.dupe_nodes.items():
            if n[0] == "group":
                self.dtree.item(iid, open=True)
        self.dtree.selection_set(items)
        self.update_dsel()

    def open_dupe(self):
        sel = self.dtree.selection()
        n = self.dupe_nodes.get(sel[0]) if sel else None
        if n:
            grp = self.dupe_groups[n[1]]
            self._explore([grp["paths"][n[2] if n[0] == "file" else 0]], True)

    def clean_dupes(self):
        files = self.selected_dupes()
        if not files:
            messagebox.showinfo(self.t("nothing_t"), self.t("nothing_m"))
            return
        # never remove every copy of a group
        by_group = {}
        for f in files:
            by_group.setdefault(f["group"], []).append(f)
        for gi, fs in by_group.items():
            if len(fs) >= len(self.dupe_groups[gi]["paths"]):
                fs.sort(key=lambda f: self.dupe_groups[gi]["paths"].index(f["path"]))
                files.remove(fs[0])

        def after(gone):
            for grp in self.dupe_groups:
                keep = [(p, m) for p, m in zip(grp["paths"], grp["mtimes"]) if p not in gone]
                grp["paths"], grp["mtimes"] = [p for p, _ in keep], [m for _, m in keep]
            self.dupe_groups = [g for g in self.dupe_groups if len(g["paths"]) > 1]
            self.populate_dupes()
        self._do_clean(files, after)

    # ---------------------------------------------------------------- overview
    def refresh_overview(self):
        s = storage.stats()
        tot = core.totals(self.hits)
        vals = {"reclaim": (core.human(tot[SAFE][1]) if self.hits else "—", f"{tot[SAFE][0]} {self.t('files')}" if self.hits else ""),
                "total": (core.human(s["total_bytes"]), f"{s['total_files']} {self.t('files')}"),
                "last30": (core.human(s["last30_bytes"]), ""),
                "ops": (str(s["operations"]), f"{s['scans']} scans")}
        for k, (a, b) in vals.items():
            self.otiles[k][1].config(text=a)
            self.otiles[k][2].config(text=b)
        self.treemap.set_data([h for h in self.hits if h["status"] != KEEP], self.scanned_root) if self.hits else self.treemap.set_data([], None)
        self.mtree.delete(*self.mtree.get_children())
        for m, (b, n, ops) in s["by_month"].items():
            self.mtree.insert("", "end", text=m, values=(core.human(b), n))


def run(folder=None):
    app = App(folder)
    app.mainloop()
    return 0


def _grab(x, y, w, h, path):
    """Screenshot a screen region (Pillow if available, otherwise PowerShell + System.Drawing)."""
    try:
        from PIL import ImageGrab
        ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(path)
    except ImportError:
        ps = ("Add-Type -AssemblyName System.Drawing; $b = New-Object System.Drawing.Bitmap %d, %d; "
              "$g = [System.Drawing.Graphics]::FromImage($b); $g.CopyFromScreen(%d, %d, 0, 0, $b.Size); "
              "$b.Save('%s')" % (w, h, x, y, path.replace("'", "''")))
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=pw.NO_WINDOW, check=True)


def selftest(root, shot_dir=None):
    """Non-destructive smoke test: scan, render every tab in both languages and themes, optional screenshots."""
    app = App()
    app.withdraw()
    root = os.path.abspath(root)
    app.scanned_root, app.keep_used = root, 3
    app.root_dir.set(root)
    app.hits = core.scan(root, app.rules, keep_history=3)
    app.dupe_root = root
    app.dupe_groups = dupes.find_duplicates(root, 1 << 20)
    out = []
    for th in ("light", "dark"):
        app.settings["theme"] = th
        app.rebuild()
        for lang in ("en", "tr"):
            app.lang = lang
            app.apply_lang()
            app.select_safe()
            app.select_copies()
            for tab in ("junk", "dupes", "overview"):
                app.show_tab(tab)
                app.update()
            out.append(f"{th}/{lang}: tiles={[app.tiles[s][1].cget('text') for s in STATUSES]} "
                       f"sel='{app.l_sel.cget('text')}' dupes='{app.l_dsum.cget('text')}'")
        if shot_dir:
            app.lang = "en"
            app.apply_lang()
            app.deiconify(); app.lift(); app.attributes("-topmost", True)
            for tab in ("junk", "dupes", "overview"):
                app.show_tab(tab)
                for _ in range(5):
                    app.update(); time.sleep(0.15)
                x, y = app.winfo_rootx(), app.winfo_rooty()
                p = os.path.join(shot_dir, f"{tab}-{th}.png")
                _grab(x, y, app.winfo_width(), app.winfo_height(), p)
                out.append("screenshot " + p)
            app.withdraw()
    app.destroy()
    return out
