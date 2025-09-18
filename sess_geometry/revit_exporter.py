#! python3
# -*- coding: utf-8 -*-
# CPython3 + pyRevit (WinForms), без pyrevit.forms

from pyrevit import revit, DB, script
from Autodesk.Revit.UI import TaskDialog
from System.Windows.Forms import (
    Form, DataGridView, DataGridViewCheckBoxColumn, DataGridViewTextBoxColumn,
    Button, FlowLayoutPanel, DockStyle, SaveFileDialog, DialogResult, FormStartPosition,
    FlowDirection, DataGridViewAutoSizeColumnsMode, Label, CheckBox, TableLayoutPanel,
    ColumnStyle, SizeType, ComboBox, ComboBoxStyle
)
from System.Drawing import Size, Color, ContentAlignment
import json, os, re
from math import sqrt
from datetime import datetime

doc = revit.doc
logger = script.get_logger()

# ===== настройки/пороговые =====
FT_TO_M = 0.3048
FT2_TO_M2 = FT_TO_M * FT_TO_M
TOL_PT_FT = 1e-4
TOL_Z_FT  = 1e-3
DECIMATE_GEOM = True
DECIM_EPS_FT  = 0.02
ROUND_COORDS  = True
ROUND_M_DEC   = 3
ROUND_FT_DEC  = 4

# валидные диапазоны (в футах)
W_MIN_FT, W_MAX_FT = 1.0, 20.0        # ширина дверей/окон 0.3–6 м
H_MIN_FT, H_MAX_FT = 5.0, 40.0        # высота 1.5–12 м
THK_MIN_FT, THK_MAX_FT = 0.15/FT_TO_M, 1.0/FT_TO_M  # 0.15–1.0 м

# ===== векторная математика =====
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
def _flatten_xy(vec):
    try:
        flat = DB.XYZ(vec.X, vec.Y, 0.0)
        mag2 = flat.X * flat.X + flat.Y * flat.Y
        if mag2 <= 1e-12:
            return None
        inv = 1.0 / sqrt(mag2)
        return DB.XYZ(flat.X * inv, flat.Y * inv, 0.0)
    except:
        return None
def _roundf(x, dec): return round(x, dec) if x is not None else None
def _xy_ft_from_pts(pts):
    if ROUND_COORDS: return [[_roundf(p.X, ROUND_FT_DEC), _roundf(p.Y, ROUND_FT_DEC)] for p in pts]
    return [[p.X, p.Y] for p in pts]
def _xy_m_from_pts(pts):
    if ROUND_COORDS: return [[_roundf(p.X*FT_TO_M, ROUND_M_DEC), _roundf(p.Y*FT_TO_M, ROUND_M_DEC)] for p in pts]
    return [[p.X*FT_TO_M, p.Y*FT_TO_M] for p in pts]

# ===== параметры =====
def _param_record(p):
    try:
        d=p.Definition; name=d.Name if d else None
        if not name: return None
        st=p.StorageType; vs=p.AsValueString(); raw=None
        if st==DB.StorageType.String:   raw=p.AsString();  vs=raw if vs is None else vs
        elif st==DB.StorageType.Integer: raw=p.AsInteger(); vs=str(raw) if vs is None else vs
        elif st==DB.StorageType.Double:  raw=p.AsDouble();  vs="" if vs is None else vs
        elif st==DB.StorageType.ElementId:
            eid=p.AsElementId(); raw=eid.IntegerValue if eid else None
            vs=(str(raw) if raw is not None else "") if vs is None else vs
        else: vs="" if vs is None else vs
        return name, {"display":vs, "raw_internal":raw,
                      "id": getattr(p,"Id",None).IntegerValue if getattr(p,"Id",None) else None,
                      "is_shared": getattr(p,"IsShared",False),
                      "guid": str(getattr(p,"GUID",None)) if getattr(p,"IsShared",False) else None,
                      "storage_type": str(p.StorageType)}
    except: return None

def _collect_params_block(el):
    out={}
    try:
        for p in el.Parameters:
            kv=_param_record(p)
            if kv: out[kv[0]]=kv[1]
    except: pass
    return out

def _collect_all_params(el, doc_):
    res={"instance":{}, "type":{}}
    try: res["instance"]=_collect_params_block(el)
    except: pass
    try:
        tid=el.GetTypeId()
        if tid and tid.IntegerValue!=-1:
            t_el=doc_.GetElement(tid)
            if t_el: res["type"]=_collect_params_block(t_el)
    except: pass
    return res

# ===== документы и линки =====
def _user_model_path(document):
    try:
        mp=document.GetWorksharingCentralModelPath()
    except: mp=None
    if not mp:
        try: mp=document.GetModelPath()
        except: mp=None
    if mp:
        try: return DB.ModelPathUtils.ConvertModelPathToUserVisiblePath(mp)
        except: pass
    return document.PathName or ""

def _doc_key(document): return _user_model_path(document) or document.Title

def _docs_sources(document):
    src=[(document, None, DB.Transform.Identity)]
    for li in DB.FilteredElementCollector(document).OfClass(DB.RevitLinkInstance):
        ldoc=li.GetLinkDocument()
        if ldoc: src.append((ldoc, li, li.GetTransform()))
    return src

def _all_levels_map(document):
    m={}
    for lv in DB.FilteredElementCollector(document).OfClass(DB.Level):
        elev=float(lv.Elevation)
        m[lv.Id.IntegerValue]={"name":lv.Name,"elevation_ft":elev,"elevation_m":elev*FT_TO_M}
    return m

# ===== Rooms (как раньше, с back-compat полями) =====
def _signed_area_xy_ft(pts):
    a=0.0
    for i in range(len(pts)-1):
        x1,y1=pts[i].X,pts[i].Y; x2,y2=pts[i+1].X,pts[i+1].Y
        a+=x1*y2 - x2*y1
    return 0.5*a
def _close_ring_if_needed(pts):
    if len(pts)>=2 and pts[0].DistanceTo(pts[-1])>TOL_PT_FT: pts.append(pts[0])
    return pts
def _dedup_pts(pts):
    out=[]; last=None
    for p in pts:
        if last is None or p.DistanceTo(last)>TOL_PT_FT: out.append(p); last=p
    return out
