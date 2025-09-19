#! python3
# -*- coding: utf-8 -*-
"""
REVIT_DATA_EXPORT – CPython3 + pyRevit (WinForms UI)

Главное окно:
- Чекбоксы: [ ] Помещения   [ ] Остекление   [ ] Двери
- Кнопки:   [Выбрать типы остекления]  [Выбрать типы дверей]
- [Экспортировать]

Экспорт:
- Помещения: контуры (тесселяция) + все параметры
- Остекление: Windows, Curtain Panels, Curtain Walls – по выбранным типам
- Двери: Doors – по выбранным типам
"""

from pyrevit import revit, DB, script
from Autodesk.Revit.UI import TaskDialog
from System.Windows.Forms import (
    Form, DataGridView, DataGridViewCheckBoxColumn, DataGridViewTextBoxColumn,
    Button, FlowLayoutPanel, DockStyle, SaveFileDialog, DialogResult, FormStartPosition,
    FlowDirection, DataGridViewAutoSizeColumnsMode, Label, CheckBox, TableLayoutPanel,
    ColumnStyle, SizeType
)
from System.Drawing import Size, Color, ContentAlignment
import json
import os
from math import sqrt
from datetime import datetime

doc = revit.doc
logger = script.get_logger()

# ---------------- Constants ----------------
FT_TO_M = 0.3048
FT2_TO_M2 = FT_TO_M * FT_TO_M
TOL_PT_FT = 1e-4
TOL_Z_FT  = 1e-3
DECIMATE_GEOM = True
DECIM_EPS_FT  = 0.02
ROUND_COORDS  = True
ROUND_M_DEC   = 3
ROUND_FT_DEC  = 4

# ---------------- Math / Transform helpers ----------------
def _add(p, v): 
    return DB.XYZ(p.X + v.X, p.Y + v.Y, p.Z + v.Z)

def _sub(a, b): 
    return DB.XYZ(a.X - b.X, a.Y - b.Y, a.Z - b.Z)

def _mul(v, s): 
    return DB.XYZ(v.X * s, v.Y * s, v.Z * s)

def _normalize(v):
    try: 
        return v.Normalize()
    except: 
        return v

def _cross(a, b):
    try: 
        return a.CrossProduct(b)
    except: 
        return None

def _of_point(T, p):
    try: 
        return T.OfPoint(p) if T else p
    except: 
        return p

def _of_vector(T, v):
    try: 
        return T.OfVector(v) if T else v
    except: 
        return v

def _roundf(x, dec): 
    return round(x, dec) if x is not None else None

def _xy_ft_from_pts(pts):
    if ROUND_COORDS:
        return [[_roundf(p.X, ROUND_FT_DEC), _roundf(p.Y, ROUND_FT_DEC)] for p in pts]
    return [[p.X, p.Y] for p in pts]

def _xy_m_from_pts(pts):
    if ROUND_COORDS:
        return [[_roundf(p.X * FT_TO_M, ROUND_M_DEC), _roundf(p.Y * FT_TO_M, ROUND_M_DEC)] for p in pts]
    return [[p.X * FT_TO_M, p.Y * FT_TO_M] for p in pts]

# ---------------- Params ----------------
def _storage_name(st):
    try:
        if st == DB.StorageType.String: return "String"
        if st == DB.StorageType.Integer: return "Integer"
        if st == DB.StorageType.Double: return "Double"
        if st == DB.StorageType.ElementId: return "ElementId"
    except: 
        pass
    return "None"

def _param_record(p):
    try:
        d = p.Definition
        name = d.Name if d else None
        if not name: 
            return None
        st = p.StorageType
        vs = p.AsValueString()
        raw = None
        
        if st == DB.StorageType.String:
            raw = p.AsString()
            vs = raw if vs is None else vs
        elif st == DB.StorageType.Integer:
            raw = p.AsInteger()
            vs = str(raw) if vs is None else vs
        elif st == DB.StorageType.Double:
            raw = p.AsDouble()
            vs = "" if vs is None else vs
        elif st == DB.StorageType.ElementId:
            eid = p.AsElementId()
            raw = eid.IntegerValue if eid else None
            vs = (str(raw) if raw is not None else "") if vs is None else vs
        else:
            vs = "" if vs is None else vs
        
        return name, {
            "display": vs,
            "raw_internal": raw,
            "id": getattr(p, "Id", None).IntegerValue if getattr(p, "Id", None) else None,
            "is_shared": getattr(p, "IsShared", False),
            "guid": str(getattr(p, "GUID", None)) if getattr(p, "IsShared", False) else None,
            "storage_type": _storage_name(st)
        }
    except:
        return None

