"""Squarified treemap on a tk.Canvas with drill-down."""
import os, tkinter as tk

from ..core import human
from .theme import FONT, blend


def squarify(items, x, y, w, h):
    """items: [(value, obj)] sorted descending, values > 0. Returns [(x, y, w, h, obj)]."""
    total = sum(v for v, _ in items)
    if total <= 0 or w <= 0 or h <= 0:
        return []
    scale = w * h / total
    items = [(v * scale, o) for v, o in items if v > 0]
    rects = []

    def worst(row, short):
        s = sum(a for a, _ in row)
        mx, mn = max(a for a, _ in row), min(a for a, _ in row)
        return max(short * short * mx / (s * s), s * s / (short * short * mn))

    while items:
        short = min(w, h)
        if short <= 0:
            break
        row, i = [items[0]], 1
        while i < len(items) and worst(row + [items[i]], short) <= worst(row, short):
            row.append(items[i])
            i += 1
        items = items[i:]
        s = sum(a for a, _ in row)
        if w >= h:
            cw = s / h
            yy = y
            for a, o in row:
                rh = a / cw
                rects.append((x, yy, cw, rh, o))
                yy += rh
            x, w = x + cw, w - cw
        else:
            rh = s / w
            xx = x
            for a, o in row:
                cw = a / rh
                rects.append((xx, y, cw, rh, o))
                xx += cw
            y, h = y + rh, h - rh
    return rects


class Node:
    __slots__ = ("name", "path", "size", "children", "statuses", "parent")

    def __init__(self, name, path, parent=None):
        self.name, self.path, self.parent = name, path, parent
        self.size, self.children, self.statuses = 0, {}, {}

    @property
    def status(self):
        live = [s for s, b in self.statuses.items() if b > 0]
        return live[0] if len(live) == 1 else "mixed"


def build_tree(hits, root):
    top = Node(root, root)
    for h in hits:
        rel = os.path.relpath(h["path"], root)
        parts = rel.split(os.sep)
        node = top
        chain = [top]
        for i, p in enumerate(parts):
            if p not in node.children:
                node.children[p] = Node(p, os.path.join(node.path, p), node)
            node = node.children[p]
            chain.append(node)
        for n in chain:
            n.size += h["size"]
            n.statuses[h["status"]] = n.statuses.get(h["status"], 0) + h["size"]
    return top


class Treemap(tk.Canvas):
    def __init__(self, master, C, on_status=None, **kw):
        super().__init__(master, bg=C["surface"], highlightthickness=0, **kw)
        self.C, self.on_status = C, on_status
        self.top = self.cur = None
        self.empty_text = ""
        self._rects = []
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Button-1>", self._click)
        self.bind("<Button-3>", lambda e: self.zoom_out())
        self.bind("<Motion>", self._hover)

    def set_data(self, hits, root):
        self.top = build_tree(hits, root) if hits else None
        self.cur = self.top
        while self.cur is not None and len(self.cur.children) == 1:
            child = next(iter(self.cur.children.values()))
            if not child.children:
                break
            self.cur = child
        self.redraw()

    def zoom_out(self):
        if self.cur is not None and self.cur.parent is not None:
            self.cur = self.cur.parent
            self.redraw()

    def _click(self, e):
        n = self._at(e.x, e.y)
        if n is not None and n.children:
            self.cur = n
            self.redraw()

    def _at(self, x, y):
        for (x0, y0, x1, y1, n) in self._rects:
            if x0 <= x < x1 and y0 <= y < y1:
                return n
        return None

    def _hover(self, e):
        n = self._at(e.x, e.y)
        if self.on_status:
            self.on_status(f"{n.path}  ·  {human(n.size)}" if n is not None else "")
        self.configure(cursor="hand2" if n is not None and n.children else "")

    def redraw(self):
        self.delete("all")
        self._rects = []
        C, W, H = self.C, self.winfo_width(), self.winfo_height()
        if self.cur is None or self.cur.size <= 0:
            self.create_text(W / 2, H / 2, text=self.empty_text, fill=C["muted"], font=(FONT, 10))
            return
        # breadcrumb
        crumbs, n = [], self.cur
        while n is not None:
            crumbs.append(n.name if n.parent is not None else n.path)
            n = n.parent
        self.create_text(8, 11, anchor="w", text="  ›  ".join(reversed(crumbs)) + f"   ({human(self.cur.size)})",
                         fill=C["muted"], font=(FONT, 9, "bold"))
        items = sorted(((c.size, c) for c in self.cur.children.values() if c.size > 0), key=lambda t: -t[0])
        for i, (x, y, w, h, node) in enumerate(squarify(items, 0, 22, W, H - 22)):
            x0, y0, x1, y1 = int(x), int(y), int(x + w), int(y + h)
            if x1 - x0 < 1 or y1 - y0 < 1:
                continue
            base = C.get(node.status, C["mixed"])
            fill = blend(base, C["surface"], 0.25 + 0.35 * ((i % 4) / 3))
            self.create_rectangle(x0, y0, x1, y1, fill=fill, outline=C["surface"], width=2)
            self._rects.append((x0, y0, x1, y1, node))
            if x1 - x0 > 60 and y1 - y0 > 34:
                label = node.name + ("\\" if node.children else "")
                self.create_text(x0 + 6, y0 + 5, anchor="nw", text=label, fill=C["text"], font=(FONT, 9, "bold"),
                                 width=x1 - x0 - 10)
                self.create_text(x0 + 6, y1 - 5, anchor="sw", text=human(node.size), fill=C["text"], font=(FONT, 9))
