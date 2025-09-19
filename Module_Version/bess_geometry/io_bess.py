# -*- coding: utf-8 -*-
"""
io_bess.py - Базовый модуль для чтения/записи BESS файлов

Этот файл создан для устранения ошибок импорта в ЭТАП 1.
Содержит минимальную функциональность для загрузки BESS JSON файлов.

ЭТАП 1: Базовая реализация для тестирования render_bess_data()
"""

import json
from typing import Dict, List, Tuple, Any

# Константы для преобразования единиц
FT_TO_M = 0.3048
FT2_TO_M2 = FT_TO_M * FT_TO_M


def r2(x):
    """Округление до 2 знаков после запятой"""
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return 0.0


def load_bess_export(path: str) -> Tuple[Dict, Dict, List, List, List, Dict]:
    """
    Загрузка BESS экспорта из JSON файла
    
    Базовая реализация для ЭТАП 1. Поддерживает стандартный формат BESS JSON.
    
    Args:
        path: Путь к JSON файлу
        
    Returns:
        Tuple: (meta, levels, rooms, areas, openings, shafts)
    """
    print(f"📥 Загрузка BESS файла: {path}")
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        print(f"✅ JSON файл загружен, размер: {len(str(data))} символов")
        
        # Извлекаем метаданные
        meta = _extract_metadata(data)
        
        # Извлекаем уровни
        levels = _extract_levels(data)
        
        # Извлекаем элементы
        rooms = _extract_rooms(data)
        areas = _extract_areas(data)
        openings = _extract_openings(data)
        shafts = _extract_shafts(data)
        
        print(f"📊 Извлечено: {len(rooms)} помещений, {len(areas)} областей, {len(openings)} отверстий")
        
        return meta, levels, rooms, areas, openings, shafts
        
    except FileNotFoundError:
        raise Exception(f"Файл не найден: {path}")
    except json.JSONDecodeError as e:
        raise Exception(f"Ошибка парсинга JSON: {e}")
    except Exception as e:
        raise Exception(f"Ошибка загрузки BESS файла: {e}")


def _extract_metadata(data: Dict) -> Dict:
    """Извлечение метаданных"""
    meta = {
        "version": data.get("version", "bess-export-1.0"),
        "units": "Meters",
        "timestamp": data.get("timestamp", ""),
        "source": data.get("source", ""),
    }
    
    # Добавляем информацию о проекте
    if "project" in data:
        meta["project"] = data["project"]
    
    # Добавляем информацию о фильтрах
    if "filters" in data:
        meta["filters"] = data["filters"]
    
    return meta


def _extract_levels(data: Dict) -> Dict:
    """Извлечение уровней здания"""
    levels = {}
    
    raw_levels = data.get("levels", {})
    
    if isinstance(raw_levels, dict):
        # Формат: {"Level 1": 0.0, "Level 2": 3.5, ...}
        for name, elevation in raw_levels.items():
            try:
                levels[str(name)] = float(elevation)
            except (TypeError, ValueError):
                levels[str(name)] = 0.0
                
    elif isinstance(raw_levels, list):
        # Формат: [{"name": "Level 1", "elevation_m": 0.0}, ...]
        for item in raw_levels:
            if isinstance(item, dict):
                name = item.get("name", f"Level_{len(levels)+1}")
                elevation = item.get("elevation_m", item.get("elevation", 0.0))
                
                try:
                    levels[str(name)] = float(elevation)
                except (TypeError, ValueError):
                    levels[str(name)] = 0.0
    
    # Если уровни не найдены, создаем уровень по умолчанию
    if not levels:
        levels["Level 1"] = 0.0
    
    print(f"🏢 Найдено уровней: {list(levels.keys())}")
    return levels


def _extract_rooms(data: Dict) -> List[Dict]:
    """Извлечение помещений"""
    rooms = []
    
    raw_rooms = data.get("rooms", [])
    if not isinstance(raw_rooms, list):
        return rooms
    
    for i, room_data in enumerate(raw_rooms):
        try:
            room = _normalize_element(room_data, f"Room_{i+1}", "room")
            if room:
                rooms.append(room)
        except Exception as e:
            print(f"⚠️ Ошибка обработки помещения {i}: {e}")
    
    return rooms


def _extract_areas(data: Dict) -> List[Dict]:
    """Извлечение областей"""
    areas = []
    
    raw_areas = data.get("areas", [])
    if not isinstance(raw_areas, list):
        return areas
    
    for i, area_data in enumerate(raw_areas):
        try:
            area = _normalize_element(area_data, f"Area_{i+1}", "area")
            if area:
                areas.append(area)
        except Exception as e:
            print(f"⚠️ Ошибка обработки области {i}: {e}")
    
    return areas


