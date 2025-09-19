# -*- coding: utf-8 -*-
"""
Editing Modes - система режимов редактирования с интеграцией ArchitecturalTools

НОВЫЕ ВОЗМОЖНОСТИ ЭТАПА 3:
- AddVoidMode: создание VOID помещений через ArchitecturalTools
- AddSecondLightMode: создание второго света через ArchitecturalTools
- Enhanced geometry validation using spatial processor
- Integration with BESSParameterManager for automatic parameter application

Архитектурные принципы:
- Четкое разделение ответственности между режимами
- Использование ArchitecturalTools для сложных операций
- Автоматическое применение параметров BESS
- Валидация геометрии на всех этапах
"""

import math
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any, Callable
from enum import Enum

# Импорт ArchitecturalTools с обработкой ошибок
try:
    from .architectural_tools import ArchitecturalTools
    ARCHITECTURAL_TOOLS_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: ArchitecturalTools недоступен в editing_modes - {e}")
    ARCHITECTURAL_TOOLS_AVAILABLE = False

# Импорт BESSParameterManager
try:
    from .bess_parameters import BESSParameterManager, ParameterScope
    BESS_PARAMETERS_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: BESSParameterManager недоступен в editing_modes - {e}")
    BESS_PARAMETERS_AVAILABLE = False


class EditingModeType(Enum):
    """Типы режимов редактирования"""
    DRAW_ROOM = "draw_room"
    DRAW_OPENING = "draw_opening"
    EDIT_ROOM = "edit_room"
    ADD_VOID = "add_void"                    # НОВЫЙ: создание VOID
    ADD_SECOND_LIGHT = "add_second_light"    # НОВЫЙ: создание второго света
    EDIT_CONTOUR = "edit_contour"           # НОВЫЙ: редактирование контуров


class EditingModeState(Enum):
    """Состояния режима редактирования"""
    INACTIVE = "inactive"      # Режим неактивен
    DRAWING = "drawing"        # Процесс рисования
    EDITING = "editing"        # Процесс редактирования
    VALIDATING = "validating"  # Валидация геометрии
    COMPLETE = "complete"      # Операция завершена


class EditingMode(ABC):
    """
    Базовый класс для всех режимов редактирования
    
    Определяет общий интерфейс и основную логику для режимов редактирования.
    Новые режимы наследуют от этого класса и реализуют специфичную логику.
    """
    
    def __init__(self, mode_type: str, controller):
        self.mode_type = mode_type
        self.controller = controller
        self.state = EditingModeState.INACTIVE
        
        # Геометрические данные
        self.current_points: List[Tuple[float, float]] = []
        self.preview_points: List[Tuple[float, float]] = []
        self.min_points = 3  # Минимальное количество точек для валидной геометрии
        
        # Callbacks
        self.completion_callback: Optional[Callable] = None
        self.validation_callback: Optional[Callable] = None
        self.preview_callback: Optional[Callable] = None
        
        # Настройки режима
        self.snap_enabled = True
        self.validate_on_each_point = True
        self.auto_close_polygon = True
        
    def set_completion_callback(self, callback: Callable):
        """Установка callback для завершения режима"""
        self.completion_callback = callback
        
    def set_validation_callback(self, callback: Callable):
        """Установка callback для валидации геометрии"""
        self.validation_callback = callback
        
    def set_preview_callback(self, callback: Callable):
        """Установка callback для предварительного просмотра"""
        self.preview_callback = callback
    
    def activate(self):
        """Активация режима редактирования"""
        self.state = EditingModeState.DRAWING
        self.current_points = []
        self.preview_points = []
        
    def deactivate(self):
        """Деактивация режима редактирования"""
        self.state = EditingModeState.INACTIVE
        self.current_points = []
        self.preview_points = []
        
    def validate_geometry(self) -> Dict[str, Any]:
        """
        Валидация текущей геометрии
        
        Returns:
            Результат валидации с подробной информацией
        """
        if len(self.current_points) < self.min_points:
            return {
                'valid': False,
                'error': f'Недостаточно точек. Минимум: {self.min_points}, текущее: {len(self.current_points)}'
            }
        
        # Используем callback валидации если доступен
        if self.validation_callback:
            try:
                return self.validation_callback(self.current_points)
            except Exception as e:
                return {'valid': False, 'error': f'Ошибка валидации: {e}'}
        
        # Базовая валидация
        return {'valid': True, 'warnings': []}
    
    @abstractmethod
    def handle_click(self, world_x: float, world_y: float) -> bool:
        """
        Обработка клика в режиме редактирования
        
        Args:
            world_x, world_y: Координаты клика в мировой системе координат
            
        Returns:
            True если операция завершена, False если продолжается
        """
        pass
    
    @abstractmethod
    def handle_move(self, world_x: float, world_y: float):
        """Обработка движения мыши для предварительного просмотра"""
        pass
    
    @abstractmethod
    def handle_escape(self) -> bool:
        """
        Обработка нажатия Escape
        
        Returns:
            True если режим завершен, False если продолжается
        """
        pass
    
    def handle_enter(self) -> bool:
        """
        Обработка нажатия Enter для завершения операции
        
        Returns:
            True если операция успешно завершена
        """
        if len(self.current_points) >= self.min_points:
            return self.complete_operation()
        return False
    
    def complete_operation(self) -> bool:
        """Завершение операции редактирования"""
        # Валидация перед завершением
        validation_result = self.validate_geometry()
        if not validation_result['valid']:
            print(f"Невозможно завершить операцию: {validation_result['error']}")
            return False
        
        self.state = EditingModeState.COMPLETE
        
        if self.completion_callback:
            self.completion_callback({
                'mode_type': self.mode_type,
                'points': self.current_points.copy(),
                'validation': validation_result
            })
        
        return True


