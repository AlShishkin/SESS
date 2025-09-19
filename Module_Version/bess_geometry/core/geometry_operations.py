# -*- coding: utf-8 -*-
"""
GeometryOperations - интерактивные операции с геометрией зданий

Этот модуль предоставляет высокоуровневые операции для интерактивного
создания, редактирования и манипулирования геометрическими элементами зданий.
Он служит мостом между пользовательским интерфейсом и системой обработки геометрии.

Ключевые принципы:
- Операции организованы как команды с возможностью отмены (Command pattern)
- Валидация данных происходит на каждом этапе операции
- Поддержка различных режимов интерактивного редактирования
- Автоматическое сохранение истории изменений для отладки

Этот модуль особенно важен для архитектурных приложений, где пользователи
должны иметь возможность интуитивно создавать и редактировать планы зданий.
"""

import uuid
import copy
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set, Union, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

# Импортируем базовые геометрические утилиты
try:
    from geometry_utils import centroid_xy, bounds, r2, polygon_area, point_in_polygon
    GEOMETRY_UTILS_AVAILABLE = True
except ImportError:
    print("Предупреждение: geometry_utils недоступен для geometry_operations")
    GEOMETRY_UTILS_AVAILABLE = False

# Импортируем систему мониторинга производительности
try:
    from performance import PerformanceMonitor, performance_monitor
    PERFORMANCE_AVAILABLE = True
except ImportError:
    print("Предупреждение: performance недоступен для geometry_operations")
    PERFORMANCE_AVAILABLE = False
    # Создаем заглушку для декоратора
    def performance_monitor(name):
        def decorator(func):
            return func
        return decorator


class DrawingMode(Enum):
    """Режимы интерактивного рисования и редактирования"""
    NONE = "none"                      # Режим выбора и навигации
    ADD_ROOM = "add_room"              # Создание нового помещения
    ADD_AREA = "add_area"              # Создание области/зоны
    ADD_VOID = "add_void"              # Создание пустоты в помещении
    ADD_OPENING = "add_opening"        # Добавление проема (дверь/окно)
    ADD_SHAFT = "add_shaft"            # Создание шахты (лифт/вентиляция)
    EDIT_CONTOUR = "edit_contour"      # Редактирование контура элемента
    MOVE_ELEMENT = "move_element"      # Перемещение элемента
    COPY_ELEMENT = "copy_element"      # Копирование элемента
    DELETE_ELEMENT = "delete_element"  # Удаление элемента


class OperationType(Enum):
    """Типы операций для системы истории и отмены действий"""
    CREATE_ELEMENT = "create_element"
    DELETE_ELEMENT = "delete_element"
    MODIFY_GEOMETRY = "modify_geometry"
    MODIFY_PROPERTIES = "modify_properties"
    MOVE_ELEMENT = "move_element"
    COPY_ELEMENT = "copy_element"
    BATCH_OPERATION = "batch_operation"
    IMPORT_DATA = "import_data"
    EXPORT_DATA = "export_data"


class ValidationLevel(Enum):
    """Уровни валидации геометрических операций"""
    NONE = "none"          # Без валидации (максимальная производительность)
    BASIC = "basic"        # Базовая валидация (проверка основных ошибок)
    STANDARD = "standard"  # Стандартная валидация (рекомендуется)
    STRICT = "strict"      # Строгая валидация (для критических операций)


@dataclass
class GeometryOperation:
    """
    Структура для представления одной геометрической операции
    
    Эта структура инкапсулирует всю информацию, необходимую для выполнения
    операции, её отмены, и ведения истории изменений.
    """
    operation_id: str                              # Уникальный идентификатор операции
    operation_type: OperationType                  # Тип операции
    timestamp: datetime                            # Время выполнения операции
    description: str                               # Человекочитаемое описание
    affected_elements: List[str] = field(default_factory=list)  # ID затронутых элементов
    before_state: Dict[str, Any] = field(default_factory=dict)  # Состояние до операции
    after_state: Dict[str, Any] = field(default_factory=dict)   # Состояние после операции
    metadata: Dict[str, Any] = field(default_factory=dict)      # Дополнительные данные
    user_data: Dict[str, Any] = field(default_factory=dict)     # Пользовательские данные
    validation_level: ValidationLevel = ValidationLevel.STANDARD
    execution_time_ms: float = 0.0                 # Время выполнения в миллисекундах
    is_undoable: bool = True                       # Можно ли отменить операцию
    is_completed: bool = False                     # Завершена ли операция успешно


