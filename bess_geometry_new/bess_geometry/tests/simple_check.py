#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Упрощенная диагностика BESS_Geometry
Быстро проверяет что есть, что отсутствует
"""

import sys
import os
from pathlib import Path

def check_files():
    """Проверка наличия файлов"""
    print("📁 ПРОВЕРКА СТРУКТУРЫ ПРОЕКТА")
    print("-" * 40)
    
    # Файлы которые должны существовать
    files_to_check = {
        "Основные файлы": [
            "__init__.py",
            "main_controller.py", 
            "geometry_operations.py",
            "editing_modes.py",
            "state.py",
            "geometry_utils.py"
        ],
        "Core модули": [
            "core/__init__.py",
            "core/spatial_processor.py",
            "core/integration_manager.py",
            "core/architectural_tools.py",
            "core/shaft_manager.py", 
            "core/bess_parameters.py"
        ],
        "UI модули": [
            "ui/__init__.py",
            "ui/geometry_canvas.py",
            "ui/contour_editor.py"
        ],
        "Тесты и примеры": [
            "tests/test_integration.py",
            "examples/integration_demo.py"
        ]
    }
    
    all_present = True
    missing_files = []
    
    for category, files in files_to_check.items():
        print(f"\n{category}:")
        category_ok = True
        
        for file_path in files:
            full_path = Path(file_path)
            if full_path.exists():
                print(f"   ✅ {file_path}")
            else:
                print(f"   ❌ {file_path} - ОТСУТСТВУЕТ!")
                missing_files.append(file_path)
                category_ok = False
                all_present = False
        
        if category_ok:
            print(f"   🎉 {category} - все файлы на месте")
    
    return all_present, missing_files

def check_imports():
    """Проверка базовых импортов"""
    print("\n📦 ПРОВЕРКА ИМПОРТОВ")
    print("-" * 40)
    
    # Проверяем стандартные библиотеки
    try:
        import tkinter
        print("✅ tkinter (GUI)")
    except ImportError:
        print("❌ tkinter - установите python3-tk")
        return False
    
    # Проверяем что можем импортировать наши модули
    imports_to_check = [
        ("core", "Core пакет"),
        ("ui", "UI пакет"),
        ("main_controller", "MainController"),
        ("geometry_operations", "GeometryOperations")
    ]
    
    success_count = 0
    
    for module_name, description in imports_to_check:
        try:
            __import__(module_name)
            print(f"✅ {description}")
            success_count += 1
        except ImportError as e:
            print(f"❌ {description}: {e}")
    
    return success_count >= len(imports_to_check) * 0.75  # 75% успеха

def check_new_components():
    """Проверка новых компонентов этапа 3"""
    print("\n🔧 ПРОВЕРКА НОВЫХ КОМПОНЕНТОВ ЭТАПА 3")
    print("-" * 40)
    
    components = [
        ("core.architectural_tools", "ArchitecturalTools", "Создание VOID и второго света"),
        ("core.shaft_manager", "ShaftManager", "Управление шахтами"),
        ("core.bess_parameters", "BESSParameterManager", "Параметры BESS"),
        ("core.integration_manager", "IntegrationManager", "Координатор интеграции"),
        ("ui.contour_editor", "ContourEditor", "Редактирование контуров")
    ]
    
    available_count = 0
    
    for module_path, class_name, description in components:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"✅ {description} ({class_name})")
            available_count += 1
        except ImportError:
            print(f"❌ {description} - модуль {module_path} не найден")
        except AttributeError:
            print(f"⚠️ {description} - класс {class_name} не найден в модуле")
        except Exception as e:
            print(f"❌ {description} - ошибка: {e}")
    
    print(f"\nДоступно: {available_count}/{len(components)} новых компонентов")
    return available_count, len(components)

def generate_recommendations(structure_ok, imports_ok, components_available, total_components):
    """Генерация рекомендаций"""
    print("\n🎯 РЕКОМЕНДАЦИИ")
    print("-" * 40)
    
    if not structure_ok:
        print("🚨 КРИТИЧНО: Отсутствуют ключевые файлы!")
        print("   • Убедитесь, что все файлы из роадмапа созданы")
        print("   • Проверьте правильность структуры директорий")
        return "critical"
    
    if not imports_ok:
        print("🔧 ПРОБЛЕМА: Ошибки импорта базовых модулей")
        print("   • Проверьте синтаксис в Python файлах")
        print("   • Установите недостающие зависимости")
        return "imports"
    
    component_rate = components_available / total_components
    
    if component_rate >= 0.8:
        print("🎉 ОТЛИЧНО: Система готова к работе!")
        print("   • Запустите: python tests/test_integration.py")
        print("   • Затем: python examples/integration_demo.py")
        print("   • И наконец: python main.py")
        return "ready"
    elif component_rate >= 0.6:
        print("🔧 ХОРОШО: Частичная готовность")
        print("   • Большинство компонентов доступно")
        print("   • Исправьте недостающие компоненты")
        print("   • Запустите тесты для диагностики")
        return "partial"
    else:
        print("⚠️ ТРЕБУЕТ РАБОТЫ: Много компонентов отсутствует")
        print("   • Создайте недостающие модули")
        print("   • Следуйте роадмапу интеграции")
        print("   • Проверьте каждый компонент отдельно")
        return "needs_work"

def main():
    """Главная функция"""
    print("🔍 БЫСТРАЯ ДИАГНОСТИКА BESS_GEOMETRY")
    print("=" * 50)
    print(f"📁 Директория: {Path.cwd()}")
    print(f"🐍 Python: {sys.version}")
    
    # Проверки
    structure_ok, missing_files = check_files()
    imports_ok = check_imports()
    components_available, total_components = check_new_components()
    
    # Рекомендации
    status = generate_recommendations(structure_ok, imports_ok, components_available, total_components)
    
    # Итог
    print("\n" + "=" * 50)
    if status == "ready":
        print("🎉 СИСТЕМА ГОТОВА! Можете приступать к тестированию.")
        return 0
    elif status == "partial":
        print("🔧 СИСТЕМА ЧАСТИЧНО ГОТОВА. Нужны небольшие доработки.")
        return 1
    else:
        print("🚨 СИСТЕМА ТРЕБУЕТ НАСТРОЙКИ.")
        if missing_files:
            print("Отсутствующие файлы:")
            for file in missing_files[:5]:  # Показываем первые 5
                print(f"   • {file}")
            if len(missing_files) > 5:
                print(f"   ... и еще {len(missing_files) - 5} файлов")
        return 2

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)