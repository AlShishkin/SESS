# -*- coding: utf-8 -*-
"""
BESS_Geometry - Building Energy Spatial System

Комплексная система для обработки геометрии зданий в задачах энергетического анализа.
Эта система позволяет импортировать геометрические данные из BIM-систем (Revit),
обрабатывать их, редактировать и экспортировать в специализированные форматы
для программ расчета энергопотребления и воздушных потоков.

Основные возможности:
• Импорт геометрии из Revit через специализированный экспортер
• Интерактивное редактирование планов зданий с точной геометрией
• Автоматическое выявление пространственных связей между помещениями
• Экспорт в формат CONTAM для расчета воздушных потоков
• Высокопроизводительная визуализация сложных геометрических моделей

Архитектурные принципы:
• Модульность: четкое разделение между UI, бизнес-логикой и контроллерами
• Производительность: оптимизированные алгоритмы для больших объемов данных
• Расширяемость: система плагинов для добавления новой функциональности
• Надежность: комплексная валидация данных и обработка ошибок
"""

# Определяем версию системы в одном месте
__version__ = '1.0.0'
__author__ = 'BESS_Geometry Development Team'
__email__ = 'contact@bess-geometry.org'
__license__ = 'MIT'
__description__ = 'Building Energy Spatial System for geometry processing'

# Импортируем основные компоненты системы с обработкой ошибок
# Это позволяет системе работать даже если некоторые модули недоступны

# Пытаемся импортировать ядро системы
try:
    from .core import (
        SpatialProcessor,
        FileManager,
        GeometryValidator,
        create_spatial_processor,
        create_file_manager,
        get_core_version,
        validate_core_installation
    )
    CORE_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: Ядро системы недоступно - {e}")
    CORE_AVAILABLE = False

# Пытаемся импортировать UI компоненты
try:
    from .ui import (
        GeometryCanvas,
        create_geometry_canvas,
        get_ui_version,
        apply_theme,
        validate_ui_installation
    )
    UI_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: UI компоненты недоступны - {e}")
    UI_AVAILABLE = False

# Пытаемся импортировать систему контроллеров
try:
    from .controllers import (
        controller_manager,
        BaseController,
        ControllerManager
    )
    CONTROLLERS_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: Контроллеры недоступны - {e}")
    CONTROLLERS_AVAILABLE = False

# Импортируем утилиты (они должны быть всегда доступны)
try:
    from .geometry_utils import centroid_xy, bounds, r2, polygon_area
    from .performance import PerformanceMonitor, RenderCache, SpatialIndex
    from .state import AppState, ALIAS_TO_PARAM
    UTILITIES_AVAILABLE = True
except ImportError as e:
    print(f"Критическое предупреждение: Утилиты недоступны - {e}")
    UTILITIES_AVAILABLE = False

# Определяем публичный API всей системы
# Это то, что пользователи могут импортировать через "from bess_geometry import ..."
__all__ = []

# Добавляем доступные компоненты в публичный API
if CORE_AVAILABLE:
    __all__.extend([
        'SpatialProcessor',
        'FileManager', 
        'GeometryValidator',
        'create_spatial_processor',
        'create_file_manager'
    ])

if UI_AVAILABLE:
    __all__.extend([
        'GeometryCanvas',
        'create_geometry_canvas',
        'apply_theme'
    ])

if CONTROLLERS_AVAILABLE:
    __all__.extend([
        'controller_manager',
        'BaseController'
    ])

if UTILITIES_AVAILABLE:
    __all__.extend([
        'centroid_xy',
        'bounds', 
        'r2',
        'polygon_area',
        'PerformanceMonitor'
    ])

# Всегда добавляем информационные функции
__all__.extend([
    'get_version',
    'get_system_status',
    'run_diagnostics',
    'create_application'
])