def _dist_point_seg_xy(p,a,b):
    ax,ay,bx,by,px,py=a.X,a.Y,b.X,b.Y,p.X,p.Y
    vx,vy=bx-ax,by-ay; wx,wy=px-ax,py-ay
    c1=vx*wx+vy*wy; c2=vx*vx+vy*vy
    t=0.0 if c2<=1e-12 else max(0.0,min(1.0,c1/c2))
    qx,qy=ax+t*vx,ay+t*vy; dx,dy=px-qx,py-qy
    return sqrt(dx*dx+dy*dy)
def _rdp_xy(pts,eps):
    if not DECIMATE_GEOM or len(pts)<5: return pts
    keep=[False]*len(pts); keep[0]=keep[-1]=True; st=[(0,len(pts)-1)]
    while st:
        i,j=st.pop(); a,b=pts[i],pts[j]; md=-1; idx=None
        for k in range(i+1,j):
            d=_dist_point_seg_xy(pts[k],a,b)
            if d>md: md,idx=d,k
        if md>eps and idx is not None:
            keep[idx]=True; st.append((i,idx)); st.append((idx,j))
    return [p for i,p in enumerate(pts) if keep[i]]
def _ring_from_segments(segs,T=None):
    pts=[]
    for s in segs:
        for pt in s.GetCurve().Tessellate():
            hp=_of_point(T,pt)
            if not pts or hp.DistanceTo(pts[-1])>TOL_PT_FT: pts.append(hp)
    return _rdp_xy(_close_ring_if_needed(_dedup_pts(pts)), DECIM_EPS_FT)
def _loops_from_boundary(seg_lists,T=None):
    loops=[]; 
    if not seg_lists: return None,[]
    for segs in seg_lists:
        p=_ring_from_segments(segs,T)
        if len(p)>=4: loops.append(p)
    if not loops: return None,[]
    areas=[abs(_signed_area_xy_ft(r)) for r in loops]
    outer=loops[areas.index(max(areas))]; inn=[r for r in loops if r is not outer]
    return outer,inn
def _room_name(r):
    try: 
        p=r.get_Parameter(DB.BuiltInParameter.ROOM_NAME); nm=p.AsString() if p else None
        return nm or getattr(r,"Name",None)
    except: return getattr(r,"Name",None)
def _room_number(r):
    try:
        p=r.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER); s=p.AsString() if p else None
        return s or getattr(r,"Number",None)
    except: return getattr(r,"Number",None)