def _extract_openings(data: Dict) -> List[Dict]:
    """Извлечение отверстий"""
    openings = []
    
    raw_openings = data.get("openings", [])
    if not isinstance(raw_openings, list):
        return openings
    
    for i, opening_data in enumerate(raw_openings):
        try:
            opening = _normalize_element(opening_data, f"Opening_{i+1}", "opening")
            if opening:
                openings.append(opening)
        except Exception as e:
            print(f"⚠️ Ошибка обработки отверстия {i}: {e}")
    
    return openings


def _extract_shafts(data: Dict) -> Dict:
    """Извлечение шахт (по уровням)"""
    shafts_by_level = {}
    
    raw_shafts = data.get("shafts", [])
    if not isinstance(raw_shafts, list):
        return shafts_by_level
    
    for i, shaft_data in enumerate(raw_shafts):
        try:
            shaft = _normalize_element(shaft_data, f"Shaft_{i+1}", "shaft")
            if shaft:
                level = shaft.get("params", {}).get("BESS_level", "Level 1")
                if level not in shafts_by_level:
                    shafts_by_level[level] = []
                shafts_by_level[level].append(shaft)
        except Exception as e:
            print(f"⚠️ Ошибка обработки шахты {i}: {e}")
    
    return shafts_by_level


def _normalize_element(element_data: Dict, default_name: str, element_type: str) -> Dict:
    """
    Нормализация элемента для единообразного формата
    
    Args:
        element_data: Исходные данные элемента
        default_name: Имя по умолчанию
        element_type: Тип элемента
        
    Returns:
        Нормализованный элемент
    """
    if not isinstance(element_data, dict):
        return None
    
    # Базовая структура
    element = {
        "id": element_data.get("id", default_name),
        "name": element_data.get("name", default_name),
        "element_type": element_type,
        "outer_xy_m": [],
        "inner_loops_xy_m": [],
        "params": {}
    }
    
    # Извлекаем геометрию
    element["outer_xy_m"] = _normalize_polygon(element_data.get("outer_xy_m", 
                                                              element_data.get("contour", 
                                                                              element_data.get("geometry", []))))
    
    # Извлекаем внутренние контуры
    inner_loops = element_data.get("inner_loops_xy_m", element_data.get("holes", []))
    if isinstance(inner_loops, list):
        element["inner_loops_xy_m"] = [_normalize_polygon(loop) for loop in inner_loops]
    
    # Извлекаем параметры
    params = element_data.get("params", {})
    if isinstance(params, dict):
        element["params"] = params.copy()
    
    # Добавляем уровень
    level = element_data.get("level", element_data.get("BESS_level", "Level 1"))
    element["params"]["BESS_level"] = level
    
    # Добавляем дополнительные свойства
    for key in ["area", "area_m2", "volume", "height", "category", "type", "function"]:
        if key in element_data:
            element[key] = element_data[key]
    
    # Проверяем валидность геометрии
    if len(element["outer_xy_m"]) < 3:
        print(f"⚠️ Элемент {element['id']} имеет недостаточно точек для отрисовки")
        return None
    
    return element


def _normalize_polygon(raw_polygon) -> List[List[float]]:
    """
    Нормализация полигона в формат [[x1,y1], [x2,y2], ...]
    
    Args:
        raw_polygon: Исходная геометрия в различных форматах
        
    Returns:
        Нормализованный полигон
    """
    if not raw_polygon:
        return []
    
    if not isinstance(raw_polygon, list):
        return []
    
    normalized = []
    
    for point in raw_polygon:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                x = r2(point[0])
                y = r2(point[1])
                normalized.append([x, y])
            except (TypeError, ValueError, IndexError):
                continue
        elif isinstance(point, dict):
            try:
                x = r2(point.get("x", point.get("X", 0)))
                y = r2(point.get("y", point.get("Y", 0)))
                normalized.append([x, y])
            except (TypeError, ValueError):
                continue
    
    return normalized


