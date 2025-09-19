# -*- coding: utf-8 -*-
"""
BESSParameterManager - система управления параметрами BESS_Geometry

Этот модуль обеспечивает централизованное управление параметрами BESS:
• Автоматический префикс BESS_ для всех параметров
• Вычисляемые параметры (высота помещений, площади)
• Система алиасов для удобства использования
• Синхронизация с изменениями уровней
• Валидация и нормализация параметров
• Экспорт/импорт настроек параметров

BESS параметры критически важны для корректного энергетического анализа
и интеграции с внешними системами расчета.
"""

import re
from typing import Dict, List, Optional, Tuple, Any, Union, Set
from datetime import datetime
from copy import deepcopy
from enum import Enum

# Импорты с обработкой ошибок
try:
    from geometry_utils import centroid_xy, bounds, r2, polygon_area
    GEOMETRY_UTILS_AVAILABLE = True
except ImportError:
    print("Предупреждение: geometry_utils недоступен для bess_parameters")
    GEOMETRY_UTILS_AVAILABLE = False
    
    def r2(value): return round(float(value), 2)


class ParameterType(Enum):
    """Типы параметров BESS"""
    STRING = "STRING"           # Строковый параметр
    NUMERIC = "NUMERIC"         # Числовой параметр
    BOOLEAN = "BOOLEAN"         # Логический параметр
    LEVEL = "LEVEL"            # Ссылка на уровень
    CALCULATED = "CALCULATED"  # Вычисляемый параметр
    ENUM = "ENUM"              # Перечисление
    AREA = "AREA"              # Площадь
    LENGTH = "LENGTH"          # Длина
    VOLUME = "VOLUME"          # Объем
    TEMPERATURE = "TEMPERATURE" # Температура


class ParameterScope(Enum):
    """Области применения параметров"""
    ROOM = "ROOM"              # Параметры помещений
    AREA = "AREA"              # Параметры областей
    OPENING = "OPENING"        # Параметры проемов
    SHAFT = "SHAFT"            # Параметры шахт
    LEVEL = "LEVEL"            # Параметры уровней
    BUILDING = "BUILDING"      # Параметры здания
    GLOBAL = "GLOBAL"          # Глобальные параметры


# Карта алиасов для удобства использования
ALIAS_TO_PARAM = {
    # Основные параметры
    "BESS_level": "BESS_level",
    "BESS_Upper_level": "BESS_Room_Upper_level",
    "BESS_Room_Height": "BESS_Room_Height",  # вычисляемый
    
    # Геометрические параметры
    "BESS_Area": "BESS_Calculated_Area_M2",
    "BESS_Perimeter": "BESS_Calculated_Perimeter_M",
    "BESS_Volume": "BESS_Calculated_Volume_M3",
    
    # Функциональные параметры
    "BESS_Function": "BESS_Function_Category",
    "BESS_Occupancy": "BESS_Occupancy_Type",
    "BESS_HVAC": "BESS_HVAC_Zone",
    
    # Статусные параметры
    "BESS_Status": "BESS_Element_Status",
    "BESS_Type": "BESS_Room_Type",
    
    # Расчетные параметры
    "BESS_Heating_Load": "BESS_Calculated_Heating_Load_W",
    "BESS_Cooling_Load": "BESS_Calculated_Cooling_Load_W",
    "BESS_Ventilation": "BESS_Calculated_Ventilation_Rate_M3H",
    
    # Температурные параметры
    "BESS_Temp_Design": "BESS_Design_Temperature_C",
    "BESS_Temp_Min": "BESS_Min_Temperature_C",
    "BESS_Temp_Max": "BESS_Max_Temperature_C"
}

