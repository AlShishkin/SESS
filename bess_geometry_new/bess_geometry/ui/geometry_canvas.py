# -*- coding: utf-8 -*-
"""
ui/geometry_canvas.py - Геометрический canvas (ЭТАП 1 - исправлен)

ИСПРАВЛЕНИЯ:
✅ Исправлены относительные импорты на прямые
✅ Добавлены fallback для отсутствующих модулей  
✅ Улучшена обработка ошибок
✅ Сохранена полная функциональность render_bess_data()
"""

import tkinter as tk
import math
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum

# ============================================================================
# ЦВЕТОВАЯ ПАЛИТРА ИЗ LEGACY (ЭТАП 1)
# ============================================================================

# Палитра помещений - портирована из legacy app.py line ~680
ROOM_PALETTE = (
    "#4cc9f0",  # Голубой
    "#3f37c9",  # Синий  
    "#4895ef",  # Светло-синий
    "#43aa8b",  # Зеленый
    "#90be6d",  # Светло-зеленый
    "#577590",  # Серо-синий
    "#f8961e",  # Оранжевый
    "#264653",  # Темно-зеленый
    "#2a9d8f"   # Темно-циан
)

# Дополнительные цвета для других типов элементов
AREA_COLOR = "#ff6b6b"      # Красный для областей
OPENING_COLOR = "#ffd93d"   # Желтый для отверстий  
SHAFT_COLOR = "#d3d3d3"     # Серый для шахт
SELECTED_COLOR = "#00ff00"  # Зеленый для выделения

# Цветовая схема для различных типов архитектурных элементов
ELEMENT_COLORS = {
    'room': {
        'fill': '#87CEEB',      # Базовый цвет (будет заменен на ROOM_PALETTE)
        'outline': '#4682B4',   
        'selected': '#00FF00',  
        'hover': '#B0E0E6',     
        'text': '#000080'       
    },
    'area': {
        'fill': AREA_COLOR,     
        'outline': '#DC143C',   
        'selected': '#00FF00',  
        'hover': '#FFC0CB',     
        'text': '#8B0000'       
    },
    'opening': {
        'fill': OPENING_COLOR,      
        'outline': '#FFD700',   
        'selected': '#00FF00',  
        'hover': '#FFFACD',     
        'text': '#B8860B'       
    },
    'shaft': {
        'fill': SHAFT_COLOR,      
        'outline': '#696969',   
        'selected': '#00FF00',  
        'hover': '#DCDCDC',     
        'text': '#2F4F4F'       
    },
    'drawing': {
        'outline': '#FF0000',   
        'fill': 'transparent', 
        'width': 2,
        'dash': (5, 3)          
    },
    'grid': {
        'major': '#E0E0E0',     
        'minor': '#F0F0F0',     
        'width': 1
    },
    'selection': {
        'outline': '#00FF00',   
        'width': 3,
        'dash': None
    }
}

# Проверяем доступность геометрических утилит (ИСПРАВЛЕНО: прямой импорт)
try:
    import geometry_utils
    from geometry_utils import bounds, centroid_xy, r2
    GEOMETRY_UTILS_AVAILABLE = True
    print("✅ Геометрические утилиты импортированы в GeometryCanvas")
except ImportError as e:
    print(f"⚠️ Геометрические утилиты недоступны в GeometryCanvas: {e}")
    GEOMETRY_UTILS_AVAILABLE = False
    
    # Создаем простые заглушки
    def bounds(points):
        """Простая реализация bounds"""
        if not points:
            return None
        xs = [p[0] for p in points if len(p) >= 2]
        ys = [p[1] for p in points if len(p) >= 2]
        if not xs or not ys:
            return None
        return (min(xs), min(ys), max(xs), max(ys))
    
    def centroid_xy(points):
        """Простая реализация centroid_xy"""
        if not points:
            return (0.0, 0.0)
        xs = [p[0] for p in points if len(p) >= 2]
        ys = [p[1] for p in points if len(p) >= 2]
        if not xs or not ys:
            return (0.0, 0.0)
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    
    def r2(x):
        """Простая реализация r2"""
        try:
            return round(float(x), 2)
        except (TypeError, ValueError):
            return 0.0

# Проверяем доступность системы производительности (ИСПРАВЛЕНО: прямой импорт)
try:
    import performance
    from performance import PerformanceMonitor
    PERFORMANCE_AVAILABLE = True
    print("✅ Система мониторинга производительности импортирована в GeometryCanvas")
