# -*- coding: utf-8 -*-
import json
from .geometry_utils import r2, FT_TO_M

def load_bess_export(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_lv = data.get("levels", {})
    levels = {}
    if isinstance(raw_lv, dict):
        it = raw_lv.items()
    elif isinstance(raw_lv, list):
        it = []
        for item in raw_lv:
            if isinstance(item, dict):
                if "name" in item:
                    it.append((str(item["name"]), item.get("elevation_m", item.get("elevation", item.get("z", 0.0)))))
                elif len(item) == 1:
                    k, v = next(iter(item.items()))
                    it.append((str(k), v))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                it.append((str(item[0]), item[1]))
    else:
        it = []
    for k, v in it:
        try:
            levels[str(k)] = float(v)
        except Exception:
            levels[str(k)] = 0.0

    def _norm_poly(poly):
        return [[r2(x), r2(y)] for x, y in poly]

    def _poly_from_item(obj):
        outer_m = obj.get("outer_xy_m"); holes_m = obj.get("inner_loops_xy_m")
        if isinstance(outer_m, list) and len(outer_m) >= 3:
            out_outer = _norm_poly(outer_m); out_holes = []
            if isinstance(holes_m, list):
                for h in holes_m:
                    if isinstance(h, list) and len(h) >= 3:
                        out_holes.append(_norm_poly(h))
            return out_outer, out_holes
        outer_ft = obj.get("outer_xy_ft"); holes_ft = obj.get("inner_loops_xy_ft")
        if isinstance(outer_ft, list) and len(outer_ft) >= 3:
            out_outer = [[float(x)*FT_TO_M, float(y)*FT_TO_M] for x, y in outer_ft]; out_holes = []
            if isinstance(holes_ft, list):
                for h in holes_ft:
                    if isinstance(h, list) and len(h) >= 3:
                        out_holes.append([[float(x)*FT_TO_M, float(y)*FT_TO_M] for x, y in h])
            return _norm_poly(out_outer), [_norm_poly(h) for h in out_holes]
        return None, []

    def _norm_roomlike(src):
        dst = []
        for r in src or []:
            outer, holes = _poly_from_item(r)
            if not outer:
                continue
            dst.append({
                "id": str(r.get("id","")),
                "level": str(r.get("level","")),
                "name": r.get("name",""),
                "number": r.get("number",""),
                "label": r.get("label","") or r.get("name",""),
                "params": r.get("params", {}) if isinstance(r.get("params"), dict) else {},
                "outer_xy_m": _norm_poly(outer),
                "inner_loops_xy_m": [_norm_poly(h) for h in holes]
            })
        return dst

    rooms = _norm_roomlike(data.get("rooms", []))
    areas = _norm_roomlike(data.get("areas", []))
    meta = {"version": data.get("version","bess-export-1"), "units": "Meters", "project": data.get("project", {})}
    return meta, levels, rooms, areas

def save_work_geometry(path, meta, work_levels, work_rooms, work_areas):
    def round_items(items):
        out = []
        for it in items:
            rec = dict(it)
            prs = rec.get("params") or {}
            rec["level"] = prs.get("BESS_level", rec.get("level",""))
            rec["outer_xy_m"] = [[r2(x), r2(y)] for x, y in it["outer_xy_m"]]
            holes = []
            for h in it.get("inner_loops_xy_m", []):
                holes.append([[r2(x), r2(y)] for x, y in h])
            rec["inner_loops_xy_m"] = holes
            out.append(rec)
        return out
    out = {
        "version": meta.get("version","bess-work-1"),
        "units": "Meters",
        "levels": [{"name": n, "elevation_m": float(work_levels[n])} for n in work_levels] if work_levels else [],
        "rooms": round_items(work_rooms),
        "areas": round_items(work_areas)
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