def _collect_params_block(el):
    out = {}
    try:
        for p in el.Parameters:
            kv = _param_record(p)
            if kv: 
                out[kv[0]] = kv[1]
    except: 
        pass
    return out

def _collect_all_params(el, doc_):
    res = {"instance": {}, "type": {}}
    try: 
        res["instance"] = _collect_params_block(el)
    except: 
        pass
    try:
        tid = el.GetTypeId()
        if tid and tid.IntegerValue != -1:
            t_el = doc_.GetElement(tid)
            if t_el: 
                res["type"] = _collect_params_block(t_el)
    except: 
        pass
    return res

# ---------------- Doc sources ----------------
def _user_model_path(document):
    try:
        mp = document.GetWorksharingCentralModelPath()
    except: 
        mp = None
    if not mp:
        try: 
            mp = document.GetModelPath()
        except: 
            mp = None
    if mp:
        try: 
            return DB.ModelPathUtils.ConvertModelPathToUserVisiblePath(mp)
        except: 
            pass
    return document.PathName or ""

def _docs_sources(document):
    src = [(document, None, DB.Transform.Identity)]
    for li in DB.FilteredElementCollector(document).OfClass(DB.RevitLinkInstance):
        ldoc = li.GetLinkDocument()
        if ldoc: 
            src.append((ldoc, li, li.GetTransform()))
    return src

def _all_levels_map(document):
    m = {}
    for lv in DB.FilteredElementCollector(document).OfClass(DB.Level):
        elev = float(lv.Elevation)
        m[lv.Id.IntegerValue] = {
            "name": lv.Name,
            "elevation_ft": elev,
            "elevation_m": elev * FT_TO_M
        }
    return m

# ---------------- Rooms (geometry) ----------------
def _signed_area_xy_ft(pts):
    a = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i].X, pts[i].Y
        x2, y2 = pts[i+1].X, pts[i+1].Y
        a += x1 * y2 - x2 * y1
    return 0.5 * a

def _close_ring_if_needed(pts):
    if len(pts) >= 2 and pts[0].DistanceTo(pts[-1]) > TOL_PT_FT:
        pts.append(pts[0])
    return pts

def _dedup_pts(pts):
    out = []
    last = None
    for p in pts:
        if last is None or p.DistanceTo(last) > TOL_PT_FT:
            out.append(p)
            last = p
    return out

def _dist_point_seg_xy(p, a, b):
    ax, ay, bx, by, px, py = a.X, a.Y, b.X, b.Y, p.X, p.Y
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    c1 = vx * wx + vy * wy
    c2 = vx * vx + vy * vy
    t = 0.0 if c2 <= 1e-12 else max(0.0, min(1.0, c1/c2))
    qx, qy = ax + t * vx, ay + t * vy
    dx, dy = px - qx, py - qy
    return sqrt(dx * dx + dy * dy)

def _rdp_xy(pts, eps_ft):
    if not DECIMATE_GEOM or len(pts) < 5: 
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    
    while stack:
        i, j = stack.pop()
        a, b = pts[i], pts[j]
        maxd = -1.0
        idx = None
        for k in range(i + 1, j):
            d = _dist_point_seg_xy(pts[k], a, b)
            if d > maxd: 
                maxd, idx = d, k
        if maxd > eps_ft and idx is not None:
            keep[idx] = True
            stack.append((i, idx))
            stack.append((idx, j))
    
    return [p for i, p in enumerate(pts) if keep[i]]

