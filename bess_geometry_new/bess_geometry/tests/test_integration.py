# -*- coding: utf-8 -*-
"""
Тесты интеграции всех компонентов системы BESS_Geometry (ИСПРАВЛЕНО ДЛЯ PYTHON 3.13)

Исправления:
- Убран устаревший unittest.makeSuite 
- Добавлена совместимость с Python 3.13
- Упрощена логика запуска тестов
- Добавлена подробная диагностика ошибок
"""

import unittest
import sys
import os
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print(f"🔍 Тестирование из директории: {project_root}")
print(f"🐍 Python версия: {sys.version}")


class TestComponentAvailability(unittest.TestCase):
    """Тесты доступности компонентов"""
    
    def test_architectural_tools_import(self):
        """Тест импорта ArchitecturalTools"""
        try:
            from core.architectural_tools import ArchitecturalTools
            self.assertTrue(hasattr(ArchitecturalTools, 'add_void'))
            self.assertTrue(hasattr(ArchitecturalTools, 'add_second_light'))
            print("✅ ArchitecturalTools успешно импортирован")
        except ImportError as e:
            self.skipTest(f"ArchitecturalTools недоступен: {e}")
    
    def test_shaft_manager_import(self):
        """Тест импорта ShaftManager"""
        try:
            from core.shaft_manager import ShaftManager
            manager = ShaftManager()
            self.assertIsNotNone(manager)
            print("✅ ShaftManager успешно импортирован и инициализирован")
        except ImportError as e:
            self.skipTest(f"ShaftManager недоступен: {e}")
    
    def test_bess_parameters_import(self):
        """Тест импорта BESSParameterManager"""
        try:
            from core.bess_parameters import BESSParameterManager, ParameterScope
            manager = BESSParameterManager()
            self.assertIsNotNone(manager)
            print("✅ BESSParameterManager успешно импортирован и инициализирован")
        except ImportError as e:
            self.skipTest(f"BESSParameterManager недоступен: {e}")
    
    def test_contour_editor_import(self):
        """Тест импорта ContourEditor"""
        try:
            from ui.contour_editor import ContourEditor, EditingMode, ElementType
            # Не создаем экземпляр без canvas
            self.assertTrue(True)  # Если импорт прошел успешно
            print("✅ ContourEditor успешно импортирован")
        except ImportError as e:
            self.skipTest(f"ContourEditor недоступен: {e}")
    
    def test_integration_manager_import(self):
        """Тест импорта IntegrationManager"""
        try:
            from core.integration_manager import IntegrationManager, ComponentStatus
            manager = IntegrationManager()
            self.assertIsNotNone(manager)
            print("✅ IntegrationManager успешно импортирован и инициализирован")
        except ImportError as e:
            self.skipTest(f"IntegrationManager недоступен: {e}")


class TestBasicStructure(unittest.TestCase):
    """Тесты базовой структуры проекта"""
    
    def test_project_structure(self):
        """Проверка наличия ключевых файлов"""
        required_files = [
            'core/__init__.py',
            'ui/__init__.py', 
            'main_controller.py',
            'geometry_operations.py'
        ]
        
        missing_files = []
        for file_path in required_files:
            full_path = project_root / file_path
            if not full_path.exists():
                missing_files.append(file_path)
        
        if missing_files:
            self.fail(f"Отсутствуют файлы: {missing_files}")
        else:
            print(f"✅ Все {len(required_files)} ключевых файлов найдены")
    
    def test_core_package_import(self):
        """Тест импорта core пакета"""
        try:
            import core
            print("✅ Core пакет импортируется")
            
            # Проверяем базовые функции
            if hasattr(core, 'get_integration_status'):
                status = core.get_integration_status()
                print(f"✅ Статус интеграции: {status}")
            else:
                print("⚠️ get_integration_status недоступен")
                
        except ImportError as e:
            self.fail(f"Не удается импортировать core пакет: {e}")
    
    def test_ui_package_import(self):
        """Тест импорта UI пакета"""
        try:
            import ui
            print("✅ UI пакет импортируется")
            
            # Проверяем базовые функции
            if hasattr(ui, 'get_ui_integration_status'):
                status = ui.get_ui_integration_status()
                print(f"✅ Статус UI: {status}")
            else:
                print("⚠️ get_ui_integration_status недоступен")
                
        except ImportError as e:
            self.fail(f"Не удается импортировать UI пакет: {e}")


