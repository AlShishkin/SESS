# -*- coding: utf-8 -*-
"""
Контроллеры системы BESS_Geometry (Controllers Package)

Этот пакет реализует паттерн Model-View-Controller (MVC), где контроллеры
служат связующим звеном между пользовательским интерфейсом (View) и бизнес-логикой (Model).

Контроллеры отвечают за:
- Обработку пользовательского ввода и событий UI
- Координацию взаимодействия между различными компонентами
- Управление состоянием приложения и переходами между режимами
- Валидацию пользовательских действий перед передачей в бизнес-логику
- Трансляцию результатов обработки обратно в интерфейс

Архитектурные принципы:
- Тонкие контроллеры: основная логика остается в core, контроллеры только координируют
- Слабое связывание: контроллеры общаются с UI и core через интерфейсы
- Тестируемость: контроллеры легко тестировать независимо от UI
- Расширяемость: легко добавлять новые контроллеры для новой функциональности

Планируемые контроллеры:
- MainController: главный контроллер приложения, управляет общим состоянием
- CanvasController: специализированный контроллер для работы с геометрическим canvas
- FileController: контроллер для операций с файлами (загрузка, сохранение, экспорт)
- GeometryController: контроллер для геометрических операций и редактирования
"""

# Пока контроллеры не созданы, импорты закомментированы
# Это позволит избежать ошибок импорта на данном этапе

# from .main_controller import MainController
# from .canvas_controller import CanvasController  
# from .file_controller import FileController
# from .geometry_controller import GeometryController

# Публичный API пакета контроллеров
# Будет заполнен по мере создания контроллеров
__all__ = [
    # 'MainController',
    # 'CanvasController', 
    # 'FileController',
    # 'GeometryController',
]

# Метаинформация о пакете контроллеров
__version__ = '1.0.0-dev'  # dev указывает, что пакет находится в разработке
__author__ = 'BESS_Geometry Development Team'
__description__ = 'MVC Controllers for building geometry application'

# Базовые интерфейсы и абстрактные классы для контроллеров
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable

class BaseController(ABC):
    """
    Базовый абстрактный класс для всех контроллеров системы
    
    Этот класс определяет общий интерфейс, который должны реализовать
    все контроллеры. Он обеспечивает единообразность архитектуры
    и упрощает добавление новых контроллеров.
    """
    
    def __init__(self, name: str):
        """
        Инициализация базового контроллера
        
        Args:
            name: Имя контроллера для логирования и отладки
        """
        self.name = name
        self.is_active = False
        self.event_handlers = {}
        
    @abstractmethod
    def initialize(self) -> bool:
        """
        Инициализация контроллера
        
        Этот метод должен быть переопределен в каждом контроллере
        для выполнения специфичной инициализации
        
        Returns:
            bool: True если инициализация прошла успешно
        """
        pass
    
    @abstractmethod
    def cleanup(self):
        """
        Очистка ресурсов контроллера
        
        Вызывается при завершении работы или деактивации контроллера
        """
        pass
    
    def activate(self):
        """Активация контроллера"""
        self.is_active = True
        
    def deactivate(self):
        """Деактивация контроллера""" 
        self.is_active = False
        
    def register_event_handler(self, event_name: str, handler: Callable):
        """
        Регистрация обработчика события
        
        Args:
            event_name: Имя события
            handler: Функция-обработчик события
        """
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []
        self.event_handlers[event_name].append(handler)
        
    def emit_event(self, event_name: str, data: Any = None):
        """
        Генерация события
        
        Args:
            event_name: Имя события
            data: Данные события
        """
        if event_name in self.event_handlers:
            for handler in self.event_handlers[event_name]:
                try:
                    handler(data)
                except Exception as e:
                    print(f"Ошибка в обработчике события {event_name}: {e}")

class ControllerManager:
    """
    Менеджер контроллеров
    
    Этот класс управляет жизненным циклом всех контроллеров в системе,
    обеспечивает их координацию и обмен сообщениями между ними
    """
    
    def __init__(self):
        self.controllers = {}
        self.active_controllers = set()
        
    def register_controller(self, controller: BaseController):
        """
        Регистрация нового контроллера
        
        Args:
            controller: Экземпляр контроллера для регистрации
        """
        self.controllers[controller.name] = controller
        
    def get_controller(self, name: str) -> Optional[BaseController]:
        """
        Получение контроллера по имени
        
        Args:
            name: Имя контроллера
            
        Returns:
            BaseController или None если контроллер не найден
        """
        return self.controllers.get(name)
        
    def initialize_all(self) -> bool:
        """
        Инициализация всех зарегистрированных контроллеров
        
        Returns:
            bool: True если все контроллеры инициализированы успешно
        """
        success = True
        for controller in self.controllers.values():
            if not controller.initialize():
                print(f"Ошибка инициализации контроллера {controller.name}")
                success = False
        return success
        
    def cleanup_all(self):
        """Очистка всех контроллеров"""
        for controller in self.controllers.values():
            controller.cleanup()

# Глобальный экземпляр менеджера контроллеров
# Будет использоваться во всем приложении для управления контроллерами
controller_manager = ControllerManager()

def get_controller_manager() -> ControllerManager:
    """
    Получение глобального менеджера контроллеров
    
    Returns:
        ControllerManager: Глобальный экземпляр менеджера
    """
    return controller_manager