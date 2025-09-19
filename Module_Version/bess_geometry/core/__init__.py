# -*- coding: utf-8 -*-
"""
Core пакет системы BESS_Geometry

Этот пакет содержит всю бизнес-логику системы - основные алгоритмы и операции,
которые не зависят от пользовательского интерфейса или способа хранения данных.

Философия core пакета:
- Полная независимость от UI компонентов
- Высокая производительность и оптимизированные алгоритмы
- Строгая валидация входных данных
- Возможность использования в других проектах

Основные компоненты:
- SpatialProcessor: мощный геометрический процессор для пространственного анализа
- FileManager: универсальная система работы с файлами различных форматов
- GeometryValidator: комплексная валидация геометрических данных
- SpatialCalculator: высокоточные геометрические расчеты
"""

# Импортируем основные классы из spatial_processor
try:
    from .spatial_processor import (
        SpatialProcessor,
        GeometryValidator, 
        SpatialCalculator,
        GeometricProperties,
        SpatialRelationship
    )
    SPATIAL_PROCESSOR_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: spatial_processor недоступен - {e}")
    SPATIAL_PROCESSOR_AVAILABLE = False

# Импортируем файловый менеджер
try:
    from .file_manager import (
        FileManager,
        FileValidator,
        ContamExporter,
        FileOperationResult,
        FileFormatInfo
    )
    FILE_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: file_manager недоступен - {e}")
    FILE_MANAGER_AVAILABLE = False

# Попытаемся импортировать geometry_operations (может быть еще в корне проекта)
try:
    from .geometry_operations import (
        GeometryOperations,
        DrawingMode,
        OperationType,
        GeometryOperation
    )
    GEOMETRY_OPERATIONS_AVAILABLE = True
except ImportError:
    # Пробуем импортировать из корня проекта (legacy расположение)
    try:
        import sys
        from pathlib import Path
        # Добавляем родительский каталог в путь поиска модулей
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
        print("✅ geometry_operations импортирован из корня проекта")
    except ImportError as e:
        print(f"Предупреждение: geometry_operations недоступен - {e}")
        GEOMETRY_OPERATIONS_AVAILABLE = False

# Попытаемся импортировать утилиты (могут быть в корне проекта)
try:
    from ..geometry_utils import centroid_xy, bounds, r2, polygon_area
    from ..performance import PerformanceMonitor, RenderCache, SpatialIndex
    UTILITIES_AVAILABLE = True
except ImportError:
    try:
        import sys
        from pathlib import Path
        parent_path = str(Path(__file__).parent.parent)
        if parent_path not in sys.path:
            sys.path.insert(0, parent_path)
        
        from geometry_utils import centroid_xy, bounds, r2, polygon_area
        from performance import PerformanceMonitor, RenderCache, SpatialIndex
        UTILITIES_AVAILABLE = True
        print("✅ Утилиты импортированы из корня проекта")
    except ImportError as e:
        print(f"Критическое предупреждение: Утилиты недоступны - {e}")
        UTILITIES_AVAILABLE = False

# Публичный API этого пакета
__all__ = []

if SPATIAL_PROCESSOR_AVAILABLE:
    __all__.extend([
        'SpatialProcessor',
        'GeometryValidator',
        'SpatialCalculator',
        'GeometricProperties',
        'SpatialRelationship'
    ])

if FILE_MANAGER_AVAILABLE:
    __all__.extend([
        'FileManager',
        'FileValidator',
        'ContamExporter',
        'FileOperationResult',
        'FileFormatInfo'
    ])

if GEOMETRY_OPERATIONS_AVAILABLE:
    __all__.extend([
        'GeometryOperations',
        'DrawingMode',
        'OperationType',
        'GeometryOperation'
    ])

# Метаинформация пакета
__version__ = '1.0.0'
__author__ = 'BESS_Geometry Development Team'
__description__ = 'Core business logic for building geometry processing'

# Настройки ядра системы по умолчанию
CORE_SETTINGS = {
    'geometry_tolerance': {
        'distance_m': 0.01,        # 1 см - минимальное различимое расстояние
        'area_m2': 0.0001,         # 1 см² - минимальная различимая площадь  
        'snap_m': 0.05,            # 5 см - радиус привязки точек
        'adjacency_m': 0.1,        # 10 см - порог определения смежности помещений
    },
    'performance_limits': {
        'max_polygon_vertices': 1000,      # Максимальное количество вершин в полигоне
        'max_elements_per_level': 5000,    # Максимальное количество элементов на уровне
        'spatial_index_grid_size': 10.0,   # Размер сетки пространственного индекса (метры)
    },
    'validation': {
        'min_room_area_m2': 0.1,           # Минимальная площадь помещения
        'max_aspect_ratio': 100.0,         # Максимальное соотношение сторон элемента
        'allow_self_intersecting': False,  # Разрешать самопересекающиеся полигоны
    },
    'building_defaults': {
        'default_height_m': 3.0,           # Высота помещений по умолчанию
        'default_floor_thickness_m': 0.2,  # Толщина перекрытий
        'default_wall_thickness_m': 0.2,   # Толщина стен
    }
}

