# -*- coding: utf-8 -*-
"""
state.py - Управление состоянием приложения BESS_Geometry

Этот модуль создан для устранения ошибки 'AppState' object has no attribute 'set_source'

ЭТАП 1: Базовая реализация AppState с методом set_source()
"""

import json
import threading
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from copy import deepcopy
import uuid


@dataclass
class UserPreferences:
    """Пользовательские настройки"""
    # Настройки интерфейса
    theme: str = "default"
    language: str = "ru"
    auto_save_enabled: bool = True
    auto_save_interval: int = 300  # секунды
    
    # Настройки отрисовки
    show_grid: bool = True
    grid_size: float = 1.0  # метры
    snap_to_grid: bool = True
    snap_tolerance: float = 0.1  # метры
    
    # Настройки производительности
    max_visible_elements: int = 5000
    use_render_cache: bool = True
    cache_size: int = 1000
    
    # Цветовая схема
    colors: Dict[str, str] = field(default_factory=lambda: {
        'room_fill': '#4cc9f0',
        'room_outline': '#333333',
        'area_fill': '#ff6b6b', 
        'area_outline': '#666666',
        'opening_fill': '#ffd93d',
        'opening_outline': '#333333',
        'selected_outline': '#00ff00',
        'background': '#ffffff',
        'grid': '#e0e0e0'
    })
    
    # Настройки единиц измерения
    units: str = "metric"  # "metric" или "imperial"
    coordinate_precision: int = 2  # количество знаков после запятой


class StateChangeEvent:
    """Событие изменения состояния"""
    
    def __init__(self, path: str, old_value: Any, new_value: Any, source: str = "unknown"):
        self.path = path
        self.old_value = old_value
        self.new_value = new_value
        self.source = source
        self.timestamp = datetime.now()
        self.event_id = str(uuid.uuid4())