def get_version():
    """
    Возвращает версию системы BESS_Geometry
    
    Эта функция предоставляет единую точку для получения информации о версии,
    что важно для диагностики совместимости и отладки проблем.
    
    Returns:
        str: Версия системы в формате semantic versioning (major.minor.patch)
        
    Example:
        >>> import bess_geometry
        >>> print(f"Версия BESS_Geometry: {bess_geometry.get_version()}")
        Версия BESS_Geometry: 1.0.0
    """
    return __version__

def get_system_status():
    """
    Возвращает детальную информацию о состоянии всех компонентов системы
    
    Эта функция выполняет проверку доступности всех основных модулей
    и возвращает структурированную информацию об их состоянии.
    Особенно полезна для диагностики проблем при развертывании.
    
    Returns:
        dict: Словарь с информацией о состоянии каждого компонента
        
    Example:
        >>> status = bess_geometry.get_system_status()
        >>> if status['overall_health']:
        ...     print("Система полностью функциональна")
        ... else:
        ...     print(f"Проблемы: {status['issues']}")
    """
    status = {
        'version': __version__,
        'components': {
            'core': CORE_AVAILABLE,
            'ui': UI_AVAILABLE, 
            'controllers': CONTROLLERS_AVAILABLE,
            'utilities': UTILITIES_AVAILABLE
        },
        'issues': [],
        'overall_health': True
    }
    
    # Анализируем состояние компонентов
    if not CORE_AVAILABLE:
        status['issues'].append("Ядро системы недоступно - ограниченная функциональность")
        status['overall_health'] = False
    
    if not UI_AVAILABLE:
        status['issues'].append("UI компоненты недоступны - графический интерфейс не работает")
        status['overall_health'] = False
        
    if not UTILITIES_AVAILABLE:
        status['issues'].append("Утилиты недоступны - критическая ошибка")
        status['overall_health'] = False
    
    if not CONTROLLERS_AVAILABLE:
        status['issues'].append("Контроллеры недоступны - ограниченная архитектура MVC")
    
    # Если есть хотя бы ядро и утилиты, система может работать
    if CORE_AVAILABLE and UTILITIES_AVAILABLE:
        status['can_process_geometry'] = True
    else:
        status['can_process_geometry'] = False
        
    if UI_AVAILABLE and UTILITIES_AVAILABLE:
        status['can_display_ui'] = True
    else:
        status['can_display_ui'] = False
    
    return status

def run_diagnostics():
    """
    Выполняет полную диагностику системы и возвращает детальный отчет
    
    Эта функция не только проверяет доступность модулей, но и тестирует
    их работоспособность, создавая тестовые объекты и выполняя базовые операции.
    Используйте её для глубокой диагностики проблем.
    
    Returns:
        dict: Детальный отчет о результатах диагностики
        
    Example:
        >>> report = bess_geometry.run_diagnostics()
        >>> print(f"Диагностика завершена. Ошибок: {len(report['errors'])}")
        >>> for error in report['errors']:
        ...     print(f"  - {error}")
    """
    report = {
        'timestamp': None,
        'system_info': get_system_status(),
        'detailed_tests': {},
        'errors': [],
        'warnings': [],
        'recommendations': []
    }
    
    from datetime import datetime
    report['timestamp'] = datetime.now().isoformat()
    
    # Тестируем ядро системы
    if CORE_AVAILABLE:
        try:
            # Проверяем возможность создания основных объектов
            processor = create_spatial_processor()
            file_manager = create_file_manager()
            
            # Выполняем валидацию установки ядра
            core_valid, core_issues = validate_core_installation()
            report['detailed_tests']['core'] = {
                'processor_creation': True,
                'file_manager_creation': True,
                'validation_passed': core_valid,
                'issues': core_issues
            }
            
            if not core_valid:
                report['errors'].extend(core_issues)
                
        except Exception as e:
            report['errors'].append(f"Ошибка тестирования ядра: {e}")
            report['detailed_tests']['core'] = {'error': str(e)}
    
    # Тестируем UI компоненты
    if UI_AVAILABLE:
        try:
            # Проверяем валидацию UI
            ui_valid, ui_issues = validate_ui_installation()
            report['detailed_tests']['ui'] = {
                'validation_passed': ui_valid,
                'issues': ui_issues
            }
            
            if not ui_valid:
                report['warnings'].extend(ui_issues)
                
        except Exception as e:
            report['errors'].append(f"Ошибка тестирования UI: {e}")
            report['detailed_tests']['ui'] = {'error': str(e)}
    
    # Генерируем рекомендации на основе найденных проблем
    if not CORE_AVAILABLE:
        report['recommendations'].append(
            "Установите недостающие модули ядра (spatial_processor.py, file_manager.py)"
        )
    
    if not UI_AVAILABLE:
        report['recommendations'].append(
            "Переместите geometry_canvas.py в директорию ui/ и создайте ui/__init__.py"
        )
        
    if not UTILITIES_AVAILABLE:
        report['recommendations'].append(
            "Проверьте наличие файлов geometry_utils.py, performance.py, state.py в корне проекта"
        )
    
    return report

