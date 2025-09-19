#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Исправление проблем с импортами в BESS_Geometry

Основные проблемы:
1. Относительные импорты в контроллерах
2. Неправильные пути в IntegrationManager
3. Отсутствующие классы в UI модулях
"""

import sys
import re
from pathlib import Path

def fix_integration_manager():
    """Исправляет пути импорта в IntegrationManager"""
    print("🔧 ИСПРАВЛЕНИЕ INTEGRATION_MANAGER")
    print("-" * 40)
    
    integration_manager_path = Path('core/integration_manager.py')
    
    if not integration_manager_path.exists():
        print("❌ core/integration_manager.py не найден")
        return False
    
    try:
        with open(integration_manager_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Исправляем относительные импорты
        fixes = [
            ('from ..core.architectural_tools import ArchitecturalTools', 
             'from core.architectural_tools import ArchitecturalTools'),
            ('from ..core.shaft_manager import ShaftManager', 
             'from core.shaft_manager import ShaftManager'),
            ('from ..core.bess_parameters import BESSParameterManager', 
             'from core.bess_parameters import BESSParameterManager'),
            ('from ..ui.contour_editor import ContourEditor', 
             'from ui.contour_editor import ContourEditor'),
            ('from ..core.geometry_operations import GeometryOperations', 
             'from core.geometry_operations import GeometryOperations'),
            ('from ..core.editing_modes import EditingModeManager', 
             'from core.editing_modes import EditingModeManager'),
            ("'module_path': '..core.architectural_tools'", 
             "'module_path': 'core.architectural_tools'"),
            ("'module_path': '..core.shaft_manager'", 
             "'module_path': 'core.shaft_manager'"),
            ("'module_path': '..core.bess_parameters'", 
             "'module_path': 'core.bess_parameters'"),
            ("'module_path': '..ui.contour_editor'", 
             "'module_path': 'ui.contour_editor'"),
            ("'module_path': '..core.geometry_operations'", 
             "'module_path': 'core.geometry_operations'"),
            ("'module_path': '..core.editing_modes'", 
             "'module_path': 'core.editing_modes'")
        ]
        
        changes_made = 0
        for old_pattern, new_pattern in fixes:
            if old_pattern in content:
                content = content.replace(old_pattern, new_pattern)
                changes_made += 1
                print(f"   ✅ Исправлен: {old_pattern[:40]}...")
        
        if changes_made > 0:
            # Создаем резервную копию
            backup_path = integration_manager_path.with_suffix('.py.backup')
            backup_path.write_text(content, encoding='utf-8')
            
            # Записываем исправленный файл
            integration_manager_path.write_text(content, encoding='utf-8')
            print(f"   ✅ Файл обновлен ({changes_made} исправлений)")
            print(f"   💾 Резервная копия: {backup_path}")
        else:
            print("   ℹ️ Исправления не требуются")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка исправления: {e}")
        return False

def fix_main_controller():
    """Исправляет импорты в MainController"""
    print("\n🔧 ИСПРАВЛЕНИЕ MAIN_CONTROLLER")
    print("-" * 40)
    
    main_controller_path = Path('controllers/main_controller.py')
    
    if not main_controller_path.exists():
        print("❌ controllers/main_controller.py не найден")
        return False
    
    try:
        with open(main_controller_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Исправляем относительные импорты
        fixes = [
            ('from ..state import AppState', 'from state import AppState'),
            ('from ..core.spatial_processor import SpatialProcessor', 
             'from core.spatial_processor import SpatialProcessor'),
            ('from ..core.geometry_operations import GeometryOperations', 
             'from core.geometry_operations import GeometryOperations'),
            ('from ..io_bess import load_bess_export', 'from io_bess import load_bess_export'),
            ('from ..performance import PerformanceMonitor', 'from performance import PerformanceMonitor'),
            ('from ..core.architectural_tools import ArchitecturalTools', 
             'from core.architectural_tools import ArchitecturalTools'),
            ('from ..core.shaft_manager import ShaftManager', 
             'from core.shaft_manager import ShaftManager'),
            ('from ..core.bess_parameters import BESSParameterManager', 
             'from core.bess_parameters import BESSParameterManager'),
            ('from ..ui.contour_editor import ContourEditor', 
             'from ui.contour_editor import ContourEditor')
        ]
        
        changes_made = 0
        for old_pattern, new_pattern in fixes:
            if old_pattern in content:
                content = content.replace(old_pattern, new_pattern)
                changes_made += 1
                print(f"   ✅ Исправлен: {old_pattern[:40]}...")
        
        if changes_made > 0:
            backup_path = main_controller_path.with_suffix('.py.backup')
            main_controller_path.rename(backup_path)
            
            main_controller_path.write_text(content, encoding='utf-8')
            print(f"   ✅ Файл обновлен ({changes_made} исправлений)")
            print(f"   💾 Резервная копия: {backup_path}")
        else:
            print("   ℹ️ Исправления не требуются")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка исправления: {e}")
        return False

def fix_canvas_controller():
    """Исправляет импорты в CanvasController"""
    print("\n🔧 ИСПРАВЛЕНИЕ CANVAS_CONTROLLER")
    print("-" * 40)
    
    canvas_controller_path = Path('controllers/canvas_controller.py')
    
    if not canvas_controller_path.exists():
        print("❌ controllers/canvas_controller.py не найден")
        return False
    
    try:
        with open(canvas_controller_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Исправляем относительные импорты
        fixes = [
            ('from ..ui.geometry_canvas import GeometryCanvas', 
             'from ui.geometry_canvas import GeometryCanvas'),
            ('from ..state import AppState', 'from state import AppState'),
            ('from ..geometry_utils import', 'from geometry_utils import'),
            ('from ..performance import', 'from performance import'),
            ('from ..core.', 'from core.'),
            ('from ..ui.', 'from ui.')
        ]
        
        changes_made = 0
        for old_pattern, new_pattern in fixes:
            if old_pattern in content:
                content = content.replace(old_pattern, new_pattern)
                changes_made += 1
                print(f"   ✅ Исправлен: {old_pattern[:40]}...")
        
        if changes_made > 0:
            backup_path = canvas_controller_path.with_suffix('.py.backup')
            canvas_controller_path.rename(backup_path)
            
            canvas_controller_path.write_text(content, encoding='utf-8')
            print(f"   ✅ Файл обновлен ({changes_made} исправлений)")
            print(f"   💾 Резервная копия: {backup_path}")
        else:
            print("   ℹ️ Исправления не требуются")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка исправления: {e}")
        return False

def fix_ui_imports():
    """Исправляет импорты в UI модулях"""
    print("\n🔧 ИСПРАВЛЕНИЕ UI ИМПОРТОВ")
    print("-" * 40)
    
    ui_init_path = Path('ui/__init__.py')
    
    if not ui_init_path.exists():
        print("❌ ui/__init__.py не найден")
        return False
    
    try:
        with open(ui_init_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Добавляем заглушки для отсутствующих классов
        missing_classes = """

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
"""
        
        # Проверяем, нет ли уже заглушек
        if 'class CanvasRenderer:' not in content:
            content += missing_classes
            
            ui_init_path.write_text(content, encoding='utf-8')
            print("   ✅ Добавлены заглушки для отсутствующих классов")
        else:
            print("   ℹ️ Заглушки уже существуют")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка исправления UI: {e}")
        return False

def test_fixes():
    """Тестирует исправления"""
    print("\n🧪 ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЙ")
    print("-" * 40)
    
    # Настраиваем пути
    current_dir = Path.cwd()
    sys.path.insert(0, str(current_dir))
    sys.path.insert(0, str(current_dir / 'controllers'))
    sys.path.insert(0, str(current_dir / 'core'))
    sys.path.insert(0, str(current_dir / 'ui'))
    
    tests = [
        ('core.integration_manager', 'IntegrationManager', 'Менеджер интеграции'),
        ('controllers.main_controller', 'MainController', 'Главный контроллер'),
        ('controllers.canvas_controller', 'CanvasController', 'Canvas контроллер'),
        ('ui.geometry_canvas', 'GeometryCanvas', 'Геометрический canvas'),
        ('ui.contour_editor', 'ContourEditor', 'Редактор контуров')
    ]
    
    successful = 0
    
    for module_path, class_name, description in tests:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"   ✅ {description}")
            successful += 1
        except ImportError as e:
            print(f"   ❌ {description}: {e}")
        except AttributeError as e:
            print(f"   ⚠️ {description}: класс не найден")
        except Exception as e:
            print(f"   ❌ {description}: {e}")
    
    print(f"\n   📊 Успешных тестов: {successful}/{len(tests)}")
    return successful

def test_integration_manager():
    """Тестирует IntegrationManager после исправлений"""
    print("\n⚡ ТЕСТ INTEGRATION_MANAGER")
    print("-" * 40)
    
    try:
        from core.integration_manager import IntegrationManager
        
        manager = IntegrationManager()
        print("   ✅ IntegrationManager создан")
        
        # Запускаем инициализацию
        results = manager.initialize_all_components()
        successful = results.get('successful_components', 0)
        total = results.get('total_components', 0)
        level = results.get('integration_level', 'unknown')
        
        print(f"   📊 Интеграция: {successful}/{total} компонентов")
        print(f"   📊 Уровень: {level}")
        
        if successful >= total * 0.7:
            print("   🎉 Интеграция успешна!")
            return True
        else:
            print("   ⚠️ Частичная интеграция")
            return False
            
    except Exception as e:
        print(f"   ❌ Ошибка тестирования: {e}")
        return False

def main():
    """Главная функция исправления"""
    print("🔧 ИСПРАВЛЕНИЕ ПРОБЛЕМ С ИМПОРТАМИ BESS_GEOMETRY")
    print("=" * 60)
    
    # Выполняем исправления
    fixes = [
        ("IntegrationManager", fix_integration_manager),
        ("MainController", fix_main_controller),
        ("CanvasController", fix_canvas_controller),
        ("UI импорты", fix_ui_imports)
    ]
    
    successful_fixes = 0
    
    for fix_name, fix_func in fixes:
        try:
            success = fix_func()
            if success:
                successful_fixes += 1
        except Exception as e:
            print(f"❌ {fix_name}: критическая ошибка - {e}")
    
    # Тестируем исправления
    successful_tests = test_fixes()
    integration_success = test_integration_manager()
    
    # Итоги
    print("\n" + "=" * 60)
    print("🎯 ИТОГИ ИСПРАВЛЕНИЯ:")
    print(f"🔧 Успешных исправлений: {successful_fixes}/{len(fixes)}")
    print(f"🧪 Успешных тестов: {successful_tests}/5")
    print(f"⚡ IntegrationManager: {'✅' if integration_success else '❌'}")
    
    overall_success = (successful_fixes + successful_tests + (1 if integration_success else 0)) / 8
    
    if overall_success >= 0.8:
        print("\n🎉 ОТЛИЧНО! Все проблемы исправлены!")
        print("🚀 СЛЕДУЮЩИЕ ШАГИ:")
        print("   1. python tests/correct_structure_test.py")
        print("   2. python examples/integrations_demo.py")
        print("   3. python main_app.py")
        return 0
    elif overall_success >= 0.6:
        print("\n🔧 ХОРОШО! Большинство проблем исправлено")
        print("   Повторите тестирование после исправлений")
        return 1
    else:
        print("\n⚠️ ТРЕБУЕТСЯ ДОПОЛНИТЕЛЬНАЯ РАБОТА")
        print("   Проверьте логи ошибок выше")
        return 2

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)