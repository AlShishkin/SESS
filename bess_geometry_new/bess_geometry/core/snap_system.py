# -*- coding: utf-8 -*-
"""
core/snap_system.py - Система привязок и ортогональности для SOFT

ЭТАП 1.3: Критически важный функционал - Система привязок и ортогональности
Портирует функционал _snap_world() из legacy sess_geometry с улучшениями

Основные принципы:
- Точное позиционирование: привязка к существующим элементам
- Ортогональные линии: горизонтальные/вертикальные направления  
- Сетка: привязка к регулярной сетке координат
- Настраиваемые допуски: гибкое управление точностью
- Производительность: оптимизированные алгоритмы поиска

Типы привязок (портировано из legacy):
📍 Вершины - привязка к точкам контуров
📏 Ребра - привязка к линиям между точками
🔲 Сетка - привязка к регулярной сетке
📐 Ортогональность - горизонтальные/вертикальные направления
🎯 Точки пересечения - пересечения линий и контуров
"""

import math
from typing import Dict, List, Set, Optional, Tuple, Callable, Any, NamedTuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

# Импорт геометрических утилит
try:
    from ..geometry_utils import distance_point_to_point, distance_point_to_line, line_intersection, r2
    GEOMETRY_UTILS_AVAILABLE = True
except ImportError:
    # Fallback функции
    def distance_point_to_point(p1, p2):
        return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
    
    def distance_point_to_line(point, line_start, line_end):
        # Простая реализация расстояния от точки до линии
        px, py = point
        x1, y1 = line_start
        x2, y2 = line_end
        
        A = px - x1
        B = py - y1
        C = x2 - x1
        D = y2 - y1
        
        dot = A * C + B * D
        len_sq = C * C + D * D
        
        if len_sq < 1e-10:
            return math.sqrt(A * A + B * B)
        
        param = dot / len_sq
        
        if param < 0:
            xx, yy = x1, y1
        elif param > 1:
            xx, yy = x2, y2
        else:
            xx = x1 + param * C
            yy = y1 + param * D
        
        dx = px - xx
        dy = py - yy
        return math.sqrt(dx * dx + dy * dy)
    
    def line_intersection(line1_start, line1_end, line2_start, line2_end):
        # Простая реализация пересечения линий
        x1, y1 = line1_start
        x2, y2 = line1_end
        x3, y3 = line2_start
        x4, y4 = line2_end
        
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-10:
            return None
        
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        x = x1 + t * (x2 - x1)
        y = y1 + t * (y2 - y1)
        
        return (x, y)
    
    def r2(value):
        return round(float(value), 2)
    
    GEOMETRY_UTILS_AVAILABLE = False


class SnapType(Enum):
    """Типы привязок"""
    NONE = "none"                 # Без привязки
    VERTEX = "vertex"             # К вершине
    EDGE = "edge"                 # К ребру/линии
    MIDPOINT = "midpoint"         # К середине ребра
    INTERSECTION = "intersection"  # К пересечению линий
    PERPENDICULAR = "perpendicular" # Перпендикуляр к линии
    GRID = "grid"                 # К сетке
    ORTHO = "ortho"               # Ортогональность
    CENTER = "center"             # К центру элемента


class OrthogonalDirection(Enum):
    """Ортогональные направления"""
    NONE = "none"
    HORIZONTAL = "horizontal"     # Горизонтальное направление
    VERTICAL = "vertical"         # Вертикальное направление
    DIAGONAL_45 = "diagonal_45"   # Диагональ 45°
    DIAGONAL_135 = "diagonal_135" # Диагональ 135°


@dataclass
class SnapPoint:
    """
    Результат привязки - точка с метаданными
    
    Содержит информацию о найденной точке привязки:
    - Координаты точки
    - Тип привязки
    - Расстояние до исходной точки
    - Дополнительная информация
    """
    x: float
    y: float
    snap_type: SnapType
    distance: float
    element_id: Optional[str] = None
    element_type: Optional[str] = None
    vertex_index: Optional[int] = None
    edge_index: Optional[int] = None
    description: str = ""
    
    def to_tuple(self) -> Tuple[float, float]:
        """Преобразование в кортеж координат"""
        return (self.x, self.y)
    
    def __str__(self) -> str:
        return f"SnapPoint({self.x:.2f}, {self.y:.2f}, {self.snap_type.value})"


