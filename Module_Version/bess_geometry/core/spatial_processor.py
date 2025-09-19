# -*- coding: utf-8 -*-
"""
SpatialProcessor - геометрический процессор для пространственного анализа зданий

Этот модуль содержит ядро системы обработки геометрических данных зданий.
SpatialProcessor понимает пространственные отношения между элементами здания
и выполняет сложные расчеты, необходимые для энергетического анализа.

Ключевые возможности:
- Анализ смежности помещений и автоматическое выявление связей
- Валидация геометрической корректности планов зданий
- Расчет площадей, объемов и других геометрических характеристик
- Оптимизация геометрии для улучшения производительности
- Подготовка данных для экспорта в специализированные программы
"""

import math
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Set, Union, Any
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

# Добавляем корневую директорию проекта в путь для импорта утилит
current_dir = Path(__file__).parent.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Импортируем наши геометрические утилиты
from geometry_utils import (
    centroid_xy, bounds, r2, polygon_area, 
    point_in_polygon, distance_point_to_line, 
    line_intersection, simplify_polygon
)
from performance import PerformanceMonitor, performance_monitor


class ElementType(Enum):
    """Типы геометрических элементов здания"""
    ROOM = "room"           # Помещение
    AREA = "area"           # Область/зона
    OPENING = "opening"     # Проем (дверь, окно)
    SHAFT = "shaft"         # Шахта (лифт, вентиляция)
    WALL = "wall"           # Стена
    SLAB = "slab"           # Перекрытие


class AdjacencyType(Enum):
    """Типы смежности между элементами"""
    DIRECT = "direct"       # Прямая смежность (общая стена)
    OPENING = "opening"     # Смежность через проем
    VERTICAL = "vertical"   # Вертикальная смежность (между этажами)
    INDIRECT = "indirect"   # Косвенная смежность


@dataclass
class GeometricProperties:
    """Геометрические свойства элемента здания"""
    area_m2: float                               # Площадь в квадратных метрах
    perimeter_m: float                          # Периметр в метрах
    centroid: Tuple[float, float]               # Центроид (центр масс)
    bounding_box: Tuple[float, float, float, float]  # Ограничивающий прямоугольник
    is_clockwise: bool                          # Направление обхода контура
    is_self_intersecting: bool                  # Наличие самопересечений
    complexity_factor: float                    # Коэффициент сложности геометрии
    volume_m3: Optional[float] = None           # Объем (если известна высота)
    height_m: Optional[float] = None            # Высота элемента


@dataclass
class SpatialRelationship:
    """Пространственное отношение между двумя элементами"""
    element1_id: str                            # ID первого элемента
    element2_id: str                            # ID второго элемента
    relationship_type: AdjacencyType            # Тип смежности
    shared_boundary_length_m: float             # Длина общей границы
    distance_m: float                           # Расстояние между центроидами
    contact_points: List[Tuple[float, float]]   # Точки контакта/пересечения
    confidence: float = 1.0                     # Уверенность в определении связи
    metadata: Dict[str, Any] = field(default_factory=dict)  # Дополнительные данные