except ImportError as e:
    print(f"⚠️ Система производительности недоступна в GeometryCanvas: {e}")
    PERFORMANCE_AVAILABLE = False
    
    # Создаем заглушку для монитора производительности
    class PerformanceMonitor:
        def __init__(self): 
            self.stats = {'fps': 30, 'frame_time': 33.3}
        def start_frame(self): 
            pass
        def end_frame(self): 
            pass
        def get_stats(self): 
            return self.stats


# ============================================================================
# COORDINATE SYSTEM (с портированными методами из legacy)
# ============================================================================

class CoordinateSystem:
    """
    Система координат с портированными методами _to_screen/_from_screen из legacy
    
    ЭТАП 1: Точная копия legacy координатных преобразований
    """
    
    def __init__(self, initial_scale: float = 50.0):
        """
        Инициализация с начальным масштабом как в legacy
        
        Args:
            initial_scale: Начальный масштаб (пикселей на метр) - как в legacy
        """
        # Параметры трансформации координат (как в legacy)
        self.scale = initial_scale      # Как _scale в legacy
        self.offset_x = 0.0            # Как _ox в legacy
        self.offset_y = 0.0            # Как _oy в legacy
        
        # Ограничения для предотвращения некорректных состояний
        self.min_scale = 0.1
        self.max_scale = 1000.0
        
        # Кэш для оптимизации производительности
        self._cached_transforms = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def world_to_screen(self, x: float, y: float) -> Tuple[float, float]:
        """
        Преобразование мировых координат в экранные
        Порт legacy _to_screen(self, x, y)
        
        Args:
            x, y: Координаты в реальном мире (метры)
            
        Returns:
            Координаты на экране (пиксели)
        """
        # Точная копия legacy _to_screen
        screen_x = x * self.scale + self.offset_x
        screen_y = -y * self.scale + self.offset_y  # Инверсия Y как в legacy
        return (screen_x, screen_y)
    
    def screen_to_world(self, X: float, Y: float) -> Tuple[float, float]:
        """
        Преобразование экранных координат в мировые
        Порт legacy _from_screen(self, X, Y)
        
        Args:
            X, Y: Координаты на экране (пиксели)
            
        Returns:
            Координаты в реальном мире (метры)
        """
        # Точная копия legacy _from_screen
        world_x = (X - self.offset_x) / self.scale
        world_y = -(Y - self.offset_y) / self.scale  # Инверсия Y как в legacy
        return (world_x, world_y)
    
    def zoom_at_point(self, screen_x: float, screen_y: float, factor: float) -> None:
        """
        Масштабирование в точке
        Порт legacy _zoom_at(self, X, Y, factor)
        
        Args:
            screen_x, screen_y: Точка на экране для масштабирования
            factor: Коэффициент масштабирования
        """
        # Запоминаем мировую точку под курсором
        world_x, world_y = self.screen_to_world(screen_x, screen_y)
        
        # Изменяем масштаб с ограничениями
        new_scale = self.scale * factor
        new_scale = max(self.min_scale, min(new_scale, self.max_scale))
        self.scale = new_scale
        
        # Корректируем смещение чтобы точка под курсором осталась на месте
        new_screen_x, new_screen_y = self.world_to_screen(world_x, world_y)
        self.offset_x += screen_x - new_screen_x
        self.offset_y += screen_y - new_screen_y
    
    def pan(self, delta_x: float, delta_y: float) -> None:
        """
        Панорамирование на указанное смещение в пикселях
        
        Args:
            delta_x, delta_y: Смещение в пикселях
        """
        self.offset_x += delta_x
        self.offset_y += delta_y
    
    def fit_to_bounds(self, min_x: float, min_y: float, max_x: float, max_y: float,
                     canvas_width: int, canvas_height: int, margin: float = 0.1) -> None:
        """
        Подгонка системы координат под указанные границы
        
        Args:
            min_x, min_y, max_x, max_y: Границы в мировых координатах
            canvas_width, canvas_height: Размеры canvas в пикселях
            margin: Отступ в долях от размера (0.1 = 10%)
        """
        # Вычисляем размеры области
        world_width = max_x - min_x
        world_height = max_y - min_y
        
        if world_width <= 0 or world_height <= 0:
            return
        
        # Вычисляем масштаб с учетом отступов
        margin_pixels_x = canvas_width * margin
        margin_pixels_y = canvas_height * margin
        
        usable_width = canvas_width - 2 * margin_pixels_x
        usable_height = canvas_height - 2 * margin_pixels_y
        
        scale_x = usable_width / world_width
        scale_y = usable_height / world_height
        
        # Используем меньший масштаб для полного помещения
        new_scale = min(scale_x, scale_y)
        new_scale = max(self.min_scale, min(new_scale, self.max_scale))
        
        self.scale = new_scale
        
        # Центрируем изображение
        center_world_x = (min_x + max_x) / 2
        center_world_y = (min_y + max_y) / 2
        
        self.offset_x = canvas_width / 2 - center_world_x * self.scale
        self.offset_y = canvas_height / 2 + center_world_y * self.scale  # + из-за инверсии Y
    
    def get_visible_world_bounds(self, canvas_width: int, canvas_height: int) -> Tuple[float, float, float, float]:
        """
        Получение границ видимой области в мировых координатах
        
        Returns:
            (min_x, min_y, max_x, max_y) в мировых координатах
        """
        top_left = self.screen_to_world(0, 0)
        bottom_right = self.screen_to_world(canvas_width, canvas_height)
        
        return (
            min(top_left[0], bottom_right[0]),
            min(top_left[1], bottom_right[1]),
            max(top_left[0], bottom_right[0]),
            max(top_left[1], bottom_right[1])
        )


