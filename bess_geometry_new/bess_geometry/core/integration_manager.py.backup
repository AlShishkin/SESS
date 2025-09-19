# -*- coding: utf-8 -*-
"""
IntegrationManager - координатор интеграции всех компонентов BESS_Geometry

Этот модуль обеспечивает правильную инициализацию, настройку и взаимодействие 
между всеми модулями системы. Он является "дирижером" процесса интеграции и
обеспечивает централизованное управление зависимостями.

Ключевые функции:
- Автоматическое обнаружение и инициализация компонентов
- Настройка связей между компонентами  
- Валидация целостности интеграции
- Диагностика проблем интеграции
- Координация обновлений компонентов

Архитектурные принципы:
- Fail-safe initialization: система работает даже при отсутствии некоторых компонентов
- Dependency injection: компоненты получают зависимости через менеджер
- Health monitoring: постоянный мониторинг состояния интеграции
- Graceful degradation: плавная деградация функциональности при проблемах
"""

import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Type
from enum import Enum
from dataclasses import dataclass, field


class ComponentStatus(Enum):
    """Статусы компонентов системы"""
    NOT_FOUND = "not_found"          # Компонент не найден
    FOUND = "found"                  # Компонент найден, но не инициализирован
    INITIALIZING = "initializing"    # Процесс инициализации
    READY = "ready"                  # Компонент готов к работе
    ERROR = "error"                  # Ошибка в компоненте
    DISABLED = "disabled"            # Компонент отключен


class IntegrationLevel(Enum):
    """Уровни интеграции"""
    BASIC = "basic"           # Базовая интеграция (импорт модулей)
    FUNCTIONAL = "functional" # Функциональная интеграция (создание экземпляров)
    FULL = "full"            # Полная интеграция (связи между компонентами)


@dataclass
class ComponentInfo:
    """Информация о компоненте системы"""
    name: str
    module_path: str
    class_name: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    status: ComponentStatus = ComponentStatus.NOT_FOUND
    instance: Any = None
    error_message: Optional[str] = None
    initialization_time: Optional[datetime] = None
    
    def is_available(self) -> bool:
        """Проверка доступности компонента"""
        return self.status in [ComponentStatus.READY, ComponentStatus.FOUND]
    
    def is_ready(self) -> bool:
        """Проверка готовности компонента к работе"""
        return self.status == ComponentStatus.READY