# Схема параметров BESS с типами и значениями по умолчанию
BESS_PARAMETER_SCHEMA = {
    # === ОСНОВНЫЕ ПАРАМЕТРЫ ===
    'BESS_level': {
        'type': ParameterType.LEVEL,
        'scope': [ParameterScope.ROOM, ParameterScope.AREA, ParameterScope.OPENING, ParameterScope.SHAFT],
        'default': '',
        'required': True,
        'description': 'Уровень элемента в здании'
    },
    'BESS_Room_Upper_level': {
        'type': ParameterType.LEVEL,
        'scope': [ParameterScope.ROOM],
        'default': '',
        'required': False,
        'description': 'Верхний уровень для помещений с переменной высотой'
    },
    'BESS_Room_Height': {
        'type': ParameterType.CALCULATED,
        'scope': [ParameterScope.ROOM],
        'default': '3.0',
        'required': True,
        'description': 'Высота помещения в метрах (вычисляется автоматически)'
    },
    
    # === ГЕОМЕТРИЧЕСКИЕ ПАРАМЕТРЫ ===
    'BESS_Calculated_Area_M2': {
        'type': ParameterType.CALCULATED,
        'scope': [ParameterScope.ROOM, ParameterScope.AREA, ParameterScope.SHAFT],
        'default': '0.0',
        'description': 'Площадь элемента в м² (вычисляется автоматически)'
    },
    'BESS_Calculated_Perimeter_M': {
        'type': ParameterType.CALCULATED,
        'scope': [ParameterScope.ROOM, ParameterScope.AREA],
        'default': '0.0',
        'description': 'Периметр элемента в м (вычисляется автоматически)'
    },
    'BESS_Calculated_Volume_M3': {
        'type': ParameterType.CALCULATED,
        'scope': [ParameterScope.ROOM],
        'default': '0.0',
        'description': 'Объем помещения в м³ (вычисляется автоматически)'
    },
    
    # === ФУНКЦИОНАЛЬНЫЕ ПАРАМЕТРЫ ===
    'BESS_Function_Category': {
        'type': ParameterType.ENUM,
        'scope': [ParameterScope.ROOM],
        'default': 'GENERAL',
        'enum_values': ['OFFICE', 'RESIDENTIAL', 'COMMERCIAL', 'INDUSTRIAL', 'STORAGE', 'MECHANICAL', 'CIRCULATION', 'GENERAL'],
        'description': 'Функциональная категория помещения'
    },
    'BESS_Occupancy_Type': {
        'type': ParameterType.ENUM,
        'scope': [ParameterScope.ROOM],
        'default': 'NORMAL',
        'enum_values': ['HIGH', 'NORMAL', 'LOW', 'NONE'],
        'description': 'Тип занятости помещения'
    },
    'BESS_Room_Type': {
        'type': ParameterType.ENUM,
        'scope': [ParameterScope.ROOM, ParameterScope.AREA],
        'default': 'ROOM',
        'enum_values': ['ROOM', 'VOID', 'SECOND_LIGHT', 'BALCONY', 'TERRACE', 'SHAFT'],
        'description': 'Тип элемента'
    },
    
    # === ИНЖЕНЕРНЫЕ ПАРАМЕТРЫ ===
    'BESS_HVAC_Zone': {
        'type': ParameterType.STRING,
        'scope': [ParameterScope.ROOM],
        'default': 'ZONE_01',
        'description': 'Зона HVAC системы'
    },
    'BESS_Fire_Zone': {
        'type': ParameterType.STRING,
        'scope': [ParameterScope.ROOM, ParameterScope.AREA],
        'default': 'FIRE_ZONE_01',
        'description': 'Пожарная зона'
    },
    'BESS_Building_Zone': {
        'type': ParameterType.STRING,
        'scope': [ParameterScope.ROOM, ParameterScope.AREA, ParameterScope.SHAFT],
        'default': 'MAIN_BUILDING',
        'description': 'Зона здания'
    },
    
    # === ТЕМПЕРАТУРНЫЕ ПАРАМЕТРЫ ===
    'BESS_Design_Temperature_C': {
        'type': ParameterType.NUMERIC,
        'scope': [ParameterScope.ROOM],
        'default': '22.0',
        'min_value': -50.0,
        'max_value': 50.0,
        'description': 'Расчетная температура в помещении, °C'
    },
    'BESS_Min_Temperature_C': {
        'type': ParameterType.NUMERIC,
        'scope': [ParameterScope.ROOM],
        'default': '18.0',
        'min_value': -50.0,
        'max_value': 50.0,
        'description': 'Минимальная температура в помещении, °C'
    },
    'BESS_Max_Temperature_C': {
        'type': ParameterType.NUMERIC,
        'scope': [ParameterScope.ROOM],
        'default': '26.0',
        'min_value': -50.0,
        'max_value': 50.0,
        'description': 'Максимальная температура в помещении, °C'
    },
    
    # === РАСЧЕТНЫЕ НАГРУЗКИ ===
    'BESS_Calculated_Heating_Load_W': {
        'type': ParameterType.CALCULATED,
        'scope': [ParameterScope.ROOM],
        'default': '0.0',
        'description': 'Расчетная тепловая нагрузка, Вт (вычисляется)'
    },
    'BESS_Calculated_Cooling_Load_W': {
        'type': ParameterType.CALCULATED,
        'scope': [ParameterScope.ROOM],
        'default': '0.0',
        'description': 'Расчетная холодильная нагрузка, Вт (вычисляется)'
    },
    'BESS_Calculated_Ventilation_Rate_M3H': {
        'type': ParameterType.CALCULATED,
        'scope': [ParameterScope.ROOM],
        'default': '0.0',
        'description': 'Расчетный расход вентиляции, м³/ч (вычисляется)'
    },
    
    # === СТАТУСНЫЕ ПАРАМЕТРЫ ===
    'BESS_Element_Status': {
        'type': ParameterType.ENUM,
        'scope': [ParameterScope.ROOM, ParameterScope.AREA, ParameterScope.OPENING, ParameterScope.SHAFT],
        'default': 'ACTIVE',
        'enum_values': ['ACTIVE', 'INACTIVE', 'DELETED', 'BLOCKED', 'MODIFIED'],
        'description': 'Статус элемента'
    },
    'BESS_Area_Excluded': {
        'type': ParameterType.BOOLEAN,
        'scope': [ParameterScope.ROOM, ParameterScope.AREA],
        'default': 'False',
        'description': 'Исключить из расчета площади'
    },
    'BESS_Energy_Excluded': {
        'type': ParameterType.BOOLEAN,
        'scope': [ParameterScope.ROOM],
        'default': 'False',
        'description': 'Исключить из энергетических расчетов'
    },
    
    # === МЕТАДАННЫЕ ===
    'BESS_Created_At': {
        'type': ParameterType.STRING,
        'scope': [ParameterScope.ROOM, ParameterScope.AREA, ParameterScope.OPENING, ParameterScope.SHAFT],
        'default': '',
        'description': 'Время создания элемента'
    },
    'BESS_Modified_At': {
        'type': ParameterType.STRING,
        'scope': [ParameterScope.ROOM, ParameterScope.AREA, ParameterScope.OPENING, ParameterScope.SHAFT],
        'default': '',
        'description': 'Время последнего изменения'
    }
}


