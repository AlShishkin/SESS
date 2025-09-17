#! python3
# -*- coding: utf-8 -*-
"""
REVIT_DATA_EXPORT — CPython3 + pyRevit (WinForms UI, без pyrevit.forms)

UI:
- Основное окно: чекбоксы [Помещения] [Остекление] [Двери]
- Кнопки "Выбрать типы остекления" / "Выбрать типы дверей" с индикаторами статуса
- Большие диалоги выбора с таблицами категорий, типов и параметров

Экспорт:
- Rooms: контуры полигонов тесселяцией + все параметры  
- Windows/Doors: bounding box + все параметры элемента
"""

from pyrevit import revit, DB, script
from Autodesk.Revit.UI import TaskDialog
import System
from System.Windows.Forms import (
    Form, DataGridView, DataGridViewCheckBoxColumn, DataGridViewTextBoxColumn,
    Button, FlowLayoutPanel, DockStyle, SaveFileDialog, DialogResult, FormStartPosition,
    FlowDirection, DataGridViewAutoSizeColumnsMode, CheckBox, Label, Panel
)
from System.Drawing import Size, Color, Font, FontStyle
import json, re, os
from math import sqrt
from datetime import datetime

doc = revit.doc
logger = script.get_logger()

# -------- константы --------
FT_TO_M = 0.3048
FT2_TO_M2 = FT_TO_M * FT_TO_M

TOL_PT_FT = 1e-4
TOL_Z_FT  = 1e-3

# Компактация геометрии
DECIMATE_GEOM = True
DECIM_EPS_FT  = 0.02   # ~6 мм
ROUND_COORDS  = True
ROUND_M_DEC   = 3      # 0.001 m
ROUND_FT_DEC  = 4      # 1e-4 ft

DOOR_SAMPLE_OFFSET_FT = 0.5
PANEL_OVERLAP_TOL_M = 0.05
PANEL_CENTROID_TOL_M = 0.25
PANEL_AREA_REL_TOL = 0.3
PANEL_AREA_ABS_TOL_M2 = 0.1

# Управление размером JSON: по умолчанию не сохраняем исходные блоки дверей/окон,
# так как унифицированный список openings содержит консолидированные данные.
INCLUDE_RAW_DOORS = False
INCLUDE_RAW_WINDOWS = False

# ---------- уровни / служебные функции ----------
def _level_name_from_map(levels_map, level_id):
    if level_id is None:
        return ""
    info = levels_map.get(level_id)
    if info:
        return info.get("name", "")
    return ""

def _copy_xy_pairs(seq):
    pts = []
    if not isinstance(seq, (list, tuple)):
        return pts
    for item in seq:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        try:
            x = float(item[0]); y = float(item[1])
        except Exception:
            continue
        pts.append([round(x, 6), round(y, 6)])
    return pts

# ---------- математика / трансформы ----------
def _add(p, v): return DB.XYZ(p.X + v.X, p.Y + v.Y, p.Z + v.Z)
def _sub(a, b): return DB.XYZ(a.X - b.X, a.Y - b.Y, a.Z - b.Z)
def _mul(v, s): return DB.XYZ(v.X * s, v.Y * s, v.Z * s)
def _normalize(v):
    try: return v.Normalize()
    except: return v
def _cross(a, b):
    try: return a.CrossProduct(b)
    except: return None
def _of_point(T, p):
    try: return T.OfPoint(p) if T else p
    except: return p
def _of_vector(T, v):
    try: return T.OfVector(v) if T else v
    except: return v

# ---------- округление / децимация ----------
def _roundf(x, dec): return round(x, dec) if x is not None else None

def _xy_ft_from_pts(pts):
    if ROUND_COORDS:
        return [[_roundf(p.X, ROUND_FT_DEC), _roundf(p.Y, ROUND_FT_DEC)] for p in pts]
    return [[p.X, p.Y] for p in pts]

def _xy_m_from_pts(pts):
    if ROUND_COORDS:
        return [[_roundf(p.X * FT_TO_M, ROUND_M_DEC), _roundf(p.Y * FT_TO_M, ROUND_M_DEC)] for p in pts]
    return [[p.X * FT_TO_M, p.Y * FT_TO_M] for p in pts]

def _close_ring_if_needed(pts):
    if len(pts) >= 2 and pts[0].DistanceTo(pts[-1]) > TOL_PT_FT:
        pts.append(pts[0])
    return pts

def _signed_area_xy_ft(pts):
    a, n = 0.0, len(pts)
    if n < 2: return 0.0
    for i in range(n - 1):
        x1, y1 = pts[i].X, pts[i].Y
        x2, y2 = pts[i + 1].X, pts[i + 1].Y
        a += x1*y2 - x2*y1
    return 0.5*a

def _dedup_pts(pts):
    out = []
    for p in pts:
        if not out or p.DistanceTo(out[-1]) > TOL_PT_FT:
            out.append(p)
    return out

def _dist_point_seg_xy(p, a, b):
    ax, ay, bx, by, px, py = a.X, a.Y, b.X, b.Y, p.X, p.Y
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    c1 = vx*wx + vy*wy
    c2 = vx*vx + vy*vy
    t = 0.0 if c2 <= 1e-12 else max(0.0, min(1.0, c1 / c2))
    qx, qy = ax + t*vx, ay + t*vy
    dx, dy = px - qx, py - qy
    return sqrt(dx*dx + dy*dy)

def _rdp_xy(pts, eps_ft):
    if not DECIMATE_GEOM or len(pts) < 5:
        return pts
    first, last = 0, len(pts) - 1
    stack = [(first, last)]
    keep = [False]*len(pts)
    keep[first] = keep[last] = True
    while stack:
        i, j = stack.pop()
        maxd, idx = -1.0, None
        a, b = pts[i], pts[j]
        k = i + 1
        while k < j:
            d = _dist_point_seg_xy(pts[k], a, b)
            if d > maxd:
                maxd, idx = d, k
            k += 1
        if maxd > eps_ft and idx is not None:
            keep[idx] = True
            stack.append((i, idx))
            stack.append((idx, j))
    return [p for i, p in enumerate(pts) if keep[i]]

# ---------- кольца / тесселяция ----------
def _tess_segments(segs, T=None):
    pts, last = [], None
    for s in segs:
        for p in s.GetCurve().Tessellate():
            hp = _of_point(T, p)
            if last is None or hp.DistanceTo(last) > TOL_PT_FT:
                pts.append(hp); last = hp
    pts = _close_ring_if_needed(_dedup_pts(pts))
    if DECIMATE_GEOM: pts = _rdp_xy(pts, DECIM_EPS_FT)
    return pts

def _ring_from_curves(curves, T=None):
    pts, last = [], None
    try:
        it = curves.GetEnumerator(); has_enum = True
    except:
        has_enum = False
    if has_enum:
        while it.MoveNext():
            for p in it.Current.Tessellate():
                hp = _of_point(T, p)
                if last is None or hp.DistanceTo(last) > TOL_PT_FT:
                    pts.append(hp); last = hp
    else:
        for crv in curves:
            for p in crv.Tessellate():
                hp = _of_point(T, p)
                if last is None or hp.DistanceTo(last) > TOL_PT_FT:
                    pts.append(hp); last = hp
    pts = _close_ring_if_needed(_dedup_pts(pts))
    if DECIMATE_GEOM: pts = _rdp_xy(pts, DECIM_EPS_FT)
    return pts

def _loops_from_boundary(seglists, T=None):
    loops = []
    if not seglists: return None, []
    for segs in seglists:
        ring = _tess_segments(segs, T)
        if len(ring) >= 4: loops.append(ring)
    if not loops: return None, []
    areas = [abs(_signed_area_xy_ft(r)) for r in loops]
    outer = loops[areas.index(max(areas))]
    inners = [r for r in loops if r is not outer]
    return outer, inners

def _loops_from_sketch(sketch, T=None):
    try:
        prof = sketch.Profile
        rings = []
        it = prof.GetEnumerator()
        while it.MoveNext():
            rings.append(_ring_from_curves(it.Current, T))
        if not rings: return None, []
        areas = [abs(_signed_area_xy_ft(r)) for r in rings]
        outer = rings[areas.index(max(areas))]
        inners = [r for r in rings if r is not outer]
        return outer, inners
    except:
        return None, []

def _ensure_ccw(pts):
    return pts if (pts and _signed_area_xy_ft(pts) > 0) else list(reversed(pts)) if pts else pts

def _loop_record_from_pts(pts):
    return {"xy_ft": _xy_ft_from_pts(pts),
            "xy_m":  _xy_m_from_pts(pts),
            "signed_area_ft2": _signed_area_xy_ft(pts)}

def _poly_area_ft2(loops):
    if not loops or not loops.get("outer"): return None
    outer = loops["outer"].get("signed_area_ft2", 0.0) or 0.0
    inn = sum(abs(r.get("signed_area_ft2", 0.0) or 0.0) for r in loops.get("inners", []))
    return outer - inn

# ---------- footprint-помощники ----------
def _rect_footprint(center, x_dir, y_dir, x_len_ft, y_len_ft):
    if not center or not x_dir or not y_dir or not x_len_ft or not y_len_ft:
        return None
    x = _normalize(x_dir); y = _normalize(y_dir)
    hx = _mul(x, 0.5*x_len_ft); hy = _mul(y, 0.5*y_len_ft)
    p1 = _add(_add(center, hx), hy)
    p2 = _add(_sub(center, hx), hy)
    p3 = _sub(_sub(center, hx), hy)
    p4 = _sub(_add(center, hx), hy)
    ring = [p1, p2, p3, p4, p1]
    return ring

def _footprint_record(ring):
    if not ring: return None
    return {"xy_ft": _xy_ft_from_pts(ring),
            "xy_m":  _xy_m_from_pts(ring),
            "signed_area_ft2": _signed_area_xy_ft(ring)}

def _bb_center(el, T=None):
    try:
        bb = el.get_BoundingBox(None)
        if not bb: return None
        pmin = _of_point(T, bb.Min); pmax = _of_point(T, bb.Max)
        return DB.XYZ((pmin.X+pmax.X)*0.5, (pmin.Y+pmax.Y)*0.5, (pmin.Z+pmax.Z)*0.5)
    except: return None