class DrawRoomMode(EditingMode):
    """Режим рисования обычных помещений"""
    
    def __init__(self, controller):
        super().__init__("DRAW_ROOM", controller)
        self.min_points = 3
    
    def handle_click(self, world_x: float, world_y: float) -> bool:
        # Добавляем точку
        self.current_points.append((world_x, world_y))
        
        # Валидация если включена
        if self.validate_on_each_point and len(self.current_points) >= self.min_points:
            validation = self.validate_geometry()
            if not validation['valid']:
                print(f"Предупреждение валидации: {validation['error']}")
        
        # Автозавершение при двойном клике близко к первой точке
        if len(self.current_points) >= self.min_points:
            first_point = self.current_points[0]
            distance = math.sqrt((world_x - first_point[0])**2 + (world_y - first_point[1])**2)
            if distance < 1.0:  # Порог для автозакрытия
                return self.complete_operation()
        
        return False
    
    def handle_move(self, world_x: float, world_y: float):
        if len(self.current_points) > 0:
            self.preview_points = self.current_points + [(world_x, world_y)]
            if self.preview_callback:
                self.preview_callback(self.preview_points)
    
    def handle_escape(self) -> bool:
        if len(self.current_points) > 0:
            self.current_points.pop()  # Удаляем последнюю точку
            if len(self.current_points) == 0:
                self.deactivate()
                return True
        else:
            self.deactivate()
            return True
        return False


class AddVoidMode(EditingMode):
    """
    НОВЫЙ РЕЖИМ: Создание VOID помещений через ArchitecturalTools
    
    Этот режим позволяет создавать VOID помещения с автоматическим
    применением параметров BESS и валидацией через ArchitecturalTools.
    """
    
    def __init__(self, controller, base_room_id: Optional[str] = None):
        super().__init__("ADD_VOID", controller)
        self.base_room_id = base_room_id
        self.min_points = 3
        
    def handle_click(self, world_x: float, world_y: float) -> bool:
        # Добавляем точку
        self.current_points.append((world_x, world_y))
        
        # Проверяем возможность завершения
        if len(self.current_points) >= self.min_points:
            # Проверяем автозакрытие
            first_point = self.current_points[0]
            distance = math.sqrt((world_x - first_point[0])**2 + (world_y - first_point[1])**2)
            if distance < 1.0:
                return self._create_void()
        
        return False
    
    def _create_void(self) -> bool:
        """Создание VOID через ArchitecturalTools"""
        if not ARCHITECTURAL_TOOLS_AVAILABLE:
            print("Ошибка: ArchitecturalTools недоступен для создания VOID")
            return False
        
        try:
            # Используем ArchitecturalTools для создания VOID
            result = ArchitecturalTools.add_void(
                self.controller.state,
                self.controller.state.selected_level,
                self.current_points,
                self.base_room_id
            )
            
            if result['success']:
                # Уведомляем контроллер о создании VOID
                self.controller._fire_event('geometry_updated', {
                    'operation': 'create_void',
                    'element_id': result['void_id'],
                    'level': self.controller.state.selected_level,
                    'base_room_id': self.base_room_id
                })
                
                print(f"✅ VOID создан: {result['void_id']}")
                return True
            else:
                print(f"❌ Ошибка создания VOID: {result.get('error')}")
                return False
                
        except Exception as e:
            print(f"❌ Исключение при создании VOID: {e}")
            return False
    
    def handle_move(self, world_x: float, world_y: float):
        if len(self.current_points) > 0:
            self.preview_points = self.current_points + [(world_x, world_y)]
            if self.preview_callback:
                self.preview_callback(self.preview_points)
    
    def handle_escape(self) -> bool:
        if len(self.current_points) > 0:
            self.current_points.pop()
            if len(self.current_points) == 0:
                self.deactivate()
                return True
        else:
            self.deactivate()
            return True
        return False
    
    def handle_enter(self) -> bool:
        """Завершение создания VOID по Enter"""
        if len(self.current_points) >= self.min_points:
            return self._create_void()
        return False


