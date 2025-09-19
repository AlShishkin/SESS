# -*- coding: utf-8 -*-
"""
Performance - система мониторинга и оптимизации производительности для BESS_Geometry

Этот модуль обеспечивает высокую производительность при работе с большими объемами
геометрических данных зданий. Включает системы кэширования, пространственного
индексирования и мониторинга производительности для обеспечения отзывчивости
пользовательского интерфейса при работе с комплексными BIM-моделями.

Основные компоненты:
- PerformanceMonitor: отслеживание времени выполнения операций
- RenderCache: кэширование результатов отрисовки для повторного использования  
- SpatialIndex: пространственное индексирование для быстрого поиска элементов
- GeometryOptimizer: оптимизация геометрических операций
"""

import time
import threading
import weakref
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from functools import wraps
import hashlib
import pickle
import math

from geometry_utils import bounds, polygon_area


@dataclass
class PerformanceMetrics:
    """Структура для хранения метрик производительности"""
    operation_name: str
    execution_time: float
    memory_usage: int
    element_count: int
    timestamp: float
    additional_data: Dict[str, Any] = field(default_factory=dict)


class PerformanceMonitor:
    """
    Система мониторинга производительности операций
    
    Отслеживает время выполнения критических операций, позволяя выявлять
    узкие места в производительности и оптимизировать работу с большими
    объемами геометрических данных.
    """
    
    def __init__(self, max_history_size: int = 1000):
        """
        Инициализация монитора производительности
        
        Args:
            max_history_size: Максимальное количество записей в истории
        """
        self.metrics_history: deque = deque(maxlen=max_history_size)
        self.active_operations: Dict[str, float] = {}  # operation_id -> start_time
        self.operation_stats: Dict[str, List[float]] = defaultdict(list)  # operation_name -> [times]
        self.lock = threading.Lock()
        self._operation_counter = 0
    
    def start_operation(self, operation_name: str) -> str:
        """
        Начало отслеживания операции
        
        Args:
            operation_name: Название операции для отслеживания
            
        Returns:
            Уникальный ID операции для последующего завершения
        """
        with self.lock:
            self._operation_counter += 1
            operation_id = f"{operation_name}_{self._operation_counter}_{threading.get_ident()}"
            self.active_operations[operation_id] = time.time()
            return operation_id
    
    def end_operation(self, operation_id: str, element_count: int = 0, 
                     additional_data: Optional[Dict[str, Any]] = None) -> float:
        """
        Завершение отслеживания операции
        
        Args:
            operation_id: ID операции, полученный от start_operation
            element_count: Количество обработанных элементов
            additional_data: Дополнительные данные для анализа
            
        Returns:
            Время выполнения операции в секундах
        """
        with self.lock:
            if operation_id not in self.active_operations:
                return 0.0
            
            start_time = self.active_operations.pop(operation_id)
            execution_time = time.time() - start_time
            
            # Извлекаем название операции из ID
            operation_name = operation_id.split('_')[0]
            
            # Записываем метрики
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                execution_time=execution_time,
                memory_usage=0,  # Можно расширить для отслеживания памяти
                element_count=element_count,
                timestamp=time.time(),
                additional_data=additional_data or {}
            )
            
            self.metrics_history.append(metrics)
            self.operation_stats[operation_name].append(execution_time)
            
            # Ограничиваем размер статистики
            if len(self.operation_stats[operation_name]) > 100:
                self.operation_stats[operation_name] = self.operation_stats[operation_name][-100:]
            
            return execution_time
    
    def get_average_time(self, operation_name: str) -> float:
        """Получение среднего времени выполнения операции"""
        with self.lock:
            times = self.operation_stats.get(operation_name, [])
            return sum(times) / len(times) if times else 0.0
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Генерация отчета о производительности
        
        Returns:
            Словарь с данными о производительности различных операций
        """
        with self.lock:
            report = {
                'total_operations': len(self.metrics_history),
                'active_operations': len(self.active_operations),
                'operation_stats': {}
            }
            
            for operation_name, times in self.operation_stats.items():
                if times:
                    report['operation_stats'][operation_name] = {
                        'count': len(times),
                        'average_time': sum(times) / len(times),
                        'min_time': min(times),
                        'max_time': max(times),
                        'total_time': sum(times)
                    }
            
            return report


def performance_monitor(operation_name: str = None):
    """
    Декоратор для автоматического мониторинга производительности функций
    
    Args:
        operation_name: Название операции (по умолчанию - имя функции)
        
    Example:
        @performance_monitor("draw_geometry")
        def draw_complex_geometry(elements):
            # Сложная операция отрисовки
            pass
    """
    def decorator(func: Callable) -> Callable:
        nonlocal operation_name
        if operation_name is None:
            operation_name = func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            monitor = _get_global_monitor()
            op_id = monitor.start_operation(operation_name)
            try:
                result = func(*args, **kwargs)
                # Пытаемся определить количество элементов из результата
                element_count = 0
                if isinstance(result, (list, tuple, set)):
                    element_count = len(result)
                elif hasattr(result, '__len__'):
                    try:
                        element_count = len(result)
                    except:
                        pass
                
                monitor.end_operation(op_id, element_count)
                return result
            except Exception as e:
                monitor.end_operation(op_id, 0, {'error': str(e)})
                raise
        return wrapper
    return decorator


class RenderCache:
    """
    Система кэширования результатов отрисовки геометрических элементов
    
    Кэширует сложные вычисления отрисовки для повторного использования,
    что критично важно при панорамировании и масштабировании больших
    планов зданий с сотнями помещений.
    """
    
    def __init__(self, max_cache_size: int = 1000, enable_compression: bool = True):
        """
        Инициализация кэша отрисовки
        
        Args:
            max_cache_size: Максимальное количество кэшированных элементов
            enable_compression: Использовать ли сжатие данных для экономии памяти
        """
        self.cache: Dict[str, Any] = {}
        self.access_times: Dict[str, float] = {}
        self.max_cache_size = max_cache_size
        self.enable_compression = enable_compression
        self.cache_hits = 0
        self.cache_misses = 0
        self.lock = threading.Lock()
    
    def _generate_cache_key(self, element_data: Dict, render_params: Dict) -> str:
        """
        Генерация ключа кэша на основе данных элемента и параметров отрисовки
        
        Args:
            element_data: Данные геометрического элемента
            render_params: Параметры отрисовки (масштаб, стиль и т.д.)
            
        Returns:
            Хэш-ключ для кэширования
        """
        # Создаем стабильное представление данных для хэширования
        cache_data = {
            'geometry': element_data.get('outer_xy_m', []),
            'holes': element_data.get('inner_loops_xy_m', []),
            'element_type': element_data.get('element_type', 'unknown'),
            'scale': render_params.get('scale', 1.0),
            'style': render_params.get('style', {}),
            'viewport': render_params.get('viewport', (0, 0, 1000, 1000))
        }
        
        # Сериализуем данные и создаем хэш
        serialized = pickle.dumps(cache_data, protocol=pickle.HIGHEST_PROTOCOL)
        return hashlib.md5(serialized).hexdigest()
    
    def get(self, element_data: Dict, render_params: Dict) -> Optional[Any]:
        """
        Получение кэшированного результата отрисовки
        
        Args:
            element_data: Данные элемента
            render_params: Параметры отрисовки
            
        Returns:
            Кэшированные данные отрисовки или None если не найдено
        """
        with self.lock:
            cache_key = self._generate_cache_key(element_data, render_params)
            
            if cache_key in self.cache:
                self.access_times[cache_key] = time.time()
                self.cache_hits += 1
                
                cached_data = self.cache[cache_key]
                if self.enable_compression and isinstance(cached_data, bytes):
                    return pickle.loads(cached_data)
                return cached_data
            
            self.cache_misses += 1
            return None
    
    def put(self, element_data: Dict, render_params: Dict, render_result: Any) -> None:
        """
        Сохранение результата отрисовки в кэш
        
        Args:
            element_data: Данные элемента
            render_params: Параметры отрисовки
            render_result: Результат отрисовки для кэширования
        """
        with self.lock:
            cache_key = self._generate_cache_key(element_data, render_params)
            
            # Управление размером кэша - удаляем старые элементы
            if len(self.cache) >= self.max_cache_size:
                self._evict_old_entries()
            
            # Сохраняем данные с возможным сжатием
            if self.enable_compression:
                try:
                    compressed_data = pickle.dumps(render_result, protocol=pickle.HIGHEST_PROTOCOL)
                    self.cache[cache_key] = compressed_data
                except:
                    # Если сжатие не удалось, сохраняем как есть
                    self.cache[cache_key] = render_result
            else:
                self.cache[cache_key] = render_result
            
            self.access_times[cache_key] = time.time()
    
    def _evict_old_entries(self) -> None:
        """Удаление старых записей из кэша для освобождения места"""
        if not self.access_times:
            return
        
        # Удаляем 20% самых старых записей
        entries_to_remove = max(1, len(self.cache) // 5)
        
        # Сортируем по времени доступа и удаляем самые старые
        sorted_entries = sorted(self.access_times.items(), key=lambda x: x[1])
        
        for cache_key, _ in sorted_entries[:entries_to_remove]:
            self.cache.pop(cache_key, None)
            self.access_times.pop(cache_key, None)
    
    def clear(self) -> None:
        """Очистка всего кэша"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            self.cache_hits = 0
            self.cache_misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша"""
        with self.lock:
            total_requests = self.cache_hits + self.cache_misses
            hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0
            
            return {
                'cache_size': len(self.cache),
                'max_cache_size': self.max_cache_size,
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'hit_rate': hit_rate,
                'compression_enabled': self.enable_compression
            }


class SpatialIndex:
    """
    Система пространственного индексирования для быстрого поиска элементов
    
    Использует сетчатую структуру данных для эффективного поиска геометрических
    элементов в заданной области. Критично важно для производительности при
    работе с большими зданиями, содержащими тысячи помещений.
    """
    
    def __init__(self, grid_size: float = 10.0, auto_resize: bool = True):
        """
        Инициализация пространственного индекса
        
        Args:
            grid_size: Размер ячейки сетки в метрах
            auto_resize: Автоматически изменять размер сетки при необходимости
        """
        self.grid_size = grid_size
        self.auto_resize = auto_resize
        self.grid: Dict[Tuple[int, int], Set[str]] = defaultdict(set)
        self.element_bounds: Dict[str, Tuple[float, float, float, float]] = {}
        self.total_bounds: Optional[Tuple[float, float, float, float]] = None
        self.lock = threading.Lock()
    
    def _get_grid_coordinates(self, x: float, y: float) -> Tuple[int, int]:
        """Получение координат ячейки сетки для точки"""
        grid_x = int(x // self.grid_size)
        grid_y = int(y // self.grid_size)
        return (grid_x, grid_y)
    
    def _get_cells_for_bounds(self, min_x: float, min_y: float, 
                             max_x: float, max_y: float) -> Set[Tuple[int, int]]:
        """Получение всех ячеек сетки, пересекающихся с прямоугольником"""
        min_grid_x = int(min_x // self.grid_size)
        min_grid_y = int(min_y // self.grid_size)
        max_grid_x = int(max_x // self.grid_size)
        max_grid_y = int(max_y // self.grid_size)
        
        cells = set()
        for grid_x in range(min_grid_x, max_grid_x + 1):
            for grid_y in range(min_grid_y, max_grid_y + 1):
                cells.add((grid_x, grid_y))
        
        return cells
    
    def add_element(self, element_id: str, geometry_points: List[Tuple[float, float]]) -> None:
        """
        Добавление элемента в пространственный индекс
        
        Args:
            element_id: Уникальный ID элемента
            geometry_points: Точки геометрии элемента
        """
        if not geometry_points:
            return
        
        element_bounds_rect = bounds(geometry_points)
        if not element_bounds_rect:
            return
        
        with self.lock:
            # Удаляем элемент если он уже существует
            self.remove_element(element_id)
            
            min_x, min_y, max_x, max_y = element_bounds_rect
            self.element_bounds[element_id] = element_bounds_rect
            
            # Обновляем общие границы
            if self.total_bounds is None:
                self.total_bounds = element_bounds_rect
            else:
                total_min_x, total_min_y, total_max_x, total_max_y = self.total_bounds
                self.total_bounds = (
                    min(total_min_x, min_x),
                    min(total_min_y, min_y),
                    max(total_max_x, max_x),
                    max(total_max_y, max_y)
                )
            
            # Добавляем элемент во все пересекающиеся ячейки
            cells = self._get_cells_for_bounds(min_x, min_y, max_x, max_y)
            for cell in cells:
                self.grid[cell].add(element_id)
    
    def remove_element(self, element_id: str) -> None:
        """
        Удаление элемента из пространственного индекса
        
        Args:
            element_id: ID элемента для удаления
        """
        with self.lock:
            if element_id not in self.element_bounds:
                return
            
            # Удаляем элемент из всех ячеек
            for cell_elements in self.grid.values():
                cell_elements.discard(element_id)
            
            # Удаляем границы элемента
            del self.element_bounds[element_id]
            
            # Очищаем пустые ячейки
            empty_cells = [cell for cell, elements in self.grid.items() if not elements]
            for cell in empty_cells:
                del self.grid[cell]
    
    def query_region(self, min_x: float, min_y: float, 
                    max_x: float, max_y: float) -> Set[str]:
        """
        Поиск всех элементов в заданном прямоугольнике
        
        Args:
            min_x, min_y, max_x, max_y: Границы области поиска
            
        Returns:
            Множество ID элементов в заданной области
        """
        with self.lock:
            cells = self._get_cells_for_bounds(min_x, min_y, max_x, max_y)
            
            # Собираем всех кандидатов из ячеек
            candidates = set()
            for cell in cells:
                candidates.update(self.grid.get(cell, set()))
            
            # Фильтруем кандидатов по точному пересечению границ
            result = set()
            for element_id in candidates:
                if element_id in self.element_bounds:
                    elem_min_x, elem_min_y, elem_max_x, elem_max_y = self.element_bounds[element_id]
                    
                    # Проверяем пересечение прямоугольников
                    if not (elem_max_x < min_x or elem_min_x > max_x or 
                           elem_max_y < min_y or elem_min_y > max_y):
                        result.add(element_id)
            
            return result
    
    def query_point(self, x: float, y: float, radius: float = 0.0) -> Set[str]:
        """
        Поиск элементов в точке или в радиусе от точки
        
        Args:
            x, y: Координаты точки
            radius: Радиус поиска
            
        Returns:
            Множество ID элементов
        """
        return self.query_region(x - radius, y - radius, x + radius, y + radius)
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики пространственного индекса"""
        with self.lock:
            non_empty_cells = sum(1 for elements in self.grid.values() if elements)
            total_elements = len(self.element_bounds)
            
            return {
                'grid_size': self.grid_size,
                'total_cells': len(self.grid),
                'non_empty_cells': non_empty_cells,
                'total_elements': total_elements,
                'total_bounds': self.total_bounds,
                'auto_resize': self.auto_resize
            }


