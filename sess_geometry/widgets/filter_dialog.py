# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

class FilterDialog(tk.Toplevel):
    def __init__(self, master, title, values, active_values, on_apply):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.on_apply = on_apply
        self._items = []
        self.geometry("320x420")
        self.resizable(True, True)

        top = tk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="Фильтр по значению", anchor="w").pack(fill="x", side="left", expand=True)

        btns = tk.Frame(self)
        btns.pack(fill="x", padx=8)
        tk.Button(btns, text="Выбрать все", command=self._select_all).pack(side="left")
        tk.Button(btns, text="Снять все", command=self._select_none).pack(side="left", padx=4)
        tk.Button(btns, text="Сбросить", command=self._clear_filter).pack(side="right")

        search_fr = tk.Frame(self)
        search_fr.pack(fill="x", padx=8, pady=(4,4))
        tk.Label(search_fr, text="Поиск:").pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(search_fr, textvariable=self.search_var)
        entry.pack(fill="x", expand=True, side="left", padx=(4,0))
        entry.bind("<KeyRelease>", lambda _e: self._filter_values())

        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.canvas = tk.Canvas(body, highlightthickness=0)
        vsb = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._on_wheel_linux(+1))
        self.canvas.bind("<Button-5>", lambda e: self._on_wheel_linux(-1))

        self.inner = tk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0,0), window=self.inner, anchor="nw")

        active = None if active_values is None else set(active_values)
        for value in values:
            display = value if value not in (None, "") else "<пусто>"
            var = tk.BooleanVar(value=(True if active is None else (value in active)))
            chk = tk.Checkbutton(self.inner, text=str(display), anchor="w", variable=var)
            chk.pack(fill="x", anchor="w")
            self._items.append((value, str(display), var, chk))

        bottom = tk.Frame(self)
        bottom.pack(fill="x", padx=8, pady=(0,8))
        tk.Button(bottom, text="Отмена", command=self._on_cancel).pack(side="right")
        tk.Button(bottom, text="Применить", command=self._apply).pack(side="right", padx=(0,6))

        self.bind("<Return>", lambda _e: self._apply())
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _select_all(self):
        for _, _, var, _ in self._items:
            var.set(True)

    def _select_none(self):
        for _, _, var, _ in self._items:
            var.set(False)

    def _clear_filter(self):
        if callable(self.on_apply):
            self.on_apply(None)
        self.destroy()

    def _apply(self):
        if callable(self.on_apply):
            selected = [value for value, _, var, _ in self._items if var.get()]
            if len(selected) == len(self._items):
                self.on_apply(None)
            else:
                self.on_apply(selected)
        self.destroy()

    def _on_cancel(self):
        self.destroy()

    def _filter_values(self):
        needle = self.search_var.get().strip().lower()
        for value, display, _var, widget in self._items:
            show = True
            if needle:
                show = needle in display.lower()
            widget.pack_forget()
            if show:
                widget.pack(fill="x", anchor="w")

    def _on_wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _on_wheel_linux(self, direction):
        self.canvas.yview_scroll(-1 if direction > 0 else 1, "units")
