# -*- coding: utf-8 -*-
"""
ShaftManager - система управления шахтами зданий BESS_Geometry

Этот модуль обеспечивает работу с вертикальными шахтами зданий:
• Импорт шахт из базовых источников (base_shafts)
• Автоматическое клонирование шахт по уровням
• Управление параметрами BESS для шахт
• Визуализация с внутренними контурами
• Синхронизация изменений по всем уровням

Шахты - критически важные элементы для расчета воздушных потоков в зданиях,
так как они создают вертикальные связи между этажами.
"""

import uuid
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime
from copy import deepcopy

# Импорты с обработкой ошибок
try:
    from geometry_utils import centroid_xy, bounds, r2, polygon_area
    GEOMETRY_UTILS_AVAILABLE = True
except ImportError:
    print("Предупреждение: geometry_utils недоступен для shaft_manager")
    GEOMETRY_UTILS_AVAILABLE = False
    
    # Заглушки
    def centroid_xy(points): return (0.0, 0.0)
    def bounds(points): return (0.0, 0.0, 100.0, 100.0)
    def r2(value): return round(float(value), 2)
    def polygon_area(points): return 1.0 if len(points) >= 3 else 0.0


class ShaftType:
    """Типы шахт в здании"""
    ELEVATOR = "ELEVATOR"           # Лифтовая шахта
    STAIR = "STAIR"                # Лестничная клетка
    VENTILATION = "VENTILATION"    # Вентиляционная шахта
    UTILITY = "UTILITY"            # Инженерная шахта
    FIRE_ESCAPE = "FIRE_ESCAPE"    # Пожарная лестница
    SMOKE_EXHAUST = "SMOKE_EXHAUST" # Дымоудаление
    GENERAL = "GENERAL"            # Общего назначения


class ShaftStatus:
    """Статусы шахт"""
    ACTIVE = "ACTIVE"              # Активная шахта
    BLOCKED = "BLOCKED"            # Заблокирована на данном уровне
    MODIFIED = "MODIFIED"          # Изменена относительно базовой
    DELETED = "DELETED"            # Удалена с уровня