class GeometryOptimizer:
    """
    Система оптимизации геометрических операций
    
    Содержит алгоритмы для ускорения обработки геометрии, включая
    упрощение полигонов, пакетную обработку и оптимизацию отрисовки.
    """
    
    @staticmethod
    def batch_bounds_calculation(elements: List[Dict]) -> Dict[str, Tuple[float, float, float, float]]:
        """
        Пакетное вычисление границ для множества элементов
        
        Args:
            elements: Список элементов с геометрией
            
        Returns:
            Словарь {element_id: bounds}
        """
        result = {}
        
        for element in elements:
            element_id = element.get('id', '')
            geometry = element.get('outer_xy_m', [])
            
            if geometry:
                element_bounds = bounds(geometry)
                if element_bounds:
                    result[element_id] = element_bounds
        
        return result
    
    @staticmethod
    def filter_visible_elements(elements: List[Dict], viewport: Tuple[float, float, float, float]) -> List[Dict]:
        """
        Фильтрация элементов, видимых в текущем окне просмотра
        
        Args:
            elements: Список всех элементов
            viewport: Границы видимого окна (min_x, min_y, max_x, max_y)
            
        Returns:
            Список элементов, пересекающихся с окном просмотра
        """
        vp_min_x, vp_min_y, vp_max_x, vp_max_y = viewport
        visible_elements = []
        
        for element in elements:
            geometry = element.get('outer_xy_m', [])
            if not geometry:
                continue
            
            element_bounds = bounds(geometry)
            if not element_bounds:
                continue
            
            elem_min_x, elem_min_y, elem_max_x, elem_max_y = element_bounds
            
            # Проверяем пересечение с областью просмотра
            if not (elem_max_x < vp_min_x or elem_min_x > vp_max_x or 
                   elem_max_y < vp_min_y or elem_min_y > vp_max_y):
                visible_elements.append(element)
        
        return visible_elements
    
    @staticmethod
    def optimize_render_order(elements: List[Dict]) -> List[Dict]:
        """
        Оптимизация порядка отрисовки элементов
        
        Сортирует элементы для минимизации переключений состояния отрисовки
        и оптимизации производительности графической системы.
        
        Args:
            elements: Список элементов для сортировки
            
        Returns:
            Отсортированный список элементов
        """
        # Сортируем по типу элемента и размеру (большие элементы сначала)
        def sort_key(element):
            element_type = element.get('element_type', 'unknown')
            geometry = element.get('outer_xy_m', [])
            area = abs(polygon_area(geometry)) if geometry else 0
            
            # Приоритет типов: areas -> rooms -> openings -> shafts
            type_priority = {
                'area': 0,
                'room': 1, 
                'opening': 2,
                'shaft': 3
            }
            
            priority = type_priority.get(element_type, 99)
            return (priority, -area)  # Отрицательная площадь для сортировки по убыванию
        
        return sorted(elements, key=sort_key)


# Глобальный экземпляр монитора производительности
_global_monitor: Optional[PerformanceMonitor] = None
_global_monitor_lock = threading.Lock()


def _get_global_monitor() -> PerformanceMonitor:
    """Получение глобального экземпляра монитора производительности"""
    global _global_monitor
    
    if _global_monitor is None:
        with _global_monitor_lock:
            if _global_monitor is None:
                _global_monitor = PerformanceMonitor()
    
    return _global_monitor


def get_performance_stats() -> Dict[str, Any]:
    """Получение глобальной статистики производительности"""
    monitor = _get_global_monitor()
    return monitor.get_performance_report()


def clear_performance_history() -> None:
    """Очистка истории производительности"""
    monitor = _get_global_monitor()
    with monitor.lock:
        monitor.metrics_history.clear()
        monitor.operation_stats.clear()


# Фабричные функции для создания компонентов
def create_render_cache(max_size: int = 1000, enable_compression: bool = True) -> RenderCache:
    """Создание экземпляра кэша отрисовки с настройками"""
    return RenderCache(max_size, enable_compression)


def create_spatial_index(grid_size: float = 10.0) -> SpatialIndex:
    """Создание экземпляра пространственного индекса"""
    return SpatialIndex(grid_size)