# ============================================================================
# GEOMETRY RENDERER (с портированным render_bess_data)
# ============================================================================

class GeometryRenderer:
    """
    Рендерер геометрии с портированной логикой из legacy
    
    ЭТАП 1: Основной метод render_bess_data() - это порт legacy _redraw() метода
    """
    
    def __init__(self, canvas: tk.Canvas, coordinate_system: CoordinateSystem):
        """
        Инициализация рендерера
        
        Args:
            canvas: Tkinter Canvas для отрисовки
            coordinate_system: Система координат для преобразований
        """
        self.canvas = canvas
        self.coords = coordinate_system
        
        # Кэш для оптимизации повторной отрисовки
        self.render_cache = {}
        self.cache_version = 0
        
        # Статистика производительности
        self.render_stats = {
            'elements_drawn': 0,
            'elements_culled': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'last_render_time': 0.0
        }
        
        # Настройки отображения
        self.show_names = True
        self.show_grid = False
        
        # Настройки уровня детализации
        self.lod_settings = {
            'min_pixel_size': 2.0,      # Минимальный размер элемента в пикселях
            'simplify_threshold': 0.5,  # Порог упрощения геометрии
            'text_scale_threshold': 10.0 # Минимальный масштаб для отображения текста
        }
    
    def render_bess_data(self, app_state, current_level: str, force_fit: bool = False) -> None:
        """
        Основной метод отрисовки данных BESS
        Порт legacy _redraw() метода с полной функциональностью
        
        ЭТАП 1: Полная реализация с цветовой палитрой ROOM_PALETTE
        
        Args:
            app_state: Объект AppState из legacy/state.py
            current_level: Название текущего уровня
            force_fit: Нужно ли автоматически масштабировать (при первой загрузке)
        """
        print(f"🎨 Начинаем отрисовку уровня '{current_level}' (fit={force_fit})")
        start_time = time.time()
        
        try:
            # 1. Получение данных текущего уровня (портирование из legacy)
            level = current_level
            rooms = [r for r in app_state.work_rooms 
                    if (r.get("params", {}).get("BESS_level", "") == level)]
            areas = [a for a in app_state.work_areas 
                    if (a.get("params", {}).get("BESS_level", "") == level)]
            openings = [o for o in app_state.work_openings 
                       if (o.get("params", {}).get("BESS_level", "") == level)]
            shafts = []
            if hasattr(app_state, 'work_shafts') and level in app_state.work_shafts:
                shafts = app_state.work_shafts[level]
            
            print(f"📊 Элементы уровня: {len(rooms)} помещений, {len(areas)} областей, {len(openings)} отверстий, {len(shafts)} шахт")
            
            # 2. Автоматическое масштабирование при первой загрузке (порт legacy auto-fit)
            if force_fit and (rooms or areas or openings or shafts):
                self._auto_fit_to_elements(rooms + areas + openings + shafts)
            
            # 3. Очистка canvas и данных отображения (порт legacy clear logic)
            self.canvas.delete("all")
            self.render_cache.clear()
            
            # 4. Отрисовка сетки (если включена)
            if self.show_grid:
                self._draw_grid()
            
            # 5. Отрисовка помещений с цветовой палитрой (порт legacy room rendering)
            self._render_rooms(rooms)
            
            # 6. Отрисовка областей (контуры) (порт legacy area rendering)
            self._render_areas(areas)
            
            # 7. Отрисовка отверстий (порт legacy opening rendering)
            self._render_openings(openings)
            
            # 8. Отрисовка шахт (порт legacy shaft rendering)
            self._render_shafts(shafts)
            
            # 9. Отрисовка названий элементов (порт legacy labels)
            if self.show_names:
                self._render_labels(rooms + areas + openings + shafts)
            
            # 10. Восстановление выделения будет добавлено в следующих этапах
            
            # Обновляем статистику
            render_time = (time.time() - start_time) * 1000
            self.render_stats['last_render_time'] = render_time
            self.render_stats['elements_drawn'] = len(rooms) + len(areas) + len(openings) + len(shafts)
            
            print(f"✅ Отрисовка завершена за {render_time:.1f} мс")
            
        except Exception as e:
            print(f"❌ Ошибка отрисовки BESS данных: {e}")
            import traceback
            traceback.print_exc()
    
    def _auto_fit_to_elements(self, elements: List[Dict]) -> None:
        """
        Автоматическое масштабирование для отображения всех элементов
        Порт legacy auto-fit логики
        """
        if not elements:
            return
        
        try:
            # Собираем все точки всех элементов
            all_points = []
            for element in elements:
                outer_points = element.get('outer_xy_m', [])
                all_points.extend(outer_points)
                
                # Добавляем точки внутренних контуров
                inner_loops = element.get('inner_loops_xy_m', [])
                for loop in inner_loops:
                    all_points.extend(loop)
            
            if not all_points:
                return
            
            # Находим общие границы
            element_bounds = bounds(all_points)
            if not element_bounds:
                return
            
            minx, miny, maxx, maxy = element_bounds
            
            # Получаем размеры canvas
            canvas_width = max(self.canvas.winfo_width(), 100)
            canvas_height = max(self.canvas.winfo_height(), 100)
            
            # Подгоняем координатную систему
            self.coords.fit_to_bounds(minx, miny, maxx, maxy, canvas_width, canvas_height, margin=0.1)
            
            print(f"🔍 Auto-fit: масштаб={self.coords.scale:.1f}, область=({minx:.1f}, {miny:.1f}) - ({maxx:.1f}, {maxy:.1f})")
            
        except Exception as e:
            print(f"❌ Ошибка auto-fit: {e}")
    
    def _render_rooms(self, rooms: List[Dict]) -> None:
        """
        Отрисовка помещений с цветовой палитрой
        Порт legacy room rendering с ROOM_PALETTE
        """
        for i, room in enumerate(rooms):
            try:
                # Используем цикличную палитру (порт legacy palette logic)
                color = ROOM_PALETTE[i % len(ROOM_PALETTE)]
                
                # Отрисовываем полигон помещения
                canvas_ids = self._draw_polygon(
                    room.get('outer_xy_m', []),
                    fill_color=color,
                    outline_color="#333333",
                    outline_width=1
                )
                
                # Отрисовываем внутренние контуры (отверстия в помещении)
                inner_loops = room.get('inner_loops_xy_m', [])
                for loop in inner_loops:
                    self._draw_polygon(
                        loop,
                        fill_color="white",  # Вырезаем отверстие
                        outline_color="#666666",
                        outline_width=1
                    )
                
            except Exception as e:
                print(f"⚠️ Ошибка отрисовки помещения {room.get('id', 'unknown')}: {e}")
    
    def _render_areas(self, areas: List[Dict]) -> None:
        """
        Отрисовка областей (контуры)
        Порт legacy area rendering
        """
        for area in areas:
            try:
                # Области рисуем только контуром (без заливки)
                self._draw_polygon(
                    area.get('outer_xy_m', []),
                    fill_color=None,  # Без заливки
                    outline_color=AREA_COLOR,
                    outline_width=2
                )
                
            except Exception as e:
                print(f"⚠️ Ошибка отрисовки области {area.get('id', 'unknown')}: {e}")
    
    def _render_openings(self, openings: List[Dict]) -> None:
        """
        Отрисовка отверстий
        Порт legacy opening rendering
        """
        for opening in openings:
            try:
                self._draw_polygon(
                    opening.get('outer_xy_m', []),
                    fill_color=OPENING_COLOR,
                    outline_color="#333333",
                    outline_width=1
                )
                
            except Exception as e:
                print(f"⚠️ Ошибка отрисовки отверстия {opening.get('id', 'unknown')}: {e}")
    
    def _render_shafts(self, shafts: List[Dict]) -> None:
        """
        Отрисовка шахт
        Порт legacy shaft rendering
        """
        for shaft in shafts:
            try:
                self._draw_polygon(
                    shaft.get('outer_xy_m', []),
                    fill_color=SHAFT_COLOR,
                    outline_color="#666666",
                    outline_width=1
                )
                
            except Exception as e:
                print(f"⚠️ Ошибка отрисовки шахты {shaft.get('id', 'unknown')}: {e}")
    
    def _render_labels(self, elements: List[Dict]) -> None:
        """
        Отрисовка названий элементов
        Порт legacy label rendering
        """
        # Не показываем текст при слишком мелком масштабе
        if self.coords.scale < self.lod_settings['text_scale_threshold']:
            return
        
        for element in elements:
            try:
                outer_points = element.get('outer_xy_m', [])
                if len(outer_points) < 3:
                    continue
                
                # Вычисляем центроид для размещения текста
                centroid_x, centroid_y = self._calculate_centroid(outer_points)
                
                # Преобразуем в экранные координаты
                screen_x, screen_y = self.coords.world_to_screen(centroid_x, centroid_y)
                
                # Получаем название элемента
                name = element.get('name', element.get('id', 'Unnamed'))
                
                # Создаем текст
                self.canvas.create_text(
                    screen_x, screen_y,
                    text=name,
                    font=('Arial', 8),
                    fill="black",
                    anchor=tk.CENTER,
                    tags=('labels',)
                )
                
            except Exception as e:
                print(f"⚠️ Ошибка отрисовки названия {element.get('id', 'unknown')}: {e}")
    
    def _draw_polygon(self, points: List[List[float]], fill_color: Optional[str] = None, 
                     outline_color: str = "black", outline_width: int = 1) -> List[int]:
        """
        Отрисовка полигона с преобразованием координат
        Порт legacy polygon drawing с координатными преобразованиями
        """
        if len(points) < 3:
            return []
        
        try:
            # Преобразуем мировые координаты в экранные (порт legacy _to_screen)
            screen_points = []
            for point in points:
                if len(point) >= 2:
                    screen_x, screen_y = self.coords.world_to_screen(point[0], point[1])
                    screen_points.extend([screen_x, screen_y])
            
            if len(screen_points) < 6:  # Минимум 3 точки = 6 координат
                return []
            
            # Создаем полигон на canvas
            polygon_id = self.canvas.create_polygon(
                screen_points,
                fill=fill_color or "",
                outline=outline_color,
                width=outline_width,
                tags=('geometry',)
            )
            
            return [polygon_id]
            
        except Exception as e:
            print(f"❌ Ошибка отрисовки полигона: {e}")
            return []
    
    def _calculate_centroid(self, points: List[List[float]]) -> Tuple[float, float]:
        """
        Вычисление центроида полигона
        Простая реализация для размещения текста
        """
        if not points:
            return (0.0, 0.0)
        
        if GEOMETRY_UTILS_AVAILABLE:
            return centroid_xy(points)
        else:
            # Простое среднее арифметическое координат
            sum_x = sum(p[0] for p in points if len(p) >= 2)
            sum_y = sum(p[1] for p in points if len(p) >= 2)
            count = len([p for p in points if len(p) >= 2])
            
            if count == 0:
                return (0.0, 0.0)
            
            return (sum_x / count, sum_y / count)
    
    def _draw_grid(self) -> None:
        """
        Отрисовка координатной сетки
        Базовая реализация для навигации
        """
        try:
            canvas_width = self.canvas.winfo_width() or 800
            canvas_height = self.canvas.winfo_height() or 600
            
            # Простая сетка с шагом 1 метр
            grid_size = 1.0
            
            # Определяем видимые границы
            visible_bounds = self.coords.get_visible_world_bounds(canvas_width, canvas_height)
            min_x, min_y, max_x, max_y = visible_bounds
            
            min_x = math.floor(min_x / grid_size) * grid_size
            max_x = math.ceil(max_x / grid_size) * grid_size
            min_y = math.floor(min_y / grid_size) * grid_size
            max_y = math.ceil(max_y / grid_size) * grid_size
            
            # Рисуем вертикальные линии
            x = min_x
            while x <= max_x:
                x1, y1 = self.coords.world_to_screen(x, min_y)
                x2, y2 = self.coords.world_to_screen(x, max_y)
                if 0 <= x1 <= canvas_width:  # Линия видна на экране
                    self.canvas.create_line(x1, y1, x2, y2, fill="#e0e0e0", tags=('grid',))
                x += grid_size
            
            # Рисуем горизонтальные линии
            y = min_y
            while y <= max_y:
                x1, y1 = self.coords.world_to_screen(min_x, y)
                x2, y2 = self.coords.world_to_screen(max_x, y)
                if 0 <= y1 <= canvas_height:  # Линия видна на экране
                    self.canvas.create_line(x1, y1, x2, y2, fill="#e0e0e0", tags=('grid',))
                y += grid_size
                
        except Exception as e:
            print(f"❌ Ошибка отрисовки сетки: {e}")
    
    def draw_element(self, element: Dict, style_override: Optional[Dict] = None) -> List[int]:
        """
        Отрисовка одного геометрического элемента
        
        Args:
            element: Данные элемента со свойствами геометрии
            style_override: Переопределение стиля отрисовки
            
        Returns:
            Список ID объектов canvas, созданных для этого элемента
        """
        canvas_ids = []
        
        try:
            # Получаем тип элемента и его геометрию
            element_type = element.get('element_type', 'room')
            outer_points = element.get('outer_xy_m', [])
            
            if len(outer_points) < 3:
                return canvas_ids
            
            # Проверяем, виден ли элемент
            if not self._is_element_visible(outer_points):
                self.render_stats['elements_culled'] += 1
                return canvas_ids
            
            # Определяем стиль отрисовки
            style = self._get_element_style(element_type)
            if style_override:
                style.update(style_override)
            
            # Отрисовываем основной контур
            polygon_ids = self._draw_polygon(
                outer_points,
                fill_color=style.get('fill'),
                outline_color=style.get('outline'),
                outline_width=style.get('width', 1)
            )
            canvas_ids.extend(polygon_ids)
            
            # Отрисовываем внутренние контуры (отверстия)
            inner_loops = element.get('inner_loops_xy_m', [])
            for loop in inner_loops:
                hole_ids = self._draw_polygon(
                    loop,
                    fill_color="white",
                    outline_color=style.get('outline'),
                    outline_width=style.get('width', 1)
                )
                canvas_ids.extend(hole_ids)
            
            self.render_stats['elements_drawn'] += 1
            
        except Exception as e:
            print(f"❌ Ошибка отрисовки элемента {element.get('id', 'unknown')}: {e}")
        
        return canvas_ids
    
    def _is_element_visible(self, points: List[List[float]]) -> bool:
        """Проверка видимости элемента"""
        if not points:
            return False
        
        try:
            # Получаем границы элемента
            element_bounds = bounds(points)
            if not element_bounds:
                return False
            
            # Получаем размеры canvas
            canvas_width = self.canvas.winfo_width() or 800
            canvas_height = self.canvas.winfo_height() or 600
            
            # Получаем видимые границы
            visible_bounds = self.coords.get_visible_world_bounds(canvas_width, canvas_height)
            
            # Проверяем пересечение
            return self._bounds_intersect(element_bounds, visible_bounds)
            
        except Exception:
            return True  # При ошибке считаем элемент видимым
    
    def _bounds_intersect(self, bounds1: Tuple[float, float, float, float], 
                         bounds2: Tuple[float, float, float, float]) -> bool:
        """Проверка пересечения двух прямоугольников"""
        min_x1, min_y1, max_x1, max_y1 = bounds1
        min_x2, min_y2, max_x2, max_y2 = bounds2
        
        return not (max_x1 < min_x2 or min_x1 > max_x2 or 
                   max_y1 < min_y2 or min_y1 > max_y2)
    
    def _get_element_style(self, element_type: str) -> Dict:
        """Получение стиля для типа элемента"""
        return ELEMENT_COLORS.get(element_type, ELEMENT_COLORS['room']).copy()
    
    def highlight_element(self, canvas_ids: List[int], highlight: bool) -> None:
        """Подсветка элементов"""
        for canvas_id in canvas_ids:
            try:
                if highlight:
                    self.canvas.itemconfig(canvas_id, outline=SELECTED_COLOR, width=3)
                else:
                    # Восстанавливаем оригинальный стиль (упрощенно)
                    self.canvas.itemconfig(canvas_id, outline="#333333", width=1)
            except Exception as e:
                print(f"⚠️ Ошибка подсветки элемента {canvas_id}: {e}")
    
    def draw_temporary_polygon(self, points: List[Tuple[float, float]]) -> Optional[int]:
        """Отрисовка временного полигона (для режимов рисования)"""
        if len(points) < 2:
            return None
        
        try:
            # Преобразуем в экранные координаты
            screen_points = []
            for point in points:
                screen_x, screen_y = self.coords.world_to_screen(point[0], point[1])
                screen_points.extend([screen_x, screen_y])
            
            if len(points) == 2:
                # Рисуем линию
                return self.canvas.create_line(
                    screen_points,
                    fill=ELEMENT_COLORS['drawing']['outline'],
                    width=ELEMENT_COLORS['drawing']['width'],
                    dash=ELEMENT_COLORS['drawing']['dash'],
                    tags=('temporary',)
                )
            else:
                # Рисуем полигон
                return self.canvas.create_polygon(
                    screen_points,
                    fill="",
                    outline=ELEMENT_COLORS['drawing']['outline'],
                    width=ELEMENT_COLORS['drawing']['width'],
                    dash=ELEMENT_COLORS['drawing']['dash'],
                    tags=('temporary',)
                )
                
        except Exception as e:
            print(f"❌ Ошибка отрисовки временного полигона: {e}")
            return None