def _ring_from_segments(segs, T=None):
    pts = []
    for s in segs:
        for pt in s.GetCurve().Tessellate():
            hp = _of_point(T, pt)
            if not pts or hp.DistanceTo(pts[-1]) > TOL_PT_FT:
                pts.append(hp)
    pts = _close_ring_if_needed(_dedup_pts(pts))
    return _rdp_xy(pts, DECIM_EPS_FT) if DECIMATE_GEOM else pts

def _loops_from_boundary(seg_lists, T=None):
    loops = []
    if not seg_lists: 
        return None, []
    
    for segs in seg_lists:
        p = _ring_from_segments(segs, T)
        if len(p) >= 4: 
            loops.append(p)
    
    if not loops: 
        return None, []
    
    areas = [abs(_signed_area_xy_ft(r)) for r in loops]
    outer = loops[areas.index(max(areas))]
    inn = [r for r in loops if r is not outer]
    return outer, inn

def _room_name(r):
    try:
        p = r.get_Parameter(DB.BuiltInParameter.ROOM_NAME)
        nm = p.AsString() if p else None
        return nm or getattr(r, "Name", None)
    except: 
        return getattr(r, "Name", None)

def _room_number(r):
    try:
        p = r.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER)
        s = p.AsString() if p else None
        return s or getattr(r, "Number", None)
    except: 
        return getattr(r, "Number", None)

