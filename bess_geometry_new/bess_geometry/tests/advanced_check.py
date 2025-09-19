#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Продвинутая диагностика BESS_Geometry с исправлением путей
Находит все файлы независимо от структуры и настраивает импорты
"""

import sys
import os
from pathlib import Path

def scan_directory_structure():
    """Сканирование полной структуры директории"""
    print("🔍 СКАНИРОВАНИЕ ДИРЕКТОРИЙ")
    print("-" * 50)
    
    current_dir = Path.cwd()
    print(f"Текущая директория: {current_dir}")
    
    # Ищем все Python файлы
    python_files = {}
    for pattern in ['*.py', '**/*.py']:
        for file_path in current_dir.glob(pattern):
            relative_path = file_path.relative_to(current_dir)
            python_files[str(relative_path)] = file_path
    
    print(f"\nНайдено {len(python_files)} Python файлов:")
    for rel_path, full_path in sorted(python_files.items()):
        size = full_path.stat().st_size if full_path.exists() else 0
        print(f"   📄 {rel_path} ({size} байт)")
    
    return python_files

def check_file_locations(python_files):
    """Проверка местоположения ключевых файлов"""
    print("\n📍 ПОИСК КЛЮЧЕВЫХ ФАЙЛОВ")
    print("-" * 50)
    
    key_files = {
        'main_controller.py': 'MainController',
        'geometry_operations.py': 'GeometryOperations', 
        'editing_modes.py': 'EditingModes',
        'core/architectural_tools.py': 'ArchitecturalTools',
        'core/shaft_manager.py': 'ShaftManager',
        'core/bess_parameters.py': 'BESSParameterManager',
        'core/integration_manager.py': 'IntegrationManager',
        'ui/contour_editor.py': 'ContourEditor'
    }
    
    found_files = {}
    
    for target_file, description in key_files.items():
        # Ищем файл в разных местах
        possible_locations = []
        
        # Прямой путь
        if target_file in python_files:
            possible_locations.append(target_file)
        
        # Поиск по имени файла в любой директории
        filename = Path(target_file).name
        for rel_path in python_files.keys():
            if Path(rel_path).name == filename:
                possible_locations.append(rel_path)
        
        if possible_locations:
            primary_location = possible_locations[0]
            found_files[target_file] = {
                'found': True,
                'location': primary_location,
                'all_locations': possible_locations,
                'description': description
            }
            print(f"   ✅ {description}: {primary_location}")
            if len(possible_locations) > 1:
                print(f"      ⚠️ Также найден в: {', '.join(possible_locations[1:])}")
        else:
            found_files[target_file] = {
                'found': False,
                'description': description
            }
            print(f"   ❌ {description}: НЕ НАЙДЕН ({target_file})")
    
    return found_files

def check_init_files(python_files):
    """Проверка __init__.py файлов"""
    print("\n📦 ПРОВЕРКА __init__.py ФАЙЛОВ")
    print("-" * 50)
    
    init_files = [path for path in python_files.keys() if path.endswith('__init__.py')]
    
    for init_file in sorted(init_files):
        full_path = python_files[init_file]
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            size = len(content)
            lines = len(content.splitlines())
            
            # Проверяем, что файл не пустой
            if size == 0:
                print(f"   ⚠️ {init_file}: ПУСТОЙ файл")
            elif size < 50:
                print(f"   ⚠️ {init_file}: Очень маленький ({size} байт, {lines} строк)")
            else:
                print(f"   ✅ {init_file}: OK ({size} байт, {lines} строк)")
            
            # Проверяем наличие импортов
            if 'import' in content or 'from' in content:
                print(f"      📥 Содержит импорты")
            else:
                print(f"      ⚠️ Нет импортов")
                
        except Exception as e:
            print(f"   ❌ {init_file}: Ошибка чтения - {e}")

def fix_python_path(found_files):
    """Исправление Python path для импортов"""
    print("\n🔧 НАСТРОЙКА PYTHON PATH")
    print("-" * 50)
    
    current_dir = Path.cwd()
    
    # Добавляем текущую директорию в sys.path если её нет
    current_str = str(current_dir)
    if current_str not in sys.path:
        sys.path.insert(0, current_str)
        print(f"   ✅ Добавлен в sys.path: {current_str}")
    else:
        print(f"   ✅ Уже в sys.path: {current_str}")
    
    # Проверяем, есть ли поддиректории с __init__.py
    subdirs_with_init = []
    for init_file in Path(current_dir).glob('**/__init__.py'):
        subdir = init_file.parent
        rel_path = subdir.relative_to(current_dir)
        if str(rel_path) != '.':  # Не корневая директория
            subdirs_with_init.append(str(rel_path))
    
    print(f"   📂 Найдены пакеты: {', '.join(subdirs_with_init) if subdirs_with_init else 'нет'}")
    
    # Показываем текущий sys.path
    print(f"   📍 Текущий sys.path:")
    for i, path in enumerate(sys.path[:5]):  # Показываем первые 5
        print(f"      {i+1}. {path}")
    if len(sys.path) > 5:
        print(f"      ... и еще {len(sys.path) - 5} путей")

def test_imports_with_fixes(found_files):
    """Тестирование импортов с различными подходами"""
    print("\n🧪 ТЕСТИРОВАНИЕ ИМПОРТОВ")
    print("-" * 50)
    
    # Список модулей для тестирования
    modules_to_test = [
        ('state', 'AppState'),
        ('geometry_utils', 'centroid_xy'),
        ('core', None),
        ('ui', None),
        ('main_controller', 'MainController'),
        ('geometry_operations', 'GeometryOperations')
    ]
    
    successful_imports = 0
    
    for module_name, expected_class in modules_to_test:
        print(f"\n   🔍 Тестируем: {module_name}")
        
        # Метод 1: Прямой импорт
        try:
            module = __import__(module_name)
            print(f"      ✅ Прямой импорт успешен")
            
            if expected_class:
                if hasattr(module, expected_class):
                    print(f"      ✅ Класс {expected_class} найден")
                else:
                    print(f"      ⚠️ Класс {expected_class} не найден")
                    # Показываем что есть в модуле
                    attrs = [attr for attr in dir(module) if not attr.startswith('_')]
                    if attrs:
                        print(f"      📋 Доступно: {', '.join(attrs[:5])}")
            
            successful_imports += 1
            
        except ImportError as e:
            print(f"      ❌ Прямой импорт: {e}")
            
            # Метод 2: Поиск файла и прямая загрузка
            if module_name in ['main_controller', 'geometry_operations', 'editing_modes']:
                module_file = f"{module_name}.py"
                if module_file in [Path(p).name for p in found_files.keys()]:
                    try:
                        # Найдем полный путь к файлу
                        for file_path, file_info in found_files.items():
                            if file_info.get('found') and Path(file_path).name == module_file:
                                print(f"      🔄 Попытка загрузить из: {file_path}")
                                
                                # Используем spec для загрузки
                                import importlib.util
                                current_dir = Path.cwd()
                                full_path = current_dir / file_path
                                
                                spec = importlib.util.spec_from_file_location(module_name, full_path)
                                if spec and spec.loader:
                                    module = importlib.util.module_from_spec(spec)
                                    sys.modules[module_name] = module
                                    spec.loader.exec_module(module)
                                    print(f"      ✅ Загружен через importlib")
                                    successful_imports += 1
                                    break
                                break
                    except Exception as e2:
                        print(f"      ❌ importlib загрузка: {e2}")
    
    print(f"\n   📊 Успешных импортов: {successful_imports}/{len(modules_to_test)}")
    return successful_imports

def create_missing_files(found_files):
    """Создание недостающих файлов"""
    print("\n🔨 СОЗДАНИЕ НЕДОСТАЮЩИХ ФАЙЛОВ")
    print("-" * 50)
    
    missing_files = [file for file, info in found_files.items() if not info['found']]
    
    if not missing_files:
        print("   🎉 Все ключевые файлы найдены!")
        return
    
    print(f"   📝 Недостающих файлов: {len(missing_files)}")
    
    for missing_file in missing_files:
        print(f"   ❌ {missing_file}")
    
    # Предлагаем создать заглушки
    response = input("\n❓ Создать заглушки для недостающих файлов? (y/n): ")
    if response.lower() in ['y', 'yes', 'да', 'д']:
        create_stubs(missing_files)

def create_stubs(missing_files):
    """Создание заглушек для недостающих файлов"""
    print("\n🔧 СОЗДАНИЕ ЗАГЛУШЕК")
    print("-" * 50)
    
    stubs = {
        'main_controller.py': '''# -*- coding: utf-8 -*-
"""MainController - заглушка"""

class MainController:
    def __init__(self, root_window=None):
        print("MainController: заглушка инициализирована")
        self.root = root_window
        
    def create_void_room(self, *args, **kwargs):
        return {'success': False, 'error': 'Заглушка - не реализовано'}
        
    def create_second_light(self, *args, **kwargs):
        return {'success': False, 'error': 'Заглушка - не реализовано'}
''',
        
        'geometry_operations.py': '''# -*- coding: utf-8 -*-
"""GeometryOperations - заглушка"""

class GeometryOperations:
    def __init__(self, state=None):
        print("GeometryOperations: заглушка инициализирована")
        self.state = state
''',
        
        'editing_modes.py': '''# -*- coding: utf-8 -*-
"""EditingModes - заглушка"""

class EditingModeManager:
    def __init__(self, controller=None):
        print("EditingModeManager: заглушка инициализирована")
        self.controller = controller
''',
        
        'examples/integration_demo.py': '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration Demo - заглушка"""

