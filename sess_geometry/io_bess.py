# -*- coding: utf-8 -*-
import json
from .geometry_utils import r2, FT_TO_M

FT2_TO_M2 = FT_TO_M * FT_TO_M

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

    def _flatten_params(raw):
        if not isinstance(raw, dict):
            return {}

        def _norm_val(val):
            if isinstance(val, (int, float)):
                return r2(val) if isinstance(val, float) else val
            if val is None:
                return ""
            if isinstance(val, (list, tuple)):
                return ", ".join(str(x) for x in val)
            return str(val)

        flat = {}
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
                        flat[str(name)] = _norm_val(val)
                    else:
                        flat[str(name)] = _norm_val(info)
        for name, value in raw.items():
            if name in ("instance", "type"):
                continue
            flat[str(name)] = _norm_val(value)
        return flat

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
                "params": _flatten_params(r.get("params")),
                "outer_xy_m": _norm_poly(outer),
                "inner_loops_xy_m": [_norm_poly(h) for h in holes]
            })
        return dst

    rooms = _norm_roomlike(data.get("rooms", []))
    areas = _norm_roomlike(data.get("areas", []))
    
    def _poly_from_opening(obj):
        outer, holes = _poly_from_item(obj)
        if outer:
            return outer, holes
        fp = obj.get("footprint", {})
        if isinstance(fp, dict):
            outer = fp.get("xy_m")
            holes = fp.get("inner_loops_xy_m") or []
            if isinstance(outer, list) and len(outer) >= 3:
                out_outer = _norm_poly(outer)
                out_holes = []
                for h in holes:
                    if isinstance(h, list) and len(h) >= 3:
                        out_holes.append(_norm_poly(h))
                return out_outer, out_holes
            outer_ft = fp.get("xy_ft")
            if isinstance(outer_ft, list) and len(outer_ft) >= 3:
                out_outer = [[float(x)*FT_TO_M, float(y)*FT_TO_M] for x, y in outer_ft]
                out_holes = []
                for h in holes:
                    if isinstance(h, list) and len(h) >= 3:
                        out_holes.append([[float(x)*FT_TO_M, float(y)*FT_TO_M] for x, y in h])
                return _norm_poly(out_outer), [_norm_poly(h) for h in out_holes]
        return None, []

    def _norm_openings(src):
        dst = []
        for op in src or []:
            outer, holes = _poly_from_opening(op)
            if not outer:
                continue
            params = _flatten_params(op.get("params"))
            level_id = op.get("level_id")
            if level_id is not None and "level_id" not in params:
                params["level_id"] = str(level_id)
            z_rng = op.get("z_range_ft") or op.get("bbox_z_ft")
            if isinstance(z_rng, (list, tuple)) and len(z_rng) == 2:
                params.setdefault("z_min_ft", r2(float(z_rng[0])))
                params.setdefault("z_max_ft", r2(float(z_rng[1])))
                params.setdefault("z_min_m", r2(float(z_rng[0]) * FT_TO_M))
                params.setdefault("z_max_m", r2(float(z_rng[1]) * FT_TO_M))
            geom = op.get("geom") or {}
            def _set_num(dst_key, value, *, metric_key=None, metric_factor=1.0):
                if isinstance(value, (int, float)):
                    params.setdefault(dst_key, r2(float(value)))
                    if metric_key:
                        params.setdefault(metric_key, r2(float(value) * metric_factor))
            _set_num("width_ft", op.get("width_ft"), metric_key="width_m", metric_factor=FT_TO_M)
            _set_num("width_ft", geom.get("width_ft"), metric_key="width_m", metric_factor=FT_TO_M)
            _set_num("height_ft", op.get("height_ft"), metric_key="height_m", metric_factor=FT_TO_M)
            _set_num("height_ft", geom.get("height_ft"), metric_key="height_m", metric_factor=FT_TO_M)
            _set_num("host_thickness_ft", geom.get("host_thickness_ft"), metric_key="host_thickness_m", metric_factor=FT_TO_M)
            _set_num("area_ft2", geom.get("area_ft2"), metric_key="area_m2", metric_factor=FT2_TO_M2)
            _set_num("approx_face_area_ft2", geom.get("approx_face_area_ft2"), metric_key="approx_face_area_m2", metric_factor=FT2_TO_M2)
            facing = op.get("facing_dir")
            if isinstance(facing, (list, tuple)) and facing and "facing_dir" not in params:
                params["facing_dir"] = [r2(float(x)) for x in facing]
            hand = op.get("hand_dir")
            if isinstance(hand, (list, tuple)) and hand and "hand_dir" not in params:
                params["hand_dir"] = [r2(float(x)) for x in hand]
            host_id = op.get("host_id")
            if host_id is not None and "host_id" not in params:
                params["host_id"] = str(host_id)
            link = op.get("in_link")
            if isinstance(link, dict):
                for k, v in link.items():
                    if k not in params:
                        params[k] = v
            for rel in ("from_room", "to_room"):
                if rel in op and isinstance(op[rel], dict):
                    brief = op[rel].get("brief") if isinstance(op[rel], dict) else None
                    if isinstance(brief, dict):
                        for k, v in brief.items():
                            params.setdefault(f"{rel}_{k}", v)
            otype = op.get("opening_type")
            if not otype:
                cat = str(op.get("category") or op.get("source_category") or "").lower()
                if "door" in cat:
                    otype = "door"
                elif "window" in cat:
                    otype = "window"
                elif "panel" in cat:
                    otype = "curtain_panel"
                else:
                    otype = ""
            rec = {
                "id": str(op.get("id","")),
                "level": str(op.get("level") or op.get("level_name") or params.get("Level", "")),
                "name": op.get("name") or op.get("symbol_name") or op.get("category") or op.get("opening_type") or "",
                "number": op.get("number", ""),
                "label": op.get("label", "") or op.get("category", ""),
                "category": op.get("category", ""),
                "opening_type": otype,
                "symbol_name": op.get("symbol_name", ""),
                "unique_id": op.get("unique_id", ""),
                "params": params,
                "outer_xy_m": _norm_poly(outer),
                "inner_loops_xy_m": [_norm_poly(h) for h in holes]
            }
            dst.append(rec)
        return dst

    openings = _norm_openings(data.get("openings", []) or (data.get("doors", []) + data.get("windows", [])))

    meta = {"version": data.get("version","bess-export-1"), "units": "Meters", "project": data.get("project", {})}
    return meta, levels, rooms, areas, openings

def save_work_geometry(path, meta, work_levels, work_rooms, work_areas, work_openings=None):
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
    if work_openings is not None:
        out["openings"] = round_items(work_openings)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
