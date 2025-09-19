# -*- coding: utf-8 -*-
"""
__main__.py - Точка входа BESS_Geometry с поддержкой модульной архитектуры

Этот обновленный модуль демонстрирует принципы "модульной архитектуры" и правильной
работы с Python пакетами. Система диагностики теперь понимает структуру проекта
с логическим разделением компонентов по функциональным областям.

Образовательная ценность: Код показывает, как правильно организовать большие
Python проекты с использованием пакетов и подмодулей, и как система импорта
работает с такой структурой.

Ключевые архитектурные принципы:
- Modular Organization: Логическое разделение компонентов по папкам
- Package-aware Imports: Понимание структуры пакетов при импорте
- Graceful Degradation: Работа даже при отсутствии некоторых компонентов
- Comprehensive Diagnostics: Детальная диагностика всех уровней системы
"""

import sys
import os
import traceback
from pathlib import Path
from datetime import datetime

# Добавляем текущую директорию в путь Python для корректного импорта модулей
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

def check_modular_structure():
    """
    Проверка модульной структуры проекта
    
    Эта функция демонстрирует принципы "architectural awareness" - система
    понимает свою собственную структуру и может диагностировать каждый
    компонент в контексте его архитектурной роли.
    
    Returns:
        tuple: (structure_valid: bool, structure_info: dict)
    """
    print("🏗️ Анализ архитектуры проекта...")
    
    structure_info = {
        'project_root': str(current_dir),
        'expected_modules': {},
        'optional_modules': {},
        'architecture_type': 'unknown',
        'issues': [],
        'recommendations': []
    }
    
    # Определяем ожидаемую структуру модульного проекта
    expected_structure = {
        'core': {
            'description': 'Базовые компоненты системы',
            'files': {
                '__init__.py': 'Инициализация core пакета',
                'file_manager.py': 'Менеджер файлов BESS',
                'spatial_processor.py': 'Пространственный процессор (опционально)',
            },
            'required': True
        },
        'ui': {
            'description': 'Компоненты пользовательского интерфейса', 
            'files': {
                '__init__.py': 'Инициализация UI пакета'
            },
            'required': False
        },
        'controllers': {
            'description': 'Контроллеры приложения',
            'files': {
                '__init__.py': 'Инициализация controllers пакета'
            },
            'required': False
        },
        'widgets': {
            'description': 'Пользовательские виджеты',
            'files': {
                '__init__.py': 'Инициализация widgets пакета'
            },
            'required': False
        }
    }
    
    # Также проверяем файлы в корневой директории
    root_files = {
        'main_app.py': 'Основное приложение',
        '__init__.py': 'Инициализация корневого пакета',
        'performance.py': 'Мониторинг производительности (опционально)',
        'state.py': 'Управление состоянием (опционально)',
        'geometry_utils.py': 'Геометрические утилиты (опционально)'
    }
    
    print("📁 Проверка структуры пакетов:")
    
    # Проверяем каждый пакет
    available_packages = 0
    total_packages = len(expected_structure)
    
    for package_name, package_info in expected_structure.items():
        package_path = current_dir / package_name
        
        if package_path.exists() and package_path.is_dir():
            print(f"  ✅ Пакет {package_name}/ ({package_info['description']})")
            structure_info['expected_modules'][package_name] = {'available': True, 'files': {}}
            available_packages += 1
            
            # Проверяем файлы внутри пакета
            for file_name, file_desc in package_info['files'].items():
                file_path = package_path / file_name
                if file_path.exists():
                    structure_info['expected_modules'][package_name]['files'][file_name] = True
                    print(f"    ✅ {file_name} ({file_desc})")
                else:
                    structure_info['expected_modules'][package_name]['files'][file_name] = False
                    if package_info['required']:
                        structure_info['issues'].append(f"Отсутствует {package_name}/{file_name}")
                    else:
                        print(f"    ⚠️ {file_name} ({file_desc}) - отсутствует")
        else:
            if package_info['required']:
                print(f"  ❌ Пакет {package_name}/ - отсутствует (требуется)")
                structure_info['expected_modules'][package_name] = {'available': False}
                structure_info['issues'].append(f"Отсутствует обязательный пакет {package_name}/")
            else:
                print(f"  ⚠️ Пакет {package_name}/ - отсутствует (опционально)")
                structure_info['expected_modules'][package_name] = {'available': False}
    
    # Проверяем корневые файлы
    print("\n📄 Проверка корневых файлов:")
    for file_name, file_desc in root_files.items():
        file_path = current_dir / file_name
        if file_path.exists():
            structure_info['optional_modules'][file_name] = True
            print(f"  ✅ {file_name} ({file_desc})")
        else:
            structure_info['optional_modules'][file_name] = False
            if file_name in ['main_app.py', '__init__.py']:
                structure_info['issues'].append(f"Отсутствует критически важный файл {file_name}")
                print(f"  ❌ {file_name} ({file_desc}) - критично важен")
            else:
                print(f"  ⚠️ {file_name} ({file_desc}) - отсутствует")
    
    # Определяем тип архитектуры
    if available_packages >= 2:
        structure_info['architecture_type'] = 'modular'
        print(f"\n🏛️ Архитектура: Модульная ({available_packages}/{total_packages} пакетов доступно)")
    elif available_packages == 1:
        structure_info['architecture_type'] = 'partial_modular'
        print(f"\n🏗️ Архитектура: Частично модульная ({available_packages}/{total_packages} пакетов)")
    else:
        structure_info['architecture_type'] = 'flat'
        print("\n📁 Архитектура: Плоская структура (legacy)")
    
    # Оценка общего состояния
    critical_issues = len([issue for issue in structure_info['issues'] 
                          if 'критически важный' in issue or 'обязательный пакет' in issue])
    
    if critical_issues == 0:
        structure_valid = True
        print("✅ Структура проекта готова к работе")
    else:
        structure_valid = False
        print(f"❌ Обнаружено {critical_issues} критических проблем со структурой")
    
    return structure_valid, structure_info

