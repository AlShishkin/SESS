# -*- coding: utf-8 -*-
"""
UI пакет системы BESS_Geometry

Этот пакет содержит все компоненты пользовательского интерфейса для
системы обработки геометрии зданий. Включает виджеты для визуализации,
редактирования и взаимодействия с геометрическими данными.

Основные компоненты:
- GeometryCanvas: мощный компонент для отрисовки и редактирования геометрии
- Диалоги и формы для настройки параметров
- Система тем и стилизации интерфейса
"""

# Импортируем основные UI компоненты с обработкой ошибок
try:
    from .geometry_canvas import (
        GeometryCanvas,
        CoordinateSystem,
        GeometryRenderer
    )
    GEOMETRY_CANVAS_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: GeometryCanvas недоступен - {e}")
    GEOMETRY_CANVAS_AVAILABLE = False

# Определяем публичный API пакета
__all__ = []

if GEOMETRY_CANVAS_AVAILABLE:
    __all__.extend([
        'GeometryCanvas',
        'CoordinateSystem', 
        'GeometryRenderer'
    ])

# Метаинформация пакета
__version__ = '1.0.0'
__author__ = 'BESS_Geometry Development Team'
__description__ = 'User interface components for building geometry processing'

# Настройки UI по умолчанию
DEFAULT_UI_SETTINGS = {
    'theme': 'default',
    'canvas_background': '#ffffff',
    'grid_color': '#e0e0e0',
    'selection_color': '#00ff00',
    'font_family': 'Arial',
    'font_size': 10,
    'toolbar_size': 'medium',
    'enable_tooltips': True,
    'auto_save_layout': True
}

# Цветовые схемы для разных типов элементов
DEFAULT_ELEMENT_COLORS = {
    'room': {
        'fill': '#4cc9f0',
        'outline': '#0077be',
        'selected': '#00ff00',
        'hover': '#7dd3fc'
    },
    'area': {
        'fill': '#ff6b6b', 
        'outline': '#dc2626',
        'selected': '#00ff00',
        'hover': '#fca5a5'
    },
    'opening': {
        'fill': '#ffd93d',
        'outline': '#f59e0b', 
        'selected': '#00ff00',
        'hover': '#fde047'
    },
    'shaft': {
        'fill': '#d1d5db',
        'outline': '#6b7280',
        'selected': '#00ff00',
        'hover': '#e5e7eb'
    }
}


def create_geometry_canvas(parent, **kwargs):
    """
    Фабричная функция для создания GeometryCanvas
    
    Args:
        parent: Родительский виджет
        **kwargs: Дополнительные параметры конфигурации
        
    Returns:
        Экземпляр GeometryCanvas или None если недоступен
        
    Example:
        >>> import tkinter as tk
        >>> from ui import create_geometry_canvas
        >>> root = tk.Tk()
        >>> canvas = create_geometry_canvas(root)
        >>> canvas.canvas.pack(fill='both', expand=True)
    """
    if not GEOMETRY_CANVAS_AVAILABLE:
        raise ImportError(
            "GeometryCanvas недоступен. Проверьте корректность установки UI компонентов."
        )
    
    # Применяем настройки по умолчанию
    config = DEFAULT_UI_SETTINGS.copy()
    config.update(kwargs)
    
    return GeometryCanvas(parent, **config)


def get_ui_version():
    """
    Возвращает версию UI компонентов
    
    Returns:
        str: Версия в формате semantic versioning
    """
    return __version__


def apply_theme(theme_name: str = "default"):
    """
    Применение цветовой темы к UI компонентам
    
    Args:
        theme_name: Название темы ("default", "dark", "light", "contrast")
        
    Note:
        Эта функция будет расширена в будущих версиях для поддержки
        полноценной системы тем и стилизации интерфейса.
    """
    # Пока что заглушка для будущего функционала
    themes = {
        'default': DEFAULT_ELEMENT_COLORS,
        'dark': {
            # Темная тема будет добавлена позже
        },
        'light': {
            # Светлая тема будет добавлена позже  
        },
        'contrast': {
            # Высококонтрастная тема для доступности
        }
    }
    
    if theme_name not in themes:
        print(f"Предупреждение: Тема '{theme_name}' не найдена, используется 'default'")
        theme_name = 'default'
    
    # TODO: Реализовать применение темы к существующим компонентам
    print(f"Применена тема: {theme_name}")


def validate_ui_installation():
    """
    Проверка корректности установки UI компонентов
    
    Returns:
        tuple: (success: bool, issues: list) где success указывает на успешность
               установки, а issues содержит список обнаруженных проблем
    """
    issues = []
    
    # Проверяем доступность основных компонентов
    if not GEOMETRY_CANVAS_AVAILABLE:
        issues.append("GeometryCanvas недоступен")
    
    # Проверяем доступность tkinter
    try:
        import tkinter as tk
        # Пробуем создать тестовое окно
        test_root = tk.Tk()
        test_root.withdraw()  # Скрываем окно
        test_root.destroy()   # Удаляем окно
    except Exception as e:
        issues.append(f"Проблемы с tkinter: {e}")
    
    # Проверяем импорты зависимостей
    try:
        import sys
        import os
        import math
        import time
        from pathlib import Path
        from typing import Dict, List, Optional, Tuple
    except ImportError as e:
        issues.append(f"Отсутствуют базовые зависимости: {e}")
    
    # Проверяем доступность утилит
    try:
        import geometry_utils
        import performance
    except ImportError as e:
        issues.append(f"Утилиты недоступны: {e}")
    
    return len(issues) == 0, issues


def get_ui_status():
    """
    Получение детального статуса UI компонентов
    
    Returns:
        dict: Словарь с информацией о состоянии UI системы
    """
    is_valid, issues = validate_ui_installation()
    
    return {
        'version': __version__,
        'geometry_canvas_available': GEOMETRY_CANVAS_AVAILABLE,
        'installation_valid': is_valid,
        'issues': issues,
        'supported_themes': ['default', 'dark', 'light', 'contrast'],
        'default_settings': DEFAULT_UI_SETTINGS
    }


# Выполняем базовую инициализацию при импорте пакета
def _initialize_ui_package():
    """Инициализация UI пакета при импорте"""
    # Проверяем базовые требования
    is_valid, issues = validate_ui_installation()
    
    if not is_valid:
        print("Предупреждения при инициализации UI:")
        for issue in issues:
            print(f"  - {issue}")
    
    if GEOMETRY_CANVAS_AVAILABLE:
        print("✅ UI пакет BESS_Geometry инициализирован успешно")
    else:
        print("⚠️ UI пакет инициализирован с ограниченной функциональностью")


# Инициализируем пакет
_initialize_ui_package()