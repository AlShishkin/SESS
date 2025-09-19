# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

class FilterDialog(tk.Toplevel):
    """Диалог фильтрации по значениям"""
    
    def __init__(self, master, title, values, active_values, on_apply):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.on_apply = on_apply
        self._items = []
        self._original_active = active_values
        self.geometry("400x500")
        self.resizable(True, True)
        
        self._build_ui(values, active_values)
        self._center_window()
        
        self.bind("<Return>", lambda e: self._apply())
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
    
    def _build_ui(self, values, active_values):
        """Создание интерфейса"""
        # Заголовок
        header = tk.Frame(self, bg="#2196F3", height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Фильтр по значениям", bg="#2196F3", fg="white",
                font=("Arial", 12, "bold")).pack(pady=10)
        
        # Кнопки управления
        btns = tk.Frame(self)
        btns.pack(fill="x", padx=8, pady=6)
        
        tk.Button(btns, text="✓ Все", command=self._select_all,
                 bg="#4CAF50", fg="white", width=8).pack(side="left", padx=2)
        tk.Button(btns, text="✗ Ничего", command=self._select_none,
                 bg="#f44336", fg="white", width=8).pack(side="left", padx=2)
        tk.Button(btns, text="⇄ Инверт", command=self._invert_selection,
                 bg="#FF9800", fg="white", width=8).pack(side="left", padx=2)
        tk.Button(btns, text="↺ Сброс", command=self._clear_filter,
                 bg="#9E9E9E", fg="white", width=8).pack(side="right", padx=2)
        
        # Поиск
        search_fr = tk.Frame(self)
        search_fr.pack(fill="x", padx=8, pady=(4,4))
        tk.Label(search_fr, text="🔍 Поиск:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_fr, textvariable=self.search_var)
        self.search_entry.pack(fill="x", expand=True, side="left", padx=(4,0))
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_values())
        self.search_entry.focus()
        
        # Статус
        self.status_label = tk.Label(self, text="", anchor="w", fg="#666")
        self.status_label.pack(fill="x", padx=8)
        
        # Область с чекбоксами
        body = tk.Frame(self, relief="sunken", bd=1)
        body.pack(fill="both", expand=True, padx=8, pady=(0,8))
        
        self.canvas = tk.Canvas(body, highlightthickness=0, bg="white")
        vsb = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._on_wheel_linux(+1))
        self.canvas.bind("<Button-5>", lambda e: self._on_wheel_linux(-1))
        
        self.inner = tk.Frame(self.canvas, bg="white")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0,0), window=self.inner, anchor="nw")
        
        # Создание чекбоксов
        active = None if active_values is None else set(active_values)
        
        # Группировка по типам значений
        empty_values = []
        text_values = []
        number_values = []
        
        for value in values:
            if value in (None, ""):
                empty_values.append(value)
            elif isinstance(value, (int, float)):
                number_values.append(value)
            else:
                text_values.append(str(value))
        
        # Сортировка
        text_values.sort(key=lambda x: x.lower())
        number_values.sort()
        
        # Добавление чекбоксов по группам
        all_sorted = empty_values + number_values + text_values
        
        for i, value in enumerate(all_sorted):
            display = value if value not in (None, "") else "〈пусто〉"
            var = tk.BooleanVar(value=(True if active is None else (value in active)))
            
            frame = tk.Frame(self.inner, bg="white" if i % 2 == 0 else "#f8f8f8")
            frame.pack(fill="x", pady=1)
            
            chk = tk.Checkbutton(frame, text=str(display), anchor="w", variable=var,
                                 bg=frame["bg"], activebackground="#e0e0e0",
                                 selectcolor="white", font=("Arial", 10))
            chk.pack(fill="x", padx=4)
            
            self._items.append((value, str(display), var, frame))
        
        # Нижняя панель
        bottom = tk.Frame(self)
        bottom.pack(fill="x", padx=8, pady=(0,8))
        
        tk.Button(bottom, text="Отмена", command=self._on_cancel,
                 bg="#9E9E9E", fg="white", width=10).pack(side="right", padx=2)
        tk.Button(bottom, text="Применить", command=self._apply,
                 bg="#2196F3", fg="white", width=10).pack(side="right", padx=2)
        
        self._update_status()
    
    def _center_window(self):
        """Центрирование окна"""
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
    
    def _select_all(self):
        """Выбрать все"""
        for _, _, var, _ in self._items:
            var.set(True)
        self._update_status()
    
    def _select_none(self):
        """Снять все"""
        for _, _, var, _ in self._items:
            var.set(False)
        self._update_status()
    
    def _invert_selection(self):
        """Инвертировать выбор"""
        for _, _, var, _ in self._items:
            var.set(not var.get())
        self._update_status()
    
    def _clear_filter(self):
        """Сбросить фильтр (выбрать все)"""
        if callable(self.on_apply):
            self.on_apply(None)
        self.destroy()
    
    def _apply(self):
        """Применить фильтр"""
        if callable(self.on_apply):
            selected = [value for value, _, var, _ in self._items if var.get()]
            if len(selected) == len(self._items):
                self.on_apply(None)  # Все выбрано = нет фильтра
            else:
                self.on_apply(selected)
        self.destroy()
    
    def _on_cancel(self):
        """Отмена"""
        self.destroy()
    
    def _filter_values(self):
        """Фильтрация значений по поиску"""
        needle = self.search_var.get().strip().lower()
        visible_count = 0
        
        for value, display, var, widget in self._items:
            show = True
            if needle:
                show = needle in display.lower()
            
            widget.pack_forget()
            if show:
                widget.pack(fill="x", pady=1)
                visible_count += 1
        
        # Обновление статуса
        if needle:
            self.status_label.config(text=f"Показано: {visible_count} из {len(self._items)}")
        else:
            self._update_status()
    
    def _update_status(self):
        """Обновление статусной строки"""
        selected = sum(1 for _, _, var, _ in self._items if var.get())
        total = len(self._items)
        self.status_label.config(text=f"Выбрано: {selected} из {total}")
    
    def _on_wheel(self, event):
        """Прокрутка колесиком мыши"""
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
    
    def _on_wheel_linux(self, direction):
        """Прокрутка для Linux"""
        self.canvas.yview_scroll(-1 if direction > 0 else 1, "units")