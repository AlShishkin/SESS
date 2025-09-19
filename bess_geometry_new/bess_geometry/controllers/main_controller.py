# -*- coding: utf-8 -*-
"""
MainController - центральный контроллер системы BESS_GEOMETRY (ОБНОВЛЕННАЯ ВЕРСИЯ)

Этот контроллер является "дирижером оркестра" - он координирует работу всех компонентов
включая новые интегрированные модули: ArchitecturalTools, ShaftManager, 
BESSParameterManager и ContourEditor.

НОВЫЕ ВОЗМОЖНОСТИ ЭТАПА 3:
- Создание VOID помещений через ArchitecturalTools
- Управление шахтами через ShaftManager
- Расширенная система параметров BESS
- Интерактивное редактирование контуров
"""

import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Dict, List, Set, Optional, Tuple, Callable, Any
from copy import deepcopy
from datetime import datetime
from enum import Enum

from state import AppState
from core.spatial_processor import SpatialProcessor
from core.geometry_operations import GeometryOperations, DrawingMode, OperationType
from io_bess import load_bess_export, save_work_geometry
from performance import PerformanceMonitor, RenderCache, SpatialIndex

# === НОВЫЕ ИМПОРТЫ ДЛЯ ИНТЕГРАЦИИ ===
try:
    from core.architectural_tools import ArchitecturalTools
    ARCHITECTURAL_TOOLS_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: ArchitecturalTools недоступен - {e}")
    ARCHITECTURAL_TOOLS_AVAILABLE = False

try:
    from core.shaft_manager import ShaftManager  
    SHAFT_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: ShaftManager недоступен - {e}")
    SHAFT_MANAGER_AVAILABLE = False

try:
    from core.bess_parameters import BESSParameterManager, ParameterScope
    BESS_PARAMETERS_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: BESSParameterManager недоступен - {e}")
    BESS_PARAMETERS_AVAILABLE = False

try:
    from ui.contour_editor import ContourEditor, EditingMode as ContourEditingMode
    CONTOUR_EDITOR_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: ContourEditor недоступен - {e}")
    CONTOUR_EDITOR_AVAILABLE = False


class ApplicationMode(Enum):
    """Режимы работы приложения"""
    NORMAL = "normal"           # Обычный режим (просмотр, выбор)
    DRAWING = "drawing"         # Режим рисования
    EDITING = "editing"         # Режим редактирования
    ANALYZING = "analyzing"     # Режим анализа геометрии
    CONTOUR_EDITING = "contour_editing"  # НОВЫЙ: Режим редактирования контуров


