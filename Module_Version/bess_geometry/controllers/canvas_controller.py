# -*- coding: utf-8 -*-
"""
CanvasController - контроллер для управления взаимодействием с графическим canvas

Этот компонент является "переводчиком" между пользователем и системой:
- Переводит действия пользователя (клики, движения мыши) в команды для бизнес-логики
- Управляет отображением геометрии на canvas через GeometryCanvas
- Обрабатывает все события взаимодействия с графическим интерфейсом
- Синхронизирует визуальное состояние с данными приложения

Ключевые принципы:
- Разделение ответственности: только обработка событий UI и управление отображением
- Делегирование бизнес-логики в MainController  
- Поддержка различных режимов взаимодействия
- Высокая производительность отрисовки
- Интуитивные паттерны взаимодействия
"""

import tkinter as tk
import math
from typing import Dict, List, Set, Optional, Tuple, Callable, Any
from enum import Enum

from ..ui.geometry_canvas import GeometryCanvas, CoordinateSystem
from ..core.geometry_operations import DrawingMode
from ..geometry_utils import centroid_xy, bounds, r2


class InteractionMode(Enum):
    """Режимы взаимодействия с canvas"""
    SELECTION = "selection"         # Выбор элементов
    NAVIGATION = "navigation"       # Навигация (панорамирование, масштабирование)
    DRAWING = "drawing"            # Рисование новых элементов
    EDITING = "editing"            # Редактирование существующих элементов
    MEASURING = "measuring"        # Измерение расстояний и площадей


class SelectionMode(Enum):
    """Режимы выбора элементов"""
    SINGLE = "single"              # Одиночный выбор
    MULTIPLE = "multiple"          # Множественный выбор
    RECTANGULAR = "rectangular"    # Прямоугольное выделение
    POLYGONAL = "polygonal"       # Полигональное выделение