def _collect_rooms(document, boundary_location, levels_map, wanted_pair):
    out=[]; opts=DB.SpatialElementBoundaryOptions(); opts.SpatialElementBoundaryLocation=boundary_location
    fec=DB.FilteredElementCollector(document).OfCategory(DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType()
    doc_key = _doc_key(document)
    for r in fec:
        if not isinstance(r, DB.SpatialElement): continue
        if not _design_option_ok(r, doc_key, wanted_pair):
            continue
        outer,inners=_loops_from_boundary(r.GetBoundarySegments(opts))
        if not outer: continue
        area_ft2=float(getattr(r,"Area",0.0)) if hasattr(r,"Area") else None
        loops={"outer":{"xy_ft":_xy_ft_from_pts(outer),"xy_m":_xy_m_from_pts(outer),
                        "signed_area_ft2":_signed_area_xy_ft(outer)},
               "inners":[{"xy_ft":_xy_ft_from_pts(inn),"xy_m":_xy_m_from_pts(inn),
                          "signed_area_ft2":_signed_area_xy_ft(inn)} for inn in inners]}
        level_id = r.LevelId.IntegerValue if getattr(r,"LevelId",None) else None
        level_name = levels_map.get(level_id,{}).get("name","")
        outer_signed = loops["outer"]["signed_area_ft2"]
        poly_area = abs(outer_signed) - sum(abs(h["signed_area_ft2"]) for h in loops["inners"])
        rec={"id":r.Id.IntegerValue,"unique_id":r.UniqueId,
             "number":_room_number(r),"name":_room_name(r),
             "level_id":level_id,"level":level_name,
             "loops":loops,
             "poly_area_ft2": poly_area,
             "area_ft2_param":area_ft2,"area_m2_param": area_ft2*FT2_TO_M2 if area_ft2 is not None else None,
             "params":_collect_all_params(r, document)}
        # back-compat поля
        ol=loops["outer"]; rec["outer_xy_m"]=ol["xy_m"]; rec["outer_xy_ft"]=ol["xy_ft"]
        rec["inner_loops_xy_m"]=[h["xy_m"] for h in loops["inners"]]
        rec["inner_loops_xy_ft"]=[h["xy_ft"] for h in loops["inners"]]
        out.append(rec)
    return out

# ===== bbox/footprint =====
def _bbox_min_max(el, T=None):
    bb = el.get_BoundingBox(None)
    if not bb:
        return None, None
    bb_tr = getattr(bb, "Transform", None)
    base = bb_tr if isinstance(bb_tr, DB.Transform) else DB.Transform.Identity
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    for xi in (bb.Min.X, bb.Max.X):
        for yi in (bb.Min.Y, bb.Max.Y):
            for zi in (bb.Min.Z, bb.Max.Z):
                loc = DB.XYZ(xi, yi, zi)
                world = base.OfPoint(loc)
                host = _of_point(T, world)
                mins[0] = min(mins[0], host.X)
                mins[1] = min(mins[1], host.Y)
                mins[2] = min(mins[2], host.Z)
                maxs[0] = max(maxs[0], host.X)
                maxs[1] = max(maxs[1], host.Y)
                maxs[2] = max(maxs[2], host.Z)
    if mins[0] == float("inf"):
        return None, None
    pmin = DB.XYZ(mins[0], mins[1], mins[2])
    pmax = DB.XYZ(maxs[0], maxs[1], maxs[2])
    return pmin, pmax

def _bb_center(el, T=None):
    pmin, pmax = _bbox_min_max(el, T)
    if not (pmin and pmax):
        return None
    return DB.XYZ((pmin.X + pmax.X) * 0.5, (pmin.Y + pmax.Y) * 0.5, (pmin.Z + pmax.Z) * 0.5)

def _bb_size(el, T=None):
    pmin, pmax = _bbox_min_max(el, T)
    if not (pmin and pmax):
        return None
    return [abs(pmax.X - pmin.X), abs(pmax.Y - pmin.Y), abs(pmax.Z - pmin.Z)]

def _bbox_record(el, T=None):
    pmin, pmax = _bbox_min_max(el, T)
    if not (pmin and pmax):
        return None
    c = DB.XYZ((pmin.X + pmax.X) * 0.5, (pmin.Y + pmax.Y) * 0.5, (pmin.Z + pmax.Z) * 0.5)
    return {"min_ft": [_roundf(pmin.X, 4), _roundf(pmin.Y, 4), _roundf(pmin.Z, 4)],
            "max_ft": [_roundf(pmax.X, 4), _roundf(pmax.Y, 4), _roundf(pmax.Z, 4)],
            "min_m": [_roundf(pmin.X * FT_TO_M, 3), _roundf(pmin.Y * FT_TO_M, 3), _roundf(pmin.Z * FT_TO_M, 3)],
            "max_m": [_roundf(pmax.X * FT_TO_M, 3), _roundf(pmax.Y * FT_TO_M, 3), _roundf(pmax.Z * FT_TO_M, 3)],
            "center_ft": [_roundf(c.X, 4), _roundf(c.Y, 4), _roundf(c.Z, 4)],
            "center_m": [_roundf(c.X * FT_TO_M, 3), _roundf(c.Y * FT_TO_M, 3), _roundf(c.Z * FT_TO_M, 3)]}
def _footprint_record(ring):
    if not ring: return None
    return {"xy_ft":_xy_ft_from_pts(ring),"xy_m":_xy_m_from_pts(ring)}

# ===== размеры (устойчивые) =====
def _len_from_params(fi, bip_list, name_list):
    # feet
    for nm in bip_list:
        try:
            bip=getattr(DB.BuiltInParameter, nm); p=fi.get_Parameter(bip)
            if p and p.StorageType==DB.StorageType.Double:
                v=p.AsDouble()
                if v and v>0: return v
        except: pass
    names={n.lower() for n in name_list}
    for p in fi.Parameters:
        try:
            d=p.Definition; nm=d.Name if d else None
            if not nm: continue
            if nm.lower() in names and p.StorageType==DB.StorageType.Double:
                v=p.AsDouble()
                if v and v>0: return v
        except: pass
    return None

_MM = 1.0/304.8  # mm -> feet
def _nominal_from_typename(name):
    if not name: return None,None
    m=re.search(r'(\d{3,4})\s*[Ww×x]\s*(\d{3,4})\s*[Hh]', name.replace('х','x'))
    if not m: return None,None
    w_ft=float(m.group(1))*_MM; h_ft=float(m.group(2))*_MM
    return w_ft,h_ft

def _valid_or_none(v, vmin, vmax):
    try:
        return v if (v and vmin<=v<=vmax) else None
    except:
        return None

def _is_root_instance(fi):
    try:
        return getattr(fi, "SuperComponent", None) is None
    except:
        return True

def _instance_frame(fi, T):
    origin = _of_point(T, getattr(getattr(fi, "Location", None), "Point", None)) or _bb_center(fi, T) or DB.XYZ.Zero
    facing = _flatten_xy(_of_vector(T, getattr(fi, "FacingOrientation", None))) or DB.XYZ.BasisY
    up = DB.XYZ.BasisZ
    hand = _normalize(_cross(up, facing))
    if not hand:
        hand = DB.XYZ.BasisX
        up = _normalize(_cross(facing, hand)) or DB.XYZ.BasisZ
    else:
        up = _normalize(_cross(facing, hand)) or up
    hand_hint = _flatten_xy(_of_vector(T, getattr(fi, "HandOrientation", None)))
    if hand_hint and (hand.X * hand_hint.X + hand.Y * hand_hint.Y) < 0.0:
        hand = DB.XYZ(-hand.X, -hand.Y, -hand.Z)
    hand = _flatten_xy(hand) or DB.XYZ.BasisX
    facing = _flatten_xy(facing) or DB.XYZ.BasisY
    up = _normalize(_cross(facing, hand)) or up
    frame = DB.Transform.Identity
    frame.Origin = origin
    frame.BasisX = hand
    frame.BasisY = facing
    frame.BasisZ = up
    return frame

def _collect_instance_local_points(fi, T, frame):
    opts = DB.Options()
    opts.IncludeNonVisibleObjects = True
    opts.ComputeReferences = False
    opts.DetailLevel = DB.ViewDetailLevel.Fine
    geom = fi.get_Geometry(opts)
    if not geom:
        return []
    inv = frame.Inverse
    pts = []

    def add(world_pt):
        if not world_pt:
            return
        host_pt = _of_point(T, world_pt)
        pts.append(inv.OfPoint(host_pt))

    def visit(geometry, tr):
        for g in geometry:
            if isinstance(g, DB.GeometryInstance):
                visit(g.GetSymbolGeometry(), tr.Multiply(g.Transform))
            elif isinstance(g, DB.Solid):
                if g.Volume <= 1e-8:
                    continue
                for face in g.Faces:
                    mesh = face.Triangulate()
                    for i in range(mesh.Vertices.Count):
                        add(tr.OfPoint(mesh.Vertices[i]))
                for edge in g.Edges:
                    curve = edge.AsCurve()
                    add(tr.OfPoint(curve.GetEndPoint(0)))
                    add(tr.OfPoint(curve.GetEndPoint(1)))
            elif isinstance(g, DB.Mesh):
                for i in range(g.Vertices.Count):
                    add(tr.OfPoint(g.Vertices[i]))
            elif isinstance(g, DB.Curve):
                add(tr.OfPoint(g.GetEndPoint(0)))
                add(tr.OfPoint(g.GetEndPoint(1)))
            elif isinstance(g, DB.Point):
                add(tr.OfPoint(g.Coord))
        if len(pts) > 4000:
            return

    visit(geom, DB.Transform.Identity)
    return pts

def _instance_rect_from_geometry(fi, T, frame):
    pts = _collect_instance_local_points(fi, T, frame)
    if not pts:
        return None
    min_x = min(p.X for p in pts); max_x = max(p.X for p in pts)
    min_y = min(p.Y for p in pts); max_y = max(p.Y for p in pts)
    min_z = min(p.Z for p in pts); max_z = max(p.Z for p in pts)
    center_local = DB.XYZ((min_x + max_x) * 0.5,
                          (min_y + max_y) * 0.5,
                          (min_z + max_z) * 0.5)
    return {
        "width": max_x - min_x,
        "depth": max_y - min_y,
        "height": max_z - min_z,
        "center_local": center_local,
        "min_local": DB.XYZ(min_x, min_y, min_z),
        "max_local": DB.XYZ(max_x, max_y, max_z),
    }

def _pick_dim(primary, secondary, vmin, vmax, default=None):
    for value in (primary, secondary, default):
        if value and vmin <= value <= vmax:
            return value
    return None

def _door_nominal_dims(fi):
    w = _len_from_params(
        fi,
        ['DOOR_WIDTH','FAMILY_WIDTH_PARAM','WIDTH'],
        ['Width','Ширина','Ширина проема','Ширина проёма']
    )
    h = _len_from_params(
        fi,
        ['DOOR_HEIGHT','FAMILY_HEIGHT_PARAM','HEIGHT'],
        ['Height','Высота','Высота проема','Высота проёма']
    )
    if not (w and h):
        w_nom, h_nom = _nominal_from_typename(_type_name(fi))
        w = w or w_nom
        h = h or h_nom
    thk = None
    try:
        host = getattr(fi, "Host", None)
        if isinstance(host, DB.Wall):
            thk = host.Width
    except:
        pass
    return _valid_or_none(w, W_MIN_FT, W_MAX_FT), \
           _valid_or_none(h, H_MIN_FT, H_MAX_FT), \
           _valid_or_none(thk, THK_MIN_FT, THK_MAX_FT)

def _window_nominal_dims(fi):
    w = _len_from_params(
        fi,
        ['WINDOW_WIDTH','FAMILY_WIDTH_PARAM','WIDTH'],
        ['Width','Ширина']
    )
    h = _len_from_params(
        fi,
        ['WINDOW_HEIGHT','FAMILY_HEIGHT_PARAM','HEIGHT'],
        ['Height','Высота']
    )
    if not (w and h):
        w_nom, h_nom = _nominal_from_typename(_type_name(fi))
        w = w or w_nom
        h = h or h_nom
    thk = None
    try:
        host = getattr(fi, "Host", None)
        if isinstance(host, DB.Wall):
            thk = host.Width
    except:
        pass
    return _valid_or_none(w, W_MIN_FT, W_MAX_FT), \
           _valid_or_none(h, H_MIN_FT, H_MAX_FT), \
           _valid_or_none(thk, THK_MIN_FT, THK_MAX_FT)

def _rect_ring_from_frame(frame, width, depth):
    if not (frame and width and depth):
        return None
    hx = 0.5 * width
    hy = 0.5 * depth
    pts = [
        frame.OfPoint(DB.XYZ( hx,  hy, 0.0)),
        frame.OfPoint(DB.XYZ(-hx,  hy, 0.0)),
        frame.OfPoint(DB.XYZ(-hx, -hy, 0.0)),
        frame.OfPoint(DB.XYZ( hx, -hy, 0.0)),
    ]
    pts.append(pts[0])
    return pts

def _door_window_record(kind, fi, sym, sdoc, linkinst, T, hints):
    frame = _instance_frame(fi, T)
    geom = _instance_rect_from_geometry(fi, T, frame)
    width_hint, height_hint, thk_hint = hints
    width_geom = geom["width"] if geom else None
    depth_geom = geom["depth"] if geom else None
    height_geom = geom["height"] if geom else None
    center_world = frame.OfPoint(geom["center_local"]) if geom else frame.Origin

    width = _pick_dim(width_hint, width_geom, W_MIN_FT, W_MAX_FT)
    if not width:
        return None
    height = _pick_dim(height_hint, height_geom, H_MIN_FT, H_MAX_FT) or H_MIN_FT
    thickness = _pick_dim(thk_hint, depth_geom, THK_MIN_FT, THK_MAX_FT) or THK_MIN_FT

    fp_ring = _rect_ring_from_frame(frame, width, thickness)
    footprint = _footprint_record(fp_ring)
    placement = {
        "origin_ft": [_roundf(center_world.X, 4), _roundf(center_world.Y, 4), _roundf(center_world.Z, 4)],
        "origin_m": [_roundf(center_world.X * FT_TO_M, 3),
                     _roundf(center_world.Y * FT_TO_M, 3),
                     _roundf(center_world.Z * FT_TO_M, 3)],
        "hand": [_roundf(frame.BasisX.X, 4), _roundf(frame.BasisX.Y, 4), _roundf(frame.BasisX.Z, 4)],
        "facing": [_roundf(frame.BasisY.X, 4), _roundf(frame.BasisY.Y, 4), _roundf(frame.BasisY.Z, 4)],
        "up": [_roundf(frame.BasisZ.X, 4), _roundf(frame.BasisZ.Y, 4), _roundf(frame.BasisZ.Z, 4)]
    }
    size_ft = {
        "width": _roundf(width, 4),
        "height": _roundf(height, 4),
        "thickness": _roundf(thickness, 4)
    }
    size_m = {
        "width": _roundf(width * FT_TO_M, 3),
        "height": _roundf(height * FT_TO_M, 3),
        "thickness": _roundf(thickness * FT_TO_M, 3)
    }
    if geom:
        placement["local_min_ft"] = [_roundf(geom["min_local"].X, 4),
                                      _roundf(geom["min_local"].Y, 4),
                                      _roundf(geom["min_local"].Z, 4)]
        placement["local_max_ft"] = [_roundf(geom["max_local"].X, 4),
                                      _roundf(geom["max_local"].Y, 4),
                                      _roundf(geom["max_local"].Z, 4)]

    rec = {
        "kind": kind,
        "id": fi.Id.IntegerValue,
        "unique_id": getattr(fi, "UniqueId", None),
        "type_id": sym.Id.IntegerValue,
        "type_name": _element_typename(fi, sdoc),
        "bbox": _bbox_record(fi, T),
        "footprint": footprint,
        "params": _collect_all_params(fi, sdoc),
        "placement": placement,
        "size_ft": size_ft,
        "size_m": size_m
    }
    if linkinst is not None:
        rec["in_link"] = {
            "link_instance_id": linkinst.Id.IntegerValue,
            "link_doc_title": sdoc.Title,
            "link_doc_full_path": _user_model_path(sdoc)
        }
    return rec

def _type_name(fi):
    try:
        sym=fi.Symbol
        if sym:
            p=sym.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
            return p.AsString() if p else getattr(sym,"Name","")
    except: pass
    return ""

def _element_typename(el, sdoc):
    try:
        if isinstance(el, DB.Wall):
            wt = sdoc.GetElement(el.GetTypeId()); return wt.Name if wt else ""
        if isinstance(el, DB.FamilyInstance):
            return _type_name(el)
    except: pass
    return ""

# ===== сбор типов для UI =====
def _flatten_params_simple_dict(raw_dict):
    if not isinstance(raw_dict, dict): return "{}"
    d = raw_dict.get("type", {}) if "type" in raw_dict else raw_dict
    out={}
    for k,v in d.items():
        out[k]=v.get("display", v.get("raw_internal","")) if isinstance(v,dict) else v
    return json.dumps(out, ensure_ascii=False)

def _gather_glazing_types():
    rows=[]; seen=set()
    for sdoc, _, _ in _docs_sources(doc):
        doc_key=_doc_key(sdoc)
        doc_title=getattr(sdoc, "Title", "") or ""
        for fs in DB.FilteredElementCollector(sdoc).OfClass(DB.FamilySymbol).OfCategory(DB.BuiltInCategory.OST_Windows):
            tname=_element_typename(fs,sdoc); key=(doc_key,"Windows",fs.Id.IntegerValue)
            if key in seen: continue
            rows.append({"cat":"Windows","type_id":fs.Id.IntegerValue,"type_name":tname,
                         "family": getattr(getattr(fs,'Family',None),'Name',""),
                         "params_json":_flatten_params_simple_dict(_collect_params_block(fs)),
                         "doc_key":doc_key,
                         "doc_title":doc_title})
            seen.add(key)
        for fs in DB.FilteredElementCollector(sdoc).OfClass(DB.FamilySymbol).OfCategory(DB.BuiltInCategory.OST_CurtainWallPanels):
            tname=_element_typename(fs,sdoc); key=(doc_key,"Curtain Panels",fs.Id.IntegerValue)
            if key in seen: continue
            rows.append({"cat":"Curtain Panels","type_id":fs.Id.IntegerValue,"type_name":tname,
                         "family": getattr(getattr(fs,'Family',None),'Name',""),
                         "params_json":_flatten_params_simple_dict(_collect_params_block(fs)),
                         "doc_key":doc_key,
                         "doc_title":doc_title})
            seen.add(key)
        for wt in DB.FilteredElementCollector(sdoc).OfClass(DB.WallType):
            try:
                if getattr(wt,"Kind",None)==DB.WallKind.Curtain:
                    key=(doc_key,"Curtain Walls",wt.Id.IntegerValue)
                    if key in seen: continue
                    rows.append({"cat":"Curtain Walls","type_id":wt.Id.IntegerValue,"type_name":wt.Name,
                                 "family":"WallType",
                                 "params_json":_flatten_params_simple_dict(_collect_params_block(wt)),
                                 "doc_key":doc_key,
                                 "doc_title":doc_title})
                    seen.add(key)
            except: pass
    rows.sort(key=lambda r:(r["cat"],r["type_name"]))
    return rows

def _gather_door_types():
    rows=[]; seen=set()
    for sdoc, _, _ in _docs_sources(doc):
        doc_key=_doc_key(sdoc)
        doc_title=getattr(sdoc, "Title", "") or ""
        for fs in DB.FilteredElementCollector(sdoc).OfClass(DB.FamilySymbol).OfCategory(DB.BuiltInCategory.OST_Doors):
            tname=_element_typename(fs,sdoc); key=(doc_key,"Doors",fs.Id.IntegerValue)
            if key in seen: continue
            rows.append({"cat":"Doors","type_id":fs.Id.IntegerValue,"type_name":tname,
                         "family": getattr(getattr(fs,'Family',None),'Name',""),
                         "params_json":_flatten_params_simple_dict(_collect_params_block(fs)),
                         "doc_key":doc_key,
                         "doc_title":doc_title})
            seen.add(key)
    rows.sort(key=lambda r:(r["cat"],r["type_name"]))
    return rows

# ===== формы =====
class TypePickerForm(Form):
    def __init__(self, rows, title):
        Form.__init__(self)
        self.Text=title; self.StartPosition=FormStartPosition.CenterScreen; self.ClientSize=Size(1100,600)
        self.grid=DataGridView(); self.grid.Dock=DockStyle.Fill
        self.grid.AllowUserToAddRows=False; self.grid.AllowUserToDeleteRows=False
        self.grid.AutoSizeColumnsMode=DataGridViewAutoSizeColumnsMode.AllCells; self.grid.RowHeadersVisible=False
        col_sel=DataGridViewCheckBoxColumn(); col_sel.HeaderText="Select"
        col_doc=DataGridViewTextBoxColumn(); col_doc.HeaderText="Document"
        col_cat=DataGridViewTextBoxColumn();  col_cat.HeaderText="Category"
        col_typ=DataGridViewTextBoxColumn();  col_typ.HeaderText="Type"
        col_fam=DataGridViewTextBoxColumn();  col_fam.HeaderText="Family"
        col_par=DataGridViewTextBoxColumn();  col_par.HeaderText="TypeParamsJson"; col_par.Width=600
        self.grid.Columns.Add(col_sel); self.grid.Columns.Add(col_doc); self.grid.Columns.Add(col_cat)
        self.grid.Columns.Add(col_typ); self.grid.Columns.Add(col_fam); self.grid.Columns.Add(col_par)
        for r in rows:
            self.grid.Rows.Add(False, r.get("doc_title",""), r["cat"], r["type_name"], r.get("family",""), r.get("params_json",""))
        panel=FlowLayoutPanel(); panel.FlowDirection=FlowDirection.LeftToRight; panel.Dock=DockStyle.Bottom; panel.Height=48
        btn_all=Button(); btn_all.Text="Select All"; btn_all.Width=100; btn_all.Click+=self._select_all
        btn_clear=Button(); btn_clear.Text="Clear"; btn_clear.Width=100; btn_clear.Click+=self._clear_all
        btn_ok=Button(); btn_ok.Text="Finish"; btn_ok.Width=120; btn_ok.Click+=self._ok
        btn_cancel=Button(); btn_cancel.Text="Cancel"; btn_cancel.Width=100; btn_cancel.Click+=self._cancel
        panel.Controls.Add(btn_all); panel.Controls.Add(btn_clear); panel.Controls.Add(btn_ok); panel.Controls.Add(btn_cancel)
        self.Controls.Add(self.grid); self.Controls.Add(panel)
        self.selected_ids={}
        self._row_type_ids=[r["type_id"] for r in rows]
        self._row_cats=[r["cat"] for r in rows]
        self._row_doc_keys=[r.get("doc_key") for r in rows]
    def _select_all(self,s,a): 
        for i in range(self.grid.Rows.Count): self.grid.Rows[i].Cells[0].Value=True
    def _clear_all(self,s,a): 
        for i in range(self.grid.Rows.Count): self.grid.Rows[i].Cells[0].Value=False
    def _ok(self,s,a):
        out={};
        for i in range(self.grid.Rows.Count):
            if bool(self.grid.Rows[i].Cells[0].Value):
                cat=self._row_cats[i]
                doc_key=self._row_doc_keys[i]
                tid=int(self._row_type_ids[i])
                if not doc_key:
                    continue
                out.setdefault(cat, {}).setdefault(doc_key, set()).add(tid)
        self.selected_ids=out; self.DialogResult=DialogResult.OK; self.Close()
    def _cancel(self,s,a): self.DialogResult=DialogResult.Cancel; self.Close()

class MainExportForm(Form):
    def __init__(self):
        Form.__init__(self)
        self.Text="REVIT_DATA_EXPORT"; self.StartPosition=FormStartPosition.CenterScreen; self.ClientSize=Size(760,220)
        self.levels_map=_all_levels_map(doc); self.sel_glazing={}; self.sel_doors={}
        grid=TableLayoutPanel(); grid.Dock=DockStyle.Fill; grid.ColumnCount=4; grid.RowCount=5
        grid.ColumnStyles.Add(ColumnStyle(SizeType.Absolute,140)); grid.ColumnStyles.Add(ColumnStyle(SizeType.Absolute,300))
        grid.ColumnStyles.Add(ColumnStyle(SizeType.Absolute,220)); grid.ColumnStyles.Add(ColumnStyle(SizeType.Absolute,80))
        self.Controls.Add(grid)
        lbl_do=Label(); lbl_do.Text="Design Option:"; lbl_do.AutoSize=True
        self.cmb_do=ComboBox(); self.cmb_do.DropDownStyle=ComboBoxStyle.DropDownList; self._fill_design_options(self.cmb_do)
        grid.Controls.Add(lbl_do,0,0); grid.Controls.Add(self.cmb_do,1,0)
        self.cb_rooms=CheckBox(); self.cb_rooms.Text="Помещения"; self.cb_rooms.Checked=True; self.cb_rooms.AutoSize=True
        self.cb_glaz=CheckBox(); self.cb_glaz.Text="Остекление"; self.cb_glaz.AutoSize=True
        self.cb_doors=CheckBox(); self.cb_doors.Text="Двери"; self.cb_doors.AutoSize=True
        grid.Controls.Add(self.cb_rooms,0,1); grid.Controls.Add(self.cb_glaz,1,1); grid.Controls.Add(self.cb_doors,2,1)
        self.btn_glaz=Button(); self.btn_glaz.Text="Выбрать типы остекления"; self.btn_glaz.Width=220; self.btn_glaz.Click+=self._pick_glazing
        self.lbl_glaz=Label(); self.lbl_glaz.Text="✖"; self.lbl_glaz.ForeColor=Color.Red; self.lbl_glaz.AutoSize=True; self.lbl_glaz.TextAlign=ContentAlignment.MiddleLeft
        grid.Controls.Add(self.btn_glaz,1,2); grid.Controls.Add(self.lbl_glaz,3,2)
        self.btn_doors=Button(); self.btn_doors.Text="Выбрать типы дверей"; self.btn_doors.Width=220; self.btn_doors.Click+=self._pick_doors
        self.lbl_doors=Label(); self.lbl_doors.Text="✖"; self.lbl_doors.ForeColor=Color.Red; self.lbl_doors.AutoSize=True; self.lbl_doors.TextAlign=ContentAlignment.MiddleLeft
        grid.Controls.Add(self.btn_doors,1,3); grid.Controls.Add(self.lbl_doors,3,3)
        self.btn_export=Button(); self.btn_export.Text="Экспортировать"; self.btn_export.Width=200; self.btn_export.Click+=self._do_export
        btn_cancel=Button(); btn_cancel.Text="Отмена"; btn_cancel.Width=100; btn_cancel.Click+=lambda s,a: self.Close()
        grid.Controls.Add(self.btn_export,1,4); grid.Controls.Add(btn_cancel,2,4)

    def _fill_design_options(self, combo):
        combo.Items.Clear()
        items=[("All (no filter)", (None,None))]
        try:
            for opt in DB.FilteredElementCollector(doc).OfClass(DB.DesignOption):
                set_name=""
                try:
                    p=opt.get_Parameter(DB.BuiltInParameter.OPTION_SET_ID); eid=p.AsElementId() if p else None
                    set_el=doc.GetElement(eid) if eid and eid.IntegerValue!=-1 else None
                    set_name=getattr(set_el,"Name","") or ""
                except: pass
                items.append(("[Host] {}{}".format((set_name+" / ") if set_name else "", opt.Name), (_doc_key(doc), opt.Id.IntegerValue)))
        except: pass
        for ldoc,_,_ in _docs_sources(doc):
            if ldoc is doc: continue
            try:
                for opt in DB.FilteredElementCollector(ldoc).OfClass(DB.DesignOption):
                    set_name=""
                    try:
                        p=opt.get_Parameter(DB.BuiltInParameter.OPTION_SET_ID); eid=p.AsElementId() if p else None
                        set_el=ldoc.GetElement(eid) if eid and eid.IntegerValue!=-1 else None
                        set_name=getattr(set_el,"Name","") or ""
                    except: pass
                    items.append(("[Link: {}] {}{}".format(ldoc.Title,(set_name+" / ") if set_name else "",opt.Name),
                                  (_doc_key(ldoc), opt.Id.IntegerValue)))
            except: pass
        for text,_ in items: combo.Items.Add(text)
        combo.SelectedIndex=0
        self._design_option_map=dict(items)

    def _selected_design_option_pair(self):
        text=self.cmb_do.SelectedItem
        return self._design_option_map.get(text,(None,None))

    @staticmethod
    def _has_any_selection(sel_dict):
        if not isinstance(sel_dict, dict):
            return False
        for doc_map in sel_dict.values():
            if isinstance(doc_map, dict):
                for ids in doc_map.values():
                    if ids:
                        return True
            elif doc_map:
                return True
        return False

    def _pick_glazing(self,s,a):
        rows=_gather_glazing_types(); dlg=TypePickerForm(rows,"Выбор типов остекления")
        if dlg.ShowDialog()==DialogResult.OK:
            self.sel_glazing=dlg.selected_ids or {}
            ok=self._has_any_selection(self.sel_glazing); self.lbl_glaz.Text="✔" if ok else "✖"; self.lbl_glaz.ForeColor=Color.Green if ok else Color.Red

    def _pick_doors(self,s,a):
        rows=_gather_door_types(); dlg=TypePickerForm(rows,"Выбор типов дверей")
        if dlg.ShowDialog()==DialogResult.OK:
            self.sel_doors=dlg.selected_ids or {}
            ok=self._has_any_selection(self.sel_doors); self.lbl_doors.Text="✔" if ok else "✖"; self.lbl_doors.ForeColor=Color.Green if ok else Color.Red

    def _do_export(self,s,a):
        if self.cb_glaz.Checked and not self._has_any_selection(self.sel_glazing):
            TaskDialog.Show("Export","Выберите типы остекления."); return
        if self.cb_doors.Checked and not self._has_any_selection(self.sel_doors):
            TaskDialog.Show("Export","Выберите типы дверей."); return
        levels_map=self.levels_map
        levels_list=[{"id":k,"name":v["name"],
                      "elevation_ft":round(v["elevation_ft"],4),
                      "elevation_m": round(v["elevation_m"],3)} for k,v in sorted(levels_map.items(), key=lambda kv: kv[1]["elevation_ft"])]
        pair=self._selected_design_option_pair()
        rooms=_collect_rooms(doc, DB.SpatialElementBoundaryLocation.Finish, levels_map, pair) if self.cb_rooms.Checked else []
        glazing={"windows":[], "curtain_panels":[], "curtain_walls":[]} if self.cb_glaz.Checked else {"windows":[], "curtain_panels":[], "curtain_walls":[]}
        doors=[]
        if self.cb_glaz.Checked: glazing=_export_glazing(self.sel_glazing, pair)
        if self.cb_doors.Checked: doors=_export_doors(self.sel_doors, pair)
        openings=_build_openings_compat(glazing, doors)
        out={"version":"bess-export-compat-2","units_note":"Internal length units are feet. Geometry exported as ft and m.",
             "meta":_meta(levels_map),"levels":levels_list,"rooms":rooms,"openings":openings}
        path=_pick_save_path()
        if not path: TaskDialog.Show("REVIT_DATA_EXPORT","Path not selected."); return
        with open(path,"w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
        TaskDialog.Show("REVIT_DATA_EXPORT","Exported:\n{}\nRooms: {}\nOpenings: {}".format(path,len(rooms),len(openings)))
        self.Close()

# ===== фильтр по Design Option =====
def _design_option_ok(el, sdoc_key, wanted_pair):
    want_doc,want_id = wanted_pair or (None,None)
    if not want_doc and not want_id: return True
    if sdoc_key != want_doc: return False
    try:
        p=el.get_Parameter(DB.BuiltInParameter.DESIGN_OPTION_ID)
        if p and p.StorageType==DB.StorageType.ElementId:
            eid=p.AsElementId(); 
            if eid and eid.IntegerValue==want_id: return True
    except: pass
    try:
        opt=getattr(el,"DesignOption",None)
        if opt and opt.Id.IntegerValue==want_id: return True
    except: pass
    return False

# ===== экспорт остекления/дверей =====
def _export_glazing(sel_glazing, wanted_pair):
    out={"windows":[], "curtain_panels":[], "curtain_walls":[]}
    win_map=sel_glazing.get("Windows",{}) if isinstance(sel_glazing, dict) else {}
    pan_map=sel_glazing.get("Curtain Panels",{}) if isinstance(sel_glazing, dict) else {}
    cw_map=sel_glazing.get("Curtain Walls",{}) if isinstance(sel_glazing, dict) else {}
    for sdoc,linkinst,T in _docs_sources(doc):
        sdoc_key=_doc_key(sdoc)
        win_ids=set(win_map.get(sdoc_key, set()))
        pan_ids=set(pan_map.get(sdoc_key, set()))
        cw_ids=set(cw_map.get(sdoc_key, set()))
        # Windows
        if win_ids:
            col=DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_Windows).WhereElementIsNotElementType()
            for fi in col:
                try:
                    if not isinstance(fi, DB.FamilyInstance): continue
                    if not _is_root_instance(fi):
                        continue
                    if not _design_option_ok(fi,sdoc_key,wanted_pair): continue
                    sym=fi.Symbol
                    if not sym or sym.Id.IntegerValue not in win_ids: continue
                    record=_door_window_record("window", fi, sym, sdoc, linkinst, T, _window_nominal_dims(fi))
                    if record:
                        out["windows"].append(record)
                except Exception as ex:
                    logger.warn("Window export issue: {}".format(ex))
        # Panels (только в elements, в openings не тащим)
        if pan_ids:
            col=DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_CurtainWallPanels).WhereElementIsNotElementType()
            for el in col:
                try:
                    if not isinstance(el, DB.FamilyInstance): continue
                    if not _is_root_instance(el):
                        continue
                    if not _design_option_ok(el,sdoc_key,wanted_pair): continue
                    sym=el.Symbol
                    if not sym or sym.Id.IntegerValue not in pan_ids: continue
                    rec={"kind":"curtain_panel","id":el.Id.IntegerValue,"unique_id":getattr(el,"UniqueId",None),
                         "type_id":sym.Id.IntegerValue,"type_name":_element_typename(el,sdoc),
                         "bbox":_bbox_record(el,T),"params":_collect_all_params(el,sdoc)}
                    if linkinst is not None:
                        rec["in_link"]={"link_instance_id":linkinst.Id.IntegerValue,"link_doc_title":sdoc.Title,"link_doc_full_path":_user_model_path(sdoc)}
                    out["curtain_panels"].append(rec)
                except Exception as ex:
                    logger.warn("CurtainPanel export issue: {}".format(ex))
        # Curtain walls (bbox)
        if cw_ids:
            col=DB.FilteredElementCollector(sdoc).OfClass(DB.Wall)
            for el in col:
                try:
                    if not _design_option_ok(el,sdoc_key,wanted_pair): continue
                    wt=sdoc.GetElement(el.GetTypeId())
                    if not wt or getattr(wt,"Kind",None)!=DB.WallKind.Curtain: continue
                    if wt.Id.IntegerValue not in cw_ids: continue
                    rec={"kind":"curtain_wall","id":el.Id.IntegerValue,"unique_id":getattr(el,"UniqueId",None),
                         "type_id":wt.Id.IntegerValue,"type_name":wt.Name,
                         "bbox":_bbox_record(el,T),"params":_collect_all_params(el,sdoc)}
                    if linkinst is not None:
                        rec["in_link"]={"link_instance_id":linkinst.Id.IntegerValue,"link_doc_title":sdoc.Title,"link_doc_full_path":_user_model_path(sdoc)}
                    out["curtain_walls"].append(rec)
                except Exception as ex:
                    logger.warn("CurtainWall export issue: {}".format(ex))
    return out