def _bb_size(el, T=None):
    try:
        bb = el.get_BoundingBox(None)
        if not bb: return None
        pmin = _of_point(T, bb.Min); pmax = _of_point(T, bb.Max)
        return [abs(pmax.X-pmin.X), abs(pmax.Y-pmin.Y), abs(pmax.Z-pmin.Z)]
    except: return None

def _bb_z_range(el, T=None):
    try:
        bb = el.get_BoundingBox(None)
        if not bb: return None, None
        pmin = _of_point(T, bb.Min); pmax = _of_point(T, bb.Max)
        return (min(pmin.Z, pmax.Z), max(pmin.Z, pmax.Z))
    except: return None, None

# ---------- параметры ----------
def _storage_name(st):
    try:
        if st == DB.StorageType.String: return "String"
        if st == DB.StorageType.Integer: return "Integer"
        if st == DB.StorageType.Double: return "Double"
        if st == DB.StorageType.ElementId: return "ElementId"
    except: pass
    return "None"

def _param_record(p):
    try:
        d = p.Definition; name = d.Name if d else None
        if not name: return None
        st = p.StorageType; vs = p.AsValueString(); raw = None
        if st == DB.StorageType.String:
            raw = p.AsString(); vs = raw if vs is None else vs
        elif st == DB.StorageType.Integer:
            raw = p.AsInteger(); vs = str(raw) if vs is None else vs
        elif st == DB.StorageType.Double:
            raw = p.AsDouble();  vs = "" if vs is None else vs
        elif st == DB.StorageType.ElementId:
            eid = p.AsElementId(); raw = eid.IntegerValue if eid else None
            vs = (str(raw) if raw is not None else "") if vs is None else vs
        else:
            vs = "" if vs is None else vs
        return name, {"display": vs, "raw_internal": raw,
                      "id": getattr(p, "Id", None).IntegerValue if getattr(p, "Id", None) else None,
                      "is_shared": getattr(p, "IsShared", False),
                      "guid": str(getattr(p, "GUID", None)) if getattr(p, "IsShared", False) else None,
                      "storage_type": _storage_name(st)}
    except: return None

def _collect_params_block(el):
    out = {}
    try:
        for p in el.Parameters:
            kv = _param_record(p)
            if kv: out[kv[0]] = kv[1]
    except: pass
    return out

def _collect_all_params(el, doc_):
    res = {"instance": {}, "type": {}}
    try: res["instance"] = _collect_params_block(el)
    except: pass
    try:
        tid = el.GetTypeId()
        if tid and tid.IntegerValue != -1:
            t_el = doc_.GetElement(tid)
            if t_el:
                res["type"] = _collect_params_block(t_el)
    except: pass
    return res

# ---------------- Категории для остекления и дверей ----------------
def _gather_glazing_data(design_option_id=None):
    """Собирает данные для остекления: Walls, Curtain Walls, Curtain Panels, Windows"""
    rows = []
    seen = set()
    type_counts = {}  # Подсчет количества элементов каждого типа
    
    for sdoc, _, _ in _docs_sources(doc):
        # Windows - сначала подсчитываем элементы
        for inst in DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_Windows).WhereElementIsNotElementType():
            if not _element_matches_design_option(inst, design_option_id):
                continue
            if hasattr(inst, 'Symbol') and inst.Symbol:
                fs = inst.Symbol
                nm = fs.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
                tname = nm.AsString() if nm else getattr(fs,"Name","")
                key = ("Windows", tname)
                type_counts[key] = type_counts.get(key, 0) + 1
        
        # Теперь собираем типы
        for fs in DB.FilteredElementCollector(sdoc).OfClass(DB.FamilySymbol).OfCategory(DB.BuiltInCategory.OST_Windows):
            nm = fs.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
            tname = nm.AsString() if nm else getattr(fs,"Name","")
            key = ("Windows", tname)
            if key not in seen:
                params = _collect_params_block(fs)
                count = type_counts.get(key, 0)
                rows.append({"category":"Windows", "type_name":tname, "type_params":params, "count":count})
                seen.add(key)
        
        # Curtain Panels - подсчитываем элементы
        for inst in DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_CurtainWallPanels).WhereElementIsNotElementType():
            if not _element_matches_design_option(inst, design_option_id):
                continue
            if hasattr(inst, 'Symbol') and inst.Symbol:
                fs = inst.Symbol
                nm = fs.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
                tname = nm.AsString() if nm else getattr(fs,"Name","")
                key = ("Curtain Panels", tname or "Curtain Panel")
                type_counts[key] = type_counts.get(key, 0) + 1
                
        # Собираем типы Curtain Panels
        for fs in DB.FilteredElementCollector(sdoc).OfClass(DB.FamilySymbol).OfCategory(DB.BuiltInCategory.OST_CurtainWallPanels):
            nm = fs.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
            tname = nm.AsString() if nm else getattr(fs,"Name","")
            key = ("Curtain Panels", tname or "Curtain Panel")
            if key not in seen:
                params = _collect_params_block(fs)
                count = type_counts.get(key, 0)
                rows.append({"category":"Curtain Panels", "type_name":(tname or "Curtain Panel"), "type_params":params, "count":count})
                seen.add(key)
        
        # Walls - подсчитываем элементы
        for inst in DB.FilteredElementCollector(sdoc).OfClass(DB.Wall):
            if not _element_matches_design_option(inst, design_option_id):
                continue
            wt = doc.GetElement(inst.GetTypeId()) if inst.GetTypeId() else None
            if wt:
                key = ("Walls", wt.Name)
                type_counts[key] = type_counts.get(key, 0) + 1
                
        # Собираем типы Walls
        for wt in DB.FilteredElementCollector(sdoc).OfClass(DB.WallType):
            key = ("Walls", wt.Name)
            if key not in seen:
                params = _collect_params_block(wt)
                count = type_counts.get(key, 0)
                rows.append({"category":"Walls", "type_name":wt.Name, "type_params":params, "count":count})
                seen.add(key)
        
        # Curtain Walls
        for wt in DB.FilteredElementCollector(sdoc).OfClass(DB.WallType):
            if hasattr(wt, 'Kind') and wt.Kind == DB.WallKind.Curtain:
                key = ("Curtain Walls", wt.Name)
                if key not in seen:
                    params = _collect_params_block(wt)
                    # Для Curtain Walls используем тот же счетчик что и для Walls
                    count = type_counts.get(("Walls", wt.Name), 0)
                    rows.append({"category":"Curtain Walls", "type_name":wt.Name, "type_params":params, "count":count})
                    seen.add(key)
    
    rows.sort(key=lambda r: (r["category"], r["type_name"]))
    return rows

def _gather_doors_data(design_option_id=None):
    """Собирает данные для дверей"""
    rows = []
    seen = set()
    type_counts = {}  # Подсчет количества элементов каждого типа
    
    for sdoc, _, _ in _docs_sources(doc):
        # Doors - сначала подсчитываем элементы
        for inst in DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_Doors).WhereElementIsNotElementType():
            if not _element_matches_design_option(inst, design_option_id):
                continue
            if hasattr(inst, 'Symbol') and inst.Symbol:
                fs = inst.Symbol
                nm = fs.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
                tname = nm.AsString() if nm else getattr(fs,"Name","")
                key = ("Doors", tname)
                type_counts[key] = type_counts.get(key, 0) + 1
        
        # Теперь собираем типы
        for fs in DB.FilteredElementCollector(sdoc).OfClass(DB.FamilySymbol).OfCategory(DB.BuiltInCategory.OST_Doors):
            nm = fs.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
            tname = nm.AsString() if nm else getattr(fs,"Name","")
            key = ("Doors", tname)
            if key not in seen:
                params = _collect_params_block(fs)
                count = type_counts.get(key, 0)
                rows.append({"category":"Doors", "type_name":tname, "type_params":params, "count":count})
                seen.add(key)
    
    rows.sort(key=lambda r: (r["category"], r["type_name"]))
    return rows

# ---------- безопасные геттеры и поиск double-параметров ----------
def _safe_int(eid):
    try: return eid.IntegerValue
    except: return None

def _safe_level_id(el):
    try:
        lid = el.LevelId
        if lid and lid.IntegerValue != -1:
            return lid.IntegerValue
    except: pass
    for bip in (DB.BuiltInParameter.INSTANCE_REFERENCE_LEVEL_PARAM,
                DB.BuiltInParameter.SCHEDULE_LEVEL_PARAM,
                DB.BuiltInParameter.LEVEL_PARAM):
        try:
            p = el.get_Parameter(bip)
            if p:
                eid = p.AsElementId()
                if eid and eid.IntegerValue != -1:
                    return eid.IntegerValue
        except: pass
    return None

def _safe_symbol_name(fi):
    try:
        sym = fi.Symbol
        if not sym: return None
        name_sym = None
        try:
            p = sym.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
            if p: name_sym = p.AsString()
        except: pass
        if not name_sym:
            try: name_sym = getattr(sym, "Name", None)
            except: name_sym = None
        fam_name = None
        try:
            fam = getattr(sym, "Family", None)
            fam_name = getattr(fam, "Name", None)
        except: fam_name = None
        if not fam_name:
            fam_name = getattr(sym, "FamilyName", None)
        return "{} : {}".format(fam_name, name_sym) if (fam_name and name_sym) else (name_sym or fam_name)
    except: return None

def _get_double_param_by(el, bip_names, name_list):
    # поиск double-параметра по BuiltInParameter и по имени
    for nm in bip_names:
        try:
            bip = getattr(DB.BuiltInParameter, nm)
            p = el.get_Parameter(bip)
            if p and p.StorageType == DB.StorageType.Double:
                v = p.AsDouble()
                if v is not None:
                    return v
        except:
            pass
    try:
        want = [n.lower() for n in name_list]
        for p in el.Parameters:
            try:
                d = p.Definition
                nm = d.Name if d else None
                if not nm: continue
                if nm.lower() in want and p.StorageType == DB.StorageType.Double:
                    v = p.AsDouble()
                    if v is not None:
                        return v
            except:
                pass
    except:
        pass
    return None

get_double_param_by = _get_double_param_by  # алиас

# ---------- пути модели / источники ----------
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
    sources = [(document, None, DB.Transform.Identity)]
    try:
        for li in DB.FilteredElementCollector(document).OfClass(DB.RevitLinkInstance):
            ldoc = li.GetLinkDocument()
            if ldoc is None: continue
            sources.append((ldoc, li, li.GetTransform()))
    except: pass
    return sources