class CanvasController:
    """
    Контроллер взаимодействия с canvas геометрии
    
    Этот класс служит "мозгом" пользовательского интерфейса - он понимает
    что хочет сделать пользователь и координирует это с остальной системой.
    """
    
    def __init__(self, parent_widget: tk.Widget, main_controller=None):
        """
        Инициализация контроллера canvas
        
        Args:
            parent_widget: Родительский Tkinter виджет для размещения canvas
            main_controller: Ссылка на главный контроллер (может быть установлена позже)
        """
        # Создаем canvas компонент
        self.geometry_canvas = GeometryCanvas(parent_widget)
        self.main_controller = main_controller
        
        # Текущие режимы взаимодействия
        self.interaction_mode = InteractionMode.SELECTION
        self.selection_mode = SelectionMode.SINGLE
        self.current_drawing_mode = DrawingMode.NONE
        
        # Состояние взаимодействия
        self.is_dragging = False
        self.drag_start_pos = None
        self.last_mouse_pos = (0, 0)
        self.selected_element_ids = set()
        
        # Навигация и масштабирование
        self.zoom_factor = 1.2
        self.min_scale = 0.01
        self.max_scale = 1000.0
        self.auto_fit_enabled = True
        
        # Прямоугольное выделение
        self.selection_rect = None
        self.selection_rect_canvas_id = None
        
        # Обработчики событий (будут установлены внешними компонентами)
        self.selection_handlers: List[Callable[[List[str]], None]] = []
        self.interaction_handlers: List[Callable[[Dict], None]] = []
        self.navigation_handlers: List[Callable[[Dict], None]] = []
        
        # Кэш для оптимизации
        self.visible_elements_cache = {}
        self.last_viewport = None
        
        self._setup_event_bindings()
    
    def set_main_controller(self, main_controller):
        """
        Установка ссылки на главный контроллер
        
        Args:
            main_controller: Экземпляр MainController
        """
        self.main_controller = main_controller
    
    def get_canvas_widget(self) -> tk.Canvas:
        """
        Получение Tkinter Canvas виджета для интеграции в GUI
        
        Returns:
            Tkinter Canvas объект
        """
        return self.geometry_canvas.canvas
    
    # === НАСТРОЙКА ОБРАБОТЧИКОВ СОБЫТИЙ ===
    
    def _setup_event_bindings(self):
        """Настройка привязки событий мыши и клавиатуры к canvas"""
        canvas = self.geometry_canvas.canvas
        
        # События мыши
        canvas.bind("<Button-1>", self._on_left_click)
        canvas.bind("<Double-Button-1>", self._on_double_click)
        canvas.bind("<Button-3>", self._on_right_click)
        canvas.bind("<B1-Motion>", self._on_drag)
        canvas.bind("<ButtonRelease-1>", self._on_release)
        
        # Масштабирование колесом мыши
        canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        canvas.bind("<Button-4>", self._on_mouse_wheel)  # Linux
        canvas.bind("<Button-5>", self._on_mouse_wheel)  # Linux
        
        # События клавиатуры
        canvas.bind("<Key>", self._on_key_press)
        canvas.focus_set()  # Включаем фокус для получения событий клавиатуры
        
        # События изменения размера
        canvas.bind("<Configure>", self._on_canvas_resize)
        
        # Движение мыши для отслеживания курсора
        canvas.bind("<Motion>", self._on_mouse_move)
    
    # === УПРАВЛЕНИЕ ОТОБРАЖЕНИЕМ ===
    
    def refresh_display(self, force_redraw: bool = False):
        """
        Обновление отображения всех элементов
        
        Args:
            force_redraw: Принудительная перерисовка без использования кэша
        """
        if not self.main_controller:
            return
        
        # Получаем элементы текущего уровня
        elements = self.main_controller.get_current_level_elements()
        
        # Очищаем canvas
        self.geometry_canvas.clear()
        
        # Получаем параметры видимого окна для оптимизации
        viewport = self._get_viewport_bounds()
        
        # Отрисовываем элементы
        self._render_elements(elements['rooms'], 'room', viewport)
        self._render_elements(elements['areas'], 'area', viewport) 
        self._render_elements(elements['openings'], 'opening', viewport)
        
        # Отображаем выделение
        self._update_selection_display()
        
        # Если включен режим рисования, показываем временную геометрию
        if self.current_drawing_mode != DrawingMode.NONE:
            self._render_drawing_state()
    
    def _render_elements(self, elements: List[Dict], element_type: str, viewport: Tuple[float, float, float, float]):
        """
        Отрисовка элементов определенного типа
        
        Args:
            elements: Список элементов для отрисовки
            element_type: Тип элементов ('room', 'area', 'opening')
            viewport: Границы видимого окна (min_x, min_y, max_x, max_y)
        """
        for element in elements:
            element_id = element.get('id')
            if not element_id:
                continue
                
            # Проверяем, попадает ли элемент в видимое окно (оптимизация)
            if not self._element_in_viewport(element, viewport):
                continue
            
            # Определяем стиль отрисовки
            is_selected = element_id in self.selected_element_ids
            style = self._get_element_style(element_type, is_selected)
            
            # Отрисовываем геометрию
            canvas_ids = self.geometry_canvas.renderer.draw_element(
                element, style
            )
            
            # Сохраняем связь между canvas ID и element ID
            for canvas_id in canvas_ids:
                self.geometry_canvas.element_mappings[canvas_id] = (element_id, element_type, style)
    
    def _get_element_style(self, element_type: str, is_selected: bool) -> Dict:
        """
        Определение стиля отрисовки для элемента
        
        Args:
            element_type: Тип элемента
            is_selected: Выбран ли элемент
            
        Returns:
            Словарь со стилевыми параметрами
        """
        # Базовые цвета для разных типов элементов
        base_styles = {
            'room': {'fill': '#4cc9f0', 'outline': '#333', 'width': 1},
            'area': {'fill': '#ff6b6b', 'outline': '#666', 'width': 1},
            'opening': {'fill': '#ffd93d', 'outline': '#333', 'width': 1}
        }
        
        style = base_styles.get(element_type, base_styles['room']).copy()
        
        # Модифицируем стиль для выбранных элементов
        if is_selected:
            style['outline'] = '#00ff00'
            style['width'] = 3
        
        return style
    
    def _element_in_viewport(self, element: Dict, viewport: Tuple[float, float, float, float]) -> bool:
        """
        Проверка, попадает ли элемент в видимое окно
        
        Args:
            element: Элемент для проверки
            viewport: Границы видимого окна
            
        Returns:
            True если элемент видим, False иначе
        """
        outer_points = element.get('outer_xy_m', [])
        if not outer_points:
            return False
        
        # Получаем границы элемента
        element_bounds = bounds(outer_points)
        if not element_bounds:
            return False
        
        min_x, min_y, max_x, max_y = element_bounds
        vp_min_x, vp_min_y, vp_max_x, vp_max_y = viewport
        
        # Проверяем пересечение прямоугольников
        return not (max_x < vp_min_x or min_x > vp_max_x or 
                   max_y < vp_min_y or min_y > vp_max_y)
    
    def _get_viewport_bounds(self) -> Tuple[float, float, float, float]:
        """
        Получение границ видимого окна в мировых координатах
        
        Returns:
            Кортеж (min_x, min_y, max_x, max_y)
        """
        canvas = self.geometry_canvas.canvas
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        
        coord_sys = self.geometry_canvas.coordinate_system
        
        # Углы видимого окна в мировых координатах
        min_world_x, max_world_y = coord_sys.screen_to_world(0, 0)
        max_world_x, min_world_y = coord_sys.screen_to_world(width, height)
        
        return (min_world_x, min_world_y, max_world_x, max_world_y)
    
    # === ОБРАБОТКА СОБЫТИЙ МЫШИ ===
    
    def _on_left_click(self, event):
        """Обработчик левого клика мыши"""
        self.last_mouse_pos = (event.x, event.y)
        world_x, world_y = self.geometry_canvas.coordinate_system.screen_to_world(event.x, event.y)
        
        if self.interaction_mode == InteractionMode.SELECTION:
            self._handle_selection_click(event.x, event.y, world_x, world_y)
            
        elif self.interaction_mode == InteractionMode.DRAWING:
            self._handle_drawing_click(world_x, world_y)
            
        elif self.interaction_mode == InteractionMode.NAVIGATION:
            self.drag_start_pos = (event.x, event.y)
            self.is_dragging = True
        
        # Уведомляем обработчики о взаимодействии
        self._fire_interaction_event({
            'type': 'click',
            'screen_x': event.x,
            'screen_y': event.y,
            'world_x': world_x,
            'world_y': world_y,
            'mode': self.interaction_mode
        })
    
    def _on_double_click(self, event):
        """Обработчик двойного клика"""
        world_x, world_y = self.geometry_canvas.coordinate_system.screen_to_world(event.x, event.y)
        
        if self.interaction_mode == InteractionMode.DRAWING:
            # Двойной клик завершает рисование
            self._fire_interaction_event({
                'type': 'double_click',
                'world_x': world_x,
                'world_y': world_y
            })
    
    def _on_right_click(self, event):
        """Обработчик правого клика (контекстное меню)"""
        world_x, world_y = self.geometry_canvas.coordinate_system.screen_to_world(event.x, event.y)
        
        # Находим элемент под курсором
        element_id = self._find_element_at_point(event.x, event.y)
        
        self._fire_interaction_event({
            'type': 'context_menu',
            'screen_x': event.x,
            'screen_y': event.y,
            'world_x': world_x,
            'world_y': world_y,
            'element_id': element_id
        })
    
    def _on_drag(self, event):
        """Обработчик перетаскивания мыши"""
        if not self.is_dragging or not self.drag_start_pos:
            return
        
        if self.interaction_mode == InteractionMode.NAVIGATION:
            # Панорамирование
            dx = event.x - self.drag_start_pos[0]
            dy = event.y - self.drag_start_pos[1]
            
            coord_sys = self.geometry_canvas.coordinate_system
            coord_sys.offset_x += dx
            coord_sys.offset_y += dy
            
            self.refresh_display()
            self.drag_start_pos = (event.x, event.y)
        
        elif self.interaction_mode == InteractionMode.SELECTION and self.selection_mode == SelectionMode.RECTANGULAR:
            # Прямоугольное выделение
            self._update_selection_rectangle(event.x, event.y)
    
    def _on_release(self, event):
        """Обработчик отпускания кнопки мыши"""
        if self.is_dragging:
            self.is_dragging = False
            
            if self.selection_mode == SelectionMode.RECTANGULAR and self.selection_rect:
                # Завершаем прямоугольное выделение
                self._complete_rectangular_selection()
        
        self.drag_start_pos = None
    
    def _on_mouse_wheel(self, event):
        """Обработчик колеса мыши (масштабирование)"""
        # Определяем направление прокрутки
        if event.delta > 0 or event.num == 4:
            scale_factor = self.zoom_factor
        else:
            scale_factor = 1.0 / self.zoom_factor
        
        # Масштабируем относительно позиции мыши
        self._zoom_at_point(event.x, event.y, scale_factor)
    
    def _on_mouse_move(self, event):
        """Обработчик движения мыши"""
        self.last_mouse_pos = (event.x, event.y)
        
        # Обновляем отображение координат курсора
        world_x, world_y = self.geometry_canvas.coordinate_system.screen_to_world(event.x, event.y)
        
        self._fire_interaction_event({
            'type': 'mouse_move',
            'screen_x': event.x,
            'screen_y': event.y,
            'world_x': world_x,
            'world_y': world_y
        })
    
    def _on_key_press(self, event):
        """Обработчик нажатий клавиш"""
        key = event.keysym.lower()
        
        if key == 'escape':
            # ESC отменяет текущую операцию
            if self.current_drawing_mode != DrawingMode.NONE:
                self.set_drawing_mode(DrawingMode.NONE)
            else:
                self.clear_selection()
        
        elif key == 'delete':
            # Delete удаляет выбранные элементы
            if self.main_controller and self.selected_element_ids:
                self.main_controller.delete_selected_elements()
        
        elif key == 'f':
            # F подгоняет все элементы в окно
            self.fit_all_elements()
        
        elif event.state & 0x4 and key == 'z':  # Ctrl+Z
            # Отмена последней операции
            if self.main_controller:
                self.main_controller.undo()
        
        elif event.state & 0x4 and key == 'y':  # Ctrl+Y
            # Повтор операции
            if self.main_controller:
                self.main_controller.redo()
    
    def _on_canvas_resize(self, event):
        """Обработчик изменения размера canvas"""
        if self.auto_fit_enabled and not self.geometry_canvas.element_mappings:
            # Если это первая отрисовка, подгоняем масштаб
            self.fit_all_elements()
    
    # === УПРАВЛЕНИЕ ВЫДЕЛЕНИЕМ ===
    
    def _handle_selection_click(self, screen_x: int, screen_y: int, world_x: float, world_y: float):
        """
        Обработка клика для выбора элементов
        
        Args:
            screen_x, screen_y: Экранные координаты клика
            world_x, world_y: Мировые координаты клика
        """
        element_id = self._find_element_at_point(screen_x, screen_y)
        
        if element_id:
            # Клик по элементу
            if self.selection_mode == SelectionMode.MULTIPLE:
                # Множественный выбор - добавляем/убираем элемент
                if element_id in self.selected_element_ids:
                    self.selected_element_ids.remove(element_id)
                else:
                    self.selected_element_ids.add(element_id)
            else:
                # Одиночный выбор - заменяем выбор
                self.selected_element_ids = {element_id}
        else:
            # Клик по пустому месту
            if self.selection_mode != SelectionMode.RECTANGULAR:
                # Очищаем выбор если это не начало прямоугольного выделения
                self.selected_element_ids.clear()
            else:
                # Начинаем прямоугольное выделение
                self._start_rectangular_selection(screen_x, screen_y)
        
        # Обновляем отображение выбора
        self._update_selection_display()
        
        # Уведомляем обработчики о изменении выбора
        self._fire_selection_event(list(self.selected_element_ids))
    
    def _find_element_at_point(self, screen_x: int, screen_y: int) -> Optional[str]:
        """
        Поиск элемента в указанной точке экрана
        
        Args:
            screen_x, screen_y: Координаты точки на экране
            
        Returns:
            ID найденного элемента или None
        """
        canvas = self.geometry_canvas.canvas
        canvas_item = canvas.find_closest(screen_x, screen_y)[0]
        
        # Проверяем, есть ли элемент в маппинге
        if canvas_item in self.geometry_canvas.element_mappings:
            element_id, element_type, style = self.geometry_canvas.element_mappings[canvas_item]
            return element_id
        
        return None
    
    def _start_rectangular_selection(self, start_x: int, start_y: int):
        """
        Начало прямоугольного выделения
        
        Args:
            start_x, start_y: Начальные координаты
        """
        self.selection_rect = [start_x, start_y, start_x, start_y]
        self.drag_start_pos = (start_x, start_y)
        self.is_dragging = True
    
    def _update_selection_rectangle(self, current_x: int, current_y: int):
        """
        Обновление прямоугольника выделения
        
        Args:
            current_x, current_y: Текущие координаты мыши
        """
        if not self.selection_rect or not self.drag_start_pos:
            return
        
        # Обновляем координаты прямоугольника
        start_x, start_y = self.drag_start_pos
        self.selection_rect = [
            min(start_x, current_x), min(start_y, current_y),
            max(start_x, current_x), max(start_y, current_y)
        ]
        
        # Перерисовываем прямоугольник выделения
        canvas = self.geometry_canvas.canvas
        
        if self.selection_rect_canvas_id:
            canvas.delete(self.selection_rect_canvas_id)
        
        self.selection_rect_canvas_id = canvas.create_rectangle(
            self.selection_rect[0], self.selection_rect[1],
            self.selection_rect[2], self.selection_rect[3],
            outline='#0080ff', fill='', width=1, dash=(5, 5)
        )
    
    def _complete_rectangular_selection(self):
        """Завершение прямоугольного выделения"""
        if not self.selection_rect:
            return
        
        # Преобразуем прямоугольник в мировые координаты
        coord_sys = self.geometry_canvas.coordinate_system
        min_x, min_y = coord_sys.screen_to_world(self.selection_rect[0], self.selection_rect[3])
        max_x, max_y = coord_sys.screen_to_world(self.selection_rect[2], self.selection_rect[1])
        
        # Находим все элементы, попадающие в прямоугольник
        selected_ids = self._find_elements_in_rectangle(min_x, min_y, max_x, max_y)
        
        # Обновляем выбор
        self.selected_element_ids.update(selected_ids)
        self._update_selection_display()
        
        # Убираем прямоугольник выделения
        if self.selection_rect_canvas_id:
            self.geometry_canvas.canvas.delete(self.selection_rect_canvas_id)
            self.selection_rect_canvas_id = None
        
        self.selection_rect = None
        
        # Уведомляем о изменении выбора
        self._fire_selection_event(list(self.selected_element_ids))
    
    def _find_elements_in_rectangle(self, min_x: float, min_y: float, max_x: float, max_y: float) -> Set[str]:
        """
        Поиск элементов, попадающих в указанный прямоугольник
        
        Args:
            min_x, min_y, max_x, max_y: Границы прямоугольника в мировых координатах
            
        Returns:
            Множество ID найденных элементов
        """
        selected_ids = set()
        
        if not self.main_controller:
            return selected_ids
        
        elements = self.main_controller.get_current_level_elements()
        
        # Проверяем каждый тип элементов
        for element_list in [elements['rooms'], elements['areas'], elements['openings']]:
            for element in element_list:
                element_id = element.get('id')
                outer_points = element.get('outer_xy_m', [])
                
                if not element_id or not outer_points:
                    continue
                
                # Проверяем, попадает ли элемент в прямоугольник
                element_bounds = bounds(outer_points)
                if element_bounds:
                    e_min_x, e_min_y, e_max_x, e_max_y = element_bounds
                    
                    # Проверяем пересечение с прямоугольником выделения
                    if (e_max_x >= min_x and e_min_x <= max_x and 
                        e_max_y >= min_y and e_min_y <= max_y):
                        selected_ids.add(element_id)
        
        return selected_ids
    
    def _update_selection_display(self):
        """Обновление визуального отображения выбранных элементов"""
        # Этот метод будет вызывать перерисовку только выбранных элементов
        # для оптимизации производительности
        self.refresh_display()
    
    def clear_selection(self):
        """Очистка выбора элементов"""
        self.selected_element_ids.clear()
        self._update_selection_display()
        self._fire_selection_event([])
    
    # === НАВИГАЦИЯ И МАСШТАБИРОВАНИЕ ===
    
    def _zoom_at_point(self, screen_x: int, screen_y: int, scale_factor: float):
        """
        Масштабирование относительно указанной точки
        
        Args:
            screen_x, screen_y: Точка масштабирования на экране
            scale_factor: Коэффициент масштабирования
        """
        coord_sys = self.geometry_canvas.coordinate_system
        
        # Проверяем ограничения масштаба
        new_scale = coord_sys.scale * scale_factor
        if new_scale < self.min_scale or new_scale > self.max_scale:
            return
        
        # Получаем мировые координаты точки масштабирования
        world_x, world_y = coord_sys.screen_to_world(screen_x, screen_y)
        
        # Применяем масштабирование
        coord_sys.scale = new_scale
        
        # Корректируем смещение чтобы точка масштабирования осталась на месте
        new_screen_x, new_screen_y = coord_sys.world_to_screen(world_x, world_y)
        coord_sys.offset_x += screen_x - new_screen_x
        coord_sys.offset_y += screen_y - new_screen_y
        
        # Обновляем отображение
        self.refresh_display()
        
        # Уведомляем о навигации
        self._fire_navigation_event({
            'type': 'zoom',
            'scale': coord_sys.scale,
            'center_x': world_x,
            'center_y': world_y
        })
    
    def fit_all_elements(self):
        """Подгонка масштаба для отображения всех элементов"""
        if not self.main_controller:
            return
        
        elements = self.main_controller.get_current_level_elements()
        all_points = []
        
        # Собираем все точки элементов
        for element_list in [elements['rooms'], elements['areas'], elements['openings']]:
            for element in element_list:
                outer_points = element.get('outer_xy_m', [])
                all_points.extend(outer_points)
        
        if not all_points:
            return
        
        # Вычисляем общие границы
        total_bounds = bounds(all_points)
        if not total_bounds:
            return
        
        min_x, min_y, max_x, max_y = total_bounds
        
        # Получаем размеры canvas
        canvas = self.geometry_canvas.canvas
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return
        
        # Вычисляем масштаб с отступами
        margin = 50  # отступ в пикселях
        width_scale = (canvas_width - 2 * margin) / (max_x - min_x)
        height_scale = (canvas_height - 2 * margin) / (max_y - min_y)
        
        coord_sys = self.geometry_canvas.coordinate_system
        coord_sys.scale = min(width_scale, height_scale)
        
        # Центрируем изображение
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        coord_sys.offset_x = canvas_width / 2 - center_x * coord_sys.scale
        coord_sys.offset_y = canvas_height / 2 + center_y * coord_sys.scale
        
        # Обновляем отображение
        self.refresh_display()
        
        # Уведомляем о навигации
        self._fire_navigation_event({
            'type': 'fit_all',
            'bounds': total_bounds,
            'scale': coord_sys.scale
        })
    
    def pan_to_element(self, element_id: str):
        """
        Панорамирование к указанному элементу
        
        Args:
            element_id: ID элемента
        """
        if not self.main_controller:
            return
        
        elements = self.main_controller.get_current_level_elements()
        target_element = None
        
        # Ищем элемент
        for element_list in [elements['rooms'], elements['areas'], elements['openings']]:
            for element in element_list:
                if element.get('id') == element_id:
                    target_element = element
                    break
            if target_element:
                break
        
        if not target_element:
            return
        
        # Получаем центр элемента
        outer_points = target_element.get('outer_xy_m', [])
        if not outer_points:
            return
        
        center = centroid_xy(outer_points)
        if not center:
            return
        
        # Панорамируем к центру элемента
        canvas = self.geometry_canvas.canvas
        canvas_center_x = canvas.winfo_width() / 2
        canvas_center_y = canvas.winfo_height() / 2
        
        coord_sys = self.geometry_canvas.coordinate_system
        screen_x, screen_y = coord_sys.world_to_screen(center[0], center[1])
        
        coord_sys.offset_x += canvas_center_x - screen_x
        coord_sys.offset_y += canvas_center_y - screen_y
        
        # Обновляем отображение
        self.refresh_display()
    
    # === УПРАВЛЕНИЕ РЕЖИМАМИ ===
    
    def set_interaction_mode(self, mode: InteractionMode):
        """
        Установка режима взаимодействия
        
        Args:
            mode: Новый режим взаимодействия
        """
        old_mode = self.interaction_mode
        self.interaction_mode = mode
        
        # Сбрасываем состояние при смене режима
        self.is_dragging = False
        self.drag_start_pos = None
        
        # Очищаем временные визуальные элементы
        if self.selection_rect_canvas_id:
            self.geometry_canvas.canvas.delete(self.selection_rect_canvas_id)
            self.selection_rect_canvas_id = None
        
        self.selection_rect = None
        
        self._fire_interaction_event({
            'type': 'mode_changed',
            'old_mode': old_mode,
            'new_mode': mode
        })
    
    def set_selection_mode(self, mode: SelectionMode):
        """
        Установка режима выбора элементов
        
        Args:
            mode: Новый режим выбора
        """
        self.selection_mode = mode
    
    def set_drawing_mode(self, mode: DrawingMode):
        """
        Установка режима рисования
        
        Args:
            mode: Новый режим рисования
        """
        self.current_drawing_mode = mode
        
        # Автоматически переключаем режим взаимодействия
        if mode == DrawingMode.NONE:
            self.set_interaction_mode(InteractionMode.SELECTION)
        else:
            self.set_interaction_mode(InteractionMode.DRAWING)
    
    # === РЕЖИМ РИСОВАНИЯ ===
    
    def _handle_drawing_click(self, world_x: float, world_y: float):
        """
        Обработка клика в режиме рисования
        
        Args:
            world_x, world_y: Мировые координаты клика
        """
        if not self.main_controller:
            return
        
        if self.current_drawing_mode == DrawingMode.ADD_ROOM:
            self.main_controller.create_room_at_point(world_x, world_y)
    
    def _render_drawing_state(self):
        """Отрисовка временного состояния рисования"""
        if not self.main_controller:
            return
        
        # Получаем текущее состояние рисования от GeometryOperations
        drawing_state = self.main_controller.get_geometry_operations().get_current_drawing_state()
        
        if drawing_state and drawing_state.get('points'):
            # Отрисовываем временные линии/полигон
            self.geometry_canvas.renderer.draw_temporary_geometry(
                drawing_state['points'],
                drawing_state.get('closed', False)
            )
    
    # === ОБРАБОТЧИКИ СОБЫТИЙ ===
    
    def set_selection_handler(self, handler: Callable[[List[str]], None]):
        """Установка обработчика изменения выбора"""
        self.selection_handlers.append(handler)
    
    def set_interaction_handler(self, handler: Callable[[Dict], None]):
        """Установка обработчика взаимодействия"""
        self.interaction_handlers.append(handler)
    
    def set_navigation_handler(self, handler: Callable[[Dict], None]):
        """Установка обработчика навигации"""
        self.navigation_handlers.append(handler)
    
    def _fire_selection_event(self, selected_ids: List[str]):
        """Вызов обработчиков изменения выбора"""
        for handler in self.selection_handlers:
            try:
                handler(selected_ids)
            except Exception as e:
                print(f"Ошибка в обработчике выбора: {e}")
    
    def _fire_interaction_event(self, data: Dict):
        """Вызов обработчиков взаимодействия"""
        for handler in self.interaction_handlers:
            try:
                handler(data)
            except Exception as e:
                print(f"Ошибка в обработчике взаимодействия: {e}")
    
    def _fire_navigation_event(self, data: Dict):
        """Вызов обработчиков навигации"""
        for handler in self.navigation_handlers:
            try:
                handler(data)
            except Exception in e:
                print(f"Ошибка в обработчике навигации: {e}")
    
    # === ПУБЛИЧНЫЙ ИНТЕРФЕЙС ===
    
    def get_selected_elements(self) -> List[str]:
        """Получение списка выбранных элементов"""
        return list(self.selected_element_ids)
    
    def select_elements(self, element_ids: List[str], append: bool = False):
        """
        Программный выбор элементов
        
        Args:
            element_ids: Список ID элементов для выбора
            append: Добавить к текущему выбору (True) или заменить (False)
        """
        if not append:
            self.selected_element_ids.clear()
        
        self.selected_element_ids.update(element_ids)
        self._update_selection_display()
        self._fire_selection_event(list(self.selected_element_ids))
    
    def get_current_scale(self) -> float:
        """Получение текущего масштаба отображения"""
        return self.geometry_canvas.coordinate_system.scale
    
    def get_viewport_center(self) -> Tuple[float, float]:
        """
        Получение центра видимого окна в мировых координатах
        
        Returns:
            Кортеж (center_x, center_y)
        """
        canvas = self.geometry_canvas.canvas
        center_x = canvas.winfo_width() / 2
        center_y = canvas.winfo_height() / 2
        
        return self.geometry_canvas.coordinate_system.screen_to_world(center_x, center_y)