def get_core_version():
    """
    Возвращает версию ядра системы
    
    Эта функция полезна для диагностики совместимости между компонентами
    и для отображения информации о версии в пользовательском интерфейсе
    
    Returns:
        str: Версия ядра в формате semantic versioning (major.minor.patch)
    """
    return __version__

def validate_core_installation():
    """
    Проверяет корректность установки всех компонентов ядра
    
    Эта функция выполняет комплексную проверку доступности всех основных
    компонентов ядра системы и возвращает детальный отчет о состоянии установки
    
    Returns:
        dict: Детальный отчет о состоянии установки компонентов ядра
    """
    validation_report = {
        'core_version': get_core_version(),
        'installation_valid': True,
        'components': {
            'spatial_processor': SPATIAL_PROCESSOR_AVAILABLE,
            'file_manager': FILE_MANAGER_AVAILABLE,
            'geometry_operations': GEOMETRY_OPERATIONS_AVAILABLE,
            'utilities': UTILITIES_AVAILABLE
        },
        'critical_missing': [],
        'warnings': [],
        'recommendations': []
    }
    
    # Проверяем критически важные компоненты
    if not SPATIAL_PROCESSOR_AVAILABLE:
        validation_report['installation_valid'] = False
        validation_report['critical_missing'].append('spatial_processor')
    
    if not UTILITIES_AVAILABLE:
        validation_report['installation_valid'] = False
        validation_report['critical_missing'].append('utilities')
    
    # Проверяем дополнительные компоненты
    if not FILE_MANAGER_AVAILABLE:
        validation_report['warnings'].append('file_manager недоступен - ограничена функциональность работы с файлами')
    
    if not GEOMETRY_OPERATIONS_AVAILABLE:
        validation_report['warnings'].append('geometry_operations недоступен - ограничена функциональность редактирования')
    
    # Добавляем рекомендации
    if validation_report['critical_missing']:
        validation_report['recommendations'].append('Переустановите недостающие критические компоненты')
    
    if validation_report['warnings']:
        validation_report['recommendations'].append('Рассмотрите возможность установки дополнительных компонентов для полной функциональности')
    
    return validation_report

def get_geometry_tolerance():
    """
    Возвращает текущие настройки точности геометрических операций
    
    Эти значения используются во всех геометрических расчетах для обеспечения
    консистентности результатов по всей системе
    
    Returns:
        dict: Словарь с настройками точности геометрических операций
    """
    return CORE_SETTINGS['geometry_tolerance'].copy()

def get_core_status():
    """
    Возвращает статус доступности основных компонентов ядра
    
    Эта функция полезна для диагностики проблем при загрузке модулей
    и для определения доступных возможностей системы
    
    Returns:
        dict: Словарь со статусом каждого компонента (True/False)
    """
    return {
        'spatial_processor': SPATIAL_PROCESSOR_AVAILABLE,
        'file_manager': FILE_MANAGER_AVAILABLE,
        'geometry_operations': GEOMETRY_OPERATIONS_AVAILABLE,
        'utilities': UTILITIES_AVAILABLE
    }

