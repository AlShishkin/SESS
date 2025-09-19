# -*- coding: utf-8 -*-
"""
ContourEditor - интерактивный редактор контуров для BESS_Geometry

Этот модуль обеспечивает профессиональное редактирование геометрических контуров:
• Визуальное выделение вершин и ребер
• Добавление вершин на ребро (Shift+Click)  
• Удаление вершин (Delete)
• Перемещение вершин drag&drop
• Привязка к сетке и другим элементам
• Валидация геометрии в реальном времени
• Отмена/повтор операций редактирования

Редактор спроектирован для работы с архитектурной точностью и обеспечивает
интуитивное взаимодействие, знакомое пользователям профессиональных CAD-систем.
"""

import math
import tkinter as tk
from typing import Dict, List, Optional, Tuple, Set, Any, Callable
from enum import Enum
from dataclasses import dataclass
from copy import deepcopy

# Импорты с обработкой ошибок
try:
    from geometry_utils import centroid_xy, bounds, r2, polygon_area, point_in_polygon
    GEOMETRY_UTILS_AVAILABLE = True
except ImportError:
    print("Предупреждение: geometry_utils недоступен для contour_editor")
    GEOMETRY_UTILS_AVAILABLE = False
    
    def r2(value): return round(float(value), 2)


class EditingMode(Enum):
    """Режимы редактирования контура"""
    NONE = "none"                    # Без редактирования
    SELECT_VERTEX = "select_vertex"  # Выбор вершин
    MOVE_VERTEX = "move_vertex"      # Перемещение вершины
    ADD_VERTEX = "add_vertex"        # Добавление вершины
    DELETE_VERTEX = "delete_vertex"  # Удаление вершины
    SELECT_EDGE = "select_edge"      # Выбор ребер
    MOVE_CONTOUR = "move_contour"    # Перемещение всего контура


class ElementType(Enum):
    """Типы элементов контура"""
    VERTEX = "vertex"    # Вершина
    EDGE = "edge"        # Ребро
    CONTOUR = "contour"  # Весь контур


@dataclass
class EditingState:
    """Состояние редактирования"""
    mode: EditingMode = EditingMode.NONE
    selected_elements: Set[int] = None  # Индексы выбранных элементов
    hover_element: Optional[Tuple[ElementType, int]] = None
    drag_start: Optional[Tuple[float, float]] = None
    drag_current: Optional[Tuple[float, float]] = None
    is_dragging: bool = False
    snap_to_grid: bool = True
    grid_size: float = 0.5  # Размер сетки в метрах
    snap_tolerance: float = 0.2  # Толерантность привязки
    
    def __post_init__(self):
        if self.selected_elements is None:
            self.selected_elements = set()