# ---------- уровни ----------
def _all_levels_map(document):
    m = {}
    for lv in DB.FilteredElementCollector(document).OfClass(DB.Level):
        try:
            elev = float(lv.Elevation)
            m[lv.Id.IntegerValue] = {"name": lv.Name,
                                     "elevation_ft": elev,
                                     "elevation_m": elev * FT_TO_M}
        except: pass
    return m

# ---------- комнаты / площади ----------
def _room_name(r):
    try:
        p = r.get_Parameter(DB.BuiltInParameter.ROOM_NAME)
        nm = p.AsString() if p else None
        return nm or getattr(r, "Name", None)
    except: return getattr(r, "Name", None)

def _room_number(r):
    try:
        p = r.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER)
        s = p.AsString() if p else None
        return s or getattr(r, "Number", None)
    except: return getattr(r, "Number", None)

def _collect_rooms(document, boundary_location, levels_map):
    out = []; opts = DB.SpatialElementBoundaryOptions(); opts.SpatialElementBoundaryLocation = boundary_location
    fec = (DB.FilteredElementCollector(document).OfCategory(DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType())
    for r in fec:
        try:
            if not isinstance(r, DB.SpatialElement): continue
            outer, inners = _loops_from_boundary(r.GetBoundarySegments(opts))
            if not outer: continue
            area_ft2 = float(getattr(r, "Area", 0.0)) if hasattr(r, "Area") else None
            loops = {"outer": _loop_record_from_pts(outer),
                     "inners": [_loop_record_from_pts(x) for x in inners]}
            level_id = _safe_level_id(r)
            level_name = _level_name_from_map(levels_map, level_id)
            rec = {"id": r.Id.IntegerValue, "unique_id": r.UniqueId,
                   "number": _room_number(r), "name": _room_name(r),
                   "level_id": level_id,
                   "level": level_name,
                   "loops": loops,
                   "poly_area_ft2": _poly_area_ft2(loops),
                   "area_ft2_param": area_ft2,
                   "area_m2_param": area_ft2 * FT2_TO_M2 if area_ft2 is not None else None,
                   "params": _collect_all_params(r, document)}

            outer_loop = loops.get("outer")
            if isinstance(outer_loop, dict):
                if outer_loop.get("xy_m"):
                    rec["outer_xy_m"] = _copy_xy_pairs(outer_loop.get("xy_m"))
                if outer_loop.get("xy_ft"):
                    rec["outer_xy_ft"] = _copy_xy_pairs(outer_loop.get("xy_ft"))
            inner_xy_m = []
            inner_xy_ft = []
            for hole in loops.get("inners", []):
                if not isinstance(hole, dict):
                    continue
                if hole.get("xy_m"):
                    inner_xy_m.append(_copy_xy_pairs(hole.get("xy_m")))
                if hole.get("xy_ft"):
                    inner_xy_ft.append(_copy_xy_pairs(hole.get("xy_ft")))
            if inner_xy_m:
                rec["inner_loops_xy_m"] = inner_xy_m
            if inner_xy_ft:
                rec["inner_loops_xy_ft"] = inner_xy_ft

            out.append(rec)
        except Exception as ex:
            logger.warn("Room {} issue: {}".format(getattr(r, "Id", "?"), ex))
    return out

def _collect_areas(document, boundary_location, levels_map):
    out = []; opts = DB.SpatialElementBoundaryOptions(); opts.SpatialElementBoundaryLocation = boundary_location
    fec = (DB.FilteredElementCollector(document).OfCategory(DB.BuiltInCategory.OST_Areas).WhereElementIsNotElementType())
    for a in fec:
        try:
            if not isinstance(a, DB.SpatialElement): continue
            outer, inners = _loops_from_boundary(a.GetBoundarySegments(opts))
            if not outer: continue
            area_ft2 = float(getattr(a, "Area", 0.0)) if hasattr(a, "Area") else None
            scheme = getattr(a, "AreaScheme", None)
            loops = {"outer": _loop_record_from_pts(outer),
                     "inners": [_loop_record_from_pts(x) for x in inners]}
            level_id = _safe_level_id(a)
            level_name = _level_name_from_map(levels_map, level_id)
            rec = {"id": a.Id.IntegerValue, "unique_id": a.UniqueId,
                   "name": getattr(a, "Name", None), "number": getattr(a, "Number", None),
                   "level_id": level_id,
                   "level": level_name,
                   "area_scheme": scheme.Name if scheme else None,
                   "loops": loops,
                   "poly_area_ft2": _poly_area_ft2(loops),
                   "area_ft2_param": area_ft2,
                   "area_m2_param": area_ft2 * FT2_TO_M2 if area_ft2 is not None else None,
                   "params": _collect_all_params(a, document)}

            outer_loop = loops.get("outer")
            if isinstance(outer_loop, dict):
                if outer_loop.get("xy_m"):
                    rec["outer_xy_m"] = _copy_xy_pairs(outer_loop.get("xy_m"))
                if outer_loop.get("xy_ft"):
                    rec["outer_xy_ft"] = _copy_xy_pairs(outer_loop.get("xy_ft"))
            inner_xy_m = []
            inner_xy_ft = []
            for hole in loops.get("inners", []):
                if not isinstance(hole, dict):
                    continue
                if hole.get("xy_m"):
                    inner_xy_m.append(_copy_xy_pairs(hole.get("xy_m")))
                if hole.get("xy_ft"):
                    inner_xy_ft.append(_copy_xy_pairs(hole.get("xy_ft")))
            if inner_xy_m:
                rec["inner_loops_xy_m"] = inner_xy_m
            if inner_xy_ft:
                rec["inner_loops_xy_ft"] = inner_xy_ft

            out.append(rec)
        except Exception as ex:
            logger.warn("Area {} issue: {}".format(getattr(a, "Id", "?"), ex))
    return out

# ---------- фаза / комнаты по точке ----------
def _get_active_phase(document):
    try:
        v = document.ActiveView; prm = v.get_Parameter(DB.BuiltInParameter.VIEW_PHASE)
        if prm:
            peid = prm.AsElementId()
            if peid and peid.IntegerValue != -1:
                ph = document.GetElement(peid)
                if isinstance(ph, DB.Phase): return ph
    except: pass
    try:
        phases = list(DB.FilteredElementCollector(document).OfClass(DB.Phase))
        if phases:
            phases.sort(key=lambda p: p.Id.IntegerValue)
            return phases[-1]
    except: pass
    return None

def _room_at_point_host(host_doc, point, phase):
    if point is None: return None
    try: return host_doc.GetRoomAtPoint(point, phase)
    except:
        try: return host_doc.GetRoomAtPoint(point)
        except: return None

def _door_rooms_via_sampling(host_doc, phase, center_host, facing_host):
    if center_host is None or facing_host is None: return None, None
    f = _normalize(facing_host)
    p_to   = _add(center_host, _mul(f,  DOOR_SAMPLE_OFFSET_FT))
    p_from = _add(center_host, _mul(f, -DOOR_SAMPLE_OFFSET_FT))
    r_to   = _room_at_point_host(host_doc, p_to,   phase)
    r_from = _room_at_point_host(host_doc, p_from, phase)
    return r_from, r_to

def _fallback_fr_tr(fi, phase):
    fr = tr = None
    try:
        fr = fi.FromRoom[DB.Phase](phase); tr = fi.ToRoom[DB.Phase](phase)
    except:
        try:
            fr = fi.FromRoom(phase); tr = fi.ToRoom(phase)
        except: pass
    return fr, tr

def _nominal_from_symbol(sym_name):
    if not sym_name: return None, None
    m = re.search(r'(\d{3,4})\s*W[xX]\s*(\d{3,4})\s*H', sym_name)
    if not m: return None, None
    return float(m.group(1))/304.8, float(m.group(2))/304.8

# ---------- двери ----------
def _collect_doors_all_docs(host_doc, phase):
    out = []
    for sdoc, linkinst, T in _docs_sources(host_doc):
        fec = (DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_Doors).WhereElementIsNotElementType())
        for fi in fec:
            try:
                if not isinstance(fi, DB.FamilyInstance): continue
                center = _of_point(T, _bb_center(fi))
                facing = _of_vector(T, getattr(fi, "FacingOrientation", None))
                hand   = _of_vector(T, getattr(fi, "HandOrientation", None))
                if hand is None and facing is not None:
                    hand = _cross(DB.XYZ.BasisZ, facing)
                host = getattr(fi, "Host", None)

                width  = _get_double_param_by(fi, ['DOOR_WIDTH','FAMILY_WIDTH_PARAM','WIDTH'],
                                                 ['Width','Ширина','Ширина проема','Ширина проёма'])
                height = _get_double_param_by(fi, ['DOOR_HEIGHT','FAMILY_HEIGHT_PARAM','HEIGHT'],
                                                 ['Height','Высота','Высота проема','Высота проёма'])
                if (not width or not height):
                    sz = _bb_size(fi, T)
                    if sz:
                        width  = width  or max(sz[0], sz[1])
                        height = height or sz[2]
                nw, nh = _nominal_from_symbol(_safe_symbol_name(fi))
                if nw and width and 1.8*nw <= width <= 2.2*nw:
                    width = nw

                host_thk = None
                try:
                    if isinstance(host, DB.Wall): host_thk = host.Width
                except: pass
                depth = host_thk or 0.5

                fp_ring  = _rect_footprint(center, hand, facing, width, depth)
                footprint = _footprint_record(fp_ring)

                zmin, zmax = _bb_z_range(fi, T)
                fr, tr = _door_rooms_via_sampling(host_doc, phase, center, facing)
                if fr is None and tr is None:
                    fr, tr = _fallback_fr_tr(fi, phase)

                rec = {"id": _safe_int(fi.Id), "unique_id": getattr(fi, "UniqueId", None),
                       "category": getattr(getattr(fi, "Category", None), "Name", None),
                       "symbol_name": _safe_symbol_name(fi),
                       "level_id": _safe_level_id(fi),
                       "host_id": _safe_int(getattr(host, "Id", None)),
                       "location": {"ft":[_roundf(center.X,ROUND_FT_DEC), _roundf(center.Y,ROUND_FT_DEC), _roundf(center.Z,ROUND_FT_DEC)]} if center else None,
                       "facing_dir": [facing.X, facing.Y, facing.Z] if facing else None,
                       "hand_dir": [hand.X, hand.Y, hand.Z] if hand else None,
                       "footprint": footprint,
                       "z_range_ft": [zmin, zmax] if (zmin is not None and zmax is not None) else None,
                       "height_ft": (zmax - zmin) if (zmin is not None and zmax is not None) else None,
                       "geom": {"frame":{"origin":None,"x_dir":None,"y_dir":None,"z_dir":None},
                                "width_ft": width, "height_ft": height,
                                "nominal_width_ft": nw, "nominal_height_ft": nh,
                                "area_ft2": (width*height) if (width and height) else None,
                                "host_thickness_ft": host_thk},
                       "from_room": {"brief":{"id": fr.Id.IntegerValue, "number": _room_number(fr), "name": _room_name(fr)}} if fr else None,
                       "to_room":   {"brief":{"id": tr.Id.IntegerValue, "number": _room_number(tr), "name": _room_name(tr)}} if tr else None,
                       "params": _collect_all_params(fi, sdoc)}
                if linkinst is not None:
                    rec["in_link"] = {"link_instance_id": linkinst.Id.IntegerValue,
                                      "link_doc_title": sdoc.Title,
                                      "link_doc_full_path": _user_model_path(sdoc)}
                out.append(rec)
            except Exception as ex:
                logger.warn("Door {} issue: {}".format(getattr(fi, "Id", "?"), ex))
                try:
                    out.append({"id": _safe_int(fi.Id), "unique_id": getattr(fi, "UniqueId", None)})
                except: pass
    return out

