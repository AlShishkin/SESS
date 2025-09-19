# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

class ColumnsPicker(tk.Toplevel):
    """Диалог выбора колонок для отображения"""
    
    def __init__(self, master, title, vars_dict, on_apply):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.vars_dict = vars_dict
        self.on_apply = on_apply
        self.geometry("400x500")
        self.resizable(True, True)
        
        self._build_ui()
        self._center_window()
        
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._apply)
        
    def _build_ui(self):
        """Создание интерфейса"""
        # Верхняя панель с кнопками
        top = tk.Frame(self, bg="#f0f0f0")
        top.pack(fill="x", padx=8, pady=6)
        
        tk.Button(top, text="✓ Выбрать все", command=self._all_on, 
                 bg="#4CAF50", fg="white").pack(side="left", padx=2)
        tk.Button(top, text="✗ Снять все", command=self._all_off,
                 bg="#f44336", fg="white").pack(side="left", padx=2)
        tk.Button(top, text="↺ Сброс", command=self._reset,
                 bg="#2196F3", fg="white").pack(side="left", padx=2)
        
        # Поиск
        search_frame = tk.Frame(self)
        search_frame.pack(fill="x", padx=8, pady=4)
        tk.Label(search_frame, text="Поиск:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self._filter_items())
        ttk.Entry(search_frame, textvariable=self.search_var).pack(side="left", fill="x", expand=True, padx=4)
        
        # Область с чекбоксами
        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=8, pady=(0,6))
        
        self.canvas = tk.Canvas(body, highlightthickness=0)
        self.vsb = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        
        self.inner = tk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0,0), window=self.inner, anchor="nw")
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        
        # Привязки для прокрутки
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._on_wheel_linux(+1))
        self.canvas.bind("<Button-5>", lambda e: self._on_wheel_linux(-1))
        
        # Создание чекбоксов
        self.checkboxes = []
        for k in sorted(self.vars_dict.keys(), key=lambda s: s.lower()):
            cb = tk.Checkbutton(self.inner, text=k, anchor="w", variable=self.vars_dict[k])
            cb.pack(fill="x", anchor="w", pady=1)
            self.checkboxes.append((k, cb))
        
        # Нижняя панель - ИСПРАВЛЕНО: правильный отступ
        bottom = tk.Frame(self)
        bottom.pack(fill="x", padx=8, pady=8)
        tk.Button(bottom, text="Отмена", command=self._cancel,
                 bg="#9E9E9E", fg="white").pack(side="right", padx=2)
        tk.Button(bottom, text="Применить", command=self._apply,
                 bg="#4CAF50", fg="white").pack(side="right", padx=2)
    
    def _center_window(self):
        """Центрирование окна"""
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
    
    def _all_on(self):
        """Выбрать все"""
        for v in self.vars_dict.values():
            v.set(True)
    
    def _all_off(self):
        """Снять все"""
        for v in self.vars_dict.values():
            v.set(False)
    
    def _reset(self):
        """Сброс к значениям по умолчанию"""
        # Установка базовых колонок
        default_cols = ["id", "name", "BESS_level"]
        for k, v in self.vars_dict.items():
            v.set(k in default_cols)
    
    def _filter_items(self):
        """Фильтрация чекбоксов по поиску"""
        search = self.search_var.get().lower()
        for k, cb in self.checkboxes:
            if search in k.lower():
                cb.pack(fill="x", anchor="w", pady=1)
            else:
                cb.pack_forget()
    
    def _apply(self):
        """Применение изменений"""
        try:
            if callable(self.on_apply):
                self.on_apply()
        finally:
            self.destroy()
    
    def _cancel(self):
        """Отмена"""
        self.destroy()
    
    def _on_wheel(self, e):
        """Прокрутка колесиком мыши"""
        self.canvas.yview_scroll(-1 if e.delta > 0 else +1, "units")
    
    def _on_wheel_linux(self, direction):
        """Прокрутка для Linux"""
        self.canvas.yview_scroll(-1 if direction > 0 else +1, "units")