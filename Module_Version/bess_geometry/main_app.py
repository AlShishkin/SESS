# -*- coding: utf-8 -*-
"""
main_app.py - Основное приложение BESS_Geometry с интегрированным InteractionController

ЭТАП 4.2: ИСПРАВЛЕНИЕ ОШИБКИ ЗАГРУЗКИ ФАЙЛА

Исправления:
✅ Устранена ошибка "'float' object has no attribute 'get'"
✅ Улучшена обработка данных из JSON файла
✅ Добавлены проверки типов данных
✅ Улучшена обработка ошибок загрузки
✅ Fallback для различных форматов входных данных
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sys
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Union
import traceback

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bess_geometry.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Константы приложения
APPLICATION_NAME = "BESS Geometry"
SYSTEM_VERSION = "2.0.2-fixed"

# Умные импорты с fallback
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Импорт InteractionController (КЛЮЧЕВОЙ КОМПОНЕНТ ЭТАПА 4)
try:
    from interaction_controller import InteractionController, InteractionMode
    INTERACTION_CONTROLLER_AVAILABLE = True
    logger.info("✅ InteractionController успешно импортирован")
except ImportError as e:
    INTERACTION_CONTROLLER_AVAILABLE = False
    logger.warning(f"⚠️ InteractionController недоступен: {e}")

# Импорт компонентов геометрии
try:
    from ui.geometry_canvas import CoordinateSystem, GeometryRenderer
    GEOMETRY_COMPONENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Компоненты геометрии недоступны: {e}")
    GEOMETRY_COMPONENTS_AVAILABLE = False

# Импорт дополнительных модулей
try:
    import io_bess
    import state
    from io_bess import load_bess_export
    from state import AppState
    IO_MODULES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ IO модули недоступны: {e}")
    IO_MODULES_AVAILABLE = False


class ComponentAvailabilityChecker:
    """Проверяет доступность компонентов системы"""
    
    def __init__(self):
        self.components = {}
        self._check_all()
    
    def _check_all(self):
        """Проверка всех компонентов"""
        self.components = {
            'interaction_controller': INTERACTION_CONTROLLER_AVAILABLE,
            'geometry_components': GEOMETRY_COMPONENTS_AVAILABLE,
            'io_modules': IO_MODULES_AVAILABLE,
            'tkinter_available': True  # Предполагаем что tkinter есть
        }
    
    def check_all_components(self):
        """Возвращает статус всех компонентов"""
        return {
            'overall_status': {
                'can_render_geometry': self.components['geometry_components'],
                'can_interact': self.components['interaction_controller'],
                'can_load_files': self.components['io_modules']
            },
            'components': self.components.copy()
        }
    
    def get_capability_level(self):
        """Определяет уровень возможностей системы"""
        available = sum(self.components.values())
        total = len(self.components)
        
        if available == total:
            return "Полная функциональность"
        elif available >= total * 0.75:
            return "Расширенная функциональность"
        elif available >= total * 0.5:
            return "Базовая функциональность" 
        else:
            return "Ограниченная функциональность"


def safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """
    Безопасное получение значения из объекта
    Решает проблему "'float' object has no attribute 'get'"
    """
    if isinstance(obj, dict):
        return obj.get(key, default)
    elif isinstance(obj, (list, tuple)) and isinstance(key, int) and 0 <= key < len(obj):
        return obj[key]
    else:
        # Если объект не dict и не поддерживает индексацию, возвращаем default
        logger.warning(f"safe_get: Объект типа {type(obj)} не поддерживает получение ключа '{key}'")
        return default


def normalize_data_structure(data: Any) -> Dict:
    """
    Нормализация структуры данных для универсальной обработки
    Преобразует различные форматы в стандартный словарь
    """
    if isinstance(data, dict):
        return data
    elif isinstance(data, list):
        # Если список, пытаемся создать словарь с индексами
        return {str(i): item for i, item in enumerate(data)}
    elif isinstance(data, (str, int, float, bool)):
        # Скалярные значения оборачиваем в словарь
        return {"value": data}
    else:
        logger.warning(f"Неизвестный тип данных: {type(data)}")
        return {}


def extract_contour_points(item: Any) -> List[List[float]]:
    """
    Извлечение контурных точек из элемента с обработкой различных форматов
    """
    contour = []
    
    # Пробуем различные способы получения контура
    if isinstance(item, dict):
        # Стандартный случай - словарь с ключом contour
        contour_data = item.get('contour', [])
    elif isinstance(item, list) and len(item) > 0:
        # Возможно, весь элемент - это список точек
        contour_data = item
    else:
        contour_data = []
    
    # Нормализуем точки контура
    if isinstance(contour_data, list):
        for point in contour_data:
            try:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    x, y = float(point[0]), float(point[1])
                    contour.append([x, y])
                elif isinstance(point, dict):
                    x = float(safe_get(point, 'x', 0))
                    y = float(safe_get(point, 'y', 0))
                    contour.append([x, y])
                elif isinstance(point, (int, float)):
                    # Возможно, координаты идут подряд: [x1, y1, x2, y2, ...]
                    # Обрабатываем в другом месте
                    pass
            except (ValueError, TypeError) as e:
                logger.warning(f"Ошибка обработки точки контура {point}: {e}")
                continue
    
    return contour


class InteractiveGeometryCanvas:
    """
    ИНТЕРАКТИВНЫЙ GeometryCanvas с улучшенной обработкой ошибок
    """
    
    def __init__(self, canvas, renderer, coord_system):
        self.canvas = canvas
        self.renderer = renderer
        self.coordinate_system = coord_system
        self._last_render_data = None
        self._pan_start = None
        
        # КЛЮЧЕВАЯ ИНТЕГРАЦИЯ: Создаем InteractionController
        if INTERACTION_CONTROLLER_AVAILABLE:
            self.interaction_controller = InteractionController(self.canvas)
            self._setup_interaction_handlers()
            logger.info("✅ InteractionController интегрирован в GeometryCanvas")
        else:
            self.interaction_controller = None
            self._setup_basic_navigation()
            logger.warning("⚠️ Используется базовая навигация без InteractionController")
        
        # Обработчики для связи с основным приложением
        self.on_selection_changed = None
        self.on_element_clicked = None
        self.on_status_update = None
    
    def _setup_interaction_handlers(self):
        """Настройка обработчиков событий от InteractionController"""
        if not self.interaction_controller:
            return
        
        # Подписываемся на события выделения
        self.interaction_controller.add_event_handler(
            'selection_changed', 
            self._handle_selection_changed
        )
        
        # Подписываемся на клики по элементам
        self.interaction_controller.add_event_handler(
            'element_clicked',
            self._handle_element_clicked
        )
        
        # Подписываемся на hover события
        self.interaction_controller.add_event_handler(
            'element_hover',
            self._handle_element_hover
        )
        
        # События режимов взаимодействия
        self.interaction_controller.add_event_handler(
            'interaction_mode_changed',
            self._handle_mode_changed
        )
        
        logger.info("🔗 Обработчики событий InteractionController настроены")
    
    def _handle_selection_changed(self, data):
        """Обработка изменения выделения"""
        selected_count = data['selection_count']
        selected_ids = data['selected_ids']
        
        logger.info(f"🎯 Выделение изменено: {selected_count} элементов")
        logger.debug(f"   ID элементов: {list(selected_ids)}")
        
        # Уведомляем основное приложение
        if self.on_selection_changed:
            self.on_selection_changed(list(selected_ids))
        
        # Обновляем статус
        if self.on_status_update:
            if selected_count == 0:
                self.on_status_update("Ничего не выделено")
            elif selected_count == 1:
                element_id = list(selected_ids)[0]
                self.on_status_update(f"Выделен: {element_id}")
            else:
                self.on_status_update(f"Выделено {selected_count} элементов")
    
    def _handle_element_clicked(self, data):
        """Обработка клика по элементу"""
        element_id = data['element_id']
        element_type = data['element_type']
        properties = data.get('properties', {})
        
        logger.info(f"🖱️ Клик по элементу: {element_id} ({element_type})")
        
        # Уведомляем основное приложение
        if self.on_element_clicked:
            self.on_element_clicked(element_id, element_type, properties)
        
        # Обновляем статус с информацией об элементе
        if self.on_status_update:
            element_name = safe_get(properties, 'name', element_id)
            if element_type == 'room':
                area = safe_get(properties, 'area', 0)
                self.on_status_update(f"Помещение: {element_name} ({area:.1f} м²)")
            elif element_type == 'area':
                area_type = safe_get(properties, 'type', 'Неизвестно')
                self.on_status_update(f"Зона: {element_name} (тип: {area_type})")
            elif element_type == 'opening':
                width = safe_get(properties, 'width', 0)
                self.on_status_update(f"Проем: {element_name} (ширина: {width:.1f} м)")
            else:
                self.on_status_update(f"Элемент: {element_name} ({element_type})")
    
    def _handle_element_hover(self, data):
        """Обработка hover по элементу"""
        element_id = data.get('element_id')
        
        if element_id:
            logger.debug(f"👆 Hover: {element_id}")
        
    def _handle_mode_changed(self, data):
        """Обработка изменения режима взаимодействия"""
        old_mode = data['old_mode']
        new_mode = data['new_mode']
        
        logger.info(f"🎮 Режим изменен: {old_mode.value} → {new_mode.value}")
        
        if self.on_status_update:
            if new_mode == InteractionMode.SELECTION:
                self.on_status_update("Режим: Выбор элементов")
            elif new_mode == InteractionMode.NAVIGATION:
                self.on_status_update("Режим: Навигация (панорамирование/масштабирование)")
            elif new_mode == InteractionMode.DRAWING:
                self.on_status_update("Режим: Рисование")
            else:
                self.on_status_update(f"Режим: {new_mode.value}")
    
    def _setup_basic_navigation(self):
        """Базовая навигация без InteractionController (fallback)"""
        # Масштабирование колесом мыши
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)
        
        # Панорамирование средней кнопкой
        self.canvas.bind("<Button-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_move)
        self.canvas.bind("<ButtonRelease-2>", self._on_pan_end)
        
        logger.info("🖱️ Базовая навигация настроена")
    
    def _on_mousewheel(self, event):
        """Обработка масштабирования колесом мыши"""
        try:
            if event.delta > 0 or event.num == 4:
                factor = 1.1
            else:
                factor = 1.0 / 1.1
            
            self.coordinate_system.zoom_at_point(event.x, event.y, factor)
            
            if self._last_render_data:
                self.render_data(self._last_render_data)
                
        except Exception as e:
            logger.error(f"Ошибка масштабирования: {e}")
    
    def _on_pan_start(self, event):
        """Начало панорамирования"""
        self._pan_start = (event.x, event.y)
        self.canvas.config(cursor="fleur")
    
    def _on_pan_move(self, event):
        """Панорамирование"""
        try:
            if self._pan_start:
                dx = event.x - self._pan_start[0]
                dy = event.y - self._pan_start[1]
                
                self.coordinate_system.offset_x += dx
                self.coordinate_system.offset_y += dy
                
                if self._last_render_data:
                    self.render_data(self._last_render_data)
                
                self._pan_start = (event.x, event.y)
        except Exception as e:
            logger.error(f"Ошибка панорамирования: {e}")
    
    def _on_pan_end(self, event):
        """Завершение панорамирования"""
        self._pan_start = None
        self.canvas.config(cursor="")
    
    def render_data(self, data):
        """
        Отрисовка данных с улучшенной обработкой ошибок
        """
        try:
            self._last_render_data = data
            
            # Очищаем canvas
            self.canvas.delete("all")
            
            # Очищаем старые элементы в InteractionController
            if self.interaction_controller:
                self.interaction_controller.clear_all_elements()
            
            # ИСПРАВЛЕНИЕ: Безопасно извлекаем данные с проверкой типов
            data_normalized = normalize_data_structure(data)
            
            levels = safe_get(data_normalized, 'levels', {})
            rooms = safe_get(data_normalized, 'rooms', [])
            areas = safe_get(data_normalized, 'areas', [])
            openings = safe_get(data_normalized, 'openings', [])
            
            # Убеждаемся что списки действительно списки
            if not isinstance(rooms, list):
                rooms = []
            if not isinstance(areas, list):
                areas = []
            if not isinstance(openings, list):
                openings = []
            
            elements_count = 0
            
            # Отрисовываем помещения
            for i, room_data in enumerate(rooms):
                try:
                    canvas_ids = self._draw_room(room_data, i)
                    
                    if canvas_ids:
                        # ИСПРАВЛЕНИЕ: Безопасное получение свойств
                        room_normalized = normalize_data_structure(room_data)
                        
                        room_id = safe_get(room_normalized, 'id', f'room_{i}')
                        properties = {
                            'name': safe_get(room_normalized, 'name', f'Помещение {i+1}'),
                            'area': float(safe_get(room_normalized, 'area', 0)),
                            'level': str(safe_get(room_normalized, 'level', 'Неизвестно')),
                            'type': safe_get(room_normalized, 'type', 'room')
                        }
                        
                        # РЕГИСТРИРУЕМ в InteractionController
                        if self.interaction_controller:
                            self.interaction_controller.register_element(
                                canvas_ids, str(room_id), 'room', properties
                            )
                        
                        elements_count += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка обработки помещения {i}: {e}")
                    continue
            
            # Отрисовываем зоны
            for i, area_data in enumerate(areas):
                try:
                    canvas_ids = self._draw_area(area_data, i)
                    
                    if canvas_ids:
                        area_normalized = normalize_data_structure(area_data)
                        
                        area_id = safe_get(area_normalized, 'id', f'area_{i}')
                        properties = {
                            'name': safe_get(area_normalized, 'name', f'Зона {i+1}'),
                            'area': float(safe_get(area_normalized, 'area', 0)),
                            'type': safe_get(area_normalized, 'type', 'Неизвестно')
                        }
                        
                        if self.interaction_controller:
                            self.interaction_controller.register_element(
                                canvas_ids, str(area_id), 'area', properties
                            )
                        
                        elements_count += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка обработки зоны {i}: {e}")
                    continue
            
            # Отрисовываем проемы
            for i, opening_data in enumerate(openings):
                try:
                    canvas_ids = self._draw_opening(opening_data, i)
                    
                    if canvas_ids:
                        opening_normalized = normalize_data_structure(opening_data)
                        
                        opening_id = safe_get(opening_normalized, 'id', f'opening_{i}')
                        properties = {
                            'name': safe_get(opening_normalized, 'name', f'Проем {i+1}'),
                            'category': safe_get(opening_normalized, 'category', 'Неизвестно'),
                            'width': float(safe_get(opening_normalized, 'width', 0.9)),
                            'level': str(safe_get(opening_normalized, 'level', 'Неизвестно'))
                        }
                        
                        if self.interaction_controller:
                            self.interaction_controller.register_element(
                                canvas_ids, str(opening_id), 'opening', properties
                            )
                        
                        elements_count += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка обработки проема {i}: {e}")
                    continue
            
            logger.info(f"✅ Отрисовка завершена: {len(rooms)} помещений, {len(areas)} зон, {len(openings)} проемов")
            logger.info(f"📊 Всего элементов зарегистрировано: {elements_count}")
            
            # Обновляем статус
            if self.on_status_update:
                self.on_status_update(f"Загружено: {elements_count} элементов")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка отрисовки данных: {e}")
            logger.error(traceback.format_exc())
            if self.on_status_update:
                self.on_status_update(f"Критическая ошибка отрисовки: {e}")
    
    def _draw_room(self, room_data: Any, index: int) -> List[int]:
        """Отрисовка помещения с улучшенной обработкой ошибок"""
        canvas_ids = []
        
        try:
            room_normalized = normalize_data_structure(room_data)
            
            # Извлекаем контур
            contour = extract_contour_points(room_data)
            
            if len(contour) < 3:
                logger.warning(f"Помещение {index}: недостаточно точек контура ({len(contour)})")
                return canvas_ids
            
            # Конвертируем в экранные координаты
            screen_points = []
            for point in contour:
                try:
                    sx, sy = self.coordinate_system.world_to_screen(float(point[0]), float(point[1]))
                    screen_points.extend([sx, sy])
                except (ValueError, TypeError, IndexError) as e:
                    logger.warning(f"Ошибка конвертации точки {point}: {e}")
                    continue
            
            if len(screen_points) < 6:  # Минимум 3 точки * 2 координаты
                logger.warning(f"Помещение {index}: недостаточно корректных точек для отрисовки")
                return canvas_ids
            
            # Полигон помещения
            fill_color = '#e6f3ff'  # Светло-голубой
            outline_color = '#0066cc'  # Синий
            
            poly_id = self.canvas.create_polygon(
                screen_points,
                fill=fill_color,
                outline=outline_color,
                width=2,
                tags=['room', 'selectable']
            )
            canvas_ids.append(poly_id)
            
            # Текст с названием и площадью
            try:
                # Вычисляем центр помещения
                center_x = sum(p[0] for p in contour) / len(contour)
                center_y = sum(p[1] for p in contour) / len(contour)
                
                text_x, text_y = self.coordinate_system.world_to_screen(center_x, center_y)
                
                room_name = safe_get(room_normalized, 'name', f'Помещение {index+1}')
                room_area = float(safe_get(room_normalized, 'area', 0))
                text = f"{room_name}\n{room_area:.1f} м²"
                
                text_id = self.canvas.create_text(
                    text_x, text_y,
                    text=text,
                    font=('Arial', 9),
                    fill='black',
                    tags=['room_text']
                )
                canvas_ids.append(text_id)
                
            except Exception as e:
                logger.warning(f"Ошибка создания текста для помещения {index}: {e}")
            
        except Exception as e:
            logger.error(f"Критическая ошибка отрисовки помещения {index}: {e}")
        
        return canvas_ids
    
    def _draw_area(self, area_data: Any, index: int) -> List[int]:
        """Отрисовка зоны с улучшенной обработкой ошибок"""
        canvas_ids = []
        
        try:
            area_normalized = normalize_data_structure(area_data)
            contour = extract_contour_points(area_data)
            
            if len(contour) < 3:
                logger.warning(f"Зона {index}: недостаточно точек контура ({len(contour)})")
                return canvas_ids
            
            # Конвертируем в экранные координаты
            screen_points = []
            for point in contour:
                try:
                    sx, sy = self.coordinate_system.world_to_screen(float(point[0]), float(point[1]))
                    screen_points.extend([sx, sy])
                except (ValueError, TypeError, IndexError):
                    continue
            
            if len(screen_points) < 6:
                return canvas_ids
            
            # Полигон зоны
            fill_color = '#ffe6e6'  # Светло-розовый
            outline_color = '#cc0000'  # Красный
            
            poly_id = self.canvas.create_polygon(
                screen_points,
                fill=fill_color,
                outline=outline_color,
                width=2,
                stipple='gray25',  # Штриховка для зон
                tags=['area', 'selectable']
            )
            canvas_ids.append(poly_id)
            
            # Текст с названием
            try:
                center_x = sum(p[0] for p in contour) / len(contour)
                center_y = sum(p[1] for p in contour) / len(contour)
                
                text_x, text_y = self.coordinate_system.world_to_screen(center_x, center_y)
                
                area_name = safe_get(area_normalized, 'name', f'Зона {index+1}')
                area_type = safe_get(area_normalized, 'type', '')
                text = f"{area_name}" + (f"\n({area_type})" if area_type else "")
                
                text_id = self.canvas.create_text(
                    text_x, text_y,
                    text=text,
                    font=('Arial', 8),
                    fill='darkred',
                    tags=['area_text']
                )
                canvas_ids.append(text_id)
                
            except Exception as e:
                logger.warning(f"Ошибка создания текста для зоны {index}: {e}")
            
        except Exception as e:
            logger.error(f"Критическая ошибка отрисовки зоны {index}: {e}")
        
        return canvas_ids
    
    def _draw_opening(self, opening_data: Any, index: int) -> List[int]:
        """Отрисовка проема с улучшенной обработкой ошибок"""
        canvas_ids = []
        
        try:
            opening_normalized = normalize_data_structure(opening_data)
            
            # Пробуем извлечь контур
            contour = extract_contour_points(opening_data)
            
            if contour and len(contour) >= 3:
                # Рисуем по контуру
                screen_points = []
                for point in contour:
                    try:
                        sx, sy = self.coordinate_system.world_to_screen(float(point[0]), float(point[1]))
                        screen_points.extend([sx, sy])
                    except (ValueError, TypeError, IndexError):
                        continue
                
                if len(screen_points) >= 6:
                    poly_id = self.canvas.create_polygon(
                        screen_points,
                        fill='yellow',
                        outline='orange',
                        width=2,
                        tags=['opening', 'selectable']
                    )
                    canvas_ids.append(poly_id)
            else:
                # Простой прямоугольник для проема
                position = safe_get(opening_normalized, 'position', [0, 0])
                if not isinstance(position, (list, tuple)) or len(position) < 2:
                    position = [0, 0]
                
                width = float(safe_get(opening_normalized, 'width', 0.9))
                height = float(safe_get(opening_normalized, 'height', 0.2))
                
                x, y = float(position[0]), float(position[1])
                
                x1, y1 = self.coordinate_system.world_to_screen(x - width/2, y - height/2)
                x2, y2 = self.coordinate_system.world_to_screen(x + width/2, y + height/2)
                
                rect_id = self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill='yellow',
                    outline='orange',
                    width=2,
                    tags=['opening', 'selectable']
                )
                canvas_ids.append(rect_id)
            
        except Exception as e:
            logger.error(f"Критическая ошибка отрисовки проема {index}: {e}")
        
        return canvas_ids
    
    def get_interaction_mode(self):
        """Получение текущего режима взаимодействия"""
        if self.interaction_controller:
            return self.interaction_controller.get_interaction_mode()
        return None
    
    def set_interaction_mode(self, mode):
        """Установка режима взаимодействия"""
        if self.interaction_controller:
            self.interaction_controller.set_interaction_mode(mode)
            return True
        return False
    
    def get_selected_elements(self):
        """Получение выбранных элементов"""
        if self.interaction_controller:
            return list(self.interaction_controller.selection_state.selected_ids)
        return []
    
    def clear_selection(self):
        """Очистка выделения"""
        if self.interaction_controller:
            self.interaction_controller.clear_selection()
    
    def select_elements(self, element_ids, append=False):
        """Программное выделение элементов"""
        if self.interaction_controller:
            self.interaction_controller.select_elements(element_ids, append)


class ModernBessApp:
    """
    Главный класс приложения BESS_Geometry с исправленной обработкой данных
    
    ЭТАП 4.2 - ИСПРАВЛЕНИЕ ОШИБОК ЗАГРУЗКИ:
    ✅ Устранена ошибка "'float' object has no attribute 'get'"
    ✅ Улучшена обработка различных форматов данных
    ✅ Добавлена нормализация структур данных
    ✅ Улучшено логирование ошибок
    """
    
    def __init__(self):
        logger.info(f"🚀 Инициализация {APPLICATION_NAME} v{SYSTEM_VERSION}")
        
        # Проверяем состояние системы
        self.component_checker = ComponentAvailabilityChecker()
        self.system_status = self.component_checker.check_all_components()
        
        # Состояние приложения
        self.current_file_path = None
        self.app_state = None
        self.geometry_canvas = None
        self.selected_elements_info = {}
        
        # Создаем главное окно
        self.root = self._create_main_window()
        
        # Создаем UI
        self._create_user_interface()
        
        logger.info("✅ ModernBessApp инициализирован")
    
    def _create_main_window(self):
        """Создание главного окна приложения"""
        root = tk.Tk()
        root.title(f"{APPLICATION_NAME} v{SYSTEM_VERSION}")
        root.geometry("1400x900")
        root.minsize(1000, 600)
        
        # Иконка и дополнительные настройки
        try:
            # Можно добавить иконку если есть файл
            # root.iconbitmap("icon.ico")
            pass
        except:
            pass
        
        return root
    
    def _create_user_interface(self):
        """Создание пользовательского интерфейса"""
        # Меню
        self._create_menu()
        
        # Панель инструментов
        self._create_toolbar()
        
        # Основная область
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Левая панель с информацией
        left_panel = self._create_info_panels(main_paned)
        main_paned.add(left_panel, weight=1)
        
        # Правая панель с canvas
        right_panel = self._create_canvas_area(main_paned)
        main_paned.add(right_panel, weight=3)
        
        # Статусная строка
        self._create_status_bar()
        
        logger.info("✅ Пользовательский интерфейс создан")
    
    def _create_menu(self):
        """Создание главного меню"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Открыть...", command=self._open_file, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self._on_closing, accelerator="Alt+F4")
        
        # Правка
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Правка", menu=edit_menu)
        edit_menu.add_command(label="Очистить выделение", command=self._clear_selection, accelerator="Esc")
        edit_menu.add_command(label="Выделить всё", command=self._select_all, accelerator="Ctrl+A")
        
        # Вид
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Вид", menu=view_menu)
        view_menu.add_command(label="Подогнать по размеру", command=self._fit_to_view, accelerator="F")
        view_menu.add_separator()
        
        if INTERACTION_CONTROLLER_AVAILABLE:
            view_menu.add_command(label="Режим выбора", command=lambda: self._set_interaction_mode(InteractionMode.SELECTION))
            view_menu.add_command(label="Режим навигации", command=lambda: self._set_interaction_mode(InteractionMode.NAVIGATION))
        
        # Справка
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self._show_about)
        
        # Горячие клавиши
        self.root.bind('<Control-o>', lambda e: self._open_file())
        self.root.bind('<Control-a>', lambda e: self._select_all())
        self.root.bind('<Escape>', lambda e: self._clear_selection())
        self.root.bind('<f>', lambda e: self._fit_to_view())
        self.root.bind('<F>', lambda e: self._fit_to_view())
    
    def _create_toolbar(self):
        """Создание панели инструментов"""
        toolbar_frame = tk.Frame(self.root, bg='lightgray', height=40)
        toolbar_frame.pack(fill=tk.X)
        toolbar_frame.pack_propagate(False)
        
        # Основные кнопки
        tk.Button(toolbar_frame, text="📁 Открыть", command=self._open_file, width=10).pack(side=tk.LEFT, padx=2, pady=5)
        
        # Разделитель
        ttk.Separator(toolbar_frame, orient='vertical').pack(side=tk.LEFT, fill='y', padx=5, pady=5)
        
        # Кнопки взаимодействия (если доступен InteractionController)
        if INTERACTION_CONTROLLER_AVAILABLE:
            tk.Label(toolbar_frame, text="Режим:", bg='lightgray').pack(side=tk.LEFT, padx=5)
            
            self.mode_var = tk.StringVar(value="selection")
            
            mode_frame = tk.Frame(toolbar_frame, bg='lightgray')
            mode_frame.pack(side=tk.LEFT)
            
            tk.Radiobutton(mode_frame, text="🖱️ Выбор", variable=self.mode_var, value="selection",
                         command=lambda: self._set_interaction_mode(InteractionMode.SELECTION),
                         bg='lightgray', indicatoron=False, width=8).pack(side=tk.LEFT, padx=1)
            
            tk.Radiobutton(mode_frame, text="🧭 Навигация", variable=self.mode_var, value="navigation", 
                         command=lambda: self._set_interaction_mode(InteractionMode.NAVIGATION),
                         bg='lightgray', indicatoron=False, width=8).pack(side=tk.LEFT, padx=1)
        
        # Разделитель
        ttk.Separator(toolbar_frame, orient='vertical').pack(side=tk.LEFT, fill='y', padx=5, pady=5)
        
        # Кнопки просмотра
        tk.Button(toolbar_frame, text="🔍 Подогнать", command=self._fit_to_view, width=10).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar_frame, text="🗃️ Очистить", command=self._clear_selection, width=10).pack(side=tk.LEFT, padx=2)
    
    def _create_canvas_area(self, parent):
        """Создание области canvas с интегрированным InteractionController"""
        canvas_frame = tk.Frame(parent, bg='white')
        
        # Заголовок с индикатором интерактивности
        header_frame = tk.Frame(canvas_frame, bg='#e8e8e8', height=35)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        title = "План здания"
        if INTERACTION_CONTROLLER_AVAILABLE:
            title += " (интерактивный)"
        
        tk.Label(header_frame, text=title, font=('Arial', 12, 'bold'), bg='#e8e8e8').pack(side=tk.LEFT, padx=10, pady=5)
        
        # Индикатор функциональности
        capability_level = self.component_checker.get_capability_level()
        color = {
            "Полная функциональность": "#00aa00",
            "Расширенная функциональность": "#aa6600", 
            "Базовая функциональность": "#aa6600",
            "Ограниченная функциональность": "#aa0000"
        }.get(capability_level, "#666666")
        
        tk.Label(header_frame, text=f"● {capability_level}", fg=color, bg='#e8e8e8', 
                font=('Arial', 9)).pack(side=tk.RIGHT, padx=10, pady=5)
        
        # Область canvas с прокруткой
        canvas_container = tk.Frame(canvas_frame, relief=tk.SUNKEN, borderwidth=2)
        canvas_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        canvas = tk.Canvas(canvas_container, bg="white", highlightthickness=0)
        
        # Scrollbars
        h_scroll = tk.Scrollbar(canvas_container, orient=tk.HORIZONTAL, command=canvas.xview)
        v_scroll = tk.Scrollbar(canvas_container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        
        # Размещение
        canvas.grid(row=0, column=0, sticky="nsew")
        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)
        
        # КЛЮЧЕВОЕ: Создаем InteractiveGeometryCanvas
        try:
            if GEOMETRY_COMPONENTS_AVAILABLE:
                coord_system = CoordinateSystem(initial_scale=50.0)
                renderer = GeometryRenderer(canvas, coord_system)
                
                # Используем новый InteractiveGeometryCanvas с полной интерактивностью
                self.geometry_canvas = InteractiveGeometryCanvas(canvas, renderer, coord_system)
                
                # Подключаем обработчики событий
                self.geometry_canvas.on_selection_changed = self._on_selection_changed
                self.geometry_canvas.on_element_clicked = self._on_element_clicked
                self.geometry_canvas.on_status_update = self._update_status
                
                logger.info("✅ InteractiveGeometryCanvas создан и подключен")
                
                # Устанавливаем начальный режим
                if INTERACTION_CONTROLLER_AVAILABLE:
                    self.geometry_canvas.set_interaction_mode(InteractionMode.SELECTION)
            else:
                logger.error("❌ Компоненты геометрии недоступны")
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания интерактивного canvas: {e}")
        
        return canvas_frame
    
    def _create_info_panels(self, parent):
        """Создание информационных панелей"""
        info_frame = tk.Frame(parent, bg='white')
        
        # Notebook для вкладок
        notebook = ttk.Notebook(info_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Вкладка "Уровни"
        levels_frame = tk.Frame(notebook)
        notebook.add(levels_frame, text="Уровни")
        
        self.levels_text = scrolledtext.ScrolledText(levels_frame, wrap=tk.WORD, height=8)
        self.levels_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Вкладка "Помещения"
        rooms_frame = tk.Frame(notebook)
        notebook.add(rooms_frame, text="Помещения")
        
        self.rooms_text = scrolledtext.ScrolledText(rooms_frame, wrap=tk.WORD, height=8)
        self.rooms_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Вкладка "Выделение" (новая)
        selection_frame = tk.Frame(notebook)
        notebook.add(selection_frame, text="Выделение")
        
        self.selection_text = scrolledtext.ScrolledText(selection_frame, wrap=tk.WORD, height=8)
        self.selection_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.selection_text.insert('1.0', "Выберите элементы на плане для просмотра информации")
        
        # Вкладка "Проемы"
        openings_frame = tk.Frame(notebook)
        notebook.add(openings_frame, text="Проемы")
        
        self.openings_text = scrolledtext.ScrolledText(openings_frame, wrap=tk.WORD, height=8)
        self.openings_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        return info_frame
    
    def _create_status_bar(self):
        """Создание статусной строки"""
        self.status_bar = tk.Label(
            self.root, 
            text="Готов к работе", 
            relief=tk.SUNKEN, 
            anchor=tk.W,
            font=('Arial', 9)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _update_status(self, message):
        """Обновление статусной строки"""
        if hasattr(self, 'status_bar'):
            self.status_bar.config(text=str(message))
            self.root.update_idletasks()
    
    # ===============================================
    # ОБРАБОТЧИКИ СОБЫТИЙ ОТ InteractionController
    # ===============================================
    
    def _on_selection_changed(self, selected_ids):
        """Обработка изменения выделения от InteractionController"""
        logger.info(f"🎯 Приложение получило изменение выделения: {selected_ids}")
        
        try:
            # Очищаем вкладку выделения
            self.selection_text.delete('1.0', tk.END)
            
            if not selected_ids:
                self.selection_text.insert('1.0', "Ничего не выделено\n\nВыберите элементы на плане кликом мыши.")
                return
            
            # Показываем информацию о выделенных элементах
            self.selection_text.insert('1.0', f"Выделено элементов: {len(selected_ids)}\n\n")
            
            # Получаем детальную информацию о каждом элементе
            if self.geometry_canvas and self.geometry_canvas.interaction_controller:
                for i, element_id in enumerate(selected_ids, 1):
                    # Ищем элемент в зарегистрированных
                    element_info = None
                    for canvas_id, hit_info in self.geometry_canvas.interaction_controller.element_mappings.items():
                        if hit_info.element_id == element_id:
                            element_info = hit_info
                            break
                    
                    if element_info:
                        self.selection_text.insert(tk.END, f"{i}. {element_info.element_type.upper()}: {element_id}\n")
                        
                        # Добавляем свойства
                        if element_info.properties:
                            for key, value in element_info.properties.items():
                                if key == 'name':
                                    self.selection_text.insert(tk.END, f"   Название: {value}\n")
                                elif key == 'area' and value > 0:
                                    self.selection_text.insert(tk.END, f"   Площадь: {value:.2f} м²\n")
                                elif key == 'level':
                                    self.selection_text.insert(tk.END, f"   Уровень: {value}\n")
                                elif key == 'type' and value != element_info.element_type:
                                    self.selection_text.insert(tk.END, f"   Тип: {value}\n")
                                elif key == 'width' and value > 0:
                                    self.selection_text.insert(tk.END, f"   Ширина: {value:.2f} м\n")
                        
                        self.selection_text.insert(tk.END, "\n")
                    else:
                        self.selection_text.insert(tk.END, f"{i}. {element_id} (информация недоступна)\n\n")
            
        except Exception as e:
            logger.error(f"Ошибка обновления информации о выделении: {e}")
            self.selection_text.delete('1.0', tk.END)
            self.selection_text.insert('1.0', f"Ошибка загрузки информации: {e}")
    
    def _on_element_clicked(self, element_id, element_type, properties):
        """Обработка клика по элементу от InteractionController"""
        logger.info(f"🖱️ Приложение получило клик по элементу: {element_id} ({element_type})")
    
    def _set_interaction_mode(self, mode):
        """Установка режима взаимодействия"""
        if self.geometry_canvas and hasattr(self.geometry_canvas, 'set_interaction_mode'):
            success = self.geometry_canvas.set_interaction_mode(mode)
            if success:
                logger.info(f"🎮 Режим взаимодействия изменен на: {mode.value}")
                # Обновляем радиокнопки
                if hasattr(self, 'mode_var'):
                    self.mode_var.set(mode.value)
            else:
                logger.warning("⚠️ Не удалось изменить режим взаимодействия")
        else:
            logger.warning("⚠️ GeometryCanvas не поддерживает смену режимов")
    
    def _clear_selection(self):
        """Очистка выделения"""
        if self.geometry_canvas and hasattr(self.geometry_canvas, 'clear_selection'):
            self.geometry_canvas.clear_selection()
            logger.info("🗃️ Выделение очищено")
    
    def _select_all(self):
        """Выделение всех элементов"""
        if self.geometry_canvas and self.geometry_canvas.interaction_controller:
            # Получаем все зарегистрированные элементы
            all_element_ids = list(self.geometry_canvas.interaction_controller.element_canvas_map.keys())
            if all_element_ids:
                self.geometry_canvas.select_elements(all_element_ids)
                logger.info(f"✅ Выделены все элементы: {len(all_element_ids)}")
            else:
                logger.info("⚠️ Нет элементов для выделения")
    
    # ===============================================
    # РАБОТА С ФАЙЛАМИ - ИСПРАВЛЕННАЯ ВЕРСИЯ
    # ===============================================
    
    def _open_file(self):
        """Открытие файла BESS с улучшенной обработкой ошибок"""
        filetypes = [
            ("BESS JSON files", "*.json"),
            ("All files", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(
            title="Выберите файл BESS для открытия",
            filetypes=filetypes
        )
        
        if not filepath:
            return
        
        try:
            system_status = self.component_checker.check_all_components()
            
            if IO_MODULES_AVAILABLE:
                # Загружаем через специализированные модули
                logger.info(f"📥 Загружаем через IO модули: {filepath}")
                self._update_status("Загрузка файла через IO модули...")
                
                try:
                    meta, levels, rooms, areas, openings, shafts = load_bess_export(filepath)
                    
                    # Создаем состояние приложения
                    app_state = AppState()
                    app_state.set_source(meta, levels, rooms, areas, openings, shafts)
                    
                    # Сохраняем состояние
                    self.app_state = app_state
                    self.current_file_path = filepath
                    
                    # Выбираем первый уровень
                    if levels:
                        first_level = next(iter(levels.keys()))
                        app_state.selected_level = first_level
                        logger.info(f"🏢 Выбран уровень: {first_level}")
                    
                    # Обновляем UI
                    self._update_levels_list(levels)
                    
                    # Отрисовываем геометрию
                    if system_status['overall_status']['can_render_geometry'] and self.geometry_canvas:
                        logger.info("🎨 Отрисовка данных на canvas...")
                        self._update_status("Отрисовка геометрии...")
                        
                        # Формируем данные для отрисовки
                        render_data = {
                            'levels': levels,
                            'rooms': rooms,
                            'areas': areas,
                            'openings': openings
                        }
                        
                        self.geometry_canvas.render_data(render_data)
                        
                        # Обновляем информационные панели
                        self._update_rooms_list(rooms)
                        self._update_openings_list(openings)
                        
                        self._update_status(f"Загружен файл: {Path(filepath).name}")
                        logger.info("✅ Файл успешно загружен и отображен через IO модули")
                    else:
                        self._update_status("Файл загружен, но геометрия не может быть отображена")
                        logger.warning("⚠️ Файл загружен, но компоненты отрисовки недоступны")
                
                except Exception as e:
                    logger.error(f"Ошибка загрузки через IO модули: {e}")
                    # Fallback на простую загрузку JSON
                    self._load_json_fallback(filepath)
            
            else:
                # Fallback: простая загрузка JSON
                self._load_json_fallback(filepath)
        
        except Exception as e:
            error_msg = f"Критическая ошибка загрузки файла: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            messagebox.showerror("Ошибка", error_msg)
            self._update_status("Критическая ошибка загрузки файла")
    
    def _load_json_fallback(self, filepath: str):
        """Fallback загрузка JSON с улучшенной обработкой ошибок"""
        try:
            logger.info(f"📥 Fallback загрузка JSON: {filepath}")
            self._update_status("Загрузка JSON файла...")
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # ИСПРАВЛЕНИЕ: Нормализуем структуру данных
            data_normalized = normalize_data_structure(data)
            
            self.current_file_path = filepath
            self._update_status(f"Загружен файл (режим просмотра): {Path(filepath).name}")
            
            # Извлекаем данные с безопасной обработкой
            levels = safe_get(data_normalized, 'levels', {})
            rooms = safe_get(data_normalized, 'rooms', [])
            areas = safe_get(data_normalized, 'areas', [])
            openings = safe_get(data_normalized, 'openings', [])
            
            # Убеждаемся что это списки
            if not isinstance(levels, dict):
                levels = {}
            if not isinstance(rooms, list):
                rooms = []
            if not isinstance(areas, list):
                areas = []
            if not isinstance(openings, list):
                openings = []
            
            logger.info(f"📊 Найдено: {len(levels)} уровней, {len(rooms)} помещений, {len(areas)} зон, {len(openings)} проемов")
            
            # Обновляем информационные панели
            self._update_levels_list(levels)
            self._update_rooms_list(rooms)
            self._update_openings_list(openings)
            
            # Пытаемся отрисовать геометрию
            system_status = self.component_checker.check_all_components()
            if system_status['overall_status']['can_render_geometry'] and self.geometry_canvas:
                logger.info("🎨 Отрисовка данных на canvas (JSON режим)...")
                self._update_status("Отрисовка геометрии (JSON режим)...")
                
                render_data = {
                    'levels': levels,
                    'rooms': rooms,
                    'areas': areas,
                    'openings': openings
                }
                
                self.geometry_canvas.render_data(render_data)
                
                self._update_status(f"Загружен файл: {Path(filepath).name} (JSON)")
                logger.info("✅ Файл успешно загружен и отображен (JSON режим)")
            else:
                self._update_status(f"Файл загружен: {Path(filepath).name} (только просмотр)")
                logger.info("✅ Файл загружен в режиме просмотра (без отрисовки)")
        
        except Exception as e:
            error_msg = f"Ошибка fallback загрузки JSON: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            messagebox.showerror("Ошибка JSON", error_msg)
            self._update_status("Ошибка загрузки JSON файла")
    
    def _update_levels_list(self, levels):
        """Обновление списка уровней с безопасной обработкой"""
        if not hasattr(self, 'levels_text'):
            return
            
        try:
            self.levels_text.delete('1.0', tk.END)
            
            levels_normalized = normalize_data_structure(levels)
            
            self.levels_text.insert('1.0', f"Уровни здания ({len(levels_normalized)}):\n\n")
            
            for level_id, level_data in levels_normalized.items():
                level_data_norm = normalize_data_structure(level_data)
                
                name = safe_get(level_data_norm, 'name', str(level_id))
                elevation = float(safe_get(level_data_norm, 'elevation', 0))
                self.levels_text.insert(tk.END, f"• {name}\n  Отметка: {elevation:.2f} м\n\n")
                
        except Exception as e:
            logger.error(f"Ошибка обновления списка уровней: {e}")
            self.levels_text.delete('1.0', tk.END)
            self.levels_text.insert('1.0', f"Ошибка отображения уровней: {e}")
    
    def _update_rooms_list(self, rooms):
        """Обновление списка помещений с безопасной обработкой"""
        if not hasattr(self, 'rooms_text'):
            return
            
        try:
            self.rooms_text.delete('1.0', tk.END)
            
            if not isinstance(rooms, list):
                rooms = []
            
            self.rooms_text.insert('1.0', f"Помещения ({len(rooms)}):\n\n")
            
            for i, room_data in enumerate(rooms[:50]):  # Ограничиваем для производительности
                try:
                    room_normalized = normalize_data_structure(room_data)
                    
                    name = safe_get(room_normalized, 'name', f'Помещение {i+1}')
                    area = float(safe_get(room_normalized, 'area', 0))
                    level = safe_get(room_normalized, 'level', 'Неизвестно')
                    self.rooms_text.insert(tk.END, f"{i+1}. {name}\n   Площадь: {area:.2f} м²\n   Уровень: {level}\n\n")
                    
                except Exception as e:
                    logger.warning(f"Ошибка обработки помещения {i}: {e}")
                    self.rooms_text.insert(tk.END, f"{i+1}. Ошибка обработки помещения\n\n")
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка обновления списка помещений: {e}")
            self.rooms_text.delete('1.0', tk.END)
            self.rooms_text.insert('1.0', f"Ошибка отображения помещений: {e}")
    
    def _update_openings_list(self, openings):
        """Обновление списка проемов с безопасной обработкой"""
        if not hasattr(self, 'openings_text'):
            return
            
        try:
            self.openings_text.delete('1.0', tk.END)
            
            if not isinstance(openings, list):
                openings = []
            
            self.openings_text.insert('1.0', f"Проемы ({len(openings)}):\n\n")
            
            for i, opening_data in enumerate(openings[:50]):
                try:
                    opening_normalized = normalize_data_structure(opening_data)
                    
                    name = safe_get(opening_normalized, 'name', f'Проем {i+1}')
                    category = safe_get(opening_normalized, 'category', 'Неизвестно')
                    level = safe_get(opening_normalized, 'level', 'Неизвестно')
                    self.openings_text.insert(tk.END, f"{i+1}. {name}\n   Тип: {category}\n   Уровень: {level}\n\n")
                    
                except Exception as e:
                    logger.warning(f"Ошибка обработки проема {i}: {e}")
                    self.openings_text.insert(tk.END, f"{i+1}. Ошибка обработки проема\n\n")
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка обновления списка проемов: {e}")
            self.openings_text.delete('1.0', tk.END)
            self.openings_text.insert('1.0', f"Ошибка отображения проемов: {e}")
    
    # ===============================================
    # ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ
    # ===============================================
    
    def _fit_to_view(self):
        """Подгонка по размеру окна"""
        if self.geometry_canvas and hasattr(self.geometry_canvas.coordinate_system, 'fit_to_bounds'):
            try:
                # Можно реализовать подгонку по boundaries данных
                self._update_status("Подгонка по размеру...")
                # TODO: Реализовать логику подгонки
            except Exception as e:
                logger.error(f"Ошибка подгонки: {e}")
    
    def _toggle_grid(self):
        """Переключение сетки"""
        # TODO: Реализовать переключение сетки
        self._update_status("Переключение сетки...")
    
    def _show_about(self):
        """Диалог о программе"""
        about_text = f"""
{APPLICATION_NAME} v{SYSTEM_VERSION}

Система обработки геометрии зданий
для энергетического анализа

Возможности:
• Интерактивный просмотр планов зданий
• Выбор и редактирование элементов  
• Загрузка данных из Revit
• Экспорт в формат CONTAM

Состояние компонентов:
• InteractionController: {'✅' if INTERACTION_CONTROLLER_AVAILABLE else '❌'}
• Геометрические компоненты: {'✅' if GEOMETRY_COMPONENTS_AVAILABLE else '❌'}
• IO модули: {'✅' if IO_MODULES_AVAILABLE else '❌'}

Исправления в версии 2.0.2:
✅ Устранена ошибка "'float' object has no attribute 'get'"
✅ Улучшена обработка различных форматов данных
✅ Добавлена нормализация структур данных

Разработано для профессионального
использования в области проектирования
энергоэффективных зданий.
        """
        messagebox.showinfo("О программе", about_text)
    
    def _on_closing(self):
        """Обработчик закрытия приложения"""
        logger.info("👋 Завершение работы приложения")
        self.root.destroy()
    
    def initialize(self):
        """Инициализация приложения"""
        try:
            self._update_status("Приложение готово к работе")
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации: {e}")
            return False
    
    def run(self):
        """Запуск главного цикла приложения"""
        logger.info("🚀 Запуск главного цикла приложения с исправлениями v2.0.2")
        
        try:
            capability_level = self.component_checker.get_capability_level()
            logger.info(f"📊 Уровень возможностей: {capability_level}")
            
            if INTERACTION_CONTROLLER_AVAILABLE:
                logger.info("🎯 Интерактивность: ПОЛНАЯ (выбор, drag-select, hover)")
            else:
                logger.info("🎯 Интерактивность: БАЗОВАЯ (только навигация)")
            
            self.root.mainloop()
            
            logger.info("✅ Приложение завершено корректно")
            return True
            
        except KeyboardInterrupt:
            logger.info("⚠️ Прерывание пользователем")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка в главном цикле: {e}")
            return False


# ===============================================
# ТОЧКА ВХОДА
# ===============================================

if __name__ == '__main__':
    """Прямой запуск приложения с исправлениями загрузки"""
    print(f"🚀 Запуск {APPLICATION_NAME} v{SYSTEM_VERSION}")
    print("🔧 ЭТАП 4.2: ИСПРАВЛЕНИЕ ОШИБОК ЗАГРУЗКИ")
    print("✅ Устранена ошибка \"'float' object has no attribute 'get'\"")
    print("✅ Улучшена обработка различных форматов данных")
    
    if INTERACTION_CONTROLLER_AVAILABLE:
        print("✅ InteractionController интегрирован")
        print("✅ Доступно: клик, drag-select, hover, режимы взаимодействия")
    else:
        print("⚠️ InteractionController недоступен, используется базовая навигация")
    
    print()
    
    try:
        app = ModernBessApp()
        
        if app.initialize():
            print("✅ Приложение инициализировано")
            print("💡 Попробуйте:")
            print("   • Открыть файл BESS (Файл → Открыть)")
            print("   • Кликать по элементам для выбора")
            print("   • Ctrl+клик для множественного выбора")
            print("   • Перетаскивание для drag-select")
            print("   • Переключать режимы в панели инструментов")
            print()
            
            success = app.run()
            print("✅ Приложение завершено" if success else "⚠️ Приложение завершено с предупреждениями")
        else:
            print("❌ Ошибка инициализации")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        traceback.print_exc()
        sys.exit(1)