# ---------- окна (включая панели) ----------
def _collect_windows_all_docs(host_doc):
    out = []
    cats = [(DB.BuiltInCategory.OST_Windows, "OST_Windows", False),
            (DB.BuiltInCategory.OST_CurtainWallPanels, "OST_CurtainWallPanels", True)]
    for sdoc, linkinst, T in _docs_sources(host_doc):
        for bic, catname, is_panel in cats:
            fec = (DB.FilteredElementCollector(sdoc).OfCategory(bic).WhereElementIsNotElementType())
            for el in fec:
                try:
                    fi = el if isinstance(el, DB.FamilyInstance) else None
                    center = _of_point(T, _bb_center(el)) if not fi else _of_point(T, _bb_center(fi))
                    facing = _of_vector(T, getattr(fi, "FacingOrientation", None)) if fi else None
                    hand   = _of_vector(T, getattr(fi, "HandOrientation", None)) if fi else None
                    if fi and hand is None and facing is not None:
                        hand = _cross(DB.XYZ.BasisZ, facing)
                    host = getattr(fi, "Host", None) if fi else None
                    zmin, zmax = _bb_z_range(el if not fi else fi, T)

                    if fi:
                        width  = _get_double_param_by(fi, ['WINDOW_WIDTH','FAMILY_WIDTH_PARAM','WIDTH'], ['Width','Ширина'])
                        height = _get_double_param_by(fi, ['WINDOW_HEIGHT','FAMILY_HEIGHT_PARAM','HEIGHT'], ['Height','Высота'])
                        if (not width or not height):
                            sz = _bb_size(fi, T)
                            if sz:
                                width = width or max(sz[0], sz[1]); height = height or sz[2]
                        host_thk = (host.Width if isinstance(host, DB.Wall) else None)
                        depth = host_thk or 0.3
                        fp_ring = _rect_footprint(center, hand, facing, width, depth)
                        footprint = _footprint_record(fp_ring)
                        geom = {"width_ft": width, "height_ft": height,
                                "area_ft2": (width*height) if (width and height) else None,
                                "host_thickness_ft": host_thk}
                    else:
                        sz = _bb_size(el, T)
                        fp_ring = None
                        if center and sz:
                            x_dir = DB.XYZ.BasisX; y_dir = DB.XYZ.BasisY
                            fp_ring = _rect_footprint(center, x_dir, y_dir, sz[0], sz[1])
                        footprint = _footprint_record(fp_ring)
                        geom = {"bbox_size_ft": sz,
                                "approx_face_area_ft2": (sz[0]*sz[2]) if sz else None,
                                "panel_thickness_ft": None}

                    rec = {"id": _safe_int(el.Id), "unique_id": getattr(el, "UniqueId", None),
                           "category": getattr(getattr(el, "Category", None), "Name", None),
                           "symbol_name": _safe_symbol_name(fi) if fi else None,
                           "level_id": _safe_level_id(fi if fi else el),
                           "host_id": _safe_int(getattr(getattr(fi, "Host", None), "Id", None)) if fi else None,
                           "location": {"ft":[_roundf(center.X,ROUND_FT_DEC), _roundf(center.Y,ROUND_FT_DEC), _roundf(center.Z,ROUND_FT_DEC)]} if center else None,
                           "facing_dir": [facing.X, facing.Y, facing.Z] if facing else None,
                           "footprint": footprint,
                           "z_range_ft": [zmin, zmax] if (zmin is not None and zmax is not None) else None,
                           "height_ft": (zmax - zmin) if (zmin is not None and zmax is not None) else None,
                           "geom": geom,
                           "params": _collect_all_params(fi if fi else el, sdoc),
                           "source_category": catname, "is_curtain_panel": is_panel}
                    if linkinst is not None:
                        rec["in_link"] = {"link_instance_id": linkinst.Id.IntegerValue,
                                          "link_doc_title": sdoc.Title,
                                          "link_doc_full_path": _user_model_path(sdoc)}
                    out.append(rec)
                except Exception as ex:
                    logger.warn("Window/Panel {} issue: {}".format(getattr(el, "Id", "?"), ex))
                    try:
                        out.append({"id": _safe_int(el.Id),
                                    "unique_id": getattr(el, "UniqueId", None),
                                    "source_category": catname,
                                    "is_curtain_panel": is_panel})
                    except: pass
    return out

# ---------- шахты ----------
def _collect_shafts_all_docs(host_doc, levels_map):
    shafts_all, by_level = [], {}
    for sdoc, linkinst, T in _docs_sources(host_doc):
        try: elems = list(DB.FilteredElementCollector(sdoc).OfClass(DB.ShaftOpening))
        except:
            elems = list(DB.FilteredElementCollector(sdoc)
                         .OfCategory(DB.BuiltInCategory.OST_ShaftOpening)
                         .WhereElementIsNotElementType())
        for so in elems:
            try:
                outer = inners = None
                try:
                    sk_id = getattr(so, "SketchId", None)
                    if sk_id and sk_id.IntegerValue != -1:
                        sk = sdoc.GetElement(sk_id)
                        if sk: outer, inners = _loops_from_sketch(sk, T)
                except: pass
                if not outer:
                    try:
                        curves = getattr(so, "BoundaryRect", None)
                        if curves:
                            r = _ring_from_curves(curves, T)
                            if r and len(r) >= 4: outer, inners = r, []
                    except: pass
                if outer: outer = _ensure_ccw(outer)

                zmin, zmax = _bb_z_range(so, T)
                loops = {"outer": _loop_record_from_pts(outer) if outer else None,
                         "inners": [_loop_record_from_pts(r) for r in (inners or [])]}
                if loops["outer"]:
                    loops["outer"]["area_ft2_abs"] = abs(loops["outer"]["signed_area_ft2"])

                rec = {"id": so.Id.IntegerValue, "unique_id": so.UniqueId,
                       "bbox_z_ft": [zmin, zmax] if (zmin is not None and zmax is not None) else None,
                       "height_ft": (zmax - zmin) if (zmin is not None and zmax is not None) else None,
                       "loops": loops,
                       "poly_area_ft2": _poly_area_ft2(loops),
                       "params": _collect_all_params(so, sdoc)}
                outer_loop = loops.get("outer") if isinstance(loops, dict) else None
                if isinstance(outer_loop, dict):
                    xy_m = outer_loop.get("xy_m")
                    if xy_m:
                        rec["outer_xy_m"] = _copy_xy_pairs(xy_m)
                    xy_ft = outer_loop.get("xy_ft")
                    if xy_ft:
                        rec["outer_xy_ft"] = _copy_xy_pairs(xy_ft)
                if linkinst is not None:
                    rec["in_link"] = {"link_instance_id": linkinst.Id.IntegerValue,
                                      "link_doc_title": sdoc.Title,
                                      "link_doc_full_path": _user_model_path(sdoc)}
                shafts_all.append(rec)

                if loops["outer"] and (zmin is not None and zmax is not None):
                    for lid, lv in levels_map.items():
                        z = lv["elevation_ft"]
                        if (z + TOL_Z_FT) >= zmin and (z - TOL_Z_FT) <= zmax:
                            entry = {"shaft_id": so.Id.IntegerValue,
                                     "unique_id": so.UniqueId,
                                     "outer": loops["outer"]}
                            by_level.setdefault(lid, []).append(entry)
            except Exception as ex:
                logger.warn("Shaft {} issue: {}".format(getattr(so, "Id", "?"), ex))
    return shafts_all, by_level

# ---------- вспомогательные функции для openings ----------
def _flatten_params_simple(raw):
    flat = {}
    if not isinstance(raw, dict):
        return flat

    def _store(name, value):
        if isinstance(value, (int, float)):
            flat[str(name)] = round(float(value), 6)
        elif value is None:
            flat[str(name)] = ""
        else:
            flat[str(name)] = value

    if "instance" in raw or "type" in raw:
        for block_name in ("instance", "type"):
            block = raw.get(block_name, {})
            if not isinstance(block, dict):
                continue
            for name, info in block.items():
                if isinstance(info, dict):
                    val = info.get("display")
                    if val in (None, ""):
                        val = info.get("raw_internal")
                    _store(name, val)
                else:
                    _store(name, info)
    for name, value in raw.items():
        if name in ("instance", "type"):
            continue
        _store(name, value)
    return flat