@dataclass
class SnapSettings:
    """
    Настройки системы привязок
    
    Портирует настройки из legacy с расширениями:
    - Допуски для различных типов привязок
    - Включение/выключение типов
    - Приоритеты привязок
    """
    
    # Главные переключатели (как в legacy)
    snap_enabled: bool = True
    ortho_enabled: bool = False
    grid_enabled: bool = False
    
    # Допуски в пикселях (портировано из legacy)
    vertex_tolerance: float = 10.0
    edge_tolerance: float = 8.0
    grid_tolerance: float = 5.0
    intersection_tolerance: float = 12.0
    
    # Настройки сетки
    grid_size: float = 1.0        # размер сетки в мировых единицах
    grid_origin: Tuple[float, float] = (0.0, 0.0)
    
    # Приоритеты привязок (больше значение = выше приоритет)
    snap_priorities: Dict[SnapType, int] = field(default_factory=lambda: {
        SnapType.VERTEX: 100,      # Высший приоритет - вершины
        SnapType.INTERSECTION: 90,  # Пересечения
        SnapType.MIDPOINT: 80,     # Середины ребер
        SnapType.EDGE: 70,         # Ребра
        SnapType.PERPENDICULAR: 60, # Перпендикуляры
        SnapType.CENTER: 50,       # Центры
        SnapType.GRID: 30,         # Сетка
        SnapType.ORTHO: 20         # Ортогональность (низший приоритет)
    })
    
    # Включенные типы привязок
    enabled_snap_types: Set[SnapType] = field(default_factory=lambda: {
        SnapType.VERTEX,
        SnapType.EDGE,
        SnapType.MIDPOINT,
        SnapType.INTERSECTION,
        SnapType.GRID
    })
    
    # Ортогональные углы в градусах (0° = горизонтально)
    ortho_angles: List[float] = field(default_factory=lambda: [0.0, 45.0, 90.0, 135.0])
    ortho_tolerance: float = 5.0  # допуск в градусах
    
    # Производительность
    max_snap_candidates: int = 100  # максимум кандидатов для анализа
    spatial_optimization: bool = True  # пространственная оптимизация
    
    def is_snap_type_enabled(self, snap_type: SnapType) -> bool:
        """Проверка включенности типа привязки"""
        if not self.snap_enabled:
            return False
        
        if snap_type == SnapType.GRID:
            return self.grid_enabled
        elif snap_type == SnapType.ORTHO:
            return self.ortho_enabled
        else:
            return snap_type in self.enabled_snap_types
    
    def get_tolerance(self, snap_type: SnapType) -> float:
        """Получение допуска для типа привязки"""
        tolerance_map = {
            SnapType.VERTEX: self.vertex_tolerance,
            SnapType.EDGE: self.edge_tolerance,
            SnapType.MIDPOINT: self.edge_tolerance,
            SnapType.INTERSECTION: self.intersection_tolerance,
            SnapType.PERPENDICULAR: self.edge_tolerance,
            SnapType.CENTER: self.vertex_tolerance,
            SnapType.GRID: self.grid_tolerance,
            SnapType.ORTHO: float('inf')  # Ортогональность всегда применяется
        }
        
        return tolerance_map.get(snap_type, 10.0)


