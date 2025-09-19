# -*- coding: utf-8 -*-
"""
Geometry Utils - базовые геометрические функции для BESS_Geometry

Этот модуль содержит фундаментальные геометрические операции, которые используются
по всей системе для обработки планов зданий. Все функции оптимизированы для работы
с архитектурными данными и обеспечивают необходимую точность для BIM-приложений.

Ключевые принципы:
- Все координаты в метрах
- Обработка вырожденных случаев  
- Численная стабильность алгоритмов
- Высокая производительность для больших объемов данных
"""

import math
from typing import List, Tuple, Optional, Union

# Константы для геометрических расчетов
TOLERANCE = 1e-10  # Допуск для сравнения чисел с плавающей точкой
MIN_POLYGON_AREA = 1e-6  # Минимальная площадь полигона (1 мм²)


def r2(value: float) -> float:
    """
    Округление до 2 знаков после запятой с обработкой граничных случаев
    
    Эта функция используется для стандартизации точности координат в системе.
    Округление до сантиметров достаточно для архитектурных задач и предотвращает
    накопление ошибок вычислений с плавающей точкой.
    
    Args:
        value: Число для округления
        
    Returns:
        Округленное значение
        
    Example:
        >>> r2(3.14159)
        3.14
        >>> r2(0.009)
        0.01
    """
    if not isinstance(value, (int, float)):
        raise TypeError(f"Ожидается числовое значение, получено {type(value)}")
    
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"Некорректное значение: {value}")
    
    return round(float(value), 2)