class GeometryValidator:
    """
    Валидатор геометрических данных для архитектурного анализа
    
    Этот класс проверяет корректность геометрических данных зданий,
    выявляет проблемы и предлагает способы их устранения.
    """
    
    def __init__(self, tolerance: float = 0.01):
        """
        Инициализация валидатора
        
        Args:
            tolerance: Допуск для геометрических вычислений (в метрах)
        """
        self.tolerance = tolerance
        self.validation_history = []
    
    @performance_monitor("geometry_validation")
    def validate_polygon(self, points: List[Tuple[float, float]], 
                        element_type: ElementType = ElementType.ROOM) -> Dict[str, Any]:
        """
        Комплексная валидация полигона для архитектурного использования
        
        Args:
            points: Точки полигона в порядке обхода
            element_type: Тип архитектурного элемента
            
        Returns:
            Словарь с результатами валидации и рекомендациями
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'recommendations': [],
            'metrics': {}
        }
        
        # Базовые проверки структуры данных
        if not points or len(points) < 3:
            validation_result['is_valid'] = False
            validation_result['errors'].append("Недостаточно точек для формирования полигона")
            return validation_result
        
        # Проверка на некорректные координаты
        for i, (x, y) in enumerate(points):
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                validation_result['errors'].append(f"Некорректные координаты в точке {i}: ({x}, {y})")
                validation_result['is_valid'] = False
                continue
            
            if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
                validation_result['errors'].append(f"Недопустимые значения координат в точке {i}: ({x}, {y})")
                validation_result['is_valid'] = False
        
        if not validation_result['is_valid']:
            return validation_result
        
        # Геометрические проверки
        area = abs(polygon_area(points))
        validation_result['metrics']['area_m2'] = area
        
        # Проверка минимальной площади
        min_area_thresholds = {
            ElementType.ROOM: 0.5,      # Минимум 0.5 м² для помещения
            ElementType.AREA: 1.0,      # Минимум 1.0 м² для области
            ElementType.OPENING: 0.01,  # Минимум 0.01 м² для проема
            ElementType.SHAFT: 0.1      # Минимум 0.1 м² для шахты
        }
        
        min_area = min_area_thresholds.get(element_type, 0.1)
        if area < min_area:
            validation_result['warnings'].append(
                f"Площадь {area:.3f} м² меньше рекомендуемого минимума {min_area} м² для {element_type.value}"
            )
        
        # Проверка на самопересечения
        if self._check_self_intersection(points):
            validation_result['errors'].append("Обнаружены самопересечения полигона")
            validation_result['is_valid'] = False
        
        # Проверка направления обхода
        is_clockwise = polygon_area(points) < 0
        validation_result['metrics']['is_clockwise'] = is_clockwise
        
        if is_clockwise:
            validation_result['recommendations'].append(
                "Рекомендуется обход против часовой стрелки для внешних контуров"
            )
        
        # Проверка сложности геометрии
        complexity = self._calculate_complexity(points)
        validation_result['metrics']['complexity_factor'] = complexity
        
        if complexity < 0.3:
            validation_result['warnings'].append(
                "Сложная геометрия может влиять на производительность"
            )
        
        # Проверка на вырожденные сегменты
        degenerate_segments = self._find_degenerate_segments(points)
        if degenerate_segments:
            validation_result['warnings'].append(
                f"Обнаружены {len(degenerate_segments)} вырожденных сегментов"
            )
            validation_result['recommendations'].append("Рассмотрите упрощение геометрии")
        
        return validation_result
    
    def _check_self_intersection(self, points: List[Tuple[float, float]]) -> bool:
        """Проверка полигона на самопересечения"""
        n = len(points)
        if n < 4:
            return False
        
        # Проверяем каждую пару несмежных сегментов
        for i in range(n):
            for j in range(i + 2, n):
                # Избегаем проверки последнего сегмента с первым
                if i == 0 and j == n - 1:
                    continue
                
                p1 = points[i]
                p2 = points[(i + 1) % n]
                p3 = points[j]
                p4 = points[(j + 1) % n]
                
                if line_intersection(p1, p2, p3, p4):
                    return True
        
        return False
    
    def _calculate_complexity(self, points: List[Tuple[float, float]]) -> float:
        """
        Вычисление коэффициента сложности геометрии
        
        Коэффициент от 0 до 1, где 1 означает простую геометрию (близкую к окружности),
        а 0 означает очень сложную геометрию с множеством углов и неровностей.
        """
        if len(points) < 3:
            return 0.0
        
        area = abs(polygon_area(points))
        if area == 0:
            return 0.0
        
        perimeter = self._calculate_perimeter(points)
        if perimeter == 0:
            return 0.0
        
        # Изопериметрический коэффициент (отношение к окружности)
        circle_area = (perimeter ** 2) / (4 * math.pi)
        complexity = area / circle_area if circle_area > 0 else 0.0
        
        return min(1.0, complexity)
    
    def _calculate_perimeter(self, points: List[Tuple[float, float]]) -> float:
        """Вычисление периметра полигона"""
        if len(points) < 2:
            return 0.0
        
        perimeter = 0.0
        n = len(points)
        
        for i in range(n):
            p1 = points[i]
            p2 = points[(i + 1) % n]
            
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            perimeter += math.sqrt(dx * dx + dy * dy)
        
        return perimeter
    
    def _find_degenerate_segments(self, points: List[Tuple[float, float]]) -> List[int]:
        """Поиск вырожденных сегментов (слишком коротких или коллинеарных)"""
        degenerate = []
        n = len(points)
        
        for i in range(n):
            p1 = points[i]
            p2 = points[(i + 1) % n]
            
            # Проверка на слишком короткий сегмент
            distance = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            if distance < self.tolerance:
                degenerate.append(i)
        
        return degenerate


class SpatialCalculator:
    """
    Калькулятор пространственных характеристик архитектурных элементов
    
    Этот класс выполняет точные геометрические расчеты для элементов зданий,
    включая площади, объемы, расстояния и пространственные отношения.
    """
    
    def __init__(self, default_height: float = 3.0):
        """
        Инициализация калькулятора
        
        Args:
            default_height: Высота помещений по умолчанию (в метрах)
        """
        self.default_height = default_height
        self.calculation_cache = {}
    
    @performance_monitor("calculate_properties")
    def calculate_geometric_properties(self, points: List[Tuple[float, float]], 
                                     height: Optional[float] = None) -> GeometricProperties:
        """
        Расчет всех геометрических свойств элемента
        
        Args:
            points: Точки контура элемента
            height: Высота элемента (если не указана, используется значение по умолчанию)
            
        Returns:
            Объект с полным набором геометрических характеристик
        """
        # Создаем ключ для кэширования
        cache_key = (tuple(tuple(p) for p in points), height)
        if cache_key in self.calculation_cache:
            return self.calculation_cache[cache_key]
        
        # Основные вычисления
        area = abs(polygon_area(points))
        perimeter = self._calculate_perimeter(points)
        centroid = centroid_xy(points) or (0.0, 0.0)
        bounding_box = bounds(points) or (0.0, 0.0, 0.0, 0.0)
        
        # Направление обхода
        is_clockwise = polygon_area(points) < 0
        
        # Проверка на самопересечения (упрощенная)
        is_self_intersecting = self._quick_self_intersection_check(points)
        
        # Коэффициент сложности
        complexity_factor = self._calculate_complexity_factor(points, area, perimeter)
        
        # Объем (если известна высота)
        element_height = height or self.default_height
        volume = area * element_height if area > 0 else None
        
        properties = GeometricProperties(
            area_m2=r2(area),
            perimeter_m=r2(perimeter),
            centroid=(r2(centroid[0]), r2(centroid[1])),
            bounding_box=(r2(bounding_box[0]), r2(bounding_box[1]), 
                         r2(bounding_box[2]), r2(bounding_box[3])),
            is_clockwise=is_clockwise,
            is_self_intersecting=is_self_intersecting,
            complexity_factor=r2(complexity_factor),
            volume_m3=r2(volume) if volume else None,
            height_m=r2(element_height) if height else None
        )
        
        # Кэшируем результат
        self.calculation_cache[cache_key] = properties
        
        return properties
    
    def calculate_adjacency(self, element1_points: List[Tuple[float, float]],
                           element2_points: List[Tuple[float, float]],
                           tolerance: float = 0.1) -> Optional[SpatialRelationship]:
        """
        Анализ смежности между двумя элементами
        
        Args:
            element1_points: Точки первого элемента
            element2_points: Точки второго элемента  
            tolerance: Допуск для определения смежности (в метрах)
            
        Returns:
            Объект с описанием пространственного отношения или None
        """
        # Вычисляем центроиды элементов
        centroid1 = centroid_xy(element1_points)
        centroid2 = centroid_xy(element2_points)
        
        if not centroid1 or not centroid2:
            return None
        
        # Расстояние между центроидами
        distance = math.sqrt((centroid2[0] - centroid1[0])**2 + 
                           (centroid2[1] - centroid1[1])**2)
        
        # Поиск общих границ
        shared_boundary_length = self._calculate_shared_boundary(
            element1_points, element2_points, tolerance
        )
        
        # Определяем тип смежности
        if shared_boundary_length > tolerance:
            relationship_type = AdjacencyType.DIRECT
            confidence = min(1.0, shared_boundary_length / tolerance)
        else:
            # Проверяем близость элементов
            if distance <= tolerance * 2:
                relationship_type = AdjacencyType.INDIRECT
                confidence = max(0.1, 1.0 - (distance / (tolerance * 2)))
            else:
                return None  # Элементы не смежны
        
        # Поиск точек контакта
        contact_points = self._find_contact_points(
            element1_points, element2_points, tolerance
        )
        
        return SpatialRelationship(
            element1_id="",  # Будет заполнено вызывающим кодом
            element2_id="",  # Будет заполнено вызывающим кодом
            relationship_type=relationship_type,
            shared_boundary_length_m=r2(shared_boundary_length),
            distance_m=r2(distance),
            contact_points=[(r2(x), r2(y)) for x, y in contact_points],
            confidence=r2(confidence)
        )
    
    def _calculate_perimeter(self, points: List[Tuple[float, float]]) -> float:
        """Вычисление периметра полигона"""
        if len(points) < 2:
            return 0.0
        
        perimeter = 0.0
        n = len(points)
        
        for i in range(n):
            p1 = points[i]
            p2 = points[(i + 1) % n]
            
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            perimeter += math.sqrt(dx * dx + dy * dy)
        
        return perimeter
    
    def _quick_self_intersection_check(self, points: List[Tuple[float, float]]) -> bool:
        """Быстрая проверка на самопересечения (упрощенная версия)"""
        # Для производительности делаем только базовую проверку
        n = len(points)
        if n < 4:
            return False
        
        # Проверяем только несколько ключевых сегментов
        for i in range(0, n, max(1, n // 10)):  # Проверяем каждый 10-й сегмент
            for j in range(i + 2, n, max(1, n // 10)):
                if i == 0 and j == n - 1:
                    continue
                
                p1 = points[i]
                p2 = points[(i + 1) % n]
                p3 = points[j]
                p4 = points[(j + 1) % n]
                
                if line_intersection(p1, p2, p3, p4):
                    return True
        
        return False
    
    def _calculate_complexity_factor(self, points: List[Tuple[float, float]], 
                                   area: float, perimeter: float) -> float:
        """Вычисление коэффициента сложности геометрии"""
        if area <= 0 or perimeter <= 0:
            return 0.0
        
        # Изопериметрическое отношение
        circle_area = (perimeter ** 2) / (4 * math.pi)
        complexity = area / circle_area if circle_area > 0 else 0.0
        
        return min(1.0, max(0.0, complexity))
    
    def _calculate_shared_boundary(self, points1: List[Tuple[float, float]],
                                 points2: List[Tuple[float, float]], 
                                 tolerance: float) -> float:
        """Вычисление длины общей границы между двумя полигонами"""
        shared_length = 0.0
        
        # Простой алгоритм: ищем близкие сегменты
        n1, n2 = len(points1), len(points2)
        
        for i in range(n1):
            seg1_start = points1[i]
            seg1_end = points1[(i + 1) % n1]
            
            for j in range(n2):
                seg2_start = points2[j]
                seg2_end = points2[(j + 1) % n2]
                
                # Проверяем близость сегментов
                if self._segments_are_close(seg1_start, seg1_end, 
                                          seg2_start, seg2_end, tolerance):
                    # Вычисляем длину перекрытия
                    overlap_length = self._calculate_segment_overlap(
                        seg1_start, seg1_end, seg2_start, seg2_end
                    )
                    shared_length += overlap_length
        
        return shared_length
    
    def _segments_are_close(self, seg1_start: Tuple[float, float], seg1_end: Tuple[float, float],
                           seg2_start: Tuple[float, float], seg2_end: Tuple[float, float],
                           tolerance: float) -> bool:
        """Проверка близости двух сегментов"""
        # Упрощенная проверка: расстояние между центрами сегментов
        center1 = ((seg1_start[0] + seg1_end[0]) / 2, (seg1_start[1] + seg1_end[1]) / 2)
        center2 = ((seg2_start[0] + seg2_end[0]) / 2, (seg2_start[1] + seg2_end[1]) / 2)
        
        distance = math.sqrt((center2[0] - center1[0])**2 + (center2[1] - center1[1])**2)
        
        return distance <= tolerance
    
    def _calculate_segment_overlap(self, seg1_start: Tuple[float, float], seg1_end: Tuple[float, float],
                                 seg2_start: Tuple[float, float], seg2_end: Tuple[float, float]) -> float:
        """Вычисление длины перекрытия двух сегментов"""
        # Упрощенная реализация - возвращаем среднюю длину сегментов
        len1 = math.sqrt((seg1_end[0] - seg1_start[0])**2 + (seg1_end[1] - seg1_start[1])**2)
        len2 = math.sqrt((seg2_end[0] - seg2_start[0])**2 + (seg2_end[1] - seg2_start[1])**2)
        
        return (len1 + len2) / 2
    
    def _find_contact_points(self, points1: List[Tuple[float, float]],
                           points2: List[Tuple[float, float]], 
                           tolerance: float) -> List[Tuple[float, float]]:
        """Поиск точек контакта между двумя полигонами"""
        contact_points = []
        
        # Простой алгоритм: ищем близкие точки
        for p1 in points1:
            for p2 in points2:
                distance = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                if distance <= tolerance:
                    # Добавляем среднюю точку как точку контакта
                    contact_point = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
                    contact_points.append(contact_point)
        
        return contact_points[:10]  # Ограничиваем количество точек


class SpatialProcessor:
    """
    Основной геометрический процессор системы BESS_Geometry
    
    Этот класс является центральным компонентом для обработки геометрических
    данных зданий. Он координирует работу валидатора и калькулятора,
    предоставляя высокоуровневый интерфейс для пространственного анализа.
    """
    
    def __init__(self, tolerance: float = 0.01, default_height: float = 3.0):
        """
        Инициализация пространственного процессора
        
        Args:
            tolerance: Геометрический допуск (в метрах)
            default_height: Высота помещений по умолчанию (в метрах)
        """
        self.tolerance = tolerance
        self.validator = GeometryValidator(tolerance)
        self.calculator = SpatialCalculator(default_height)
        self.performance_monitor = PerformanceMonitor()
        
        # Кэш для результатов обработки
        self.processing_cache = {}
        self.adjacency_cache = {}
        
        print(f"✅ SpatialProcessor инициализирован (допуск: {tolerance}м, высота: {default_height}м)")
    
    @performance_monitor("process_elements")
    def process_building_elements(self, elements: List[Dict]) -> Dict[str, Any]:
        """
        Комплексная обработка элементов здания
        
        Args:
            elements: Список элементов здания с геометрией
            
        Returns:
            Словарь с результатами обработки, включая валидацию,
            геометрические свойства и пространственные отношения
        """
        processing_result = {
            'processed_elements': [],
            'validation_summary': {'valid': 0, 'invalid': 0, 'warnings': 0},
            'spatial_relationships': [],
            'geometry_statistics': {},
            'processing_errors': []
        }
        
        print(f"🔄 Обработка {len(elements)} элементов здания...")
        
        # Обрабатываем каждый элемент
        for i, element in enumerate(elements):
            try:
                processed_element = self._process_single_element(element, i)
                processing_result['processed_elements'].append(processed_element)
                
                # Обновляем статистику валидации
                if processed_element['validation']['is_valid']:
                    processing_result['validation_summary']['valid'] += 1
                else:
                    processing_result['validation_summary']['invalid'] += 1
                
                if processed_element['validation']['warnings']:
                    processing_result['validation_summary']['warnings'] += 1
                    
            except Exception as e:
                error_msg = f"Ошибка обработки элемента {i}: {str(e)}"
                processing_result['processing_errors'].append(error_msg)
                print(f"❌ {error_msg}")
        
        # Анализируем пространственные отношения
        if len(processing_result['processed_elements']) > 1:
            relationships = self._analyze_spatial_relationships(
                processing_result['processed_elements']
            )
            processing_result['spatial_relationships'] = relationships
        
        # Вычисляем общую статистику
        processing_result['geometry_statistics'] = self._calculate_building_statistics(
            processing_result['processed_elements']
        )
        
        print(f"✅ Обработка завершена: {processing_result['validation_summary']['valid']} валидных элементов")
        
        return processing_result
    
    def _process_single_element(self, element: Dict, index: int) -> Dict[str, Any]:
        """Обработка одного элемента здания"""
        element_id = element.get('id', f'element_{index}')
        element_type_str = element.get('element_type', 'room')
        
        # Преобразуем строку в enum
        try:
            element_type = ElementType(element_type_str)
        except ValueError:
            element_type = ElementType.ROOM
        
        # Получаем геометрию
        outer_points = element.get('outer_xy_m', [])
        height = element.get('height_m') or element.get('params', {}).get('height')
        
        processed_element = {
            'id': element_id,
            'element_type': element_type.value,
            'original_data': element,
            'geometry': {
                'outer_points': outer_points,
                'inner_loops': element.get('inner_loops_xy_m', [])
            }
        }
        
        if outer_points:
            # Валидация геометрии
            validation_result = self.validator.validate_polygon(outer_points, element_type)
            processed_element['validation'] = validation_result
            
            # Расчет геометрических свойств
            if validation_result['is_valid']:
                properties = self.calculator.calculate_geometric_properties(
                    outer_points, height
                )
                processed_element['properties'] = properties
            else:
                processed_element['properties'] = None
        else:
            processed_element['validation'] = {
                'is_valid': False,
                'errors': ['Отсутствует геометрия'],
                'warnings': [],
                'recommendations': []
            }
            processed_element['properties'] = None
        
        return processed_element
    
    @performance_monitor("analyze_adjacency")
    def _analyze_spatial_relationships(self, processed_elements: List[Dict]) -> List[Dict]:
        """Анализ пространственных отношений между элементами"""
        relationships = []
        n = len(processed_elements)
        
        print(f"🔍 Анализ смежности между {n} элементами...")
        
        for i in range(n):
            for j in range(i + 1, n):
                element1 = processed_elements[i]
                element2 = processed_elements[j]
                
                # Пропускаем элементы без валидной геометрии
                if (not element1.get('properties') or 
                    not element2.get('properties')):
                    continue
                
                points1 = element1['geometry']['outer_points']
                points2 = element2['geometry']['outer_points']
                
                # Вычисляем пространственное отношение
                relationship = self.calculator.calculate_adjacency(
                    points1, points2, self.tolerance
                )
                
                if relationship:
                    relationship.element1_id = element1['id']
                    relationship.element2_id = element2['id']
                    
                    # Конвертируем в словарь для JSON-сериализации
                    relationships.append({
                        'element1_id': relationship.element1_id,
                        'element2_id': relationship.element2_id,
                        'relationship_type': relationship.relationship_type.value,
                        'shared_boundary_length_m': relationship.shared_boundary_length_m,
                        'distance_m': relationship.distance_m,
                        'contact_points': relationship.contact_points,
                        'confidence': relationship.confidence
                    })
        
        print(f"✅ Найдено {len(relationships)} пространственных связей")
        return relationships
    
    def _calculate_building_statistics(self, processed_elements: List[Dict]) -> Dict[str, Any]:
        """Вычисление общей статистики здания"""
        stats = {
            'total_elements': len(processed_elements),
            'elements_by_type': defaultdict(int),
            'total_area_m2': 0.0,
            'total_volume_m3': 0.0,
            'average_room_area_m2': 0.0,
            'building_bounds': None,
            'complexity_distribution': {'simple': 0, 'medium': 0, 'complex': 0}
        }
        
        valid_elements = [e for e in processed_elements if e.get('properties')]
        room_areas = []
        all_points = []
        
        for element in valid_elements:
            element_type = element['element_type']
            properties = element['properties']
            
            stats['elements_by_type'][element_type] += 1
            stats['total_area_m2'] += properties.area_m2
            
            if properties.volume_m3:
                stats['total_volume_m3'] += properties.volume_m3
            
            if element_type == 'room':
                room_areas.append(properties.area_m2)
            
            # Собираем все точки для общих границ здания
            outer_points = element['geometry']['outer_points']
            all_points.extend(outer_points)
            
            # Анализ сложности
            complexity = properties.complexity_factor
            if complexity > 0.7:
                stats['complexity_distribution']['simple'] += 1
            elif complexity > 0.4:
                stats['complexity_distribution']['medium'] += 1
            else:
                stats['complexity_distribution']['complex'] += 1
        
        # Средняя площадь помещений
        if room_areas:
            stats['average_room_area_m2'] = sum(room_areas) / len(room_areas)
        
        # Общие границы здания
        if all_points:
            building_bounds = bounds(all_points)
            if building_bounds:
                stats['building_bounds'] = {
                    'min_x': building_bounds[0],
                    'min_y': building_bounds[1], 
                    'max_x': building_bounds[2],
                    'max_y': building_bounds[3],
                    'width_m': building_bounds[2] - building_bounds[0],
                    'height_m': building_bounds[3] - building_bounds[1]
                }
        
        # Округляем числовые значения
        stats['total_area_m2'] = r2(stats['total_area_m2'])
        stats['total_volume_m3'] = r2(stats['total_volume_m3'])
        stats['average_room_area_m2'] = r2(stats['average_room_area_m2'])
        
        return dict(stats)  # Преобразуем defaultdict в обычный dict
    
    def optimize_geometry(self, elements: List[Dict], 
                         simplification_tolerance: float = 0.05) -> List[Dict]:
        """
        Оптимизация геометрии элементов для улучшения производительности
        
        Args:
            elements: Список элементов для оптимизации
            simplification_tolerance: Допуск для упрощения геометрии
            
        Returns:
            Список элементов с оптимизированной геометрией
        """
        optimized_elements = []
        
        for element in elements:
            outer_points = element.get('outer_xy_m', [])
            
            if len(outer_points) > 4:  # Оптимизируем только сложную геометрию
                # Упрощаем основной контур
                simplified_points = simplify_polygon(outer_points, simplification_tolerance)
                
                optimized_element = element.copy()
                optimized_element['outer_xy_m'] = simplified_points
                
                # Оптимизируем внутренние контуры
                inner_loops = element.get('inner_loops_xy_m', [])
                optimized_loops = []
                
                for loop in inner_loops:
                    if len(loop) > 4:
                        simplified_loop = simplify_polygon(loop, simplification_tolerance)
                        optimized_loops.append(simplified_loop)
                    else:
                        optimized_loops.append(loop)
                
                optimized_element['inner_loops_xy_m'] = optimized_loops
                optimized_elements.append(optimized_element)
            else:
                optimized_elements.append(element)
        
        return optimized_elements
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Получение статистики работы процессора"""
        return {
            'cache_size': len(self.processing_cache),
            'adjacency_cache_size': len(self.adjacency_cache),
            'tolerance': self.tolerance,
            'performance_stats': self.performance_monitor.get_performance_report()
        }
    
    def clear_cache(self) -> None:
        """Очистка всех кэшей процессора"""
        self.processing_cache.clear()
        self.adjacency_cache.clear()
        self.calculator.calculation_cache.clear()
        print("🧹 Кэш SpatialProcessor очищен")


# Фабричные функции для создания компонентов
def create_spatial_processor(tolerance: float = 0.01, 
                           default_height: float = 3.0) -> SpatialProcessor:
    """
    Создание экземпляра SpatialProcessor с заданными параметрами
    
    Args:
        tolerance: Геометрический допуск
        default_height: Высота помещений по умолчанию
        
    Returns:
        Настроенный экземпляр SpatialProcessor
    """
    return SpatialProcessor(tolerance, default_height)


def create_geometry_validator(tolerance: float = 0.01) -> GeometryValidator:
    """Создание валидатора геометрии"""
    return GeometryValidator(tolerance)


def create_spatial_calculator(default_height: float = 3.0) -> SpatialCalculator:
    """Создание калькулятора пространственных характеристик"""
    return SpatialCalculator(default_height)