class SnapCandidate(NamedTuple):
    """Кандидат для привязки - найденная потенциальная точка"""
    point: Tuple[float, float]
    snap_type: SnapType
    distance: float
    priority: int
    element_id: Optional[str] = None
    element_type: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ISnapProvider(ABC):
    """
    Интерфейс поставщика точек привязки
    
    Позволяет различным компонентам системы предоставлять свои точки привязки:
    - Геометрические элементы (комнаты, области)
    - Вспомогательные элементы (сетка, оси)
    - Временные элементы (предварительный просмотр)
    """
    
    @abstractmethod
    def get_snap_candidates(self, 
                          x: float, y: float, 
                          tolerance: float,
                          snap_types: Set[SnapType],
                          coordinate_system: Any = None) -> List[SnapCandidate]:
        """
        Получение кандидатов привязки в области поиска
        
        Args:
            x, y: Координаты для поиска (мировые)
            tolerance: Радиус поиска в пикселях
            snap_types: Требуемые типы привязок
            coordinate_system: Система координат для преобразований
            
        Returns:
            Список кандидатов, отсортированный по приоритету
        """
        pass
    
    @abstractmethod
    def get_provider_id(self) -> str:
        """Уникальный идентификатор поставщика"""
        pass


class GeometrySnapProvider(ISnapProvider):
    """
    Поставщик привязок для геометрических элементов
    
    Портирует логику из legacy _snap_world() для работы с:
    - Комнатами (rooms)
    - Областями (areas) 
    - Проемами (openings)
    - Шахтами (shafts)
    """
    
    def __init__(self, geometry_data: Dict[str, List[Dict]]):
        """
        Инициализация с геометрическими данными
        
        Args:
            geometry_data: Словарь с списками элементов по типам
                          {'rooms': [...], 'areas': [...], 'openings': [...]}
        """
        self.geometry_data = geometry_data
        self.provider_id = "geometry_snap_provider"
        
        # Кэш для оптимизации поиска
        self._vertex_cache: Dict[str, List[Tuple[float, float]]] = {}
        self._edge_cache: Dict[str, List[Tuple[Tuple[float, float], Tuple[float, float]]]] = {}
        self._cache_valid = False
    
    def get_provider_id(self) -> str:
        return self.provider_id
    
    def get_snap_candidates(self, 
                          x: float, y: float,
                          tolerance: float,
                          snap_types: Set[SnapType],
                          coordinate_system: Any = None) -> List[SnapCandidate]:
        """Поиск кандидатов привязки в геометрических элементах"""
        
        candidates = []
        
        # Обновляем кэш если нужно
        if not self._cache_valid:
            self._rebuild_cache()
        
        # Преобразуем допуск из пикселей в мировые единицы
        world_tolerance = tolerance
        if coordinate_system:
            # Преобразование пиксели -> мировые координаты
            try:
                p1_world = coordinate_system.screen_to_world(0, 0)
                p2_world = coordinate_system.screen_to_world(tolerance, 0)
                world_tolerance = abs(p2_world[0] - p1_world[0])
            except:
                world_tolerance = tolerance * 0.01  # fallback
        
        # Поиск привязок к вершинам
        if SnapType.VERTEX in snap_types:
            vertex_candidates = self._find_vertex_candidates(x, y, world_tolerance)
            candidates.extend(vertex_candidates)
        
        # Поиск привязок к ребрам
        if SnapType.EDGE in snap_types or SnapType.MIDPOINT in snap_types:
            edge_candidates = self._find_edge_candidates(x, y, world_tolerance, snap_types)
            candidates.extend(edge_candidates)
        
        # Поиск пересечений (более сложная логика)
        if SnapType.INTERSECTION in snap_types:
            intersection_candidates = self._find_intersection_candidates(x, y, world_tolerance)
            candidates.extend(intersection_candidates)
        
        # Сортируем по приоритету и расстоянию
        candidates.sort(key=lambda c: (-c.priority, c.distance))
        
        return candidates
    
    def _rebuild_cache(self):
        """Перестроение кэша геометрических элементов"""
        self._vertex_cache.clear()
        self._edge_cache.clear()
        
        for element_type, elements in self.geometry_data.items():
            for element in elements:
                element_id = element.get('id', f'{element_type}_{id(element)}')
                
                # Кэшируем вершины
                outer_points = element.get('outer_xy_m', [])
                if outer_points:
                    self._vertex_cache[element_id] = [(float(p[0]), float(p[1])) for p in outer_points]
                    
                    # Кэшируем ребра
                    edges = []
                    for i in range(len(outer_points)):
                        p1 = (float(outer_points[i][0]), float(outer_points[i][1]))
                        p2 = (float(outer_points[(i + 1) % len(outer_points)][0]), 
                              float(outer_points[(i + 1) % len(outer_points)][1]))
                        edges.append((p1, p2))
                    self._edge_cache[element_id] = edges
                
                # Внутренние контуры
                inner_loops = element.get('inner_loops_xy_m', [])
                for loop_idx, loop in enumerate(inner_loops):
                    loop_id = f"{element_id}_inner_{loop_idx}"
                    self._vertex_cache[loop_id] = [(float(p[0]), float(p[1])) for p in loop]
                    
                    edges = []
                    for i in range(len(loop)):
                        p1 = (float(loop[i][0]), float(loop[i][1]))
                        p2 = (float(loop[(i + 1) % len(loop)][0]), 
                              float(loop[(i + 1) % len(loop)][1]))
                        edges.append((p1, p2))
                    self._edge_cache[loop_id] = edges
        
        self._cache_valid = True
    
    def _find_vertex_candidates(self, x: float, y: float, tolerance: float) -> List[SnapCandidate]:
        """Поиск ближайших вершин (портировано из legacy)"""
        candidates = []
        
        for element_id, vertices in self._vertex_cache.items():
            for vertex_idx, vertex in enumerate(vertices):
                distance = distance_point_to_point((x, y), vertex)
                
                if distance <= tolerance:
                    candidates.append(SnapCandidate(
                        point=vertex,
                        snap_type=SnapType.VERTEX,
                        distance=distance,
                        priority=100,  # Высокий приоритет для вершин
                        element_id=element_id,
                        element_type=self._get_element_type(element_id),
                        metadata={'vertex_index': vertex_idx}
                    ))
        
        return candidates
    
    def _find_edge_candidates(self, x: float, y: float, tolerance: float, 
                            snap_types: Set[SnapType]) -> List[SnapCandidate]:
        """Поиск ближайших ребер и их середин"""
        candidates = []
        
        for element_id, edges in self._edge_cache.items():
            for edge_idx, (p1, p2) in enumerate(edges):
                distance = distance_point_to_line((x, y), p1, p2)
                
                if distance <= tolerance:
                    # Ближайшая точка на ребре
                    closest_point = self._closest_point_on_edge((x, y), p1, p2)
                    
                    if SnapType.EDGE in snap_types:
                        candidates.append(SnapCandidate(
                            point=closest_point,
                            snap_type=SnapType.EDGE,
                            distance=distance,
                            priority=70,
                            element_id=element_id,
                            element_type=self._get_element_type(element_id),
                            metadata={'edge_index': edge_idx, 'edge': (p1, p2)}
                        ))
                    
                    # Середина ребра
                    if SnapType.MIDPOINT in snap_types:
                        midpoint = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
                        mid_distance = distance_point_to_point((x, y), midpoint)
                        
                        if mid_distance <= tolerance:
                            candidates.append(SnapCandidate(
                                point=midpoint,
                                snap_type=SnapType.MIDPOINT,
                                distance=mid_distance,
                                priority=80,
                                element_id=element_id,
                                element_type=self._get_element_type(element_id),
                                metadata={'edge_index': edge_idx, 'edge': (p1, p2)}
                            ))
        
        return candidates
    
    def _find_intersection_candidates(self, x: float, y: float, 
                                    tolerance: float) -> List[SnapCandidate]:
        """Поиск пересечений линий (упрощенная версия)"""
        candidates = []
        
        # Для демонстрации - поиск пересечений между всеми ребрами
        # В реальной реализации нужна пространственная оптимизация
        
        all_edges = []
        for element_id, edges in self._edge_cache.items():
            for edge_idx, edge in enumerate(edges):
                all_edges.append((edge, element_id, edge_idx))
        
        # Ищем пересечения между парами ребер
        for i, (edge1, elem1, idx1) in enumerate(all_edges):
            for j, (edge2, elem2, idx2) in enumerate(all_edges[i+1:], i+1):
                if elem1 == elem2:  # Пропускаем ребра одного элемента
                    continue
                
                intersection = line_intersection(edge1[0], edge1[1], edge2[0], edge2[1])
                if intersection:
                    distance = distance_point_to_point((x, y), intersection)
                    if distance <= tolerance:
                        candidates.append(SnapCandidate(
                            point=intersection,
                            snap_type=SnapType.INTERSECTION,
                            distance=distance,
                            priority=90,
                            element_id=f"{elem1}x{elem2}",
                            element_type="intersection",
                            metadata={
                                'edge1': edge1,
                                'edge2': edge2,
                                'element1_id': elem1,
                                'element2_id': elem2
                            }
                        ))
        
        return candidates
    
    def _closest_point_on_edge(self, point: Tuple[float, float], 
                             edge_start: Tuple[float, float],
                             edge_end: Tuple[float, float]) -> Tuple[float, float]:
        """Нахождение ближайшей точки на ребре"""
        px, py = point
        x1, y1 = edge_start
        x2, y2 = edge_end
        
        # Вектор ребра
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            return edge_start
        
        # Параметр проекции точки на прямую
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        
        # Ограничиваем параметр в пределах ребра
        t = max(0, min(1, t))
        
        # Вычисляем точку
        return (x1 + t * dx, y1 + t * dy)
    
    def _get_element_type(self, element_id: str) -> str:
        """Определение типа элемента по ID"""
        if '_inner_' in element_id:
            return 'inner_loop'
        
        for element_type, elements in self.geometry_data.items():
            for element in elements:
                if element.get('id') == element_id or element_id.startswith(element_type):
                    return element_type
        
        return 'unknown'
    
    def invalidate_cache(self):
        """Инвалидация кэша при изменении геометрии"""
        self._cache_valid = False