def _opening_from(src, opening_type, levels_map):
    footprint = src.get("footprint") or {}
    outer_m = _copy_xy_pairs(footprint.get("xy_m"))
    if not outer_m:
        outer_ft = footprint.get("xy_ft")
        if isinstance(outer_ft, list):
            outer_m = _copy_xy_pairs([[float(x)*FT_TO_M, float(y)*FT_TO_M] for x, y in outer_ft])
    if not outer_m:
        return None

    params = _flatten_params_simple(src.get("params"))
    geom = src.get("geom") or {}

    def _set_num(dst_key, value, metric_key=None, metric_factor=1.0):
        if isinstance(value, (int, float)):
            params.setdefault(dst_key, round(float(value), 6))
            if metric_key:
                params.setdefault(metric_key, round(float(value) * metric_factor, 6))

    _set_num("width_ft", geom.get("width_ft"), "width_m", FT_TO_M)
    _set_num("height_ft", geom.get("height_ft"), "height_m", FT_TO_M)
    _set_num("host_thickness_ft", geom.get("host_thickness_ft"), "host_thickness_m", FT_TO_M)
    _set_num("area_ft2", geom.get("area_ft2"), "area_m2", FT2_TO_M2)
    _set_num("approx_face_area_ft2", geom.get("approx_face_area_ft2"), "approx_face_area_m2", FT2_TO_M2)

    z_rng = src.get("z_range_ft") or src.get("bbox_z_ft")
    if isinstance(z_rng, (list, tuple)) and len(z_rng) == 2:
        params.setdefault("z_min_ft", round(float(z_rng[0]), 6))
        params.setdefault("z_max_ft", round(float(z_rng[1]), 6))
        params.setdefault("z_min_m", round(float(z_rng[0]) * FT_TO_M, 6))
        params.setdefault("z_max_m", round(float(z_rng[1]) * FT_TO_M, 6))

    height_ft = src.get("height_ft")
    _set_num("height_ft", height_ft, "height_m", FT_TO_M)

    facing = src.get("facing_dir")
    if facing and "facing_dir" not in params:
        params["facing_dir"] = [round(float(x), 6) for x in facing]
    hand = src.get("hand_dir")
    if hand and "hand_dir" not in params:
        params["hand_dir"] = [round(float(x), 6) for x in hand]

    host_id = src.get("host_id")
    if host_id is not None:
        params.setdefault("host_id", str(host_id))

    link = src.get("in_link")
    if isinstance(link, dict):
        for k, v in link.items():
            params.setdefault(k, v)

    for rel in ("from_room", "to_room"):
        brief = (src.get(rel) or {}).get("brief") if isinstance(src.get(rel), dict) else None
        if isinstance(brief, dict):
            for k, v in brief.items():
                params.setdefault(f"{rel}_{k}", v)

    cat = src.get("category") or src.get("source_category") or ""
    if not opening_type:
        low = str(cat).lower()
        if "door" in low:
            opening_type = "door"
        elif "panel" in low:
            opening_type = "curtain_panel"
        else:
            opening_type = "window"

    level_id = src.get("level_id")
    level_name = ""
    if level_id is not None:
        info = levels_map.get(level_id)
        if info:
            level_name = info.get("name", "")
    if not level_name:
        level_name = params.get("Level", "")

    params.setdefault("source_category", src.get("source_category"))

    base_id = src.get("id")
    if base_id is None:
        base_id = src.get("unique_id") or ""
    record = {
        "id": base_id,
        "unique_id": src.get("unique_id"),
        "category": cat,
        "opening_type": opening_type,
        "symbol_name": src.get("symbol_name"),
        "level_id": level_id,
        "level": level_name,
        "name": src.get("symbol_name") or cat or opening_type,
        "label": cat or opening_type,
        "outer_xy_m": _copy_xy_pairs(outer_m),
        "inner_loops_xy_m": [],
        "params": params,
    }
    return record

def _levels_for_opening(levels_map, z_range_ft, fallback_id, fallback_name):
    hits = []
    if isinstance(z_range_ft, (list, tuple)) and len(z_range_ft) == 2:
        try:
            zmin = float(min(z_range_ft[0], z_range_ft[1]))
            zmax = float(max(z_range_ft[0], z_range_ft[1]))
        except Exception:
            zmin = zmax = None
        if zmin is not None and zmax is not None:
            tmp = []
            for lid, info in levels_map.items():
                elev = info.get("elevation_ft")
                if elev is None:
                    continue
                try:
                    ze = float(elev)
                except Exception:
                    continue
                if (ze + TOL_Z_FT) >= zmin and (ze - TOL_Z_FT) <= zmax:
                    tmp.append((ze, lid, info.get("name", "")))
            tmp.sort(key=lambda item: item[0])
            hits = [(lid, name) for _, lid, name in tmp]
    if not hits:
        name = fallback_name or _level_name_from_map(levels_map, fallback_id)
        hits = [(fallback_id, name)] if (fallback_id is not None or name) else []
    return hits

def _opening_bbox_key(rec):
    poly = rec.get("outer_xy_m") or []
    if len(poly) < 2:
        return None
    xs = []
    ys = []
    for x, y in poly:
        try:
            xs.append(round(float(x), 3))
            ys.append(round(float(y), 3))
        except Exception:
            continue
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs), max(ys), str(rec.get("level") or ""), str(rec.get("level_id") or ""))

def _opening_bounds(rec):
    poly = rec.get("outer_xy_m") or []
    xs = []
    ys = []
    for pt in poly:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            try:
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))
            except Exception:
                continue
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs), max(ys))

def _opening_area_m2(rec):
    poly = rec.get("outer_xy_m") or []
    pts = []
    for pt in poly:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            try:
                pts.append((float(pt[0]), float(pt[1])))
            except Exception:
                continue
    n = len(pts)
    if n < 3:
        return None
    area = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5

def _opening_centroid(rec):
    poly = rec.get("outer_xy_m") or []
    pts = []
    for pt in poly:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            try:
                pts.append((float(pt[0]), float(pt[1])))
            except Exception:
                continue
    n = len(pts)
    if n < 3:
        return None
    area = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    area *= 0.5
    if abs(area) < 1e-9:
        return None
    return (cx / (6.0 * area), cy / (6.0 * area))

def _levels_match(a, b):
    lid_a = a.get("level_id")
    lid_b = b.get("level_id")
    if lid_a is not None and lid_b is not None:
        return lid_a == lid_b
    name_a = str(a.get("level") or "").strip().lower()
    name_b = str(b.get("level") or "").strip().lower()
    return bool(name_a or name_b) and name_a == name_b

def _bbox_overlap(a, b, tol=PANEL_OVERLAP_TOL_M):
    if a is None or b is None:
        return False
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 < bx0 - tol or bx1 < ax0 - tol or ay1 < by0 - tol or by1 < ay0 - tol)

def _centroid_distance(a, b):
    if a is None or b is None:
        return None
    try:
        return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
    except Exception:
        return None

def _clone_for_levels(base_record, src, levels_map):
    z_rng = src.get("z_range_ft") or src.get("bbox_z_ft")
    base_level_id = base_record.get("level_id")
    base_level_name = base_record.get("level")
    hits = _levels_for_opening(levels_map, z_rng, base_level_id, base_level_name)

    params_template = base_record.get("params") or {}
    params_template = dict(params_template)
    base_id = str(base_record.get("id") or base_record.get("unique_id") or "")
    if base_id:
        params_template.setdefault("source_element_id", base_id)
    if base_level_id is not None:
        params_template.setdefault("source_level_id", str(base_level_id))
    if base_level_name:
        params_template.setdefault("source_level_name", base_level_name)

    clones = []
    multi = len(hits) > 1
    if multi:
        params_template.setdefault("levels_spanned", [name for _, name in hits if name])

    for idx, (lid, name) in enumerate(hits):
        rec = dict(base_record)
        rec["params"] = dict(params_template)
        rec["level_id"] = lid
        if name:
            rec["level"] = name
            rec["params"].setdefault("Level", name)
        elif rec.get("level"):
            rec["params"].setdefault("Level", rec.get("level"))

        if multi:
            suffix = name or str(idx)
            if base_id:
                rec["id"] = f"{base_id}@{suffix}"
            else:
                rec["id"] = f"{rec.get('unique_id') or idx}@{suffix}"
        else:
            rec["id"] = base_id or rec.get("id")

        rec["outer_xy_m"] = _copy_xy_pairs(rec.get("outer_xy_m"))
        rec["inner_loops_xy_m"] = [_copy_xy_pairs(loop) for loop in rec.get("inner_loops_xy_m", [])]
        clones.append(rec)

    return clones

def _build_openings(doors, windows, levels_map):
    openings = []
    bbox_map = {}

    def _append(src, opening_type):
        base = _opening_from(src, opening_type, levels_map)
        if not base:
            return
        clones = _clone_for_levels(base, src, levels_map) or [base]
        for rec in clones:
            if rec.get("opening_type") == "curtain_panel":
                panel_bbox = _opening_bounds(rec)
                panel_area = _opening_area_m2(rec)
                panel_centroid = _opening_centroid(rec)
                if panel_bbox:
                    skip_panel = False
                    for existing in openings:
                        if existing.get("opening_type") not in ("door", "window"):
                            continue
                        if not _levels_match(existing, rec):
                            continue
                        existing_bbox = _opening_bounds(existing)
                        if not _bbox_overlap(existing_bbox, panel_bbox):
                            continue
                        existing_area = _opening_area_m2(existing)
                        if existing_area is not None and panel_area is not None:
                            area_diff = abs(existing_area - panel_area)
                            if area_diff > max(existing_area, panel_area) * PANEL_AREA_REL_TOL and area_diff > PANEL_AREA_ABS_TOL_M2:
                                continue
                        existing_centroid = _opening_centroid(existing)
                        if panel_centroid and existing_centroid:
                            dist = _centroid_distance(panel_centroid, existing_centroid)
                            if dist is not None and dist > PANEL_CENTROID_TOL_M:
                                continue
                        skip_panel = True
                        break
                    if skip_panel:
                        continue
            key = _opening_bbox_key(rec)
            if key is None:
                openings.append(rec)
                continue
            existing_idx = bbox_map.get(key)
            if existing_idx is not None:
                existing = openings[existing_idx]
                if existing.get("opening_type") == "door" and rec.get("opening_type") != "door":
                    continue
                if rec.get("opening_type") == "door" and existing.get("opening_type") != "door":
                    openings[existing_idx] = rec
                    continue
                # одинаковый footprint и уровень — считаем дублем и пропускаем
                continue
            bbox_map[key] = len(openings)
            openings.append(rec)

    for src in doors:
        _append(src, "door")
    for src in windows:
        otype = "curtain_panel" if src.get("is_curtain_panel") else "window"
        _append(src, otype)

    return openings