def _export_doors(sel_doors, wanted_pair):
    door_map=sel_doors.get("Doors",{}) if isinstance(sel_doors, dict) else {}
    res=[]
    for sdoc,linkinst,T in _docs_sources(doc):
        sdoc_key=_doc_key(sdoc)
        door_ids=set(door_map.get(sdoc_key, set()))
        if not door_ids:
            continue
        col=DB.FilteredElementCollector(sdoc).OfCategory(DB.BuiltInCategory.OST_Doors).WhereElementIsNotElementType()
        for fi in col:
            try:
                if not isinstance(fi, DB.FamilyInstance): continue
                if not _is_root_instance(fi):
                    continue
                if not _design_option_ok(fi,sdoc_key,wanted_pair): continue
                sym=fi.Symbol
                if not sym or sym.Id.IntegerValue not in door_ids: continue
                record=_door_window_record("door", fi, sym, sdoc, linkinst, T, _door_nominal_dims(fi))
                if record:
                    res.append(record)
            except Exception as ex:
                logger.warn("Door export issue: {}".format(ex))
    return res

# ===== openings для канваса =====
def _poly_from_footprint_or_bbox_xy_m(ent):
    fp=ent.get("footprint")
    if fp and fp.get("xy_m"): return fp["xy_m"]
    b=ent.get("bbox"); 
    if not b: return None
    mn, mx = b.get("min_m"), b.get("max_m")
    if not (mn and mx): return None
    x0,y0=float(mn[0]),float(mn[1]); x1,y1=float(mx[0]),float(mx[1])
    return [[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]]