class AppState:
    """
    Центральное хранилище состояния приложения BESS_Geometry
    
    ЭТАП 1: Базовая реализация с методом set_source() для совместимости с legacy кодом
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Инициализация состояния приложения
        
        Args:
            config_dir: Директория конфигурации (опционально)
        """
        print("🏗️ Инициализация AppState")
        
        # Основные данные проекта
        self.meta = {}
        self.base_levels = {}  # Исходные уровни
        self.selected_level = ""
        
        # Исходные данные (source) - неизменяемые после загрузки
        self.source_rooms = []
        self.source_areas = []
        self.source_openings = []
        self.source_shafts = {}
        
        # Рабочие данные (work) - изменяемые в процессе редактирования
        self.work_rooms = []
        self.work_areas = []
        self.work_openings = []
        self.work_shafts = {}
        
        # Состояние приложения
        self.selected_elements = set()
        self.clipboard = []
        self.undo_stack = []
        self.redo_stack = []
        
        # Настройки пользователя
        self.preferences = UserPreferences()
        
        # Метаданные состояния
        self.is_modified = False
        self.last_saved = None
        self.current_file_path = None
        
        # Система событий
        self._event_listeners = {}
        self._lock = threading.Lock()
        
        print("✅ AppState инициализирован")
    
    def set_source(self, meta: Dict, levels: Dict, rooms: List, areas: List, openings: List, shafts: Dict):
        """
        Установка исходных данных (source data)
        
        Этот метод устанавливает исходные данные, которые не изменяются в процессе работы.
        Рабочие копии создаются автоматически для редактирования.
        
        Args:
            meta: Метаданные проекта
            levels: Уровни здания {name: elevation}
            rooms: Список помещений
            areas: Список областей
            openings: Список отверстий
            shafts: Шахты по уровням {level: [shafts]}
        """
        print("📥 Установка исходных данных в AppState")
        
        with self._lock:
            # Сохраняем исходные данные
            self.meta = deepcopy(meta) if meta else {}
            self.base_levels = deepcopy(levels) if levels else {}
            self.source_rooms = deepcopy(rooms) if rooms else []
            self.source_areas = deepcopy(areas) if areas else []
            self.source_openings = deepcopy(openings) if openings else []
            self.source_shafts = deepcopy(shafts) if shafts else {}
            
            # Создаем рабочие копии для редактирования
            self.work_rooms = deepcopy(self.source_rooms)
            self.work_areas = deepcopy(self.source_areas)
            self.work_openings = deepcopy(self.source_openings)
            self.work_shafts = deepcopy(self.source_shafts)
            
            # Устанавливаем первый доступный уровень
            if self.base_levels:
                self.selected_level = next(iter(self.base_levels.keys()))
            
            # Очищаем состояние редактирования
            self.selected_elements.clear()
            self.clipboard.clear()
            self.undo_stack.clear()
            self.redo_stack.clear()
            
            # Нормализуем данные
            self._normalize_elements()
            
            # Отмечаем как неизмененное (только что загружено)
            self.is_modified = False
            
        print(f"✅ Данные установлены: {len(self.work_rooms)} помещений, {len(self.work_areas)} областей, {len(self.work_openings)} отверстий")
        print(f"🏢 Доступные уровни: {list(self.base_levels.keys())}")
        print(f"📍 Выбранный уровень: {self.selected_level}")
        
        # Уведомляем о загрузке данных
        self._fire_event('data_loaded', {
            'rooms_count': len(self.work_rooms),
            'areas_count': len(self.work_areas),
            'openings_count': len(self.work_openings),
            'levels': list(self.base_levels.keys())
        })
    
    def _normalize_elements(self):
        """Нормализация данных элементов"""
        print("🔧 Нормализация элементов...")
        
        # Нормализуем помещения
        for room in self.work_rooms:
            self._normalize_element(room, 'room')
        
        # Нормализуем области
        for area in self.work_areas:
            self._normalize_element(area, 'area')
        
        # Нормализуем отверстия
        for opening in self.work_openings:
            self._normalize_element(opening, 'opening')
        
        # Нормализуем шахты
        for level, shafts in self.work_shafts.items():
            for shaft in shafts:
                self._normalize_element(shaft, 'shaft')
    
    def _normalize_element(self, element: Dict, element_type: str):
        """Нормализация одного элемента"""
        if not isinstance(element, dict):
            return
        
        # Устанавливаем тип элемента
        if 'element_type' not in element:
            element['element_type'] = element_type
        
        # Проверяем наличие ID
        if 'id' not in element:
            element['id'] = self.unique_id(f"{element_type}_{len(self.work_rooms) + len(self.work_areas) + len(self.work_openings)}")
        
        # Проверяем наличие имени
        if 'name' not in element:
            element['name'] = element['id']
        
        # Проверяем геометрию
        if 'outer_xy_m' not in element:
            element['outer_xy_m'] = []
        
        if 'inner_loops_xy_m' not in element:
            element['inner_loops_xy_m'] = []
        
        # Проверяем параметры
        if 'params' not in element:
            element['params'] = {}
        
        # Устанавливаем уровень
        if 'BESS_level' not in element['params']:
            element['params']['BESS_level'] = self.selected_level or 'Level 1'
    
    def unique_id(self, base_name: str = "element") -> str:
        """
        Генерация уникального ID
        
        Args:
            base_name: Базовое имя для ID
            
        Returns:
            Уникальный ID
        """
        # Собираем все существующие ID
        existing_ids = set()
        
        for room in self.work_rooms:
            existing_ids.add(room.get('id', ''))
        
        for area in self.work_areas:
            existing_ids.add(area.get('id', ''))
        
        for opening in self.work_openings:
            existing_ids.add(opening.get('id', ''))
        
        for shafts in self.work_shafts.values():
            for shaft in shafts:
                existing_ids.add(shaft.get('id', ''))
        
        # Генерируем уникальный ID
        counter = 1
        while True:
            candidate_id = f"{base_name}_{counter}"
            if candidate_id not in existing_ids:
                return candidate_id
            counter += 1
    
    def get_current_level_elements(self) -> Dict[str, List]:
        """
        Получение элементов текущего уровня
        
        Returns:
            Словарь с элементами: {'rooms': [...], 'areas': [...], 'openings': [...]}
        """
        current_level = self.selected_level
        
        rooms = [r for r in self.work_rooms 
                if r.get('params', {}).get('BESS_level', '') == current_level]
        
        areas = [a for a in self.work_areas 
                if a.get('params', {}).get('BESS_level', '') == current_level]
        
        openings = [o for o in self.work_openings 
                   if o.get('params', {}).get('BESS_level', '') == current_level]
        
        return {
            'rooms': rooms,
            'areas': areas,
            'openings': openings
        }
    
    def set_selected_level(self, level_name: str):
        """
        Установка текущего уровня
        
        Args:
            level_name: Название уровня
        """
        if level_name in self.base_levels:
            old_level = self.selected_level
            self.selected_level = level_name
            
            print(f"📍 Переключение на уровень: {level_name}")
            
            # Очищаем выбор при смене уровня
            self.selected_elements.clear()
            
            # Уведомляем о смене уровня
            self._fire_event('level_changed', {
                'old_level': old_level,
                'new_level': level_name
            })
    
    def mark_modified(self):
        """Отметка состояния как измененного"""
        self.is_modified = True
        self._fire_event('state_modified', {'modified': True})
    
    def mark_saved(self):
        """Отметка состояния как сохраненного"""
        self.is_modified = False
        self.last_saved = datetime.now()
        self._fire_event('state_saved', {'saved_at': self.last_saved})
    
    def add_event_listener(self, event_type: str, callback):
        """
        Добавление слушателя событий
        
        Args:
            event_type: Тип события
            callback: Функция обратного вызова
        """
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = []
        self._event_listeners[event_type].append(callback)
    
    def remove_event_listener(self, event_type: str, callback):
        """Удаление слушателя событий"""
        if event_type in self._event_listeners:
            try:
                self._event_listeners[event_type].remove(callback)
            except ValueError:
                pass
    
    def _fire_event(self, event_type: str, data: Dict = None):
        """Генерация события"""
        if event_type in self._event_listeners:
            for callback in self._event_listeners[event_type]:
                try:
                    callback(data or {})
                except Exception as e:
                    print(f"⚠️ Ошибка в обработчике события {event_type}: {e}")
    
    def get_stats(self) -> Dict:
        """Получение статистики состояния"""
        return {
            'rooms_count': len(self.work_rooms),
            'areas_count': len(self.work_areas),
            'openings_count': len(self.work_openings),
            'levels_count': len(self.base_levels),
            'selected_elements_count': len(self.selected_elements),
            'is_modified': self.is_modified,
            'current_level': self.selected_level,
            'last_saved': self.last_saved.isoformat() if self.last_saved else None
        }
    
    def save_to_file(self, filepath: str):
        """
        Сохранение состояния в файл
        
        Args:
            filepath: Путь к файлу
        """
        try:
            from io_bess import save_work_geometry
            
            save_work_geometry(
                filepath,
                self.meta,
                self.base_levels,
                self.work_rooms,
                self.work_areas,
                self.work_openings,
                self.work_shafts
            )
            
            self.current_file_path = filepath
            self.mark_saved()
            
            print(f"💾 Состояние сохранено в файл: {filepath}")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения состояния: {e}")
            raise
    
    def clear(self):
        """Очистка всех данных"""
        print("🧹 Очистка состояния AppState")
        
        with self._lock:
            self.meta.clear()
            self.base_levels.clear()
            self.selected_level = ""
            
            self.source_rooms.clear()
            self.source_areas.clear()
            self.source_openings.clear()
            self.source_shafts.clear()
            
            self.work_rooms.clear()
            self.work_areas.clear()
            self.work_openings.clear()
            self.work_shafts.clear()
            
            self.selected_elements.clear()
            self.clipboard.clear()
            self.undo_stack.clear()
            self.redo_stack.clear()
            
            self.is_modified = False
            self.last_saved = None
            self.current_file_path = None
        
        self._fire_event('state_cleared', {})


