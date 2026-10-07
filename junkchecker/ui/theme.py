"""Flat, sharp-edged ttk styling with light and dark palettes."""
from tkinter import ttk

FONT = "Segoe UI"
MONO = "Consolas"

PALETTES = {
    "light": dict(bg="#F3F4F6", surface="#FFFFFF", border="#D1D5DB", text="#111827", muted="#6B7280",
                  head="#0F1115", head_text="#F9FAFB", head_muted="#9CA3AF", head_line="#2A2E36", head_hover="#1C1F26",
                  accent="#2563EB", accent_dk="#1D4ED8", danger="#DC2626", danger_dk="#B91C1C",
                  hover="#E5E7EB", sel="#DBEAFE", on_accent="#FFFFFF",
                  safe="#15803D", unknown="#B45309", keep="#6B7280", mixed="#2563EB",
                  warn_bg="#FEF3C7", warn_fg="#92400E"),
    "dark": dict(bg="#14161B", surface="#1C1F26", border="#2E333D", text="#E5E7EB", muted="#9CA3AF",
                 head="#0A0B0E", head_text="#F9FAFB", head_muted="#9CA3AF", head_line="#262A33", head_hover="#16181D",
                 accent="#3B82F6", accent_dk="#2563EB", danger="#EF4444", danger_dk="#DC2626",
                 hover="#262A33", sel="#1E3A5F", on_accent="#FFFFFF",
                 safe="#22C55E", unknown="#F59E0B", keep="#9CA3AF", mixed="#60A5FA",
                 warn_bg="#3A2A0A", warn_fg="#FCD34D"),
}