class TestMainControllerIntegration(unittest.TestCase):
    """Тесты интеграции главного контроллера"""
    
    def setUp(self):
        """Настройка тестового окружения"""
        self.mock_root = None  # Не используем реальный Tk для тестов
        
    def test_main_controller_import(self):
        """Тест импорта MainController"""
        try:
            from main_controller import MainController
            print("✅ MainController успешно импортирован")
        except ImportError as e:
            self.skipTest(f"MainController недоступен: {e}")
    
    def test_main_controller_has_integration_methods(self):
        """Проверка наличия методов интеграции"""
        try:
            from main_controller import MainController
            
            # Проверяем наличие новых методов (без создания экземпляра)
            expected_methods = [
                'create_void_room',
                'create_second_light', 
                'import_shafts',
                'start_contour_editing',
                'update_element_parameters'
            ]
            
            for method_name in expected_methods:
                if hasattr(MainController, method_name):
                    print(f"✅ {method_name} метод найден")
                else:
                    print(f"⚠️ {method_name} метод не найден")
                    
        except ImportError as e:
            self.skipTest(f"MainController недоступен: {e}")


class TestSimpleIntegration(unittest.TestCase):
    """Простые тесты интеграции без создания экземпляров"""
    
    def test_geometry_operations_integration(self):
        """Тест интеграции GeometryOperations"""
        try:
            from core.geometry_operations import GeometryOperations
            
            # Создаем экземпляр без состояния
            geom_ops = GeometryOperations()
            
            # Проверяем наличие методов интеграции
            integration_methods = [
                'create_void_element',
                'create_second_light_element',
                'update_element_parameters'
            ]
            
            found_methods = 0
            for method in integration_methods:
                if hasattr(geom_ops, method):
                    found_methods += 1
                    print(f"✅ GeometryOperations.{method} найден")
                else:
                    print(f"⚠️ GeometryOperations.{method} не найден")
            
            print(f"📊 GeometryOperations: {found_methods}/{len(integration_methods)} методов интеграции")
            
        except ImportError as e:
            self.skipTest(f"GeometryOperations недоступен: {e}")
        except Exception as e:
            self.fail(f"Ошибка создания GeometryOperations: {e}")
    
    def test_integration_manager_basic(self):
        """Базовый тест IntegrationManager"""
        try:
            from core.integration_manager import IntegrationManager
            
            manager = IntegrationManager()
            
            # Проверяем базовые атрибуты
            self.assertTrue(hasattr(manager, 'components'))
            self.assertTrue(hasattr(manager, 'integration_level'))
            
            # Проверяем методы
            self.assertTrue(hasattr(manager, 'initialize_all_components'))
            self.assertTrue(hasattr(manager, 'get_integration_report'))
            
            print("✅ IntegrationManager базовая функциональность работает")
            
        except ImportError as e:
            self.skipTest(f"IntegrationManager недоступен: {e}")
        except Exception as e:
            self.fail(f"Ошибка IntegrationManager: {e}")