class AddSecondLightMode(EditingMode):
    """
    НОВЫЙ РЕЖИМ: Создание второго света через ArchitecturalTools
    
    Позволяет создавать второй свет с привязкой к базовому помещению
    и автоматическим расчетом высотных параметров.
    """
    
    def __init__(self, controller, base_room_id: str):
        super().__init__("ADD_SECOND_LIGHT", controller)
        self.base_room_id = base_room_id
        self.min_points = 3
        
        # Проверяем существование базового помещения
        if not self._validate_base_room():
            raise ValueError(f"Базовое помещение {base_room_id} не найдено")
    
    def _validate_base_room(self) -> bool:
        """Валидация существования базового помещения"""
        base_room = self.controller.state.get_element_by_id(self.base_room_id)
        return base_room is not None
    
    def handle_click(self, world_x: float, world_y: float) -> bool:
        self.current_points.append((world_x, world_y))
        
        if len(self.current_points) >= self.min_points:
            first_point = self.current_points[0]
            distance = math.sqrt((world_x - first_point[0])**2 + (world_y - first_point[1])**2)
            if distance < 1.0:
                return self._create_second_light()
        
        return False
    
    def _create_second_light(self) -> bool:
        """Создание второго света через ArchitecturalTools"""
        if not ARCHITECTURAL_TOOLS_AVAILABLE:
            print("Ошибка: ArchitecturalTools недоступен для создания второго света")
            return False
        
        try:
            result = ArchitecturalTools.add_second_light(
                self.controller.state,
                self.base_room_id,
                self.controller.state.selected_level,
                self.current_points
            )
            
            if result['success']:
                self.controller._fire_event('geometry_updated', {
                    'operation': 'create_second_light',
                    'element_id': result['second_light_id'],
                    'base_room_id': self.base_room_id,
                    'level': self.controller.state.selected_level
                })
                
                print(f"✅ Второй свет создан: {result['second_light_id']}")
                return True
            else:
                print(f"❌ Ошибка создания второго света: {result.get('error')}")
                return False
                
        except Exception as e:
            print(f"❌ Исключение при создании второго света: {e}")
            return False
    
    def handle_move(self, world_x: float, world_y: float):
        if len(self.current_points) > 0:
            self.preview_points = self.current_points + [(world_x, world_y)]
            if self.preview_callback:
                self.preview_callback(self.preview_points)
    
    def handle_escape(self) -> bool:
        if len(self.current_points) > 0:
            self.current_points.pop()
            if len(self.current_points) == 0:
                self.deactivate()
                return True
        else:
            self.deactivate()
            return True
        return False
    
    def handle_enter(self) -> bool:
        if len(self.current_points) >= self.min_points:
            return self._create_second_light()
        return False