class ShaftManager:
    """
    Менеджер для работы с шахтами зданий
    
    Управляет вертикальными элементами здания, обеспечивая их корректное
    отображение и синхронизацию по всем уровням.
    """
    
    def __init__(self):
        """Инициализация менеджера шахт"""
        # Шахты, сгруппированные по уровням: {level_name: [shaft_data, ...]}
        self.shafts_by_level = {}
        
        # Базовые шахты (эталонные): {shaft_id: shaft_data}
        self.base_shafts = {}
        
        # Карта соответствий: базовая шахта -> шахты по уровням
        # {base_shaft_id: {level: shaft_id}}
        self.shaft_instances = {}
        
        # Кэш для быстрого поиска
        self._shaft_cache = {}
        self._dirty_cache = False
        
        # Настройки клонирования
        self.cloning_options = {
            'auto_prefix': True,        # Автоматический префикс BESS_
            'preserve_geometry': True,   # Сохранять геометрию
            'inherit_parameters': True,  # Наследовать параметры
            'sync_modifications': True   # Синхронизировать изменения
        }
        
        print("✅ ShaftManager инициализирован")
    
    def import_from_base(self, base_shafts: List[Dict], target_levels: List[str]) -> Dict[str, Any]:
        """
        Импорт шахт из базового источника с автоматическим клонированием по уровням
        
        Args:
            base_shafts: Список базовых шахт для импорта
            target_levels: Список уровней, на которые нужно клонировать шахты
            
        Returns:
            Отчет об импорте с результатами операции
        """
        import_report = {
            'success': True,
            'base_shafts_processed': 0,
            'total_instances_created': 0,
            'shafts_by_level': {},
            'errors': [],
            'warnings': []
        }
        
        try:
            print(f"🔄 Начало импорта шахт: {len(base_shafts)} базовых шахт на {len(target_levels)} уровней")
            
            for base_shaft in base_shafts:
                try:
                    # Валидация базовой шахты
                    validation = self._validate_base_shaft(base_shaft)
                    if not validation['is_valid']:
                        import_report['errors'].extend(validation['errors'])
                        if validation['is_critical']:
                            continue
                        else:
                            import_report['warnings'].extend(validation['warnings'])
                    
                    # Подготовка базовой шахты
                    prepared_shaft = self._prepare_base_shaft(base_shaft)
                    base_shaft_id = prepared_shaft['id']
                    
                    # Сохранение базовой шахты
                    self.base_shafts[base_shaft_id] = prepared_shaft
                    self.shaft_instances[base_shaft_id] = {}
                    
                    # Клонирование на каждый уровень
                    for level in target_levels:
                        try:
                            cloned_shaft = self._clone_shaft(prepared_shaft, level)
                            
                            # Добавление в структуры данных
                            if level not in self.shafts_by_level:
                                self.shafts_by_level[level] = []
                                import_report['shafts_by_level'][level] = 0
                            
                            self.shafts_by_level[level].append(cloned_shaft)
                            self.shaft_instances[base_shaft_id][level] = cloned_shaft['id']
                            
                            import_report['shafts_by_level'][level] += 1
                            import_report['total_instances_created'] += 1
                            
                        except Exception as e:
                            error_msg = f"Ошибка клонирования шахты {base_shaft_id} на уровень {level}: {e}"
                            import_report['errors'].append(error_msg)
                            import_report['success'] = False
                    
                    import_report['base_shafts_processed'] += 1
                    
                except Exception as e:
                    error_msg = f"Ошибка обработки базовой шахты: {e}"
                    import_report['errors'].append(error_msg)
                    import_report['success'] = False
            
            # Обновление кэша
            self._rebuild_cache()
            
            print(f"✅ Импорт завершен: {import_report['base_shafts_processed']} базовых шахт, {import_report['total_instances_created']} экземпляров")
            
            if import_report['warnings']:
                print(f"⚠️ Предупреждения: {len(import_report['warnings'])}")
            
            if import_report['errors']:
                print(f"❌ Ошибки: {len(import_report['errors'])}")
                import_report['success'] = False
                
        except Exception as e:
            import_report['errors'].append(f"Критическая ошибка импорта: {e}")
            import_report['success'] = False
            
        return import_report
    
    def _clone_shaft(self, source_shaft: Dict, level: str) -> Dict[str, Any]:
        """
        Клонирование шахты с префиксом BESS_ и адаптацией под уровень
        
        Args:
            source_shaft: Исходная шахта для клонирования
            level: Целевой уровень
            
        Returns:
            Клонированная шахта с параметрами BESS
        """
        cloned = deepcopy(source_shaft)
        
        # Генерация нового ID для клона
        base_id = source_shaft['id']
        cloned_id = f"{base_id}_{level}"
        cloned['id'] = cloned_id
        
        # Обновление имени
        original_name = source_shaft.get('name', 'Shaft')
        cloned['name'] = f"{original_name}_{level}"
        
        # Параметры BESS
        if 'params' not in cloned:
            cloned['params'] = {}
        
        params = cloned['params']
        
        # Добавление префиксов BESS_ к существующим параметрам
        if self.cloning_options['auto_prefix']:
            prefixed_params = {}
            for key, value in params.items():
                if not key.startswith('BESS_'):
                    prefixed_key = f'BESS_{key}'
                    prefixed_params[prefixed_key] = value
                else:
                    prefixed_params[key] = value
            
            cloned['params'] = prefixed_params
        
        # Обязательные BESS параметры для шахт
        cloned['params'].update({
            'BESS_level': level,
            'BESS_Element_Type': 'SHAFT',
            'BESS_Base_Shaft_Id': source_shaft['id'],
            'BESS_Shaft_Status': ShaftStatus.ACTIVE,
            'BESS_Created_At': datetime.now().isoformat(),
            'BESS_Modified_At': datetime.now().isoformat(),
            'BESS_Is_Cloned': 'True'
        })
        
        # Наследование типа шахты
        shaft_type = source_shaft.get('params', {}).get('shaft_type', ShaftType.GENERAL)
        cloned['params']['BESS_Shaft_Type'] = shaft_type
        
        # Специфичные для типа шахты параметры
        if shaft_type == ShaftType.ELEVATOR:
            cloned['params']['BESS_Elevator_Count'] = source_shaft.get('params', {}).get('elevator_count', '1')
            cloned['params']['BESS_Elevator_Capacity'] = source_shaft.get('params', {}).get('capacity', '1000')
        
        elif shaft_type == ShaftType.STAIR:
            cloned['params']['BESS_Stair_Width'] = source_shaft.get('params', {}).get('width', '1.2')
            cloned['params']['BESS_Emergency_Exit'] = source_shaft.get('params', {}).get('emergency_exit', 'True')
        
        elif shaft_type == ShaftType.VENTILATION:
            cloned['params']['BESS_Airflow_Rate'] = source_shaft.get('params', {}).get('airflow_rate', '1000')
            cloned['params']['BESS_Vent_Direction'] = source_shaft.get('params', {}).get('direction', 'EXHAUST')
        
        # Геометрические расчеты
        if GEOMETRY_UTILS_AVAILABLE and cloned.get('outer_xy_m'):
            coords = cloned['outer_xy_m']
            cloned['calculated_area_m2'] = abs(polygon_area(coords))
            cloned['centroid'] = centroid_xy(coords)
            cloned['bounds'] = bounds(coords)
        
        # Дополнительные вычисляемые параметры
        self._compute_shaft_parameters(cloned)
        
        return cloned
    
    def _prepare_base_shaft(self, shaft: Dict) -> Dict[str, Any]:
        """Подготовка базовой шахты для системы"""
        prepared = deepcopy(shaft)
        
        # Генерация ID если отсутствует
        if 'id' not in prepared or not prepared['id']:
            prepared['id'] = str(uuid.uuid4())
        
        # Обеспечение базовых полей
        if 'name' not in prepared:
            shaft_type = prepared.get('params', {}).get('shaft_type', ShaftType.GENERAL)
            prepared['name'] = f"{shaft_type}_Shaft_{len(self.base_shafts) + 1}"
        
        if 'params' not in prepared:
            prepared['params'] = {}
        
        # Базовые параметры
        prepared['params'].update({
            'is_base_shaft': 'True',
            'created_at': datetime.now().isoformat(),
            'shaft_type': prepared['params'].get('shaft_type', ShaftType.GENERAL)
        })
        
        return prepared
    
    def _compute_shaft_parameters(self, shaft: Dict):
        """Вычисление дополнительных параметров шахты"""
        if not GEOMETRY_UTILS_AVAILABLE:
            return
        
        coords = shaft.get('outer_xy_m', [])
        if not coords:
            return
        
        area = abs(polygon_area(coords))
        shaft['params']['BESS_Area_M2'] = str(r2(area))
        
        # Классификация по размеру
        if area < 2.0:
            shaft['params']['BESS_Size_Category'] = 'SMALL'
        elif area < 10.0:
            shaft['params']['BESS_Size_Category'] = 'MEDIUM'
        else:
            shaft['params']['BESS_Size_Category'] = 'LARGE'
        
        # Периметр для расчета потерь тепла
        if len(coords) >= 3:
            perimeter = 0.0
            for i in range(len(coords)):
                j = (i + 1) % len(coords)
                dx = coords[j][0] - coords[i][0]
                dy = coords[j][1] - coords[i][1]
                perimeter += (dx * dx + dy * dy) ** 0.5
            shaft['params']['BESS_Perimeter_M'] = str(r2(perimeter))
    
    def get_shafts_for_level(self, level: str) -> List[Dict[str, Any]]:
        """
        Получение всех шахт для указанного уровня
        
        Args:
            level: Имя уровня
            
        Returns:
            Список шахт на уровне
        """
        return self.shafts_by_level.get(level, [])
    
    def get_shaft_by_id(self, shaft_id: str) -> Optional[Dict[str, Any]]:
        """Поиск шахты по ID"""
        if self._dirty_cache:
            self._rebuild_cache()
        
        return self._shaft_cache.get(shaft_id)
    
    def get_base_shaft(self, base_shaft_id: str) -> Optional[Dict[str, Any]]:
        """Получение базовой шахты"""
        return self.base_shafts.get(base_shaft_id)
    
    def modify_shaft(self, shaft_id: str, modifications: Dict[str, Any]) -> bool:
        """
        Изменение параметров шахты
        
        Args:
            shaft_id: ID шахты
            modifications: Словарь изменений
            
        Returns:
            True если изменение успешно
        """
        shaft = self.get_shaft_by_id(shaft_id)
        if not shaft:
            return False
        
        try:
            # Применяем изменения
            for key, value in modifications.items():
                if key == 'params':
                    shaft['params'].update(value)
                else:
                    shaft[key] = value
            
            # Обновляем статус и время изменения
            shaft['params']['BESS_Shaft_Status'] = ShaftStatus.MODIFIED
            shaft['params']['BESS_Modified_At'] = datetime.now().isoformat()
            
            # Пересчитываем параметры если изменилась геометрия
            if 'outer_xy_m' in modifications:
                self._compute_shaft_parameters(shaft)
            
            # Синхронизация с другими экземплярами если включена
            if self.cloning_options['sync_modifications']:
                self._sync_shaft_modifications(shaft)
            
            self._dirty_cache = True
            return True
            
        except Exception as e:
            print(f"Ошибка изменения шахты {shaft_id}: {e}")
            return False
    
    def remove_shaft(self, shaft_id: str, level: Optional[str] = None) -> bool:
        """
        Удаление шахты
        
        Args:
            shaft_id: ID шахты
            level: Уровень (если None, удаляется со всех уровней)
            
        Returns:
            True если удаление успешно
        """
        removed = False
        
        if level:
            # Удаление с конкретного уровня
            if level in self.shafts_by_level:
                self.shafts_by_level[level] = [
                    s for s in self.shafts_by_level[level] 
                    if s.get('id') != shaft_id
                ]
                removed = True
        else:
            # Удаление со всех уровней
            for level_name in self.shafts_by_level:
                original_count = len(self.shafts_by_level[level_name])
                self.shafts_by_level[level_name] = [
                    s for s in self.shafts_by_level[level_name] 
                    if s.get('id') != shaft_id
                ]
                if len(self.shafts_by_level[level_name]) < original_count:
                    removed = True
        
        if removed:
            self._dirty_cache = True
        
        return removed
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики по шахтам"""
        stats = {
            'base_shafts_count': len(self.base_shafts),
            'total_instances': 0,
            'by_level': {},
            'by_type': {},
            'by_status': {},
            'by_size_category': {}
        }
        
        for level, shafts in self.shafts_by_level.items():
            stats['by_level'][level] = len(shafts)
            stats['total_instances'] += len(shafts)
            
            for shaft in shafts:
                params = shaft.get('params', {})
                
                # По типам
                shaft_type = params.get('BESS_Shaft_Type', ShaftType.GENERAL)
                stats['by_type'][shaft_type] = stats['by_type'].get(shaft_type, 0) + 1
                
                # По статусам
                status = params.get('BESS_Shaft_Status', ShaftStatus.ACTIVE)
                stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
                
                # По размерам
                size_cat = params.get('BESS_Size_Category', 'UNKNOWN')
                stats['by_size_category'][size_cat] = stats['by_size_category'].get(size_cat, 0) + 1
        
        return stats
    
    def _validate_base_shaft(self, shaft: Dict) -> Dict[str, Any]:
        """Валидация базовой шахты"""
        result = {
            'is_valid': True,
            'is_critical': False,
            'errors': [],
            'warnings': []
        }
        
        # Проверка обязательных полей
        if 'outer_xy_m' not in shaft or not shaft['outer_xy_m']:
            result['errors'].append("Отсутствует геометрия шахты (outer_xy_m)")
            result['is_critical'] = True
            result['is_valid'] = False
            return result
        
        coords = shaft['outer_xy_m']
        if len(coords) < 3:
            result['errors'].append("Контур шахты должен содержать минимум 3 точки")
            result['is_critical'] = True
            result['is_valid'] = False
            return result
        
        # Проверка площади
        if GEOMETRY_UTILS_AVAILABLE:
            area = abs(polygon_area(coords))
            if area < 0.5:
                result['warnings'].append("Очень маленькая площадь шахты (< 0.5 м²)")
            elif area > 100.0:
                result['warnings'].append("Очень большая площадь шахты (> 100 м²)")
        
        # Проверка параметров
        params = shaft.get('params', {})
        shaft_type = params.get('shaft_type')
        if shaft_type and shaft_type not in [ShaftType.ELEVATOR, ShaftType.STAIR, 
                                           ShaftType.VENTILATION, ShaftType.UTILITY,
                                           ShaftType.FIRE_ESCAPE, ShaftType.SMOKE_EXHAUST,
                                           ShaftType.GENERAL]:
            result['warnings'].append(f"Неизвестный тип шахты: {shaft_type}")
        
        return result
    
    def _sync_shaft_modifications(self, modified_shaft: Dict):
        """Синхронизация изменений с другими экземплярами шахты"""
        base_shaft_id = modified_shaft.get('params', {}).get('BESS_Base_Shaft_Id')
        if not base_shaft_id or base_shaft_id not in self.shaft_instances:
            return
        
        # Получаем параметры для синхронизации (исключаем уровне-специфичные)
        sync_params = {}
        exclude_keys = {'BESS_level', 'BESS_Created_At', 'BESS_Modified_At', 'id', 'name'}
        
        for key, value in modified_shaft.get('params', {}).items():
            if key not in exclude_keys:
                sync_params[key] = value
        
        # Синхронизируем с другими экземплярами
        instances = self.shaft_instances[base_shaft_id]
        for level, shaft_id in instances.items():
            if shaft_id != modified_shaft['id']:  # Не синхронизируем с самим собой
                target_shaft = self.get_shaft_by_id(shaft_id)
                if target_shaft:
                    target_shaft['params'].update(sync_params)
                    target_shaft['params']['BESS_Modified_At'] = datetime.now().isoformat()
    
    def _rebuild_cache(self):
        """Перестроение кэша для быстрого поиска"""
        self._shaft_cache.clear()
        
        for level, shafts in self.shafts_by_level.items():
            for shaft in shafts:
                shaft_id = shaft.get('id')
                if shaft_id:
                    self._shaft_cache[shaft_id] = shaft
        
        self._dirty_cache = False
        
    def export_to_state(self, state) -> int:
        """
        Экспорт шахт в состояние приложения как специальные areas
        
        Args:
            state: Состояние приложения (AppState)
            
        Returns:
            Количество экспортированных шахт
        """
        exported_count = 0
        
        try:
            for level, shafts in self.shafts_by_level.items():
                for shaft in shafts:
                    # Конвертируем шахту в формат area для совместимости
                    area_data = {
                        'id': shaft['id'],
                        'name': shaft['name'],
                        'outer_xy_m': shaft.get('outer_xy_m', []),
                        'inner_loops_xy_m': shaft.get('inner_loops_xy_m', []),
                        'params': shaft.get('params', {})
                    }
                    
                    # Добавляем маркер что это шахта
                    area_data['params']['BESS_Is_Shaft'] = 'True'
                    
                    # Проверяем, не существует ли уже такой элемент
                    existing = next((a for a in state.work_areas if a.get('id') == shaft['id']), None)
                    if not existing:
                        state.work_areas.append(area_data)
                        exported_count += 1
                    
            print(f"✅ Экспортировано {exported_count} шахт в состояние приложения")
            
        except Exception as e:
            print(f"Ошибка экспорта шахт: {e}")
        
        return exported_count