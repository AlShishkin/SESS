# -*- coding: utf-8 -*-
"""
ArchitecturalTools - модуль архитектурных инструментов BESS_Geometry

Этот модуль реализует специализированные архитектурные операции:
• Создание VOID помещений с автонумерацией
• Создание второго света с привязкой к базовому помещению
• Автовычисление высот помещений
• Валидация архитектурных правил

Модуль критично важен для работы с реальными архитектурными проектами,
где требуется точное следование строительным нормам и стандартам.
"""

import uuid
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from copy import deepcopy

# Импорты с обработкой ошибок
try:
    from geometry_utils import centroid_xy, bounds, r2, polygon_area, point_in_polygon
    GEOMETRY_UTILS_AVAILABLE = True
except ImportError:
    print("Предупреждение: geometry_utils недоступен для architectural_tools")
    GEOMETRY_UTILS_AVAILABLE = False
    
    # Заглушки для базовой функциональности
    def centroid_xy(points): return (0.0, 0.0) if points else (0.0, 0.0)
    def bounds(points): return (0.0, 0.0, 100.0, 100.0) if points else (0.0, 0.0, 0.0, 0.0)
    def r2(value): return round(float(value), 2)
    def polygon_area(points): return 1.0 if len(points) >= 3 else 0.0
    def point_in_polygon(point, polygon): return False