def create_application():
    """
    Фабричная функция для создания готового к работе приложения BESS_Geometry
    
    Эта функция является главной точкой входа для создания приложения.
    Она автоматически определяет доступные компоненты и создает
    соответствующую конфигурацию приложения.
    
    Returns:
        object: Экземпляр приложения (ModernBessApp или LegacyApp)
        None: Если не удалось создать приложение
        
    Example:
        >>> app = bess_geometry.create_application()
        >>> if app:
        ...     app.run()
        ... else:
        ...     print("Не удалось создать приложение")
    """
    # Проверяем состояние системы
    status = get_system_status()
    
    if not status['overall_health']:
        print("Предупреждение: Система имеет проблемы, но попытаемся создать приложение...")
        for issue in status['issues']:
            print(f"  - {issue}")
    
    # Пытаемся создать современное приложение
    if UI_AVAILABLE and CORE_AVAILABLE:
        try:
            from .main_app import ModernBessApp
            app = ModernBessApp()
            if app.initialize():
                print("✅ Создано современное приложение с модульной архитектурой")
                return app
            else:
                print("❌ Не удалось инициализировать современное приложение")
        except Exception as e:
            print(f"❌ Ошибка создания современного приложения: {e}")
    
    # Fallback на legacy приложение
    try:
        from .app import App as LegacyApp
        app = LegacyApp()
        print("⚠️ Создано legacy приложение (ограниченная функциональность)")
        return app
    except Exception as e:
        print(f"❌ Не удалось создать даже legacy приложение: {e}")
    
    return None

def quick_start():
    """
    Быстрый запуск приложения BESS_Geometry с автоматической диагностикой
    
    Эта удобная функция выполняет диагностику системы и сразу запускает
    приложение, если это возможно. Идеально подходит для быстрого тестирования.
    
    Returns:
        bool: True если приложение успешно запущено и завершено
    """
    print("🚀 BESS_Geometry Quick Start")
    print("=" * 50)
    print(f"Версия: {get_version()}")
    print()
    
    # Выполняем быструю диагностику
    status = get_system_status()
    print("📊 Состояние системы:")
    for component, available in status['components'].items():
        icon = "✅" if available else "❌"
        print(f"  {icon} {component}")
    print()
    
    if not status['overall_health']:
        print("⚠️ Обнаружены проблемы:")
        for issue in status['issues']:
            print(f"  - {issue}")
        print()
    
    # Пытаемся создать и запустить приложение
    app = create_application()
    if app:
        try:
            return app.run() if hasattr(app, 'run') else app.mainloop()
        except Exception as e:
            print(f"❌ Ошибка во время работы приложения: {e}")
            return False
    else:
        print("❌ Не удалось создать приложение")
        return False

# Выводим информацию о статусе при импорте модуля
print(f"BESS_Geometry v{__version__} загружен")
_status = get_system_status()
if _status['overall_health']:
    print("✅ Все компоненты системы доступны")
else:
    available_count = sum(_status['components'].values())
    total_count = len(_status['components'])
    print(f"⚠️ Доступно {available_count}/{total_count} компонентов")
    print("Запустите bess_geometry.run_diagnostics() для детальной диагностики")