def _build_openings_compat(glazing, doors):
    res=[]
    for d in doors:
        poly=_poly_from_footprint_or_bbox_xy_m(d)
        if poly:
            res.append({"id":d["id"],"opening_type":"door","outer_xy_m":poly,
                        "params":d.get("params",{}),"category":"Doors","symbol_name":d.get("type_name","")})
    for w in glazing.get("windows",[]):
        poly=_poly_from_footprint_or_bbox_xy_m(w)
        if poly:
            res.append({"id":w["id"],"opening_type":"window","outer_xy_m":poly,
                        "params":w.get("params",{}),"category":"Windows","symbol_name":w.get("type_name","")})
    return res

# ===== сохранение/мета =====
def _pick_save_path():
    try:
        dlg=SaveFileDialog(); dlg.Filter="JSON files (*.json)|*.json|All files (*.*)|*.*"; dlg.FileName="bess_export.json"
        if dlg.ShowDialog()==DialogResult.OK: return dlg.FileName
        return None
    except:
        base=_user_model_path(doc); folder=os.path.dirname(base) if base else os.path.expanduser("~/Desktop")
        ts=datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"); return os.path.join(folder,"bess_export_{}.json".format(ts))

def _meta(levels_map):
    host_full=_user_model_path(doc)
    return {"doc_title":doc.Title,"doc_full_path":host_full,"doc_dir":os.path.dirname(host_full) if host_full else "",
            "export_time":datetime.utcnow().isoformat(),
            "links":[{"instance_id":li.Id.IntegerValue,"doc_title":ldoc.Title,"doc_full_path":_user_model_path(ldoc)}
                     for ldoc,li,_ in _docs_sources(doc) if li is not None]}

# ===== вход =====
def main():
    if doc.IsLinked:
        TaskDialog.Show("REVIT_DATA_EXPORT","Open a host model, not a linked file."); return
    MainExportForm().ShowDialog()

if __name__=="__main__":
    try: main()
    except Exception as ex:
        TaskDialog.Show("REVIT_DATA_EXPORT","Export failed:\n{}".format(ex))
