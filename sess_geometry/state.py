# -*- coding: utf-8 -*-
from copy import deepcopy

ALIAS_TO_PARAM = {
    "BESS_level": "BESS_level",
    "BESS_Upper_level": "BESS_Room_Upper_level",   # алиас для показа
    "BESS_Room_Upper_level": "BESS_Room_Upper_level",
    "BESS_Room_Height": "BESS_Room_Height",        # вычисляемое
}

DEFAULT_ROOM_WORK_COLS = ["id","name","BESS_level","BESS_Upper_level","BESS_Room_Height"]
DEFAULT_AREA_WORK_COLS = ["id","name","BESS_level"]
DEFAULT_OPENING_WORK_COLS = ["id","name","category","opening_type","BESS_level"]
DEFAULT_ROOM_SRC_COLS  = ["id","level","name"]
DEFAULT_AREA_SRC_COLS  = ["id","level","name"]
DEFAULT_OPENING_SRC_COLS = ["id","level","name","category","opening_type"]

class AppState:
    def __init__(self):
        self.meta = {}
        self.base_levels = {}
        self.base_rooms = []
        self.base_areas = []
        self.base_openings = []
        self.work_levels = {}
        self.work_rooms = []
        self.work_areas = []
        self.work_openings = []
        self.selected_level = ""
        self.room_work_cols = DEFAULT_ROOM_WORK_COLS[:]
        self.area_work_cols = DEFAULT_AREA_WORK_COLS[:]
        self.opening_work_cols = DEFAULT_OPENING_WORK_COLS[:]
        self.room_src_cols  = DEFAULT_ROOM_SRC_COLS[:]
        self.area_src_cols  = DEFAULT_AREA_SRC_COLS[:]
        self.opening_src_cols = DEFAULT_OPENING_SRC_COLS[:]

    @staticmethod
    def levels_sorted_names(levels_dict):
        try:
            return [n for n, _ in sorted(levels_dict.items(), key=lambda kv: (float(kv[1]), str(kv[0])))]
        except Exception:
            return sorted(levels_dict.keys(), key=lambda s: str(s))

    @staticmethod
    def _quantize(coords):
        return [[round(float(x), 2), round(float(y), 2)] for x, y in (coords or [])]

    def set_source(self, meta, levels, rooms, areas, openings):
        from copy import deepcopy  # локально на случай прямого вызова

        self.meta = meta
        self.base_levels = deepcopy(levels)
        self.base_rooms  = deepcopy(rooms)
        self.base_areas  = deepcopy(areas)
        self.base_openings = deepcopy(openings)

        # требование: рабочие уровни = источнику
        self.work_levels = deepcopy(self.base_levels)

        # НОВОЕ: автокопия всех помещений и оболочек в рабочую модель
        self.work_rooms = [self._clone_room(r) for r in self.base_rooms]
        self.work_areas = [self._clone_area(a) for a in self.base_areas]
        self.work_openings = [self._clone_opening(o) for o in self.base_openings]

        # выбрать первый уровень
        self.selected_level = self.levels_sorted_names(self.work_levels)[0] if self.work_levels else ""


    def level_elev(self, name, *, from_work=True):
        src = self.work_levels if from_work else self.base_levels
        if not name:
            return None
        if name in src:
            return float(src[name])
        for k, v in src.items():
            if str(k).strip().lower() == str(name).strip().lower():
                return float(v)
        return None

    @staticmethod
    def prefixed_params(src_params):
        out = {}
        for k, v in (src_params or {}).items():
            key = k if k.startswith("BESS_") else "BESS_" + k
            out[key] = v
        return out

    def _clone_room(self, src):
        new = deepcopy(src)
        prs = self.prefixed_params(new.get("params"))
        prs["BESS_level"] = new.get("level", "")
        new["params"] = prs
        new["outer_xy_m"] = self._quantize(new.get("outer_xy_m", []))
        new["inner_loops_xy_m"] = [self._quantize(loop) for loop in new.get("inner_loops_xy_m", [])]
        # установить верхний уровень по правилу и затем высота посчитается «на лету»
        self.ensure_room_upper(new)
        return new

    def _clone_area(self, src):
        new = deepcopy(src)
        prs = self.prefixed_params(new.get("params"))
        prs["BESS_level"] = new.get("level", "")
        new["params"] = prs
        new["outer_xy_m"] = self._quantize(new.get("outer_xy_m", []))
        return new

    def _clone_opening(self, src):
        new = deepcopy(src)
        prs = self.prefixed_params(new.get("params"))
        prs["BESS_level"] = new.get("level", "")
        new["params"] = prs
        new["outer_xy_m"] = self._quantize(new.get("outer_xy_m", []))
        new["inner_loops_xy_m"] = [self._quantize(loop) for loop in new.get("inner_loops_xy_m", [])]
        return new

    def ensure_room_upper(self, room):
        prs = room.get("params") or {}
        base_name = prs.get("BESS_level") or room.get("level","") or ""
        upper = prs.get("BESS_Room_Upper_level") or (room.get("params") or {}).get("Upper Limit") or ""
        if not upper or upper == base_name:
            names = self.levels_sorted_names(self.work_levels)
            try:
                i = names.index(base_name)
                if i+1 < len(names):
                    upper = names[i+1]
            except Exception:
                if names:
                    upper = names[0]
        prs["BESS_Room_Upper_level"] = upper
        room["params"] = prs

    def room_height_m(self, room):
        prs = room.get("params") or {}
        base_name  = prs.get("BESS_level") or room.get("level","")
        upper_name = prs.get("BESS_Room_Upper_level") or ""
        ez = self.level_elev(base_name, from_work=True)
        eu = self.level_elev(upper_name, from_work=True)
        if ez is None or eu is None:
            return ""
        return round(eu - ez, 2)

    def unique_id(self, base):
        base = str(base)
        existing = (
            {str(it.get("id","")) for it in self.work_rooms}
            | {str(it.get("id","")) for it in self.work_areas}
            | {str(it.get("id","")) for it in self.work_openings}
        )
        if base not in existing:
            return base
        i = 1
        while True:
            cand = f"{base}#{i}"
            if cand not in existing:
                return cand
            i += 1

    def add_rooms_to_level(self, ids):
        level = self.selected_level
        id2room = {str(r["id"]): r for r in self.base_rooms}
        new_ids = []
        for rid in ids:
            src = id2room.get(str(rid))
            if not src:
                continue
            new = deepcopy(src)
            new["id"] = self.unique_id(f"{src['id']}@{level}")
            prs = self.prefixed_params(new.get("params"))
            prs["BESS_level"] = level
            new["params"] = prs
            new["outer_xy_m"] = self._quantize(new.get("outer_xy_m", []))
            new["inner_loops_xy_m"] = [self._quantize(loop) for loop in new.get("inner_loops_xy_m", [])]
            self.ensure_room_upper(new)
            new_ids.append(new["id"])
            self.work_rooms.append(new)
        return new_ids

    def add_areas_to_level(self, ids):
        level = self.selected_level
        id2area = {str(a["id"]): a for a in self.base_areas}
        new_ids = []
        for aid in ids:
            src = id2area.get(str(aid))
            if not src:
                continue
            new = deepcopy(src)
            new["id"] = self.unique_id(f"{src['id']}@{level}")
            prs = self.prefixed_params(new.get("params"))
            prs["BESS_level"] = level
            new["params"] = prs
            new["outer_xy_m"] = self._quantize(new.get("outer_xy_m", []))
            new_ids.append(new["id"])
            self.work_areas.append(new)
        return new_ids

    def remove_rooms(self, ids):
        self.work_rooms = [r for r in self.work_rooms if str(r.get("id")) not in set(ids)]

    def remove_areas(self, ids):
        self.work_areas = [a for a in self.work_areas if str(a.get("id")) not in set(ids)]

    def remove_openings(self, ids):
        self.work_openings = [o for o in self.work_openings if str(o.get("id")) not in set(ids)]

    def reset_openings(self):
        self.work_openings = [self._clone_opening(o) for o in self.base_openings]

    def delete_levels(self, level_names):
        self.work_rooms = [r for r in self.work_rooms if (r.get("params",{}).get("BESS_level","") not in level_names)]
        self.work_areas = [a for a in self.work_areas if (a.get("params",{}).get("BESS_level","") not in level_names)]
        self.work_openings = [o for o in self.work_openings if (o.get("params",{}).get("BESS_level","") not in level_names)]
        for n in level_names:
            self.work_levels.pop(n, None)
        names = self.levels_sorted_names(self.work_levels)
        self.selected_level = names[0] if names else ""

    def add_void(self, level, coords):
        i = 1
        for r in self.work_rooms:
            name = str(r.get("name", ""))
            if name.startswith("Void"):
                try:
                    n = int(''.join(ch for ch in name[4:] if ch.isdigit()) or "0")
                    i = max(i, n+1)
                except Exception:
                    pass
        name = f"Void{i}"
        new_id = self.unique_id(name)
        room = {
            "id": new_id,
            "name": name,
            "outer_xy_m": self._quantize(coords),
            "inner_loops_xy_m": [],
            "params": {"BESS_level": level}
        }
        self.ensure_room_upper(room)
        self.work_rooms.append(room)
        return new_id

    def add_second_light(self, base_id, level, coords):
        base = next((r for r in self.work_rooms if str(r.get("id")) == str(base_id)), None)
        if not base:
            return None
        new = deepcopy(base)
        base_name = base.get("name", "")
        new_name = f"{base_name}_2ndL"
        new["name"] = new_name
        new["id"] = self.unique_id(f"{base_id}_2ndL")
        new["outer_xy_m"] = self._quantize(coords)
        new["inner_loops_xy_m"] = []
        prs = deepcopy(base.get("params", {}))
        for k, v in prs.items():
            if isinstance(v, str) and base_name and base_name in v:
                prs[k] = v.replace(base_name, new_name)
        prs["BESS_level"] = level
        new["params"] = prs
        self.ensure_room_upper(new)
        self.work_rooms.append(new)
        return new["id"]

    def update_area_coords(self, area_id, coords):
        """Update outer contour of a working-area polygon."""
        for a in self.work_areas:
            if str(a.get("id")) == str(area_id):
                a["outer_xy_m"] = self._quantize(coords)
                return True
        return False
