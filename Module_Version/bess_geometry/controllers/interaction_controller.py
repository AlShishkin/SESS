# -*- coding: utf-8 -*-
"""
InteractionController - современная система интерактивности для SOFT

Этап 4: "Реанимация интерактивности"
Портирует лучшие практики из legacy CanvasController в модульную архитектуру SOFT.

Ключевые особенности:
🖱️ Выбор элементов кликом (с Ctrl/Shift для множественного выбора)
📦 Drag-select (прямоугольное выделение)
✨ Визуальная подсветка (hover и selection)
🔗 Синхронизация с UI таблицами
⚡ Оптимизированная производительность
🎯 Event-driven архитектура
"""

import tkinter as tk
import math
from typing import Dict, List, Set, Optional, Tuple, Callable, Any
from enum import Enum
from dataclasses import dataclass
import time

# Импорты из модульной архитектуры SOFT
try:
    from geometry_utils import centroid_xy, bounds, r2, point_in_polygon
except ImportError:
    # Fallback для case когда utils недоступны
    def centroid_xy(points): return (0.0, 0.0) if points else (0.0, 0.0)
    def bounds(points): return (0.0, 0.0, 100.0, 100.0) if points else None
    def r2(value): return round(float(value), 2)
    def point_in_polygon(point, polygon): return False


class InteractionMode(Enum):
    """Режимы взаимодействия с canvas"""
    SELECTION = "selection"         # Выбор элементов ⭐ Основной режим
    NAVIGATION = "navigation"       # Панорамирование, зум
    DRAWING = "drawing"            # Рисование новых элементов
    EDITING = "editing"            # Редактирование существующих
    MEASURING = "measuring"        # Измерения


class SelectionMode(Enum):
    """Режимы выбора элементов"""
    SINGLE = "single"              # Одиночный выбор
    MULTIPLE = "multiple"          # Множественный (Ctrl/Shift)
    RECTANGULAR = "rectangular"    # Drag-select прямоугольник


@dataclass
class ElementHitInfo:
    """Информация о найденном элементе"""
    element_id: str
    element_type: str
    canvas_ids: List[int]
    distance: float = 0.0
    properties: Dict = None


@dataclass
class SelectionState:
    """Состояние выделения"""
    selected_ids: Set[str]
    hover_id: Optional[str] = None
    last_selected: Optional[str] = None
    selection_time: float = 0.0