class IntegrationManager:
    """
    Менеджер интеграции компонентов BESS_Geometry
    
    Центральный координатор, который обеспечивает правильную инициализацию
    и взаимодействие всех компонентов системы.
    """
    
    def __init__(self, main_controller=None):
        self.main_controller = main_controller
        
        # Реестр компонентов
        self.components: Dict[str, ComponentInfo] = {}
        self.integration_level = IntegrationLevel.BASIC
        self.integration_status = {}
        
        # Callbacks для событий интеграции
        self.event_handlers: Dict[str, List[Callable]] = {
            'component_found': [],
            'component_ready': [],
            'component_error': [],
            'integration_complete': [],
            'integration_failed': []
        }
        
        # Настройки интеграции
        self.auto_retry_failed = True
        self.max_retry_attempts = 3
        self.component_timeout = 30  # секунд
        
        # Инициализируем реестр компонентов
        self._initialize_component_registry()
    
    def _initialize_component_registry(self):
        """Инициализация реестра компонентов для интеграции"""
        components_config = [
            {
                'name': 'architectural_tools',
                'module_path': 'core.architectural_tools',
                'class_name': 'ArchitecturalTools',
                'dependencies': []
            },
            {
                'name': 'shaft_manager',
                'module_path': 'core.shaft_manager',
                'class_name': 'ShaftManager',
                'dependencies': []
            },
            {
                'name': 'bess_parameters',
                'module_path': 'core.bess_parameters',
                'class_name': 'BESSParameterManager',
                'dependencies': []
            },
            {
                'name': 'contour_editor',
                'module_path': 'ui.contour_editor',
                'class_name': 'ContourEditor',
                'dependencies': ['geometry_canvas']  # Зависит от canvas
            },
            {
                'name': 'geometry_operations',
                'module_path': 'core.geometry_operations',
                'class_name': 'GeometryOperations',
                'dependencies': ['architectural_tools', 'bess_parameters', 'shaft_manager']
            },
            {
                'name': 'editing_modes',
                'module_path': 'core.editing_modes',
                'class_name': 'EditingModeManager',
                'dependencies': ['architectural_tools']
            }
        ]
        
        for config in components_config:
            component = ComponentInfo(
                name=config['name'],
                module_path=config['module_path'],
                class_name=config.get('class_name'),
                dependencies=config.get('dependencies', [])
            )
            self.components[config['name']] = component
    
    def initialize_all_components(self) -> Dict[str, Any]:
        """
        Инициализация всех доступных компонентов
        
        Returns:
            Подробный отчет о результатах инициализации
        """
        print("🚀 Начинаем интеграцию компонентов BESS_Geometry...")
        
        results = {
            'start_time': datetime.now(),
            'components': {},
            'integration_level': IntegrationLevel.BASIC,
            'total_components': len(self.components),
            'successful_components': 0,
            'failed_components': 0,
            'warnings': [],
            'errors': []
        }
        
        # Этап 1: Обнаружение компонентов
        print("\n📋 Этап 1: Обнаружение компонентов")
        discovery_results = self._discover_components()
        results['discovery'] = discovery_results
        
        # Этап 2: Инициализация компонентов
        print("\n⚙️ Этап 2: Инициализация компонентов")
        initialization_results = self._initialize_components()
        results['initialization'] = initialization_results
        
        # Этап 3: Настройка связей между компонентами
        print("\n🔗 Этап 3: Настройка связей между компонентами")
        connection_results = self._setup_component_connections()
        results['connections'] = connection_results
        
        # Подсчет статистики
        for component_name, component in self.components.items():
            results['components'][component_name] = {
                'status': component.status.value,
                'available': component.is_available(),
                'ready': component.is_ready(),
                'has_instance': component.instance is not None,
                'error': component.error_message
            }
            
            if component.is_ready():
                results['successful_components'] += 1
            elif component.status == ComponentStatus.ERROR:
                results['failed_components'] += 1
        
        # Определение достигнутого уровня интеграции
        self.integration_level = self._determine_integration_level()
        results['integration_level'] = self.integration_level
        results['end_time'] = datetime.now()
        results['duration'] = (results['end_time'] - results['start_time']).total_seconds()
        
        # Генерация отчета
        self._generate_integration_report(results)
        
        # Уведомление о завершении интеграции
        if results['successful_components'] >= results['total_components'] * 0.7:  # 70% успеха
            self._fire_event('integration_complete', results)
        else:
            self._fire_event('integration_failed', results)
        
        return results
    
    def _discover_components(self) -> Dict[str, Any]:
        """Обнаружение доступных компонентов"""
        discovery_results = {
            'found_components': [],
            'missing_components': [],
            'import_errors': {}
        }
        
        for component_name, component in self.components.items():
            try:
                print(f"  🔍 Поиск {component_name}...")
                
                # Попытка импорта модуля
                module = self._import_module(component.module_path)
                
                if module:
                    component.status = ComponentStatus.FOUND
                    discovery_results['found_components'].append(component_name)
                    print(f"    ✅ {component_name} найден")
                    self._fire_event('component_found', {'name': component_name})
                else:
                    component.status = ComponentStatus.NOT_FOUND
                    discovery_results['missing_components'].append(component_name)
                    print(f"    ❌ {component_name} не найден")
                    
            except ImportError as e:
                component.status = ComponentStatus.ERROR
                component.error_message = str(e)
                discovery_results['import_errors'][component_name] = str(e)
                discovery_results['missing_components'].append(component_name)
                print(f"    ❌ {component_name} - ошибка импорта: {e}")
            except Exception as e:
                component.status = ComponentStatus.ERROR
                component.error_message = f"Неожиданная ошибка: {e}"
                discovery_results['import_errors'][component_name] = str(e)
                print(f"    ❌ {component_name} - неожиданная ошибка: {e}")
        
        print(f"📊 Обнаружено: {len(discovery_results['found_components'])} из {len(self.components)} компонентов")
        return discovery_results
    
    def _initialize_components(self) -> Dict[str, Any]:
        """Инициализация найденных компонентов"""
        initialization_results = {
            'initialized_components': [],
            'failed_initializations': {},
            'dependency_issues': []
        }
        
        # Сортируем компоненты по зависимостям (сначала независимые)
        sorted_components = self._sort_components_by_dependencies()
        
        for component_name in sorted_components:
            component = self.components[component_name]
            
            if component.status != ComponentStatus.FOUND:
                continue
            
            try:
                print(f"  ⚙️ Инициализация {component_name}...")
                component.status = ComponentStatus.INITIALIZING
                
                # Проверяем зависимости
                if not self._check_dependencies(component):
                    dependency_issue = f"Не выполнены зависимости для {component_name}: {component.dependencies}"
                    initialization_results['dependency_issues'].append(dependency_issue)
                    print(f"    ⚠️ {dependency_issue}")
                    continue
                
                # Создаем экземпляр компонента
                instance = self._create_component_instance(component_name, component)
                
                if instance:
                    component.instance = instance
                    component.status = ComponentStatus.READY
                    component.initialization_time = datetime.now()
                    initialization_results['initialized_components'].append(component_name)
                    print(f"    ✅ {component_name} инициализирован")
                    self._fire_event('component_ready', {'name': component_name, 'instance': instance})
                else:
                    component.status = ComponentStatus.ERROR
                    component.error_message = "Не удалось создать экземпляр"
                    print(f"    ❌ {component_name} - не удалось создать экземпляр")
                    
            except Exception as e:
                component.status = ComponentStatus.ERROR
                component.error_message = str(e)
                initialization_results['failed_initializations'][component_name] = str(e)
                print(f"    ❌ {component_name} - ошибка инициализации: {e}")
                self._fire_event('component_error', {'name': component_name, 'error': str(e)})
        
        print(f"📊 Инициализировано: {len(initialization_results['initialized_components'])} компонентов")
        return initialization_results
    
    def _setup_component_connections(self) -> Dict[str, Any]:
        """Настройка связей между компонентами"""
        connection_results = {
            'established_connections': [],
            'failed_connections': {},
            'cross_component_features': []
        }
        
        # Настройка GeometryOperations с интегрированными компонентами
        if self._is_component_ready('geometry_operations'):
            geom_ops = self.get_component_instance('geometry_operations')
            
            # Подключаем BESSParameterManager
            if self._is_component_ready('bess_parameters'):
                bess_params = self.get_component_instance('bess_parameters')
                if hasattr(geom_ops, 'parameter_manager'):
                    geom_ops.parameter_manager = bess_params
                    connection_results['established_connections'].append('geometry_operations -> bess_parameters')
                    print("    🔗 GeometryOperations связан с BESSParameterManager")
            
            # Подключаем ShaftManager
            if self._is_component_ready('shaft_manager'):
                shaft_mgr = self.get_component_instance('shaft_manager')
                if hasattr(geom_ops, 'shaft_manager'):
                    geom_ops.shaft_manager = shaft_mgr
                    connection_results['established_connections'].append('geometry_operations -> shaft_manager')
                    print("    🔗 GeometryOperations связан с ShaftManager")
        
        # Настройка MainController с новыми компонентами
        if self.main_controller:
            try:
                self._setup_main_controller_connections()
                connection_results['established_connections'].append('main_controller -> all_components')
                print("    🔗 MainController связан с интегрированными компонентами")
            except Exception as e:
                connection_results['failed_connections']['main_controller'] = str(e)
                print(f"    ❌ Ошибка связи MainController: {e}")
        
        # Настройка ContourEditor с canvas (если доступен)
        if self._is_component_ready('contour_editor') and self.main_controller:
            try:
                self._setup_contour_editor_connection()
                connection_results['established_connections'].append('contour_editor -> canvas')
                print("    🔗 ContourEditor связан с canvas")
            except Exception as e:
                connection_results['failed_connections']['contour_editor'] = str(e)
                print(f"    ⚠️ ContourEditor не связан с canvas: {e}")
        
        print(f"📊 Установлено связей: {len(connection_results['established_connections'])}")
        return connection_results
    
    def _import_module(self, module_path: str):
        """Безопасный импорт модуля"""
        try:
            if module_path.startswith('..'):
                # Относительный импорт
                module_path = module_path[2:].replace('.', '/')
                from importlib import import_module
                return import_module(module_path)
            else:
                exec(f"import {module_path}")
                return eval(module_path)
        except ImportError:
            return None
        except Exception:
            return None
    
    def _create_component_instance(self, component_name: str, component: ComponentInfo):
        """Создание экземпляра компонента"""
        if not component.class_name:
            # Компонент не требует создания экземпляра (статический)
            return True
        
        try:
            # Специальная логика для разных компонентов
            if component_name == 'shaft_manager':
                from core.shaft_manager import ShaftManager
                return ShaftManager()
            elif component_name == 'bess_parameters':
                from core.bess_parameters import BESSParameterManager
                return BESSParameterManager()
            elif component_name == 'geometry_operations':
                from core.geometry_operations import GeometryOperations
                state = getattr(self.main_controller, 'state', None) if self.main_controller else None
                return GeometryOperations(state)
            elif component_name == 'editing_modes':
                from core.editing_modes import EditingModeManager
                return EditingModeManager(self.main_controller)
            elif component_name == 'contour_editor':
                # ContourEditor создается позже при связи с canvas
                return None
            else:
                # Общий случай - пытаемся создать экземпляр
                module = self._import_module(component.module_path)
                if module and hasattr(module, component.class_name):
                    cls = getattr(module, component.class_name)
                    return cls()
                return None
                
        except Exception as e:
            print(f"Ошибка создания экземпляра {component_name}: {e}")
            return None
    
    def _sort_components_by_dependencies(self) -> List[str]:
        """Сортировка компонентов по зависимостям"""
        sorted_components = []
        remaining_components = set(self.components.keys())
        
        while remaining_components:
            # Находим компоненты без неудовлетворенных зависимостей
            ready_components = []
            for name in remaining_components:
                component = self.components[name]
                unmet_deps = [dep for dep in component.dependencies if dep in remaining_components]
                if not unmet_deps:
                    ready_components.append(name)
            
            if not ready_components:
                # Циклические зависимости или все оставшиеся имеют зависимости
                # Добавляем оставшиеся в произвольном порядке
                ready_components = list(remaining_components)
            
            sorted_components.extend(ready_components)
            remaining_components -= set(ready_components)
        
        return sorted_components
    
    def _check_dependencies(self, component: ComponentInfo) -> bool:
        """Проверка выполнения зависимостей компонента"""
        for dep_name in component.dependencies:
            if dep_name in self.components:
                dep_component = self.components[dep_name]
                if not dep_component.is_ready():
                    return False
            else:
                # Зависимость не является частью управляемых компонентов
                # Предполагаем, что она доступна (например, внешние модули)
                pass
        return True
    
    def _setup_main_controller_connections(self):
        """Настройка связей MainController с интегрированными компонентами"""
        if not self.main_controller:
            return
        
        # Подключаем ShaftManager
        if self._is_component_ready('shaft_manager'):
            self.main_controller.shaft_manager = self.get_component_instance('shaft_manager')
        
        # Подключаем BESSParameterManager
        if self._is_component_ready('bess_parameters'):
            self.main_controller.parameter_manager = self.get_component_instance('bess_parameters')
        
        # Подключаем EditingModeManager
        if self._is_component_ready('editing_modes'):
            self.main_controller.editing_mode_manager = self.get_component_instance('editing_modes')
    
    def _setup_contour_editor_connection(self):
        """Настройка связи ContourEditor с canvas"""
        if not self.main_controller or not hasattr(self.main_controller, 'canvas_controller'):
            return
        
        canvas_controller = getattr(self.main_controller, 'canvas_controller', None)
        if canvas_controller and hasattr(canvas_controller, 'canvas'):
            from ui.contour_editor import ContourEditor
            contour_editor = ContourEditor(canvas_controller.canvas)
            self.main_controller.contour_editor = contour_editor
            self.components['contour_editor'].instance = contour_editor
            self.components['contour_editor'].status = ComponentStatus.READY
    
    def _determine_integration_level(self) -> IntegrationLevel:
        """Определение достигнутого уровня интеграции"""
        ready_components = sum(1 for comp in self.components.values() if comp.is_ready())
        total_components = len(self.components)
        
        if ready_components == 0:
            return IntegrationLevel.BASIC
        elif ready_components < total_components * 0.7:
            return IntegrationLevel.FUNCTIONAL
        else:
            return IntegrationLevel.FULL
    
    def _generate_integration_report(self, results: Dict[str, Any]):
        """Генерация отчета об интеграции"""
        print(f"\n📋 ОТЧЕТ О ИНТЕГРАЦИИ BESS_GEOMETRY")
        print(f"{'='*60}")
        print(f"Время интеграции: {results['duration']:.2f} секунд")
        print(f"Уровень интеграции: {self.integration_level.value.upper()}")
        print(f"Успешно: {results['successful_components']}/{results['total_components']} компонентов")
        
        print(f"\n📊 СТАТУС КОМПОНЕНТОВ:")
        for name, info in results['components'].items():
            status_icon = "✅" if info['ready'] else "⚠️" if info['available'] else "❌"
            print(f"  {status_icon} {name}: {info['status']}")
            if info['error']:
                print(f"    └─ Ошибка: {info['error']}")
        
        if results.get('warnings'):
            print(f"\n⚠️ ПРЕДУПРЕЖДЕНИЯ:")
            for warning in results['warnings']:
                print(f"  • {warning}")
        
        if results.get('errors'):
            print(f"\n❌ ОШИБКИ:")
            for error in results['errors']:
                print(f"  • {error}")
        
        print(f"\n🎯 РЕКОМЕНДАЦИИ:")
        self._generate_recommendations(results)
    
    def _generate_recommendations(self, results: Dict[str, Any]):
        """Генерация рекомендаций по улучшению интеграции"""
        failed_count = results['failed_components']
        
        if failed_count == 0:
            print("  🎉 Все компоненты успешно интегрированы!")
        elif failed_count <= 2:
            print("  🔧 Рассмотрите возможность установки недостающих компонентов")
            print("  📚 Проверьте документацию по установке зависимостей")
        else:
            print("  🚨 Критическое количество неудачных интеграций")
            print("  🔄 Рекомендуется переустановка системы")
            print("  📞 Обратитесь в техническую поддержку")
        
        if self.integration_level != IntegrationLevel.FULL:
            print("  🎯 Для полной функциональности интегрируйте все компоненты")
    
    def _fire_event(self, event_name: str, data: Any):
        """Генерация события интеграции"""
        if event_name in self.event_handlers:
            for handler in self.event_handlers[event_name]:
                try:
                    handler(data)
                except Exception as e:
                    print(f"Ошибка в обработчике события {event_name}: {e}")
    
    # === PUBLIC API ===
    
    def get_component_instance(self, component_name: str):
        """Получение экземпляра компонента"""
        component = self.components.get(component_name)
        return component.instance if component and component.is_ready() else None
    
    def _is_component_ready(self, component_name: str) -> bool:
        """Проверка готовности компонента"""
        component = self.components.get(component_name)
        return component.is_ready() if component else False
    
    def get_integration_report(self) -> Dict[str, Any]:
        """Получение отчета о статусе интеграции"""
        return {
            'timestamp': datetime.now().isoformat(),
            'integration_level': self.integration_level.value,
            'components': {
                name: {
                    'status': comp.status.value,
                    'available': comp.is_available(),
                    'ready': comp.is_ready(),
                    'has_instance': comp.instance is not None,
                    'dependencies': comp.dependencies,
                    'error': comp.error_message
                }
                for name, comp in self.components.items()
            },
            'summary': {
                'total_components': len(self.components),
                'ready_components': sum(1 for comp in self.components.values() if comp.is_ready()),
                'available_components': sum(1 for comp in self.components.values() if comp.is_available()),
                'error_components': sum(1 for comp in self.components.values() if comp.status == ComponentStatus.ERROR)
            }
        }
    
    def register_event_handler(self, event_name: str, handler: Callable):
        """Регистрация обработчика события интеграции"""
        if event_name in self.event_handlers:
            self.event_handlers[event_name].append(handler)
    
    def reload_component(self, component_name: str) -> bool:
        """Перезагрузка компонента"""
        if component_name not in self.components:
            return False
        
        component = self.components[component_name]
        
        try:
            # Деинициализация
            if component.instance and hasattr(component.instance, 'cleanup'):
                component.instance.cleanup()
            
            component.instance = None
            component.status = ComponentStatus.NOT_FOUND
            component.error_message = None
            
            # Повторная инициализация
            discovery = self._discover_components()
            if component_name in discovery['found_components']:
                initialization = self._initialize_components()
                if component_name in initialization['initialized_components']:
                    return True
            
            return False
            
        except Exception as e:
            component.status = ComponentStatus.ERROR
            component.error_message = str(e)
            return False