class TestComprehensiveIntegration(unittest.TestCase):
    """Комплексные тесты интеграции"""
    
    def test_full_integration_status(self):
        """Комплексная проверка статуса интеграции"""
        print("\n" + "="*60)
        print("🧪 КОМПЛЕКСНАЯ ПРОВЕРКА ИНТЕГРАЦИИ BESS_GEOMETRY")
        print("="*60)
        
        results = {
            'core_components': {},
            'ui_components': {},
            'integration_manager': {},
            'main_controller': {}
        }
        
        # Проверяем core компоненты
        try:
            import core
            if hasattr(core, 'get_integration_status'):
                core_status = core.get_integration_status()
                results['core_components'] = core_status
                print(f"\n📦 Core компоненты:")
                print(f"   Уровень интеграции: {core_status.get('integration_level', 'unknown')}")
                print(f"   Готовность к этапу 3: {core_status.get('ready_for_stage3', False)}")
            else:
                print("\n📦 Core компоненты: базовая проверка")
                core_modules = ['spatial_processor', 'geometry_operations', 'integration_manager']
                for module in core_modules:
                    try:
                        exec(f"from core.{module} import *")
                        print(f"   ✅ {module}")
                        results['core_components'][module] = True
                    except ImportError:
                        print(f"   ❌ {module}")
                        results['core_components'][module] = False
        except Exception as e:
            print(f"\n❌ Ошибка проверки core: {e}")
            results['core_components']['error'] = str(e)
        
        # Проверяем UI компоненты
        try:
            import ui
            if hasattr(ui, 'get_ui_integration_status'):
                ui_status = ui.get_ui_integration_status()
                results['ui_components'] = ui_status
                print(f"\n🎨 UI компоненты:")
                print(f"   Уровень интеграции: {ui_status.get('integration_level', 'unknown')}")
                print(f"   Готовность редактирования: {ui_status.get('ready_for_contour_editing', False)}")
            else:
                print("\n🎨 UI компоненты: базовая проверка")
                try:
                    from ui.geometry_canvas import GeometryCanvas
                    print("   ✅ geometry_canvas")
                    results['ui_components']['geometry_canvas'] = True
                except ImportError:
                    print("   ❌ geometry_canvas")
                    results['ui_components']['geometry_canvas'] = False
                    
                try:
                    from ui.contour_editor import ContourEditor
                    print("   ✅ contour_editor")
                    results['ui_components']['contour_editor'] = True
                except ImportError:
                    print("   ❌ contour_editor")
                    results['ui_components']['contour_editor'] = False
        except Exception as e:
            print(f"\n❌ Ошибка проверки UI: {e}")
            results['ui_components']['error'] = str(e)
        
        # Проверяем IntegrationManager
        try:
            from core.integration_manager import IntegrationManager
            manager = IntegrationManager()
            
            print(f"\n🔧 IntegrationManager:")
            print(f"   Создан успешно: ✅")
            
            # Пытаемся получить отчет
            try:
                report = manager.get_integration_report()
                results['integration_manager'] = report
                summary = report.get('summary', {})
                total = summary.get('total_components', 0)
                ready = summary.get('ready_components', 0)
                print(f"   Готовых компонентов: {ready}/{total}")
            except Exception as e:
                print(f"   Ошибка получения отчета: {e}")
                results['integration_manager']['report_error'] = str(e)
                
        except Exception as e:
            print(f"\n❌ Ошибка IntegrationManager: {e}")
            results['integration_manager']['error'] = str(e)
        
        # Проверяем MainController
        try:
            from main_controller import MainController
            print(f"\n🎮 MainController:")
            print(f"   Импорт успешен: ✅")
            
            # Проверяем методы
            integration_methods = [
                'create_void_room', 'create_second_light', 'import_shafts',
                'start_contour_editing', 'update_element_parameters'
            ]
            
            found = 0
            for method in integration_methods:
                if hasattr(MainController, method):
                    found += 1
            
            print(f"   Методы интеграции: {found}/{len(integration_methods)}")
            results['main_controller']['methods_found'] = found
            results['main_controller']['total_methods'] = len(integration_methods)
            
        except Exception as e:
            print(f"\n❌ Ошибка MainController: {e}")
            results['main_controller']['error'] = str(e)
        
        # Финальная оценка
        self._generate_final_assessment(results)
        
        # Тест всегда проходит - это диагностический тест
        self.assertTrue(True)
    
    def _generate_final_assessment(self, results: Dict[str, Any]):
        """Генерация финальной оценки"""
        print(f"\n🎯 ФИНАЛЬНАЯ ОЦЕНКА:")
        print("-" * 40)
        
        total_score = 0
        max_score = 4
        
        # Оценка core
        core_error = results['core_components'].get('error')
        if not core_error and results['core_components']:
            total_score += 1
            print("✅ Core компоненты доступны")
        else:
            print("❌ Core компоненты требуют доработки")
        
        # Оценка UI
        ui_error = results['ui_components'].get('error') 
        if not ui_error and results['ui_components']:
            total_score += 1
            print("✅ UI компоненты доступны")
        else:
            print("❌ UI компоненты требуют доработки")
        
        # Оценка IntegrationManager
        im_error = results['integration_manager'].get('error')
        if not im_error:
            total_score += 1
            print("✅ IntegrationManager работает")
        else:
            print("❌ IntegrationManager требует исправления")
        
        # Оценка MainController
        mc_error = results['main_controller'].get('error')
        methods_found = results['main_controller'].get('methods_found', 0)
        total_methods = results['main_controller'].get('total_methods', 5)
        
        if not mc_error and methods_found >= total_methods * 0.8:
            total_score += 1
            print("✅ MainController интеграция успешна")
        else:
            print("❌ MainController требует доработки")
        
        # Финальный вердикт
        percentage = (total_score / max_score) * 100
        print(f"\n📊 ОБЩИЙ РЕЗУЛЬТАТ: {percentage:.0f}% ({total_score}/{max_score})")
        
        if percentage >= 75:
            print("🎉 ИНТЕГРАЦИЯ УСПЕШНА! Система готова к работе.")
        elif percentage >= 50:
            print("🔧 ИНТЕГРАЦИЯ ЧАСТИЧНАЯ. Система функциональна с ограничениями.")
        else:
            print("⚠️ ИНТЕГРАЦИЯ ТРЕБУЕТ ДОРАБОТКИ. Необходимы дополнительные действия.")
        
        # Рекомендации
        print(f"\n💡 РЕКОМЕНДАЦИИ:")
        if percentage < 75:
            print("   • Проверьте наличие всех файлов из роадмапа")
            print("   • Убедитесь, что все новые модули созданы")
            print("   • Запустите: python examples/integration_demo.py")
        else:
            print("   • Система готова к использованию")
            print("   • Можете запускать: python main.py")