def create_spatial_processor(custom_settings=None):
    """
    Фабричная функция для создания настроенного SpatialProcessor
    
    ИСПРАВЛЕННАЯ ВЕРСИЯ: Использует элегантное делегирование к правильной
    фабричной функции из модуля spatial_processor, обеспечивая совместимость
    с новым API и избегая дублирования логики создания объектов.
    
    Архитектурный принцип: Эта функция служит адаптером между старым API
    (основанным на CORE_SETTINGS) и новым API (основанным на явных параметрах).
    Такой подход обеспечивает обратную совместимость и единообразный интерфейс.
    
    Args:
        custom_settings (dict, optional): Пользовательские настройки для переопределения
                                        стандартных значений. Может содержать:
                                        - 'tolerance': float - геометрический допуск
                                        - 'default_height': float - высота по умолчанию
                                        - любые другие настройки из CORE_SETTINGS
        
    Returns:
        SpatialProcessor: Настроенный экземпляр процессора с корректными параметрами
        
    Raises:
        ImportError: Если SpatialProcessor недоступен
        ValueError: Если переданы некорректные настройки
        
    Example:
        # Создание с настройками по умолчанию
        processor = create_spatial_processor()
        
        # Создание с пользовательскими настройками
        custom = {
            'tolerance': 0.005,  # более высокая точность
            'default_height': 2.7  # нестандартная высота потолков
        }
        processor = create_spatial_processor(custom)
    """
    # Проверяем доступность компонента
    if not SPATIAL_PROCESSOR_AVAILABLE:
        raise ImportError(
            "SpatialProcessor недоступен. Проверьте установку модуля spatial_processor. "
            "Возможно, требуется переустановка core пакета."
        )
    
    # Импортируем правильную фабричную функцию из spatial_processor
    # Это ключевой момент - мы делегируем создание объекта специализированной функции,
    # которая знает точную сигнатуру конструктора SpatialProcessor
    try:
        from .spatial_processor import create_spatial_processor as sp_factory
    except ImportError as e:
        raise ImportError(f"Не удается импортировать фабричную функцию из spatial_processor: {e}")
    
    # Объединяем настройки по умолчанию с пользовательскими
    # Это обеспечивает гибкость конфигурации при сохранении разумных значений по умолчанию
    effective_settings = CORE_SETTINGS.copy()
    if custom_settings:
        # Глубокое слияние настроек - важно для вложенных словарей
        for key, value in custom_settings.items():
            if key in effective_settings and isinstance(effective_settings[key], dict) and isinstance(value, dict):
                effective_settings[key].update(value)
            else:
                effective_settings[key] = value
    
    # Извлекаем параметры в соответствии с новым API SpatialProcessor
    # Tolerance (геометрический допуск) - критически важный параметр для точности расчетов
    tolerance = effective_settings['geometry_tolerance']['distance_m']
    if custom_settings and 'tolerance' in custom_settings:
        tolerance = custom_settings['tolerance']
        # Валидация разумных границ для tolerance
        if tolerance <= 0 or tolerance > 1.0:
            raise ValueError(f"Tolerance должен быть в диапазоне (0, 1.0], получен: {tolerance}")
    
    # Default height (высота по умолчанию) - используется для расчета объемов
    default_height = effective_settings['building_defaults']['default_height_m']
    if custom_settings and 'default_height' in custom_settings:
        default_height = custom_settings['default_height']
        # Валидация разумных границ для высоты
        if default_height <= 0 or default_height > 20.0:
            raise ValueError(f"Default height должен быть в диапазоне (0, 20.0], получен: {default_height}")
    
    # Создаем и возвращаем настроенный процессор через правильную фабричную функцию
    # Этот подход обеспечивает:
    # 1. Корректное создание объекта с правильными параметрами
    # 2. Централизованную логику инициализации в spatial_processor модуле
    # 3. Отсутствие дублирования кода инициализации
    try:
        processor = sp_factory(tolerance=tolerance, default_height=default_height)
        
        # Логируем успешное создание для отладки
        print(f"✅ SpatialProcessor создан через делегирование (tolerance: {tolerance}м, height: {default_height}м)")
        
        return processor
        
    except Exception as e:
        # Предоставляем подробную информацию об ошибке для диагностики
        raise RuntimeError(
            f"Ошибка при создании SpatialProcessor через делегирование: {e}. "
            f"Параметры: tolerance={tolerance}, default_height={default_height}"
        ) from e

def create_file_manager():
    """
    Фабричная функция для создания FileManager
    
    Создает готовый к использованию файловый менеджер с поддержкой
    всех основных форматов файлов системы BESS_Geometry
    
    Returns:
        FileManager: Готовый к использованию файловый менеджер
        
    Raises:
        ImportError: Если FileManager недоступен
    """
    if not FILE_MANAGER_AVAILABLE:
        raise ImportError(
            "FileManager недоступен. Проверьте установку модуля file_manager. "
            "Возможно, требуется переустановка core пакета."
        )
    
    # Аналогично SpatialProcessor, при необходимости можно добавить
    # делегирование к специализированной фабричной функции
    try:
        file_manager = FileManager()
        print("✅ FileManager создан успешно")
        return file_manager
    except Exception as e:
        raise RuntimeError(f"Ошибка при создании FileManager: {e}") from e

# Добавляем фабричные функции в публичный API
__all__.extend([
    'create_spatial_processor',
    'create_file_manager',
    'get_core_version',
    'validate_core_installation',
    'get_geometry_tolerance',
    'get_core_status',
    'CORE_SETTINGS'
])