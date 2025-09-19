#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Исправленный тест для реальной структуры BESS_Geometry

Учитывает реальное расположение файлов:
- main_controller.py в controllers/
- geometry_operations.py в core/
- integration_demo.py как integrations_demo.py в examples/
"""

import sys
import os
from pathlib import Path

# Добавляем текущую директорию в путь
current_dir = Path(__file__).parent.parent  # Поднимаемся из tests/ в корень
sys.path.insert(0, str(current_dir))

def fix_python_path():
    """Исправляет Python path для корректных импортов"""
    print("🔧 НАСТРОЙКА PYTHON PATH")
    print("-" * 40)
    
    paths_to_add = [
        str(current_dir),  # Корень проекта
        str(current_dir / 'controllers'),  # Папка controllers
        str(current_dir / 'core'),  # Папка core  
        str(current_dir / 'ui'),  # Папка ui
    ]
    
    for path in paths_to_add:
        if path not in sys.path:
            sys.path.insert(0, path)
            print(f"✅ Добавлен: {path}")
        else:
            print(f"✅ Уже есть: {path}")

def test_actual_structure():
    """Тестирует импорты с учетом реальной структуры"""
    print("\n🧪 ТЕСТИРОВАНИЕ РЕАЛЬНОЙ СТРУКТУРЫ")
    print("-" * 40)
    
    tests = [
        # (модуль, ожидаемый класс/функция, описание)
        ('state', 'AppState', 'Состояние приложения'),
        ('geometry_utils', 'centroid_xy', 'Геометрические утилиты'),
        ('performance', 'PerformanceMonitor', 'Мониторинг производительности'),
        ('io_bess', 'load_bess_export', 'Загрузка BESS файлов'),
    ]
    
    successful = 0
    
    for module_name, expected_item, description in tests:
        try:
            module = __import__(module_name)
            
            if expected_item and hasattr(module, expected_item):
                print(f"✅ {description} - {expected_item} найден")
            elif expected_item:
                print(f"⚠️ {description} - {expected_item} не найден")
                # Покажем что есть
                available = [item for item in dir(module) if not item.startswith('_')]
                if available:
                    print(f"   📦 Доступно: {', '.join(available[:3])}")
            else:
                print(f"✅ {description} - модуль импортирован")
            
            successful += 1
            
        except ImportError as e:
            print(f"❌ {description}: {e}")
        except Exception as e:
            print(f"⚠️ {description}: ошибка - {e}")
    
    return successful

def test_controllers():
    """Тестирует контроллеры"""
    print("\n🎮 ТЕСТИРОВАНИЕ КОНТРОЛЛЕРОВ")
    print("-" * 40)
    
    controller_tests = [
        ('controllers', None, 'Controllers пакет'),
        ('controllers.main_controller', 'MainController', 'Главный контроллер'),
        ('controllers.canvas_controller', 'CanvasController', 'Canvas контроллер'),
        ('controllers.interaction_controller', 'InteractionController', 'Контроллер взаимодействий'),
    ]
    
    successful = 0
    
    for module_path, expected_class, description in controller_tests:
        try:
            if '.' in module_path:
                module = __import__(module_path, fromlist=[expected_class or 'dummy'])
            else:
                module = __import__(module_path)
            
            if expected_class:
                if hasattr(module, expected_class):
                    cls = getattr(module, expected_class)
                    print(f"✅ {description} - класс {expected_class} найден")
                    
                    # Проверим методы интеграции для MainController
                    if expected_class == 'MainController':
                        integration_methods = [
                            'create_void_room', 'create_second_light', 'import_shafts',
                            'start_contour_editing', 'update_element_parameters'
                        ]
                        found_methods = sum(1 for method in integration_methods if hasattr(cls, method))
                        print(f"   🔧 Методы интеграции: {found_methods}/{len(integration_methods)}")
                else:
                    print(f"⚠️ {description} - класс {expected_class} не найден в модуле")
                    # Покажем что есть
                    available = [item for item in dir(module) if not item.startswith('_') and not item.islower()]
                    if available:
                        print(f"   📦 Классы: {', '.join(available[:3])}")
            else:
                print(f"✅ {description} - пакет импортирован")
            
            successful += 1
            
        except ImportError as e:
            print(f"❌ {description}: {e}")
        except Exception as e:
            print(f"⚠️ {description}: ошибка - {e}")
    
    return successful

def test_core_components():
    """Тестирует core компоненты"""
    print("\n🔧 ТЕСТИРОВАНИЕ CORE КОМПОНЕНТОВ")
    print("-" * 40)
    
    core_tests = [
        ('core', None, 'Core пакет'),
        ('core.spatial_processor', 'SpatialProcessor', 'Пространственный процессор'),
        ('core.geometry_operations', 'GeometryOperations', 'Геометрические операции'),
        ('core.architectural_tools', 'ArchitecturalTools', 'Архитектурные инструменты'),
        ('core.shaft_manager', 'ShaftManager', 'Менеджер шахт'),
        ('core.bess_parameters', 'BESSParameterManager', 'Параметры BESS'),
        ('core.integration_manager', 'IntegrationManager', 'Менеджер интеграции'),
        ('core.editing_modes', 'EditingModeManager', 'Режимы редактирования'),
    ]
    
    successful = 0
    
    for module_path, expected_class, description in core_tests:
        try:
            if '.' in module_path:
                module = __import__(module_path, fromlist=[expected_class or 'dummy'])
            else:
                module = __import__(module_path)
            
            if expected_class:
                if hasattr(module, expected_class):
                    cls = getattr(module, expected_class)
                    print(f"✅ {description}")
                    
                    # Пробуем создать экземпляр для некоторых классов
                    try:
                        if expected_class in ['ShaftManager', 'BESSParameterManager', 'IntegrationManager']:
                            instance = cls()
                            print(f"   🎉 Экземпляр создан")
                        elif expected_class == 'ArchitecturalTools':
                            if hasattr(cls, 'add_void') and hasattr(cls, 'add_second_light'):
                                print(f"   🎉 Методы add_void и add_second_light найдены")
                        elif expected_class == 'GeometryOperations':
                            # Создаем с пустым состоянием
                            instance = cls()
                            print(f"   🎉 Экземпляр создан")
                    except Exception as e:
                        print(f"   ⚠️ Экземпляр не создан: {e}")
                else:
                    print(f"⚠️ {description} - класс {expected_class} не найден")
                    # Покажем что есть
                    available = [item for item in dir(module) if not item.startswith('_') and item[0].isupper()]
                    if available:
                        print(f"   📦 Классы: {', '.join(available[:3])}")
            else:
                print(f"✅ {description} - пакет импортирован")
                
                # Для core пакета покажем что доступно
                if module_path == 'core':
                    if hasattr(module, 'get_integration_status'):
                        try:
                            status = module.get_integration_status()
                            print(f"   📊 Статус интеграции: {status}")
                        except Exception as e:
                            print(f"   ⚠️ Ошибка получения статуса: {e}")
            
            successful += 1
            
        except ImportError as e:
            print(f"❌ {description}: {e}")
        except Exception as e:
            print(f"⚠️ {description}: ошибка - {e}")
    
    return successful

def test_ui_components():
    """Тестирует UI компоненты"""
    print("\n🎨 ТЕСТИРОВАНИЕ UI КОМПОНЕНТОВ")
    print("-" * 40)
    
    ui_tests = [
        ('ui', None, 'UI пакет'),
        ('ui.geometry_canvas', 'GeometryCanvas', 'Геометрический canvas'),
        ('ui.contour_editor', 'ContourEditor', 'Редактор контуров'),
    ]
    
    successful = 0
    
    for module_path, expected_class, description in ui_tests:
        try:
            if '.' in module_path:
                module = __import__(module_path, fromlist=[expected_class or 'dummy'])
            else:
                module = __import__(module_path)
            
            if expected_class:
                if hasattr(module, expected_class):
                    print(f"✅ {description}")
                    
                    # Для ContourEditor проверим дополнительные классы
                    if expected_class == 'ContourEditor':
                        additional_classes = ['EditingMode', 'ElementType', 'EditingState']
                        found_additional = sum(1 for cls_name in additional_classes if hasattr(module, cls_name))
                        print(f"   📦 Дополнительные классы: {found_additional}/{len(additional_classes)}")
                else:
                    print(f"⚠️ {description} - класс {expected_class} не найден")
                    available = [item for item in dir(module) if not item.startswith('_') and item[0].isupper()]
                    if available:
                        print(f"   📦 Классы: {', '.join(available[:3])}")
            else:
                print(f"✅ {description} - пакет импортирован")
                
                # Для UI пакета покажем статус
                if module_path == 'ui':
                    if hasattr(module, 'get_ui_integration_status'):
                        try:
                            status = module.get_ui_integration_status()
                            print(f"   📊 UI статус: {status}")
                        except Exception as e:
                            print(f"   ⚠️ Ошибка получения UI статуса: {e}")
            
            successful += 1
            
        except ImportError as e:
            print(f"❌ {description}: {e}")
        except Exception as e:
            print(f"⚠️ {description}: ошибка - {e}")
    
    return successful

def test_examples():
    """Тестирует примеры"""
    print("\n🎬 ТЕСТИРОВАНИЕ ПРИМЕРОВ")
    print("-" * 40)
    
    try:
        # Проверяем integrations_demo.py (не integration_demo.py)
        from examples.integrations_demo import main as demo_main
        print("✅ integrations_demo импортирован")
        print("   📝 Примечание: файл называется integrations_demo.py (с 's')")
        return 1
    except ImportError as e:
        print(f"❌ integrations_demo: {e}")
        
        # Проверим что есть в examples
        try:
            import examples
            available = [item for item in dir(examples) if not item.startswith('_')]
            if available:
                print(f"   📦 Доступно в examples: {', '.join(available)}")
        except:
            pass
        return 0

def run_integration_test():
    """Запускает интеграционный тест"""
    print("\n⚡ ИНТЕГРАЦИОННЫЙ ТЕСТ")
    print("-" * 40)
    
    try:
        # Тестируем создание IntegrationManager и его работу
        from core.integration_manager import IntegrationManager
        
        print("🔧 Создание IntegrationManager...")
        manager = IntegrationManager()
        print("✅ IntegrationManager создан")
        
        print("🔧 Запуск инициализации компонентов...")
        try:
            results = manager.initialize_all_components()
            successful = results.get('successful_components', 0)
            total = results.get('total_components', 0)
            level = results.get('integration_level', 'unknown')
            
            print(f"✅ Интеграция завершена: {successful}/{total} компонентов")
            print(f"📊 Уровень интеграции: {level}")
            
            if successful >= total * 0.7:
                print("🎉 Интеграция успешна!")
                return True
            else:
                print("⚠️ Частичная интеграция")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка инициализации: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка IntegrationManager: {e}")
        return False

def main():
    """Главная функция"""
    print("🔍 ТЕСТ РЕАЛЬНОЙ СТРУКТУРЫ BESS_GEOMETRY")
    print("=" * 60)
    print(f"📁 Корень проекта: {current_dir}")
    print(f"🐍 Python: {sys.version}")
    
    # Исправляем пути
    fix_python_path()
    
    # Запускаем тесты
    results = {}
    results['basic'] = test_actual_structure()
    results['controllers'] = test_controllers()
    results['core'] = test_core_components()
    results['ui'] = test_ui_components()
    results['examples'] = test_examples()
    
    # Интеграционный тест
    integration_success = run_integration_test()
    
    # Подсчитываем результаты
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ:")
    print("-" * 40)
    
    total_successful = sum(results.values())
    total_tests = len(results)
    
    print(f"✅ Базовые модули: {results['basic']}/4")
    print(f"🎮 Контроллеры: {results['controllers']}/4") 
    print(f"🔧 Core компоненты: {results['core']}/8")
    print(f"🎨 UI компоненты: {results['ui']}/3")
    print(f"🎬 Примеры: {results['examples']}/1")
    print(f"⚡ Интеграционный тест: {'✅' if integration_success else '❌'}")
    
    success_rate = (total_successful / 20) * 100  # Примерно 20 тестов всего
    
    print(f"\n🎯 ОБЩИЙ РЕЗУЛЬТАТ: {success_rate:.0f}%")
    
    if success_rate >= 70 and integration_success:
        print("🎉 ОТЛИЧНО! Система готова к работе!")
        print("\n🚀 СЛЕДУЮЩИЕ ШАГИ:")
        print("   1. python tests/test_integration.py")
        print("   2. python examples/integrations_demo.py")  # С 's'!
        print("   3. python main_app.py")
        return 0
    elif success_rate >= 50:
        print("🔧 ХОРОШО! Система частично готова")
        print("\n🔧 РЕКОМЕНДАЦИИ:")
        print("   1. Исправьте проблемные компоненты")
        print("   2. Запустите: python tests/test_integration.py")
        return 1
    else:
        print("⚠️ ТРЕБУЕТСЯ РАБОТА")
        print("\n🔧 РЕКОМЕНДАЦИИ:")
        print("   1. Проверьте отсутствующие компоненты")
        print("   2. Исправьте ошибки импорта")
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