class ContourEditor:
    """
    Интерактивный редактор контуров для геометрических элементов
    
    Предоставляет полнофункциональный интерфейс для редактирования контуров
    с поддержкой всех стандартных операций CAD-систем.
    """
    
    def __init__(self, canvas: tk.Canvas):
        """
        Инициализация редактора контуров
        
        Args:
            canvas: Tkinter Canvas для отрисовки
        """
        self.canvas = canvas
        
        # Состояние редактирования
        self.editing_state = EditingState()
        
        # Данные контура
        self.contour_coords = []  # Координаты в мировой системе (метры)
        self.original_coords = []  # Оригинальные координаты для отмены
        self.element_id = None    # ID редактируемого элемента
        
        # Визуальные настройки
        self.visual_settings = {
            'vertex_radius': 4,
            'vertex_color': '#ff6b6b',
            'vertex_selected_color': '#00ff00',
            'vertex_hover_color': '#ffd93d',
            'edge_color': '#4cc9f0',
            'edge_selected_color': '#00ff00',
            'edge_hover_color': '#ffd93d',
            'edge_width': 2,
            'contour_color': '#6b7280',
            'contour_width': 1,
            'grid_color': '#e5e7eb',
            'snap_indicator_color': '#f59e0b'
        }
        
        # Объекты отрисовки на canvas
        self.canvas_objects = {
            'vertices': [],
            'edges': [],
            'contour': None,
            'grid': [],
            'snap_indicators': [],
            'selection_box': None
        }
        
        # Система координат
        self.coordinate_system = None  # Будет установлена извне
        
        # Обработчики событий
        self.event_handlers = {
            'vertex_moved': [],
            'vertex_added': [],
            'vertex_deleted': [],
            'contour_modified': [],
            'editing_finished': []
        }
        
        # Операции для отмены
        self.operation_history = []
        self.current_operation_index = -1
        
        # Привязка событий мыши
        self._bind_mouse_events()
        
        print("✅ ContourEditor инициализирован")
    
    def start_editing(self, element_id: str, coords: List[Tuple[float, float]]):
        """
        Начало редактирования контура элемента
        
        Args:
            element_id: ID элемента для редактирования
            coords: Координаты контура в мировой системе (метры)
        """
        self.element_id = element_id
        self.contour_coords = deepcopy(coords)
        self.original_coords = deepcopy(coords)
        
        # Сбрасываем состояние
        self.editing_state = EditingState()
        self.editing_state.mode = EditingMode.SELECT_VERTEX
        
        # Очищаем историю операций
        self.operation_history = [deepcopy(coords)]
        self.current_operation_index = 0
        
        # Отрисовываем контур
        self._redraw_all()
        
        print(f"🎨 Начато редактирование контура элемента {element_id}")
    
    def finish_editing(self, save_changes: bool = True) -> List[Tuple[float, float]]:
        """
        Завершение редактирования
        
        Args:
            save_changes: Сохранить изменения или вернуться к оригиналу
            
        Returns:
            Итоговые координаты контура
        """
        if not save_changes:
            self.contour_coords = deepcopy(self.original_coords)
        
        # Очищаем canvas
        self._clear_all_objects()
        
        # Сбрасываем состояние
        self.editing_state.mode = EditingMode.NONE
        result_coords = deepcopy(self.contour_coords)
        
        # Уведомляем о завершении
        self._fire_event('editing_finished', {
            'element_id': self.element_id,
            'coords': result_coords,
            'changes_saved': save_changes
        })
        
        print(f"🎨 Завершено редактирование контура элемента {self.element_id}")
        
        return result_coords
    
    def set_coordinate_system(self, coord_system):
        """Установка системы координат для конвертации pixel <-> meter"""
        self.coordinate_system = coord_system
    
    # === ОБРАБОТКА СОБЫТИЙ МЫШИ ===
    
    def _bind_mouse_events(self):
        """Привязка событий мыши к canvas"""
        self.canvas.bind('<Button-1>', self._on_mouse_click)
        self.canvas.bind('<B1-Motion>', self._on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_mouse_release)
        self.canvas.bind('<Motion>', self._on_mouse_move)
        self.canvas.bind('<Shift-Button-1>', self._on_shift_click)
        self.canvas.bind('<Delete>', self._on_delete_key)
        self.canvas.bind('<Escape>', self._on_escape_key)
        
        # Фокус для клавиш
        self.canvas.focus_set()
    
    def _on_mouse_click(self, event):
        """Обработка клика мыши"""
        if self.editing_state.mode == EditingMode.NONE:
            return
        
        canvas_x, canvas_y = event.x, event.y
        world_x, world_y = self._canvas_to_world(canvas_x, canvas_y)
        
        # Поиск элемента под курсором
        element = self.find_nearest_element(canvas_x, canvas_y, self.contour_coords)
        
        if element:
            element_type, element_index = element
            
            if element_type == ElementType.VERTEX:
                self._handle_vertex_click(element_index, world_x, world_y)
            elif element_type == ElementType.EDGE:
                self._handle_edge_click(element_index, world_x, world_y)
    
    def _on_mouse_drag(self, event):
        """Обработка перетаскивания мыши"""
        if self.editing_state.mode != EditingMode.MOVE_VERTEX:
            return
        
        canvas_x, canvas_y = event.x, event.y
        world_x, world_y = self._canvas_to_world(canvas_x, canvas_y)
        
        # Применяем привязку к сетке
        if self.editing_state.snap_to_grid:
            world_x, world_y = self._snap_to_grid(world_x, world_y)
        
        self.editing_state.drag_current = (world_x, world_y)
        self.editing_state.is_dragging = True
        
        # Обновляем позицию выбранных вершин
        self._update_vertex_positions(world_x, world_y)
        self._redraw_all()
    
    def _on_mouse_release(self, event):
        """Обработка отпускания кнопки мыши"""
        if self.editing_state.is_dragging:
            self.editing_state.is_dragging = False
            
            # Сохраняем операцию для отмены
            self._save_operation()
            
            # Уведомляем о перемещении вершины
            self._fire_event('vertex_moved', {
                'element_id': self.element_id,
                'coords': self.contour_coords
            })
    
    def _on_mouse_move(self, event):
        """Обработка движения мыши (hover эффекты)"""
        if self.editing_state.mode == EditingMode.NONE:
            return
        
        canvas_x, canvas_y = event.x, event.y
        
        # Поиск элемента под курсором
        element = self.find_nearest_element(canvas_x, canvas_y, self.contour_coords)
        
        # Обновляем hover состояние
        old_hover = self.editing_state.hover_element
        self.editing_state.hover_element = element
        
        # Перерисовываем если hover изменился
        if old_hover != element:
            self._redraw_all()
        
        # Обновляем курсор
        self._update_cursor(element)
    
    def _on_shift_click(self, event):
        """Обработка Shift+Click для добавления вершин"""
        canvas_x, canvas_y = event.x, event.y
        world_x, world_y = self._canvas_to_world(canvas_x, canvas_y)
        
        # Применяем привязку к сетке
        if self.editing_state.snap_to_grid:
            world_x, world_y = self._snap_to_grid(world_x, world_y)
        
        # Поиск ребра для вставки вершины
        element = self.find_nearest_element(canvas_x, canvas_y, self.contour_coords)
        
        if element and element[0] == ElementType.EDGE:
            edge_index = element[1]
            self._add_vertex_on_edge(edge_index, world_x, world_y)
    
    def _on_delete_key(self, event):
        """Обработка клавиши Delete"""
        self._delete_selected_vertices()
    
    def _on_escape_key(self, event):
        """Обработка клавиши Escape"""
        self.editing_state.selected_elements.clear()
        self._redraw_all()
    
    # === ОПЕРАЦИИ С ВЕРШИНАМИ ===
    
    def _handle_vertex_click(self, vertex_index: int, world_x: float, world_y: float):
        """Обработка клика по вершине"""
        # Toggle выбор вершины
        if vertex_index in self.editing_state.selected_elements:
            self.editing_state.selected_elements.remove(vertex_index)
        else:
            self.editing_state.selected_elements.add(vertex_index)
        
        # Если есть выбранные вершины, переходим в режим перемещения
        if self.editing_state.selected_elements:
            self.editing_state.mode = EditingMode.MOVE_VERTEX
            self.editing_state.drag_start = (world_x, world_y)
        
        self._redraw_all()
    
    def _handle_edge_click(self, edge_index: int, world_x: float, world_y: float):
        """Обработка клика по ребру"""
        # В будущем можно добавить выбор ребер
        pass
    
    def _update_vertex_positions(self, world_x: float, world_y: float):
        """Обновление позиций выбранных вершин"""
        if not self.editing_state.drag_start:
            return
        
        start_x, start_y = self.editing_state.drag_start
        dx = world_x - start_x
        dy = world_y - start_y
        
        for vertex_index in self.editing_state.selected_elements:
            if 0 <= vertex_index < len(self.contour_coords):
                old_x, old_y = self.contour_coords[vertex_index]
                self.contour_coords[vertex_index] = (old_x + dx, old_y + dy)
        
        # Обновляем точку старта для следующего движения
        self.editing_state.drag_start = (world_x, world_y)
    
    def _add_vertex_on_edge(self, edge_index: int, world_x: float, world_y: float):
        """Добавление вершины на ребро"""
        if 0 <= edge_index < len(self.contour_coords):
            # Вставляем новую вершину после edge_index
            insert_index = edge_index + 1
            self.contour_coords.insert(insert_index, (world_x, world_y))
            
            # Обновляем выбор
            self.editing_state.selected_elements.clear()
            self.editing_state.selected_elements.add(insert_index)
            
            # Сохраняем операцию
            self._save_operation()
            
            # Уведомляем
            self._fire_event('vertex_added', {
                'element_id': self.element_id,
                'vertex_index': insert_index,
                'coords': self.contour_coords
            })
            
            self._redraw_all()
    
    def _delete_selected_vertices(self):
        """Удаление выбранных вершин"""
        if not self.editing_state.selected_elements:
            return
        
        # Проверяем, что не удаляем слишком много вершин
        if len(self.contour_coords) - len(self.editing_state.selected_elements) < 3:
            print("⚠️ Нельзя удалить вершины: контур должен содержать минимум 3 точки")
            return
        
        # Удаляем вершины (в обратном порядке индексов)
        sorted_indices = sorted(self.editing_state.selected_elements, reverse=True)
        for vertex_index in sorted_indices:
            if 0 <= vertex_index < len(self.contour_coords):
                del self.contour_coords[vertex_index]
        
        # Очищаем выбор
        self.editing_state.selected_elements.clear()
        
        # Сохраняем операцию
        self._save_operation()
        
        # Уведомляем
        self._fire_event('vertex_deleted', {
            'element_id': self.element_id,
            'coords': self.contour_coords
        })
        
        self._redraw_all()
    
    # === ПОИСК ЭЛЕМЕНТОВ ===
    
    def find_nearest_element(self, canvas_x: int, canvas_y: int, 
                           polygon: List[Tuple[float, float]]) -> Optional[Tuple[ElementType, int]]:
        """
        Поиск ближайшей вершины или ребра к точке на canvas
        
        Args:
            canvas_x, canvas_y: Координаты на canvas
            polygon: Координаты полигона в мировой системе
            
        Returns:
            Tuple (тип_элемента, индекс) или None
        """
        if not polygon or len(polygon) < 3:
            return None
        
        min_distance = float('inf')
        nearest_element = None
        
        # Поиск ближайшей вершины
        for i, (world_x, world_y) in enumerate(polygon):
            pixel_x, pixel_y = self._world_to_canvas(world_x, world_y)
            distance = math.sqrt((canvas_x - pixel_x) ** 2 + (canvas_y - pixel_y) ** 2)
            
            # Приоритет вершинам - больший радиус поиска
            vertex_tolerance = self.visual_settings['vertex_radius'] + 3
            if distance <= vertex_tolerance and distance < min_distance:
                min_distance = distance
                nearest_element = (ElementType.VERTEX, i)
        
        # Если вершина найдена, возвращаем её
        if nearest_element:
            return nearest_element
        
        # Поиск ближайшего ребра
        edge_tolerance = 5  # Пиксели
        for i in range(len(polygon)):
            j = (i + 1) % len(polygon)
            
            world_x1, world_y1 = polygon[i]
            world_x2, world_y2 = polygon[j]
            
            pixel_x1, pixel_y1 = self._world_to_canvas(world_x1, world_y1)
            pixel_x2, pixel_y2 = self._world_to_canvas(world_x2, world_y2)
            
            # Расстояние от точки до отрезка
            distance = self._point_to_line_distance(
                canvas_x, canvas_y, pixel_x1, pixel_y1, pixel_x2, pixel_y2
            )
            
            if distance <= edge_tolerance and distance < min_distance:
                min_distance = distance
                nearest_element = (ElementType.EDGE, i)
        
        return nearest_element
    
    def _point_to_line_distance(self, px: float, py: float, 
                              x1: float, y1: float, x2: float, y2: float) -> float:
        """Расстояние от точки до отрезка"""
        # Длина отрезка
        line_length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if line_length == 0:
            return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
        
        # Проекция точки на прямую
        t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / (line_length ** 2)
        
        # Ограничиваем проекцию отрезком
        t = max(0, min(1, t))
        
        # Ближайшая точка на отрезке
        closest_x = x1 + t * (x2 - x1)
        closest_y = y1 + t * (y2 - y1)
        
        # Расстояние
        return math.sqrt((px - closest_x) ** 2 + (py - closest_y) ** 2)
    
    # === ПРИВЯЗКИ ===
    
    def _snap_to_grid(self, world_x: float, world_y: float) -> Tuple[float, float]:
        """Привязка к сетке"""
        grid_size = self.editing_state.grid_size
        
        snapped_x = round(world_x / grid_size) * grid_size
        snapped_y = round(world_y / grid_size) * grid_size
        
        return (r2(snapped_x), r2(snapped_y))
    
    # === ОТРИСОВКА ===
    
    def _redraw_all(self):
        """Полная перерисовка всех элементов"""
        self._clear_all_objects()
        
        if not self.contour_coords:
            return
        
        # Отрисовываем контур
        self._draw_contour()
        
        # Отрисовываем ребра
        self._draw_edges()
        
        # Отрисовываем вершины
        self._draw_vertices()
        
        # Отрисовываем сетку (если включена)
        if self.editing_state.snap_to_grid:
            self._draw_grid()
    
    def _draw_contour(self):
        """Отрисовка контура"""
        if len(self.contour_coords) < 3:
            return
        
        canvas_coords = []
        for world_x, world_y in self.contour_coords:
            pixel_x, pixel_y = self._world_to_canvas(world_x, world_y)
            canvas_coords.extend([pixel_x, pixel_y])
        
        contour_obj = self.canvas.create_polygon(
            canvas_coords,
            fill='',
            outline=self.visual_settings['contour_color'],
            width=self.visual_settings['contour_width']
        )
        
        self.canvas_objects['contour'] = contour_obj
    
    def _draw_edges(self):
        """Отрисовка ребер"""
        self.canvas_objects['edges'] = []
        
        for i in range(len(self.contour_coords)):
            j = (i + 1) % len(self.contour_coords)
            
            world_x1, world_y1 = self.contour_coords[i]
            world_x2, world_y2 = self.contour_coords[j]
            
            pixel_x1, pixel_y1 = self._world_to_canvas(world_x1, world_y1)
            pixel_x2, pixel_y2 = self._world_to_canvas(world_x2, world_y2)
            
            # Определяем цвет ребра
            color = self.visual_settings['edge_color']
            if (self.editing_state.hover_element and 
                self.editing_state.hover_element[0] == ElementType.EDGE and 
                self.editing_state.hover_element[1] == i):
                color = self.visual_settings['edge_hover_color']
            
            edge_obj = self.canvas.create_line(
                pixel_x1, pixel_y1, pixel_x2, pixel_y2,
                fill=color,
                width=self.visual_settings['edge_width']
            )
            
            self.canvas_objects['edges'].append(edge_obj)
    
    def _draw_vertices(self):
        """Отрисовка вершин"""
        self.canvas_objects['vertices'] = []
        
        for i, (world_x, world_y) in enumerate(self.contour_coords):
            pixel_x, pixel_y = self._world_to_canvas(world_x, world_y)
            
            # Определяем цвет вершины
            color = self.visual_settings['vertex_color']
            if i in self.editing_state.selected_elements:
                color = self.visual_settings['vertex_selected_color']
            elif (self.editing_state.hover_element and 
                  self.editing_state.hover_element[0] == ElementType.VERTEX and 
                  self.editing_state.hover_element[1] == i):
                color = self.visual_settings['vertex_hover_color']
            
            radius = self.visual_settings['vertex_radius']
            vertex_obj = self.canvas.create_oval(
                pixel_x - radius, pixel_y - radius,
                pixel_x + radius, pixel_y + radius,
                fill=color,
                outline='white',
                width=1
            )
            
            self.canvas_objects['vertices'].append(vertex_obj)
    
    def _draw_grid(self):
        """Отрисовка сетки"""
        # Упрощенная реализация сетки
        # В реальной системе нужно учитывать viewport и масштаб
        pass
    
    def _clear_all_objects(self):
        """Очистка всех объектов с canvas"""
        for obj_list in self.canvas_objects.values():
            if isinstance(obj_list, list):
                for obj in obj_list:
                    self.canvas.delete(obj)
                obj_list.clear()
            elif obj_list:
                self.canvas.delete(obj_list)
                
        self.canvas_objects = {key: [] if isinstance(value, list) else None 
                             for key, value in self.canvas_objects.items()}
    
    def _update_cursor(self, element: Optional[Tuple[ElementType, int]]):
        """Обновление курсора в зависимости от элемента под мышью"""
        if not element:
            self.canvas.config(cursor="arrow")
        elif element[0] == ElementType.VERTEX:
            if self.editing_state.mode == EditingMode.MOVE_VERTEX:
                self.canvas.config(cursor="fleur")
            else:
                self.canvas.config(cursor="hand2")
        elif element[0] == ElementType.EDGE:
            self.canvas.config(cursor="crosshair")
    
    # === СИСТЕМА КООРДИНАТ ===
    
    def _world_to_canvas(self, world_x: float, world_y: float) -> Tuple[int, int]:
        """Конвертация мировых координат в пиксели canvas"""
        if self.coordinate_system:
            return self.coordinate_system.world_to_canvas(world_x, world_y)
        else:
            # Простая заглушка
            return (int(world_x * 50), int(world_y * 50))
    
    def _canvas_to_world(self, canvas_x: int, canvas_y: int) -> Tuple[float, float]:
        """Конвертация пикселей canvas в мировые координаты"""
        if self.coordinate_system:
            return self.coordinate_system.canvas_to_world(canvas_x, canvas_y)
        else:
            # Простая заглушка
            return (r2(canvas_x / 50), r2(canvas_y / 50))
    
    # === ОТМЕНА/ПОВТОР ===
    
    def _save_operation(self):
        """Сохранение операции для отмены"""
        # Удаляем операции после текущей позиции
        self.operation_history = self.operation_history[:self.current_operation_index + 1]
        
        # Добавляем новую операцию
        self.operation_history.append(deepcopy(self.contour_coords))
        self.current_operation_index += 1
        
        # Ограничиваем размер истории
        max_history = 50
        if len(self.operation_history) > max_history:
            self.operation_history = self.operation_history[-max_history:]
            self.current_operation_index = len(self.operation_history) - 1
    
    def undo(self) -> bool:
        """
        Отмена последней операции
        
        Returns:
            True если отмена выполнена
        """
        if self.current_operation_index <= 0:
            return False
        
        self.current_operation_index -= 1
        self.contour_coords = deepcopy(self.operation_history[self.current_operation_index])
        self.editing_state.selected_elements.clear()
        
        self._redraw_all()
        
        self._fire_event('contour_modified', {
            'element_id': self.element_id,
            'coords': self.contour_coords,
            'operation': 'undo'
        })
        
        return True
    
    def redo(self) -> bool:
        """
        Повтор отмененной операции
        
        Returns:
            True если повтор выполнен
        """
        if self.current_operation_index >= len(self.operation_history) - 1:
            return False
        
        self.current_operation_index += 1
        self.contour_coords = deepcopy(self.operation_history[self.current_operation_index])
        self.editing_state.selected_elements.clear()
        
        self._redraw_all()
        
        self._fire_event('contour_modified', {
            'element_id': self.element_id,
            'coords': self.contour_coords,
            'operation': 'redo'
        })
        
        return True
    
    # === СОБЫТИЯ ===
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """Добавление обработчика событий"""
        if event_type in self.event_handlers:
            self.event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable):
        """Удаление обработчика событий"""
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
            except ValueError:
                pass
    
    def _fire_event(self, event_type: str, event_data: Dict[str, Any]):
        """Генерация события"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    handler(event_data)
                except Exception as e:
                    print(f"Ошибка в обработчике события {event_type}: {e}")
    
    # === УТИЛИТЫ ===
    
    def validate_contour(self) -> Dict[str, Any]:
        """
        Валидация текущего контура
        
        Returns:
            Результат валидации
        """
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'area': 0.0,
            'perimeter': 0.0
        }
        
        if len(self.contour_coords) < 3:
            result['errors'].append("Контур должен содержать минимум 3 точки")
            result['is_valid'] = False
            return result
        
        # Расчет площади и периметра
        if GEOMETRY_UTILS_AVAILABLE:
            try:
                area = polygon_area(self.contour_coords)
                result['area'] = abs(area)
                
                if area < 0:
                    result['warnings'].append("Контур имеет неправильную ориентацию (по часовой стрелке)")
                
                if result['area'] < 0.1:
                    result['warnings'].append("Очень маленькая площадь контура")
                
                # Периметр
                perimeter = 0.0
                for i in range(len(self.contour_coords)):
                    j = (i + 1) % len(self.contour_coords)
                    dx = self.contour_coords[j][0] - self.contour_coords[i][0]
                    dy = self.contour_coords[j][1] - self.contour_coords[i][1]
                    perimeter += math.sqrt(dx * dx + dy * dy)
                
                result['perimeter'] = r2(perimeter)
                
            except Exception as e:
                result['errors'].append(f"Ошибка расчета геометрии: {e}")
                result['is_valid'] = False
        
        return result
    
    def get_editing_info(self) -> Dict[str, Any]:
        """Получение информации о текущем редактировании"""
        return {
            'element_id': self.element_id,
            'mode': self.editing_state.mode.value if self.editing_state.mode else None,
            'vertex_count': len(self.contour_coords),
            'selected_vertices': len(self.editing_state.selected_elements),
            'can_undo': self.current_operation_index > 0,
            'can_redo': self.current_operation_index < len(self.operation_history) - 1,
            'has_changes': self.contour_coords != self.original_coords
        }