@dataclass
class InteractionContext:
    """
    Контекст для интерактивных операций
    
    Содержит информацию о текущем состоянии пользовательского интерфейса
    и параметрах взаимодействия с геометрией.
    """
    current_level: str = ""                        # Текущий уровень здания
    snap_to_grid: bool = True                      # Привязка к сетке
    grid_size: float = 1.0                         # Размер сетки в метрах
    snap_tolerance: float = 0.1                    # Толерантность привязки
    auto_close_polygons: bool = True               # Автоматическое замыкание полигонов
    validate_during_creation: bool = True          # Валидация во время создания
    show_preview: bool = True                      # Показывать предварительный просмотр
    highlight_conflicts: bool = True               # Подсвечивать конфликты геометрии
    default_element_height: float = 3.0            # Высота элементов по умолчанию
    mouse_position: Tuple[float, float] = (0.0, 0.0)  # Текущая позиция мыши
    modifier_keys: Set[str] = field(default_factory=set)  # Нажатые клавиши-модификаторы


class GeometryOperations:
    """
    Центральный класс для выполнения интерактивных операций с геометрией
    
    Этот класс координирует создание, редактирование и манипулирование
    геометрическими элементами зданий. Он обеспечивает единообразный
    интерфейс для различных типов операций и ведет полную историю изменений.
    
    Архитектурные принципы:
    - Command Pattern: каждая операция инкапсулирована и может быть отменена
    - Observer Pattern: уведомления о изменениях для обновления UI
    - Strategy Pattern: различные алгоритмы валидации и обработки
    """
    
    def __init__(self, validation_level: ValidationLevel = ValidationLevel.STANDARD):
        """
        Инициализация системы геометрических операций
        
        Args:
            validation_level: Уровень валидации операций по умолчанию
        """
        self.validation_level = validation_level
        
        # История операций для поддержки Undo/Redo
        self.operation_history: List[GeometryOperation] = []
        self.current_operation_index: int = -1  # Индекс текущей операции в истории
        self.max_history_size: int = 100        # Максимальный размер истории
        
        # Текущие данные геометрии
        self.elements: Dict[str, Dict] = {}     # ID элемента -> данные элемента
        self.selected_elements: Set[str] = set() # Множество выбранных элементов
        self.clipboard: List[Dict] = []         # Буфер обмена для копирования
        
        # Контекст взаимодействия
        self.interaction_context = InteractionContext()
        
        # Система уведомлений
        self.change_listeners: List[Callable] = []
        
        # Монитор производительности
        if PERFORMANCE_AVAILABLE:
            self.performance_monitor = PerformanceMonitor()
        else:
            self.performance_monitor = None
        
        # Статистика использования
        self.operation_stats = {
            'total_operations': 0,
            'operations_by_type': {},
            'average_execution_time': 0.0,
            'undo_count': 0,
            'redo_count': 0
        }
        
        print("✅ GeometryOperations инициализирован")
        print(f"   Уровень валидации: {validation_level.value}")
        print(f"   Размер истории: {self.max_history_size}")
    
    @performance_monitor("create_room")
    def create_room(self, points: List[Tuple[float, float]], 
                   room_name: str = "", 
                   level: str = "",
                   properties: Optional[Dict] = None) -> GeometryOperation:
        """
        Создание нового помещения
        
        Args:
            points: Точки контура помещения в порядке обхода
            room_name: Название помещения
            level: Уровень здания
            properties: Дополнительные свойства помещения
            
        Returns:
            Объект операции с результатами создания
        """
        operation = GeometryOperation(
            operation_id=str(uuid.uuid4()),
            operation_type=OperationType.CREATE_ELEMENT,
            timestamp=datetime.now(),
            description=f"Создание помещения: {room_name or 'Без названия'}",
            validation_level=self.validation_level
        )
        
        start_time = time.time()
        
        try:
            # Применяем привязку к сетке если включена
            if self.interaction_context.snap_to_grid:
                points = self._snap_points_to_grid(points)
            
            # Валидация геометрии
            if self.validation_level != ValidationLevel.NONE:
                validation_result = self._validate_room_geometry(points)
                if not validation_result['is_valid']:
                    operation.metadata['validation_errors'] = validation_result['errors']
                    if self.validation_level == ValidationLevel.STRICT:
                        raise ValueError(f"Валидация не пройдена: {validation_result['errors']}")
            
            # Создаем элемент
            element_id = str(uuid.uuid4())
            room_element = {
                'id': element_id,
                'element_type': 'room',
                'name': room_name or f"Room_{len(self.elements) + 1}",
                'level': level or self.interaction_context.current_level,
                'outer_xy_m': points,
                'inner_loops_xy_m': [],
                'params': properties or {},
                'created_at': datetime.now().isoformat(),
                'modified_at': datetime.now().isoformat()
            }
            
            # Добавляем расчетные свойства если доступны утилиты
            if GEOMETRY_UTILS_AVAILABLE:
                room_element['calculated_area_m2'] = abs(polygon_area(points))
                room_element['centroid'] = centroid_xy(points)
                room_element['bounds'] = bounds(points)
            
            # Сохраняем состояние для возможности отмены
            operation.after_state = {element_id: copy.deepcopy(room_element)}
            operation.affected_elements = [element_id]
            
            # Добавляем элемент в коллекцию
            self.elements[element_id] = room_element
            
            # Завершаем операцию
            operation.execution_time_ms = (time.time() - start_time) * 1000
            operation.is_completed = True
            
            # Добавляем в историю
            self._add_to_history(operation)
            
            # Уведомляем слушателей
            self._notify_change('element_created', {'element_id': element_id, 'element': room_element})
            
            # Обновляем статистику
            self._update_operation_stats(operation)
            
            print(f"✅ Создано помещение '{room_element['name']}' с площадью {room_element.get('calculated_area_m2', 0):.2f} м²")
            
            return operation
            
        except Exception as e:
            operation.metadata['error'] = str(e)
            operation.is_completed = False
            print(f"❌ Ошибка создания помещения: {e}")
            return operation
    
    @performance_monitor("create_area")
    def create_area(self, points: List[Tuple[float, float]], 
                   area_name: str = "", 
                   level: str = "",
                   properties: Optional[Dict] = None) -> GeometryOperation:
        """
        Создание новой области/зоны
        
        Области используются для группировки помещений или определения
        функциональных зон здания (например, офисная зона, техническая зона).
        
        Args:
            points: Точки контура области
            area_name: Название области
            level: Уровень здания
            properties: Дополнительные свойства области
            
        Returns:
            Объект операции с результатами создания
        """
        operation = GeometryOperation(
            operation_id=str(uuid.uuid4()),
            operation_type=OperationType.CREATE_ELEMENT,
            timestamp=datetime.now(),
            description=f"Создание области: {area_name or 'Без названия'}",
            validation_level=self.validation_level
        )
        
        start_time = time.time()
        
        try:
            # Применяем привязку к сетке
            if self.interaction_context.snap_to_grid:
                points = self._snap_points_to_grid(points)
            
            # Создаем элемент области
            element_id = str(uuid.uuid4())
            area_element = {
                'id': element_id,
                'element_type': 'area',
                'name': area_name or f"Area_{len([e for e in self.elements.values() if e.get('element_type') == 'area']) + 1}",
                'level': level or self.interaction_context.current_level,
                'outer_xy_m': points,
                'inner_loops_xy_m': [],
                'params': properties or {},
                'created_at': datetime.now().isoformat(),
                'modified_at': datetime.now().isoformat()
            }
            
            # Добавляем расчетные свойства
            if GEOMETRY_UTILS_AVAILABLE:
                area_element['calculated_area_m2'] = abs(polygon_area(points))
                area_element['centroid'] = centroid_xy(points)
                area_element['bounds'] = bounds(points)
            
            # Сохраняем для отмены
            operation.after_state = {element_id: copy.deepcopy(area_element)}
            operation.affected_elements = [element_id]
            
            # Добавляем элемент
            self.elements[element_id] = area_element
            
            # Завершаем операцию
            operation.execution_time_ms = (time.time() - start_time) * 1000
            operation.is_completed = True
            
            self._add_to_history(operation)
            self._notify_change('element_created', {'element_id': element_id, 'element': area_element})
            self._update_operation_stats(operation)
            
            print(f"✅ Создана область '{area_element['name']}' с площадью {area_element.get('calculated_area_m2', 0):.2f} м²")
            
            return operation
            
        except Exception as e:
            operation.metadata['error'] = str(e)
            operation.is_completed = False
            print(f"❌ Ошибка создания области: {e}")
            return operation
    
    def delete_elements(self, element_ids: List[str]) -> GeometryOperation:
        """
        Удаление выбранных элементов
        
        Args:
            element_ids: Список ID элементов для удаления
            
        Returns:
            Объект операции с результатами удаления
        """
        operation = GeometryOperation(
            operation_id=str(uuid.uuid4()),
            operation_type=OperationType.DELETE_ELEMENT,
            timestamp=datetime.now(),
            description=f"Удаление {len(element_ids)} элементов",
            affected_elements=element_ids.copy()
        )
        
        start_time = time.time()
        
        try:
            # Сохраняем состояние элементов перед удалением
            deleted_elements = {}
            for element_id in element_ids:
                if element_id in self.elements:
                    deleted_elements[element_id] = copy.deepcopy(self.elements[element_id])
            
            operation.before_state = deleted_elements
            
            # Удаляем элементы
            for element_id in element_ids:
                if element_id in self.elements:
                    del self.elements[element_id]
                
                # Убираем из выделения
                self.selected_elements.discard(element_id)
            
            operation.execution_time_ms = (time.time() - start_time) * 1000
            operation.is_completed = True
            
            self._add_to_history(operation)
            self._notify_change('elements_deleted', {'element_ids': element_ids})
            self._update_operation_stats(operation)
            
            print(f"✅ Удалено {len(element_ids)} элементов")
            
            return operation
            
        except Exception as e:
            operation.metadata['error'] = str(e)
            operation.is_completed = False
            print(f"❌ Ошибка удаления элементов: {e}")
            return operation
    
    def undo_operation(self) -> bool:
        """
        Отмена последней операции
        
        Returns:
            True если операция успешно отменена, False иначе
        """
        if self.current_operation_index < 0:
            print("⚠️ Нет операций для отмены")
            return False
        
        operation = self.operation_history[self.current_operation_index]
        
        if not operation.is_undoable:
            print(f"⚠️ Операция '{operation.description}' не может быть отменена")
            return False
        
        try:
            # Восстанавливаем состояние до операции
            self._restore_state(operation.before_state, operation.after_state)
            
            self.current_operation_index -= 1
            self.operation_stats['undo_count'] += 1
            
            self._notify_change('operation_undone', {'operation': operation})
            
            print(f"↶ Отменена операция: {operation.description}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка отмены операции: {e}")
            return False
    
    def redo_operation(self) -> bool:
        """
        Повтор отмененной операции
        
        Returns:
            True если операция успешно повторена, False иначе
        """
        if self.current_operation_index >= len(self.operation_history) - 1:
            print("⚠️ Нет операций для повтора")
            return False
        
        self.current_operation_index += 1
        operation = self.operation_history[self.current_operation_index]
        
        try:
            # Применяем состояние после операции
            self._restore_state(operation.after_state, operation.before_state)
            
            self.operation_stats['redo_count'] += 1
            
            self._notify_change('operation_redone', {'operation': operation})
            
            print(f"↷ Повторена операция: {operation.description}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка повтора операции: {e}")
            return False
    
    def get_elements_by_type(self, element_type: str) -> List[Dict]:
        """Получение всех элементов определенного типа"""
        return [element for element in self.elements.values() 
                if element.get('element_type') == element_type]
    
    def get_elements_on_level(self, level: str) -> List[Dict]:
        """Получение всех элементов на определенном уровне"""
        return [element for element in self.elements.values() 
                if element.get('level') == level]
    
    def add_change_listener(self, listener: Callable) -> None:
        """Добавление слушателя изменений"""
        if listener not in self.change_listeners:
            self.change_listeners.append(listener)
    
    def remove_change_listener(self, listener: Callable) -> None:
        """Удаление слушателя изменений"""
        if listener in self.change_listeners:
            self.change_listeners.remove(listener)
    
    def get_operation_statistics(self) -> Dict[str, Any]:
        """Получение статистики операций"""
        return {
            **self.operation_stats,
            'history_size': len(self.operation_history),
            'current_position': self.current_operation_index,
            'elements_count': len(self.elements),
            'selected_count': len(self.selected_elements)
        }
    
    def _snap_points_to_grid(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Привязка точек к сетке"""
        if not self.interaction_context.snap_to_grid:
            return points
        
        grid_size = self.interaction_context.grid_size
        snapped_points = []
        
        for x, y in points:
            snapped_x = round(x / grid_size) * grid_size
            snapped_y = round(y / grid_size) * grid_size
            snapped_points.append((snapped_x, snapped_y))
        
        return snapped_points
    
    def _validate_room_geometry(self, points: List[Tuple[float, float]]) -> Dict[str, Any]:
        """Валидация геометрии помещения"""
        validation_result = {'is_valid': True, 'errors': [], 'warnings': []}
        
        # Базовые проверки
        if len(points) < 3:
            validation_result['is_valid'] = False
            validation_result['errors'].append("Недостаточно точек для формирования помещения")
            return validation_result
        
        # Проверка площади если доступны утилиты
        if GEOMETRY_UTILS_AVAILABLE:
            area = abs(polygon_area(points))
            if area < 0.1:  # Минимальная площадь 0.1 м²
                validation_result['warnings'].append(f"Очень маленькая площадь: {area:.3f} м²")
            elif area > 10000:  # Максимальная площадь 10,000 м²
                validation_result['warnings'].append(f"Очень большая площадь: {area:.1f} м²")
        
        return validation_result
    
    def _add_to_history(self, operation: GeometryOperation) -> None:
        """Добавление операции в историю"""
        # Удаляем операции после текущей позиции (при добавлении новой операции после отмены)
        if self.current_operation_index < len(self.operation_history) - 1:
            self.operation_history = self.operation_history[:self.current_operation_index + 1]
        
        # Добавляем новую операцию
        self.operation_history.append(operation)
        self.current_operation_index += 1
        
        # Ограничиваем размер истории
        if len(self.operation_history) > self.max_history_size:
            removed_count = len(self.operation_history) - self.max_history_size
            self.operation_history = self.operation_history[removed_count:]
            self.current_operation_index -= removed_count
    
    def _restore_state(self, target_state: Dict[str, Dict], 
                      reference_state: Dict[str, Dict]) -> None:
        """Восстановление состояния элементов"""
        # Удаляем элементы, которых не должно быть
        elements_to_remove = []
        for element_id in self.elements:
            if element_id not in target_state and element_id in reference_state:
                elements_to_remove.append(element_id)
        
        for element_id in elements_to_remove:
            del self.elements[element_id]
            self.selected_elements.discard(element_id)
        
        # Восстанавливаем или создаем элементы
        for element_id, element_data in target_state.items():
            self.elements[element_id] = copy.deepcopy(element_data)
    
    def _notify_change(self, change_type: str, change_data: Dict) -> None:
        """Уведомление слушателей об изменениях"""
        for listener in self.change_listeners:
            try:
                listener(change_type, change_data)
            except Exception as e:
                print(f"⚠️ Ошибка в слушателе изменений: {e}")
    
    def _update_operation_stats(self, operation: GeometryOperation) -> None:
        """Обновление статистики операций"""
        self.operation_stats['total_operations'] += 1
        
        op_type = operation.operation_type.value
        if op_type not in self.operation_stats['operations_by_type']:
            self.operation_stats['operations_by_type'][op_type] = 0
        self.operation_stats['operations_by_type'][op_type] += 1
        
        # Обновляем среднее время выполнения
        total_time = (self.operation_stats['average_execution_time'] * 
                     (self.operation_stats['total_operations'] - 1) + 
                     operation.execution_time_ms)
        self.operation_stats['average_execution_time'] = total_time / self.operation_stats['total_operations']


# Фабричные функции для удобного создания объектов
def create_geometry_operations(validation_level: ValidationLevel = ValidationLevel.STANDARD) -> GeometryOperations:
    """
    Создание экземпляра GeometryOperations с заданными параметрами
    
    Args:
        validation_level: Уровень валидации операций
        
    Returns:
        Настроенный экземпляр GeometryOperations
    """
    return GeometryOperations(validation_level)


def create_simple_room(points: List[Tuple[float, float]], name: str = "") -> Dict:
    """
    Упрощенное создание помещения без полной системы операций
    
    Args:
        points: Точки контура помещения
        name: Название помещения
        
    Returns:
        Словарь с данными помещения
    """
    element = {
        'id': str(uuid.uuid4()),
        'element_type': 'room',
        'name': name or f"Room_{int(time.time())}",
        'outer_xy_m': points,
        'inner_loops_xy_m': [],
        'params': {},
        'created_at': datetime.now().isoformat()
    }
    
    # Добавляем расчетные свойства если возможно
    if GEOMETRY_UTILS_AVAILABLE:
        element['calculated_area_m2'] = abs(polygon_area(points))
        element['centroid'] = centroid_xy(points)
        element['bounds'] = bounds(points)
    
    return element


# Экспортируем основные классы и функции
__all__ = [
    'GeometryOperations',
    'DrawingMode',
    'OperationType', 
    'ValidationLevel',
    'GeometryOperation',
    'InteractionContext',
    'create_geometry_operations',
    'create_simple_room'
]