def _collect_rooms(document, boundary_location, levels_map):
    out = []
    opts = DB.SpatialElementBoundaryOptions()
    opts.SpatialElementBoundaryLocation = boundary_location
    fec = DB.FilteredElementCollector(document).OfCategory(DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType()
    
    for r in fec:
        if not isinstance(r, DB.SpatialElement): 
            continue
        
        outer, inners = _loops_from_boundary(r.GetBoundarySegments(opts))
        if not outer: 
            continue
        
        area_ft2 = float(getattr(r, "Area", 0.0)) if hasattr(r, "Area") else None
        
        loops = {
            "outer": {
                "xy_ft": _xy_ft_from_pts(outer),
                "xy_m": _xy_m_from_pts(outer),
                "signed_area_ft2": _signed_area_xy_ft(outer)
            },
            "inners": []
        }
        
        for inn in inners:
            loops["inners"].append({
                "xy_ft": _xy_ft_from_pts(inn),
                "xy_m": _xy_m_from_pts(inn),
                "signed_area_ft2": _signed_area_xy_ft(inn)
            })
        
        level_id = r.LevelId.IntegerValue if getattr(r, "LevelId", None) else None
        level_name = levels_map.get(level_id, {}).get("name", "")
        
        rec = {
            "id": r.Id.IntegerValue,
            "unique_id": r.UniqueId,
            "number": _room_number(r),
            "name": _room_name(r),
            "level_id": level_id,
            "level": level_name,
            "loops": loops,
            "poly_area_ft2": (loops["outer"]["signed_area_ft2"] - 
                             sum(abs(h["signed_area_ft2"]) for h in loops["inners"])),
            "area_ft2_param": area_ft2,
            "area_m2_param": area_ft2 * FT2_TO_M2 if area_ft2 is not None else None,
            "params": _collect_all_params(r, document),
            "outer_xy_m": loops["outer"]["xy_m"],
            "outer_xy_ft": loops["outer"]["xy_ft"],
            "inner_loops_xy_m": [h["xy_m"] for h in loops["inners"]],
            "inner_loops_xy_ft": [h["xy_ft"] for h in loops["inners"]]
        }
        out.append(rec)
    
    return out

# ---------------- BBox + oriented footprint ----------------
def _bb_center(el, T=None):
    bb = el.get_BoundingBox(None)
    if not bb: 
        return None
    pmin = _of_point(T, bb.Min)
    pmax = _of_point(T, bb.Max)
    return DB.XYZ((pmin.X + pmax.X) * 0.5, (pmin.Y + pmax.Y) * 0.5, (pmin.Z + pmax.Z) * 0.5)

def _bb_size(el, T=None):
    bb = el.get_BoundingBox(None)
    if not bb: 
        return None
    pmin = _of_point(T, bb.Min)
    pmax = _of_point(T, bb.Max)
    return [abs(pmax.X - pmin.X), abs(pmax.Y - pmin.Y), abs(pmax.Z - pmin.Z)]

def _bbox_record(el, T=None):
    bb = el.get_BoundingBox(None)
    if not bb: 
        return None
    pmin = _of_point(T, bb.Min)
    pmax = _of_point(T, bb.Max)
    c = DB.XYZ((pmin.X + pmax.X) * 0.5, (pmin.Y + pmax.Y) * 0.5, (pmin.Z + pmax.Z) * 0.5)
    
    return {
        "min_ft": [_roundf(pmin.X, 4), _roundf(pmin.Y, 4), _roundf(pmin.Z, 4)],
        "max_ft": [_roundf(pmax.X, 4), _roundf(pmax.Y, 4), _roundf(pmax.Z, 4)],
        "min_m": [_roundf(pmin.X * FT_TO_M, 3), _roundf(pmin.Y * FT_TO_M, 3), _roundf(pmin.Z * FT_TO_M, 3)],
        "max_m": [_roundf(pmax.X * FT_TO_M, 3), _roundf(pmax.Y * FT_TO_M, 3), _roundf(pmax.Z * FT_TO_M, 3)],
        "center_ft": [_roundf(c.X, 4), _roundf(c.Y, 4), _roundf(c.Z, 4)],
        "center_m": [_roundf(c.X * FT_TO_M, 3), _roundf(c.Y * FT_TO_M, 3), _roundf(c.Z * FT_TO_M, 3)]
    }

def _rect_footprint(center, x_dir, y_dir, x_len_ft, y_len_ft):
    if not (center and x_dir and y_dir and x_len_ft and y_len_ft): 
        return None
    x = _normalize(x_dir)
    y = _normalize(y_dir)
    hx = _mul(x, 0.5 * x_len_ft)
    hy = _mul(y, 0.5 * y_len_ft)
    p1 = _add(_add(center, hx), hy)
    p2 = _add(_sub(center, hx), hy)
    p3 = _sub(_sub(center, hx), hy)
    p4 = _sub(_add(center, hx), hy)
    return [p1, p2, p3, p4, p1]

def _footprint_record(ring):
    if not ring: 
        return None
    return {"xy_ft": _xy_ft_from_pts(ring), "xy_m": _xy_m_from_pts(ring)}

def _element_typename(el, sdoc):
    try:
        if isinstance(el, DB.Wall):
            wt = sdoc.GetElement(el.GetTypeId())
            return wt.Name if wt else ""
        if isinstance(el, DB.FamilyInstance):
            sym = el.Symbol
            if sym:
                p = sym.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
                return p.AsString() if p else getattr(sym, "Name", "")
    except: 
        pass
    return ""

# ---------------- Type tables ----------------
def _flatten_params_simple(raw_dict):
    if not isinstance(raw_dict, dict): 
        return "{}"
    try:
        d = raw_dict.get("type", {}) if "type" in raw_dict else raw_dict
        out = {}
        for k, v in d.items():
            if isinstance(v, dict):
                out[k] = v.get("display", v.get("raw_internal", ""))
            else:
                out[k] = v
        return json.dumps(out, ensure_ascii=False)
    except:
        return "{}"

def _gather_glazing_types():
    rows = []
    seen = set()
    
    for sdoc, _, _ in _docs_sources(doc):
        # Windows
        for fs in DB.FilteredElementCollector(sdoc).OfClass(DB.FamilySymbol).OfCategory(DB.BuiltInCategory.OST_Windows):
            tname = fs.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
            tname = tname.AsString() if tname else getattr(fs, 'Name', '')
            key = ("Windows", fs.Id.IntegerValue)
            if key in seen: 
                continue
            rows.append({
                "cat": "Windows",
                "type_id": fs.Id.IntegerValue,
                "type_name": tname,
                "family": getattr(getattr(fs, 'Family', None), 'Name', ""),
                "params_json": _flatten_params_simple(_collect_params_block(fs))
            })
            seen.add(key)
        
        # Curtain Panels
        for fs in DB.FilteredElementCollector(sdoc).OfClass(DB.FamilySymbol).OfCategory(DB.BuiltInCategory.OST_CurtainWallPanels):
            tname = fs.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
            tname = tname.AsString() if tname else getattr(fs, 'Name', '')
            key = ("Curtain Panels", fs.Id.IntegerValue)
            if key in seen: 
                continue
            rows.append({
                "cat": "Curtain Panels",
                "type_id": fs.Id.IntegerValue,
                "type_name": tname,
                "family": getattr(getattr(fs, 'Family', None), 'Name', ""),
                "params_json": _flatten_params_simple(_collect_params_block(fs))
            })
            seen.add(key)
        
        # Curtain Walls
        for wt in DB.FilteredElementCollector(sdoc).OfClass(DB.WallType):
            try:
                if getattr(wt, "Kind", None) == DB.WallKind.Curtain:
                    key = ("Curtain Walls", wt.Id.IntegerValue)
                    if key in seen: 
                        continue
                    rows.append({
                        "cat": "Curtain Walls",
                        "type_id": wt.Id.IntegerValue,
                        "type_name": wt.Name,
                        "family": "WallType",
                        "params_json": _flatten_params_simple(_collect_params_block(wt))
                    })
                    seen.add(key)
            except: 
                pass
    
    rows.sort(key=lambda r: (r["cat"], r["type_name"]))
    return rows

def _gather_door_types():
    rows = []
    seen = set()
    
    for sdoc, _, _ in _docs_sources(doc):
        for fs in DB.FilteredElementCollector(sdoc).OfClass(DB.FamilySymbol).OfCategory(DB.BuiltInCategory.OST_Doors):
            tname = fs.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
            tname = tname.AsString() if tname else getattr(fs, 'Name', '')
            key = ("Doors", fs.Id.IntegerValue)
            if key in seen: 
                continue
            rows.append({
                "cat": "Doors",
                "type_id": fs.Id.IntegerValue,
                "type_name": tname,
                "family": getattr(getattr(fs, 'Family', None), 'Name', ""),
                "params_json": _flatten_params_simple(_collect_params_block(fs))
            })
            seen.add(key)
    
    rows.sort(key=lambda r: (r["cat"], r["type_name"]))
    return rows

# ---------------- Type Picker Form ----------------
class TypePickerForm(Form):
    def __init__(self, rows, title):
        Form.__init__(self)
        self.Text = title
        self.StartPosition = FormStartPosition.CenterScreen
        self.ClientSize = Size(1100, 600)

        self.grid = DataGridView()
        self.grid.Dock = DockStyle.Fill
        self.grid.AllowUserToAddRows = False
        self.grid.AllowUserToDeleteRows = False
        self.grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.AllCells
        self.grid.RowHeadersVisible = False

        self.grid.Columns.Add(DataGridViewCheckBoxColumn(HeaderText="Select"))
        self.grid.Columns.Add(DataGridViewTextBoxColumn(HeaderText="Category"))
        self.grid.Columns.Add(DataGridViewTextBoxColumn(HeaderText="Type"))
        self.grid.Columns.Add(DataGridViewTextBoxColumn(HeaderText="Family"))
        col_params = DataGridViewTextBoxColumn()
        col_params.HeaderText = "TypeParamsJson"
        col_params.Width = 600
        self.grid.Columns.Add(col_params)

        for r in rows:
            self.grid.Rows.Add(False, r["cat"], r["type_name"], r.get("family", ""), r.get("params_json", ""))

        panel = FlowLayoutPanel()
        panel.FlowDirection = FlowDirection.LeftToRight
        panel.Dock = DockStyle.Bottom
        panel.Height = 48
        
        btn_all = Button()
        btn_all.Text = "Select All"
        btn_all.Width = 100
        btn_all.Click += self._select_all
        
        btn_clear = Button()
        btn_clear.Text = "Clear"
        btn_clear.Width = 100
        btn_clear.Click += self._clear_all
        
        btn_ok = Button()
        btn_ok.Text = "Finish"
        btn_ok.Width = 120
        btn_ok.Click += self._ok
        
        btn_cancel = Button()
        btn_cancel.Text = "Cancel"
        btn_cancel.Width = 100
        btn_cancel.Click += self._cancel
        
        panel.Controls.Add(btn_all)
        panel.Controls.Add(btn_clear)
        panel.Controls.Add(btn_ok)
        panel.Controls.Add(btn_cancel)

        self.Controls.Add(self.grid)
        self.Controls.Add(panel)

        self.selected_ids = {}
        self._row_type_ids = [r["type_id"] for r in rows]
        self._row_cats = [r["cat"] for r in rows]

    def _select_all(self, sender, args):
        for i in range(self.grid.Rows.Count):
            self.grid.Rows[i].Cells[0].Value = True

    def _clear_all(self, sender, args):
        for i in range(self.grid.Rows.Count):
            self.grid.Rows[i].Cells[0].Value = False

    def _ok(self, sender, args):
        out = {}
        for i in range(self.grid.Rows.Count):
            if bool(self.grid.Rows[i].Cells[0].Value):
                cat = str(self.grid.Rows[i].Cells[1].Value or self._row_cats[i])
                tid = int(self._row_type_ids[i])
                out.setdefault(cat, set()).add(tid)
        self.selected_ids = out
        self.DialogResult = DialogResult.OK
        self.Close()

    def _cancel(self, sender, args):
        self.DialogResult = DialogResult.Cancel
        self.Close()

# ---------------- Main Form ----------------
class MainExportForm(Form):
    def __init__(self):
        Form.__init__(self)
        self.Text = "REVIT_DATA_EXPORT"
        self.StartPosition = FormStartPosition.CenterScreen
        self.ClientSize = Size(540, 180)

        self.levels_map = _all_levels_map(doc)
        self.sel_glazing = {}
        self.sel_doors = {}

        grid = TableLayoutPanel()
        grid.Dock = DockStyle.Fill
        grid.ColumnCount = 3
        grid.RowCount = 4
        grid.ColumnStyles.Add(ColumnStyle(SizeType.Absolute, 45))
        grid.ColumnStyles.Add(ColumnStyle(SizeType.Absolute, 250))
        grid.ColumnStyles.Add(ColumnStyle(SizeType.Absolute, 220))
        self.Controls.Add(grid)

        self.cb_rooms = CheckBox(Text="Помещения")
        self.cb_rooms.Checked = True
        self.cb_glaz = CheckBox(Text="Остекление")
        self.cb_doors = CheckBox(Text="Двери")
        grid.Controls.Add(self.cb_rooms, 0, 0)
        grid.Controls.Add(self.cb_glaz, 0, 1)
        grid.Controls.Add(self.cb_doors, 0, 2)

        self.btn_glaz = Button(Text="Выбрать типы остекления")
        self.btn_glaz.Width = 200
        self.btn_glaz.Click += self._pick_glazing
        self.lbl_glaz = Label(Text="✖", ForeColor=Color.Red, AutoSize=True, TextAlign=ContentAlignment.MiddleLeft)
        grid.Controls.Add(self.btn_glaz, 1, 1)
        grid.Controls.Add(self.lbl_glaz, 2, 1)

        self.btn_doors = Button(Text="Выбрать типы дверей")
        self.btn_doors.Width = 200
        self.btn_doors.Click += self._pick_doors
        self.lbl_doors = Label(Text="✖", ForeColor=Color.Red, AutoSize=True, TextAlign=ContentAlignment.MiddleLeft)
        grid.Controls.Add(self.btn_doors, 1, 2)
        grid.Controls.Add(self.lbl_doors, 2, 2)

        self.btn_export = Button(Text="Экспортировать")
        self.btn_export.Width = 180
        self.btn_export.Click += self._do_export
        grid.Controls.Add(self.btn_export, 1, 3)

    def _pick_glazing(self, sender, args):
        rows = _gather_glazing_types()
        dlg = TypePickerForm(rows, "Выбор типов остекления")
        if dlg.ShowDialog() == DialogResult.OK:
            self.sel_glazing = dlg.selected_ids or {}
            has_any = any(len(s) > 0 for s in self.sel_glazing.values())
            self.lbl_glaz.Text = "✔" if has_any else "✖"
            self.lbl_glaz.ForeColor = Color.Green if has_any else Color.Red

    def _pick_doors(self, sender, args):
        rows = _gather_door_types()
        dlg = TypePickerForm(rows, "Выбор типов дверей")
        if dlg.ShowDialog() == DialogResult.OK:
            self.sel_doors = dlg.selected_ids or {}
            has_any = any(len(s) > 0 for s in self.sel_doors.values())
            self.lbl_doors.Text = "✔" if has_any else "✖"
            self.lbl_doors.ForeColor = Color.Green if has_any else Color.Red

    def _do_export(self, sender, args):
        if self.cb_glaz.Checked and not any(self.sel_glazing.values()):
            TaskDialog.Show("Export", "Выберите типы остекления.")
            return
        if self.cb_doors.Checked and not any(self.sel_doors.values()):
            TaskDialog.Show("Export", "Выберите типы дверей.")
            return

        levels_list = [
            {"id": k, "name": v["name"], "elevation_ft": round(v["elevation_ft"], 4), "elevation_m": round(v["elevation_m"], 3)}
            for k, v in sorted(self.levels_map.items(), key=lambda kv: kv[1]["elevation_ft"])
        ]

        rooms = _collect_rooms(doc, DB.SpatialElementBoundaryLocation.Finish, self.levels_map) if self.cb_rooms.Checked else []
        openings = []
        
        if self.cb_glaz.Checked:
            openings.extend(_export_glazing_as_openings(self.sel_glazing))
        if self.cb_doors.Checked:
            openings.extend(_export_doors_as_openings(self.sel_doors))

        out = {
            "version": "bess-export-3.0",
            "units_note": "Internal length units are feet. Geometry exported as ft and m.",
            "meta": _meta(self.levels_map),
            "levels": levels_list,
            "rooms": rooms,
            "openings": openings
        }

        path = _pick_save_path()
        if not path:
            TaskDialog.Show("REVIT_DATA_EXPORT", "Path not selected.")
            return
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        TaskDialog.Show(
            "REVIT_DATA_EXPORT",
            "Exported:\n{}\nRooms: {}\nOpenings: {}".format(path, len(rooms), len(openings))
        )
        self.Close()

# ---------------- Export helpers ----------------
def _export_glazing_as_openings(sel_glazing):
    """Экспорт остекления как отверстий"""
    openings = []
    windows_ids = set(sel_glazing.get("Windows", set()))
    panels_ids = set(sel_glazing.get("Curtain Panels", set()))
    cw_ids = set(sel_glazing.get("Curtain Walls", set()))
    
    for sdoc, linkinst, T in _docs_sources(doc):
        # Windows
        if windows_ids:
            col = DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_Windows).WhereElementIsNotElementType()
            for el in col:
                try:
                    if not isinstance(el, DB.FamilyInstance):
                        continue
                    sym = el.Symbol
                    if not sym or sym.Id.IntegerValue not in windows_ids:
                        continue
                    
                    opening = _create_opening_record(el, sym, sdoc, linkinst, T, "window")
                    if opening:
                        openings.append(opening)
                except Exception as ex:
                    logger.warn("Window export issue: {}".format(ex))
        
        # Curtain Panels
        if panels_ids:
            col = DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_CurtainWallPanels).WhereElementIsNotElementType()
            for el in col:
                try:
                    if not isinstance(el, DB.FamilyInstance):
                        continue
                    sym = el.Symbol
                    if not sym or sym.Id.IntegerValue not in panels_ids:
                        continue
                    
                    opening = _create_opening_record(el, sym, sdoc, linkinst, T, "curtain_panel")
                    if opening:
                        openings.append(opening)
                except Exception as ex:
                    logger.warn("CurtainPanel export issue: {}".format(ex))
    
    return openings

