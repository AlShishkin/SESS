# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

class ColumnsPicker(tk.Toplevel):
    def __init__(self, master, title, vars_dict, on_apply):
        super().__init__(master)
        self.title(title); self.transient(master)
        self.vars_dict = vars_dict; self.on_apply = on_apply
        self.geometry("360x420"); self.resizable(True, True)

        top = tk.Frame(self); top.pack(fill="x", padx=8, pady=6)
        tk.Button(top, text="Выбрать все", command=self._all_on).pack(side="left")
        tk.Button(top, text="Снять все", command=self._all_off).pack(side="left", padx=6)

        body = tk.Frame(self); body.pack(fill="both", expand=True, padx=8, pady=(0,6))
        self.canvas = tk.Canvas(body, highlightthickness=0)
        self.vsb = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.inner = tk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0,0), window=self.inner, anchor="nw")
        self.canvas.pack(side="left", fill="both", expand=True); self.vsb.pack(side="right", fill="y")

        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._on_wheel_linux(+1))
        self.canvas.bind("<Button-5>", lambda e: self._on_wheel_linux(-1))

        for k in sorted(self.vars_dict.keys(), key=lambda s: s.lower()):
            tk.Checkbutton(self.inner, text=k, anchor="w", variable=self.vars_dict[k]).pack(fill="x", anchor="w")

        bot = tk.Frame(self); bot.pack(fill="x", padx=8, pady=8)
        tk.Button(bot, text="Применить", command=self._apply).pack(side="right")

        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._apply)

    def _all_on(self):
        for v in self.vars_dict.values():
            v.set(True)

    def _all_off(self):
        for v in self.vars_dict.values():
            v.set(False)

    def _apply(self):
        try:
            if callable(self.on_apply):
                self.on_apply()
        finally:
            self.destroy()

    def _on_wheel(self, e):
        self.canvas.yview_scroll(-1 if e.delta > 0 else +1, "units")

    def _on_wheel_linux(self, direction):
        self.canvas.yview_scroll(-1 if direction > 0 else +1, "units")