def blend(c1, c2, t):
    """Mix two #RRGGBB colours, t=0 -> c1, t=1 -> c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def apply(root, C):
    s = ttk.Style(root)
    s.theme_use("clam")
    base = (FONT, 10)
    s.configure(".", font=base, background=C["bg"], foreground=C["text"], borderwidth=0, focuscolor=C["accent"],
                troughcolor=C["bg"], selectbackground=C["sel"], selectforeground=C["text"],
                fieldbackground=C["surface"], insertcolor=C["text"])
    s.configure("TFrame", background=C["bg"])
    s.configure("Surface.TFrame", background=C["surface"])
    s.configure("TLabel", background=C["bg"], foreground=C["text"])
    s.configure("Surface.TLabel", background=C["surface"], foreground=C["text"])
    s.configure("Muted.TLabel", background=C["bg"], foreground=C["muted"], font=(FONT, 9))
    s.configure("Cap.TLabel", background=C["bg"], foreground=C["muted"], font=(FONT, 8, "bold"))
    s.configure("SurfCap.TLabel", background=C["surface"], foreground=C["muted"], font=(FONT, 8, "bold"))

    def btn(name, bg, fg, hov, bold=True, border=None):
        s.configure(name, background=bg, foreground=fg, padding=(14, 7), font=(FONT, 10, "bold" if bold else "normal"),
                    relief="solid" if border else "flat", borderwidth=1 if border else 0,
                    bordercolor=border or bg, lightcolor=border or bg, darkcolor=border or bg)
        s.map(name, background=[("disabled", C["hover"]), ("pressed", hov), ("active", hov)],
              foreground=[("disabled", C["muted"])])
    btn("Accent.TButton", C["accent"], C["on_accent"], C["accent_dk"])
    btn("Danger.TButton", C["danger"], C["on_accent"], C["danger_dk"])
    btn("Ghost.TButton", C["surface"], C["text"], C["hover"], bold=False, border=C["border"])

    def seg(name, bg, fg, border, hov, bold):
        s.configure(name, background=bg, foreground=fg, padding=(12, 5), relief="solid", borderwidth=1,
                    bordercolor=border, lightcolor=border, darkcolor=border, font=(FONT, 9, "bold" if bold else "normal"))
        s.map(name, background=[("active", hov)])
    seg("Seg.TButton", C["surface"], C["text"], C["border"], C["hover"], False)
    seg("SegOn.TButton", C["text"], C["bg"], C["text"], C["text"], True)

    # tabs: underline style built from two button styles
    s.configure("Tab.TButton", background=C["bg"], foreground=C["muted"], padding=(16, 9), relief="flat",
                borderwidth=0, font=(FONT, 10, "bold"))
    s.map("Tab.TButton", foreground=[("active", C["text"])], background=[("active", C["bg"])])
    s.configure("TabOn.TButton", background=C["bg"], foreground=C["text"], padding=(16, 9), relief="flat",
                borderwidth=0, font=(FONT, 10, "bold"))
    s.map("TabOn.TButton", background=[("active", C["bg"])])

    def head(name, bg, fg, border, hov_bg, hov_fg):
        s.configure(name, background=bg, foreground=fg, padding=(10, 4), relief="solid", borderwidth=1,
                    bordercolor=border, lightcolor=border, darkcolor=border, font=(FONT, 9, "bold"))
        s.map(name, background=[("active", hov_bg)], foreground=[("active", hov_fg)])
    head("Head.TButton", C["head"], C["head_muted"], C["head_line"], C["head_hover"], C["head_text"])
    head("HeadOn.TButton", C["head_text"], C["head"], C["head_text"], C["head_text"], C["head"])

    for w in ("TEntry", "TSpinbox", "TCombobox"):
        s.configure(w, fieldbackground=C["surface"], background=C["surface"], foreground=C["text"],
                    bordercolor=C["border"], lightcolor=C["border"], darkcolor=C["border"], borderwidth=1,
                    relief="flat", padding=6, arrowcolor=C["text"], insertcolor=C["text"])
        s.map(w, bordercolor=[("focus", C["accent"])], lightcolor=[("focus", C["accent"])],
              darkcolor=[("focus", C["accent"])], fieldbackground=[("readonly", C["surface"])])
    for w in ("TCheckbutton", "TRadiobutton"):
        s.configure(w, background=C["surface"], foreground=C["text"], indicatorbackground=C["surface"],
                    indicatorforeground=C["accent"], upperbordercolor=C["border"], lowerbordercolor=C["border"],
                    indicatorrelief="flat", padding=(2, 3))
        s.map(w, background=[("active", C["surface"])], indicatorbackground=[("selected", C["surface"]), ("pressed", C["hover"])])

    s.configure("Treeview", background=C["surface"], fieldbackground=C["surface"], foreground=C["text"],
                rowheight=26, borderwidth=0, relief="flat", font=base)
    s.map("Treeview", background=[("selected", C["sel"])], foreground=[("selected", C["text"])])
    s.configure("Treeview.Heading", background=C["bg"], foreground=C["muted"], relief="flat", borderwidth=0,
                font=(FONT, 9, "bold"), padding=(6, 6))
    s.map("Treeview.Heading", background=[("active", C["hover"])])
    s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    s.configure("Thin.Horizontal.TProgressbar", troughcolor=C["border"], background=C["accent"], borderwidth=0,
                thickness=4, lightcolor=C["accent"], darkcolor=C["accent"])
    for o in ("Vertical", "Horizontal"):
        s.configure(f"{o}.TScrollbar", background=C["bg"], troughcolor=C["surface"], bordercolor=C["surface"],
                    lightcolor=C["bg"], darkcolor=C["bg"], arrowcolor=C["muted"], relief="flat", gripcount=0)
        s.map(f"{o}.TScrollbar", background=[("active", C["hover"])])
    root.option_add("*TCombobox*Listbox.background", C["surface"])
    root.option_add("*TCombobox*Listbox.foreground", C["text"])
    root.option_add("*Menu.background", C["surface"])
    root.option_add("*Menu.foreground", C["text"])
    root.option_add("*Menu.activeBackground", C["sel"])
    root.option_add("*Menu.activeForeground", C["text"])
    root.option_add("*Menu.relief", "flat")
    return s