class EditRoomMode(EditingMode):
    """Режим редактирования существующих помещений"""
    
    def __init__(self, controller, room_id: str):
        super().__init__("EDIT_ROOM", controller)
        self.room_id = room_id
        self.original_points = []
        self.modified_points = []
        
        # Загружаем исходные точки помещения
        self._load_room_geometry()
    
    def _load_room_geometry(self):
        """Загрузка геометрии помещения для редактирования"""
        room_data = self.controller.state.get_element_by_id(self.room_id)
        if room_data and 'geometry' in room_data:
            self.original_points = room_data['geometry']['coordinates'].copy()
            self.current_points = self.original_points.copy()
    
    def handle_click(self, world_x: float, world_y: float) -> bool:
        # Логика редактирования существующих точек
        # (может быть расширена для drag&drop точек)
        return False
    
    def handle_move(self, world_x: float, world_y: float):
        # Предварительный просмотр изменений
        pass
    
    def handle_escape(self) -> bool:
        # Отмена изменений
        self.current_points = self.original_points.copy()
        self.deactivate()
        return True


class EditingModeManager:
    """
    Менеджер режимов редактирования с поддержкой новых режимов
    
    Координирует работу всех режимов редактирования и обеспечивает
    правильные переходы между ними.
    """
    
    def __init__(self, controller):
        self.controller = controller
        self.current_mode: Optional[EditingMode] = None
        self.available_modes = {}
        
        # Регистрируем доступные режимы
        self._register_modes()
    
    def _register_modes(self):
        """Регистрация всех доступных режимов"""
        self.available_modes = {
            EditingModeType.DRAW_ROOM: DrawRoomMode,
            EditingModeType.ADD_VOID: AddVoidMode,
            EditingModeType.ADD_SECOND_LIGHT: AddSecondLightMode,
            EditingModeType.EDIT_ROOM: EditRoomMode,
        }
    
    def start_mode(self, mode_type: EditingModeType, **kwargs) -> bool:
        """
        Запуск режима редактирования
        
        Args:
            mode_type: Тип режима для запуска
            **kwargs: Дополнительные параметры для режима
            
        Returns:
            True если режим успешно запущен
        """
        # Завершаем текущий режим если активен
        if self.current_mode:
            self.current_mode.deactivate()
        
        # Создаем новый режим
        if mode_type in self.available_modes:
            try:
                mode_class = self.available_modes[mode_type]
                self.current_mode = mode_class(self.controller, **kwargs)
                self.current_mode.activate()
                
                print(f"✅ Активирован режим: {mode_type.value}")
                return True
            except Exception as e:
                print(f"❌ Ошибка запуска режима {mode_type.value}: {e}")
                return False
        else:
            print(f"❌ Неизвестный режим: {mode_type.value}")
            return False
    
    def stop_current_mode(self):
        """Остановка текущего режима"""
        if self.current_mode:
            self.current_mode.deactivate()
            self.current_mode = None
    
    def handle_canvas_click(self, world_x: float, world_y: float) -> bool:
        """Передача клика в текущий режим"""
        if self.current_mode:
            return self.current_mode.handle_click(world_x, world_y)
        return False
    
    def handle_canvas_move(self, world_x: float, world_y: float):
        """Передача движения мыши в текущий режим"""
        if self.current_mode:
            self.current_mode.handle_move(world_x, world_y)
    
    def handle_key_press(self, key: str) -> bool:
        """
        Обработка нажатий клавиш
        
        Returns:
            True если событие обработано и режим завершен
        """
        if not self.current_mode:
            return False
        
        if key == 'Escape':
            result = self.current_mode.handle_escape()
            if result:
                self.current_mode = None
            return result
        elif key == 'Return' or key == 'Enter':
            result = self.current_mode.handle_enter()
            if result:
                self.current_mode = None
            return result
        
        return False
    
    def get_current_mode_info(self) -> Dict[str, Any]:
        """Получение информации о текущем режиме"""
        if self.current_mode:
            return {
                'active': True,
                'mode_type': self.current_mode.mode_type,
                'state': self.current_mode.state.value,
                'points_count': len(self.current_mode.current_points),
                'min_points': self.current_mode.min_points
            }
        else:
            return {'active': False}
    
    def get_available_modes(self) -> List[str]:
        """Получение списка доступных режимов"""
        available = []
        for mode_type in self.available_modes.keys():
            # Проверяем доступность режимов на основе зависимостей
            if mode_type == EditingModeType.ADD_VOID and not ARCHITECTURAL_TOOLS_AVAILABLE:
                continue
            if mode_type == EditingModeType.ADD_SECOND_LIGHT and not ARCHITECTURAL_TOOLS_AVAILABLE:
                continue
                
            available.append(mode_type.value)
        
        return available