# Псевдонимы для совместимости с legacy кодом
ALIAS_TO_PARAM = {
    # Псевдонимы для цветов
    'room_color': 'preferences.colors.room_fill',
    'area_color': 'preferences.colors.area_fill',
    'opening_color': 'preferences.colors.opening_fill',
    'selected_color': 'preferences.colors.selected_outline',
    'background_color': 'preferences.colors.background',
    
    # Псевдонимы для масштаба и позиции
    'scale': 'viewport.scale',
    'center_x': 'viewport.center_x',
    'center_y': 'viewport.center_y',
    
    # Псевдонимы для режимов
    'mode': 'edit_mode',
    'level': 'current_level',
    
    # Псевдонимы для производительности
    'cache_enabled': 'preferences.use_render_cache',
    'cache_size': 'preferences.cache_size',
    'max_elements': 'preferences.max_visible_elements'
}


# Глобальный экземпляр состояния приложения
_global_app_state: Optional[AppState] = None
_state_lock = threading.Lock()


def get_app_state() -> AppState:
    """Получение глобального экземпляра состояния приложения"""
    global _global_app_state
    
    if _global_app_state is None:
        with _state_lock:
            if _global_app_state is None:
                _global_app_state = AppState()
    
    return _global_app_state


def initialize_app_state(config_dir: Optional[Path] = None) -> AppState:
    """
    Инициализация глобального состояния приложения
    
    Args:
        config_dir: Директория конфигурации
        
    Returns:
        Экземпляр состояния приложения
    """
    global _global_app_state
    
    with _state_lock:
        _global_app_state = AppState(config_dir)
    
    return _global_app_state


