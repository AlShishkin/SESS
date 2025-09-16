# -*- coding: utf-8 -*-
import math
import os, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from copy import deepcopy

from .geometry_utils import centroid_xy, bounds
from .state import (
    AppState, ALIAS_TO_PARAM,
    DEFAULT_ROOM_WORK_COLS, DEFAULT_AREA_WORK_COLS,
    DEFAULT_ROOM_SRC_COLS,  DEFAULT_AREA_SRC_COLS
)
from .io_bess import load_bess_export, save_work_geometry
from .widgets.columns_picker import ColumnsPicker

TOL_AREA_PICK_PX     = 3
TOL_ROOM_OUTLINE_PX  = 5
DRAW_COLOR           = "#ff00ff"
DRAW_SEL_EDGE_COLOR  = "#00ffff"
DRAW_SEL_VERTEX_COLOR = "#00ff00"
MAX_GRID_POINTS      = 20000

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BESS_GEOMETRY | Источник ↔ Рабочая модель")
        self.geometry("1200x800")

        self.state = AppState()

        self._undo_stack = []; self._redo_stack = []; self._UNDO_LIMIT = 60
        self._scale = 1.0; self._ox = 0.0; self._oy = 0.0; self._fit_done = False
        self._id2canvas = {}; self._canvas2rid = {}; self._sel_ids = set()
        self._orig_fill = {}; self._orig_outline = {}
        self._rebuilding = False; self._syncing = False
        self._sort_orders = {}; self._tree_anchor = {}
        self._edit_popup = None

        self._add_room_mode = None
        self._add_room_pts = []
        self._add_room_redo = []
        self._add_room_temp = []
        self._snap_var = tk.BooleanVar(value=True)
        self._ortho_var = tk.BooleanVar(value=False)
        self._add_room_base_id = None
        self._add_room_win = None

        self._edit_area_mode = False
        self._edit_area_pts = []
        self._edit_area_undo = []
        self._edit_area_redo = []
        self._edit_area_temp = []
        self._edit_area_sel_idx = None
        self._edit_area_sel_edge = None
        self._edit_area_area_id = None
        self._edit_area_win = None

        self._grid_mode_var = tk.StringVar(value="default")
        self._grid_size_var = tk.DoubleVar(value=1.0)
        self._grid_backup = {"rooms": {}, "areas": {}}
        self._grid_items = []
        self._grid_origin = (0.0, 0.0)

        self._build_ui()
        self._open_add_room_window()
        self.bind_all("<Delete>", self._on_delete_key)
        self.bind_all("<Control-z>", lambda e: self._undo())
        self.bind_all("<Control-y>", lambda e: self._redo())
        self.bind_all("<BackSpace>", self._on_backspace_key)
        self.bind_all("<Key-s>", self._toggle_snap_key)
        self.bind_all("<Key-o>", self._toggle_ortho_key)
        self.bind_all("<Escape>", self._on_escape_key)

    def _build_ui(self):
        self._build_top_frame()

        hsplit = tk.PanedWindow(self, orient="horizontal", sashwidth=6)
        hsplit.pack(fill="both", expand=True, padx=8, pady=(0,8))

        lv_box = tk.Frame(hsplit, bd=1, relief="groove", width=200)
        tk.Label(lv_box, text="Уровни (рабочая модель)", anchor="w").pack(fill="x", padx=6, pady=4)
        self.level_list = tk.Listbox(lv_box, activestyle="dotbox", exportselection=False, selectmode="extended")
        lvsb = ttk.Scrollbar(lv_box, orient="vertical", command=self.level_list.yview)
        self.level_list.configure(yscrollcommand=lvsb.set)
        self.level_list.pack(side="left", fill="both", expand=True); lvsb.pack(side="right", fill="y")
        tk.Button(lv_box, text="Удалить уровень (раб. модель)", command=self._delete_current_level).pack(fill="x", padx=6, pady=6)
        lv_box.pack_propagate(False)
        hsplit.add(lv_box)

        cv_box = tk.Frame(hsplit, bd=1, relief="groove")
        self.canvas = tk.Canvas(cv_box, bg="white"); self.canvas.pack(fill="both", expand=True)
        hsplit.add(cv_box)

        prop = tk.Frame(hsplit, bd=1, relief="groove", width=320)
        prop.pack_propagate(False)
        hsplit.add(prop)

        self._tool_frame = tk.Frame(prop)
        self._tool_frame.pack(fill="x", pady=(4,4))
        self._tool_bar = tk.Frame(self._tool_frame)
        self._tool_bar.pack(fill="x")
        self._add_grid_controls(self._tool_frame)
        self._tool_body = tk.Frame(self._tool_frame)
        self._tool_body.pack(fill="both", expand=True, padx=4, pady=4)

        rooms_section = tk.Frame(prop); rooms_section.pack(fill="both", expand=True, padx=4, pady=(0,4))
        tk.Label(rooms_section, text="Помещения (рабочая модель)", anchor="w").pack(fill="x")
        rm_btns = tk.Frame(rooms_section); rm_btns.pack(fill="x", pady=(2,2))
        tk.Button(rm_btns, text="Добавить помещение", command=self._open_rooms_source_window).pack(side="left")
        tk.Button(rm_btns, text="Удалить помещение", command=self._remove_selected_rooms).pack(side="left", padx=4)
        rm_tree_fr = tk.Frame(rooms_section); rm_tree_fr.pack(fill="both", expand=True)
        self.rooms_tree = ttk.Treeview(rm_tree_fr, columns=(), show="headings", selectmode="extended")
        vsbR = ttk.Scrollbar(rm_tree_fr, orient="vertical", command=self.rooms_tree.yview)
        self.rooms_tree.configure(yscrollcommand=vsbR.set)
        self.rooms_tree.pack(side="left", fill="both", expand=True); vsbR.pack(side="right", fill="y")

        areas_section = tk.Frame(prop); areas_section.pack(fill="both", expand=True, padx=4, pady=(0,4))
        tk.Label(areas_section, text="Оболочки (рабочая модель)", anchor="w").pack(fill="x")
        ar_btns = tk.Frame(areas_section); ar_btns.pack(fill="x", pady=(2,2))
        tk.Button(ar_btns, text="Добавить оболочку", command=self._open_areas_source_window).pack(side="left")
        tk.Button(ar_btns, text="Изменить оболочку", command=self._open_edit_area_window).pack(side="left", padx=4)
        tk.Button(ar_btns, text="Удалить оболочку", command=self._remove_selected_areas).pack(side="left", padx=4)
        ar_tree_fr = tk.Frame(areas_section); ar_tree_fr.pack(fill="both", expand=True)
        self.areas_tree = ttk.Treeview(ar_tree_fr, columns=(), show="headings", selectmode="extended")
        vsbA = ttk.Scrollbar(ar_tree_fr, orient="vertical", command=self.areas_tree.yview)
        self.areas_tree.configure(yscrollcommand=vsbA.set)
        self.areas_tree.pack(side="left", fill="both", expand=True); vsbA.pack(side="right", fill="y")

        self._rooms_src_win = None; self._areas_src_win = None
        self.rooms_all_tree = None; self.areas_all_tree = None
        self._rooms_src_canvas = None; self._areas_src_canvas = None

        self._setup_bindings()
        self._create_context_menu()

        self._rebuild_columns_models()
        self._rebuild_levels_list(select_index=0)
        self._fill_all_tables()
        self._redraw(force_fit=True)

    def _build_top_frame(self):
        top = tk.Frame(self)
        top.pack(fill="x", padx=8, pady=(8,4))
        tk.Button(top, text="Открыть JSON…", command=self._open_json).pack(side="left")
        tk.Button(top, text="Отменить", command=self._undo).pack(side="left", padx=(8,0))
        tk.Button(top, text="Вернуть",  command=self._redo).pack(side="left", padx=(6,8))
        self.file_label = tk.Label(top, text="", anchor="w")
        self.file_label.pack(side="left", fill="x", expand=True, padx=8)

    def _setup_bindings(self):
        self.canvas.bind("<Configure>", lambda e: self._redraw(force_fit=not self._fit_done))
        self.canvas.bind("<ButtonPress-1>", self._on_lmb_down)
        self.canvas.bind("<B1-Motion>", self._on_lmb_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_lmb_up)
        self.canvas.bind("<Button-3>", self._on_canvas_rclick)
        self.canvas.bind("<Button-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_move)
        self.canvas.bind("<ButtonRelease-2>", self._on_pan_end)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", lambda e: self._on_mousewheel_linux(e, +1))
        self.canvas.bind("<Button-5>", lambda e: self._on_mousewheel_linux(e, -1))

        self.level_list.bind("<<ListboxSelect>>", self._on_level_changed)

        for t in (self.rooms_tree, self.areas_tree):
            self._bind_tree_common(t)
        self.rooms_tree.bind("<Double-1>", lambda e: self._try_edit_combo(e, self.rooms_tree), add="+")
        self.areas_tree.bind("<Double-1>", lambda e: self._try_edit_combo(e, self.areas_tree), add="+")

    def _bind_tree_common(self, t):
        t.bind("<Button-1>", self._on_tree_click, add="+")
        t.bind("<<TreeviewSelect>>", self._on_tree_select, add="+")
        t.bind("<Button-3>", self._on_tree_rclick, add="+")

    def _create_context_menu(self):
        self.ctx = tk.Menu(self, tearoff=0)
        self.ctx.add_command(label="Удалить выбранное (раб.)", command=self._ctx_delete)

    # ---------- add room window ----------
    def _open_add_room_window(self):
        if self._edit_area_win:
            self._edit_area_cancel(reopen=False)
        self._add_room_cancel()
        for c in self._tool_bar.winfo_children():
            c.destroy()
        for c in self._tool_body.winfo_children():
            c.destroy()
        self._add_room_win = True
        bar = tk.Frame(self._tool_bar); bar.pack(fill="x", pady=4)
        tk.Button(bar, text="Добавить VOID", command=lambda: self._select_add_room_mode("void")).pack(side="left")
        tk.Button(bar, text="Добавить Второй свет", command=lambda: self._select_add_room_mode("second")).pack(side="left", padx=4)
        tk.Button(bar, text="Внести изменения", command=self._add_room_finish).pack(side="left", padx=4)
        self._add_room_opts = self._tool_body

    def _select_add_room_mode(self, mode):
        self._add_room_mode = mode
        self._add_room_pts = []
        self._add_room_redo = []
        for c in self._add_room_opts.winfo_children():
            c.destroy()
        tk.Checkbutton(self._add_room_opts, text="Включить привязки", variable=self._snap_var).pack(anchor="w")
        tk.Checkbutton(self._add_room_opts, text="Ортогональный режим", variable=self._ortho_var).pack(anchor="w")
        ctrl = tk.Frame(self._add_room_opts); ctrl.pack(anchor="w", pady=(4,0))
        tk.Button(ctrl, text="Назад", command=self._add_room_undo).pack(side="left")
        tk.Button(ctrl, text="Вперед", command=self._add_room_redo_fn).pack(side="left", padx=4)
        if mode == "second":
            lowers = self._lower_levels(self._current_level())
            rooms = [r for r in self.state.work_rooms if r.get("params",{}).get("BESS_level","") in lowers]
            names = []
            self._base_name2id = {}
            for r in rooms:
                nm = r.get("name", "")
                lvl = r.get("params", {}).get("BESS_level", "")
                label = f"{nm} (level={lvl})"
                names.append(label)
                self._base_name2id[label] = r.get("id")
            self._base_room_var = tk.StringVar(value=names[0] if names else "")
            self._add_room_base_id = self._base_name2id.get(self._base_room_var.get())
            ttk.Label(self._add_room_opts, text="Выбрать основное помещение").pack(anchor="w", pady=(4,0))
            combo = ttk.Combobox(self._add_room_opts, values=names, textvariable=self._base_room_var, state="readonly")
            combo.pack(fill="x", pady=(0,4))
            combo.bind(
                "<<ComboboxSelected>>",
                lambda e: setattr(self, "_add_room_base_id", self._base_name2id.get(self._base_room_var.get())),
            )

    def _add_room_undo(self):
        if self._add_room_pts:
            self._add_room_redo.append(self._add_room_pts.pop())
            self._draw_temp_poly()

    def _add_room_redo_fn(self):
        if self._add_room_redo:
            self._add_room_pts.append(self._add_room_redo.pop())
            self._draw_temp_poly()

    def _add_room_cancel(self):
        self._add_room_mode = None
        self._add_room_pts = []
        self._add_room_redo = []
        for cid in getattr(self, "_add_room_temp", []) or []:
            self.canvas.delete(cid)
        self._add_room_temp = []

    def _add_room_finish(self):
        if len(self._add_room_pts) < 3:
            return
        level = self._current_level()
        self._push_undo()
        coords = [self._snap_point(x, y) for x, y in self._add_room_pts]
        if self._add_room_mode == "void":
            new_id = self.state.add_void(level, coords)
        elif self._add_room_mode == "second" and self._add_room_base_id:
            new_id = self.state.add_second_light(self._add_room_base_id, level, coords)
        else:
            new_id = None
        self._add_room_pts = []
        self._add_room_redo = []
        self._draw_temp_poly()
        self._fill_all_tables(); self._redraw(False)
        if new_id:
            self._select_ids([new_id], additive=False)

    def _draw_temp_poly(self):
        for cid in self._add_room_temp:
            self.canvas.delete(cid)
        self._add_room_temp = []
        if not self._add_room_pts:
            return
        pts = self._add_room_pts
        for i in range(len(pts)-1):
            x0, y0 = self._to_screen(*pts[i])
            x1, y1 = self._to_screen(*pts[i+1])
            self._add_room_temp.append(
                self.canvas.create_line(x0, y0, x1, y1, fill=DRAW_COLOR, dash=(4,2), width=6)
            )
        for x, y in pts:
            X, Y = self._to_screen(x, y)
            self._add_room_temp.append(
                self.canvas.create_oval(X-8, Y-8, X+8, Y+8, outline=DRAW_COLOR, fill=DRAW_COLOR, width=0)
            )

    def _lower_levels(self, lvl):
        names = self.state.levels_sorted_names(self.state.work_levels)
        try:
            i = names.index(lvl)
            return names[:i]
        except Exception:
            return []

    def _add_room_click(self, e):
        X, Y = e.x, e.y
        if self._snap_var.get():
            wx, wy = self._snap_world(X, Y)
        else:
            wx, wy = self._from_screen(X, Y)
        wx, wy = self._snap_point(wx, wy)
        wx, wy = self._snap_point(wx, wy)
        if self._add_room_pts:
            x0, y0 = self._to_screen(*self._add_room_pts[0])
            dist = ((X - x0)**2 + (Y - y0)**2) ** 0.5
            if dist <= 10 and len(self._add_room_pts) >= 3:
                self._add_room_finish()
                return
        if self._ortho_var.get() and self._add_room_pts:
            x_prev, y_prev = self._add_room_pts[-1]
            if abs(wx - x_prev) >= abs(wy - y_prev):
                wy = y_prev
            else:
                wx = x_prev
        self._add_room_pts.append((wx, wy))
        self._add_room_redo = []
        self._draw_temp_poly()

    def _snap_world(self, X, Y):
        pts = []
        segs = []
        lvl = self._current_level()
        items = [r for r in self.state.work_rooms if r.get("params",{}).get("BESS_level","") == lvl]
        items += [a for a in self.state.work_areas if a.get("params",{}).get("BESS_level","") == lvl]
        for it in items:
            loops = [it.get("outer_xy_m", [])] + it.get("inner_loops_xy_m", [])
            for loop in loops:
                pts.extend(loop)
                for i in range(len(loop)):
                    p1 = loop[i]; p2 = loop[(i+1)%len(loop)]
                    segs.append((p1, p2))
        best_v = None; dv = 1e9
        for x, y in pts:
            sx, sy = self._to_screen(x, y)
            d = ((sx - X)**2 + (sy - Y)**2) ** 0.5
            if d < dv:
                dv = d; best_v = (x, y)
        if best_v and dv <= 10:
            return best_v
        wx, wy = self._from_screen(X, Y)
        best_e = None; de = 1e9
        for (x1, y1), (x2, y2) in segs:
            dx = x2 - x1; dy = y2 - y1
            if dx == 0 and dy == 0:
                continue
            t = ((wx - x1) * dx + (wy - y1) * dy) / (dx*dx + dy*dy)
            t = max(0, min(1, t))
            px = x1 + t*dx; py = y1 + t*dy
            sx, sy = self._to_screen(px, py)
            d = ((sx - X)**2 + (sy - Y)**2) ** 0.5
            if d < de:
                de = d; best_e = (px, py)
        if best_e and de <= 10:
            return best_e
        return wx, wy

    # ---------- edit area window ----------
    def _open_edit_area_window(self):
        if self._add_room_win:
            self._add_room_cancel()
            self._add_room_win = None
        if self._edit_area_win:
            self._edit_area_cancel(reopen=False)
        self._edit_area_mode = True
        for c in self._tool_bar.winfo_children():
            c.destroy()
        for c in self._tool_body.winfo_children():
            c.destroy()
        self._edit_area_win = True
        bar = tk.Frame(self._tool_bar); bar.pack(fill="x", pady=4)
        tk.Button(bar, text="Внести изменения", command=self._edit_area_finish).pack(side="left")
        tk.Button(bar, text="Закрыть", command=self._edit_area_cancel).pack(side="right")
        self._edit_area_opts = self._tool_body
        level = self._current_level()
        areas = [a for a in self.state.work_areas if a.get("params",{}).get("BESS_level","") == level]
        names = []; self._area_name2id = {}
        for a in areas:
            nm = a.get("name","") or str(a.get("id"))
            names.append(nm); self._area_name2id[nm] = a.get("id")
        self._edit_area_var = tk.StringVar(value=names[0] if names else "")
        ttk.Label(self._edit_area_opts, text="Выбрать оболочку").pack(anchor="w")
        combo = ttk.Combobox(self._edit_area_opts, values=names, textvariable=self._edit_area_var, state="readonly")
        combo.pack(fill="x", pady=(0,4))
        combo.bind("<<ComboboxSelected>>", lambda e: self._load_edit_area())
        tk.Checkbutton(self._edit_area_opts, text="Включить привязки", variable=self._snap_var).pack(anchor="w")
        tk.Checkbutton(self._edit_area_opts, text="Ортогональный режим", variable=self._ortho_var).pack(anchor="w")
        ctrl = tk.Frame(self._edit_area_opts); ctrl.pack(anchor="w", pady=(4,0))
        tk.Button(ctrl, text="Назад", command=self._edit_area_undo_fn).pack(side="left")
        tk.Button(ctrl, text="Вперед", command=self._edit_area_redo_fn).pack(side="left", padx=4)
        if names:
            self._edit_area_area_id = self._area_name2id.get(self._edit_area_var.get())
            self._load_edit_area()

    def _load_edit_area(self):
        aid = self._area_name2id.get(self._edit_area_var.get())
        self._edit_area_area_id = aid
        self._edit_area_pts = []
        self._edit_area_undo = []
        self._edit_area_redo = []
        self._edit_area_sel_idx = None
        self._edit_area_sel_edge = None
        area = next((a for a in self.state.work_areas if str(a.get("id")) == str(aid)), None)
        if area:
            self._edit_area_pts = [tuple(p) for p in area.get("outer_xy_m", [])]
        self._draw_edit_area_poly()

    def _edit_area_push_undo(self):
        self._edit_area_undo.append(self._edit_area_pts[:])
        if len(self._edit_area_undo) > self._UNDO_LIMIT:
            self._edit_area_undo.pop(0)

    def _edit_area_undo_fn(self):
        if self._edit_area_undo:
            self._edit_area_redo.append(self._edit_area_pts[:])
            self._edit_area_pts = self._edit_area_undo.pop()
            self._edit_area_sel_idx = None
            self._edit_area_sel_edge = None
            self._draw_edit_area_poly()

    def _edit_area_redo_fn(self):
        if self._edit_area_redo:
            self._edit_area_undo.append(self._edit_area_pts[:])
            self._edit_area_pts = self._edit_area_redo.pop()
            self._edit_area_sel_idx = None
            self._edit_area_sel_edge = None
            self._draw_edit_area_poly()

    def _edit_area_cancel(self, reopen=True):
        self._edit_area_mode = False
        self._edit_area_pts = []
        self._edit_area_undo = []
        self._edit_area_redo = []
        self._edit_area_sel_idx = None
        self._edit_area_sel_edge = None
        for cid in self._edit_area_temp:
            self.canvas.delete(cid)
        self._edit_area_temp = []
        if self._edit_area_win:
            self._edit_area_win = None
            if reopen:
                self._open_add_room_window()

    def _edit_area_finish(self):
        if len(self._edit_area_pts) < 3 or not self._edit_area_area_id:
            return
        self._push_undo()
        coords = [self._snap_point(x, y) for x, y in self._edit_area_pts]
        self.state.update_area_coords(self._edit_area_area_id, coords)
        aid = self._edit_area_area_id
        self._fill_all_tables(); self._redraw(False)
        self._select_ids([aid], additive=False)
        self._edit_area_undo = []
        self._edit_area_redo = []
        self._edit_area_sel_idx = None
        self._edit_area_sel_edge = None
        self._draw_edit_area_poly()

    def _draw_edit_area_poly(self):
        for cid in self._edit_area_temp:
            self.canvas.delete(cid)
        self._edit_area_temp = []
        if not self._edit_area_pts:
            return
        pts = self._edit_area_pts
        n = len(pts)
        for i in range(n):
            x0, y0 = self._to_screen(*pts[i])
            x1, y1 = self._to_screen(*pts[(i+1)%n])
            col = DRAW_SEL_EDGE_COLOR if i == self._edit_area_sel_edge else DRAW_COLOR
            width = 6 if i == self._edit_area_sel_edge else 4
            self._edit_area_temp.append(
                self.canvas.create_line(x0, y0, x1, y1, fill=col, dash=(4,2), width=width)
            )
        for idx, (x, y) in enumerate(pts):
            X, Y = self._to_screen(x, y)
            r = 8 if idx == self._edit_area_sel_idx else 6
            fill = DRAW_SEL_VERTEX_COLOR if idx == self._edit_area_sel_idx else DRAW_COLOR
            self._edit_area_temp.append(
                self.canvas.create_oval(X-r, Y-r, X+r, Y+r, fill=fill, outline="")
            )

    def _nearest_vertex_edge(self, X, Y, pts):
        vi = None; vd = 1e9
        for i, (x, y) in enumerate(pts):
            sx, sy = self._to_screen(x, y)
            d = ((sx - X)**2 + (sy - Y)**2) ** 0.5
            if d < vd:
                vd = d; vi = i
        ei = None; ed = 1e9; ept = None
        wx, wy = self._from_screen(X, Y)
        for i in range(len(pts)):
            x1, y1 = pts[i]; x2, y2 = pts[(i+1)%len(pts)]
            dx = x2 - x1; dy = y2 - y1
            if dx == 0 and dy == 0:
                continue
            t = ((wx - x1) * dx + (wy - y1) * dy) / (dx*dx + dy*dy)
            t = max(0, min(1, t))
            px = x1 + t*dx; py = y1 + t*dy
            sx, sy = self._to_screen(px, py)
            d = ((sx - X)**2 + (sy - Y)**2) ** 0.5
            if d < ed:
                ed = d; ei = i; ept = (px, py)
        return vi, vd, ei, ept, ed

    def _edit_area_click(self, e):
        X, Y = e.x, e.y
        if self._snap_var.get():
            wx, wy = self._snap_world(X, Y)
        else:
            wx, wy = self._from_screen(X, Y)
        wx, wy = self._snap_point(wx, wy)
        vi, vd, ei, ept, ed = self._nearest_vertex_edge(X, Y, self._edit_area_pts)
        if vi is not None and vd <= 10:
            self._edit_area_sel_idx = vi
            self._edit_area_sel_edge = None
            self._draw_edit_area_poly()
            return
        if ei is not None and ed <= 10:
            if e.state & 0x0001:
                self._edit_area_push_undo()
                if self._ortho_var.get():
                    x0, y0 = self._edit_area_pts[ei]
                    if abs(wx - x0) >= abs(wy - y0):
                        wy = y0
                    else:
                        wx = x0
                wx, wy = self._snap_point(wx, wy)
                self._edit_area_pts.insert(ei+1, (wx, wy))
                self._edit_area_sel_idx = ei+1
                self._edit_area_sel_edge = None
                self._draw_edit_area_poly()
            else:
                self._edit_area_sel_idx = None
                self._edit_area_sel_edge = ei
                self._draw_edit_area_poly()
            return
        self._edit_area_push_undo()
        if self._ortho_var.get() and self._edit_area_pts:
            x_prev, y_prev = self._edit_area_pts[-1]
            if abs(wx - x_prev) >= abs(wy - y_prev):
                wy = y_prev
            else:
                wx = x_prev
        wx, wy = self._snap_point(wx, wy)
        self._edit_area_pts.append((wx, wy))
        self._edit_area_sel_idx = len(self._edit_area_pts) - 1
        self._edit_area_sel_edge = None
        self._draw_edit_area_poly()

    def _edit_area_delete_selected(self):
        if self._edit_area_sel_idx is not None and len(self._edit_area_pts) > 3:
            self._edit_area_push_undo()
            del self._edit_area_pts[self._edit_area_sel_idx]
            self._edit_area_sel_idx = None
            self._draw_edit_area_poly()
        elif self._edit_area_sel_edge is not None and len(self._edit_area_pts) > 3:
            idx = (self._edit_area_sel_edge + 1) % len(self._edit_area_pts)
            self._edit_area_push_undo()
            del self._edit_area_pts[idx]
            self._edit_area_sel_edge = None
            self._draw_edit_area_poly()


    # ---------- columns pickers ----------
    def _rebuild_columns_models(self):
        def build_vars(keys, defaults):
            vars_dict = {}
            for k in sorted(keys, key=lambda s: s.lower()):
                vars_dict[k] = tk.BooleanVar(value=(k in defaults))
            return vars_dict

        r_work_keys = set(["id","name","number","label","BESS_level","BESS_Upper_level","BESS_Room_Upper_level","BESS_Room_Height"])
        for it in self.state.work_rooms:
            for k in (it.get("params") or {}).keys():
                r_work_keys.add(k)
        a_work_keys = set(["id","name","number","label","BESS_level"])
        for it in self.state.work_areas:
            for k in (it.get("params") or {}).keys():
                a_work_keys.add(k)
        r_src_keys = set(["id","level","name","number","label"])
        for it in self.state.base_rooms:
            for k in (it.get("params") or {}).keys():
                r_src_keys.add(k)
        a_src_keys = set(["id","level","name","number","label"])
        for it in self.state.base_areas:
            for k in (it.get("params") or {}).keys():
                a_src_keys.add(k)

        self.room_work_cols_vars = build_vars(r_work_keys, DEFAULT_ROOM_WORK_COLS)
        self.area_work_cols_vars = build_vars(a_work_keys, DEFAULT_AREA_WORK_COLS)
        self.room_src_cols_vars  = build_vars(r_src_keys,  DEFAULT_ROOM_SRC_COLS)
        self.area_src_cols_vars  = build_vars(a_src_keys,  DEFAULT_AREA_SRC_COLS)

    def _open_room_work_cols(self):
        ColumnsPicker(self, "Столбцы рабочих помещений", self.room_work_cols_vars, self._refresh_tables)

    def _open_area_work_cols(self):
        ColumnsPicker(self, "Столбцы рабочей оболочки", self.area_work_cols_vars, self._refresh_tables)

    def _open_room_src_cols(self):
        ColumnsPicker(self, "Столбцы источника (помещения)", self.room_src_cols_vars, self._refresh_tables)

    def _open_area_src_cols(self):
        ColumnsPicker(self, "Столбцы источника (оболочка)", self.area_src_cols_vars, self._refresh_tables)

    # ---------- undo/redo ----------
    def _snapshot(self):
        s = AppState()
        s.meta = deepcopy(self.state.meta)
        s.base_levels = deepcopy(self.state.base_levels)
        s.base_rooms  = deepcopy(self.state.base_rooms)
        s.base_areas  = deepcopy(self.state.base_areas)
        s.work_levels = deepcopy(self.state.work_levels)
        s.work_rooms  = deepcopy(self.state.work_rooms)
        s.work_areas  = deepcopy(self.state.work_areas)
        s.selected_level = self.state.selected_level
        s.room_work_cols = self.state.room_work_cols[:]
        s.area_work_cols = self.state.area_work_cols[:]
        s.room_src_cols  = self.state.room_src_cols[:]
        s.area_src_cols  = self.state.area_src_cols[:]
        return s

    def _apply_snapshot(self, s):
        self.state = s
        self._clear_selection()
        self._rebuild_levels_list()
        self._fill_all_tables()
        self._redraw(True)

    def _push_undo(self):
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > self._UNDO_LIMIT:
            self._undo_stack.pop(0)
        self._redo_stack[:] = []

    def _undo(self):
        if not self._undo_stack:
            return
        snap = self._undo_stack.pop()
        self._redo_stack.append(self._snapshot())
        self._apply_snapshot(snap)

    def _redo(self):
        if not self._redo_stack:
            return
        snap = self._redo_stack.pop()
        self._undo_stack.append(self._snapshot())
        self._apply_snapshot(snap)

    # ---------- file ops ----------
    def _open_json(self):
        path = filedialog.askopenfilename(title="Открыть bess_export.json", filetypes=[("JSON","*.json")])
        if not path:
            return
        try:
            meta, base_lv, base_rooms, base_areas = load_bess_export(path)
            self.state.set_source(meta, base_lv, base_rooms, base_areas)
        except Exception as e:
            messagebox.showerror("Ошибка чтения JSON", str(e)); return

        self.file_label.config(text=os.path.basename(path))
        self._undo_stack[:] = []; self._redo_stack[:] = []
        self._rebuild_columns_models()
        self._rebuild_levels_list(select_index=0)
        self._fill_all_tables()
        self._redraw(force_fit=True)

    def _save_energy_json(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON","*.json")],
                                            initialfile="bess_work_geometry.json")
        if not path:
            return
        try:
            save_work_geometry(path, self.state.meta, self.state.work_levels, self.state.work_rooms, self.state.work_areas)
            messagebox.showinfo("Сохранено", f"Рабочая геометрия записана:\n{os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Ошибка записи", str(e))

    # ---------- levels ----------
    def _rebuild_levels_list(self, select_index=None):
        self.level_list.delete(0, "end")
        for n in self.state.levels_sorted_names(self.state.work_levels):
            self.level_list.insert("end", n)
        if select_index is not None and self.level_list.size() > 0:
            idx = max(0, min(select_index, self.level_list.size()-1))
            self.level_list.selection_clear(0, "end")
            self.level_list.selection_set(idx)

    def _current_level(self):
        sel = self.level_list.curselection()
        if sel:
            return self.level_list.get(sel[-1])
        if self.level_list.size() > 0:
            return self.level_list.get(0)
        return ""

    def _on_level_changed(self, _e=None):
        self.state.selected_level = self._current_level()
        self._clear_selection()
        self._refill_level_tables()
        self._redraw(False)

    def _delete_current_level(self):
        sel = list(self.level_list.curselection())
        if not sel:
            return
        lv_names = [self.level_list.get(i) for i in sel]
        self._push_undo()
        self.state.delete_levels(lv_names)
        next_idx = min(sel[0], max(0, self.level_list.size()-1))
        self._rebuild_levels_list(select_index=next_idx)
        self._refill_level_tables(); self._redraw(True)

    # ---------- tables ----------
    def _apply_columns(self, tree, cols):
        tree["columns"] = cols
        for c in cols:
            tree.heading(c, text=c, command=lambda cc=c, tt=tree: self._sort_tree(tt, cc))
            tree.column(c, width=(150 if c in ("BESS_level","BESS_Upper_level","BESS_Room_Height") else 140), anchor="w")

    def _sort_tree(self, tree, col):
        prev = self._sort_orders.get(tree, ("", False))
        reverse = not prev[1] if prev[0] == col else False
        self._sort_orders[tree] = (col, reverse)

        def _num(x):
            try:
                return float(str(x).replace(" ","").replace(",", "."))
            except Exception:
                return str(x)

        rows = [(tree.set(i, col), i) for i in tree.get_children("")]
        rows.sort(key=lambda t: _num(t[0]), reverse=reverse)
        for idx, (_, iid) in enumerate(rows):
            tree.move(iid, "", idx)

    def _fill_one_table(self, tree, items, cols, *, is_work):
        self._rebuilding = True
        try:
            self._apply_columns(tree, cols)
            tree.delete(*tree.get_children(""))

            def val(it, k):
                if is_work:
                    prs = it.get("params") or {}
                    if k == "BESS_Room_Height":
                        return str(self.state.room_height_m(it))
                    key = ALIAS_TO_PARAM.get(k, k)
                    if k in ("id","name","number","label"):
                        return str(it.get(k,""))
                    return str(prs.get(key, ""))
                else:
                    if k in ("id","level","name","number","label"):
                        return str(it.get(k,""))
                    return str((it.get("params") or {}).get(k, ""))

            for it in items:
                row = [val(it, k) for k in cols]
                tree.insert("", "end", iid=str(it.get("id","")), values=row)
        finally:
            self._rebuilding = False

    def _fill_all_tables(self):
        room_cols = [k for k,v in self.room_src_cols_vars.items() if v.get()] or DEFAULT_ROOM_SRC_COLS
        area_cols = [k for k,v in self.area_src_cols_vars.items() if v.get()] or DEFAULT_AREA_SRC_COLS
        if self.rooms_all_tree:
            self._fill_one_table(self.rooms_all_tree, self.state.base_rooms, room_cols, is_work=False)
        if self.areas_all_tree:
            self._fill_one_table(self.areas_all_tree, self.state.base_areas, area_cols, is_work=False)
        self._refill_level_tables()

    def _refill_level_tables(self):
        lvl = self._current_level()
        r_items = [r for r in self.state.work_rooms if (r.get("params",{}).get("BESS_level","") == lvl)]
        a_items = [a for a in self.state.work_areas if (a.get("params",{}).get("BESS_level","") == lvl)]
        room_cols = [k for k,v in self.room_work_cols_vars.items() if v.get()] or DEFAULT_ROOM_WORK_COLS
        area_cols = [k for k,v in self.area_work_cols_vars.items() if v.get()] or DEFAULT_AREA_WORK_COLS
        self._fill_one_table(self.rooms_tree, r_items, room_cols, is_work=True)
        self._fill_one_table(self.areas_tree, a_items, area_cols, is_work=True)

    def _refresh_tables(self):
        self._fill_all_tables(); self._redraw(False)

    # ---------- add/remove ----------
    def _add_rooms_to_level(self):
        if not self.rooms_all_tree:
            return
        ids = set(self.rooms_all_tree.selection())
        if not ids: return
        self._push_undo()
        new_ids = self.state.add_rooms_to_level(ids)
        self._rebuild_columns_models()
        self._fill_all_tables(); self._redraw(False)
        if new_ids:
            self._select_ids(new_ids, additive=False)

    def _add_areas_to_level(self):
        if not self.areas_all_tree:
            return
        ids = set(self.areas_all_tree.selection())
        if not ids: return
        self._push_undo()
        new_ids = self.state.add_areas_to_level(ids)
        self._rebuild_columns_models()
        self._fill_all_tables(); self._redraw(False)
        if new_ids:
            self._select_ids(new_ids, additive=False)

    def _remove_selected_rooms(self):
        ids = set(self.rooms_tree.selection()) or {i for i in self._sel_ids if any(str(r.get("id")) == i for r in self.state.work_rooms)}
        if not ids: return
        self._push_undo()
        self.state.remove_rooms(ids)
        self._fill_all_tables(); self._clear_selection(); self._redraw(False)

    def _remove_selected_areas(self):
        ids = set(self.areas_tree.selection()) or {i for i in self._sel_ids if any(str(a.get("id")) == i for a in self.state.work_areas)}
        if not ids: return
        self._push_undo()
        self.state.remove_areas(ids)
        self._fill_all_tables(); self._clear_selection(); self._redraw(False)

    def _open_rooms_source_window(self):
        if self._rooms_src_win:
            self._rooms_src_win.lift(); return
        win = tk.Toplevel(self); win.title("Помещения (источник)")
        pan = tk.PanedWindow(win, orient="horizontal", sashwidth=4)
        pan.pack(fill="both", expand=True)
        tree_fr = tk.Frame(pan)
        self.rooms_all_tree = ttk.Treeview(tree_fr, columns=(), show="headings", selectmode="extended")
        vsb = ttk.Scrollbar(tree_fr, orient="vertical", command=self.rooms_all_tree.yview)
        self.rooms_all_tree.configure(yscrollcommand=vsb.set)
        self.rooms_all_tree.pack(side="left", fill="both", expand=True); vsb.pack(side="right", fill="y")
        pan.add(tree_fr, width=300)
        cv_fr = tk.Frame(pan)
        self._rooms_src_canvas = tk.Canvas(cv_fr, bg="white")
        self._rooms_src_canvas.pack(fill="both", expand=True)
        pan.add(cv_fr)
        btns = tk.Frame(win); btns.pack(fill="x")
        tk.Button(btns, text="Добавить выбранные", command=self._add_rooms_to_level).pack(side="left")
        tk.Button(btns, text="Закрыть", command=self._close_rooms_source_window).pack(side="right")
        self._rooms_src_win = win
        win.protocol("WM_DELETE_WINDOW", self._close_rooms_source_window)
        self._bind_tree_common(self.rooms_all_tree)
        self.rooms_all_tree.bind("<<TreeviewSelect>>", lambda e: self._draw_rooms_src_preview(), add="+")
        room_cols = [k for k,v in self.room_src_cols_vars.items() if v.get()] or DEFAULT_ROOM_SRC_COLS
        self._fill_one_table(self.rooms_all_tree, self.state.base_rooms, room_cols, is_work=False)
        self._draw_rooms_src_preview()

    def _close_rooms_source_window(self):
        if self._rooms_src_win:
            self._rooms_src_win.destroy()
            self._rooms_src_win = None
            self.rooms_all_tree = None
            self._rooms_src_canvas = None

    def _draw_rooms_src_preview(self):
        if not self._rooms_src_canvas or not self.rooms_all_tree:
            return
        sel = set(self.rooms_all_tree.selection())
        items = [r for r in self.state.base_rooms if str(r.get("id")) in sel] or self.state.base_rooms
        self._draw_preview(self._rooms_src_canvas, items, outline="#333", fill="#bfe3ff")

    def _open_areas_source_window(self):
        if self._areas_src_win:
            self._areas_src_win.lift(); return
        win = tk.Toplevel(self); win.title("Оболочки (источник)")
        pan = tk.PanedWindow(win, orient="horizontal", sashwidth=4)
        pan.pack(fill="both", expand=True)
        tree_fr = tk.Frame(pan)
        self.areas_all_tree = ttk.Treeview(tree_fr, columns=(), show="headings", selectmode="extended")
        vsb = ttk.Scrollbar(tree_fr, orient="vertical", command=self.areas_all_tree.yview)
        self.areas_all_tree.configure(yscrollcommand=vsb.set)
        self.areas_all_tree.pack(side="left", fill="both", expand=True); vsb.pack(side="right", fill="y")
        pan.add(tree_fr, width=300)
        cv_fr = tk.Frame(pan)
        self._areas_src_canvas = tk.Canvas(cv_fr, bg="white")
        self._areas_src_canvas.pack(fill="both", expand=True)
        pan.add(cv_fr)
        btns = tk.Frame(win); btns.pack(fill="x")
        tk.Button(btns, text="Добавить выбранные", command=self._add_areas_to_level).pack(side="left")
        tk.Button(btns, text="Закрыть", command=self._close_areas_source_window).pack(side="right")
        self._areas_src_win = win
        win.protocol("WM_DELETE_WINDOW", self._close_areas_source_window)
        self._bind_tree_common(self.areas_all_tree)
        self.areas_all_tree.bind("<<TreeviewSelect>>", lambda e: self._draw_areas_src_preview(), add="+")
        area_cols = [k for k,v in self.area_src_cols_vars.items() if v.get()] or DEFAULT_AREA_SRC_COLS
        self._fill_one_table(self.areas_all_tree, self.state.base_areas, area_cols, is_work=False)
        self._draw_areas_src_preview()

    def _close_areas_source_window(self):
        if self._areas_src_win:
            self._areas_src_win.destroy()
            self._areas_src_win = None
            self.areas_all_tree = None
            self._areas_src_canvas = None

    def _draw_areas_src_preview(self):
        if not self._areas_src_canvas or not self.areas_all_tree:
            return
        sel = set(self.areas_all_tree.selection())
        items = [a for a in self.state.base_areas if str(a.get("id")) in sel] or self.state.base_areas
        self._draw_preview(self._areas_src_canvas, items, outline="#D22", fill="")

    def _draw_preview(self, cv, items, outline="#333", fill=""):
        cv.delete("all")
        if not items:
            return
        minx, miny, maxx, maxy = bounds(items)
        w = max(maxx - minx, 1e-9); h = max(maxy - miny, 1e-9)
        cw = max(cv.winfo_width(), 100); ch = max(cv.winfo_height(), 100)
        m = 20
        scale = min((cw - m) / w, (ch - m) / h)
        ox = (-minx * scale) + m / 2.0
        oy = (maxy * scale) + m / 2.0
        for it in items:
            flat = []
            for x, y in it["outer_xy_m"]:
                X = x * scale + ox
                Y = -y * scale + oy
                flat += [X, Y]
            cv.create_polygon(flat, outline=outline, fill=fill)
            for hole in it.get("inner_loops_xy_m", []):
                flat = []
                for x, y in hole:
                    X = x * scale + ox
                    Y = -y * scale + oy
                    flat += [X, Y]
                cv.create_polygon(flat, outline=outline, fill="")

    # ---------- selection sync ----------
    def _set_selected(self, rid, on):
        rid = str(rid)
        if rid not in self._id2canvas:
            return
        kind, base = self._id2canvas[rid]
        oc, ow = self._orig_outline.get(rid, ("#333" if kind=="room" else "#D22", 2 if kind=="room" else 4))
        fill0 = self._orig_fill.get(rid, "")
        if on:
            if kind == "room":
                self.canvas.itemconfigure(base, outline="#0078D7", width=4, fill="#bfe3ff", stipple="gray25")
            else:
                self.canvas.itemconfigure(base, outline="#0078D7", width=6)
        else:
            if kind == "room":
                self.canvas.itemconfigure(base, outline=oc, width=ow, fill=fill0, stipple="")
            else:
                self.canvas.itemconfigure(base, outline=oc, width=ow)

    def _clear_selection(self):
        if not self._sel_ids: return
        for rid in list(self._sel_ids):
            self._set_selected(rid, False)
        self._sel_ids.clear()
        self._syncing = True
        try:
            for t in (self.rooms_tree, self.areas_tree, self.rooms_all_tree, self.areas_all_tree):
                try:
                    t.selection_remove(*t.selection())
                except Exception:
                    pass
        finally:
            self._syncing = False

    def _sync_tables_to_target(self, target_ids):
        self._syncing = True
        try:
            for t in (self.rooms_tree, self.areas_tree, self.rooms_all_tree, self.areas_all_tree):
                if not t:
                    continue
                ch = set(t.get_children(""))
                cur = set(t.selection()); desired = ch & target_ids
                to_add = desired - cur; to_del = cur - desired
                if to_del:
                    t.selection_remove(*list(to_del))
                if to_add:
                    t.selection_add(*list(to_add))
                    t.see(next(iter(to_add)))
        finally:
            self._syncing = False

    def _select_ids(self, ids, additive=False):
        target = set(self._sel_ids)
        if additive:
            target |= {str(i) for i in ids}
        else:
            target = {str(i) for i in ids}
        if target == self._sel_ids:
            return
        to_add = target - self._sel_ids; to_del = self._sel_ids - target
        for rid in to_del:
            self._set_selected(rid, False)
        for rid in to_add:
            self._set_selected(rid, True)
        self._sel_ids = target
        self._sync_tables_to_target(self._sel_ids)

    # ---------- table & canvas events ----------
    def _on_tree_click(self, e):
        if self._rebuilding or self._syncing:
            return "break"
        region = e.widget.identify("region", e.x, e.y)
        if region == "heading":
            return
        t = e.widget
        ctrl  = (e.state & 0x0004) != 0
        shift = (e.state & 0x0001) != 0
        item = t.identify_row(e.y)

        self._syncing = True
        try:
            for other in (self.rooms_tree, self.areas_tree, self.rooms_all_tree, self.areas_all_tree):
                if other is not t:
                    other.selection_remove(*other.selection())
        finally:
            self._syncing = False

        if not item:
            if not ctrl and not shift:
                self._clear_selection()
            return "break"

        children = list(t.get_children(""))
        if ctrl:
            if item in t.selection():
                t.selection_remove(item)
            else:
                t.selection_add(item)
            self._tree_anchor[t] = item
        elif shift:
            anchor = self._tree_anchor.get(t, item)
            if anchor not in children:
                anchor = item
            i0 = children.index(anchor); i1 = children.index(item)
            lo, hi = (i0, i1) if i0 <= i1 else (i1, i0)
            t.selection_set(children[lo:hi+1])
        else:
            t.selection_set(item); self._tree_anchor[t] = item
        t.focus(item); t.see(item)
        self._select_ids(set(t.selection()), additive=False)
        return "break"

    def _on_tree_select(self, e):
        if self._rebuilding or self._syncing:
            return
        self._select_ids(set(e.widget.selection()), additive=False)

    def _on_tree_rclick(self, e):
        self._ctx_widget = e.widget
        try:
            self.ctx.tk_popup(e.x_root, e.y_root)
        finally:
            self.ctx.grab_release()

    def _on_canvas_rclick(self, e):
        self._ctx_widget = self.canvas
        try:
            self.ctx.tk_popup(e.x_root, e.y_root)
        finally:
            self.ctx.grab_release()

    def _ctx_delete(self):
        w = getattr(self, "_ctx_widget", None)
        if w in (self.rooms_tree, self.rooms_all_tree):
            self._remove_selected_rooms()
        elif w in (self.areas_tree, self.areas_all_tree):
            self._remove_selected_areas()
        elif w is self.canvas:
            if not self._sel_ids:
                return
            self._push_undo()
            self.state.remove_rooms(self._sel_ids)
            self.state.remove_areas(self._sel_ids)
            self._fill_all_tables(); self._clear_selection(); self._redraw(False)

    def _on_delete_key(self, _e):
        """Delete selected rooms or areas via keyboard.

        Levels are intentionally ignored here – they can only be removed
        through the dedicated UI button. The handler checks for selections in
        the work trees first regardless of focus, falling back to canvas
        selections. When editing an area, pressing Delete removes the selected
        vertex or edge if any, otherwise normal deletion logic applies.
        """
        focus = self.focus_get()
        if isinstance(focus, tk.Entry):
            return
        if self._edit_area_mode and (
            self._edit_area_sel_idx is not None or self._edit_area_sel_edge is not None
        ):
            self._edit_area_delete_selected()
            return
        if self.rooms_tree.selection():
            self._remove_selected_rooms()
            return
        if self.areas_tree.selection():
            self._remove_selected_areas()
            return
        if self._sel_ids:
            self._ctx_widget = self.canvas
            self._ctx_delete()

    def _on_backspace_key(self, _e):
        if isinstance(self.focus_get(), tk.Entry):
            return
        if self._add_room_mode:
            self._add_room_undo()
        elif self._edit_area_mode:
            self._edit_area_undo_fn()

    def _toggle_snap_key(self, _e):
        if isinstance(self.focus_get(), tk.Entry):
            return
        if self._add_room_mode or self._edit_area_mode:
            self._snap_var.set(not self._snap_var.get())

    def _toggle_ortho_key(self, _e):
        if isinstance(self.focus_get(), tk.Entry):
            return
        if self._add_room_mode or self._edit_area_mode:
            self._ortho_var.set(not self._ortho_var.get())

    def _snap_point(self, x, y):
        size = max(float(self._grid_size_var.get() or 1.0), 0.01)
        if self._grid_mode_var.get() == "grid":
            ox, oy = self._grid_origin
            x = ox + round((x - ox) / size) * size
            y = oy + round((y - oy) / size) * size
        return round(x, 2), round(y, 2)

    def _poly_area(self, pts):
        a = 0.0
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            a += x1 * y2 - x2 * y1
        return abs(a) * 0.5

    def _snap_poly(self, pts):
        snapped = [self._snap_point(x, y) for x, y in pts]
        uniq = {p for p in snapped}
        if len(uniq) < 3 or self._poly_area(snapped) < 1e-6:
            return list(pts)
        return snapped

    def _add_grid_controls(self, parent):
        fr = tk.Frame(parent); fr.pack(anchor="w", padx=4, pady=(4,0))
        tk.Label(fr, text="Режим").pack(side="left")
        combo = ttk.Combobox(fr, values=["default","grid"], textvariable=self._grid_mode_var, state="readonly", width=8)
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", self._apply_grid_mode)
        tk.Label(fr, text="шаг, м").pack(side="left", padx=(4,0))
        entry = tk.Entry(fr, textvariable=self._grid_size_var, width=6)
        entry.pack(side="left")
        entry.bind("<Return>", self._apply_grid_mode)
        entry.bind("<FocusOut>", self._apply_grid_mode)

    def _apply_grid_mode(self, _e=None):
        mode = self._grid_mode_var.get()
        try:
            size = float(self._grid_size_var.get())
        except Exception:
            size = 1.0
        if size <= 0:
            size = 1.0
        size = max(size, 0.01)
        self._grid_size_var.set(round(size, 2))
        if mode == "grid":
            items = []
            for r in self.state.work_rooms:
                rid = r.get("id")
                pts = self._grid_backup["rooms"].get(rid, r.get("outer_xy_m", []))
                items.append({"outer_xy_m": pts})
            for a in self.state.work_areas:
                aid = a.get("id")
                pts = self._grid_backup["areas"].get(aid, a.get("outer_xy_m", []))
                items.append({"outer_xy_m": pts})
            if items:
                xmin, ymin, xmax, ymax = bounds(items)
                self._grid_origin = (
                    round(xmin / size) * size,
                    round(ymin / size) * size,
                )
            else:
                self._grid_origin = (0.0, 0.0)

            for r in self.state.work_rooms:
                rid = r.get("id")
                if rid not in self._grid_backup["rooms"]:
                    self._grid_backup["rooms"][rid] = [tuple(p) for p in r.get("outer_xy_m", [])]
                base = self._grid_backup["rooms"][rid]
                r["outer_xy_m"] = self._snap_poly(base)
            for a in self.state.work_areas:
                aid = a.get("id")
                if aid not in self._grid_backup["areas"]:
                    self._grid_backup["areas"][aid] = [tuple(p) for p in a.get("outer_xy_m", [])]
                base = self._grid_backup["areas"][aid]
                a["outer_xy_m"] = self._snap_poly(base)
        else:
            self._grid_origin = (0.0, 0.0)
            for r in self.state.work_rooms:
                rid = r.get("id")
                if rid in self._grid_backup["rooms"]:
                    r["outer_xy_m"] = [tuple(p) for p in self._grid_backup["rooms"][rid]]
            for a in self.state.work_areas:
                aid = a.get("id")
                if aid in self._grid_backup["areas"]:
                    a["outer_xy_m"] = [tuple(p) for p in self._grid_backup["areas"][aid]]
            self._grid_backup = {"rooms": {}, "areas": {}}
        self._redraw(False)

    def _draw_grid(self):
        for cid in self._grid_items:
            self.canvas.delete(cid)
        self._grid_items = []
        if self._grid_mode_var.get() != "grid":
            return
        size = max(float(self._grid_size_var.get() or 1.0), 0.01)
        w = self.canvas.winfo_width(); h = self.canvas.winfo_height()
        x0, y0 = self._to_world(0, 0)
        x1, y1 = self._to_world(w, h)
        xmin, xmax = sorted([x0, x1])
        ymin, ymax = sorted([y0, y1])
        ox, oy = self._grid_origin
        ix0 = math.floor((xmin - ox) / size) - 1
        ix1 = math.floor((xmax - ox) / size) + 1
        iy0 = math.floor((ymin - oy) / size) - 1
        iy1 = math.floor((ymax - oy) / size) + 1

        cols = max(0, ix1 - ix0 + 1)
        rows = max(0, iy1 - iy0 + 1)
        if not cols or not rows:
            return

        total = cols * rows
        stride_x = 1
        stride_y = 1
        if total > MAX_GRID_POINTS:
            target = math.sqrt(MAX_GRID_POINTS)
            stride_x = max(1, math.ceil(cols / target))
            stride_y = max(1, math.ceil(rows / target))

        xs = list(range(ix0, ix1 + 1, stride_x))
        ys = list(range(iy0, iy1 + 1, stride_y))
        len_x = len(xs)
        len_y = len(ys)
        if xs and xs[-1] != ix1 and (len_x + 1) * len_y <= MAX_GRID_POINTS:
            xs.append(ix1)
            len_x += 1
        if ys and ys[-1] != iy1 and len_x * (len_y + 1) <= MAX_GRID_POINTS:
            ys.append(iy1)
            len_y += 1

        scale = self._scale
        ox_screen = self._ox
        oy_screen = self._oy

        grid_xmin = ox + ix0 * size
        grid_xmax = ox + ix1 * size
        grid_ymin = oy + iy0 * size
        grid_ymax = oy + iy1 * size

        sx_min = grid_xmin * scale + ox_screen
        sx_max = grid_xmax * scale + ox_screen
        sy_min = -grid_ymin * scale + oy_screen
        sy_max = -grid_ymax * scale + oy_screen

        for ix in xs:
            gx = ox + ix * size
            sx = gx * scale + ox_screen
            self._grid_items.append(
                self.canvas.create_line(sx, sy_min, sx, sy_max, fill="#d0d0d0")
            )

        for iy in ys:
            gy = oy + iy * size
            sy = -gy * scale + oy_screen
            self._grid_items.append(
                self.canvas.create_line(sx_min, sy, sx_max, sy, fill="#d0d0d0")
            )

    def _on_escape_key(self, _e):
        if self._add_room_mode:
            self._add_room_cancel()
        elif self._edit_area_mode:
            self._edit_area_cancel()
        else:
            self._clear_selection()

    def _try_edit_combo(self, e, tree):
        region = tree.identify("region", e.x, e.y)
        if region != "cell":
            return
        col_id = tree.identify_column(e.x)
        if not col_id or not col_id.startswith("#"):
            return
        idx = int(col_id[1:]) - 1
        cols = list(tree["columns"])
        if idx < 0 or idx >= len(cols):
            return
        colname = cols[idx]
        if tree not in (self.rooms_tree, self.areas_tree):
            return
        if colname not in ("BESS_level","BESS_Upper_level"):
            return
        iid = tree.identify_row(e.y)
        if not iid:
            return

        bbox = tree.bbox(iid, column=col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        rx = tree.winfo_rootx() + x; ry = tree.winfo_rooty() + y

        rid = str(iid)
        if tree is self.rooms_tree:
            obj = next((r for r in self.state.work_rooms if str(r.get("id","")) == rid), None)
        else:
            obj = next((a for a in self.state.work_areas if str(a.get("id","")) == rid), None)
        if not obj:
            return

        prs = obj.get("params") or {}
        param_key = ALIAS_TO_PARAM.get(colname, colname)
        cur = prs.get(param_key, "")
        values = self.state.levels_sorted_names(self.state.work_levels)
        if not values:
            return

        self._destroy_edit_popup()
        self._edit_popup = tk.Toplevel(self)
        self._edit_popup.wm_overrideredirect(True)
        self._edit_popup.geometry("+%d+%d" % (rx, ry))
        frame = tk.Frame(self._edit_popup, bd=1, relief="solid"); frame.pack(fill="both", expand=True)
        var = tk.StringVar(value=(cur if cur in values else values[0]))
        cb = ttk.Combobox(frame, values=values, textvariable=var, state="readonly", width=max(12, int(w/8)))
        cb.pack(fill="x", padx=2, pady=2); cb.focus_set()

        def commit():
            newv = var.get()
            prs = obj.get("params") or {}
            prs[param_key] = newv
            obj["params"] = prs
            if tree is self.rooms_tree and param_key == "BESS_level":
                self.state.ensure_room_upper(obj)
            self._fill_all_tables(); self._redraw(False)
            try:
                tree.selection_set(rid); tree.see(rid)
            except Exception:
                pass
            self._destroy_edit_popup()

        cb.bind("<<ComboboxSelected>>", lambda _e: commit())
        cb.bind("<Return>", lambda _e: commit())
        cb.bind("<Escape>", lambda _e: self._destroy_edit_popup())

    def _destroy_edit_popup(self):
        if self._edit_popup:
            try:
                self._edit_popup.destroy()
            except Exception:
                pass
            self._edit_popup = None

    # ---------- canvas ----------
    def _to_screen(self, x, y):
        return (x*self._scale + self._ox, -y*self._scale + self._oy)

    def _from_screen(self, X, Y):
        return ((X - self._ox)/self._scale, -(Y - self._oy)/self._scale)

    def _to_world(self, X, Y):
        """Convert canvas coordinates back into world units.

        Historically the code used a `_to_world` helper when computing
        grid points, but only `_from_screen` was implemented which performs
        the same conversion.  As soon as the grid mode was enabled the
        `_draw_grid` method attempted to call the missing helper resulting in
        an `AttributeError`.  The redraw routine stops at that point and the
        canvas is cleared, which looked like the polygons disappearing.  By
        providing the dedicated helper we keep the existing call sites intact
        and ensure the conversion matches the rest of the code.
        """

        return self._from_screen(X, Y)

    def _zoom_at(self, X, Y, factor):
        wx, wy = self._from_screen(X, Y)
        new_scale = max(1e-9, min(self._scale * factor, 1e9))
        self._scale = new_scale
        self._ox = X - wx * new_scale
        self._oy = Y + wy * new_scale
        self._redraw(False)

    def _on_mousewheel(self, e):
        k = 1.1 if e.delta > 0 else (1.0/1.1)
        self._zoom_at(e.x, e.y, k)

    def _on_mousewheel_linux(self, e, direction):
        class _E: pass
        ev = _E(); ev.x = e.x; ev.y = e.y; ev.state = e.state; ev.delta = 120 if direction > 0 else -120
        self._on_mousewheel(ev)

    def _on_pan_start(self, e):
        self._pan_last = (e.x, e.y)

    def _on_pan_move(self, e):
        dx = e.x - self._pan_last[0]; dy = e.y - self._pan_last[1]
        self._ox += dx; self._oy += dy; self._pan_last = (e.x, e.y); self._redraw(False)

    def _on_pan_end(self, _e):
        self._pan_last = None

    def _id_under_point(self, x, y):
        pixhits = [i for i in self.canvas.find_overlapping(x, y, x, y) if "room" in self.canvas.gettags(i)]
        if pixhits:
            rid, kind = self._canvas2rid.get(pixhits[-1], (None, None))
            if kind == "room":
                return rid, "room"
        hits = [i for i in self.canvas.find_overlapping(x-TOL_ROOM_OUTLINE_PX, y-TOL_ROOM_OUTLINE_PX,
                                                        x+TOL_ROOM_OUTLINE_PX, y+TOL_ROOM_OUTLINE_PX)
                if "room" in self.canvas.gettags(i)]
        if hits:
            rid, kind = self._canvas2rid.get(hits[-1], (None, None))
            if kind == "room":
                return rid, "room"
        hits = [i for i in self.canvas.find_overlapping(x-TOL_AREA_PICK_PX, y-TOL_AREA_PICK_PX,
                                                        x+TOL_AREA_PICK_PX, y+TOL_AREA_PICK_PX)
                if "area" in self.canvas.gettags(i)]
        if hits:
            rid, kind = self._canvas2rid.get(hits[-1], (None, None))
            if kind == "area":
                return rid, "area"
        return None, None

    def _on_lmb_down(self, e):
        if self._add_room_mode:
            self._drag_start = None
            self._add_room_click(e)
            return
        if self._edit_area_mode:
            self._drag_start = None
            self._edit_area_click(e)
            return
        self._drag_start = (e.x, e.y)

    def _on_lmb_drag(self, e):
        if self._add_room_mode or self._edit_area_mode:
            return
        if not self._drag_start:
            return
        x0, y0 = self._drag_start; x1, y1 = e.x, e.y
        if getattr(self, "_drag_rect", None) is None:
            self._drag_rect = self.canvas.create_rectangle(x0, y0, x1, y1, outline="#0078D7", dash=(4,2))
        else:
            self.canvas.coords(self._drag_rect, x0, y0, x1, y1)

    def _on_lmb_up(self, e):
        if self._add_room_mode or self._edit_area_mode:
            return
        if getattr(self, "_drag_rect", None) is not None:
            x0, y0 = self._drag_start; x1, y1 = e.x, e.y
            if x0 > x1: x0, x1 = x1, x0
            if y0 > y1: y0, y1 = y1, y0
            additive = (e.state & 0x0004) != 0
            ids = set()
            for item in self.canvas.find_overlapping(x0, y0, x1, y1):
                if "geom" in self.canvas.gettags(item):
                    rid_kind = self._canvas2rid.get(item)
                    if rid_kind:
                        rid, _ = rid_kind; ids.add(rid)
            self.canvas.delete(self._drag_rect); self._drag_rect = None; self._drag_start = None
            if ids: self._select_ids(ids, additive=additive)
            else:
                if not additive: self._clear_selection()
            return
        rid, _ = self._id_under_point(e.x, e.y)
        additive = (e.state & 0x0004) != 0
        if rid: self._select_ids([rid], additive=additive)
        else:
            if not additive: self._clear_selection()
        self._drag_start = None

    def _redraw(self, force_fit=False):
        level = self._current_level()
        rooms = [r for r in self.state.work_rooms if (r.get("params",{}).get("BESS_level","") == level)]
        areas = [a for a in self.state.work_areas if (a.get("params",{}).get("BESS_level","") == level)]
        c = self.canvas

        if force_fit:
            minx, miny, maxx, maxy = bounds(rooms+areas)
            w = max(maxx-minx, 1e-9); h = max(maxy-miny, 1e-9)
            cw = max(c.winfo_width(), 100); ch = max(c.winfo_height(), 100)
            m = 40; sx = (cw - m)/w; sy = (ch - m)/h
            self._scale = max(1e-9, min(sx, sy))
            self._ox = (-minx*self._scale) + m/2.0
            self._oy = ( maxy*self._scale) + m/2.0
            self._fit_done = True

        c.delete("all")
        self._id2canvas.clear(); self._canvas2rid.clear()
        self._orig_fill.clear(); self._orig_outline.clear()

        self._draw_grid()

        palette = ("#4cc9f0","#3f37c9","#4895ef","#43aa8b","#90be6d","#577590","#f8961e","#264653","#2a9d8f")
        for i, r in enumerate(rooms):
            col = palette[i % len(palette)]
            flat = []
            for x, y in r["outer_xy_m"]:
                X, Y = self._to_screen(x, y); flat += [X, Y]
            pid = c.create_polygon(flat, outline="#333", fill=col, width=2, tags=("geom","room", str(r["id"])))
            for h in r.get("inner_loops_xy_m", []):
                flat_h = []
                for x, y in h:
                    X, Y = self._to_screen(x, y); flat_h += [X, Y]
                c.create_polygon(flat_h, outline="#333", fill="", width=1, tags=("geom","room_hole"))
            rid = str(r["id"])
            self._id2canvas[rid] = ("room", pid); self._canvas2rid[pid] = (rid, "room")
            self._orig_fill[rid] = col; self._orig_outline[rid] = ("#333", 2)

        for a in areas:
            flat = []
            for x, y in a["outer_xy_m"]:
                X, Y = self._to_screen(x, y); flat += [X, Y]
            pid = c.create_polygon(flat, outline="#D22", fill="", width=4, tags=("geom","area", str(a["id"])))
            rid = str(a["id"])
            self._id2canvas[rid] = ("area", pid); self._canvas2rid[pid] = (rid, "area")
            self._orig_outline[rid] = ("#D22", 4); self._orig_fill[rid] = ""

        for r in rooms:
            cx, cy = centroid_xy(r["outer_xy_m"]); X, Y = self._to_screen(cx, cy)
            c.create_text(X+6, Y+6, text=r.get("name",""), anchor="nw", font=("Arial",9), fill="#000")

        for rid in list(self._sel_ids):
            self._set_selected(rid, True)

        if self._add_room_pts:
            self._draw_temp_poly()
        if self._edit_area_pts:
            self._draw_edit_area_poly()

if __name__ == "__main__":
    App().mainloop()