def _export_doors_as_openings(sel_doors):
    """Экспорт дверей как отверстий"""
    openings = []
    door_ids = set()
    for k, v in sel_doors.items():
        if k == "Doors":
            door_ids |= set(v)
    
    if not door_ids:
        return openings
    
    for sdoc, linkinst, T in _docs_sources(doc):
        col = DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_Doors).WhereElementIsNotElementType()
        for el in col:
            try:
                if not isinstance(el, DB.FamilyInstance):
                    continue
                sym = el.Symbol
                if not sym or sym.Id.IntegerValue not in door_ids:
                    continue
                
                opening = _create_opening_record(el, sym, sdoc, linkinst, T, "door")
                if opening:
                    openings.append(opening)
            except Exception as ex:
                logger.warn("Door export issue: {}".format(ex))
    
    return openings

def _create_opening_record(el, sym, sdoc, linkinst, T, opening_type):
    """Создание записи отверстия"""
    bbox = _bbox_record(el, T)
    if not bbox:
        return None
    
    # Получаем размеры из bbox
    min_m = bbox.get("min_m", [0, 0, 0])
    max_m = bbox.get("max_m", [0, 0, 0])
    
    # Создаем прямоугольный контур на основе bbox
    x0, y0 = min_m[0], min_m[1]
    x1, y1 = max_m[0], max_m[1]
    outer_xy_m = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
    
    params = _collect_all_params(el, sdoc)
    
    # Добавляем информацию о связанных помещениях
    from_room = ""
    to_room = ""
    try:
        if hasattr(el, "FromRoom") and el.FromRoom:
            from_room = _room_name(el.FromRoom)
        if hasattr(el, "ToRoom") and el.ToRoom:
            to_room = _room_name(el.ToRoom)
    except:
        pass
    
    opening = {
        "id": el.Id.IntegerValue,
        "unique_id": getattr(el, "UniqueId", None),
        "opening_type": opening_type,
        "category": sym.Category.Name if sym.Category else "",
        "symbol_name": _element_typename(el, sdoc),
        "name": _element_typename(el, sdoc),
        "level": params.get("type", {}).get("Level", "") or params.get("instance", {}).get("Level", ""),
        "from_room": from_room,
        "to_room": to_room,
        "outer_xy_m": outer_xy_m,
        "inner_loops_xy_m": [],
        "params": params
    }
    
    if linkinst is not None:
        opening["in_link"] = {
            "link_instance_id": linkinst.Id.IntegerValue,
            "link_doc_title": sdoc.Title,
            "link_doc_full_path": _user_model_path(sdoc)
        }
    
    return opening