def save_work_geometry(path: str, meta: Dict, work_levels: Dict, work_rooms: List, 
                      work_areas: List, work_openings: List = None, work_shafts: Dict = None):
    """
    Сохранение рабочей геометрии в JSON файл
    
    Базовая реализация для ЭТАП 1.
    
    Args:
        path: Путь для сохранения
        meta: Метаданные
        work_levels: Уровни здания
        work_rooms: Помещения
        work_areas: Области
        work_openings: Отверстия (опционально)
        work_shafts: Шахты (опционально)
    """
    print(f"💾 Сохранение рабочей геометрии: {path}")
    
    try:
        # Формируем выходную структуру
        output = {
            "version": meta.get("version", "bess-work-1.0"),
            "units": "Meters",
            "timestamp": meta.get("timestamp", ""),
            "levels": [{"name": name, "elevation_m": float(elevation)} 
                      for name, elevation in work_levels.items()],
            "rooms": _round_elements(work_rooms),
            "areas": _round_elements(work_areas)
        }
        
        # Добавляем опциональные элементы
        if work_openings:
            output["openings"] = _round_elements(work_openings)
        
        if work_shafts:
            shafts_list = []
            for level, shafts in work_shafts.items():
                for shaft in shafts:
                    shaft_copy = shaft.copy()
                    shaft_copy["level"] = level
                    shafts_list.append(shaft_copy)
            output["shafts"] = _round_elements(shafts_list)
        
        # Сохраняем файл
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Файл сохранен: {path}")
        
    except Exception as e:
        raise Exception(f"Ошибка сохранения файла: {e}")


def _round_elements(elements: List[Dict]) -> List[Dict]:
    """Округление координат элементов для сохранения"""
    rounded = []
    
    for element in elements:
        if not isinstance(element, dict):
            continue
        
        element_copy = element.copy()
        
        # Округляем внешний контур
        if "outer_xy_m" in element_copy:
            element_copy["outer_xy_m"] = [[r2(x), r2(y)] for x, y in element_copy["outer_xy_m"]]
        
        # Округляем внутренние контуры
        if "inner_loops_xy_m" in element_copy:
            element_copy["inner_loops_xy_m"] = [
                [[r2(x), r2(y)] for x, y in loop] 
                for loop in element_copy["inner_loops_xy_m"]
            ]
        
        # Извлекаем уровень в корень
        if "params" in element_copy and "BESS_level" in element_copy["params"]:
            element_copy["level"] = element_copy["params"]["BESS_level"]
        
        rounded.append(element_copy)
    
    return rounded


# Дополнительные функции для совместимости
def create_test_data() -> Tuple[Dict, Dict, List, List, List, Dict]:
    """
    Создание тестовых данных для проверки render_bess_data()
    
    Returns:
        Тестовые данные в формате BESS
    """
    meta = {
        "version": "bess-test-1.0",
        "units": "Meters",
        "project": {"name": "Test Building", "description": "Test data for ЭТАП 1"}
    }
    
    levels = {
        "Level 1": 0.0,
        "Level 2": 3.5
    }
    
    rooms = [
        {
            "id": "room_1",
            "name": "Офис 1",
            "element_type": "room",
            "outer_xy_m": [[0, 0], [5, 0], [5, 3], [0, 3], [0, 0]],
            "inner_loops_xy_m": [],
            "params": {"BESS_level": "Level 1"},
            "area_m2": 15.0
        },
        {
            "id": "room_2",
            "name": "Офис 2", 
            "element_type": "room",
            "outer_xy_m": [[6, 0], [10, 0], [10, 3], [6, 3], [6, 0]],
            "inner_loops_xy_m": [],
            "params": {"BESS_level": "Level 1"},
            "area_m2": 12.0
        },
        {
            "id": "room_3",
            "name": "Конференц-зал",
            "element_type": "room", 
            "outer_xy_m": [[0, 4], [10, 4], [10, 8], [0, 8], [0, 4]],
            "inner_loops_xy_m": [],
            "params": {"BESS_level": "Level 1"},
            "area_m2": 40.0
        }
    ]
    
    areas = []
    openings = []
    shafts = {}
    
    return meta, levels, rooms, areas, openings, shafts


if __name__ == "__main__":
    """Тестирование модуля io_bess"""
    print("🧪 Тестирование io_bess модуля")
    
    # Создаем тестовые данные
    meta, levels, rooms, areas, openings, shafts = create_test_data()
    
    print(f"📊 Тестовые данные созданы:")
    print(f"  • Уровни: {list(levels.keys())}")
    print(f"  • Помещения: {len(rooms)}")
    print(f"  • Области: {len(areas)}")
    print(f"  • Отверстия: {len(openings)}")
    
    # Тестируем сохранение
    test_file = "test_bess_data.json"
    try:
        save_work_geometry(test_file, meta, levels, rooms, areas, openings, shafts)
        print(f"✅ Тестовый файл сохранен: {test_file}")
        
        # Тестируем загрузку
        loaded_meta, loaded_levels, loaded_rooms, loaded_areas, loaded_openings, loaded_shafts = load_bess_export(test_file)
        print(f"✅ Тестовый файл загружен обратно")
        print(f"  • Загружено помещений: {len(loaded_rooms)}")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
    
    print("🎉 Тестирование завершено")