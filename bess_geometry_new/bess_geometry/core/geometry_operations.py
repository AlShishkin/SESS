# -*- coding: utf-8 -*-
"""
GeometryOperations - расширенные геометрические операции с интеграцией новых компонентов

НОВЫЕ ВОЗМОЖНОСТИ ЭТАПА 3:
- Интеграция с ArchitecturalTools для создания VOID и второго света
- Автоматическое применение параметров BESS через BESSParameterManager
- Расширенная валидация геометрии через SpatialProcessor
- Поддержка операций с шахтами через ShaftManager

Архитектурные принципы:
- Единая точка входа для всех геометрических операций
- Автоматическая валидация и применение параметров
- Консистентная обработка ошибок
- Поддержка undo/redo для всех операций
"""

from enum import Enum
from typing import Dict, List, Tuple, Optional, Any, Callable
from copy import deepcopy
from datetime import datetime
import math

# Интеграция с новыми компонентами
try:
    from .architectural_tools import ArchitecturalTools
    ARCHITECTURAL_TOOLS_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: ArchitecturalTools недоступен в geometry_operations - {e}")
    ARCHITECTURAL_TOOLS_AVAILABLE = False

try:
    from .bess_parameters import BESSParameterManager, ParameterScope
    BESS_PARAMETERS_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: BESSParameterManager недоступен в geometry_operations - {e}")
    BESS_PARAMETERS_AVAILABLE = False

try:
    from .shaft_manager import ShaftManager
    SHAFT_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: ShaftManager недоступен в geometry_operations - {e}")
    SHAFT_MANAGER_AVAILABLE = False


class DrawingMode(Enum):
    """Режимы рисования"""
    NONE = "none"
    ROOM = "room"
    OPENING = "opening"
    WALL = "wall"
    VOID = "void"                    # НОВЫЙ: создание VOID
    SECOND_LIGHT = "second_light"    # НОВЫЙ: создание второго света
    SHAFT = "shaft"                  # НОВЫЙ: создание шахт


class OperationType(Enum):
    """Типы геометрических операций"""
    CREATE_ROOM = "create_room"
    CREATE_OPENING = "create_opening"
    CREATE_WALL = "create_wall"
    CREATE_VOID = "create_void"                      # НОВЫЙ
    CREATE_SECOND_LIGHT = "create_second_light"      # НОВЫЙ
    CREATE_SHAFT = "create_shaft"                    # НОВЫЙ
    EDIT_GEOMETRY = "edit_geometry"
    DELETE_ELEMENT = "delete_element"
    MOVE_ELEMENT = "move_element"
    COPY_ELEMENT = "copy_element"
    UPDATE_PARAMETERS = "update_parameters"          # НОВЫЙ


class GeometryValidationLevel(Enum):
    """Уровни валидации геометрии"""
    BASIC = "basic"        # Базовая валидация (пересечения, площадь)
    ADVANCED = "advanced"  # Расширенная валидация (топология, связность)
    FULL = "full"         # Полная валидация (BESS параметры, энергетические характеристики)


class GeometryOperation:
    """
    Класс для представления геометрической операции
    
    Расширен для поддержки новых типов операций и автоматического
    применения параметров BESS.
    """
    
    def __init__(self, operation_type: OperationType, data: Dict[str, Any]):
        self.operation_type = operation_type
        self.data = data
        self.timestamp = datetime.now()
        self.validation_result = None
        self.applied_parameters = {}  # НОВОЕ: сохраняем примененные параметры BESS
        
    def set_validation_result(self, result: Dict[str, Any]):
        """Установка результата валидации"""
        self.validation_result = result
        
    def set_applied_parameters(self, parameters: Dict[str, Any]):
        """Установка примененных параметров BESS"""
        self.applied_parameters = parameters
        
    def get_operation_summary(self) -> Dict[str, Any]:
        """Получение сводки операции для логирования"""
        return {
            'type': self.operation_type.value,
            'timestamp': self.timestamp.isoformat(),
            'element_id': self.data.get('element_id'),
            'level': self.data.get('level'),
            'has_validation': self.validation_result is not None,
            'has_parameters': bool(self.applied_parameters),
            'success': self.validation_result.get('valid', True) if self.validation_result else True
        }