# ---------------- UI Components ----------------
class TypeSelectionDialog(Form):
    def __init__(self, title, data_rows):
        Form.__init__(self)
        self.Text = title
        self.StartPosition = FormStartPosition.CenterScreen
        self.ClientSize = Size(1200, 700)
        
        self.grid = DataGridView()
        self.grid.Dock = DockStyle.Fill
        self.grid.AllowUserToAddRows = False
        self.grid.AllowUserToDeleteRows = False
        self.grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.AllCells
        self.grid.RowHeadersVisible = False
        # self.grid.SelectionMode = DataGridViewSelectionMode.FullRowSelect
        
        # Колонки
        col_sel = DataGridViewCheckBoxColumn()
        col_sel.HeaderText = "Выбрать"
        col_sel.Width = 80
        self.grid.Columns.Add(col_sel)
        
        col_cat = DataGridViewTextBoxColumn()
        col_cat.HeaderText = "Категория"
        col_cat.Width = 120
        self.grid.Columns.Add(col_cat)
        
        col_type = DataGridViewTextBoxColumn()
        col_type.HeaderText = "Тип"
        col_type.Width = 200
        self.grid.Columns.Add(col_type)
        
        col_count = DataGridViewTextBoxColumn()
        col_count.HeaderText = "Количество"
        col_count.Width = 80
        self.grid.Columns.Add(col_count)
        
        # Добавляем колонки для основных параметров типа
        param_columns = set()
        for row in data_rows:
            for param_name in row.get("type_params", {}):
                param_columns.add(param_name)
        
        param_columns = sorted(list(param_columns))
        for param_name in param_columns[:10]:  # Ограничиваем количество колонок
            col_param = DataGridViewTextBoxColumn()
            col_param.HeaderText = param_name
            col_param.Width = 120
            self.grid.Columns.Add(col_param)
        
        # Заполняем данными
        for row in data_rows:
            count = row.get("count", 0)
            values = [False, row["category"], row["type_name"], str(count)]
            type_params = row.get("type_params", {})
            for param_name in param_columns[:10]:
                param_data = type_params.get(param_name, {})
                display_value = param_data.get("display", "")
                values.append(display_value)
            self.grid.Rows.Add(*values)
        
        # Кнопки
        panel = FlowLayoutPanel()
        panel.FlowDirection = FlowDirection.LeftToRight
        panel.Dock = DockStyle.Bottom
        panel.Height = 48
        
        btn_all = Button()
        btn_all.Text = "Выбрать все"
        btn_all.Width = 120
        btn_all.Click += self._select_all
        
        btn_clear = Button()
        btn_clear.Text = "Очистить"
        btn_clear.Width = 100
        btn_clear.Click += self._clear_all
        
        btn_ok = Button()
        btn_ok.Text = "Завершить выбор"
        btn_ok.Width = 150
        btn_ok.Click += self._ok
        
        btn_cancel = Button()
        btn_cancel.Text = "Отмена"
        btn_cancel.Width = 100
        btn_cancel.Click += self._cancel
        
        panel.Controls.Add(btn_all)
        panel.Controls.Add(btn_clear)
        panel.Controls.Add(btn_ok)
        panel.Controls.Add(btn_cancel)
        
        self.Controls.Add(self.grid)
        self.Controls.Add(panel)
        self.selected = []
    
    def _select_all(self, sender, args):
        for i in range(self.grid.Rows.Count):
            self.grid.Rows[i].Cells[0].Value = True
    
    def _clear_all(self, sender, args):
        for i in range(self.grid.Rows.Count):
            self.grid.Rows[i].Cells[0].Value = False
    
    def _ok(self, sender, args):
        sel = []
        for i in range(self.grid.Rows.Count):
            if bool(self.grid.Rows[i].Cells[0].Value):
                cat = str(self.grid.Rows[i].Cells[1].Value or "")
                typ = str(self.grid.Rows[i].Cells[2].Value or "")
                count = str(self.grid.Rows[i].Cells[3].Value or "0")
                sel.append({"category": cat, "type_name": typ, "count": count})
        
        if not sel:
            TaskDialog.Show("Выбор типов", "Ничего не выбрано.")
            return
        
        self.selected = sel
        self.DialogResult = DialogResult.OK
        self.Close()
    
    def _cancel(self, sender, args):
        self.DialogResult = DialogResult.Cancel
        self.Close()

class MainExportForm(Form):
    def __init__(self):
        Form.__init__(self)
        self.Text = "Экспорт данных из Revit"
        self.StartPosition = FormStartPosition.CenterScreen
        self.ClientSize = Size(500, 300)
        
        # Основная панель - используем простой Panel с вертикальной компоновкой
        main_panel = Panel()
        main_panel.Dock = DockStyle.Fill
        main_panel.AutoScroll = True
        
        y_pos = 20
        
        # Выбор Design Option
        design_option_label = Label()
        design_option_label.Text = "Design Option:"
        design_option_label.Font = Font("Microsoft Sans Serif", 10, FontStyle.Regular)
        design_option_label.Location = System.Drawing.Point(20, y_pos)
        design_option_label.Size = Size(100, 25)
        main_panel.Controls.Add(design_option_label)
        
        self.design_option_combo = System.Windows.Forms.ComboBox()
        self.design_option_combo.Location = System.Drawing.Point(130, y_pos)
        self.design_option_combo.Size = Size(200, 25)
        self.design_option_combo.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList
        
        # Заполняем Design Options
        self.design_options_list = self._get_design_options()
        for opt in self.design_options_list:
            self.design_option_combo.Items.Add(opt["name"])
        if self.design_options_list:
            self.design_option_combo.SelectedIndex = 0
        
        main_panel.Controls.Add(self.design_option_combo)
        y_pos += 40
        
        # Чекбокс для помещений
        self.cb_rooms = CheckBox()
        self.cb_rooms.Text = "Помещения"
        self.cb_rooms.Checked = True
        self.cb_rooms.Font = Font("Microsoft Sans Serif", 10, FontStyle.Regular)
        self.cb_rooms.Location = System.Drawing.Point(20, y_pos)
        self.cb_rooms.Size = Size(200, 25)
        main_panel.Controls.Add(self.cb_rooms)
        y_pos += 40
        
        # Панель для остекления
        glazing_panel = Panel()
        glazing_panel.Location = System.Drawing.Point(20, y_pos)
        glazing_panel.Size = Size(450, 30)
        
        self.cb_glazing = CheckBox()
        self.cb_glazing.Text = "Остекление"
        self.cb_glazing.Font = Font("Microsoft Sans Serif", 10, FontStyle.Regular)
        self.cb_glazing.Location = System.Drawing.Point(0, 5)
        self.cb_glazing.Size = Size(100, 25)
        self.cb_glazing.CheckedChanged += self._glazing_changed
        
        self.btn_select_glazing = Button()
        self.btn_select_glazing.Text = "Выбрать типы остекления"
        self.btn_select_glazing.Location = System.Drawing.Point(110, 2)
        self.btn_select_glazing.Size = Size(200, 25)
        self.btn_select_glazing.Enabled = False
        self.btn_select_glazing.Click += self._select_glazing_types
        
        self.lbl_glazing_status = Label()
        self.lbl_glazing_status.Text = "✗"
        self.lbl_glazing_status.ForeColor = Color.Red
        self.lbl_glazing_status.Font = Font("Microsoft Sans Serif", 12, FontStyle.Bold)
        self.lbl_glazing_status.Location = System.Drawing.Point(320, 5)
        self.lbl_glazing_status.Size = Size(20, 20)
        
        glazing_panel.Controls.Add(self.cb_glazing)
        glazing_panel.Controls.Add(self.btn_select_glazing)
        glazing_panel.Controls.Add(self.lbl_glazing_status)
        main_panel.Controls.Add(glazing_panel)
        y_pos += 40
        
        # Панель для дверей
        doors_panel = Panel()
        doors_panel.Location = System.Drawing.Point(20, y_pos)
        doors_panel.Size = Size(450, 30)
        
        self.cb_doors = CheckBox()
        self.cb_doors.Text = "Двери"
        self.cb_doors.Font = Font("Microsoft Sans Serif", 10, FontStyle.Regular)
        self.cb_doors.Location = System.Drawing.Point(0, 5)
        self.cb_doors.Size = Size(100, 25)
        self.cb_doors.CheckedChanged += self._doors_changed
        
        self.btn_select_doors = Button()
        self.btn_select_doors.Text = "Выбрать типы дверей"
        self.btn_select_doors.Location = System.Drawing.Point(110, 2)
        self.btn_select_doors.Size = Size(200, 25)
        self.btn_select_doors.Enabled = False
        self.btn_select_doors.Click += self._select_doors_types
        
        self.lbl_doors_status = Label()
        self.lbl_doors_status.Text = "✗"
        self.lbl_doors_status.ForeColor = Color.Red
        self.lbl_doors_status.Font = Font("Microsoft Sans Serif", 12, FontStyle.Bold)
        self.lbl_doors_status.Location = System.Drawing.Point(320, 5)
        self.lbl_doors_status.Size = Size(20, 20)
        
        doors_panel.Controls.Add(self.cb_doors)
        doors_panel.Controls.Add(self.btn_select_doors)
        doors_panel.Controls.Add(self.lbl_doors_status)
        main_panel.Controls.Add(doors_panel)
        y_pos += 60
        
        # Кнопки управления
        buttons_panel = Panel()
        buttons_panel.Location = System.Drawing.Point(20, y_pos)
        buttons_panel.Size = Size(450, 40)
        
        self.btn_export = Button()
        self.btn_export.Text = "Экспортировать"
        self.btn_export.Location = System.Drawing.Point(0, 10)
        self.btn_export.Size = Size(150, 30)
        self.btn_export.Click += self._export
        
        btn_cancel = Button()
        btn_cancel.Text = "Отмена"
        btn_cancel.Location = System.Drawing.Point(160, 10)
        btn_cancel.Size = Size(100, 30)
        btn_cancel.Click += self._cancel
        
        buttons_panel.Controls.Add(self.btn_export)
        buttons_panel.Controls.Add(btn_cancel)
        main_panel.Controls.Add(buttons_panel)
        
        self.Controls.Add(main_panel)
        
        # Данные выбранных типов
        self.selected_glazing = []
        self.selected_doors = []
        self.selected_design_option_id = None
        
        # Подключаем обработчик изменения Design Option после создания всех элементов
        self.design_option_combo.SelectedIndexChanged += self._design_option_changed
        
    def _get_design_options(self):
        """Получает список Design Options из проекта"""
        options = [{"name": "Main Model", "id": None}]  # Основная модель
        
        try:
            collector = DB.FilteredElementCollector(doc).OfClass(DB.DesignOption)
            for opt in collector:
                options.append({
                    "name": opt.Name,
                    "id": opt.Id.IntegerValue
                })
        except Exception as ex:
            logger.warn("Failed to get design options: {}".format(ex))
        
        return options
        
    def _design_option_changed(self, sender, args):
        """Обработчик изменения Design Option - сбрасывает выбранные типы"""
        # Обновляем ID выбранной Design Option
        if self.design_option_combo.SelectedIndex > 0:
            if self.design_option_combo.SelectedIndex < len(self.design_options_list):
                self.selected_design_option_id = self.design_options_list[self.design_option_combo.SelectedIndex]["id"]
        else:
            self.selected_design_option_id = None
            
        # Сбрасываем выбранные типы, так как количества могли измениться
        # Проверяем, что элементы интерфейса существуют
        if hasattr(self, 'selected_glazing'):
            self.selected_glazing = []
        if hasattr(self, 'selected_doors'):
            self.selected_doors = []
        if hasattr(self, 'lbl_glazing_status'):
            self.lbl_glazing_status.Text = "✗"
            self.lbl_glazing_status.ForeColor = Color.Red
        if hasattr(self, 'lbl_doors_status'):
            self.lbl_doors_status.Text = "✗"
            self.lbl_doors_status.ForeColor = Color.Red
    
    def _glazing_changed(self, sender, args):
        self.btn_select_glazing.Enabled = self.cb_glazing.Checked
        if not self.cb_glazing.Checked:
            self.selected_glazing = []
            self.lbl_glazing_status.Text = "✗"
            self.lbl_glazing_status.ForeColor = Color.Red
    
    def _doors_changed(self, sender, args):
        self.btn_select_doors.Enabled = self.cb_doors.Checked
        if not self.cb_doors.Checked:
            self.selected_doors = []
            self.lbl_doors_status.Text = "✗"
            self.lbl_doors_status.ForeColor = Color.Red
    
    def _select_glazing_types(self, sender, args):
        glazing_data = _gather_glazing_data(self.selected_design_option_id)
        if not glazing_data:
            TaskDialog.Show("Остекление", "Типы остекления не найдены.")
            return
        
        dialog = TypeSelectionDialog("Выбор типов остекления", glazing_data)
        if dialog.ShowDialog() == DialogResult.OK:
            self.selected_glazing = dialog.selected
            self.lbl_glazing_status.Text = "✓"
            self.lbl_glazing_status.ForeColor = Color.Green
        dialog.Dispose()
    
    def _select_doors_types(self, sender, args):
        doors_data = _gather_doors_data(self.selected_design_option_id)
        if not doors_data:
            TaskDialog.Show("Двери", "Типы дверей не найдены.")
            return
        
        dialog = TypeSelectionDialog("Выбор типов дверей", doors_data)
        if dialog.ShowDialog() == DialogResult.OK:
            self.selected_doors = dialog.selected
            self.lbl_doors_status.Text = "✓"
            self.lbl_doors_status.ForeColor = Color.Green
        dialog.Dispose()
    
    def _export(self, sender, args):
        # Проверяем, что что-то выбрано
        if not self.cb_rooms.Checked and not (self.cb_glazing.Checked and self.selected_glazing) and not (self.cb_doors.Checked and self.selected_doors):
            TaskDialog.Show("Экспорт", "Выберите что экспортировать.")
            return
        
        if self.cb_glazing.Checked and not self.selected_glazing:
            TaskDialog.Show("Экспорт", "Выберите типы остекления.")
            return
        
        if self.cb_doors.Checked and not self.selected_doors:
            TaskDialog.Show("Экспорт", "Выберите типы дверей.")
            return
            
        # Получаем выбранную Design Option
        if self.design_option_combo.SelectedIndex > 0:  # 0 - это "Main Model"
            design_options = self._get_design_options()
            if self.design_option_combo.SelectedIndex < len(design_options):
                self.selected_design_option_id = design_options[self.design_option_combo.SelectedIndex]["id"]
        else:
            self.selected_design_option_id = None
        
        self.DialogResult = DialogResult.OK
        self.Close()
    
    def _cancel(self, sender, args):
        self.DialogResult = DialogResult.Cancel
        self.Close()

