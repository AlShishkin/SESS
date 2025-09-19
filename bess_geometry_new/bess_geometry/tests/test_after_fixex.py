#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Быстрый тест после исправления проблем с импортами
"""

import sys
from pathlib import Path

# Настройка путей
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / 'controllers'))
sys.path.insert(0, str(current_dir / 'core'))
sys.path.insert(0, str(current_dir / 'ui'))

def test_critical_components():
    """Тест критических компонентов"""
    print("🧪 ТЕСТ КРИТИЧЕСКИХ КОМПОНЕНТОВ")
    print("-" * 40)
    
    # Тест IntegrationManager
    try:
        from core.integration_manager import IntegrationManager
        manager = IntegrationManager()
        
        # Запускаем инициализацию
        results = manager.initialize_all_components()
        successful = results.get('successful_components', 0)
        total = results.get('total_components', 0)
        
        print(f"✅ IntegrationManager: {successful}/{total} компонентов")
        
        if successful >= 4:  # Ожидаем хотя бы 4 из 6 компонентов
            print("   🎉 Интеграция успешна!")
            integration_success = True
        else:
            print("   ⚠️ Частичная интеграция")
            integration_success = False
            
    except Exception as e:
        print(f"❌ IntegrationManager: {e}")
        integration_success = False
    
    # Тест MainController
    try:
        from controllers.main_controller import MainController
        print("✅ MainController импортирован из controllers/")
        
        # Проверяем методы интеграции
        methods = ['create_void_room', 'create_second_light', 'import_shafts']
        found = sum(1 for method in methods if hasattr(MainController, method))
        print(f"   🔧 Методы интеграции: {found}/{len(methods)}")
        main_controller_success = True
        
    except Exception as e:
        print(f"❌ MainController: {e}")
        main_controller_success = False
    
    # Тест CanvasController
    try:
        from controllers.canvas_controller import CanvasController
        print("✅ CanvasController импортирован")
        canvas_controller_success = True
    except Exception as e:
        print(f"❌ CanvasController: {e}")
        canvas_controller_success = False
    
    return integration_success, main_controller_success, canvas_controller_success

def test_ui_components():
    """Тест UI компонентов"""
    print("\n🎨 ТЕСТ UI КОМПОНЕНТОВ")
    print("-" * 40)
    
    try:
        from ui.geometry_canvas import GeometryCanvas, CanvasRenderer
        print("✅ GeometryCanvas и CanvasRenderer")
        geometry_canvas_success = True
    except Exception as e:
        print(f"❌ GeometryCanvas: {e}")
        geometry_canvas_success = False
    
    try:
        from ui.contour_editor import ContourEditor, VertexManipulator
        print("✅ ContourEditor и VertexManipulator")
        contour_editor_success = True
    except Exception as e:
        print(f"❌ ContourEditor: {e}")
        contour_editor_success = False
    
    try:
        import ui
        status = ui.get_ui_integration_status()
        level = status.get('integration_level', 'unknown')
        print(f"✅ UI статус: {level}")
        ui_status_success = True
    except Exception as e:
        print(f"❌ UI статус: {e}")
        ui_status_success = False
    
    return geometry_canvas_success, contour_editor_success, ui_status_success

def test_core_full():
    """Полный тест core компонентов"""
    print("\n🔧 ПОЛНЫЙ ТЕСТ CORE")
    print("-" * 40)
    
    try:
        import core
        status = core.get_integration_status()
        level = status.get('integration_level', 'unknown')
        ready = status.get('ready_for_stage3', False)
        
        print(f"✅ Core статус: {level}")
        print(f"✅ Готовность к этапу 3: {ready}")
        
        return level == 'full' and ready
    except Exception as e:
        print(f"❌ Core статус: {e}")
        return False

def test_examples():
    """Тест примеров"""
    print("\n🎬 ТЕСТ ПРИМЕРОВ")
    print("-" * 40)
    
    try:
        from examples.integrations_demo import main as demo_main
        print("✅ integrations_demo готов к запуску")
        return True
    except Exception as e:
        print(f"❌ integrations_demo: {e}")
        return False

def main():
    """Главная функция теста"""
    print("🧪 ТЕСТ ПОСЛЕ ИСПРАВЛЕНИЙ")
    print("=" * 50)
    
    # Запускаем все тесты
    integration_ok, main_ctrl_ok, canvas_ctrl_ok = test_critical_components()
    geometry_canvas_ok, contour_editor_ok, ui_status_ok = test_ui_components()
    core_ok = test_core_full()
    examples_ok = test_examples()
    
    # Подсчитываем результаты
    results = [
        integration_ok, main_ctrl_ok, canvas_ctrl_ok,
        geometry_canvas_ok, contour_editor_ok, ui_status_ok,
        core_ok, examples_ok
    ]
    
    successful = sum(results)
    total = len(results)
    success_rate = (successful / total) * 100
    
    print("\n" + "=" * 50)
    print("🎯 ИТОГИ ТЕСТИРОВАНИЯ:")
    print(f"✅ Успешных тестов: {successful}/{total} ({success_rate:.0f}%)")
    
    # Детализация
    test_names = [
        "IntegrationManager", "MainController", "CanvasController",
        "GeometryCanvas", "ContourEditor", "UI статус",
        "Core готовность", "Примеры"
    ]
    
    print("\nДетализация:")
    for i, (name, result) in enumerate(zip(test_names, results)):
        icon = "✅" if result else "❌"
        print(f"   {icon} {name}")
    
    # Рекомендации
    if success_rate >= 90:
        print("\n🎉 ОТЛИЧНО! Система полностью готова!")
        print("🚀 ЗАПУСКАЙТЕ:")
        print("   1. python examples/integrations_demo.py")
        print("   2. python main_app.py")
        return 0
    elif success_rate >= 75:
        print("\n🔧 ХОРОШО! Система в основном готова")
        print("🚀 МОЖЕТЕ ЗАПУСКАТЬ:")
        print("   1. python examples/integrations_demo.py")
        print("   2. Исправьте оставшиеся проблемы")
        return 1
    elif success_rate >= 60:
        print("\n⚠️ ЧАСТИЧНО ГОТОВО")
        print("🔧 НУЖНО:")
        print("   1. Исправить оставшиеся ошибки импорта")
        print("   2. Повторить тестирование")
        return 2
    else:
        print("\n🚨 ТРЕБУЕТ РАБОТЫ")
        print("🔧 ДЕЙСТВИЯ:")
        print("   1. Проверьте ошибки выше")
        print("   2. Запустите: python fix_import_issues.py")
        return 3

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(4)