class InteractionController:
    """
    Современный контроллер интерактивности для SOFT
    
    Управляет всеми типами взаимодействия пользователя с canvas:
    - Выбор элементов (клик, drag-select)
    - Визуальная обратная связь (подсветка, hover)
    - Синхронизация с UI компонентами
    - Обработка горячих клавиш
    
    Архитектурные принципы:
    - Event-driven: все через события
    - Модульность: легко расширяется новыми режимами
    - Производительность: умное кэширование и оптимизации
    """
    
    def __init__(self, canvas_widget: tk.Canvas):
        """
        Инициализация контроллера интерактивности
        
        Args:
            canvas_widget: Tkinter Canvas для обработки событий
        """
        self.canvas = canvas_widget
        
        # === СОСТОЯНИЕ СИСТЕМЫ ===
        self.interaction_mode = InteractionMode.SELECTION
        self.selection_mode = SelectionMode.SINGLE
        self.selection_state = SelectionState(selected_ids=set())
        
        # Координатная система (будет установлена извне)
        self.coordinate_system = None
        
        # === МАППИНГ ЭЛЕМЕНТОВ ===
        # canvas_id -> ElementHitInfo
        self.element_mappings: Dict[int, ElementHitInfo] = {}
        # element_id -> List[canvas_id]
        self.element_canvas_map: Dict[str, List[int]] = {}
        
        # === DRAG-SELECT СОСТОЯНИЕ ===
        self.is_dragging = False
        self.drag_start_pos: Optional[Tuple[int, int]] = None
        self.selection_rect: Optional[List[int]] = None  # [x1, y1, x2, y2]
        self.selection_rect_canvas_id: Optional[int] = None
        
        # === HOVER СОСТОЯНИЕ ===
        self.hover_element_id: Optional[str] = None
        self.hover_canvas_ids: List[int] = []
        
        # === ОБРАБОТЧИКИ СОБЫТИЙ ===
        self.event_handlers = {
            'selection_changed': [],
            'element_clicked': [],
            'element_hover': [],
            'interaction_mode_changed': []
        }
        
        # === НАСТРОЙКИ ВИЗУАЛИЗАЦИИ ===
        self.colors = {
            'selection': '#00ff00',      # Зеленый для выделения
            'hover': '#ffff00',          # Желтый для hover
            'drag_select': '#0080ff',    # Синий для drag-select
            'normal': '#000000'          # Черный для обычного состояния
        }
        
        self.styles = {
            'selection_width': 3,
            'hover_width': 2,
            'drag_select_width': 1,
            'dash_pattern': (5, 5)
        }
        
        # === КЭШ ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ ===
        self.hit_test_cache = {}
        self.last_mouse_pos = (0, 0)
        self.cache_invalidation_time = 0.1  # секунд
        
        # Подключаем обработчики событий мыши и клавиатуры
        self._setup_event_handlers()
        
        print("✅ InteractionController инициализирован")
    
    def set_coordinate_system(self, coord_system):
        """Установка системы координат"""
        self.coordinate_system = coord_system
    
    def _setup_event_handlers(self):
        """Настройка обработчиков событий мыши и клавиатуры"""
        # === СОБЫТИЯ МЫШИ ===
        self.canvas.bind("<Button-1>", self._on_left_click)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_release)
        
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Enter>", self._on_mouse_enter)
        self.canvas.bind("<Leave>", self._on_mouse_leave)
        
        # === СОБЫТИЯ КЛАВИАТУРЫ ===
        self.canvas.bind("<Key>", self._on_key_press)
        self.canvas.focus_set()  # Включаем прием событий клавиатуры
        
        print("🖱️ Обработчики событий настроены")
    
    # ================================
    # ОСНОВНЫЕ ОБРАБОТЧИКИ СОБЫТИЙ
    # ================================
    
    def _on_left_click(self, event):
        """Обработка левого клика мыши"""
        if self.interaction_mode == InteractionMode.SELECTION:
            self._handle_selection_click(event)
        elif self.interaction_mode == InteractionMode.DRAWING:
            self._handle_drawing_click(event)
    
    def _on_left_drag(self, event):
        """Обработка перетаскивания левой кнопкой"""
        if self.interaction_mode == InteractionMode.SELECTION:
            self._handle_selection_drag(event)
        elif self.interaction_mode == InteractionMode.NAVIGATION:
            self._handle_navigation_drag(event)
    
    def _on_left_release(self, event):
        """Обработка отпускания левой кнопки"""
        if self.is_dragging:
            self._complete_drag_operation(event)
    
    def _on_mouse_move(self, event):
        """Обработка движения мыши"""
        self.last_mouse_pos = (event.x, event.y)
        
        if not self.is_dragging:
            # Обновляем hover только когда не тащим
            self._update_hover_state(event.x, event.y)
    
    def _on_mouse_enter(self, event):
        """Мышь вошла в canvas"""
        self.canvas.focus_set()
    
    def _on_mouse_leave(self, event):
        """Мышь покинула canvas"""
        self._clear_hover_state()
    
    def _on_key_press(self, event):
        """Обработка нажатий клавиш"""
        key = event.keysym.lower()
        
        # Esc - сброс выделения
        if key == 'escape':
            self.clear_selection()
        
        # Delete - удаление выбранных элементов
        elif key == 'delete':
            self._fire_event('elements_delete_requested', {
                'element_ids': list(self.selection_state.selected_ids)
            })
        
        # Ctrl+A - выделить все
        elif event.state & 0x4 and key == 'a':  # Ctrl+A
            self._select_all_elements()
        
        # F - подогнать все элементы в окно
        elif key == 'f':
            self._fire_event('fit_all_requested', {})
    
    # ================================
    # ОБРАБОТКА ВЫДЕЛЕНИЯ
    # ================================
    
    def _handle_selection_click(self, event):
        """Обработка клика для выделения элементов"""
        screen_x, screen_y = event.x, event.y
        
        # Определяем режим выделения по модификаторам
        ctrl_pressed = event.state & 0x4
        shift_pressed = event.state & 0x1
        
        if ctrl_pressed or shift_pressed:
            self.selection_mode = SelectionMode.MULTIPLE
        else:
            self.selection_mode = SelectionMode.SINGLE
        
        # Находим элемент под курсором
        hit_info = self._find_element_at_point(screen_x, screen_y)
        
        if hit_info:
            # Клик по элементу
            self._handle_element_selection(hit_info, ctrl_pressed, shift_pressed)
        else:
            # Клик по пустому месту
            if self.selection_mode == SelectionMode.SINGLE:
                # Очищаем выделение
                self.clear_selection()
            else:
                # Начинаем drag-select
                self._start_drag_select(screen_x, screen_y)
    
    def _handle_element_selection(self, hit_info: ElementHitInfo, ctrl: bool, shift: bool):
        """Обработка выделения конкретного элемента"""
        element_id = hit_info.element_id
        
        if ctrl:
            # Ctrl - переключение выделения
            if element_id in self.selection_state.selected_ids:
                self.selection_state.selected_ids.remove(element_id)
            else:
                self.selection_state.selected_ids.add(element_id)
        elif shift and self.selection_state.last_selected:
            # Shift - диапазон выделения (TODO: реализовать логику диапазона)
            self.selection_state.selected_ids.add(element_id)
        else:
            # Обычный клик - заменить выделение
            self.selection_state.selected_ids = {element_id}
        
        self.selection_state.last_selected = element_id
        self.selection_state.selection_time = time.time()
        
        # Обновляем визуализацию и уведомляем подписчиков
        self._update_selection_display()
        self._fire_selection_changed_event()
        
        # Уведомляем о клике по элементу
        self._fire_event('element_clicked', {
            'element_id': element_id,
            'element_type': hit_info.element_type,
            'properties': hit_info.properties,
            'ctrl_pressed': ctrl,
            'shift_pressed': shift
        })
    
    def _handle_selection_drag(self, event):
        """Обработка drag-select"""
        if not self.is_dragging:
            return
        
        # Обновляем прямоугольник выделения
        current_x, current_y = event.x, event.y
        if self.drag_start_pos:
            start_x, start_y = self.drag_start_pos
            
            # Координаты прямоугольника (упорядочиваем)
            min_x = min(start_x, current_x)
            max_x = max(start_x, current_x)
            min_y = min(start_y, current_y)
            max_y = max(start_y, current_y)
            
            self.selection_rect = [min_x, min_y, max_x, max_y]
            
            # Перерисовываем прямоугольник выделения
            self._update_drag_select_rectangle()
    
    def _start_drag_select(self, x: int, y: int):
        """Начало drag-select операции"""
        self.is_dragging = True
        self.drag_start_pos = (x, y)
        self.selection_rect = [x, y, x, y]
        
        # Создаем визуальный прямоугольник
        self.selection_rect_canvas_id = self.canvas.create_rectangle(
            x, y, x, y,
            outline=self.colors['drag_select'],
            fill='',
            width=self.styles['drag_select_width'],
            dash=self.styles['dash_pattern']
        )
    
    def _update_drag_select_rectangle(self):
        """Обновление визуального прямоугольника drag-select"""
        if self.selection_rect_canvas_id and self.selection_rect:
            x1, y1, x2, y2 = self.selection_rect
            self.canvas.coords(self.selection_rect_canvas_id, x1, y1, x2, y2)
    
    def _complete_drag_operation(self, event):
        """Завершение drag-select операции"""
        if not self.is_dragging:
            return
        
        # Находим элементы в прямоугольнике выделения
        if self.selection_rect:
            selected_ids = self._find_elements_in_rectangle()
            
            # Обновляем выделение
            if event.state & 0x4:  # Ctrl - добавляем к выделению
                self.selection_state.selected_ids.update(selected_ids)
            else:  # Заменяем выделение
                self.selection_state.selected_ids = selected_ids
            
            self._update_selection_display()
            self._fire_selection_changed_event()
        
        # Убираем прямоугольник выделения
        if self.selection_rect_canvas_id:
            self.canvas.delete(self.selection_rect_canvas_id)
            self.selection_rect_canvas_id = None
        
        # Сбрасываем состояние
        self.is_dragging = False
        self.drag_start_pos = None
        self.selection_rect = None
    
    # ================================
    # HOVER ЭФФЕКТЫ
    # ================================
    
    def _update_hover_state(self, x: int, y: int):
        """Обновление состояния hover"""
        hit_info = self._find_element_at_point(x, y)
        
        new_hover_id = hit_info.element_id if hit_info else None
        
        if new_hover_id != self.hover_element_id:
            # Убираем старый hover
            if self.hover_element_id:
                self._remove_hover_highlight(self.hover_element_id)
            
            # Добавляем новый hover
            if new_hover_id:
                self._add_hover_highlight(new_hover_id)
                
                # Уведомляем о hover
                self._fire_event('element_hover', {
                    'element_id': new_hover_id,
                    'element_type': hit_info.element_type,
                    'mouse_pos': (x, y)
                })
            
            self.hover_element_id = new_hover_id
    
    def _clear_hover_state(self):
        """Очистка hover состояния"""
        if self.hover_element_id:
            self._remove_hover_highlight(self.hover_element_id)
            self.hover_element_id = None
    
    # ================================
    # ПОИСК ЭЛЕМЕНТОВ
    # ================================
    
    def _find_element_at_point(self, x: int, y: int) -> Optional[ElementHitInfo]:
        """
        Поиск элемента в указанной точке
        
        Returns:
            ElementHitInfo если элемент найден, None иначе
        """
        # Используем встроенный метод Canvas для поиска
        canvas_item = self.canvas.find_closest(x, y)[0]
        
        # Проверяем, есть ли элемент в нашем маппинге
        if canvas_item in self.element_mappings:
            return self.element_mappings[canvas_item]
        
        return None
    
    def _find_elements_in_rectangle(self) -> Set[str]:
        """
        Поиск элементов в прямоугольнике drag-select
        
        Returns:
            Множество ID найденных элементов
        """
        if not self.selection_rect or not self.coordinate_system:
            return set()
        
        screen_x1, screen_y1, screen_x2, screen_y2 = self.selection_rect
        
        # Преобразуем в мировые координаты
        world_x1, world_y1 = self.coordinate_system.screen_to_world(screen_x1, screen_y2)
        world_x2, world_y2 = self.coordinate_system.screen_to_world(screen_x2, screen_y1)
        
        # Нормализуем координаты
        min_x, max_x = min(world_x1, world_x2), max(world_x1, world_x2)
        min_y, max_y = min(world_y1, world_y2), max(world_y1, world_y2)
        
        selected_ids = set()
        
        # Проходим по всем элементам и проверяем пересечение
        for canvas_id, hit_info in self.element_mappings.items():
            # Получаем bounding box элемента из canvas
            try:
                bbox = self.canvas.bbox(canvas_id)
                if bbox:
                    item_x1, item_y1, item_x2, item_y2 = bbox
                    
                    # Преобразуем в мировые координаты
                    item_world_x1, item_world_y1 = self.coordinate_system.screen_to_world(item_x1, item_y2)
                    item_world_x2, item_world_y2 = self.coordinate_system.screen_to_world(item_x2, item_y1)
                    
                    # Проверяем пересечение
                    if (max(min_x, min(item_world_x1, item_world_x2)) < 
                        min(max_x, max(item_world_x1, item_world_x2)) and
                        max(min_y, min(item_world_y1, item_world_y2)) < 
                        min(max_y, max(item_world_y1, item_world_y2))):
                        selected_ids.add(hit_info.element_id)
            except tk.TclError:
                # Элемент был удален из canvas
                continue
        
        return selected_ids
    
    # ================================
    # ВИЗУАЛИЗАЦИЯ
    # ================================
    
    def _update_selection_display(self):
        """Обновление визуального отображения выделения"""
        # Проходим по всем элементам и обновляем их стиль
        for canvas_id, hit_info in self.element_mappings.items():
            is_selected = hit_info.element_id in self.selection_state.selected_ids
            self._set_element_selection_style(canvas_id, is_selected)
    
    def _set_element_selection_style(self, canvas_id: int, selected: bool):
        """Установка стиля выделения для элемента"""
        try:
            if selected:
                # Выделенный стиль
                self.canvas.itemconfig(canvas_id, 
                    outline=self.colors['selection'],
                    width=self.styles['selection_width'])
            else:
                # Обычный стиль (восстанавливаем исходный)
                self.canvas.itemconfig(canvas_id,
                    outline=self.colors['normal'],
                    width=1)
        except tk.TclError:
            # Элемент был удален из canvas
            pass
    
    def _add_hover_highlight(self, element_id: str):
        """Добавление hover подсветки элементу"""
        canvas_ids = self.element_canvas_map.get(element_id, [])
        for canvas_id in canvas_ids:
            if canvas_id not in [cid for cid, info in self.element_mappings.items() 
                               if info.element_id in self.selection_state.selected_ids]:
                # Применяем hover только если элемент не выделен
                try:
                    self.canvas.itemconfig(canvas_id,
                        outline=self.colors['hover'],
                        width=self.styles['hover_width'])
                except tk.TclError:
                    pass
    
    def _remove_hover_highlight(self, element_id: str):
        """Удаление hover подсветки элемента"""
        canvas_ids = self.element_canvas_map.get(element_id, [])
        for canvas_id in canvas_ids:
            if canvas_id not in [cid for cid, info in self.element_mappings.items() 
                               if info.element_id in self.selection_state.selected_ids]:
                # Восстанавливаем обычный стиль только если элемент не выделен
                try:
                    self.canvas.itemconfig(canvas_id,
                        outline=self.colors['normal'],
                        width=1)
                except tk.TclError:
                    pass
    
    # ================================
    # УПРАВЛЕНИЕ ЭЛЕМЕНТАМИ
    # ================================
    
    def register_element(self, canvas_ids: List[int], element_id: str, 
                        element_type: str, properties: Dict = None):
        """
        Регистрация элемента для интерактивности
        
        Args:
            canvas_ids: Список ID canvas объектов элемента
            element_id: Уникальный ID элемента
            element_type: Тип элемента (room, area, opening)
            properties: Дополнительные свойства элемента
        """
        hit_info = ElementHitInfo(
            element_id=element_id,
            element_type=element_type,
            canvas_ids=canvas_ids.copy(),
            properties=properties or {}
        )
        
        # Регистрируем каждый canvas_id
        for canvas_id in canvas_ids:
            self.element_mappings[canvas_id] = hit_info
        
        # Обновляем обратное отображение
        self.element_canvas_map[element_id] = canvas_ids.copy()
        
        print(f"🎯 Зарегистрирован элемент {element_id} ({element_type}) с {len(canvas_ids)} canvas объектами")
    
    def unregister_element(self, element_id: str):
        """Отмена регистрации элемента"""
        if element_id in self.element_canvas_map:
            canvas_ids = self.element_canvas_map[element_id]
            
            # Удаляем из маппингов
            for canvas_id in canvas_ids:
                if canvas_id in self.element_mappings:
                    del self.element_mappings[canvas_id]
            
            del self.element_canvas_map[element_id]
            
            # Убираем из выделения
            self.selection_state.selected_ids.discard(element_id)
            
            print(f"🗑️ Элемент {element_id} удален из системы интерактивности")
    
    def clear_all_elements(self):
        """Очистка всех зарегистрированных элементов"""
        self.element_mappings.clear()
        self.element_canvas_map.clear()
        self.clear_selection()
        self._clear_hover_state()
        print("🧹 Все элементы очищены из системы интерактивности")
    
    # ================================
    # УПРАВЛЕНИЕ ВЫДЕЛЕНИЕМ
    # ================================
    
    def select_elements(self, element_ids: List[str], append: bool = False):
        """
        Программное выделение элементов
        
        Args:
            element_ids: Список ID элементов для выделения
            append: Добавить к текущему выделению (True) или заменить (False)
        """
        if not append:
            self.selection_state.selected_ids.clear()
        
        # Добавляем только существующие элементы
        valid_ids = [eid for eid in element_ids if eid in self.element_canvas_map]
        self.selection_state.selected_ids.update(valid_ids)
        
        if valid_ids:
            self.selection_state.last_selected = valid_ids[-1]
            self.selection_state.selection_time = time.time()
        
        self._update_selection_display()
        self._fire_selection_changed_event()
        
        print(f"📋 Выделено {len(valid_ids)} элементов программно")
    
    def clear_selection(self):
        """Очистка выделения"""
        if self.selection_state.selected_ids:
            self.selection_state.selected_ids.clear()
            self.selection_state.last_selected = None
            self._update_selection_display()
            self._fire_selection_changed_event()
            print("🧹 Выделение очищено")
    
    def get_selected_elements(self) -> List[str]:
        """Получение списка выделенных элементов"""
        return list(self.selection_state.selected_ids)
    
    def _select_all_elements(self):
        """Выделение всех элементов"""
        all_ids = list(self.element_canvas_map.keys())
        self.select_elements(all_ids, append=False)
        print(f"🎯 Выделены все элементы ({len(all_ids)})")
    
    # ================================
    # СИСТЕМА СОБЫТИЙ
    # ================================
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """Добавление обработчика события"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable):
        """Удаление обработчика события"""
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
            except ValueError:
                pass
    
    def _fire_event(self, event_type: str, data: Dict):
        """Вызов обработчиков события"""
        for handler in self.event_handlers.get(event_type, []):
            try:
                handler(data)
            except Exception as e:
                print(f"❌ Ошибка в обработчике события {event_type}: {e}")
    
    def _fire_selection_changed_event(self):
        """Вызов события изменения выделения"""
        self._fire_event('selection_changed', {
            'selected_ids': list(self.selection_state.selected_ids),
            'selection_count': len(self.selection_state.selected_ids),
            'last_selected': self.selection_state.last_selected,
            'selection_time': self.selection_state.selection_time
        })
    
    # ================================
    # РЕЖИМЫ ВЗАИМОДЕЙСТВИЯ
    # ================================
    
    def set_interaction_mode(self, mode: InteractionMode):
        """Смена режима взаимодействия"""
        old_mode = self.interaction_mode
        self.interaction_mode = mode
        
        # Сбрасываем состояние при смене режима
        if self.is_dragging:
            self._complete_drag_operation(None)
        
        self._fire_event('interaction_mode_changed', {
            'old_mode': old_mode,
            'new_mode': mode
        })
        
        print(f"🎮 Режим взаимодействия изменен: {old_mode.value} → {mode.value}")
    
    def get_interaction_mode(self) -> InteractionMode:
        """Получение текущего режима взаимодействия"""
        return self.interaction_mode
    
    # ================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ================================
    
    def _handle_drawing_click(self, event):
        """Обработка клика в режиме рисования"""
        # TODO: Реализовать логику рисования
        print(f"🎨 Клик в режиме рисования: ({event.x}, {event.y})")
    
    def _handle_navigation_drag(self, event):
        """Обработка drag в режиме навигации"""
        # TODO: Реализовать панорамирование
        print(f"🧭 Навигация: ({event.x}, {event.y})")
    
    def get_statistics(self) -> Dict:
        """Получение статистики работы контроллера"""
        return {
            'registered_elements': len(self.element_canvas_map),
            'canvas_objects': len(self.element_mappings),
            'selected_count': len(self.selection_state.selected_ids),
            'interaction_mode': self.interaction_mode.value,
            'selection_mode': self.selection_mode.value,
            'hover_element': self.hover_element_id,
            'is_dragging': self.is_dragging
        }


# =====================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ И ИНТЕГРАЦИИ
# =====================================

def create_interaction_demo():
    """
    Демонстрация создания и использования InteractionController
    """
    import tkinter as tk
    
    # Создаем тестовое окно
    root = tk.Tk()
    root.title("SOFT - Интерактивность Этап 4")
    root.geometry("800x600")
    
    # Создаем canvas
    canvas = tk.Canvas(root, bg='white')
    canvas.pack(fill='both', expand=True)
    
    # Создаем контроллер интерактивности
    interaction = InteractionController(canvas)
    
    # Добавляем обработчики событий
    def on_selection_changed(data):
        print(f"🎯 Выделение изменено: {data['selection_count']} элементов")
        print(f"   ID: {data['selected_ids']}")
    
    def on_element_clicked(data):
        print(f"🖱️ Клик по элементу: {data['element_id']} ({data['element_type']})")
    
    def on_element_hover(data):
        print(f"👆 Hover: {data['element_id']}")
    
    interaction.add_event_handler('selection_changed', on_selection_changed)
    interaction.add_event_handler('element_clicked', on_element_clicked)
    interaction.add_event_handler('element_hover', on_element_hover)
    
    # Создаем тестовые элементы
    def create_test_elements():
        # Комната 1
        room1_ids = [
            canvas.create_rectangle(50, 50, 200, 150, outline='blue', fill='lightblue'),
            canvas.create_text(125, 100, text="Комната 1")
        ]
        interaction.register_element(room1_ids, "room_1", "room", 
                                   {"name": "Комната 1", "area": 15.0})
        
        # Комната 2  
        room2_ids = [
            canvas.create_rectangle(250, 80, 400, 200, outline='green', fill='lightgreen'),
            canvas.create_text(325, 140, text="Комната 2")
        ]
        interaction.register_element(room2_ids, "room_2", "room",
                                   {"name": "Комната 2", "area": 22.5})
        
        # Проем
        opening_ids = [
            canvas.create_rectangle(180, 90, 220, 110, outline='red', fill='yellow')
        ]
        interaction.register_element(opening_ids, "opening_1", "opening",
                                   {"name": "Дверь", "width": 0.9})
    
    # Создаем элементы после небольшой задержки
    root.after(100, create_test_elements)
    
    # Добавляем статус-бар
    status_bar = tk.Label(root, text="Готов к работе", relief='sunken', anchor='w')
    status_bar.pack(side='bottom', fill='x')
    
    def update_status():
        stats = interaction.get_statistics()
        status_text = f"Режим: {stats['interaction_mode']} | " \
                     f"Элементов: {stats['registered_elements']} | " \
                     f"Выделено: {stats['selected_count']}"
        if stats['hover_element']:
            status_text += f" | Hover: {stats['hover_element']}"
        status_bar.config(text=status_text)
        root.after(100, update_status)
    
    update_status()
    
    print("🚀 Демо интерактивности запущено!")
    print("💡 Попробуйте:")
    print("   • Кликать по элементам")
    print("   • Ctrl+клик для множественного выбора")  
    print("   • Перетаскивание для drag-select")
    print("   • Наведение мыши для hover эффектов")
    print("   • Escape для сброса выделения")
    print("   • Ctrl+A для выделения всех")
    
    return root, interaction

if __name__ == "__main__":
    # Запуск демо если файл запущен напрямую
    root, interaction = create_interaction_demo()
    root.mainloop()