# ---------------- Save path + meta ----------------
def _pick_save_path():
    try:
        dlg = SaveFileDialog()
        dlg.Filter = "JSON files (*.json)|*.json|All files (*.*)|*.*"
        dlg.FileName = "bess_export.json"
        if dlg.ShowDialog() == DialogResult.OK:
            return dlg.FileName
        return None
    except:
        base = _user_model_path(doc)
        folder = os.path.dirname(base) if base else os.path.expanduser("~/Desktop")
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        return os.path.join(folder, "bess_export_{}.json".format(ts))

def _meta(levels_map):
    host_full = _user_model_path(doc)
    return {
        "doc_title": doc.Title,
        "doc_full_path": host_full,
        "doc_dir": os.path.dirname(host_full) if host_full else "",
        "export_time": datetime.utcnow().isoformat(),
        "links": [
            {
                "instance_id": li.Id.IntegerValue,
                "doc_title": ldoc.Title,
                "doc_full_path": _user_model_path(ldoc)
            }
            for ldoc, li, _ in _docs_sources(doc) if li is not None
        ]
    }

# ---------------- Entry ----------------
def main():
    if doc.IsLinked:
        TaskDialog.Show("REVIT_DATA_EXPORT", "Open a host model, not a linked file.")
        return
    form = MainExportForm()
    form.ShowDialog()

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        TaskDialog.Show("REVIT_DATA_EXPORT", "Export failed:\n{}".format(ex))