def check_system_requirements():
    """
    Проверка системных требований с учетом модульной структуры
    
    Эта обновленная функция демонстрирует принципы "architecture-aware diagnostics" -
    система понимает свою модульную структуру и проверяет компоненты в правильных
    местах, а не ищет все файлы в корневой папке.
    
    Returns:
        tuple: (is_ready: bool, status_info: dict)
    """
    print("🔍 Комплексная диагностика системы...")
    
    status_info = {
        'python_version': sys.version_info,
        'current_directory': str(current_dir),
        'timestamp': datetime.now().isoformat(),
        'components': {},
        'issues': [],
        'recommendations': [],
        'architecture_info': {}
    }
    
    # Этап 1: Базовые системные требования
    print("\n📋 Этап 1: Базовые системные требования")
    
    # Проверка версии Python
    if sys.version_info < (3, 7):
        status_info['issues'].append("Требуется Python 3.7 или новее")
        status_info['recommendations'].append("Обновите Python до версии 3.7+")
        return False, status_info
    else:
        print(f"  ✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Проверка доступности tkinter для GUI
    try:
        import tkinter
        status_info['components']['tkinter'] = True
        print("  ✅ GUI библиотека (tkinter) доступна")
    except ImportError:
        status_info['components']['tkinter'] = False
        status_info['issues'].append("Отсутствует tkinter для графического интерфейса")
        status_info['recommendations'].append("Установите tkinter: apt-get install python3-tk (Linux) или переустановите Python с tkinter")
        return False, status_info
    
    # Этап 2: Анализ архитектуры проекта  
    print("\n🏗️ Этап 2: Анализ архитектуры проекта")
    structure_valid, structure_info = check_modular_structure()
    status_info['architecture_info'] = structure_info
    
    if not structure_valid:
        status_info['issues'].extend(structure_info['issues'])
        status_info['recommendations'].append("Восстановите критически важные компоненты проекта")
        return False, status_info
    
    # Этап 3: Проверка импорта модулей
    print("\n🔗 Этап 3: Проверка импорта модулей")
    
    # Проверяем core модули (самые важные)
    core_modules_status = {}
    
    # Проверяем file_manager из пакета core
    try:
        from core.file_manager import FileManager
        # Пытаемся создать экземпляр для полной проверки
        fm = FileManager()
        core_modules_status['core.file_manager'] = True
        print("  ✅ core.file_manager - FileManager успешно импортирован и инициализирован")
    except ImportError as e:
        core_modules_status['core.file_manager'] = False
        status_info['issues'].append(f"Не удается импортировать core.file_manager: {e}")
        print(f"  ❌ core.file_manager - ошибка импорта: {e}")
    except Exception as e:
        core_modules_status['core.file_manager'] = False
        status_info['issues'].append(f"Ошибка инициализации FileManager: {e}")
        print(f"  ⚠️ core.file_manager - импорт успешен, но ошибка инициализации: {e}")
    
    # Проверяем основное приложение
    try:
        from main_app import ModernBessApp
        core_modules_status['main_app'] = True
        print("  ✅ main_app - ModernBessApp доступен")
    except ImportError as e:
        core_modules_status['main_app'] = False
        status_info['issues'].append(f"Не удается импортировать ModernBessApp: {e}")
        print(f"  ❌ main_app - ошибка импорта: {e}")
    
    # Проверяем опциональные модули
    optional_modules_status = {}
    
    optional_modules = [
        ('geometry_utils', 'Геометрические утилиты'),
        ('performance', 'Мониторинг производительности'), 
        ('state', 'Управление состоянием')
    ]
    
    for module_name, description in optional_modules:
        try:
            __import__(module_name)
            optional_modules_status[module_name] = True
            print(f"  ✅ {module_name} - {description}")
        except ImportError:
            optional_modules_status[module_name] = False
            print(f"  ⚠️ {module_name} - {description} (недоступен)")
    
    status_info['components'].update(core_modules_status)
    status_info['components'].update(optional_modules_status)
    
    # Этап 4: Оценка общей готовности системы
    print("\n🎯 Этап 4: Оценка готовности системы")
    
    # Подсчет критических компонентов
    critical_components = ['core.file_manager', 'main_app']
    available_critical = sum(1 for comp in critical_components if status_info['components'].get(comp, False))
    
    # Подсчет опциональных компонентов
    available_optional = sum(1 for status in optional_modules_status.values() if status)
    
    # Определение уровня функциональности
    if available_critical == len(critical_components):
        if available_optional >= len(optional_modules) * 0.8:  # 80% опциональных модулей
            functionality_level = "Полная функциональность"
            system_ready = True
        elif available_optional >= len(optional_modules) * 0.5:  # 50% опциональных модулей
            functionality_level = "Расширенная функциональность"
            system_ready = True
        else:
            functionality_level = "Базовая функциональность"
            system_ready = True
    else:
        functionality_level = "Неполная функциональность"
        system_ready = False
        status_info['issues'].append("Отсутствуют критически важные компоненты")
    
    status_info['functionality_level'] = functionality_level
    print(f"  🎯 Уровень функциональности: {functionality_level}")
    print(f"  📊 Критические компоненты: {available_critical}/{len(critical_components)}")
    print(f"  📊 Опциональные компоненты: {available_optional}/{len(optional_modules)}")
    
    if system_ready:
        print("\n✅ Система готова к запуску!")
    else:
        print("\n❌ Система не готова к запуску")
        print("\n🚨 ОБНАРУЖЕННЫЕ ПРОБЛЕМЫ:")
        for issue in status_info['issues']:
            print(f"  • {issue}")
        
        print("\n💡 РЕКОМЕНДАЦИИ:")
        recommendations = status_info['recommendations'] + [
            "Убедитесь, что файл core/file_manager.py существует и содержит класс FileManager",
            "Проверьте наличие файла core/__init__.py для корректной работы пакета",
            "Рассмотрите возможность переустановки отсутствующих компонентов"
        ]
        for recommendation in recommendations:
            print(f"  • {recommendation}")
    
    return system_ready, status_info

def create_application():
    """
    Создание и инициализация приложения с учетом модульной структуры
    
    Эта функция демонстрирует принципы "adaptive architecture" - система
    адаптируется к доступным компонентам и создает наилучшую возможную
    конфигурацию приложения.
    
    Returns:
        ModernBessApp или None в случае ошибки
    """
    try:
        print("🏗️ Создание приложения...")
        
        # Импортируем основное приложение
        from main_app import ModernBessApp
        
        # Создаем экземпляр приложения
        app = ModernBessApp()
        print("  ✅ Экземпляр приложения создан")
        
        # Инициализируем приложение
        print("  ⚙️ Инициализация компонентов...")
        if app.initialize():
            print("  ✅ Приложение успешно инициализировано")
            return app
        else:
            print("  ⚠️ Частичная инициализация - некоторые компоненты могут быть недоступны")
            print("  💡 Приложение будет работать в режиме ограниченной функциональности")
            return app
            
    except ImportError as e:
        print(f"  ❌ Не удается импортировать приложение: {e}")
        print("  💡 Проверьте наличие файла main_app.py")
        return None
        
    except Exception as e:
        print(f"  ❌ Неожиданная ошибка при создании приложения: {e}")
        print("  📋 Детали ошибки:")
        traceback.print_exc()
        return None

def run_application(app):
    """
    Запуск основного цикла приложения
    
    Args:
        app: Экземпляр ModernBessApp для запуска
        
    Returns:
        bool: True если приложение завершилось корректно
    """
    try:
        print("🚀 Запуск приложения...")
        print("💡 Для завершения работы закройте окно приложения")
        print("=" * 60)
        
        # Запускаем основной цикл приложения
        success = app.run()
        
        if success:
            print("\n" + "=" * 60)
            print("✅ Приложение завершено успешно")
        else:
            print("\n" + "=" * 60)
            print("⚠️ Приложение завершено с предупреждениями")
            print("💡 Проверьте лог-файлы для получения дополнительной информации")
        
        return success
        
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("⚠️ Получен сигнал прерывания (Ctrl+C)")
        print("✅ Приложение корректно завершено пользователем")
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Критическая ошибка во время работы приложения: {e}")
        print("📋 Детали ошибки:")
        traceback.print_exc()
        print("\n💡 Рекомендации:")
        print("  • Проверьте целостность файлов проекта")
        print("  • Перезапустите приложение")
        print("  • Обратитесь к документации по устранению неполадок")
        return False

def show_startup_banner():
    """
    Отображение стартового баннера приложения
    """
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                          BESS_GEOMETRY v2.0                                 ║
║                   Building Energy Spatial System                            ║
║                                                                              ║
║  🏗️ Система обработки геометрии зданий для энергетического анализа          ║
║  🏛️ Модульная архитектура с разделением компонентов                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"📅 Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 Рабочая директория: {current_dir}")
    print(f"🐍 Python версия: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print()

def show_error_help():
    """
    Отображение справки при критических ошибках
    """
    help_text = """
🆘 СПРАВКА ПО УСТРАНЕНИЮ ПРОБЛЕМ

Если приложение не запускается, попробуйте следующее:

🔧 ОСНОВНЫЕ ПРОВЕРКИ:
  1. Убедитесь, что Python версии 3.7 или новее
  2. Проверьте наличие всех файлов проекта в правильных директориях
  3. Убедитесь, что у вас есть права на чтение файлов

📁 ОЖИДАЕМАЯ СТРУКТУРА ПРОЕКТА:
  • core/file_manager.py (менеджер файлов)
  • core/__init__.py (инициализация core пакета)
  • main_app.py (основное приложение)
  • __init__.py (инициализация корневого пакета)

🔍 ДИАГНОСТИКА:
  • Проверьте структуру папок в файловом менеджере
  • Убедитесь, что core/file_manager.py содержит класс FileManager
  • Проверьте права доступа к файлам

💡 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ:
  • Документация по модульной архитектуре Python
  • Руководство по организации больших проектов
  • Примеры правильной структуры пакетов

📧 ПОДДЕРЖКА:
  Если проблема не решается, обратитесь к разработчикам
  с информацией о структуре вашего проекта и тексте ошибки.
    """
    print(help_text)

def main():
    """
    Главная функция приложения с поддержкой модульной архитектуры
    
    Returns:
        int: Код возврата (0 - успех, 1 - ошибка)
    """
    try:
        # Этап 1: Показываем стартовый баннер
        show_startup_banner()
        
        # Этап 2: Проверяем готовность системы (с учетом модульной структуры)
        print("🔍 Этап 1: Комплексная проверка системы")
        is_ready, status_info = check_system_requirements()
        
        if not is_ready:
            show_error_help()
            return 1
        
        print(f"✅ Система готова ({status_info['functionality_level']})")
        print()
        
        # Этап 3: Создание приложения
        print("🏗️ Этап 2: Создание приложения")
        app = create_application()
        
        if app is None:
            print("\n❌ Не удалось создать приложение")
            show_error_help()
            return 1
        
        print("✅ Приложение готово к запуску")
        print()
        
        # Этап 4: Запуск приложения
        print("🚀 Этап 3: Запуск приложения")
        success = run_application(app)
        
        # Возвращаем соответствующий код завершения
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️ Запуск прерван пользователем")
        return 0
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка при запуске: {e}")
        print("\n📋 Подробности ошибки:")
        traceback.print_exc()
        show_error_help()
        return 1

# Специальные команды для диагностики
def handle_special_commands():
    """Обработка специальных команд командной строки"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command in ['--help', '-h']:
            print("BESS_Geometry - Система обработки геометрии зданий")
            print("\nКоманды:")
            print("  python __main__.py          - Запуск приложения")
            print("  python __main__.py --check  - Только диагностика системы")
            print("  python __main__.py --help   - Эта справка")
            return True
            
        elif command == '--check':
            show_startup_banner()
            is_ready, status_info = check_system_requirements()
            print(f"\nРезультат: {'Готов' if is_ready else 'Не готов'}")
            return True
    
    return False

# Точка входа
if __name__ == '__main__':
    if not handle_special_commands():
        exit_code = main()
        sys.exit(exit_code)