def reset_app_state() -> None:
    """Сброс глобального состояния приложения"""
    global _global_app_state
    
    with _state_lock:
        _global_app_state = None


# Функция для создания тестового состояния
def create_test_state() -> AppState:
    """
    Создание тестового состояния для проверки приложения
    
    Returns:
        AppState с тестовыми данными
    """
    print("🧪 Создание тестового состояния")
    
    app_state = AppState()
    
    # Тестовые метаданные
    meta = {
        "version": "bess-test-1.0",
        "project": {"name": "Test Building", "description": "Test data for ЭТАП 1"}
    }
    
    # Тестовые уровни
    levels = {
        "Level 1": 0.0,
        "Level 2": 3.5
    }
    
    # Тестовые помещения
    rooms = [
        {
            "id": "room_1",
            "name": "Офис 1",
            "outer_xy_m": [[0, 0], [5, 0], [5, 3], [0, 3], [0, 0]],
            "inner_loops_xy_m": [],
            "params": {"BESS_level": "Level 1"},
            "area_m2": 15.0
        },
        {
            "id": "room_2",
            "name": "Офис 2", 
            "outer_xy_m": [[6, 0], [10, 0], [10, 3], [6, 3], [6, 0]],
            "inner_loops_xy_m": [],
            "params": {"BESS_level": "Level 1"},
            "area_m2": 12.0
        },
        {
            "id": "room_3",
            "name": "Конференц-зал",
            "outer_xy_m": [[0, 4], [10, 4], [10, 8], [0, 8], [0, 4]],
            "inner_loops_xy_m": [],
            "params": {"BESS_level": "Level 1"},
            "area_m2": 40.0
        }
    ]
    
    # Устанавливаем данные
    app_state.set_source(meta, levels, rooms, [], [], {})
    
    print("✅ Тестовое состояние создано")
    return app_state


if __name__ == "__main__":
    """Тестирование модуля state"""
    print("🧪 Тестирование state модуля")
    
    # Создаем тестовое состояние
    test_state = create_test_state()
    
    # Проверяем статистику
    stats = test_state.get_stats()
    print(f"📊 Статистика состояния:")
    for key, value in stats.items():
        print(f"  • {key}: {value}")
    
    # Тестируем смену уровня
    test_state.set_selected_level("Level 2")
    
    # Получаем элементы уровня
    elements = test_state.get_current_level_elements()
    print(f"📍 Элементы Level 2: {len(elements['rooms'])} помещений")
    
    test_state.set_selected_level("Level 1")
    elements = test_state.get_current_level_elements()
    print(f"📍 Элементы Level 1: {len(elements['rooms'])} помещений")
    
    print("🎉 Тестирование завершено")