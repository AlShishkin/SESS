# -*- coding: utf-8 -*-
"""
Core пакет системы BESS_Geometry (ОБНОВЛЕННАЯ ВЕРСИЯ С ИНТЕГРАЦИЕЙ)

Этот пакет содержит всю бизнес-логику системы включая новые интегрированные
компоненты: ArchitecturalTools, ShaftManager, BESSParameterManager и
расширенный IntegrationManager.

НОВЫЕ ВОЗМОЖНОСТИ ЭТАПА 3:
- ArchitecturalTools: создание VOID помещений и второго света
- ShaftManager: управление шахтами по уровням
- BESSParameterManager: продвинутая система параметров
- IntegrationManager: координация интеграции всех компонентов
- Расширенные GeometryOperations с поддержкой новых операций

Философия core пакета:
- Полная независимость от UI компонентов
- Высокая производительность и оптимизированные алгоритмы  
- Строгая валидация входных данных
- Возможность использования в других проектах
- Graceful degradation при отсутствии компонентов
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union

# === ИМПОРТ ОСНОВНЫХ КЛАССОВ ИЗ SPATIAL_PROCESSOR ===
try:
    from .spatial_processor import (
        SpatialProcessor,
        GeometryValidator, 
        SpatialCalculator,
        GeometricProperties,
        SpatialRelationship
    )
    SPATIAL_PROCESSOR_AVAILABLE = True
    print("✅ SpatialProcessor успешно импортирован")
except ImportError as e:
    print(f"Предупреждение: spatial_processor недоступен - {e}")
    SPATIAL_PROCESSOR_AVAILABLE = False

# === ИМПОРТ FILE MANAGER ===
try:
    from .file_manager import (
        FileManager,
        FileValidator,
        ContamExporter,
        FileOperationResult,
        FileFormatInfo
    )
    FILE_MANAGER_AVAILABLE = True
    print("✅ FileManager успешно импортирован")
except ImportError as e:
    print(f"Предупреждение: file_manager недоступен - {e}")
    FILE_MANAGER_AVAILABLE = False

# === ИМПОРТ GEOMETRY OPERATIONS ===
try:
    from .geometry_operations import (
        GeometryOperations,
        DrawingMode,
        OperationType,
        GeometryOperation,
        GeometryValidationLevel
    )
    GEOMETRY_OPERATIONS_AVAILABLE = True
    print("✅ GeometryOperations успешно импортирован")
except ImportError:
    # Пробуем импортировать из корня проекта (legacy расположение)
    try:
        import sys
        from pathlib import Path
        parent_path = str(Path(__file__).parent.parent)
        if parent_path not in sys.path:
            sys.path.insert(0, parent_path)
        
        from geometry_operations import (
            GeometryOperations,
            DrawingMode,
            OperationType,
            GeometryOperation
        )
        GEOMETRY_OPERATIONS_AVAILABLE = True
        print("✅ GeometryOperations импортирован из корня проекта (legacy)")
    except ImportError as e:
        print(f"Предупреждение: geometry_operations недоступен - {e}")
        GEOMETRY_OPERATIONS_AVAILABLE = False

# === НОВЫЕ ИМПОРТЫ ИНТЕГРИРОВАННЫХ КОМПОНЕНТОВ ===

# Импорт ArchitecturalTools
try:
    from .architectural_tools import ArchitecturalTools
    ARCHITECTURAL_TOOLS_AVAILABLE = True
    print("✅ ArchitecturalTools успешно импортирован")
except ImportError as e:
    print(f"Предупреждение: ArchitecturalTools недоступен - {e}")
    ARCHITECTURAL_TOOLS_AVAILABLE = False

# Импорт ShaftManager  
try:
    from .shaft_manager import ShaftManager
    SHAFT_MANAGER_AVAILABLE = True
    print("✅ ShaftManager успешно импортирован")
except ImportError as e:
    print(f"Предупреждение: ShaftManager недоступен - {e}")
    SHAFT_MANAGER_AVAILABLE = False

# Импорт BESSParameterManager
try:
    from .bess_parameters import BESSParameterManager, ParameterScope
    BESS_PARAMETERS_AVAILABLE = True
    print("✅ BESSParameterManager успешно импортирован")
except ImportError as e:
    print(f"Предупреждение: BESSParameterManager недоступен - {e}")
    BESS_PARAMETERS_AVAILABLE = False

# Импорт IntegrationManager
try:
    from .integration_manager import IntegrationManager, ComponentStatus, IntegrationLevel
    INTEGRATION_MANAGER_AVAILABLE = True
    print("✅ IntegrationManager успешно импортирован")
except ImportError as e:
    print(f"Предупреждение: IntegrationManager недоступен - {e}")
    INTEGRATION_MANAGER_AVAILABLE = False

# Импорт расширенных EditingModes
try:
    from .editing_modes import (
        EditingMode,
        DrawRoomMode,
        AddVoidMode,
        AddSecondLightMode,
        EditingModeManager,
        EditingModeType
    )
    EDITING_MODES_AVAILABLE = True
    print("✅ Расширенные EditingModes успешно импортированы")
except ImportError as e:
    print(f"Предупреждение: расширенные EditingModes недоступны - {e}")
    EDITING_MODES_AVAILABLE = False

# === ОБНОВЛЕННЫЙ PUBLIC API ===
__all__ = [
    # Основные компоненты (существующие)
    'SpatialProcessor',
    'GeometryValidator',
    'SpatialCalculator', 
    'GeometricProperties',
    'SpatialRelationship',
    'FileManager',
    'FileValidator',
    'ContamExporter',
    'FileOperationResult',
    'FileFormatInfo',
    'GeometryOperations',
    'DrawingMode',
    'OperationType',
    'GeometryOperation',
    
    # НОВЫЕ ИНТЕГРИРОВАННЫЕ КОМПОНЕНТЫ
    'ArchitecturalTools',
    'ShaftManager',
    'BESSParameterManager',
    'ParameterScope',
    'IntegrationManager',
    'ComponentStatus',
    'IntegrationLevel',
    
    # Расширенные режимы редактирования
    'EditingMode',
    'DrawRoomMode', 
    'AddVoidMode',
    'AddSecondLightMode',
    'EditingModeManager',
    'EditingModeType',
    
    # Фабричные функции
    'create_spatial_processor',
    'create_file_manager',
    'create_shaft_manager',
    'create_parameter_manager',
    'create_integration_manager',
    
    # Утилиты
    'get_core_version',
    'validate_core_installation',
    'get_integration_status',
    'validate_integration'
]

# === РАСШИРЕННЫЕ НАСТРОЙКИ ЯДРА ===
CORE_SETTINGS = {
    'version': '1.3.0',  # Обновили версию для этапа 3
    'integration_level': 'full',  # Новый параметр
    'geometry_tolerance': {
        'coordinate_precision': 1e-6,
        'area_threshold': 1e-4,
        'angle_tolerance': 1e-8,
        'void_min_area': 0.1,        # НОВОЕ: минимальная площадь VOID
        'second_light_min_area': 1.0  # НОВОЕ: минимальная площадь второго света
    },
    'bess_parameters': {            # НОВАЯ СЕКЦИЯ
        'auto_apply': True,
        'validate_parameters': True,
        'calculation_precision': 0.01
    },
    'shaft_management': {          # НОВАЯ СЕКЦИЯ
        'auto_clone_levels': True,
        'validate_shaft_geometry': True,
        'default_shaft_height': 3.0
    },
    'integration': {               # НОВАЯ СЕКЦИЯ
        'auto_discover_components': True,
        'retry_failed_components': True,
        'max_retry_attempts': 3,
        'component_timeout': 30
    }
}

# === ФАБРИЧНЫЕ ФУНКЦИИ (СУЩЕСТВУЮЩИЕ И НОВЫЕ) ===

def create_spatial_processor(custom_settings=None):
    """
    Фабричная функция для создания настроенного SpatialProcessor
    
    Args:
        custom_settings (dict, optional): Пользовательские настройки
    
    Returns:
        SpatialProcessor или None если недоступен
    """
    if not SPATIAL_PROCESSOR_AVAILABLE:
        print("Предупреждение: SpatialProcessor недоступен")
        return None
    
    settings = CORE_SETTINGS.copy()
    if custom_settings:
        settings.update(custom_settings)
    
    return SpatialProcessor(
        coordinate_precision=settings['geometry_tolerance']['coordinate_precision'],
        area_threshold=settings['geometry_tolerance']['area_threshold']
    )

def create_file_manager(custom_settings=None):
    """
    Фабричная функция для создания FileManager
    
    Returns:
        FileManager или None если недоступен
    """
    if not FILE_MANAGER_AVAILABLE:
        print("Предупреждение: FileManager недоступен")
        return None
    
    return FileManager()

def create_shaft_manager():
    """
    НОВАЯ ФАБРИЧНАЯ ФУНКЦИЯ: Создание ShaftManager
    
    Returns:
        ShaftManager или None если недоступен
    """
    if not SHAFT_MANAGER_AVAILABLE:
        print("Предупреждение: ShaftManager недоступен")
        return None
    
    shaft_manager = ShaftManager()
    
    # Применяем настройки из CORE_SETTINGS
    if hasattr(shaft_manager, 'set_auto_clone'):
        shaft_manager.set_auto_clone(CORE_SETTINGS['shaft_management']['auto_clone_levels'])
    
    if hasattr(shaft_manager, 'set_default_height'):
        shaft_manager.set_default_height(CORE_SETTINGS['shaft_management']['default_shaft_height'])
    
    return shaft_manager

def create_parameter_manager():
    """
    НОВАЯ ФАБРИЧНАЯ ФУНКЦИЯ: Создание BESSParameterManager
    
    Returns:
        BESSParameterManager или None если недоступен
    """
    if not BESS_PARAMETERS_AVAILABLE:
        print("Предупреждение: BESSParameterManager недоступен")
        return None
    
    param_manager = BESSParameterManager()
    
    # Применяем настройки
    if hasattr(param_manager, 'set_auto_apply'):
        param_manager.set_auto_apply(CORE_SETTINGS['bess_parameters']['auto_apply'])
    
    if hasattr(param_manager, 'set_calculation_precision'):
        param_manager.set_calculation_precision(CORE_SETTINGS['bess_parameters']['calculation_precision'])
    
    return param_manager

def create_integration_manager(main_controller=None):
    """
    НОВАЯ ФАБРИЧНАЯ ФУНКЦИЯ: Создание IntegrationManager
    
    Args:
        main_controller: Главный контроллер для интеграции
        
    Returns:
        IntegrationManager или None если недоступен
    """
    if not INTEGRATION_MANAGER_AVAILABLE:
        print("Предупреждение: IntegrationManager недоступен")
        return None
    
    integration_manager = IntegrationManager(main_controller)
    
    # Применяем настройки интеграции
    integration_settings = CORE_SETTINGS['integration']
    integration_manager.auto_retry_failed = integration_settings['retry_failed_components']
    integration_manager.max_retry_attempts = integration_settings['max_retry_attempts']
    integration_manager.component_timeout = integration_settings['component_timeout']
    
    return integration_manager

def create_geometry_operations_with_integration(state=None):
    """
    НОВАЯ ФАБРИЧНАЯ ФУНКЦИЯ: Создание GeometryOperations с интегрированными компонентами
    
    Args:
        state: Состояние приложения
        
    Returns:
        GeometryOperations с подключенными компонентами
    """
    if not GEOMETRY_OPERATIONS_AVAILABLE:
        print("Предупреждение: GeometryOperations недоступен")
        return None
    
    geom_ops = GeometryOperations(state)
    
    # Интегрируем доступные компоненты
    if BESS_PARAMETERS_AVAILABLE:
        geom_ops.parameter_manager = create_parameter_manager()
    
    if SHAFT_MANAGER_AVAILABLE:
        geom_ops.shaft_manager = create_shaft_manager()
    
    # Настраиваем параметры валидации
    geom_ops.validate_before_create = True
    geom_ops.auto_apply_parameters = CORE_SETTINGS['bess_parameters']['auto_apply']
    
    return geom_ops

# === УТИЛИТЫ ПРОВЕРКИ И ВАЛИДАЦИИ ===

def get_core_version():
    """Получение версии ядра системы"""
    return CORE_SETTINGS['version']

def validate_core_installation():
    """
    Комплексная валидация установки ядра с интегрированными компонентами
    
    Returns:
        dict: Подробный отчет о валидации
    """
    validation_report = {
        'installation_valid': True,
        'core_version': get_core_version(),
        'components': {
            'spatial_processor': SPATIAL_PROCESSOR_AVAILABLE,
            'file_manager': FILE_MANAGER_AVAILABLE,
            'geometry_operations': GEOMETRY_OPERATIONS_AVAILABLE,
            'architectural_tools': ARCHITECTURAL_TOOLS_AVAILABLE,
            'shaft_manager': SHAFT_MANAGER_AVAILABLE,
            'bess_parameters': BESS_PARAMETERS_AVAILABLE,
            'integration_manager': INTEGRATION_MANAGER_AVAILABLE,
            'editing_modes': EDITING_MODES_AVAILABLE
        },
        'integration_level': _determine_integration_level(),
        'critical_missing': [],
        'warnings': [],
        'recommendations': [],
        'timestamp': datetime.now().isoformat()
    }
    
    # Проверяем критические компоненты
    critical_components = ['spatial_processor', 'geometry_operations']
    for component in critical_components:
        if not validation_report['components'][component]:
            validation_report['installation_valid'] = False
            validation_report['critical_missing'].append(component)
    
    # Проверяем интегрированные компоненты
    integration_components = ['architectural_tools', 'shaft_manager', 'bess_parameters']
    missing_integration = [comp for comp in integration_components 
                          if not validation_report['components'][comp]]
    
    if missing_integration:
        if len(missing_integration) >= 2:
            validation_report['warnings'].append(
                f'Несколько интегрированных компонентов недоступны: {", ".join(missing_integration)}'
            )
        else:
            validation_report['warnings'].append(
                f'Интегрированный компонент недоступен: {missing_integration[0]}'
            )
    
    # Генерируем рекомендации
    if validation_report['critical_missing']:
        validation_report['recommendations'].append('Переустановите недостающие критические компоненты')
    
    if missing_integration:
        validation_report['recommendations'].append('Установите недостающие компоненты для полной функциональности')
    
    if validation_report['integration_level'] == 'partial':
        validation_report['recommendations'].append('Используйте IntegrationManager для диагностики проблем интеграции')
    
    return validation_report

def get_integration_status():
    """
    НОВАЯ ФУНКЦИЯ: Получение статуса интеграции компонентов
    
    Returns:
        dict: Статус доступности всех компонентов
    """
    return {
        'core_components': {
            'spatial_processor': SPATIAL_PROCESSOR_AVAILABLE,
            'file_manager': FILE_MANAGER_AVAILABLE,
            'geometry_operations': GEOMETRY_OPERATIONS_AVAILABLE
        },
        'integrated_components': {
            'architectural_tools': ARCHITECTURAL_TOOLS_AVAILABLE,
            'shaft_manager': SHAFT_MANAGER_AVAILABLE,
            'bess_parameters': BESS_PARAMETERS_AVAILABLE,
            'integration_manager': INTEGRATION_MANAGER_AVAILABLE,
            'editing_modes': EDITING_MODES_AVAILABLE
        },
        'integration_level': _determine_integration_level(),
        'ready_for_stage3': _check_stage3_readiness()
    }

def _determine_integration_level():
    """Определение уровня интеграции системы"""
    integrated_count = sum([
        ARCHITECTURAL_TOOLS_AVAILABLE,
        SHAFT_MANAGER_AVAILABLE,
        BESS_PARAMETERS_AVAILABLE,
        INTEGRATION_MANAGER_AVAILABLE
    ])
    
    if integrated_count == 4:
        return 'full'
    elif integrated_count >= 2:
        return 'partial'
    else:
        return 'basic'

def _check_stage3_readiness():
    """Проверка готовности к этапу 3 интеграции"""
    essential_components = [
        SPATIAL_PROCESSOR_AVAILABLE,
        GEOMETRY_OPERATIONS_AVAILABLE,
        ARCHITECTURAL_TOOLS_AVAILABLE,
        INTEGRATION_MANAGER_AVAILABLE
    ]
    return all(essential_components)

def validate_integration():
    """
    НОВАЯ ФУНКЦИЯ: Валидация корректности интеграции компонентов
    
    Returns:
        dict: Результат валидации интеграции
    """
    validation = {
        'integration_valid': True,
        'issues': [],
        'suggestions': [],
        'component_tests': {}
    }
    
    # Тестируем основные компоненты
    if SPATIAL_PROCESSOR_AVAILABLE:
        try:
            processor = create_spatial_processor()
            validation['component_tests']['spatial_processor'] = processor is not None
        except Exception as e:
            validation['component_tests']['spatial_processor'] = False
            validation['issues'].append(f'SpatialProcessor не инициализируется: {e}')
    
    if ARCHITECTURAL_TOOLS_AVAILABLE:
        try:
            # Проверяем доступность основных методов ArchitecturalTools
            validation['component_tests']['architectural_tools'] = (
                hasattr(ArchitecturalTools, 'add_void') and 
                hasattr(ArchitecturalTools, 'add_second_light')
            )
        except Exception as e:
            validation['component_tests']['architectural_tools'] = False
            validation['issues'].append(f'ArchitecturalTools не работает корректно: {e}')
    
    # Проверяем взаимосвязи компонентов
    if GEOMETRY_OPERATIONS_AVAILABLE and BESS_PARAMETERS_AVAILABLE:
        try:
            geom_ops = create_geometry_operations_with_integration()
            has_param_manager = hasattr(geom_ops, 'parameter_manager') and geom_ops.parameter_manager is not None
            validation['component_tests']['geometry_bess_integration'] = has_param_manager
        except Exception as e:
            validation['component_tests']['geometry_bess_integration'] = False
            validation['issues'].append(f'Интеграция GeometryOperations и BESSParameters не работает: {e}')
    
    # Генерируем предложения
    if len(validation['issues']) > 0:
        validation['integration_valid'] = False
        validation['suggestions'].append('Запустите IntegrationManager для автоматической диагностики')
        validation['suggestions'].append('Проверьте логи инициализации компонентов')
    
    if _determine_integration_level() != 'full':
        validation['suggestions'].append('Установите все компоненты для полной функциональности')
    
    return validation

# === ВЫВОД СТАТУСА ИНИЦИАЛИЗАЦИИ ===
print(f"\n🏗️ BESS_Geometry Core v{get_core_version()} - Статус интеграции:")
print(f"  Уровень интеграции: {_determine_integration_level().upper()}")
print(f"  Готовность к этапу 3: {'✅' if _check_stage3_readiness() else '❌'}")

integration_status = get_integration_status()
core_ready = all(integration_status['core_components'].values())
integrated_ready = sum(integration_status['integrated_components'].values())

print(f"  Основные компоненты: {'✅' if core_ready else '⚠️'}")
print(f"  Интегрированные компоненты: {integrated_ready}/5")

if integrated_ready == 5:
    print("🎉 Все компоненты этапа 3 готовы к работе!")
elif integrated_ready >= 3:
    print("🔧 Частичная интеграция - система функциональна")
else:
    print("⚠️ Требуется дополнительная настройка компонентов")