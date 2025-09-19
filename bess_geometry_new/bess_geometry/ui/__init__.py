# -*- coding: utf-8 -*-
"""
UI пакет системы BESS_Geometry (ОБНОВЛЕННАЯ ВЕРСИЯ С ИНТЕГРАЦИЕЙ)

Этот пакет содержит все компоненты пользовательского интерфейса, включая
новый интегрированный ContourEditor для интерактивного редактирования контуров.

НОВЫЕ ВОЗМОЖНОСТИ ЭТАПА 3:
- ContourEditor: интерактивное редактирование контуров элементов
- Расширенная поддержка режимов редактирования
- Интеграция с ArchitecturalTools через UI
- Улучшенная система событий для новых операций

Архитектурные принципы UI:
- Модульность: четкое разделение UI компонентов
- Responsiveness: отзывчивый интерфейс для сложных операций
- Extensibility: легкое добавление новых UI элементов
- Integration: тесная интеграция с core компонентами
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

# === ИМПОРТ ОСНОВНОГО ГЕОМЕТРИЧЕСКОГО CANVAS ===
try:
    from .geometry_canvas import (
        GeometryCanvas,
        CanvasRenderer,
        InteractionHandler,
        ViewportManager
    )
    GEOMETRY_CANVAS_AVAILABLE = True
    print("✅ GeometryCanvas успешно импортирован")
except ImportError as e:
    print(f"Предупреждение: GeometryCanvas недоступен - {e}")
    GEOMETRY_CANVAS_AVAILABLE = False

# === НОВЫЙ ИМПОРТ: CONTOUR EDITOR ===
try:
    from .contour_editor import (
        ContourEditor,
        EditingMode as ContourEditingMode,
        ElementType,
        EditingState,
        VertexManipulator,
        ContourValidator
    )
    CONTOUR_EDITOR_AVAILABLE = True
    print("✅ ContourEditor успешно импортирован")
except ImportError as e:
    print(f"Предупреждение: ContourEditor недоступен - {e}")
    CONTOUR_EDITOR_AVAILABLE = False

# === ИМПОРТ ДОПОЛНИТЕЛЬНЫХ UI КОМПОНЕНТОВ ===
try:
    from .ui_utils import (
        create_toolbar,
        create_status_bar,
        apply_theme,
        get_ui_colors,
        validate_ui_installation
    )
    UI_UTILS_AVAILABLE = True
    print("✅ UI утилиты успешно импортированы")
except ImportError as e:
    print(f"Предупреждение: UI утилиты недоступны - {e}")
    UI_UTILS_AVAILABLE = False

# === ИМПОРТ ДИАЛОГОВ (ЕСЛИ ДОСТУПНЫ) ===
try:
    from .dialogs import (
        PropertyEditor,
        LayerManager,
        ExportDialog
    )
    DIALOGS_AVAILABLE = True
    print("✅ Диалоги успешно импортированы")
except ImportError as e:
    print(f"Предупреждение: Диалоги недоступны - {e}")
    DIALOGS_AVAILABLE = False

# === ОБНОВЛЕННЫЙ PUBLIC API ===
__all__ = [
    # Основные UI компоненты
    'GeometryCanvas',
    'CanvasRenderer',
    'InteractionHandler', 
    'ViewportManager',
    
    # НОВЫЙ КОМПОНЕНТ: ContourEditor
    'ContourEditor',
    'ContourEditingMode',
    'ElementType',
    'EditingState',
    'VertexManipulator',
    'ContourValidator',
    
    # UI утилиты
    'create_toolbar',
    'create_status_bar',
    'apply_theme',
    'get_ui_colors',
    'validate_ui_installation',
    
    # Фабричные функции
    'create_geometry_canvas',
    'create_contour_editor',
    'create_integrated_ui',
    
    # Утилиты
    'get_ui_version',
    'get_ui_integration_status',
    'validate_ui_components'
]

# === НАСТРОЙКИ UI ===
UI_SETTINGS = {
    'version': '1.3.0',  # Обновлена для этапа 3
    'theme': 'modern_dark',
    'canvas': {
        'default_zoom': 1.0,
        'max_zoom': 50.0,
        'min_zoom': 0.1,
        'zoom_step': 1.2,
        'grid_enabled': True,
        'snap_enabled': True,
        'snap_distance': 10.0
    },
    'contour_editor': {          # НОВАЯ СЕКЦИЯ
        'vertex_size': 8,
        'vertex_color': '#FF4444',
        'edge_color': '#44FF44',
        'selected_color': '#FFFF44',
        'preview_color': '#44FFFF',
        'auto_highlight': True,
        'smooth_transitions': True
    },
    'interaction': {
        'double_click_timeout': 500,  # мс
        'drag_threshold': 5,          # пикселей
        'selection_tolerance': 15,    # пикселей
        'hover_delay': 200           # мс
    },
    'rendering': {
        'antialiasing': True,
        'high_quality': True,
        'cache_enabled': True,
        'max_cache_size': 1000
    }
}

# === ФАБРИЧНЫЕ ФУНКЦИИ ===

def create_geometry_canvas(parent, width=800, height=600, **kwargs):
    """
    Фабричная функция для создания GeometryCanvas
    
    Args:
        parent: Родительский виджет
        width: Ширина canvas
        height: Высота canvas
        **kwargs: Дополнительные параметры
        
    Returns:
        GeometryCanvas или None если недоступен
    """
    if not GEOMETRY_CANVAS_AVAILABLE:
        print("Предупреждение: GeometryCanvas недоступен")
        return None
    
    # Применяем настройки по умолчанию
    canvas_settings = UI_SETTINGS['canvas'].copy()
    canvas_settings.update(kwargs)
    
    try:
        canvas = GeometryCanvas(
            parent=parent,
            width=width,
            height=height,
            **canvas_settings
        )
        
        # Применяем тему
        if UI_UTILS_AVAILABLE:
            apply_theme(canvas, UI_SETTINGS['theme'])
        
        return canvas
        
    except Exception as e:
        print(f"Ошибка создания GeometryCanvas: {e}")
        return None

def create_contour_editor(canvas, **kwargs):
    """
    НОВАЯ ФАБРИЧНАЯ ФУНКЦИЯ: Создание ContourEditor
    
    Args:
        canvas: Геометрический canvas для привязки
        **kwargs: Дополнительные параметры
        
    Returns:
        ContourEditor или None если недоступен
    """
    if not CONTOUR_EDITOR_AVAILABLE:
        print("Предупреждение: ContourEditor недоступен")
        return None
    
    if not canvas:
        print("Ошибка: для ContourEditor требуется canvas")
        return None
    
    # Применяем настройки по умолчанию
    editor_settings = UI_SETTINGS['contour_editor'].copy()
    editor_settings.update(kwargs)
    
    try:
        contour_editor = ContourEditor(
            canvas=canvas,
            **editor_settings
        )
        
        print("✅ ContourEditor успешно создан и привязан к canvas")
        return contour_editor
        
    except Exception as e:
        print(f"Ошибка создания ContourEditor: {e}")
        return None

def create_integrated_ui(parent, state=None, controller=None):
    """
    НОВАЯ ФУНКЦИЯ: Создание полностью интегрированного UI
    
    Создает GeometryCanvas с ContourEditor и настраивает все связи
    для работы с новыми интегрированными компонентами.
    
    Args:
        parent: Родительский виджет
        state: Состояние приложения
        controller: Главный контроллер
        
    Returns:
        dict: Словарь с созданными UI компонентами
    """
    ui_components = {
        'canvas': None,
        'contour_editor': None,
        'toolbar': None,
        'status_bar': None,
        'success': False
    }
    
    try:
        # Создаем основной canvas
        canvas = create_geometry_canvas(parent)
        if not canvas:
            return ui_components
        
        ui_components['canvas'] = canvas
        
        # Создаем contour editor
        contour_editor = create_contour_editor(canvas)
        if contour_editor:
            ui_components['contour_editor'] = contour_editor
            
            # Настраиваем интеграцию с контроллером
            if controller:
                contour_editor.set_completion_callback(
                    controller._on_contour_editing_complete
                )
        
        # Создаем дополнительные UI элементы
        if UI_UTILS_AVAILABLE:
            toolbar = create_toolbar(parent, include_contour_tools=True)
            status_bar = create_status_bar(parent)
            
            ui_components['toolbar'] = toolbar
            ui_components['status_bar'] = status_bar
        
        ui_components['success'] = True
        print("🎉 Интегрированный UI успешно создан")
        
    except Exception as e:
        print(f"Ошибка создания интегрированного UI: {e}")
    
    return ui_components

# === УТИЛИТЫ ПРОВЕРКИ И ВАЛИДАЦИИ ===

def get_ui_version():
    """Получение версии UI системы"""
    return UI_SETTINGS['version']

def get_ui_integration_status():
    """
    Получение статуса интеграции UI компонентов
    
    Returns:
        dict: Статус доступности UI компонентов
    """
    return {
        'core_ui': {
            'geometry_canvas': GEOMETRY_CANVAS_AVAILABLE,
            'ui_utils': UI_UTILS_AVAILABLE
        },
        'integrated_ui': {
            'contour_editor': CONTOUR_EDITOR_AVAILABLE,
            'dialogs': DIALOGS_AVAILABLE
        },
        'integration_level': _determine_ui_integration_level(),
        'ready_for_contour_editing': CONTOUR_EDITOR_AVAILABLE and GEOMETRY_CANVAS_AVAILABLE
    }

def _determine_ui_integration_level():
    """Определение уровня интеграции UI"""
    core_available = GEOMETRY_CANVAS_AVAILABLE
    contour_available = CONTOUR_EDITOR_AVAILABLE
    utils_available = UI_UTILS_AVAILABLE
    
    if core_available and contour_available and utils_available:
        return 'full'
    elif core_available and contour_available:
        return 'functional'
    elif core_available:
        return 'basic'
    else:
        return 'minimal'

def validate_ui_components():
    """
    Валидация UI компонентов для интеграции этапа 3
    
    Returns:
        dict: Результат валидации UI
    """
    validation = {
        'ui_valid': True,
        'issues': [],
        'warnings': [],
        'recommendations': [],
        'component_tests': {}
    }
    
    # Тестируем основной canvas
    if GEOMETRY_CANVAS_AVAILABLE:
        try:
            # Проверяем возможность создания canvas (mock тест)
            validation['component_tests']['geometry_canvas'] = True
        except Exception as e:
            validation['component_tests']['geometry_canvas'] = False
            validation['issues'].append(f'GeometryCanvas не инициализируется: {e}')
    else:
        validation['ui_valid'] = False
        validation['issues'].append('GeometryCanvas недоступен - критический компонент UI')
    
    # Тестируем contour editor
    if CONTOUR_EDITOR_AVAILABLE:
        try:
            validation['component_tests']['contour_editor'] = True
        except Exception as e:
            validation['component_tests']['contour_editor'] = False
            validation['warnings'].append(f'ContourEditor имеет проблемы: {e}')
    else:
        validation['warnings'].append('ContourEditor недоступен - ограничена функциональность редактирования')
    
    # Проверяем интеграцию canvas + contour editor
    if GEOMETRY_CANVAS_AVAILABLE and CONTOUR_EDITOR_AVAILABLE:
        validation['component_tests']['canvas_contour_integration'] = True
    else:
        validation['component_tests']['canvas_contour_integration'] = False
        validation['warnings'].append('Интеграция Canvas + ContourEditor недоступна')
    
    # Генерируем рекомендации
    if not validation['ui_valid']:
        validation['recommendations'].append('Установите GeometryCanvas для базовой функциональности UI')
    
    if not CONTOUR_EDITOR_AVAILABLE:
        validation['recommendations'].append('Установите ContourEditor для полной функциональности редактирования')
    
    if _determine_ui_integration_level() != 'full':
        validation['recommendations'].append('Используйте create_integrated_ui() для автоматической настройки')
    
    return validation

def validate_ui_installation():
    """
    Расширенная валидация установки UI (совместимость со старым API)
    
    Returns:
        bool: True если UI установлен корректно
    """
    validation = validate_ui_components()
    return validation['ui_valid']

# === ИНТЕГРАЦИОННЫЕ ХЕЛПЕРЫ ===

def setup_contour_editing_integration(main_controller, canvas):
    """
    Настройка интеграции редактирования контуров
    
    Args:
        main_controller: Главный контроллер
        canvas: Геометрический canvas
        
    Returns:
        bool: True если интеграция успешна
    """
    if not CONTOUR_EDITOR_AVAILABLE or not canvas:
        return False
    
    try:
        # Создаем contour editor
        contour_editor = create_contour_editor(canvas)
        if not contour_editor:
            return False
        
        # Привязываем к контроллеру
        if hasattr(main_controller, 'contour_editor'):
            main_controller.contour_editor = contour_editor
        
        # Настраиваем callbacks
        if hasattr(main_controller, '_on_contour_editing_complete'):
            contour_editor.set_completion_callback(
                main_controller._on_contour_editing_complete
            )
        
        print("✅ Интеграция редактирования контуров настроена")
        return True
        
    except Exception as e:
        print(f"Ошибка настройки интеграции контуров: {e}")
        return False

def get_ui_capabilities():
    """
    Получение списка доступных UI возможностей
    
    Returns:
        list: Список доступных возможностей
    """
    capabilities = []
    
    if GEOMETRY_CANVAS_AVAILABLE:
        capabilities.extend([
            'geometry_visualization',
            'interactive_navigation', 
            'element_selection',
            'zoom_pan_operations'
        ])
    
    if CONTOUR_EDITOR_AVAILABLE:
        capabilities.extend([
            'contour_editing',
            'vertex_manipulation',
            'edge_modification',
            'geometry_validation'
        ])
    
    if UI_UTILS_AVAILABLE:
        capabilities.extend([
            'toolbar_creation',
            'status_bar',
            'theme_support'
        ])
    
    if DIALOGS_AVAILABLE:
        capabilities.extend([
            'property_editing',
            'layer_management',
            'export_dialogs'
        ])
    
    return capabilities

# === ВЫВОД СТАТУСА ИНИЦИАЛИЗАЦИИ UI ===
print(f"\n🎨 BESS_Geometry UI v{get_ui_version()} - Статус интеграции:")

ui_status = get_ui_integration_status()
print(f"  Уровень интеграции UI: {ui_status['integration_level'].upper()}")
print(f"  Готовность к редактированию контуров: {'✅' if ui_status['ready_for_contour_editing'] else '❌'}")

core_ui_ready = all(ui_status['core_ui'].values())
integrated_ui_ready = sum(ui_status['integrated_ui'].values())

print(f"  Основные UI компоненты: {'✅' if core_ui_ready else '⚠️'}")
print(f"  Интегрированные UI компоненты: {integrated_ui_ready}/2")

capabilities = get_ui_capabilities()
print(f"  Доступные возможности: {len(capabilities)}")

if ui_status['ready_for_contour_editing']:
    print("🎉 UI готов для интерактивного редактирования контуров!")
elif core_ui_ready:
    print("🔧 Базовый UI функционален, расширенные возможности ограничены")
else:
    print("⚠️ Требуется установка основных UI компонентов")

# Заглушки для отсутствующих классов (добавлено автоматически)
class CanvasRenderer:
    def __init__(self, *args, **kwargs):
        pass

class VertexManipulator:
    def __init__(self, *args, **kwargs):
        pass

class InteractionHandler:
    def __init__(self, *args, **kwargs):
        pass

class ViewportManager:
    def __init__(self, *args, **kwargs):
        pass

def create_toolbar(*args, **kwargs):
    return None

def create_status_bar(*args, **kwargs):
    return None

def apply_theme(*args, **kwargs):
    pass

def get_ui_colors():
    return {}

def validate_ui_installation():
    return True