class MainController:
    """
    Главный контроллер системы BESS_GEOMETRY с интегрированными компонентами
    
    РАСШИРЕННЫЕ ВОЗМОЖНОСТИ:
    - Создание архитектурных элементов (VOID, второй свет)
    - Управление шахтами по уровням
    - Продвинутая система параметров BESS
    - Интерактивное редактирование контуров
    """
    
    def __init__(self, root_window: tk.Tk):
        """
        Инициализация главного контроллера с интегрированными компонентами
        
        Args:
            root_window: Главное окно приложения Tkinter
        """
        self.root = root_window
        
        # === ОСНОВНЫЕ КОМПОНЕНТЫ СИСТЕМЫ ===
        self.state = AppState()
        self.spatial_processor = SpatialProcessor()
        self.geometry_operations = GeometryOperations()
        
        # === НОВЫЕ ИНТЕГРИРОВАННЫЕ МОДУЛИ ===
        if SHAFT_MANAGER_AVAILABLE:
            self.shaft_manager = ShaftManager()
            print("✅ ShaftManager инициализирован")
        else:
            self.shaft_manager = None
        
        if BESS_PARAMETERS_AVAILABLE:
            self.parameter_manager = BESSParameterManager()
            print("✅ BESSParameterManager инициализирован")
        else:
            self.parameter_manager = None
        
        # Контур-редактор (будет связан с canvas позже)
        self.contour_editor = None
        
        # === КОМПОНЕНТЫ ПРОИЗВОДИТЕЛЬНОСТИ ===
        self.performance_monitor = PerformanceMonitor()
        self.render_cache = RenderCache(max_size=2000)
        self.spatial_index = SpatialIndex(grid_size=10.0)
        
        # === РАСШИРЕННЫЕ РЕЖИМЫ ===
        self.current_mode = ApplicationMode.NORMAL
        self.current_drawing_mode = DrawingMode.NONE
        self.contour_editing_mode = ContourEditingMode.NONE if CONTOUR_EDITOR_AVAILABLE else None
        self.selected_elements = set()
        
        # === ОБРАБОТЧИКИ СОБЫТИЙ ===
        self.event_handlers: Dict[str, List[Callable]] = {
            'data_changed': [],
            'selection_changed': [], 
            'mode_changed': [],
            'geometry_updated': [],
            'file_loaded': [],
            'level_changed': [],
            # Новые события для интегрированных компонентов
            'void_created': [],
            'second_light_created': [],
            'shaft_imported': [],
            'contour_editing_started': [],
            'contour_editing_finished': [],
            'parameters_updated': []
        }
        
        # === КОНТРОЛЛЕРЫ ПОДКОМПОНЕНТОВ ===
        self.canvas_controller = None
        
        # === ИСТОРИЯ ОПЕРАЦИЙ ===
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
        
        # === ИНИЦИАЛИЗАЦИЯ ИНТЕГРИРОВАННЫХ КОМПОНЕНТОВ ===
        
        # Настройка ShaftManager
        if self.shaft_manager:
            # Подключаем валидацию шахт к пространственному процессору
            self.shaft_manager.set_validator(self.spatial_processor.validate_geometry)
        
        # Настройка ParameterManager 
        if self.parameter_manager:
            # Инициализируем параметры по умолчанию для проекта
            self.parameter_manager.initialize_project_defaults()
    
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
        
        # === ИНИЦИАЛИЗАЦИЯ CONTOUR EDITOR ===
        if CONTOUR_EDITOR_AVAILABLE and hasattr(canvas_controller, 'canvas'):
            self.contour_editor = ContourEditor(canvas_controller.canvas)
            self.contour_editor.set_completion_callback(self._on_contour_editing_complete)
            print("✅ ContourEditor связан с canvas")
    
    # === НОВЫЕ МЕТОДЫ АРХИТЕКТУРНЫХ ИНСТРУМЕНТОВ ===
    
    def create_void_room(self, level: str, coords: List[Tuple[float, float]], 
                         base_room_id: Optional[str] = None) -> bool:
        """
        Создание VOID помещения через ArchitecturalTools
        
        Args:
            level: Уровень для создания VOID
            coords: Координаты контура VOID
            base_room_id: ID базового помещения (для связи)
            
        Returns:
            True если создание успешно
        """
        if not ARCHITECTURAL_TOOLS_AVAILABLE:
            messagebox.showerror("Ошибка", "ArchitecturalTools недоступен")
            return False
        
        try:
            # Используем ArchitecturalTools для создания VOID
            result = ArchitecturalTools.add_void(
                self.state, level, coords, base_room_id
            )
            
            if result['success']:
                # Применяем параметры BESS если доступны
                if self.parameter_manager:
                    void_element = result['void_data']
                    self.parameter_manager.apply_default_parameters(
                        void_element, ParameterScope.AREA
                    )
                
                # Уведомляем об изменениях
                self._fire_event('void_created', {
                    'void_id': result['void_id'],
                    'level': level,
                    'base_room_id': base_room_id
                })
                self._fire_event('geometry_updated', {
                    'operation': 'create_void',
                    'element_id': result['void_id']
                })
                
                # Обновляем кэши
                self.render_cache.invalidate_level(level)
                self.spatial_index.update_element(result['void_id'], coords)
                
                return True
            else:
                messagebox.showerror("Ошибка создания VOID", result.get('error', 'Неизвестная ошибка'))
                return False
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать VOID: {e}")
            return False
    
    def create_second_light(self, base_room_id: str, level: str, 
                           coords: List[Tuple[float, float]]) -> bool:
        """
        Создание второго света через ArchitecturalTools
        
        Args:
            base_room_id: ID помещения-основы
            level: Уровень для создания второго света
            coords: Координаты контура второго света
            
        Returns:
            True если создание успешно
        """
        if not ARCHITECTURAL_TOOLS_AVAILABLE:
            messagebox.showerror("Ошибка", "ArchitecturalTools недоступен")
            return False
        
        try:
            result = ArchitecturalTools.add_second_light(
                self.state, base_room_id, level, coords
            )
            
            if result['success']:
                # Применяем параметры BESS
                if self.parameter_manager:
                    second_light_element = result['second_light_data']
                    self.parameter_manager.apply_default_parameters(
                        second_light_element, ParameterScope.AREA
                    )
                    # Вычисляем высоты автоматически
                    self.parameter_manager.calculate_all_parameters(
                        second_light_element, self.state.levels
                    )
                
                self._fire_event('second_light_created', {
                    'second_light_id': result['second_light_id'],
                    'base_room_id': base_room_id,
                    'level': level
                })
                self._fire_event('geometry_updated', {
                    'operation': 'create_second_light',
                    'element_id': result['second_light_id']
                })
                
                return True
            else:
                messagebox.showerror("Ошибка создания второго света", result.get('error'))
                return False
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать второй свет: {e}")
            return False
    
    # === МЕТОДЫ УПРАВЛЕНИЯ ШАХТАМИ ===
    
    def import_shafts(self, base_shafts: List[Dict]) -> Dict[str, Any]:
        """
        Импорт шахт через ShaftManager
        
        Args:
            base_shafts: Список данных о базовых шахтах
            
        Returns:
            Результат импорта с подробной информацией
        """
        if not self.shaft_manager:
            return {'success': False, 'error': 'ShaftManager недоступен'}
        
        try:
            # Импортируем шахты
            result = self.shaft_manager.import_base_shafts(base_shafts)
            
            if result['success']:
                # Клонируем по всем уровням
                levels = list(self.state.levels.keys())
                clone_result = self.shaft_manager.clone_to_levels(levels)
                
                # Применяем параметры BESS к шахтам
                if self.parameter_manager:
                    for shaft_id in result['imported_shafts']:
                        shaft_data = self.shaft_manager.get_shaft_data(shaft_id)
                        if shaft_data:
                            self.parameter_manager.apply_default_parameters(
                                shaft_data, ParameterScope.SHAFT
                            )
                
                self._fire_event('shaft_imported', {
                    'imported_count': len(result['imported_shafts']),
                    'levels_count': len(levels)
                })
                self._fire_event('geometry_updated', {
                    'operation': 'import_shafts',
                    'element_ids': result['imported_shafts']
                })
                
                return result
            else:
                messagebox.showerror("Ошибка импорта шахт", result.get('error'))
                return result
                
        except Exception as e:
            error_msg = f"Не удалось импортировать шахты: {e}"
            messagebox.showerror("Ошибка", error_msg)
            return {'success': False, 'error': error_msg}
    
    # === МЕТОДЫ РЕДАКТИРОВАНИЯ КОНТУРОВ ===
    
    def start_contour_editing(self, element_id: str) -> bool:
        """
        Запуск режима редактирования контура элемента
        
        Args:
            element_id: ID элемента для редактирования
            
        Returns:
            True если режим успешно запущен
        """
        if not self.contour_editor:
            messagebox.showerror("Ошибка", "ContourEditor недоступен")
            return False
        
        try:
            # Получаем данные элемента
            element_data = self.state.get_element_by_id(element_id)
            if not element_data:
                messagebox.showerror("Ошибка", f"Элемент {element_id} не найден")
                return False
            
            # Запускаем редактирование
            success = self.contour_editor.start_editing(element_id, element_data)
            
            if success:
                self.current_mode = ApplicationMode.CONTOUR_EDITING
                self._fire_event('contour_editing_started', {'element_id': element_id})
                self._fire_event('mode_changed', {'new_mode': self.current_mode})
                return True
            else:
                messagebox.showerror("Ошибка", "Не удалось запустить редактирование контура")
                return False
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка запуска редактирования: {e}")
            return False
    
    def finish_contour_editing(self, save_changes: bool = True) -> bool:
        """
        Завершение режима редактирования контура
        
        Args:
            save_changes: Сохранить ли изменения
            
        Returns:
            True если завершение успешно
        """
        if not self.contour_editor or self.current_mode != ApplicationMode.CONTOUR_EDITING:
            return False
        
        try:
            element_id = self.contour_editor.current_element_id
            result = self.contour_editor.finish_editing(save_changes)
            
            if result['success'] and save_changes:
                # Обновляем данные элемента
                updated_coords = result['updated_coords']
                self.state.update_element_coordinates(element_id, updated_coords)
                
                # Пересчитываем параметры если доступно
                if self.parameter_manager:
                    element_data = self.state.get_element_by_id(element_id)
                    if element_data:
                        self.parameter_manager.calculate_all_parameters(
                            element_data, self.state.levels
                        )
                
                self._fire_event('geometry_updated', {
                    'operation': 'edit_contour',
                    'element_id': element_id
                })
            
            self.current_mode = ApplicationMode.NORMAL
            self._fire_event('contour_editing_finished', {
                'element_id': element_id,
                'saved': save_changes
            })
            self._fire_event('mode_changed', {'new_mode': self.current_mode})
            
            return True
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка завершения редактирования: {e}")
            return False
    
    # === МЕТОДЫ УПРАВЛЕНИЯ ПАРАМЕТРАМИ ===
    
    def update_element_parameters(self, element_id: str, params: Dict[str, Any]) -> bool:
        """
        Обновление параметров элемента через BESSParameterManager
        
        Args:
            element_id: ID элемента
            params: Новые параметры
            
        Returns:
            True если обновление успешно
        """
        if not self.parameter_manager:
            messagebox.showerror("Ошибка", "BESSParameterManager недоступен")
            return False
        
        try:
            element_data = self.state.get_element_by_id(element_id)
            if not element_data:
                return False
            
            # Обновляем параметры
            success = self.parameter_manager.update_element_parameters(
                element_data, params
            )
            
            if success:
                # Пересчитываем зависимые параметры
                self.parameter_manager.calculate_all_parameters(
                    element_data, self.state.levels
                )
                
                self._fire_event('parameters_updated', {
                    'element_id': element_id,
                    'updated_params': params
                })
                self._fire_event('geometry_updated', {
                    'operation': 'update_parameters',
                    'element_id': element_id
                })
                
                return True
            else:
                return False
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обновить параметры: {e}")
            return False
    
    # === CALLBACK МЕТОДЫ ===
    
    def _on_contour_editing_complete(self, result: Dict[str, Any]):
        """Callback для завершения редактирования контура"""
        self.finish_contour_editing(result.get('save_changes', True))
    
    def _on_operation_completed(self, operation: Dict[str, Any]):
        """Callback для завершения операции (для истории)"""
        # Добавляем операцию в историю
        if len(self.operation_history) >= self.max_history_size:
            self.operation_history.pop(0)
        
        self.operation_history.append({
            'timestamp': datetime.now(),
            'operation': operation,
            'state_snapshot': deepcopy(self.state.get_current_snapshot())
        })
        self.current_operation_index = len(self.operation_history) - 1
    
    def _fire_event(self, event_name: str, data: Any):
        """Генерация события для всех подписчиков"""
        if event_name in self.event_handlers:
            for handler in self.event_handlers[event_name]:
                try:
                    handler(data)
                except Exception as e:
                    print(f"Ошибка в обработчике события {event_name}: {e}")
    
    def _on_selection_changed(self, selected_ids: Set[str]):
        """Обработка изменения выделения"""
        self.selected_elements = selected_ids
        self._fire_event('selection_changed', {'selected_ids': selected_ids})
    
    def _on_canvas_interaction(self, interaction_data: Dict[str, Any]):
        """Обработка взаимодействия с canvas"""
        # Может быть расширена для специфичных взаимодействий
        pass
    
    # === МЕТОДЫ РЕЖИМОВ РАБОТЫ ===
    
    def set_mode(self, new_mode: ApplicationMode):
        """Изменение режима работы приложения"""
        old_mode = self.current_mode
        self.current_mode = new_mode
        
        self._fire_event('mode_changed', {
            'old_mode': old_mode,
            'new_mode': new_mode
        })
    
    def get_integration_status(self) -> Dict[str, Any]:
        """
        Получение статуса интеграции всех компонентов
        
        Returns:
            Словарь с информацией о статусе интеграции
        """
        return {
            'architectural_tools': ARCHITECTURAL_TOOLS_AVAILABLE,
            'shaft_manager': self.shaft_manager is not None,
            'parameter_manager': self.parameter_manager is not None,
            'contour_editor': self.contour_editor is not None,
            'integration_complete': all([
                ARCHITECTURAL_TOOLS_AVAILABLE,
                self.shaft_manager is not None,
                self.parameter_manager is not None,
                CONTOUR_EDITOR_AVAILABLE
            ])
        }

    # === ОСТАЛЬНЫЕ МЕТОДЫ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ ===
    # (load_bess_file, save_geometry, undo_operation, redo_operation и т.д.)
    
    def load_bess_file(self, filepath: Optional[str] = None) -> bool:
        """Загрузка файла экспорта из BESS (без изменений)"""
        # ... существующий код остается без изменений
        pass
    
    def save_geometry(self, filepath: Optional[str] = None) -> bool:
        """Сохранение рабочей геометрии (без изменений)"""
        # ... существующий код остается без изменений
        pass