class ArchitecturalTools:
    """
    Класс архитектурных инструментов для работы с элементами зданий
    
    Предоставляет высокоуровневые методы для создания архитектурных элементов
    с соблюдением строительных норм и автоматической валидацией.
    """
    
    @staticmethod
    def add_void(state, level: str, coords: List[Tuple[float, float]], 
                 base_room_id: Optional[str] = None, 
                 void_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Создание VOID помещения с автонумерацией
        
        VOID - это архитектурная пустота в здании (атриум, световой колодец, шахта).
        Помещения VOID не участвуют в расчетах энергопотребления, но влияют на
        воздушные потоки и освещение.
        
        Args:
            state: Состояние приложения (AppState)
            level: Уровень здания
            coords: Координаты контура VOID в метрах
            base_room_id: ID базового помещения (опционально)
            void_name: Имя VOID (автогенерируется если не указано)
            
        Returns:
            Dict с результатами операции:
            {
                'success': bool,
                'void_id': str,
                'void_data': dict,
                'warnings': list,
                'validation_results': dict
            }
        """
        result = {
            'success': False,
            'void_id': None,
            'void_data': None,
            'warnings': [],
            'validation_results': {}
        }
        
        try:
            # 1. Валидация входных данных
            validation = ArchitecturalTools._validate_void_geometry(coords, state, level)
            result['validation_results'] = validation
            
            if not validation['is_valid']:
                result['warnings'].extend(validation['errors'])
                if validation['is_critical']:
                    return result
            
            # 2. Генерация уникального ID и имени
            void_count = len([r for r in state.work_rooms 
                            if r.get('params', {}).get('BESS_Room_Type') == 'VOID'])
            
            if not void_name:
                void_name = f"VOID_{void_count + 1:03d}"
            
            # Обеспечиваем уникальность имени
            existing_names = {r.get('name', '') for r in state.work_rooms}
            original_name = void_name
            counter = 1
            while void_name in existing_names:
                void_name = f"{original_name}_{counter}"
                counter += 1
            
            void_id = state.unique_id(f"VOID_{void_count + 1}")
            
            # 3. Создание VOID элемента
            void_data = {
                'id': void_id,
                'name': void_name,
                'outer_xy_m': coords,
                'inner_loops_xy_m': [],  # VOID обычно не имеет внутренних петель
                'params': {
                    'BESS_level': level,
                    'BESS_Room_Type': 'VOID',
                    'BESS_Room_Height': '0.0',  # VOID может иметь переменную высоту
                    'BESS_Void_Category': 'GENERAL',  # ATRIUM, SHAFT, LIGHTWELL, GENERAL
                    'BESS_Area_Excluded': 'True',  # Исключается из расчета площадей
                    'BESS_Energy_Excluded': 'True',  # Исключается из энергорасчетов
                    'BESS_Created_At': datetime.now().isoformat(),
                    'BESS_Modified_At': datetime.now().isoformat()
                }
            }
            
            # 4. Связь с базовым помещением
            if base_room_id:
                base_room = next((r for r in state.work_rooms if r.get('id') == base_room_id), None)
                if base_room:
                    void_data['params']['BESS_Base_Room_Id'] = base_room_id
                    void_data['params']['BESS_Base_Room_Name'] = base_room.get('name', '')
                    
                    # Наследуем некоторые параметры от базового помещения
                    base_params = base_room.get('params', {})
                    void_data['params']['BESS_Building_Zone'] = base_params.get('BESS_Building_Zone', '')
                    void_data['params']['BESS_Fire_Zone'] = base_params.get('BESS_Fire_Zone', '')
                else:
                    result['warnings'].append(f"Базовое помещение {base_room_id} не найдено")
            
            # 5. Расчет геометрических свойств
            if GEOMETRY_UTILS_AVAILABLE:
                void_data['calculated_area_m2'] = abs(polygon_area(coords))
                void_data['centroid'] = centroid_xy(coords)
                void_data['bounds'] = bounds(coords)
                
                # Дополнительные расчеты для VOID
                area = void_data['calculated_area_m2']
                if area > 100.0:
                    void_data['params']['BESS_Void_Category'] = 'ATRIUM'
                elif area < 4.0:
                    void_data['params']['BESS_Void_Category'] = 'SHAFT'
                else:
                    void_data['params']['BESS_Void_Category'] = 'LIGHTWELL'
            
            # 6. Добавление в состояние
            state.work_rooms.append(void_data)
            
            result.update({
                'success': True,
                'void_id': void_id,
                'void_data': void_data
            })
            
            # Успех с предупреждениями
            if validation['warnings']:
                result['warnings'].extend(validation['warnings'])
            
        except Exception as e:
            result['warnings'].append(f"Ошибка создания VOID: {str(e)}")
            
        return result
    
    @staticmethod
    def add_second_light(state, base_room_id: str, level: str, 
                        coords: List[Tuple[float, float]], 
                        second_light_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Создание второго света с привязкой к базовому помещению
        
        Второй свет - это архитектурный прием, при котором помещение имеет
        увеличенную высоту (обычно в 2 или более этажей).
        
        Args:
            state: Состояние приложения (AppState)
            base_room_id: ID базового помещения на нижнем уровне
            level: Верхний уровень второго света
            coords: Координаты контура на верхнем уровне
            second_light_name: Имя элемента второго света
            
        Returns:
            Dict с результатами операции
        """
        result = {
            'success': False,
            'second_light_id': None,
            'second_light_data': None,
            'warnings': [],
            'validation_results': {},
            'base_room_updated': False
        }
        
        try:
            # 1. Поиск базового помещения
            base_room = next((r for r in state.work_rooms if r.get('id') == base_room_id), None)
            if not base_room:
                result['warnings'].append(f"Базовое помещение {base_room_id} не найдено")
                return result
            
            # 2. Валидация базового помещения
            base_level = base_room.get('params', {}).get('BESS_level', '')
            if not base_level:
                result['warnings'].append("У базового помещения не указан уровень")
                return result
            
            # 3. Определение верхнего уровня
            upper_level = ArchitecturalTools.determine_upper_level(state, level, base_level)
            if not upper_level:
                result['warnings'].append(f"Не удалось определить верхний уровень для {level}")
                return result
            
            # 4. Валидация геометрии
            validation = ArchitecturalTools._validate_second_light_geometry(
                coords, base_room.get('outer_xy_m', []), state, level
            )
            result['validation_results'] = validation
            
            if not validation['is_valid']:
                result['warnings'].extend(validation['errors'])
                if validation['is_critical']:
                    return result
            
            # 5. Генерация ID и имени
            if not second_light_name:
                base_name = base_room.get('name', 'Room')
                second_light_name = f"{base_name}_2ndLight"
            
            # Обеспечиваем уникальность
            existing_names = {r.get('name', '') for r in state.work_rooms}
            original_name = second_light_name
            counter = 1
            while second_light_name in existing_names:
                second_light_name = f"{original_name}_{counter}"
                counter += 1
            
            second_light_id = state.unique_id(f"2ndLight_{len(state.work_rooms) + 1}")
            
            # 6. Создание элемента второго света
            second_light_data = {
                'id': second_light_id,
                'name': second_light_name,
                'outer_xy_m': coords,
                'inner_loops_xy_m': [],
                'params': {
                    'BESS_level': level,
                    'BESS_Upper_level': upper_level,
                    'BESS_Room_Type': 'SECOND_LIGHT',
                    'BESS_Base_Room_Id': base_room_id,
                    'BESS_Base_Room_Name': base_room.get('name', ''),
                    'BESS_Base_Level': base_level,
                    'BESS_Area_Excluded': 'True',  # Не считается в общей площади
                    'BESS_Energy_Linked': 'True',  # Связан с базовым помещением энергетически
                    'BESS_Created_At': datetime.now().isoformat(),
                    'BESS_Modified_At': datetime.now().isoformat()
                }
            }
            
            # 7. Наследование параметров от базового помещения
            base_params = base_room.get('params', {})
            inherited_params = [
                'BESS_Building_Zone', 'BESS_Fire_Zone', 'BESS_HVAC_Zone',
                'BESS_Function_Category', 'BESS_Occupancy_Type'
            ]
            
            for param in inherited_params:
                if param in base_params:
                    second_light_data['params'][param] = base_params[param]
            
            # 8. Расчет геометрических свойств
            if GEOMETRY_UTILS_AVAILABLE:
                second_light_data['calculated_area_m2'] = abs(polygon_area(coords))
                second_light_data['centroid'] = centroid_xy(coords)
                second_light_data['bounds'] = bounds(coords)
            
            # 9. Вычисление общей высоты
            total_height = ArchitecturalTools.compute_room_height(
                base_room, state.levels, upper_level
            )
            
            if total_height > 0:
                second_light_data['params']['BESS_Total_Height'] = str(total_height)
                second_light_data['params']['BESS_Room_Height'] = str(total_height)
            
            # 10. Обновление базового помещения
            base_room['params']['BESS_Has_Second_Light'] = 'True'
            base_room['params']['BESS_Second_Light_Id'] = second_light_id
            base_room['params']['BESS_Upper_level'] = upper_level
            base_room['params']['BESS_Room_Height'] = str(total_height) if total_height > 0 else base_room['params'].get('BESS_Room_Height', '3.0')
            base_room['params']['BESS_Modified_At'] = datetime.now().isoformat()
            
            result['base_room_updated'] = True
            
            # 11. Добавление в состояние
            state.work_rooms.append(second_light_data)
            
            result.update({
                'success': True,
                'second_light_id': second_light_id,
                'second_light_data': second_light_data
            })
            
            if validation['warnings']:
                result['warnings'].extend(validation['warnings'])
                
        except Exception as e:
            result['warnings'].append(f"Ошибка создания второго света: {str(e)}")
            
        return result
    
    @staticmethod
    def compute_room_height(room: Dict[str, Any], levels: List[Dict], 
                           upper_level: Optional[str] = None) -> float:
        """
        Вычисление высоты помещения на основе уровней здания
        
        Args:
            room: Данные помещения
            levels: Список уровней здания
            upper_level: Верхний уровень (для помещений с переменной высотой)
            
        Returns:
            Высота помещения в метрах
        """
        try:
            room_params = room.get('params', {})
            room_level = room_params.get('BESS_level', '')
            
            if not room_level or not levels:
                # Возвращаем значение по умолчанию
                current_height = room_params.get('BESS_Room_Height', '3.0')
                try:
                    return float(current_height)
                except (ValueError, TypeError):
                    return 3.0
            
            # Поиск текущего уровня
            current_level_data = next((l for l in levels if l.get('name') == room_level), None)
            if not current_level_data:
                return 3.0
            
            current_elevation = float(current_level_data.get('elevation_m', 0.0))
            
            # Если указан верхний уровень (второй свет)
            if upper_level:
                upper_level_data = next((l for l in levels if l.get('name') == upper_level), None)
                if upper_level_data:
                    upper_elevation = float(upper_level_data.get('elevation_m', 0.0))
                    return r2(abs(upper_elevation - current_elevation))
            
            # Поиск следующего уровня
            current_index = next((i for i, l in enumerate(levels) if l.get('name') == room_level), -1)
            if current_index >= 0 and current_index < len(levels) - 1:
                next_level = levels[current_index + 1]
                next_elevation = float(next_level.get('elevation_m', 0.0))
                return r2(abs(next_elevation - current_elevation))
            
            # Если это верхний уровень, используем высоту по умолчанию
            default_floor_height = 3.0  # Стандартная высота этажа
            return default_floor_height
            
        except (ValueError, TypeError, KeyError) as e:
            print(f"Ошибка вычисления высоты помещения: {e}")
            return 3.0
    
    @staticmethod
    def determine_upper_level(state, target_level: str, base_level: str) -> Optional[str]:
        """
        Определение верхнего уровня для помещений с переменной высотой
        
        Args:
            state: Состояние приложения
            target_level: Целевой уровень
            base_level: Базовый (нижний) уровень
            
        Returns:
            Имя верхнего уровня или None
        """
        try:
            if not hasattr(state, 'levels') or not state.levels:
                return None
            
            # Поиск индексов уровней
            base_index = next((i for i, l in enumerate(state.levels) if l.get('name') == base_level), -1)
            target_index = next((i for i, l in enumerate(state.levels) if l.get('name') == target_level), -1)
            
            if base_index < 0 or target_index < 0:
                return None
            
            # Верхний уровень должен быть выше базового
            if target_index <= base_index:
                return None
            
            # Возвращаем следующий уровень после целевого или сам целевой
            if target_index < len(state.levels) - 1:
                return state.levels[target_index + 1].get('name')
            else:
                return target_level
                
        except (IndexError, KeyError, AttributeError):
            return None
    
    # === МЕТОДЫ ВАЛИДАЦИИ ===
    
    @staticmethod
    def _validate_void_geometry(coords: List[Tuple[float, float]], 
                              state, level: str) -> Dict[str, Any]:
        """Валидация геометрии VOID помещения"""
        result = {
            'is_valid': True,
            'is_critical': False,
            'errors': [],
            'warnings': []
        }
        
        # 1. Базовая валидация контура
        if len(coords) < 3:
            result['errors'].append("VOID должен иметь минимум 3 точки")
            result['is_valid'] = False
            result['is_critical'] = True
            return result
        
        # 2. Проверка самопересечений (если доступны утилиты)
        if GEOMETRY_UTILS_AVAILABLE:
            area = polygon_area(coords)
            if abs(area) < 0.1:  # Минимальная площадь 0.1 м²
                result['warnings'].append("VOID имеет очень маленькую площадь")
            
            if area < 0:
                result['warnings'].append("VOID имеет неправильную ориентацию (по часовой стрелке)")
        
        # 3. Проверка пересечений с существующими элементами
        existing_rooms = [r for r in state.work_rooms 
                         if r.get('params', {}).get('BESS_level') == level]
        
        overlapping_count = 0
        for room in existing_rooms:
            # Упрощенная проверка пересечений через центроиды
            if GEOMETRY_UTILS_AVAILABLE:
                void_centroid = centroid_xy(coords)
                room_coords = room.get('outer_xy_m', [])
                if room_coords and point_in_polygon(void_centroid, room_coords):
                    overlapping_count += 1
        
        if overlapping_count > 1:
            result['warnings'].append(f"VOID пересекается с {overlapping_count} помещениями")
        
        return result
    
    @staticmethod
    def _validate_second_light_geometry(coords: List[Tuple[float, float]], 
                                      base_coords: List[Tuple[float, float]],
                                      state, level: str) -> Dict[str, Any]:
        """Валидация геометрии второго света"""
        result = {
            'is_valid': True,
            'is_critical': False,
            'errors': [],
            'warnings': []
        }
        
        # 1. Базовая валидация
        if len(coords) < 3:
            result['errors'].append("Контур второго света должен иметь минимум 3 точки")
            result['is_valid'] = False
            result['is_critical'] = True
            return result
        
        # 2. Сравнение с базовым помещением
        if GEOMETRY_UTILS_AVAILABLE and base_coords:
            second_light_area = abs(polygon_area(coords))
            base_area = abs(polygon_area(base_coords))
            
            if second_light_area > base_area * 1.2:  # Превышение на 20%
                result['warnings'].append("Площадь второго света значительно больше базового помещения")
            elif second_light_area < base_area * 0.5:  # Менее 50%
                result['warnings'].append("Площадь второго света значительно меньше базового помещения")
        
        return result

    # === ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ ===
    
    @staticmethod
    def get_void_statistics(state) -> Dict[str, Any]:
        """
        Получение статистики по VOID помещениям
        
        Returns:
            Статистика по VOID элементам в проекте
        """
        void_rooms = [r for r in state.work_rooms 
                     if r.get('params', {}).get('BESS_Room_Type') == 'VOID']
        
        stats = {
            'total_count': len(void_rooms),
            'by_category': {},
            'by_level': {},
            'total_area_m2': 0.0,
            'average_area_m2': 0.0
        }
        
        for void in void_rooms:
            # По категориям
            category = void.get('params', {}).get('BESS_Void_Category', 'GENERAL')
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1
            
            # По уровням
            level = void.get('params', {}).get('BESS_level', 'Unknown')
            stats['by_level'][level] = stats['by_level'].get(level, 0) + 1
            
            # Площади
            area = void.get('calculated_area_m2', 0.0)
            stats['total_area_m2'] += area
        
        if len(void_rooms) > 0:
            stats['average_area_m2'] = r2(stats['total_area_m2'] / len(void_rooms))
        
        return stats
    
    @staticmethod
    def get_second_light_statistics(state) -> Dict[str, Any]:
        """Получение статистики по помещениям с вторым светом"""
        second_light_rooms = [r for r in state.work_rooms 
                            if r.get('params', {}).get('BESS_Room_Type') == 'SECOND_LIGHT']
        
        base_rooms_with_second_light = [r for r in state.work_rooms 
                                      if r.get('params', {}).get('BESS_Has_Second_Light') == 'True']
        
        stats = {
            'second_light_elements': len(second_light_rooms),
            'base_rooms_with_second_light': len(base_rooms_with_second_light),
            'by_level': {},
            'average_height_m': 0.0,
            'max_height_m': 0.0
        }
        
        heights = []
        for room in base_rooms_with_second_light:
            level = room.get('params', {}).get('BESS_level', 'Unknown')
            stats['by_level'][level] = stats['by_level'].get(level, 0) + 1
            
            try:
                height = float(room.get('params', {}).get('BESS_Room_Height', '3.0'))
                heights.append(height)
            except (ValueError, TypeError):
                pass
        
        if heights:
            stats['average_height_m'] = r2(sum(heights) / len(heights))
            stats['max_height_m'] = r2(max(heights))
        
        return stats