class GridSnapProvider(ISnapProvider):
    """Поставщик привязок к сетке"""
    
    def __init__(self, grid_size: float = 1.0, origin: Tuple[float, float] = (0.0, 0.0)):
        self.grid_size = grid_size
        self.origin = origin
        self.provider_id = "grid_snap_provider"
    
    def get_provider_id(self) -> str:
        return self.provider_id
    
    def get_snap_candidates(self, x: float, y: float, tolerance: float,
                          snap_types: Set[SnapType],
                          coordinate_system: Any = None) -> List[SnapCandidate]:
        """Поиск ближайших точек сетки"""
        if SnapType.GRID not in snap_types:
            return []
        
        candidates = []
        
        # Преобразуем допуск из пикселей в мировые единицы
        world_tolerance = tolerance * 0.01  # упрощенное преобразование
        if coordinate_system:
            try:
                p1_world = coordinate_system.screen_to_world(0, 0)
                p2_world = coordinate_system.screen_to_world(tolerance, 0)
                world_tolerance = abs(p2_world[0] - p1_world[0])
            except:
                pass
        
        # Найти ближайшую точку сетки
        grid_x = round((x - self.origin[0]) / self.grid_size) * self.grid_size + self.origin[0]
        grid_y = round((y - self.origin[1]) / self.grid_size) * self.grid_size + self.origin[1]
        
        distance = distance_point_to_point((x, y), (grid_x, grid_y))
        
        if distance <= world_tolerance:
            candidates.append(SnapCandidate(
                point=(grid_x, grid_y),
                snap_type=SnapType.GRID,
                distance=distance,
                priority=30,
                element_id="grid",
                element_type="grid",
                metadata={'grid_size': self.grid_size}
            ))
        
        return candidates