def main():
    print("🎬 Демонстрация интеграции - заглушка")
    print("Основные компоненты пока не реализованы")
    
if __name__ == '__main__':
    main()
'''
    }
    
    for missing_file in missing_files:
        if missing_file in stubs:
            try:
                # Создаем директорию если нужно
                file_path = Path(missing_file)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Записываем заглушку
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(stubs[missing_file])
                
                print(f"   ✅ Создан: {missing_file}")
                
            except Exception as e:
                print(f"   ❌ Ошибка создания {missing_file}: {e}")

def generate_final_recommendations(python_files, found_files, successful_imports):
    """Финальные рекомендации"""
    print("\n🎯 ФИНАЛЬНЫЕ РЕКОМЕНДАЦИИ")
    print("=" * 50)
    
    total_key_files = len(found_files)
    found_key_files = sum(1 for info in found_files.values() if info['found'])
    
    print(f"📊 Статистика:")
    print(f"   • Всего Python файлов: {len(python_files)}")
    print(f"   • Ключевых файлов найдено: {found_key_files}/{total_key_files}")
    print(f"   • Успешных импортов: {successful_imports}")
    
    if found_key_files >= total_key_files * 0.8 and successful_imports >= 3:
        print("\n🎉 ОТЛИЧНО! Система готова к работе:")
        print("   1. python tests/test_integration.py")
        print("   2. python examples/integration_demo.py")
        print("   3. python main.py")
        return "ready"
    
    elif found_key_files >= total_key_files * 0.6:
        print("\n🔧 ХОРОШО! Нужны небольшие доработки:")
        print("   1. Создайте недостающие файлы")
        print("   2. Исправьте импорты в __init__.py")
        print("   3. Запустите тесты: python tests/test_integration.py")
        return "partial"
    
    else:
        print("\n⚠️ ТРЕБУЕТСЯ РАБОТА:")
        print("   1. Создайте все недостающие файлы")
        print("   2. Проверьте структуру пакетов")
        print("   3. Повторите диагностику")
        return "needs_work"

def main():
    """Главная функция продвинутой диагностики"""
    print("🔍 ПРОДВИНУТАЯ ДИАГНОСТИКА BESS_GEOMETRY")
    print("=" * 60)
    print(f"📁 Рабочая директория: {Path.cwd()}")
    print(f"🐍 Python: {sys.version}")
    print(f"📍 sys.path содержит {len(sys.path)} путей")
    
    # Выполняем диагностику
    python_files = scan_directory_structure()
    found_files = check_file_locations(python_files)
    check_init_files(python_files)
    fix_python_path(found_files)
    successful_imports = test_imports_with_fixes(found_files)
    
    # Создаем недостающие файлы если нужно
    create_missing_files(found_files)
    
    # Финальные рекомендации
    status = generate_final_recommendations(python_files, found_files, successful_imports)
    
    return 0 if status == "ready" else 1 if status == "partial" else 2

if __name__ == '__main__':
    try:
        exit_code = main()
        print(f"\n{'='*60}")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n❌ Диагностика прервана пользователем")
        sys.exit(3)
    except Exception as e:
        print(f"\n\n💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(4)