def _pick_save_path():
    try:
        dlg = SaveFileDialog()
        dlg.Filter = "JSON files (*.json)|*.json|All files (*.*)|*.*"
        dlg.FileName = "revit_export.json"
        if dlg.ShowDialog() == DialogResult.OK:
            return dlg.FileName
        return None
    except:
        base = _user_model_path(doc)
        folder = os.path.dirname(base) if base else os.path.expanduser("~/Desktop")
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        return os.path.join(folder, "revit_export_{}.json".format(ts))

def _room_brief(r):
    if not r: return None
    return {"id": r.Id.IntegerValue, "unique_id": r.UniqueId,
            "number": _room_number(r), "name": _room_name(r),
            "level_id": _safe_level_id(r)}

# ---------------- Export logic ----------------
def _element_matches_design_option(el, design_option_id):
    """Проверяет, принадлежит ли элемент к указанной Design Option"""
    if design_option_id is None:
        # Main Model - элемент не должен принадлежать к Design Option
        return getattr(el, 'DesignOption', None) is None
    else:
        # Проверяем, что элемент принадлежит к указанной Design Option
        el_design_option = getattr(el, 'DesignOption', None)
        if el_design_option is None:
            return False
        return el_design_option.Id.IntegerValue == design_option_id

def _export_elements_by_selection(selection, category_key, design_option_id=None):
    """Экспорт элементов по выбранным типам"""
    results = []
    
    # Группируем по категориям
    types_by_category = {}
    for sel in selection:
        cat = sel["category"]
        typ = sel["type_name"]
        if cat not in types_by_category:
            types_by_category[cat] = set()
        types_by_category[cat].add(typ)
    
    for sdoc, linkinst, T in _docs_sources(doc):
        for category, type_names in types_by_category.items():
            if category == "Windows":
                col = DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_Windows).WhereElementIsNotElementType()
            elif category == "Doors":
                col = DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_Doors).WhereElementIsNotElementType()
            elif category == "Curtain Panels":
                col = DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_CurtainWallPanels).WhereElementIsNotElementType()
            elif category == "Walls" or category == "Curtain Walls":
                col = DB.FilteredElementCollector(sdoc).OfClass(DB.Wall)
            else:
                continue
            
            for el in col:
                try:
                    # Проверяем Design Option
                    if not _element_matches_design_option(el, design_option_id):
                        continue
                        
                    tname = _get_type_name(el, sdoc)
                    if tname not in type_names:
                        continue
                    
                    bbox = _bbox_record(el, T)
                    if not bbox:
                        continue
                    
                    # Создаем footprint для визуализации
                    footprint = _create_element_footprint(el, T, category)
                    
                    rec = {
                        "id": getattr(el.Id, "IntegerValue", None),
                        "unique_id": getattr(el, "UniqueId", None),
                        "category": category,
                        "type_name": tname,
                        "bbox": bbox,
                        "footprint": footprint,
                        "params": _collect_all_params(el, sdoc)
                    }
                    
                    if linkinst is not None:
                        rec["in_link"] = {
                            "link_instance_id": linkinst.Id.IntegerValue,
                            "link_doc_title": sdoc.Title,
                            "link_doc_full_path": _user_model_path(sdoc)
                        }
                    
                    results.append(rec)
                except Exception as ex:
                    logger.warn("Export issue for {}: {}".format(category, ex))
    
    return results

def _bbox_record(el, T=None):
    bb=el.get_BoundingBox(None)
    if not bb: return None
    pmin=_of_point(T,bb.Min); pmax=_of_point(T,bb.Max)
    c=DB.XYZ((pmin.X+pmax.X)*0.5,(pmin.Y+pmax.Y)*0.5,(pmin.Z+pmax.Z)*0.5)
    return {
        "min_ft":[_roundf(pmin.X,4),_roundf(pmin.Y,4),_roundf(pmin.Z,4)],
        "max_ft":[_roundf(pmax.X,4),_roundf(pmax.Y,4),_roundf(pmax.Z,4)],
        "min_m":[_roundf(pmin.X*FT_TO_M,3),_roundf(pmin.Y*FT_TO_M,3),_roundf(pmin.Z*FT_TO_M,3)],
        "max_m":[_roundf(pmax.X*FT_TO_M,3),_roundf(pmax.Y*FT_TO_M,3),_roundf(pmax.Z*FT_TO_M,3)],
        "center_ft":[_roundf(c.X,4),_roundf(c.Y,4),_roundf(c.Z,4)],
        "center_m":[_roundf(c.X*FT_TO_M,3),_roundf(c.Y*FT_TO_M,3),_roundf(c.Z*FT_TO_M,3)]
    }