# ============================================================================
# GEOMETRY CANVAS (основной класс)
# ============================================================================

class GeometryCanvas:
    """
    Главный класс геометрического canvas
    
    ЭТАП 1: Интегрирован с render_bess_data() и навигацией (исправлен)
    """
    
    def __init__(self, parent: tk.Widget, **config):
        """
        Инициализация GeometryCanvas
        
        Args:
            parent: Родительский виджет
            **config: Дополнительные настройки
        """
        # Создаем Canvas
        self.canvas = tk.Canvas(parent, **config)
        
        # Создаем компоненты
        self.coordinate_system = CoordinateSystem()
        self.renderer = GeometryRenderer(self.canvas, self.coordinate_system)
        
        # Система производительности
        self.performance_monitor = PerformanceMonitor()
        
        # Состояние canvas
        self.elements_to_display = []
        self.selected_elements = set()
        self.element_canvas_mappings = {}
        self.temp_canvas_objects = []
        
        # Callbacks
        self.on_element_selected = None
        self.on_view_changed = None
        
        print("✅ GeometryCanvas инициализирован (ЭТАП 1 - исправлен)")
    
    def pack(self, **kwargs):
        """Wrapper для pack"""
        self.canvas.pack(**kwargs)
    
    def grid(self, **kwargs):
        """Wrapper для grid"""
        self.canvas.grid(**kwargs)
    
    def clear(self) -> None:
        """Очистка canvas"""
        self.canvas.delete("all")
        self.element_canvas_mappings.clear()
        self.temp_canvas_objects.clear()
    
    def refresh_display(self) -> None:
        """
        Обновление отображения всех элементов
        """
        try:
            start_time = time.time()
            self.performance_monitor.start_frame()
            
            # Очищаем canvas
            self.clear()
            
            # Отрисовываем элементы
            for element in self.elements_to_display:
                canvas_ids = self.renderer.draw_element(element)
                
                for canvas_id in canvas_ids:
                    self.element_canvas_mappings[canvas_id] = {
                        'element_id': element.get('id'),
                        'element_data': element
                    }
            
            # Отрисовываем временные объекты (для режимов рисования)
            if hasattr(self, 'drawing_points') and self.drawing_points:
                temp_id = self.renderer.draw_temporary_polygon(self.drawing_points)
                if temp_id:
                    self.temp_canvas_objects.append(temp_id)
            
            # Восстанавливаем выделение элементов
            self._restore_selection_highlighting()
            
            self.performance_monitor.end_frame()
            render_time = (time.time() - start_time) * 1000
            
            # Уведомляем о изменении вида
            if self.on_view_changed:
                self.on_view_changed({
                    'elements_count': len(self.elements_to_display),
                    'render_time_ms': render_time,
                    'scale': self.coordinate_system.scale
                })
                
        except Exception as e:
            print(f"❌ Ошибка обновления отображения: {e}")
    
    def fit_to_elements(self, elements: Optional[List[Dict]] = None) -> None:
        """
        Подгонка масштаба для отображения всех элементов
        
        Args:
            elements: Элементы для подгонки (если None, используются текущие)
        """
        if elements is None:
            elements = self.elements_to_display
        
        if not elements:
            return
        
        try:
            # Собираем все точки всех элементов
            all_points = []
            for element in elements:
                outer_points = element.get('outer_xy_m', [])
                all_points.extend(outer_points)
                
                # Добавляем точки внутренних контуров
                inner_loops = element.get('inner_loops_xy_m', [])
                for loop in inner_loops:
                    all_points.extend(loop)
            
            if not all_points:
                return
            
            # Находим общие границы
            element_bounds = bounds(all_points)
            if not element_bounds:
                return
            
            # Получаем размеры canvas
            canvas_width = max(self.canvas.winfo_width(), 100)
            canvas_height = max(self.canvas.winfo_height(), 100)
            
            # Подгоняем координатную систему
            self.coordinate_system.fit_to_bounds(
                element_bounds[0], element_bounds[1],  # min_x, min_y
                element_bounds[2], element_bounds[3],  # max_x, max_y
                canvas_width, canvas_height,
                margin=0.1  # 10% отступ
            )
            
            # Обновляем отображение
            self.refresh_display()
            
        except Exception as e:
            print(f"❌ Ошибка подгонки к элементам: {e}")
    
    def zoom_to_point(self, screen_x: float, screen_y: float, zoom_factor: float) -> None:
        """Масштабирование относительно точки на экране"""
        self.coordinate_system.zoom_to_point(screen_x, screen_y, zoom_factor)
        self.refresh_display()
    
    def pan_view(self, delta_x: float, delta_y: float) -> None:
        """Панорамирование вида"""
        self.coordinate_system.pan(delta_x, delta_y)
        self.refresh_display()
    
    def get_element_at_screen_point(self, screen_x: float, screen_y: float) -> Optional[Dict]:
        """
        Получение элемента в указанной точке экрана
        
        Args:
            screen_x, screen_y: Координаты точки на экране
            
        Returns:
            Данные элемента или None если элемент не найден
        """
        try:
            # Находим объект canvas под курсором
            canvas_id = self.canvas.find_overlapping(screen_x, screen_y, screen_x, screen_y)
            
            if canvas_id:
                top_item = canvas_id[-1]  # Берем верхний элемент
                mapping = self.element_canvas_mappings.get(top_item)
                
                if mapping:
                    return mapping['element_data']
                    
        except Exception as e:
            print(f"⚠️ Ошибка поиска элемента: {e}")
        
        return None
    
    def get_world_coordinates(self, screen_x: float, screen_y: float) -> Tuple[float, float]:
        """Преобразование экранных координат в мировые"""
        return self.coordinate_system.screen_to_world(screen_x, screen_y)
    
    def get_screen_coordinates(self, world_x: float, world_y: float) -> Tuple[float, float]:
        """Преобразование мировых координат в экранные"""
        return self.coordinate_system.world_to_screen(world_x, world_y)
    
    def _restore_selection_highlighting(self) -> None:
        """Восстановление визуального выделения после перерисовки"""
        for canvas_id, mapping in self.element_canvas_mappings.items():
            element_id = mapping['element_id']
            is_selected = element_id in self.selected_elements
            
            if is_selected:
                self.renderer.highlight_element([canvas_id], True)
    
    def _update_selection_display(self) -> None:
        """Обновление отображения выделенных элементов"""
        # Обновляем все элементы
        for canvas_id, mapping in self.element_canvas_mappings.items():
            element_id = mapping['element_id']
            is_selected = element_id in self.selected_elements
            self.renderer.highlight_element([canvas_id], is_selected)


# ============================================================================
# ФАБРИЧНЫЕ ФУНКЦИИ
# ============================================================================

def create_geometry_canvas(parent: tk.Widget, **config) -> GeometryCanvas:
    """
    Удобная функция для создания экземпляра GeometryCanvas
    
    Args:
        parent: Родительский виджет
        **config: Дополнительные настройки
        
    Returns:
        Настроенный экземпляр GeometryCanvas
    """
    return GeometryCanvas(parent, **config)


# Экспортируем основные классы
__all__ = [
    'GeometryCanvas',
    'CoordinateSystem', 
    'GeometryRenderer',
    'create_geometry_canvas',
    'ELEMENT_COLORS',
    'ROOM_PALETTE'
]