class SnapSystem:
    """
    Главный класс системы привязок - портирует _snap_world() из legacy
    
    Координирует работу всех поставщиков привязок и применяет ортогональность.
    Это центральный компонент, который использует все остальные системы привязок.
    
    Основные функции:
    - Поиск оптимальной точки привязки среди всех кандидатов
    - Применение ортогональности
    - Управление настройками и поставщиками
    - Кэширование результатов для производительности
    """
    
    def __init__(self, settings: Optional[SnapSettings] = None):
        """
        Инициализация системы привязок
        
        Args:
            settings: Настройки привязок (по умолчанию создаются стандартные)
        """
        self.settings = settings or SnapSettings()
        self.providers: Dict[str, ISnapProvider] = {}
        
        # Кэш результатов для производительности
        self._last_snap_result: Optional[SnapPoint] = None
        self._last_snap_input: Optional[Tuple[float, float]] = None
        
        # Статистика для отладки
        self.stats = {
            'total_snaps': 0,
            'successful_snaps': 0,
            'cache_hits': 0,
            'average_candidates': 0.0
        }
        
        print("✅ SnapSystem инициализирована")
    
    def add_provider(self, provider: ISnapProvider) -> None:
        """Добавление поставщика привязок"""
        self.providers[provider.get_provider_id()] = provider
        print(f"📍 Добавлен поставщик привязок: {provider.get_provider_id()}")
    
    def remove_provider(self, provider_id: str) -> None:
        """Удаление поставщика привязок"""
        if provider_id in self.providers:
            del self.providers[provider_id]
            print(f"🗑️ Удален поставщик привязок: {provider_id}")
    
    def snap_world(self, x: float, y: float, 
                  coordinate_system: Any = None,
                  reference_point: Optional[Tuple[float, float]] = None) -> Tuple[float, float]:
        """
        Главная функция привязки - портированная из legacy _snap_world()
        
        Args:
            x, y: Исходные координаты в мировой системе
            coordinate_system: Система координат для преобразований
            reference_point: Опорная точка для ортогональности
            
        Returns:
            Привязанные координаты (x, y)
        """
        self.stats['total_snaps'] += 1
        
        # Проверяем кэш
        if (self._last_snap_input and 
            abs(self._last_snap_input[0] - x) < 0.001 and 
            abs(self._last_snap_input[1] - y) < 0.001):
            self.stats['cache_hits'] += 1
            if self._last_snap_result:
                return self._last_snap_result.to_tuple()
        
        original_point = (x, y)
        best_snap = None
        
        # Если привязка отключена, сразу возвращаем исходную точку
        if not self.settings.snap_enabled:
            return self._apply_final_processing(original_point, reference_point)
        
        # Собираем кандидатов от всех поставщиков
        all_candidates = []
        enabled_types = {snap_type for snap_type in SnapType 
                        if self.settings.is_snap_type_enabled(snap_type)}
        
        for provider in self.providers.values():
            try:
                candidates = provider.get_snap_candidates(
                    x, y,
                    max(self.settings.vertex_tolerance, self.settings.edge_tolerance),
                    enabled_types,
                    coordinate_system
                )
                all_candidates.extend(candidates)
            except Exception as e:
                print(f"⚠️ Ошибка поставщика {provider.get_provider_id()}: {e}")
        
        # Обновляем статистику
        if all_candidates:
            self.stats['average_candidates'] = (
                self.stats['average_candidates'] * (self.stats['total_snaps'] - 1) + 
                len(all_candidates)
            ) / self.stats['total_snaps']
        
        # Выбираем лучший кандидат
        if all_candidates:
            best_snap = self._select_best_candidate(all_candidates, original_point, coordinate_system)
        
        # Применяем выбранную привязку или возвращаем исходную точку
        if best_snap:
            self.stats['successful_snaps'] += 1
            result_point = best_snap.to_tuple()
        else:
            result_point = original_point
        
        # Применяем окончательную обработку (ортогональность и т.д.)
        final_point = self._apply_final_processing(result_point, reference_point)
        
        # Сохраняем в кэше
        self._last_snap_input = original_point
        self._last_snap_result = SnapPoint(
            x=final_point[0],
            y=final_point[1], 
            snap_type=best_snap.snap_type if best_snap else SnapType.NONE,
            distance=0.0,
            description="Final result"
        )
        
        return final_point
    
    def _select_best_candidate(self, candidates: List[SnapCandidate], 
                             original_point: Tuple[float, float],
                             coordinate_system: Any) -> Optional[SnapPoint]:
        """Выбор лучшего кандидата привязки"""
        if not candidates:
            return None
        
        # Фильтруем кандидатов по допускам
        valid_candidates = []
        
        for candidate in candidates:
            tolerance = self.settings.get_tolerance(candidate.snap_type)
            
            # Преобразуем расстояние в пиксели если нужно
            distance_pixels = candidate.distance
            if coordinate_system:
                try:
                    # Простая аппроксимация масштаба
                    scale = getattr(coordinate_system, 'scale', 1.0)
                    distance_pixels = candidate.distance * scale
                except:
                    pass
            
            if distance_pixels <= tolerance:
                valid_candidates.append(candidate)
        
        if not valid_candidates:
            return None
        
        # Сортируем по приоритету, затем по расстоянию
        valid_candidates.sort(key=lambda c: (-c.priority, c.distance))
        
        best = valid_candidates[0]
        
        return SnapPoint(
            x=best.point[0],
            y=best.point[1],
            snap_type=best.snap_type,
            distance=best.distance,
            element_id=best.element_id,
            element_type=best.element_type,
            description=f"Snap to {best.snap_type.value}"
        )
    
    def _apply_final_processing(self, point: Tuple[float, float], 
                              reference_point: Optional[Tuple[float, float]]) -> Tuple[float, float]:
        """Применение финальной обработки - ортогональность и т.д."""
        x, y = point
        
        # Применяем ортогональность если включена и есть опорная точка
        if (self.settings.ortho_enabled and reference_point and 
            self.settings.is_snap_type_enabled(SnapType.ORTHO)):
            x, y = self._apply_orthogonal_constraint(x, y, reference_point)
        
        # Квантование результата
        return (r2(x), r2(y))
    
    def _apply_orthogonal_constraint(self, x: float, y: float, 
                                   reference_point: Tuple[float, float]) -> Tuple[float, float]:
        """
        Применение ортогонального ограничения (портировано из legacy)
        
        Привязывает точку к ортогональному направлению относительно опорной точки.
        """
        ref_x, ref_y = reference_point
        dx = x - ref_x
        dy = y - ref_y
        
        if abs(dx) < 0.001 and abs(dy) < 0.001:
            return (x, y)
        
        # Вычисляем угол
        angle = math.degrees(math.atan2(dy, dx))
        if angle < 0:
            angle += 360
        
        # Находим ближайший ортогональный угол
        best_ortho_angle = None
        min_angle_diff = float('inf')
        
        for ortho_angle in self.settings.ortho_angles:
            # Проверяем разность углов с учетом цикличности
            diff1 = abs(angle - ortho_angle)
            diff2 = abs(angle - ortho_angle + 360)
            diff3 = abs(angle - ortho_angle - 360)
            
            min_diff = min(diff1, diff2, diff3)
            
            if min_diff < min_angle_diff:
                min_angle_diff = min_diff
                best_ortho_angle = ortho_angle
        
        # Применяем ортогональность если угол достаточно близок
        if (best_ortho_angle is not None and 
            min_angle_diff <= self.settings.ortho_tolerance):
            
            # Вычисляем расстояние от опорной точки
            distance = math.sqrt(dx * dx + dy * dy)
            
            # Применяем ортогональный угол
            ortho_radians = math.radians(best_ortho_angle)
            new_x = ref_x + distance * math.cos(ortho_radians)
            new_y = ref_y + distance * math.sin(ortho_radians)
            
            return (new_x, new_y)
        
        return (x, y)
    
    def get_snap_info(self, x: float, y: float, 
                     coordinate_system: Any = None) -> Optional[SnapPoint]:
        """
        Получение информации о привязке без применения
        
        Полезно для отображения подсказок пользователю.
        """
        if not self.settings.snap_enabled:
            return None
        
        # Используем ту же логику что и snap_world, но не применяем результат
        all_candidates = []
        enabled_types = {snap_type for snap_type in SnapType 
                        if self.settings.is_snap_type_enabled(snap_type)}
        
        for provider in self.providers.values():
            try:
                candidates = provider.get_snap_candidates(
                    x, y,
                    max(self.settings.vertex_tolerance, self.settings.edge_tolerance),
                    enabled_types,
                    coordinate_system
                )
                all_candidates.extend(candidates)
            except Exception as e:
                print(f"⚠️ Ошибка поставщика {provider.get_provider_id()}: {e}")
        
        return self._select_best_candidate(all_candidates, (x, y), coordinate_system)
    
    def toggle_snap(self) -> bool:
        """Переключение привязки (клавиша S)"""
        self.settings.snap_enabled = not self.settings.snap_enabled
        self._clear_cache()
        return self.settings.snap_enabled
    
    def toggle_ortho(self) -> bool:
        """Переключение ортогональности (клавиша O)"""
        self.settings.ortho_enabled = not self.settings.ortho_enabled
        self._clear_cache()
        return self.settings.ortho_enabled
    
    def toggle_grid(self) -> bool:
        """Переключение привязки к сетке (клавиша G)"""
        self.settings.grid_enabled = not self.settings.grid_enabled
        self._clear_cache()
        return self.settings.grid_enabled
    
    def set_grid_size(self, size: float) -> None:
        """Установка размера сетки"""
        self.settings.grid_size = size
        
        # Обновляем поставщиков сетки
        for provider in self.providers.values():
            if isinstance(provider, GridSnapProvider):
                provider.grid_size = size
        
        self._clear_cache()
    
    def get_status_text(self) -> str:
        """Получение текста состояния для UI"""
        status_parts = []
        
        if self.settings.snap_enabled:
            status_parts.append("SNAP")
        if self.settings.ortho_enabled:
            status_parts.append("ORTHO")  
        if self.settings.grid_enabled:
            status_parts.append("GRID")
        
        if not status_parts:
            return "No constraints"
        
        return " | ".join(status_parts)
    
    def _clear_cache(self) -> None:
        """Очистка кэша при изменении настроек"""
        self._last_snap_result = None
        self._last_snap_input = None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики для отладки"""
        return self.stats.copy()


# =============================================================================
# УТИЛИТЫ И ФАБРИЧНЫЕ ФУНКЦИИ
# =============================================================================

def create_snap_system(geometry_data: Dict[str, List[Dict]], 
                      settings: Optional[SnapSettings] = None) -> SnapSystem:
    """
    Создание полной системы привязок с настройками по умолчанию
    
    Args:
        geometry_data: Геометрические данные для привязки
        settings: Настройки системы (опционально)
        
    Returns:
        Настроенная система привязок
    """
    snap_system = SnapSystem(settings)
    
    # Добавляем геометрического поставщика
    geometry_provider = GeometrySnapProvider(geometry_data)
    snap_system.add_provider(geometry_provider)
    
    # Добавляем поставщика сетки
    grid_provider = GridSnapProvider(
        grid_size=settings.grid_size if settings else 1.0,
        origin=settings.grid_origin if settings else (0.0, 0.0)
    )
    snap_system.add_provider(grid_provider)
    
    print("✅ Создана полная система привязок")
    return snap_system


def create_snap_settings_from_legacy(legacy_settings: Dict[str, Any]) -> SnapSettings:
    """
    Создание настроек привязки из legacy конфигурации
    
    Портирует настройки из старой системы в новую структуру.
    """
    settings = SnapSettings()
    
    # Основные переключатели
    settings.snap_enabled = legacy_settings.get('snap_enabled', True)
    settings.ortho_enabled = legacy_settings.get('ortho_enabled', False)
    settings.grid_enabled = legacy_settings.get('grid_enabled', False)
    
    # Допуски
    settings.vertex_tolerance = legacy_settings.get('vertex_tolerance', 10.0)
    settings.edge_tolerance = legacy_settings.get('edge_tolerance', 8.0)
    
    # Сетка
    settings.grid_size = legacy_settings.get('grid_size', 1.0)
    
    return settings


# =============================================================================
# ЭКСПОРТ ПУБЛИЧНЫХ ИНТЕРФЕЙСОВ  
# =============================================================================

__all__ = [
    'SnapSystem',
    'SnapSettings', 
    'SnapPoint',
    'SnapType',
    'OrthogonalDirection',
    'ISnapProvider',
    'GeometrySnapProvider',
    'GridSnapProvider',
    'create_snap_system',
    'create_snap_settings_from_legacy'
]