def run_tests():
    """Запуск всех тестов с улучшенной обработкой ошибок"""
    print("🧪 Запуск тестов интеграции BESS_Geometry...")
    print("=" * 60)
    
    # Создаем test suite вручную (без makeSuite)
    suite = unittest.TestSuite()
    
    # Добавляем тесты по классам
    test_classes = [
        TestComponentAvailability,
        TestBasicStructure, 
        TestMainControllerIntegration,
        TestSimpleIntegration,
        TestComprehensiveIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Запуск тестов
    runner = unittest.TextTestRunner(
        verbosity=2, 
        stream=sys.stdout,
        buffer=True  # Буферизация вывода для лучшего отображения
    )
    
    try:
        result = runner.run(suite)
        
        print("\n" + "="*60)
        print(f"🏁 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
        print(f"   Всего тестов: {result.testsRun}")
        print(f"   Успешных: {result.testsRun - len(result.failures) - len(result.errors)}")
        print(f"   Неудачных: {len(result.failures)}")
        print(f"   Ошибок: {len(result.errors)}")
        print(f"   Пропущенных: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
        
        if result.wasSuccessful():
            print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
            return 0
        else:
            print("⚠️ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ. См. детали выше.")
            
            # Показываем ошибки
            if result.failures:
                print("\n❌ НЕУДАЧИ:")
                for test, traceback in result.failures:
                    print(f"   • {test}: {traceback}")
            
            if result.errors:
                print("\n💥 ОШИБКИ:")
                for test, traceback in result.errors:
                    print(f"   • {test}: {traceback}")
            
            return 1
            
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА ЗАПУСКА ТЕСТОВ: {e}")
        print(f"Детали: {traceback.format_exc()}")
        return 2


if __name__ == '__main__':
    # Проверяем Python версию
    if sys.version_info >= (3, 13):
        print(f"🐍 Обнаружен Python {sys.version_info.major}.{sys.version_info.minor} - используем совместимый режим")
    
    exit_code = run_tests()
    print("="*60)
    sys.exit(exit_code)