def _door_footprint(el, T=None):
    """Generate an oriented rectangle footprint for a door family instance."""

    try:
        if not isinstance(el, DB.FamilyInstance):
            return None

        center = _of_point(T, _bb_center(el))
        facing = _of_vector(T, getattr(el, "FacingOrientation", None))
        hand   = _of_vector(T, getattr(el, "HandOrientation", None))
        if hand is None and facing is not None:
            hand = _cross(DB.XYZ.BasisZ, facing)
        if center is None or facing is None or hand is None:
            return None

        width_ft = _get_double_param_by(
            el,
            ['DOOR_WIDTH', 'FAMILY_WIDTH_PARAM', 'WIDTH'],
            ['Width', 'Ширина', 'Ширина проема', 'Ширина проёма']
        )
        width_ft = abs(float(width_ft)) if width_ft else None

        host_thk = None
        try:
            host = getattr(el, "Host", None)
            if isinstance(host, DB.Wall):
                host_thk = getattr(host, "Width", None)
        except Exception:
            host_thk = None

        depth_ft = host_thk
        if depth_ft in (None, 0.0):
            depth_ft = _get_double_param_by(
                el,
                ['DOOR_THICKNESS', 'FAMILY_THICKNESS_PARAM', 'THICKNESS'],
                ['Thickness', 'Толщина']
            )
        depth_ft = abs(float(depth_ft)) if depth_ft else None

        bbox_size = _bb_size(el, T)
        if not width_ft and bbox_size:
            width_ft = max(bbox_size[0], bbox_size[1])
        if not depth_ft and bbox_size:
            depth_ft = min(bbox_size[0], bbox_size[1])

        if not width_ft or not depth_ft or width_ft <= 1e-6 or depth_ft <= 1e-6:
            return None

        ring = _rect_footprint(center, hand, facing, width_ft, depth_ft)
        if not ring:
            return None

        footprint = _footprint_record(ring)
        if not footprint:
            return None

        area_ft2 = width_ft * depth_ft
        footprint.update({
            "width_ft": _roundf(width_ft, 4),
            "height_ft": _roundf(depth_ft, 4),
            "width_m": _roundf(width_ft * FT_TO_M, 3),
            "height_m": _roundf(depth_ft * FT_TO_M, 3),
            "real_width_ft": _roundf(width_ft, 4),
            "real_width_m": _roundf(width_ft * FT_TO_M, 3),
            "real_height_ft": _roundf(depth_ft, 4),
            "real_height_m": _roundf(depth_ft * FT_TO_M, 3),
            "area_ft2": _roundf(area_ft2, 4),
            "area_m2": _roundf(area_ft2 * FT2_TO_M2, 3)
        })

        door_height_ft = _get_double_param_by(
            el,
            ['DOOR_HEIGHT', 'FAMILY_HEIGHT_PARAM', 'HEIGHT'],
            ['Height', 'Высота', 'Высота проема', 'Высота проёма']
        )
        if door_height_ft:
            footprint["door_height_ft"] = _roundf(door_height_ft, 4)
            footprint["door_height_m"] = _roundf(door_height_ft * FT_TO_M, 3)

        return footprint
    except Exception:
        return None

def _create_element_footprint(el, T=None, category=""):
    """Создает footprint элемента для визуализации в SESS_geometry"""
    try:
        bb = el.get_BoundingBox(None)
        if not bb:
            return None

        pmin = _of_point(T, bb.Min)
        pmax = _of_point(T, bb.Max)
        center = DB.XYZ((pmin.X + pmax.X) * 0.5, (pmin.Y + pmax.Y) * 0.5, (pmin.Z + pmax.Z) * 0.5)

        cat_lower = str(category or "").strip().lower()
        if cat_lower == "doors":
            oriented = _door_footprint(el, T)
            if oriented:
                return oriented

        # Получаем реальные размеры элемента из параметров
        width_ft = None
        height_ft = None

        if cat_lower == "doors":
            # Для дверей извлекаем ТОЛЬКО ширину из параметров (высота не нужна для плана)
            width_ft = _get_double_param_by(el,
                ['DOOR_WIDTH', 'FAMILY_WIDTH_PARAM', 'WIDTH'],
                ['Width', 'Ширина', 'Ширина проема', 'Ширина проёма'])
            # Для плана используем толщину стены или фиксированную глубину двери
            height_ft = _get_double_param_by(el,
                ['DOOR_THICKNESS', 'FAMILY_THICKNESS_PARAM', 'THICKNESS'],
                ['Thickness', 'Толщина'])
            if not height_ft:
                # Если толщина не найдена, используем стандартную толщину двери
                height_ft = 0.25  # ~7.5 см - стандартная толщина двери

        elif cat_lower == "windows":
            # Для окон аналогично
            width_ft = _get_double_param_by(el,
                ['WINDOW_WIDTH', 'FAMILY_WIDTH_PARAM', 'WIDTH'],
                ['Width', 'Ширина'])
            height_ft = _get_double_param_by(el,
                ['WINDOW_HEIGHT', 'FAMILY_HEIGHT_PARAM', 'HEIGHT'],
                ['Height', 'Высота'])

        elif cat_lower == "curtain panels":
            # Для панелей используем bbox, но ограничиваем размеры
            bbox_width = abs(pmax.X - pmin.X)
            bbox_height = abs(pmax.Y - pmin.Y)
            width_ft = min(bbox_width, 3.0)
            height_ft = min(bbox_height, 3.0)
            
        # Если не удалось получить размеры из параметров, используем bbox
        if width_ft is None or height_ft is None:
            width_ft = abs(pmax.X - pmin.X)
            height_ft = abs(pmax.Y - pmin.Y)
            
        # Минимальные размеры для видимости
        min_size_ft = 0.3  # ~9 см минимум
        if width_ft < min_size_ft:
            width_ft = min_size_ft
        if height_ft < min_size_ft:
            height_ft = min_size_ft
            
        # Максимальные размеры для разумности
        max_size_ft = 10.0  # ~3 метра максимум
        if width_ft > max_size_ft:
            width_ft = max_size_ft
        if height_ft > max_size_ft:
            height_ft = max_size_ft
            
        # Используем реальные размеры элемента как есть
        plan_width = width_ft
        plan_height = height_ft
            
        # Создаем прямоугольный контур
        half_w = plan_width * 0.5
        half_h = plan_height * 0.5
        
        # Точки прямоугольника в футах
        pts_ft = [
            [center.X - half_w, center.Y - half_h],
            [center.X + half_w, center.Y - half_h], 
            [center.X + half_w, center.Y + half_h],
            [center.X - half_w, center.Y + half_h],
            [center.X - half_w, center.Y - half_h]  # замыкаем контур
        ]
        
        # Конвертируем в метры
        pts_m = [[_roundf(x * FT_TO_M, 3), _roundf(y * FT_TO_M, 3)] for x, y in pts_ft]
        
        return {
            "xy_ft": pts_ft,
            "xy_m": pts_m,
            "width_ft": _roundf(plan_width, 4),
            "height_ft": _roundf(plan_height, 4),
            "width_m": _roundf(plan_width * FT_TO_M, 3),
            "height_m": _roundf(plan_height * FT_TO_M, 3),
            "area_ft2": _roundf(plan_width * plan_height, 4),
            "area_m2": _roundf(plan_width * plan_height * FT2_TO_M2, 3),
            "real_width_ft": _roundf(width_ft, 4) if width_ft else None,
            "real_height_ft": _roundf(height_ft, 4) if height_ft else None,
            "real_width_m": _roundf(width_ft * FT_TO_M, 3) if width_ft else None,
            "real_height_m": _roundf(height_ft * FT_TO_M, 3) if height_ft else None
        }
        
    except Exception as ex:
        logger.warn("Footprint creation failed: {}".format(ex))
        return None

def _get_type_name(el, sdoc):
    try:
        if isinstance(el, DB.Wall):
            wt = sdoc.GetElement(el.GetTypeId())
            return wt.Name if wt else ""
        if isinstance(el, DB.FamilyInstance):
            sym = el.Symbol
            if sym:
                n = sym.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
                return n.AsString() if n else getattr(sym, "Name", "")
    except: pass
    return ""

def _meta(levels_map):
    host_full = _user_model_path(doc)
    return {
        "doc_title": doc.Title,
        "doc_full_path": host_full,
        "doc_dir": os.path.dirname(host_full) if host_full else "",
        "export_time": datetime.utcnow().isoformat(),
        "links": [{"instance_id": li.Id.IntegerValue,
                   "doc_title": ldoc.Title,
                   "doc_full_path": _user_model_path(ldoc)}
                  for ldoc, li, _ in _docs_sources(doc) if li is not None]
    }

# ---------- main ----------
def main():
    if doc.IsLinked:
        TaskDialog.Show("REVIT_DATA_EXPORT", "Откройте основную модель, а не связанный файл.")
        return
    
    # Показываем основное окно
    form = MainExportForm()
    if form.ShowDialog() != DialogResult.OK:
        return
    
    # Собираем данные для экспорта
    levels_map = _all_levels_map(doc)
    levels_list = [{"id": k, "name": v["name"],
                    "elevation_ft": round(v["elevation_ft"], 4),
                    "elevation_m": round(v["elevation_m"], 3)}
                   for k, v in sorted(levels_map.items(), key=lambda kv: kv[1]["elevation_ft"])]

    rooms = []
    glazing = []
    doors = []
    
    # Экспорт помещений
    if form.cb_rooms.Checked:
        rooms = _collect_rooms(doc, DB.SpatialElementBoundaryLocation.Finish, levels_map)
    
    # Экспорт остекления
    if form.cb_glazing.Checked and form.selected_glazing:
        glazing = _export_elements_by_selection(form.selected_glazing, "glazing", form.selected_design_option_id)
    
    # Экспорт дверей
    if form.cb_doors.Checked and form.selected_doors:
        doors = _export_elements_by_selection(form.selected_doors, "doors", form.selected_design_option_id)
    
    # Формируем результат
    out = {
        "version": "revit-export-v2",
        "units_note": "Internal length units are feet. Geometry exported as ft and m.",
        "meta": _meta(levels_map),
        "levels": levels_list,
        "filters": {
            "rooms_enabled": form.cb_rooms.Checked,
            "glazing_types": form.selected_glazing if form.cb_glazing.Checked else [],
            "doors_types": form.selected_doors if form.cb_doors.Checked else [],
            "design_option_id": form.selected_design_option_id
        },
        "rooms": rooms,
        "glazing": glazing,
        "doors": doors
    }
    
    # Сохраняем файл
    path = _pick_save_path()
    if not path:
        TaskDialog.Show("REVIT_DATA_EXPORT", "Путь для сохранения не выбран.")
        return
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    
    TaskDialog.Show("REVIT_DATA_EXPORT",
                    "Экспорт завершен:\n{}\n\nПомещений: {}\nОстекление: {}\nДвери: {}".format(
                        path, len(rooms), len(glazing), len(doors)
                    ))
    
    form.Dispose()

if __name__ == "__main__":
    try: main()
    except Exception as ex:
        TaskDialog.Show("REVIT_DATA_EXPORT", "Ошибка экспорта:\n{}".format(ex))