def centroid_xy(points: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    """
    Вычисление центроида (центра масс) полигона
    
    Использует алгоритм, основанный на формуле для центроида произвольного полигона.
    Эта функция критично важна для размещения подписей помещений и определения
    точек вставки для элементов.
    
    Args:
        points: Список точек полигона [(x, y), ...]
        
    Returns:
        Координаты центроида (x, y) или None для некорректных данных
        
    Example:
        >>> points = [(0, 0), (4, 0), (4, 3), (0, 3)]  # Прямоугольник 4x3
        >>> centroid_xy(points)
        (2.0, 1.5)
    """
    if not points or len(points) < 3:
        return None
    
    # Проверяем корректность входных данных
    try:
        validated_points = []
        for x, y in points:
            if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                return None
            if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
                return None
            validated_points.append((float(x), float(y)))
        points = validated_points
    except (TypeError, ValueError):
        return None
    
    # Вычисляем площадь полигона для проверки ориентации
    area = polygon_area(points)
    if abs(area) < MIN_POLYGON_AREA:
        # Для вырожденного полигона возвращаем среднее арифметическое точек
        n = len(points)
        cx = sum(x for x, y in points) / n
        cy = sum(y for x, y in points) / n
        return (r2(cx), r2(cy))
    
    # Алгоритм вычисления центроида через интеграл
    cx = 0.0
    cy = 0.0
    
    # Добавляем замыкающую точку если её нет
    if points[0] != points[-1]:
        points = points + [points[0]]
    
    for i in range(len(points) - 1):
        x_i, y_i = points[i]
        x_next, y_next = points[i + 1]
        
        # Кросс-произведение для формулы центроида
        cross = x_i * y_next - x_next * y_i
        cx += (x_i + x_next) * cross
        cy += (y_i + y_next) * cross
    
    # Нормализуем результат
    area_factor = 6.0 * area
    if abs(area_factor) < TOLERANCE:
        # Избегаем деления на ноль
        n = len(points) - 1  # Исключаем дублированную точку
        cx = sum(x for x, y in points[:-1]) / n
        cy = sum(y for x, y in points[:-1]) / n
    else:
        cx /= area_factor
        cy /= area_factor
    
    return (r2(cx), r2(cy))


def bounds(points: List[Tuple[float, float]]) -> Optional[Tuple[float, float, float, float]]:
    """
    Вычисление ограничивающего прямоугольника (bounding box) для набора точек
    
    Эта функция используется для оптимизации отрисовки (проверка видимости),
    пространственного индексирования и определения масштаба при автоматическом
    помещении геометрии в видимую область.
    
    Args:
        points: Список точек [(x, y), ...]
        
    Returns:
        Кортеж (min_x, min_y, max_x, max_y) или None для пустого списка
        
    Example:
        >>> points = [(1, 2), (5, 1), (3, 4)]
        >>> bounds(points)
        (1.0, 1.0, 5.0, 4.0)
    """
    if not points:
        return None
    
    # Проверяем и валидируем входные данные
    valid_points = []
    for point in points:
        try:
            x, y = point
            if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                continue
            if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
                continue
            valid_points.append((float(x), float(y)))
        except (TypeError, ValueError):
            continue
    
    if not valid_points:
        return None
    
    # Находим минимальные и максимальные координаты
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    
    for x, y in valid_points:
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
    
    return (r2(min_x), r2(min_y), r2(max_x), r2(max_y))


def polygon_area(points: List[Tuple[float, float]]) -> float:
    """
    Вычисление площади полигона по формуле шнурков (Shoelace formula)
    
    Алгоритм работает для любых простых полигонов (без самопересечений).
    Возвращает положительную площадь для полигонов, обходимых против часовой стрелки,
    и отрицательную для полигонов по часовой стрелке.
    
    Args:
        points: Список точек полигона [(x, y), ...]
        
    Returns:
        Площадь полигона в квадратных метрах (может быть отрицательной)
        
    Example:
        >>> square = [(0, 0), (1, 0), (1, 1), (0, 1)]
        >>> polygon_area(square)
        1.0
    """
    if not points or len(points) < 3:
        return 0.0
    
    # Проверяем корректность входных данных
    try:
        validated_points = []
        for x, y in points:
            if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                return 0.0
            if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
                return 0.0
            validated_points.append((float(x), float(y)))
        points = validated_points
    except (TypeError, ValueError):
        return 0.0
    
    # Применяем формулу шнурков
    area = 0.0
    n = len(points)
    
    for i in range(n):
        j = (i + 1) % n  # Следующая точка с замыканием
        area += points[i][0] * points[j][1]  # x_i * y_(i+1)
        area -= points[j][0] * points[i][1]  # x_(i+1) * y_i
    
    return area / 2.0


def point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """
    Проверка, находится ли точка внутри полигона (ray casting algorithm)
    
    Использует алгоритм трассировки луча - проводит луч от точки вправо
    и подсчитывает пересечения с границами полигона. Нечетное количество
    пересечений означает, что точка внутри.
    
    Args:
        point: Координаты точки (x, y)
        polygon: Список точек полигона [(x, y), ...]
        
    Returns:
        True если точка внутри полигона, False иначе
        
    Example:
        >>> square = [(0, 0), (2, 0), (2, 2), (0, 2)]
        >>> point_in_polygon((1, 1), square)
        True
        >>> point_in_polygon((3, 1), square)
        False
    """
    if not polygon or len(polygon) < 3:
        return False
    
    try:
        px, py = point
        if math.isnan(px) or math.isnan(py) or math.isinf(px) or math.isinf(py):
            return False
    except (TypeError, ValueError):
        return False
    
    # Алгоритм ray casting
    inside = False
    n = len(polygon)
    
    # Предыдущая точка для начала алгоритма
    j = n - 1
    
    for i in range(n):
        try:
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            
            # Проверяем пересечение луча с ребром полигона
            if ((yi > py) != (yj > py)) and \
               (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
                inside = not inside
            
            j = i
        except (TypeError, ValueError, ZeroDivisionError):
            continue
    
    return inside


def distance_point_to_line(point: Tuple[float, float], 
                          line_start: Tuple[float, float], 
                          line_end: Tuple[float, float]) -> float:
    """
    Вычисление расстояния от точки до отрезка
    
    Находит кратчайшее расстояние от точки до отрезка, учитывая что
    ближайшая точка может находиться как на самом отрезке, так и
    на его продолжении (в этом случае берется расстояние до ближайшей конечной точки).
    
    Args:
        point: Координаты точки (x, y)
        line_start: Начальная точка отрезка (x, y)
        line_end: Конечная точка отрезка (x, y)
        
    Returns:
        Минимальное расстояние от точки до отрезка
        
    Example:
        >>> distance_point_to_line((1, 1), (0, 0), (2, 0))
        1.0
    """
    try:
        px, py = point
        x1, y1 = line_start
        x2, y2 = line_end
        
        # Проверяем корректность данных
        for val in [px, py, x1, y1, x2, y2]:
            if math.isnan(val) or math.isinf(val):
                return float('inf')
        
        # Если отрезок вырожден в точку
        if abs(x2 - x1) < TOLERANCE and abs(y2 - y1) < TOLERANCE:
            return math.sqrt((px - x1)**2 + (py - y1)**2)
        
        # Вычисляем параметр t для ближайшей точки на прямой
        dx = x2 - x1
        dy = y2 - y1
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        
        # Ограничиваем t отрезком [0, 1]
        t = max(0, min(1, t))
        
        # Находим ближайшую точку на отрезке
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        
        # Вычисляем расстояние
        return math.sqrt((px - closest_x)**2 + (py - closest_y)**2)
        
    except (TypeError, ValueError, ZeroDivisionError):
        return float('inf')


def line_intersection(line1_start: Tuple[float, float], line1_end: Tuple[float, float],
                     line2_start: Tuple[float, float], line2_end: Tuple[float, float]) -> Optional[Tuple[float, float]]:
    """
    Находит точку пересечения двух отрезков
    
    Использует параметрическое представление прямых для нахождения точки пересечения.
    Важно для определения смежности помещений и автоматического построения 
    топологии здания.
    
    Args:
        line1_start: Начало первого отрезка (x, y)
        line1_end: Конец первого отрезка (x, y)
        line2_start: Начало второго отрезка (x, y)
        line2_end: Конец второго отрезка (x, y)
        
    Returns:
        Координаты точки пересечения (x, y) или None если отрезки не пересекаются
    """
    try:
        x1, y1 = line1_start
        x2, y2 = line1_end
        x3, y3 = line2_start
        x4, y4 = line2_end
        
        # Вычисляем определитель системы
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        
        if abs(denom) < TOLERANCE:
            return None  # Прямые параллельны или совпадают
        
        # Вычисляем параметры пересечения
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
        
        # Проверяем, что пересечение внутри обоих отрезков
        if 0 <= t <= 1 and 0 <= u <= 1:
            intersection_x = x1 + t * (x2 - x1)
            intersection_y = y1 + t * (y2 - y1)
            return (r2(intersection_x), r2(intersection_y))
        
        return None
        
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def simplify_polygon(points: List[Tuple[float, float]], tolerance: float = 0.01) -> List[Tuple[float, float]]:
    """
    Упрощение полигона с использованием алгоритма Дугласа-Пёкера
    
    Удаляет избыточные точки, сохраняя общую форму полигона.
    Это важно для оптимизации производительности отрисовки сложных
    контуров, импортированных из BIM-систем.
    
    Args:
        points: Исходный список точек полигона
        tolerance: Допустимое отклонение от исходной формы (в метрах)
        
    Returns:
        Упрощенный список точек
    """
    if len(points) <= 2:
        return points.copy()
    
    def douglas_peucker(points_segment: List[Tuple[float, float]], epsilon: float) -> List[Tuple[float, float]]:
        """Рекурсивная реализация алгоритма Дугласа-Пёкера"""
        if len(points_segment) <= 2:
            return points_segment
        
        # Находим точку с максимальным расстоянием до прямой между первой и последней точками
        max_distance = 0
        max_index = 0
        
        for i in range(1, len(points_segment) - 1):
            distance = distance_point_to_line(points_segment[i], points_segment[0], points_segment[-1])
            if distance > max_distance:
                max_distance = distance
                max_index = i
        
        # Если максимальное расстояние больше допуска, разбиваем сегмент
        if max_distance > epsilon:
            # Рекурсивно упрощаем левую и правую части
            left_result = douglas_peucker(points_segment[:max_index + 1], epsilon)
            right_result = douglas_peucker(points_segment[max_index:], epsilon)
            
            # Объединяем результаты, избегая дублирования средней точки
            return left_result[:-1] + right_result
        else:
            # Возвращаем только концевые точки
            return [points_segment[0], points_segment[-1]]
    
    # Применяем алгоритм к замкнутому полигону
    if points[0] == points[-1]:
        # Полигон уже замкнут
        simplified = douglas_peucker(points, tolerance)
        if simplified[0] != simplified[-1]:
            simplified.append(simplified[0])  # Замыкаем полигон
    else:
        # Замыкаем полигон перед упрощением
        closed_points = points + [points[0]]
        simplified = douglas_peucker(closed_points, tolerance)
        
    return simplified