class GeometryOperations:
    """
    Система геометрических операций с интеграцией новых компонентов
    
    РАСШИРЕННАЯ ФУНКЦИОНАЛЬНОСТЬ:
    - Создание VOID помещений через ArchitecturalTools
    - Создание второго света с автоматическим расчетом высот
    - Управление шахтами через ShaftManager
    - Автоматическое применение параметров BESS
    - Продвинутая валидация геометрии
    """
    
    def __init__(self, state=None):
        self.state = state
        
        # === ИНТЕГРАЦИЯ НОВЫХ КОМПОНЕНТОВ ===
        self.parameter_manager = None
        if BESS_PARAMETERS_AVAILABLE:
            self.parameter_manager = BESSParameterManager()
            print("✅ BESSParameterManager интегрирован в GeometryOperations")
        
        self.shaft_manager = None
        if SHAFT_MANAGER_AVAILABLE:
            self.shaft_manager = ShaftManager()
            print("✅ ShaftManager интегрирован в GeometryOperations")
        
        # === CALLBACK ФУНКЦИИ ===
        self.validation_callback: Optional[Callable] = None
        self.history_callback: Optional[Callable] = None
        self.update_callback: Optional[Callable] = None
        
        # === НАСТРОЙКИ ВАЛИДАЦИИ ===
        self.validation_level = GeometryValidationLevel.ADVANCED
        self.auto_apply_parameters = True  # Автоматически применять параметры BESS
        self.validate_before_create = True  # Валидировать перед созданием элементов
        
        # === ИСТОРИЯ ОПЕРАЦИЙ ===
        self.operation_history: List[GeometryOperation] = []
        self.max_history_size = 1000
    
    def set_validation_callback(self, callback: Callable):
        """Установка callback для валидации геометрии"""
        self.validation_callback = callback
    
    def set_history_callback(self, callback: Callable):
        """Установка callback для истории операций"""
        self.history_callback = callback
    
    def set_update_callback(self, callback: Callable):
        """Установка callback для уведомлений об обновлениях"""
        self.update_callback = callback
    
    def _validate_geometry(self, coords: List[Tuple[float, float]], 
                          operation_type: OperationType) -> Dict[str, Any]:
        """
        Комплексная валидация геометрии
        
        Args:
            coords: Координаты для валидации
            operation_type: Тип операции для контекстной валидации
            
        Returns:
            Результат валидации с подробной информацией
        """
        result = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'suggestions': []
        }
        
        # Базовая валидация
        if len(coords) < 3:
            result['valid'] = False
            result['errors'].append('Недостаточно точек для создания геометрии')
            return result
        
        # Проверка на самопересечения
        if self._has_self_intersections(coords):
            result['valid'] = False
            result['errors'].append('Контур имеет самопересечения')
        
        # Проверка площади
        area = self._calculate_polygon_area(coords)
        if area < 0.1:  # Минимальная площадь 0.1 м²
            result['warnings'].append(f'Малая площадь: {area:.2f} м²')
        
        # Специфичная валидация для VOID
        if operation_type == OperationType.CREATE_VOID:
            if area > 1000:  # Максимальная площадь VOID 1000 м²
                result['warnings'].append(f'Большая площадь для VOID: {area:.2f} м²')
        
        # Использование внешнего валидатора если доступен
        if self.validation_callback:
            try:
                external_result = self.validation_callback(coords)
                if not external_result.get('valid', True):
                    result['valid'] = False
                    result['errors'].extend(external_result.get('errors', []))
                result['warnings'].extend(external_result.get('warnings', []))
            except Exception as e:
                result['warnings'].append(f'Ошибка внешнего валидатора: {e}')
        
        return result
    
    def _has_self_intersections(self, coords: List[Tuple[float, float]]) -> bool:
        """Проверка на самопересечения контура"""
        n = len(coords)
        if n < 4:
            return False
        
        for i in range(n):
            for j in range(i + 2, n):
                if j == n - 1 and i == 0:  # Не проверяем замыкающий сегмент
                    continue
                    
                p1, p2 = coords[i], coords[(i + 1) % n]
                p3, p4 = coords[j], coords[(j + 1) % n]
                
                if self._segments_intersect(p1, p2, p3, p4):
                    return True
        
        return False
    
    def _segments_intersect(self, p1: Tuple[float, float], p2: Tuple[float, float],
                           p3: Tuple[float, float], p4: Tuple[float, float]) -> bool:
        """Проверка пересечения двух отрезков"""
        def orientation(p, q, r):
            val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
            if val == 0:
                return 0  # коллинеарны
            return 1 if val > 0 else 2  # по часовой или против часовой стрелки
        
        def on_segment(p, q, r):
            return (q[0] <= max(p[0], r[0]) and q[0] >= min(p[0], r[0]) and
                    q[1] <= max(p[1], r[1]) and q[1] >= min(p[1], r[1]))
        
        o1 = orientation(p1, p2, p3)
        o2 = orientation(p1, p2, p4)
        o3 = orientation(p3, p4, p1)
        o4 = orientation(p3, p4, p2)
        
        # Общий случай
        if o1 != o2 and o3 != o4:
            return True
        
        # Специальные случаи
        if (o1 == 0 and on_segment(p1, p3, p2)) or \
           (o2 == 0 and on_segment(p1, p4, p2)) or \
           (o3 == 0 and on_segment(p3, p1, p4)) or \
           (o4 == 0 and on_segment(p3, p2, p4)):
            return True
        
        return False
    
    def _calculate_polygon_area(self, coords: List[Tuple[float, float]]) -> float:
        """Вычисление площади полигона"""
        if len(coords) < 3:
            return 0.0
        
        area = 0.0
        n = len(coords)
        for i in range(n):
            j = (i + 1) % n
            area += coords[i][0] * coords[j][1]
            area -= coords[j][0] * coords[i][1]
        
        return abs(area) / 2.0
    
    def _apply_bess_parameters(self, element_data: Dict[str, Any], 
                              scope: ParameterScope) -> Dict[str, Any]:
        """
        Применение параметров BESS к элементу
        
        Args:
            element_data: Данные элемента
            scope: Область применения параметров
            
        Returns:
            Примененные параметры
        """
        if not self.parameter_manager or not self.auto_apply_parameters:
            return {}
        
        try:
            # Применяем параметры по умолчанию
            self.parameter_manager.apply_default_parameters(element_data, scope)
            
            # Вычисляем расчетные параметры
            if self.state:
                self.parameter_manager.calculate_all_parameters(
                    element_data, self.state.levels
                )
            
            # Возвращаем примененные параметры для логирования
            return element_data.get('bess_parameters', {})
            
        except Exception as e:
            print(f"Предупреждение: не удалось применить параметры BESS - {e}")
            return {}
    
    def _record_operation(self, operation: GeometryOperation):
        """Запись операции в историю"""
        self.operation_history.append(operation)
        
        # Ограничиваем размер истории
        if len(self.operation_history) > self.max_history_size:
            self.operation_history.pop(0)
        
        # Уведомляем callback
        if self.history_callback:
            self.history_callback(operation.get_operation_summary())
    
    # === НОВЫЕ МЕТОДЫ ДЛЯ СОЗДАНИЯ АРХИТЕКТУРНЫХ ЭЛЕМЕНТОВ ===
    
    def create_void_element(self, coords: List[Tuple[float, float]], 
                           level: str, base_room_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Создание VOID элемента через ArchitecturalTools
        
        Args:
            coords: Координаты контура VOID
            level: Уровень для создания
            base_room_id: ID базового помещения (опционально)
            
        Returns:
            Результат создания VOID
        """
        if not ARCHITECTURAL_TOOLS_AVAILABLE:
            return {'success': False, 'error': 'ArchitecturalTools недоступны'}
        
        # Валидация перед созданием
        if self.validate_before_create:
            validation = self._validate_geometry(coords, OperationType.CREATE_VOID)
            if not validation['valid']:
                return {
                    'success': False, 
                    'error': f"Валидация не пройдена: {'; '.join(validation['errors'])}"
                }
        
        try:
            # Создаем VOID через ArchitecturalTools
            result = ArchitecturalTools.add_void(
                self.state, level, coords, base_room_id
            )
            
            if result['success']:
                void_element = result['void_data']
                
                # Применяем параметры BESS
                applied_params = self._apply_bess_parameters(
                    void_element, ParameterScope.AREA
                )
                
                # Записываем операцию в историю
                operation = GeometryOperation(OperationType.CREATE_VOID, {
                    'element_id': result['void_id'],
                    'level': level,
                    'coords': coords,
                    'base_room_id': base_room_id
                })
                
                if self.validate_before_create:
                    operation.set_validation_result(validation)
                operation.set_applied_parameters(applied_params)
                
                self._record_operation(operation)
                
                # Уведомляем об обновлении
                if self.update_callback:
                    self.update_callback({
                        'operation': 'create_void',
                        'element_id': result['void_id'],
                        'level': level
                    })
                
                return result
            else:
                return result
                
        except Exception as e:
            return {'success': False, 'error': f'Исключение при создании VOID: {e}'}
    
    def create_second_light_element(self, base_room_id: str, level: str,
                                   coords: List[Tuple[float, float]]) -> Dict[str, Any]:
        """
        Создание элемента второго света через ArchitecturalTools
        
        Args:
            base_room_id: ID помещения-основы
            level: Уровень для создания второго света
            coords: Координаты контура
            
        Returns:
            Результат создания второго света
        """
        if not ARCHITECTURAL_TOOLS_AVAILABLE:
            return {'success': False, 'error': 'ArchitecturalTools недоступны'}
        
        # Валидация
        if self.validate_before_create:
            validation = self._validate_geometry(coords, OperationType.CREATE_SECOND_LIGHT)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': f"Валидация не пройдена: {'; '.join(validation['errors'])}"
                }
        
        try:
            result = ArchitecturalTools.add_second_light(
                self.state, base_room_id, level, coords
            )
            
            if result['success']:
                second_light_element = result['second_light_data']
                
                # Применяем параметры BESS с особым вниманием к высотным характеристикам
                applied_params = self._apply_bess_parameters(
                    second_light_element, ParameterScope.AREA
                )
                
                # Записываем операцию
                operation = GeometryOperation(OperationType.CREATE_SECOND_LIGHT, {
                    'element_id': result['second_light_id'],
                    'base_room_id': base_room_id,
                    'level': level,
                    'coords': coords
                })
                
                if self.validate_before_create:
                    operation.set_validation_result(validation)
                operation.set_applied_parameters(applied_params)
                
                self._record_operation(operation)
                
                # Уведомляем об обновлении
                if self.update_callback:
                    self.update_callback({
                        'operation': 'create_second_light',
                        'element_id': result['second_light_id'],
                        'base_room_id': base_room_id,
                        'level': level
                    })
                
                return result
            else:
                return result
                
        except Exception as e:
            return {'success': False, 'error': f'Исключение при создании второго света: {e}'}
    
    def create_shaft_element(self, shaft_data: Dict[str, Any], 
                            levels: List[str]) -> Dict[str, Any]:
        """
        Создание шахты через ShaftManager
        
        Args:
            shaft_data: Данные шахты
            levels: Список уровней для клонирования
            
        Returns:
            Результат создания шахты
        """
        if not self.shaft_manager:
            return {'success': False, 'error': 'ShaftManager недоступен'}
        
        try:
            # Создаем базовую шахту
            result = self.shaft_manager.import_base_shafts([shaft_data])
            
            if result['success']:
                shaft_id = result['imported_shafts'][0]
                
                # Клонируем по уровням
                clone_result = self.shaft_manager.clone_to_levels(levels)
                
                # Применяем параметры BESS
                shaft_element = self.shaft_manager.get_shaft_data(shaft_id)
                applied_params = {}
                if shaft_element:
                    applied_params = self._apply_bess_parameters(
                        shaft_element, ParameterScope.SHAFT
                    )
                
                # Записываем операцию
                operation = GeometryOperation(OperationType.CREATE_SHAFT, {
                    'element_id': shaft_id,
                    'levels': levels,
                    'shaft_type': shaft_data.get('shaft_type', 'UNKNOWN')
                })
                operation.set_applied_parameters(applied_params)
                
                self._record_operation(operation)
                
                # Уведомляем об обновлении
                if self.update_callback:
                    self.update_callback({
                        'operation': 'create_shaft',
                        'element_id': shaft_id,
                        'levels': levels
                    })
                
                return {
                    'success': True,
                    'shaft_id': shaft_id,
                    'cloned_levels': clone_result.get('cloned_levels', [])
                }
            else:
                return result
                
        except Exception as e:
            return {'success': False, 'error': f'Исключение при создании шахты: {e}'}
    
    def update_element_parameters(self, element_id: str, 
                                 new_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обновление параметров элемента через BESSParameterManager
        
        Args:
            element_id: ID элемента
            new_params: Новые параметры
            
        Returns:
            Результат обновления
        """
        if not self.parameter_manager:
            return {'success': False, 'error': 'BESSParameterManager недоступен'}
        
        try:
            element_data = self.state.get_element_by_id(element_id) if self.state else None
            if not element_data:
                return {'success': False, 'error': f'Элемент {element_id} не найден'}
            
            # Обновляем параметры
            success = self.parameter_manager.update_element_parameters(
                element_data, new_params
            )
            
            if success:
                # Пересчитываем зависимые параметры
                if self.state:
                    self.parameter_manager.calculate_all_parameters(
                        element_data, self.state.levels
                    )
                
                # Записываем операцию
                operation = GeometryOperation(OperationType.UPDATE_PARAMETERS, {
                    'element_id': element_id,
                    'updated_params': new_params
                })
                operation.set_applied_parameters(new_params)
                
                self._record_operation(operation)
                
                # Уведомляем об обновлении
                if self.update_callback:
                    self.update_callback({
                        'operation': 'update_parameters',
                        'element_id': element_id,
                        'updated_params': new_params
                    })
                
                return {'success': True, 'updated_parameters': new_params}
            else:
                return {'success': False, 'error': 'Не удалось обновить параметры'}
                
        except Exception as e:
            return {'success': False, 'error': f'Исключение при обновлении параметров: {e}'}
    
    # === МЕТОДЫ ДЛЯ ПОЛУЧЕНИЯ СТАТИСТИКИ ===
    
    def get_operations_statistics(self) -> Dict[str, Any]:
        """Получение статистики операций"""
        stats = {
            'total_operations': len(self.operation_history),
            'operations_by_type': {},
            'successful_operations': 0,
            'operations_with_parameters': 0,
            'recent_operations': []
        }
        
        for operation in self.operation_history:
            op_type = operation.operation_type.value
            stats['operations_by_type'][op_type] = stats['operations_by_type'].get(op_type, 0) + 1
            
            if operation.validation_result is None or operation.validation_result.get('valid', True):
                stats['successful_operations'] += 1
            
            if operation.applied_parameters:
                stats['operations_with_parameters'] += 1
        
        # Последние 10 операций
        stats['recent_operations'] = [
            op.get_operation_summary() for op in self.operation_history[-10:]
        ]
        
        return stats
    
    def get_integration_status(self) -> Dict[str, bool]:
        """Получение статуса интеграции компонентов"""
        return {
            'architectural_tools': ARCHITECTURAL_TOOLS_AVAILABLE,
            'bess_parameters': self.parameter_manager is not None,
            'shaft_manager': self.shaft_manager is not None,
            'validation_enabled': self.validation_callback is not None,
            'history_enabled': self.history_callback is not None
        }