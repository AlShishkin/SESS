# -*- coding: utf-8 -*-
import json
from .geometry_utils import r2, FT_TO_M

FT2_TO_M2 = FT_TO_M * FT_TO_M

def load_bess_export(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_lv = data.get("levels", {})
    levels = {}
    level_id_map = {}

    def _register_level(name, elev, lid=None):
        if name is None:
            return
        key = str(name)
        try:
            levels[key] = float(elev)
        except Exception:
            levels[key] = 0.0
        if lid is not None:
            level_id_map[str(lid)] = key

    if isinstance(raw_lv, dict):
        for k, v in raw_lv.items():
            _register_level(k, v)
    elif isinstance(raw_lv, list):
        for item in raw_lv:
            if isinstance(item, dict):
                name = item.get("name")
                lid = item.get("id")
                elev = item.get("elevation_m", item.get("elevation", item.get("z", item.get("elevation_ft", 0.0))))
                if name is None and lid is not None:
                    name = lid
                if name is not None or lid is not None:
                    _register_level(name if name is not None else lid, elev, lid)
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                _register_level(item[0], item[1])
    else:
        pass

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

    def _as_point(pt, *, factor=1.0):
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            try:
                x = float(pt[0]) * factor
                y = float(pt[1]) * factor
                z = float(pt[2]) * factor if len(pt) >= 3 else 0.0
                return [x, y, z]
            except Exception:
                return None
        return None

    def _bbox_metrics(bbox):
        if not isinstance(bbox, dict):
            return None, None, None
        min_m = _as_point(bbox.get("min_m"))
        max_m = _as_point(bbox.get("max_m"))
        if not (min_m and max_m):
            min_ft = _as_point(bbox.get("min_ft"), factor=FT_TO_M)
            max_ft = _as_point(bbox.get("max_ft"), factor=FT_TO_M)
            if min_ft and max_ft:
                min_m, max_m = min_ft, max_ft
        center_m = _as_point(bbox.get("center_m"))
        if not center_m:
            center_ft = _as_point(bbox.get("center_ft"), factor=FT_TO_M)
            if center_ft:
                center_m = center_ft
        return min_m, max_m, center_m

    def _bbox_poly_xy(bbox):
        min_m, max_m, _ = _bbox_metrics(bbox)
        if not (min_m and max_m):
            return None
        try:
            x0 = min(min_m[0], max_m[0])
            x1 = max(min_m[0], max_m[0])
            y0 = min(min_m[1], max_m[1])
            y1 = max(min_m[1], max_m[1])
        except Exception:
            return None
        rect = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        return _norm_poly(rect)

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
        bbox_poly = _bbox_poly_xy(obj.get("bbox"))
        if bbox_poly:
            return bbox_poly, []
        return None, []

    def _poly_from_loop_record(loop):
        if isinstance(loop, dict):
            pts_m = loop.get("xy_m")
            if isinstance(pts_m, list) and len(pts_m) >= 3:
                return _norm_poly(pts_m)
            pts_ft = loop.get("xy_ft")
            if isinstance(pts_ft, list) and len(pts_ft) >= 3:
                pts = []
                for pair in pts_ft:
                    if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                        try:
                            pts.append([float(pair[0]) * FT_TO_M, float(pair[1]) * FT_TO_M])
                        except Exception:
                            continue
                if len(pts) >= 3:
                    return _norm_poly(pts)
        elif isinstance(loop, (list, tuple)) and len(loop) >= 3:
            pts = []
            for pair in loop:
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    try:
                        pts.append([float(pair[0]), float(pair[1])])
                    except Exception:
                        continue
            if len(pts) >= 3:
                return _norm_poly(pts)
        return None

    def _loops_from_record(loop_rec):
        if not isinstance(loop_rec, dict):
            return None, []
        outer = _poly_from_loop_record(loop_rec.get("outer"))
        holes = []
        inners = loop_rec.get("inners")
        if isinstance(inners, list):
            for inner in inners:
                hole = _poly_from_loop_record(inner)
                if hole:
                    holes.append(hole)
        return outer, holes

    def _room_label_from_params(params, prefix):
        if not isinstance(params, dict):
            return ""
        name = str(params.get(f"{prefix}_name", "") or "").strip()
        number = str(params.get(f"{prefix}_number", "") or "").strip()
        label_parts = [part for part in (number, name) if part]
        if label_parts:
            return " ".join(label_parts)
        fallback = params.get(f"{prefix}_id") or params.get(f"{prefix}_unique_id")
        if fallback not in (None, ""):
            return str(fallback)
        return ""

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

            bucket = op.get("__bucket") or op.get("bucket")
            category_name = op.get("category") or op.get("source_category") or ""
            cat_lower = str(category_name).lower()
            if bucket is None:
                if "door" in cat_lower:
                    bucket = "doors"
                elif "window" in cat_lower:
                    bucket = "windows"
                elif any(key in cat_lower for key in ("panel", "glaz", "wall")):
                    bucket = "glazing"
            if bucket and "BESS_source_bucket" not in params:
                params["BESS_source_bucket"] = bucket
            if category_name and "BESS_selection_category" not in params:
                params["BESS_selection_category"] = category_name
            type_name = op.get("type_name")
            if type_name not in (None, "") and "type_name" not in params:
                params["type_name"] = type_name

            bbox = op.get("bbox")
            min_m, max_m, center_m = _bbox_metrics(bbox)
            min_vals = max_vals = None
            size_m = None
            if min_m and max_m:
                min_vals = [min(min_m[i], max_m[i]) for i in range(3)]
                max_vals = [max(min_m[i], max_m[i]) for i in range(3)]
                size_m = [max_vals[i] - min_vals[i] for i in range(3)]
                size_ft = [val / FT_TO_M for val in size_m]

                def _store_point(prefix, coords):
                    if not coords or len(coords) < 3:
                        return
                    params.setdefault(f"{prefix}_x_m", r2(coords[0]))
                    params.setdefault(f"{prefix}_y_m", r2(coords[1]))
                    params.setdefault(f"{prefix}_z_m", r2(coords[2]))
                    params.setdefault(f"{prefix}_x_ft", r2(coords[0] / FT_TO_M))
                    params.setdefault(f"{prefix}_y_ft", r2(coords[1] / FT_TO_M))
                    params.setdefault(f"{prefix}_z_ft", r2(coords[2] / FT_TO_M))

                _store_point("bbox_min", min_vals)
                _store_point("bbox_max", max_vals)
                params.setdefault("bbox_size_x_m", r2(size_m[0]))
                params.setdefault("bbox_size_y_m", r2(size_m[1]))
                params.setdefault("bbox_size_z_m", r2(size_m[2]))
                params.setdefault("bbox_size_x_ft", r2(size_ft[0]))
                params.setdefault("bbox_size_y_ft", r2(size_ft[1]))
                params.setdefault("bbox_size_z_ft", r2(size_ft[2]))
                area_m2 = size_m[0] * size_m[1]
                if abs(area_m2) > 1e-9:
                    params.setdefault("bbox_area_m2", r2(area_m2))
                    params.setdefault("bbox_area_ft2", r2(area_m2 / FT2_TO_M2))
                if abs(size_m[2]) > 1e-9:
                    params.setdefault("height_m", r2(size_m[2]))
                    params.setdefault("height_ft", r2(size_m[2] / FT_TO_M))
            if center_m and len(center_m) >= 3:
                params.setdefault("bbox_center_x_m", r2(center_m[0]))
                params.setdefault("bbox_center_y_m", r2(center_m[1]))
                params.setdefault("bbox_center_z_m", r2(center_m[2]))
                params.setdefault("bbox_center_x_ft", r2(center_m[0] / FT_TO_M))
                params.setdefault("bbox_center_y_ft", r2(center_m[1] / FT_TO_M))
                params.setdefault("bbox_center_z_ft", r2(center_m[2] / FT_TO_M))

            z_rng = op.get("z_range_ft") or op.get("bbox_z_ft")
            if isinstance(z_rng, (list, tuple)) and len(z_rng) == 2:
                params.setdefault("z_min_ft", r2(float(z_rng[0])))
                params.setdefault("z_max_ft", r2(float(z_rng[1])))
                params.setdefault("z_min_m", r2(float(z_rng[0]) * FT_TO_M))
                params.setdefault("z_max_m", r2(float(z_rng[1]) * FT_TO_M))
            elif min_vals and max_vals:
                params.setdefault("z_min_m", r2(min_vals[2]))
                params.setdefault("z_max_m", r2(max_vals[2]))
                params.setdefault("z_min_ft", r2(min_vals[2] / FT_TO_M))
                params.setdefault("z_max_ft", r2(max_vals[2] / FT_TO_M))

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

            from_label = _room_label_from_params(params, "from_room")
            to_label = _room_label_from_params(params, "to_room")
            params["from_room"] = from_label
            params["to_room"] = to_label

            otype = op.get("opening_type")
            if not otype:
                if bucket == "doors":
                    otype = "door"
                elif bucket == "windows":
                    otype = "window"
                elif bucket == "glazing":
                    if "panel" in cat_lower:
                        otype = "curtain_panel"
                    elif "window" in cat_lower:
                        otype = "window"
                    elif "wall" in cat_lower:
                        otype = "wall"
                    else:
                        otype = "glazing"
                else:
                    if "door" in cat_lower:
                        otype = "door"
                    elif "window" in cat_lower:
                        otype = "window"
                    elif "panel" in cat_lower:
                        otype = "curtain_panel"
                    else:
                        otype = ""

            name = op.get("name") or op.get("symbol_name") or type_name or category_name or op.get("opening_type") or bucket or ""
            label = op.get("label") or type_name or category_name or bucket or ""

            rec = {
                "id": str(op.get("id", "")),
                "level": str(op.get("level") or op.get("level_name") or params.get("Level", "")),
                "name": name,
                "number": op.get("number", ""),
                "label": label,
                "category": category_name,
                "opening_type": otype,
                "symbol_name": op.get("symbol_name", ""),
                "unique_id": op.get("unique_id", ""),
                "from_room": from_label,
                "to_room": to_label,
                "params": params,
                "outer_xy_m": _norm_poly(outer),
                "inner_loops_xy_m": [_norm_poly(h) for h in holes]
            }
            dst.append(rec)
        return dst

    raw_openings = data.get("openings")
    openings_src = []
    if isinstance(raw_openings, list) and raw_openings:
        openings_src = raw_openings
    else:
        for bucket_name in ("doors", "windows", "glazing"):
            bucket_items = data.get(bucket_name)
            if not isinstance(bucket_items, list):
                continue
            for item in bucket_items:
                if isinstance(item, dict):
                    cloned = dict(item)
                    cloned["__bucket"] = bucket_name
                    openings_src.append(cloned)
        if not openings_src and isinstance(raw_openings, list):
            openings_src = raw_openings
    openings = _norm_openings(openings_src)

    shaft_details = {}
    raw_shafts = data.get("shafts", [])
    if isinstance(raw_shafts, list):
        for sh in raw_shafts:
            if not isinstance(sh, dict):
                continue
            sid = sh.get("id")
            uid = sh.get("unique_id")
            keys = []
            if sid is not None:
                keys.append(str(sid))
            if uid:
                keys.append(str(uid))
            params = _flatten_params(sh.get("params"))
            height_ft = sh.get("height_ft")
            if isinstance(height_ft, (int, float)):
                params.setdefault("height_ft", r2(float(height_ft)))
                params.setdefault("height_m", r2(float(height_ft) * FT_TO_M))
            area_ft2 = sh.get("poly_area_ft2")
            if isinstance(area_ft2, (int, float)):
                params.setdefault("area_ft2", r2(float(area_ft2)))
                params.setdefault("area_m2", r2(float(area_ft2) * FT2_TO_M2))
            z_rng = sh.get("bbox_z_ft")
            if isinstance(z_rng, (list, tuple)) and len(z_rng) == 2:
                try:
                    zmin = float(min(z_rng[0], z_rng[1]))
                    zmax = float(max(z_rng[0], z_rng[1]))
                    params.setdefault("z_min_ft", r2(zmin))
                    params.setdefault("z_max_ft", r2(zmax))
                    params.setdefault("z_min_m", r2(zmin * FT_TO_M))
                    params.setdefault("z_max_m", r2(zmax * FT_TO_M))
                except Exception:
                    pass
            outer_base, holes_base = _loops_from_record(sh.get("loops", {}))
            meta_rec = {
                "name": sh.get("name", ""),
                "label": sh.get("label", ""),
                "params": params,
                "outer_xy_m": outer_base,
                "inner_loops_xy_m": holes_base or [],
            }
            if not keys:
                keys = [str(uid or sid or len(shaft_details))]
            for k in keys:
                shaft_details[str(k)] = meta_rec

    shafts_by_level = {}
    raw_shaft_levels = data.get("shaft_openings_by_level", [])
    if isinstance(raw_shaft_levels, list):
        for item in raw_shaft_levels:
            if not isinstance(item, dict):
                continue
            lid = item.get("level_id")
            lvl_name = None
            if lid is not None:
                lvl_name = level_id_map.get(str(lid)) or level_id_map.get(lid)
            if not lvl_name:
                level_field = item.get("level")
                if level_field:
                    lvl_name = str(level_field)
            if not lvl_name:
                continue
            bucket = shafts_by_level.setdefault(lvl_name, [])
            for sh in item.get("openings", []):
                if not isinstance(sh, dict):
                    continue
                loop_rec = sh.get("outer") or {}
                outer = _poly_from_loop_record(loop_rec)
                if not outer:
                    continue
                shaft_id = sh.get("shaft_id")
                uid = sh.get("unique_id")
                base_meta = None
                if shaft_id is not None:
                    base_meta = shaft_details.get(str(shaft_id))
                if base_meta is None and uid:
                    base_meta = shaft_details.get(str(uid))
                params = {}
                if base_meta and isinstance(base_meta.get("params"), dict):
                    params.update(base_meta["params"])
                if shaft_id is not None:
                    params.setdefault("shaft_id", str(shaft_id))
                if uid:
                    params.setdefault("shaft_unique_id", uid)
                area_ft2 = None
                if isinstance(loop_rec, dict):
                    area_ft2 = loop_rec.get("area_ft2_abs", loop_rec.get("signed_area_ft2"))
                if isinstance(area_ft2, (int, float)):
                    params.setdefault("area_ft2", r2(abs(float(area_ft2))))
                    params.setdefault("area_m2", r2(abs(float(area_ft2)) * FT2_TO_M2))
                params.setdefault("BESS_level", lvl_name)
                rec = {
                    "id": str(uid or shaft_id or f"{lvl_name}_shaft_{len(bucket)+1}"),
                    "level": lvl_name,
                    "name": (base_meta.get("name") if base_meta else "") or params.get("name") or params.get("Mark") or "Shaft",
                    "label": (base_meta.get("label") if base_meta else "") or params.get("label") or params.get("name") or params.get("Mark") or "Shaft",
                    "unique_id": uid or "",
                    "params": params,
                    "outer_xy_m": outer,
                    "inner_loops_xy_m": []
                }
                holes = []
                if base_meta:
                    for hole in base_meta.get("inner_loops_xy_m", []):
                        if hole:
                            holes.append(_norm_poly(hole))
                rec["inner_loops_xy_m"] = holes
                bucket.append(rec)

    if not shafts_by_level:
        fallback_shafts = data.get("shafts", [])
        if isinstance(fallback_shafts, list):
            for sh in fallback_shafts:
                if not isinstance(sh, dict):
                    continue
                lvl = sh.get("level") or (sh.get("params") or {}).get("BESS_level")
                if not lvl:
                    continue
                outer, holes = _poly_from_item(sh)
                if not outer:
                    outer, holes = _loops_from_record(sh.get("loops", {}))
                if not outer:
                    continue
                params = _flatten_params(sh.get("params"))
                params.setdefault("BESS_level", lvl)
                rec = {
                    "id": str(sh.get("id", "")),
                    "level": str(lvl),
                    "name": sh.get("name", ""),
                    "label": sh.get("label", ""),
                    "unique_id": sh.get("unique_id", ""),
                    "params": params,
                    "outer_xy_m": outer,
                    "inner_loops_xy_m": [_norm_poly(h) for h in holes]
                }
                shafts_by_level.setdefault(str(lvl), []).append(rec)

    version = data.get("version", "bess-export-1")
    meta = {"version": version, "units": "Meters"}
    base_meta = data.get("meta")
    if isinstance(base_meta, dict):
        meta.update(base_meta)
    meta["version"] = version
    project = data.get("project")
    if isinstance(project, dict) and "project" not in meta:
        meta["project"] = project
    filters_info = data.get("filters")
    if isinstance(filters_info, dict):
        meta["filters"] = filters_info
    units_note = data.get("units_note")
    if units_note not in (None, ""):
        meta["units_note"] = units_note
    return meta, levels, rooms, areas, openings, shafts_by_level

def save_work_geometry(path, meta, work_levels, work_rooms, work_areas, work_openings=None, work_shafts=None):
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
    if work_shafts:
        shafts_out = []
        for lvl, items in work_shafts.items():
            for it in items:
                rec = dict(it)
                prs = dict(rec.get("params") or {})
                prs["BESS_level"] = lvl
                rec["level"] = lvl
                rec["params"] = prs
                rec["outer_xy_m"] = [[r2(x), r2(y)] for x, y in it.get("outer_xy_m", [])]
                holes = []
                for h in it.get("inner_loops_xy_m", []):
                    holes.append([[r2(x), r2(y)] for x, y in h])
                rec["inner_loops_xy_m"] = holes
                shafts_out.append(rec)
        out["shafts"] = shafts_out
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
