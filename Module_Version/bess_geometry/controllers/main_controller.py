# -*- coding: utf-8 -*-
"""
MainController - центральный контроллер системы BESS_GEOMETRY

Этот контроллер является "дирижером оркестра" - он координирует работу всех компонентов
и обеспечивает правильное взаимодействие между UI, данными и бизнес-логикой.

Основные принципы:
- Единая точка входа для всех операций пользователя
- Координация между различными подсистемами
- Управление состоянием приложения
- Обеспечение консистентности данных
- Централизованная обработка команд
"""

import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Dict, List, Set, Optional, Tuple, Callable, Any
from copy import deepcopy
from datetime import datetime
from enum import Enum

from ..state import AppState
from ..core.spatial_processor import SpatialProcessor
from ..core.geometry_operations import GeometryOperations, DrawingMode, OperationType
from ..io_bess import load_bess_export, save_work_geometry
from ..performance import PerformanceMonitor, RenderCache, SpatialIndex


class ApplicationMode(Enum):
    """Режимы работы приложения"""
    NORMAL = "normal"           # Обычный режим (просмотр, выбор)
    DRAWING = "drawing"         # Режим рисования
    EDITING = "editing"         # Режим редактирования
    ANALYZING = "analyzing"     # Режим анализа геометрии


class MainController:
    """
    Главный контроллер системы BESS_GEOMETRY
    
    Координирует взаимодействие между всеми компонентами системы:
    - Управляет состоянием приложения
    - Обрабатывает команды пользователя
    - Обеспечивает синхронизацию данных
    - Координирует операции с файлами
    """
    
    def __init__(self, root_window: tk.Tk):
        """
        Инициализация главного контроллера
        
        Args:
            root_window: Главное окно приложения Tkinter
        """
        self.root = root_window
        
        # Основные компоненты системы
        self.state = AppState()
        self.spatial_processor = SpatialProcessor()
        self.geometry_operations = GeometryOperations()
        
        # Компоненты производительности
        self.performance_monitor = PerformanceMonitor()
        self.render_cache = RenderCache(max_size=2000)
        self.spatial_index = SpatialIndex(grid_size=10.0)
        
        # Текущее состояние приложения
        self.current_mode = ApplicationMode.NORMAL
        self.current_drawing_mode = DrawingMode.NONE
        self.selected_elements = set()  # ID выбранных элементов
        
        # Обработчики событий
        self.event_handlers: Dict[str, List[Callable]] = {
            'data_changed': [],
            'selection_changed': [], 
            'mode_changed': [],
            'geometry_updated': [],
            'file_loaded': [],
            'level_changed': []
        }
        
        # Контроллеры подкомпонентов (будут созданы позже)
        self.canvas_controller = None
        
        # История операций для Undo/Redo
        self.operation_history = []
        self.current_operation_index = -1
        self.max_history_size = 100
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Инициализация всех компонентов системы"""
        # Подключаем обработчики событий к компонентам
        self.geometry_operations.set_validation_callback(
            self.spatial_processor.validate_geometry
        )
        
        # Настраиваем систему отмены/повтора
        self.geometry_operations.set_history_callback(
            self._on_operation_completed
        )
    
    def set_canvas_controller(self, canvas_controller):
        """
        Установка контроллера canvas после его создания
        
        Args:
            canvas_controller: Экземпляр CanvasController
        """
        self.canvas_controller = canvas_controller
        
        # Подключаем обработчики событий canvas
        canvas_controller.set_selection_handler(self._on_selection_changed)
        canvas_controller.set_interaction_handler(self._on_canvas_interaction)
    
    # === УПРАВЛЕНИЕ ФАЙЛАМИ ===
    
    def load_bess_file(self, filepath: Optional[str] = None) -> bool:
        """
        Загрузка файла экспорта из BESS
        
        Args:
            filepath: Путь к файлу (если None - показывает диалог выбора)
            
        Returns:
            True если загрузка успешна, False иначе
        """
        if not filepath:
            filepath = filedialog.askopenfilename(
                title="Открыть экспорт из BESS/Revit",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("All files", "*.*")
                ]
            )
            if not filepath:
                return False
        
        try:
            # Загружаем данные через IO модуль
            meta, levels, rooms, areas, openings, shafts = load_bess_export(filepath)
            
            # Обновляем состояние
            self.state.set_source(meta, levels, rooms, areas, openings, shafts)
            
            # Перестраиваем пространственный индекс
            self._update_spatial_index()
            
            # Очищаем кэш отрисовки
            self.render_cache.clear()
            
            # Сбрасываем выбор
            self.clear_selection()
            
            # Уведомляем о загрузке файла
            self._fire_event('file_loaded', {
                'filepath': filepath,
                'filename': os.path.basename(filepath),
                'rooms_count': len(rooms),
                'areas_count': len(areas), 
                'openings_count': len(openings)
            })
            
            messagebox.showinfo(
                "Успех", 
                f"Загружено:\n{len(rooms)} помещений\n{len(areas)} областей\n{len(openings)} отверстий"
            )
            
            return True
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить файл:\n{str(e)}")
            return False
    
    def save_work_geometry_file(self, filepath: Optional[str] = None) -> bool:
        """
        Сохранение рабочей геометрии
        
        Args:
            filepath: Путь к файлу (если None - показывает диалог сохранения)
            
        Returns:
            True если сохранение успешно, False иначе
        """
        if not filepath:
            filepath = filedialog.asksaveasfilename(
                title="Сохранить рабочую геометрию",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if not filepath:
                return False
        
        try:
            save_work_geometry(
                filepath,
                self.state.meta,
                self.state.work_levels,
                self.state.work_rooms,
                self.state.work_areas,
                self.state.work_openings,
                self.state.work_shafts
            )
            
            messagebox.showinfo("Успех", "Файл сохранен")
            return True
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{str(e)}")
            return False
    
    def export_to_contam(self, filepath: Optional[str] = None) -> bool:
        """
        Экспорт в формат CONTAM
        
        Args:
            filepath: Путь к файлу (если None - показывает диалог сохранения)
            
        Returns:
            True если экспорт успешен, False иначе
        """
        if not filepath:
            filepath = filedialog.asksaveasfilename(
                title="Экспорт в CONTAM",
                defaultextension=".prj",
                filetypes=[("CONTAM Project", "*.prj"), ("All files", "*.*")]
            )
            if not filepath:
                return False
        
        try:
            # Подготавливаем данные для CONTAM
            contam_data = self._prepare_contam_data()
            
            # Записываем файл
            self._write_contam_file(filepath, contam_data)
            
            messagebox.showinfo("Успех", "Экспорт в CONTAM завершен")
            return True
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось экспортировать:\n{str(e)}")
            return False
    
    # === УПРАВЛЕНИЕ УРОВНЯМИ ===
    
    def select_level(self, level_name: str) -> bool:
        """
        Выбор текущего уровня для работы
        
        Args:
            level_name: Имя уровня
            
        Returns:
            True если уровень найден и выбран, False иначе
        """
        if level_name not in self.state.work_levels:
            return False
        
        self.state.selected_level = level_name
        
        # Очищаем выбор при смене уровня
        self.clear_selection()
        
        # Обновляем пространственный индекс для текущего уровня
        self._update_spatial_index()
        
        # Очищаем кэш отрисовки
        self.render_cache.clear()
        
        # Уведомляем о смене уровня
        self._fire_event('level_changed', {'level_name': level_name})
        
        return True
    
    def get_current_level_elements(self) -> Dict[str, List]:
        """
        Получение всех элементов текущего уровня
        
        Returns:
            Словарь с элементами: {'rooms': [], 'areas': [], 'openings': []}
        """
        if not self.state.selected_level:
            return {'rooms': [], 'areas': [], 'openings': []}
        
        level = self.state.selected_level
        
        rooms = [r for r in self.state.work_rooms 
                if r.get("params", {}).get("BESS_level", "") == level]
        
        areas = [a for a in self.state.work_areas 
                if a.get("params", {}).get("BESS_level", "") == level]
        
        openings = [o for o in self.state.work_openings 
                   if o.get("params", {}).get("BESS_level", "") == level]
        
        return {
            'rooms': rooms,
            'areas': areas,
            'openings': openings
        }
    
    # === УПРАВЛЕНИЕ ВЫДЕЛЕНИЕМ ===
    
    def select_elements(self, element_ids: List[str], append: bool = False):
        """
        Выбор элементов
        
        Args:
            element_ids: Список ID элементов для выбора
            append: True для добавления к текущему выбору, False для замены
        """
        if not append:
            self.selected_elements.clear()
        
        self.selected_elements.update(element_ids)
        
        # Уведомляем о изменении выбора
        self._fire_event('selection_changed', {
            'selected_ids': list(self.selected_elements),
            'append': append
        })
    
    def clear_selection(self):
        """Очистка выбора"""
        if self.selected_elements:
            self.selected_elements.clear()
            self._fire_event('selection_changed', {'selected_ids': [], 'append': False})
    
    def is_selected(self, element_id: str) -> bool:
        """
        Проверка, выбран ли элемент
        
        Args:
            element_id: ID элемента
            
        Returns:
            True если элемент выбран, False иначе
        """
        return element_id in self.selected_elements
    
    # === УПРАВЛЕНИЕ РЕЖИМАМИ РАБОТЫ ===
    
    def set_drawing_mode(self, mode: DrawingMode):
        """
        Установка режима рисования
        
        Args:
            mode: Новый режим рисования
        """
        old_mode = self.current_drawing_mode
        self.current_drawing_mode = mode
        
        # Обновляем режим в операциях геометрии
        self.geometry_operations.set_drawing_mode(mode)
        
        # Меняем общий режим приложения
        if mode == DrawingMode.NONE:
            self.current_mode = ApplicationMode.NORMAL
        else:
            self.current_mode = ApplicationMode.DRAWING
        
        # Уведомляем о смене режима
        self._fire_event('mode_changed', {
            'old_mode': old_mode,
            'new_mode': mode,
            'app_mode': self.current_mode
        })
    
    # === ГЕОМЕТРИЧЕСКИЕ ОПЕРАЦИИ ===
    
    def create_room_at_point(self, world_x: float, world_y: float) -> Optional[str]:
        """
        Создание помещения в указанной точке (интерактивное рисование)
        
        Args:
            world_x, world_y: Координаты в мировой системе координат
            
        Returns:
            ID созданного помещения или None если операция не завершена
        """
        if self.current_drawing_mode != DrawingMode.ADD_ROOM:
            return None
        
        # Делегируем операцию компоненту GeometryOperations
        result = self.geometry_operations.add_room_point(
            world_x, world_y, self.state.selected_level
        )
        
        if result.get('room_completed'):
            # Помещение создано - добавляем в состояние
            room_data = result['room_data']
            room_id = self._add_room_to_state(room_data)
            
            # Обновляем пространственный индекс
            self._update_spatial_index()
            
            # Уведомляем об изменении геометрии
            self._fire_event('geometry_updated', {
                'operation': 'create_room',
                'element_id': room_id,
                'element_type': 'room'
            })
            
            return room_id
        
        return None
    
    def finish_room_creation(self) -> Optional[str]:
        """
        Завершение создания помещения
        
        Returns:
            ID созданного помещения или None если невозможно завершить
        """
        result = self.geometry_operations.finish_room_creation()
        
        if result and result.get('success'):
            room_data = result['room_data']
            room_id = self._add_room_to_state(room_data)
            
            # Возвращаемся в обычный режим
            self.set_drawing_mode(DrawingMode.NONE)
            
            return room_id
        
        return None
    
    def delete_selected_elements(self) -> bool:
        """
        Удаление выбранных элементов
        
        Returns:
            True если удаление выполнено успешно, False иначе
        """
        if not self.selected_elements:
            return False
        
        try:
            deleted_count = 0
            
            # Удаляем по типам элементов
            room_ids = []
            area_ids = []
            opening_ids = []
            
            # Определяем типы выбранных элементов
            for element_id in self.selected_elements:
                element_type = self._get_element_type(element_id)
                if element_type == 'room':
                    room_ids.append(element_id)
                elif element_type == 'area':
                    area_ids.append(element_id)
                elif element_type == 'opening':
                    opening_ids.append(element_id)
            
            # Удаляем из состояния
            if room_ids:
                self.state.remove_rooms([str(rid) for rid in room_ids])
                deleted_count += len(room_ids)
            
            if area_ids:
                self.state.remove_areas([str(aid) for aid in area_ids])
                deleted_count += len(area_ids)
            
            if opening_ids:
                self.state.remove_openings([str(oid) for oid in opening_ids])
                deleted_count += len(opening_ids)
            
            # Очищаем выбор
            self.clear_selection()
            
            # Обновляем пространственный индекс
            self._update_spatial_index()
            
            # Уведомляем об изменении геометрии
            self._fire_event('geometry_updated', {
                'operation': 'delete_elements',
                'deleted_count': deleted_count,
                'deleted_ids': list(self.selected_elements)
            })
            
            return True
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось удалить элементы:\n{str(e)}")
            return False
    
    # === ОТМЕНА/ПОВТОР ОПЕРАЦИЙ ===
    
    def undo(self) -> bool:
        """
        Отмена последней операции
        
        Returns:
            True если отмена выполнена, False иначе
        """
        if not self.can_undo():
            return False
        
        operation = self.operation_history[self.current_operation_index]
        success = self.geometry_operations.undo_operation(operation)
        
        if success:
            self.current_operation_index -= 1
            self._update_spatial_index()
            self._fire_event('geometry_updated', {'operation': 'undo'})
        
        return success
    
    def redo(self) -> bool:
        """
        Повтор отмененной операции
        
        Returns:
            True если повтор выполнен, False иначе
        """
        if not self.can_redo():
            return False
        
        self.current_operation_index += 1
        operation = self.operation_history[self.current_operation_index]
        success = self.geometry_operations.redo_operation(operation)
        
        if success:
            self._update_spatial_index()
            self._fire_event('geometry_updated', {'operation': 'redo'})
        
        return success
    
    def can_undo(self) -> bool:
        """Проверка возможности отмены"""
        return self.current_operation_index >= 0
    
    def can_redo(self) -> bool:
        """Проверка возможности повтора"""
        return self.current_operation_index < len(self.operation_history) - 1
    
    # === ОБРАБОТЧИКИ СОБЫТИЙ ===
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """
        Добавление обработчика события
        
        Args:
            event_type: Тип события
            handler: Функция-обработчик
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable):
        """
        Удаление обработчика события
        
        Args:
            event_type: Тип события
            handler: Функция-обработчик
        """
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
            except ValueError:
                pass
    
    def _fire_event(self, event_type: str, data: Dict[str, Any]):
        """
        Вызов всех обработчиков события
        
        Args:
            event_type: Тип события
            data: Данные события
        """
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    handler(data)
                except Exception as e:
                    print(f"Ошибка в обработчике события {event_type}: {e}")
    
    # === ВНУТРЕННИЕ МЕТОДЫ ===
    
    def _update_spatial_index(self):
        """Обновление пространственного индекса"""
        self.spatial_index.clear()
        
        elements = self.get_current_level_elements()
        
        # Добавляем все элементы в индекс
        for room in elements['rooms']:
            room_id = room.get('id')
            if room_id and room.get('outer_xy_m'):
                self.spatial_index.add_element(room_id, 'room', room['outer_xy_m'])
        
        for area in elements['areas']:
            area_id = area.get('id')
            if area_id and area.get('outer_xy_m'):
                self.spatial_index.add_element(area_id, 'area', area['outer_xy_m'])
        
        for opening in elements['openings']:
            opening_id = opening.get('id')
            if opening_id and opening.get('outer_xy_m'):
                self.spatial_index.add_element(opening_id, 'opening', opening['outer_xy_m'])
    
    def _add_room_to_state(self, room_data: Dict) -> str:
        """
        Добавление помещения в состояние
        
        Args:
            room_data: Данные помещения
            
        Returns:
            ID добавленного помещения
        """
        # Генерируем уникальный ID
        room_id = self.state.unique_id(f"Room_{len(self.state.work_rooms) + 1}")
        
        # Создаем структуру помещения
        room = {
            'id': room_id,
            'name': f'Room_{len(self.state.work_rooms) + 1}',
            'outer_xy_m': room_data['outer_xy_m'],
            'inner_loops_xy_m': room_data.get('inner_loops_xy_m', []),
            'params': {
                'BESS_level': self.state.selected_level,
                'BESS_Room_Height': '3.0'  # Значение по умолчанию
            }
        }
        
        # Добавляем в состояние
        self.state.work_rooms.append(room)
        
        return room_id
    
    def _get_element_type(self, element_id: str) -> Optional[str]:
        """
        Определение типа элемента по ID
        
        Args:
            element_id: ID элемента
            
        Returns:
            Тип элемента ('room', 'area', 'opening') или None если не найден
        """
        elements = self.get_current_level_elements()
        
        for room in elements['rooms']:
            if room.get('id') == element_id:
                return 'room'
        
        for area in elements['areas']:
            if area.get('id') == element_id:
                return 'area'
        
        for opening in elements['openings']:
            if opening.get('id') == element_id:
                return 'opening'
        
        return None
    
    def _prepare_contam_data(self) -> Dict:
        """
        Подготовка данных для экспорта в CONTAM
        
        Returns:
            Словарь с данными для CONTAM
        """
        elements = self.get_current_level_elements()
        
        zones = []
        paths = []
        
        # Обрабатываем помещения как зоны
        for room in elements['rooms']:
            zone = {
                'id': room.get('id', ''),
                'name': room.get('name', ''),
                'floor_area': self.spatial_processor.calculate_element_properties(room).area_m2,
                'volume': self.spatial_processor.calculate_element_properties(room).area_m2 * 3.0,  # Примерная высота
                'height': 3.0
            }
            zones.append(zone)
        
        # Обрабатываем отверстия как пути воздушного потока
        for opening in elements['openings']:
            path = {
                'id': opening.get('id', ''),
                'type': opening.get('category', 'Door'),
                'from_zone': opening.get('from_room', ''),
                'to_zone': opening.get('to_room', ''),
                'area': opening.get('real_width_m', 1.0) * opening.get('real_height_m', 2.0)
            }
            paths.append(path)
        
        return {
            'zones': zones,
            'paths': paths,
            'timestamp': datetime.now().isoformat()
        }
    
    def _write_contam_file(self, filepath: str, data: Dict):
        """
        Запись файла CONTAM
        
        Args:
            filepath: Путь к выходному файлу
            data: Данные для записи
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"! CONTAM Project File\n")
            f.write(f"! Generated by BESS_GEOMETRY\n")
            f.write(f"! Zones: {len(data['zones'])}\n")
            f.write(f"! Paths: {len(data['paths'])}\n\n")
            
            # Записываем зоны
            for zone in data['zones']:
                f.write(f"ZONE {zone['id']} {zone['name']}\n")
                f.write(f"  Volume: {zone['volume']:.2f} m3\n")
                f.write(f"  Area: {zone['floor_area']:.2f} m2\n")
                f.write(f"  Height: {zone['height']:.2f} m\n\n")
            
            # Записываем пути
            for path in data['paths']:
                f.write(f"PATH {path['id']}\n")
                f.write(f"  Type: {path['type']}\n")
                f.write(f"  From: {path['from_zone']}\n")
                f.write(f"  To: {path['to_zone']}\n")
                f.write(f"  Area: {path['area']:.2f} m2\n\n")
    
    def _on_operation_completed(self, operation):
        """
        Обработчик завершения операции для системы Undo/Redo
        
        Args:
            operation: Завершенная операция
        """
        # Добавляем операцию в историю
        self.operation_history = self.operation_history[:self.current_operation_index + 1]
        self.operation_history.append(operation)
        self.current_operation_index = len(self.operation_history) - 1
        
        # Ограничиваем размер истории
        if len(self.operation_history) > self.max_history_size:
            self.operation_history.pop(0)
            self.current_operation_index -= 1
    
    def _on_selection_changed(self, selected_ids: List[str]):
        """
        Обработчик изменения выбора от canvas
        
        Args:
            selected_ids: Список выбранных ID
        """
        self.selected_elements = set(selected_ids)
        self._fire_event('selection_changed', {
            'selected_ids': selected_ids,
            'append': False
        })
    
    def _on_canvas_interaction(self, interaction_data: Dict):
        """
        Обработчик взаимодействия с canvas
        
        Args:
            interaction_data: Данные о взаимодействии
        """
        interaction_type = interaction_data.get('type')
        
        if interaction_type == 'click':
            world_x = interaction_data.get('world_x', 0)
            world_y = interaction_data.get('world_y', 0)
            
            if self.current_drawing_mode == DrawingMode.ADD_ROOM:
                self.create_room_at_point(world_x, world_y)
        
        elif interaction_type == 'double_click':
            if self.current_drawing_mode == DrawingMode.ADD_ROOM:
                self.finish_room_creation()
    
    # === ПУБЛИЧНЫЙ ИНТЕРФЕЙС ДЛЯ ИНТЕГРАЦИИ ===
    
    def get_state(self) -> AppState:
        """Получение состояния приложения"""
        return self.state
    
    def get_spatial_processor(self) -> SpatialProcessor:
        """Получение процессора геометрии"""
        return self.spatial_processor
    
    def get_geometry_operations(self) -> GeometryOperations:
        """Получение компонента операций геометрии"""
        return self.geometry_operations
    
    def get_performance_monitor(self) -> PerformanceMonitor:
        """Получение монитора производительности"""
        return self.performance_monitor