class BESSParameterManager:
    """
    Менеджер параметров BESS для централизованного управления
    
    Обеспечивает единообразную работу с параметрами элементов здания,
    их валидацию, вычисление и синхронизацию.
    """
    
    def __init__(self):
        """Инициализация менеджера параметров"""
        # Кэш для вычисляемых параметров
        self._calculated_cache = {}
        self._dirty_cache = set()
        
        # Настройки
        self.auto_calculate = True  # Автоматическое вычисление параметров
        self.validate_on_set = True  # Валидация при установке значений
        self.sync_levels = True     # Синхронизация с изменениями уровней
        
        print("✅ BESSParameterManager инициализирован")
    
    @staticmethod
    def prefixed_params(params: Dict[str, Any]) -> Dict[str, str]:
        """
        Добавление префикса BESS_ к параметрам
        
        Args:
            params: Исходные параметры
            
        Returns:
            Параметры с префиксом BESS_
        """
        prefixed = {}
        
        for key, value in params.items():
            # Если уже есть префикс BESS_, оставляем как есть
            if key.startswith('BESS_'):
                prefixed[key] = str(value)
            else:
                # Добавляем префикс
                prefixed[f'BESS_{key}'] = str(value)
        
        return prefixed
    
    @staticmethod
    def normalize_parameter_value(param_name: str, value: Any) -> str:
        """
        Нормализация значения параметра согласно его типу
        
        Args:
            param_name: Имя параметра
            value: Значение для нормализации
            
        Returns:
            Нормализованное строковое значение
        """
        if param_name not in BESS_PARAMETER_SCHEMA:
            # Для неизвестных параметров просто преобразуем в строку
            return str(value) if value is not None else ''
        
        schema = BESS_PARAMETER_SCHEMA[param_name]
        param_type = schema['type']
        
        try:
            if param_type == ParameterType.BOOLEAN:
                if isinstance(value, bool):
                    return 'True' if value else 'False'
                elif isinstance(value, str):
                    return 'True' if value.lower() in ['true', '1', 'yes', 'on'] else 'False'
                else:
                    return 'True' if value else 'False'
            
            elif param_type == ParameterType.NUMERIC:
                float_val = float(value)
                
                # Проверяем ограничения
                min_val = schema.get('min_value')
                max_val = schema.get('max_value')
                
                if min_val is not None and float_val < min_val:
                    float_val = min_val
                if max_val is not None and float_val > max_val:
                    float_val = max_val
                
                # Округляем до 2 знаков для большинства параметров
                if param_name.endswith('_M') or param_name.endswith('_M2') or param_name.endswith('_M3'):
                    return str(r2(float_val))
                else:
                    return str(float_val)
            
            elif param_type == ParameterType.ENUM:
                str_val = str(value).upper()
                enum_values = schema.get('enum_values', [])
                
                if str_val in enum_values:
                    return str_val
                else:
                    # Возвращаем значение по умолчанию
                    return schema.get('default', enum_values[0] if enum_values else str_val)
            
            else:
                # Для остальных типов - строковое представление
                return str(value) if value is not None else schema.get('default', '')
                
        except (ValueError, TypeError):
            # При ошибке преобразования возвращаем значение по умолчанию
            return schema.get('default', str(value) if value is not None else '')
    
    def apply_default_parameters(self, element: Dict[str, Any], 
                                scope: ParameterScope) -> Dict[str, Any]:
        """
        Применение параметров по умолчанию для элемента
        
        Args:
            element: Элемент для обработки
            scope: Область применения (ROOM, AREA, etc.)
            
        Returns:
            Элемент с дополненными параметрами
        """
        if 'params' not in element:
            element['params'] = {}
        
        params = element['params']
        
        # Добавляем обязательные параметры
        for param_name, schema in BESS_PARAMETER_SCHEMA.items():
            if scope in schema['scope']:
                if param_name not in params:
                    # Устанавливаем значение по умолчанию
                    default_value = schema.get('default', '')
                    
                    # Для вычисляемых параметров сразу вычисляем
                    if schema['type'] == ParameterType.CALCULATED:
                        calculated_value = self._calculate_parameter(element, param_name)
                        params[param_name] = calculated_value
                    else:
                        params[param_name] = default_value
        
        # Добавляем метаданные если отсутствуют
        if 'BESS_Created_At' not in params:
            params['BESS_Created_At'] = datetime.now().isoformat()
        
        params['BESS_Modified_At'] = datetime.now().isoformat()
        
        return element
    
    def calculate_all_parameters(self, element: Dict[str, Any], 
                               levels: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Вычисление всех вычисляемых параметров элемента
        
        Args:
            element: Элемент для расчета
            levels: Список уровней здания для расчета высот
            
        Returns:
            Элемент с обновленными вычисляемыми параметрами
        """
        if 'params' not in element:
            element['params'] = {}
        
        params = element['params']
        element_id = element.get('id', 'unknown')
        
        # Помечаем кэш как грязный для данного элемента
        self._dirty_cache.add(element_id)
        
        # Геометрические параметры
        coords = element.get('outer_xy_m', [])
        if coords and len(coords) >= 3 and GEOMETRY_UTILS_AVAILABLE:
            # Площадь
            area = abs(polygon_area(coords))
            params['BESS_Calculated_Area_M2'] = str(r2(area))
            
            # Периметр
            perimeter = 0.0
            for i in range(len(coords)):
                j = (i + 1) % len(coords)
                dx = coords[j][0] - coords[i][0]
                dy = coords[j][1] - coords[i][1]
                perimeter += (dx * dx + dy * dy) ** 0.5
            params['BESS_Calculated_Perimeter_M'] = str(r2(perimeter))
            
            # Объем (для помещений)
            room_type = params.get('BESS_Room_Type', 'ROOM')
            if room_type == 'ROOM':
                height_str = params.get('BESS_Room_Height', '3.0')
                try:
                    height = float(height_str)
                    volume = area * height
                    params['BESS_Calculated_Volume_M3'] = str(r2(volume))
                except (ValueError, TypeError):
                    params['BESS_Calculated_Volume_M3'] = '0.0'
        
        # Высота помещения
        if levels and element.get('outer_xy_m'):
            from .architectural_tools import ArchitecturalTools
            height = ArchitecturalTools.compute_room_height(element, levels)
            if height > 0:
                params['BESS_Room_Height'] = str(r2(height))
        
        # Расчетные нагрузки (упрощенные формулы)
        self._calculate_thermal_loads(element)
        
        # Вентиляция
        self._calculate_ventilation_rate(element)
        
        # Обновляем кэш
        if element_id in self._dirty_cache:
            self._dirty_cache.remove(element_id)
        
        self._calculated_cache[element_id] = params.copy()
        
        return element
    
    def _calculate_parameter(self, element: Dict[str, Any], param_name: str) -> str:
        """Вычисление конкретного параметра"""
        if param_name == 'BESS_Calculated_Area_M2':
            coords = element.get('outer_xy_m', [])
            if coords and len(coords) >= 3 and GEOMETRY_UTILS_AVAILABLE:
                area = abs(polygon_area(coords))
                return str(r2(area))
        
        elif param_name == 'BESS_Calculated_Volume_M3':
            coords = element.get('outer_xy_m', [])
            if coords and len(coords) >= 3 and GEOMETRY_UTILS_AVAILABLE:
                area = abs(polygon_area(coords))
                height_str = element.get('params', {}).get('BESS_Room_Height', '3.0')
                try:
                    height = float(height_str)
                    volume = area * height
                    return str(r2(volume))
                except (ValueError, TypeError):
                    pass
        
        # Значение по умолчанию
        schema = BESS_PARAMETER_SCHEMA.get(param_name, {})
        return schema.get('default', '0.0')
    
    def _calculate_thermal_loads(self, element: Dict[str, Any]):
        """Упрощенный расчет тепловых нагрузок"""
        params = element['params']
        
        try:
            area = float(params.get('BESS_Calculated_Area_M2', '0'))
            volume = float(params.get('BESS_Calculated_Volume_M3', '0'))
            
            if area <= 0:
                params['BESS_Calculated_Heating_Load_W'] = '0.0'
                params['BESS_Calculated_Cooling_Load_W'] = '0.0'
                return
            
            # Упрощенные коэффициенты (Вт/м²)
            function_category = params.get('BESS_Function_Category', 'GENERAL')
            occupancy_type = params.get('BESS_Occupancy_Type', 'NORMAL')
            
            # Базовые нагрузки по функциям
            heating_coeffs = {
                'OFFICE': 80.0,
                'RESIDENTIAL': 60.0,
                'COMMERCIAL': 100.0,
                'INDUSTRIAL': 50.0,
                'STORAGE': 30.0,
                'MECHANICAL': 40.0,
                'CIRCULATION': 50.0,
                'GENERAL': 70.0
            }
            
            cooling_coeffs = {
                'OFFICE': 90.0,
                'RESIDENTIAL': 70.0,
                'COMMERCIAL': 120.0,
                'INDUSTRIAL': 60.0,
                'STORAGE': 40.0,
                'MECHANICAL': 50.0,
                'CIRCULATION': 60.0,
                'GENERAL': 80.0
            }
            
            # Коэффициенты занятости
            occupancy_mult = {
                'HIGH': 1.3,
                'NORMAL': 1.0,
                'LOW': 0.7,
                'NONE': 0.3
            }
            
            heating_coeff = heating_coeffs.get(function_category, 70.0)
            cooling_coeff = cooling_coeffs.get(function_category, 80.0)
            occ_mult = occupancy_mult.get(occupancy_type, 1.0)
            
            heating_load = area * heating_coeff * occ_mult
            cooling_load = area * cooling_coeff * occ_mult
            
            params['BESS_Calculated_Heating_Load_W'] = str(r2(heating_load))
            params['BESS_Calculated_Cooling_Load_W'] = str(r2(cooling_load))
            
        except (ValueError, TypeError):
            params['BESS_Calculated_Heating_Load_W'] = '0.0'
            params['BESS_Calculated_Cooling_Load_W'] = '0.0'
    
    def _calculate_ventilation_rate(self, element: Dict[str, Any]):
        """Упрощенный расчет расхода вентиляции"""
        params = element['params']
        
        try:
            volume = float(params.get('BESS_Calculated_Volume_M3', '0'))
            
            if volume <= 0:
                params['BESS_Calculated_Ventilation_Rate_M3H'] = '0.0'
                return
            
            # Кратности воздухообмена по функциям (1/ч)
            air_changes = {
                'OFFICE': 4.0,
                'RESIDENTIAL': 2.0,
                'COMMERCIAL': 6.0,
                'INDUSTRIAL': 8.0,
                'STORAGE': 1.0,
                'MECHANICAL': 10.0,
                'CIRCULATION': 3.0,
                'GENERAL': 3.0
            }
            
            function_category = params.get('BESS_Function_Category', 'GENERAL')
            air_change_rate = air_changes.get(function_category, 3.0)
            
            ventilation_rate = volume * air_change_rate
            params['BESS_Calculated_Ventilation_Rate_M3H'] = str(r2(ventilation_rate))
            
        except (ValueError, TypeError):
            params['BESS_Calculated_Ventilation_Rate_M3H'] = '0.0'
    
    def validate_parameter(self, param_name: str, value: Any, 
                          scope: Optional[ParameterScope] = None) -> Dict[str, Any]:
        """
        Валидация параметра
        
        Args:
            param_name: Имя параметра
            value: Значение для валидации
            scope: Область применения
            
        Returns:
            Результат валидации
        """
        result = {
            'is_valid': True,
            'normalized_value': str(value),
            'errors': [],
            'warnings': []
        }
        
        if param_name not in BESS_PARAMETER_SCHEMA:
            result['warnings'].append(f"Неизвестный параметр: {param_name}")
            return result
        
        schema = BESS_PARAMETER_SCHEMA[param_name]
        
        # Проверка области применения
        if scope and scope not in schema['scope']:
            result['errors'].append(f"Параметр {param_name} не применим к области {scope.value}")
            result['is_valid'] = False
        
        # Нормализация и валидация значения
        try:
            normalized = self.normalize_parameter_value(param_name, value)
            result['normalized_value'] = normalized
            
            # Дополнительная валидация для числовых параметров
            param_type = schema['type']
            if param_type == ParameterType.NUMERIC:
                float_val = float(normalized)
                min_val = schema.get('min_value')
                max_val = schema.get('max_value')
                
                if min_val is not None and float_val < min_val:
                    result['warnings'].append(f"Значение {float_val} меньше минимального {min_val}")
                if max_val is not None and float_val > max_val:
                    result['warnings'].append(f"Значение {float_val} больше максимального {max_val}")
            
            elif param_type == ParameterType.ENUM:
                enum_values = schema.get('enum_values', [])
                if normalized not in enum_values:
                    result['errors'].append(f"Недопустимое значение {normalized}. Допустимые: {enum_values}")
                    result['is_valid'] = False
            
        except (ValueError, TypeError) as e:
            result['errors'].append(f"Ошибка нормализации значения: {e}")
            result['is_valid'] = False
        
        return result
    
    def get_parameter_info(self, param_name: str) -> Optional[Dict[str, Any]]:
        """Получение информации о параметре"""
        return BESS_PARAMETER_SCHEMA.get(param_name)
    
    def get_parameters_by_scope(self, scope: ParameterScope) -> Dict[str, Dict]:
        """Получение всех параметров для указанной области"""
        result = {}
        for param_name, schema in BESS_PARAMETER_SCHEMA.items():
            if scope in schema['scope']:
                result[param_name] = schema
        return result
    
    def resolve_alias(self, alias: str) -> str:
        """Разрешение алиаса в полное имя параметра"""
        return ALIAS_TO_PARAM.get(alias, alias)
    
    def sync_with_levels(self, elements: List[Dict[str, Any]], 
                        levels: List[Dict]) -> int:
        """
        Синхронизация параметров с изменениями в уровнях
        
        Args:
            elements: Список элементов для синхронизации
            levels: Обновленный список уровней
            
        Returns:
            Количество обновленных элементов
        """
        updated_count = 0
        
        for element in elements:
            if 'params' not in element:
                continue
            
            params = element['params']
            element_level = params.get('BESS_level', '')
            
            # Проверяем существование уровня
            level_exists = any(l.get('name') == element_level for l in levels)
            if not level_exists and element_level:
                params['BESS_Element_Status'] = 'BLOCKED'
                params['BESS_Modified_At'] = datetime.now().isoformat()
                updated_count += 1
                continue
            
            # Пересчитываем высоту помещения
            if element.get('outer_xy_m') and levels:
                old_height = params.get('BESS_Room_Height', '3.0')
                
                from .architectural_tools import ArchitecturalTools
                new_height = ArchitecturalTools.compute_room_height(element, levels)
                
                if new_height > 0 and abs(float(old_height) - new_height) > 0.01:
                    params['BESS_Room_Height'] = str(r2(new_height))
                    
                    # Пересчитываем зависимые параметры
                    self.calculate_all_parameters(element, levels)
                    updated_count += 1
        
        return updated_count
    
    def export_parameter_settings(self) -> Dict[str, Any]:
        """Экспорт настроек параметров"""
        return {
            'schema_version': '1.0',
            'parameter_schema': BESS_PARAMETER_SCHEMA,
            'aliases': ALIAS_TO_PARAM,
            'manager_settings': {
                'auto_calculate': self.auto_calculate,
                'validate_on_set': self.validate_on_set,
                'sync_levels': self.sync_levels
            },
            'exported_at': datetime.now().isoformat()
        }
    
    def get_statistics(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Получение статистики по параметрам"""
        stats = {
            'total_elements': len(elements),
            'parameter_usage': {},
            'validation_issues': 0,
            'calculated_parameters': 0,
            'by_scope': {}
        }
        
        for element in elements:
            params = element.get('params', {})
            element_type = params.get('BESS_Room_Type', 'UNKNOWN')
            
            # Определяем scope
            if element_type == 'ROOM':
                scope = ParameterScope.ROOM
            elif element_type in ['VOID', 'SECOND_LIGHT']:
                scope = ParameterScope.AREA
            elif element_type == 'SHAFT':
                scope = ParameterScope.SHAFT
            else:
                scope = ParameterScope.ROOM  # По умолчанию
            
            scope_name = scope.value
            if scope_name not in stats['by_scope']:
                stats['by_scope'][scope_name] = 0
            stats['by_scope'][scope_name] += 1
            
            # Подсчет использования параметров
            for param_name in params.keys():
                if param_name not in stats['parameter_usage']:
                    stats['parameter_usage'][param_name] = 0
                stats['parameter_usage'][param_name] += 1
                
                # Подсчет вычисляемых параметров
                if param_name in BESS_PARAMETER_SCHEMA:
                    schema = BESS_PARAMETER_SCHEMA[param_name]
                    if schema['type'] == ParameterType.CALCULATED:
                        stats['calculated_parameters'] += 1
        
        return stats