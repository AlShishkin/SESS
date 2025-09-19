# -*- coding: utf-8 -*-
"""
file_manager.py - Менеджер файлов для BESS_Geometry

Этот модуль реализует принципы "single responsibility" и "separation of concerns" -
он отвечает исключительно за операции с файлами, изолируя эту логику от
пользовательского интерфейса и бизнес-логики приложения.

Образовательная ценность: Код демонстрирует, как правильно проектировать
файловые операции в приложениях обработки данных - с валидацией, обработкой
ошибок и поддержкой различных форматов.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import traceback

# Настройка логирования для отслеживания файловых операций
logger = logging.getLogger(__name__)

class FileManager:  # ← ИСПРАВЛЕНО: было BessFileManager
    """
    Менеджер файлов для работы с данными BESS
    
    Этот класс инкапсулирует всю логику работы с файлами, обеспечивая
    единообразный интерфейс для чтения, записи и валидации данных BESS.
    
    Принципы проектирования:
    - Single Responsibility: только файловые операции
    - Error Handling: graceful обработка всех возможных ошибок
    - Validation: проверка целостности данных при каждой операции
    - Logging: полное логирование для диагностики проблем
    """
    
    def __init__(self):
        """Инициализация менеджера файлов"""
        self.supported_formats = {'.json': 'BESS JSON Export'}
        self.last_opened_file = None
        self.file_statistics = {}
        logger.info("Инициализирован FileManager")  # ← ИСПРАВЛЕНО: было BessFileManager
    
    def validate_file_path(self, filepath: str) -> Tuple[bool, str]:
        """
        Валидация пути к файлу
        
        Эта функция демонстрирует принцип "fail-fast" - мы проверяем
        все возможные проблемы с файлом до попытки его открытия.
        
        Args:
            filepath: Путь к файлу для проверки
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            path = Path(filepath)
            
            # Проверка существования файла
            if not path.exists():
                return False, f"Файл не существует: {filepath}"
            
            # Проверка, что это файл, а не директория
            if not path.is_file():
                return False, f"Указанный путь не является файлом: {filepath}"
            
            # Проверка расширения файла
            if path.suffix.lower() not in self.supported_formats:
                supported = ", ".join(self.supported_formats.keys())
                return False, f"Неподдерживаемый формат файла. Поддерживаются: {supported}"
            
            # Проверка прав доступа на чтение
            if not os.access(filepath, os.R_OK):
                return False, f"Нет прав доступа для чтения файла: {filepath}"
            
            return True, "Файл прошел валидацию"
            
        except Exception as e:
            logger.error(f"Ошибка при валидации файла {filepath}: {e}")
            return False, f"Ошибка валидации: {str(e)}"
    
    def validate_bess_structure(self, data: Dict) -> Tuple[bool, str]:
        """
        Валидация структуры данных BESS
        
        Проверяет, что загруженные данные соответствуют ожидаемой
        схеме BESS и содержат все необходимые поля.
        
        Args:
            data: Словарь с данными для проверки
            
        Returns:
            Tuple[bool, str]: (is_valid, message)
        """
        try:
            # Проверка основной структуры
            required_top_level = ['project_info', 'rooms', 'openings']
            for field in required_top_level:
                if field not in data:
                    return False, f"Отсутствует обязательное поле: {field}"
            
            # Проверка информации о проекте
            project_info = data.get('project_info', {})
            required_project_fields = ['name', 'export_date']
            for field in required_project_fields:
                if field not in project_info:
                    return False, f"Отсутствует обязательное поле в project_info: {field}"
            
            # Проверка структуры помещений
            rooms = data.get('rooms', [])
            if not isinstance(rooms, list):
                return False, "Поле 'rooms' должно быть списком"
            
            for i, room in enumerate(rooms):
                if not isinstance(room, dict):
                    return False, f"Помещение {i} должно быть объектом"
                required_room_fields = ['id', 'name', 'coordinates']
                for field in required_room_fields:
                    if field not in room:
                        return False, f"Отсутствует поле '{field}' в помещении {i}"
            
            # Проверка структуры отверстий
            openings = data.get('openings', [])
            if not isinstance(openings, list):
                return False, "Поле 'openings' должно быть списком"
            
            logger.info(f"Валидация успешна: {len(rooms)} помещений, {len(openings)} отверстий")
            return True, f"Структура валидна: {len(rooms)} помещений, {len(openings)} отверстий"
            
        except Exception as e:
            logger.error(f"Ошибка при валидации структуры: {e}")
            return False, f"Ошибка валидации структуры: {str(e)}"
    
    def load_bess_file(self, filepath: str) -> Tuple[bool, Optional[Dict], str]:
        """
        Загрузка файла BESS
        
        Полный цикл загрузки файла с валидацией, обработкой ошибок
        и логированием. Демонстрирует паттерн "defensive programming".
        
        Args:
            filepath: Путь к файлу для загрузки
            
        Returns:
            Tuple[bool, Optional[Dict], str]: (success, data, message)
        """
        try:
            logger.info(f"Начинается загрузка файла: {filepath}")
            
            # Этап 1: Валидация пути к файлу
            is_valid_path, path_message = self.validate_file_path(filepath)
            if not is_valid_path:
                logger.warning(f"Валидация пути неуспешна: {path_message}")
                return False, None, path_message
            
            # Этап 2: Чтение и парсинг JSON
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.debug(f"JSON файл успешно загружен: {len(str(data))} символов")
            except json.JSONDecodeError as e:
                error_msg = f"Ошибка парсинга JSON: {str(e)}"
                logger.error(error_msg)
                return False, None, error_msg
            except UnicodeDecodeError as e:
                error_msg = f"Ошибка кодировки файла: {str(e)}"
                logger.error(error_msg)
                return False, None, error_msg
            
            # Этап 3: Валидация структуры данных BESS
            is_valid_structure, structure_message = self.validate_bess_structure(data)
            if not is_valid_structure:
                logger.warning(f"Валидация структуры неуспешна: {structure_message}")
                return False, None, structure_message
            
            # Этап 4: Сбор статистики о файле
            self.file_statistics[filepath] = self._collect_file_statistics(data, filepath)
            self.last_opened_file = filepath
            
            logger.info(f"Файл успешно загружен: {structure_message}")
            return True, data, f"Файл успешно загружен: {structure_message}"
            
        except Exception as e:
            error_msg = f"Неожиданная ошибка при загрузке файла: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return False, None, error_msg
    
    def _collect_file_statistics(self, data: Dict, filepath: str) -> Dict:
        """
        Сбор статистики о загруженном файле
        
        Собирает детальную информацию о содержимом файла,
        которая может быть полезна для анализа и диагностики.
        
        Args:
            data: Загруженные данные BESS
            filepath: Путь к файлу
            
        Returns:
            Dict: Статистика файла
        """
        try:
            stats = {
                'filepath': filepath,
                'file_size_mb': Path(filepath).stat().st_size / 1024 / 1024,
                'load_time': datetime.now().isoformat(),
                'rooms_count': len(data.get('rooms', [])),
                'openings_count': len(data.get('openings', [])),
                'project_name': data.get('project_info', {}).get('name', 'Не указано'),
                'revit_version': data.get('project_info', {}).get('revit_version', 'Не указано'),
                'export_date': data.get('project_info', {}).get('export_date', 'Не указано')
            }
            
            # Анализ типов помещений
            room_types = {}
            for room in data.get('rooms', []):
                room_type = room.get('type', 'Не определен')
                room_types[room_type] = room_types.get(room_type, 0) + 1
            stats['room_types'] = room_types
            
            # Анализ типов отверстий
            opening_types = {}
            for opening in data.get('openings', []):
                opening_type = opening.get('type', 'Не определен')
                opening_types[opening_type] = opening_types.get(opening_type, 0) + 1
            stats['opening_types'] = opening_types
            
            logger.info(f"Собрана статистика: {stats['rooms_count']} помещений, {stats['openings_count']} отверстий")
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка сбора статистики: {e}")
            return {'error': str(e)}
    
    def save_bess_file(self, data: Dict, filepath: str) -> Tuple[bool, str]:
        """
        Сохранение данных BESS в файл
        
        Args:
            data: Данные для сохранения
            filepath: Путь для сохранения
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            logger.info(f"Сохранение файла: {filepath}")
            
            # Валидация данных перед сохранением
            is_valid, validation_message = self.validate_bess_structure(data)
            if not is_valid:
                return False, f"Данные не прошли валидацию: {validation_message}"
            
            # Создание резервной копии, если файл уже существует
            path = Path(filepath)
            if path.exists():
                backup_path = path.with_suffix(f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                path.rename(backup_path)
                logger.info(f"Создана резервная копия: {backup_path}")
            
            # Сохранение с красивым форматированием
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Файл успешно сохранен: {filepath}")
            return True, f"Файл успешно сохранен: {filepath}"
            
        except Exception as e:
            error_msg = f"Ошибка при сохранении файла: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_file_statistics(self, filepath: str = None) -> Dict:
        """
        Получение статистики о файле
        
        Args:
            filepath: Путь к файлу (если None, возвращает статистику последнего загруженного)
            
        Returns:
            Dict: Статистика файла
        """
        if filepath is None:
            filepath = self.last_opened_file
        
        if filepath and filepath in self.file_statistics:
            return self.file_statistics[filepath]
        
        return {'error': 'Статистика недоступна'}


# Дополнительные классы для экосистемы файлового менеджера

class FileValidator:
    """Валидатор файлов для различных форматов"""
    
    @staticmethod
    def validate_json_syntax(filepath: str) -> Tuple[bool, str]:
        """Проверка синтаксиса JSON файла"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                json.load(f)
            return True, "JSON синтаксис корректен"
        except json.JSONDecodeError as e:
            return False, f"Ошибка JSON синтаксиса: {e}"
        except Exception as e:
            return False, f"Ошибка при проверке файла: {e}"


class ContamExporter:
    """Экспортер в формат CONTAM"""
    
    def __init__(self):
        self.export_settings = {
            'units': 'metric',
            'precision': 3,
            'include_zones': True,
            'include_openings': True
        }
    
    def export_to_contam(self, bess_data: Dict, output_path: str) -> Tuple[bool, str]:
        """
        Экспорт данных BESS в формат CONTAM
        
        Args:
            bess_data: Данные BESS для экспорта
            output_path: Путь для сохранения CONTAM файла
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        # Заглушка для будущей реализации экспорта в CONTAM
        logger.info("ContamExporter: экспорт в CONTAM пока не реализован")
        return False, "Экспорт в CONTAM находится в разработке"


# Вспомогательные классы для типизации результатов

class FileOperationResult:
    """Результат файловой операции"""
    
    def __init__(self, success: bool, message: str, data: Optional[Dict] = None):
        self.success = success
        self.message = message
        self.data = data
        self.timestamp = datetime.now()


class FileFormatInfo:
    """Информация о поддерживаемых форматах файлов"""
    
    SUPPORTED_FORMATS = {
        '.json': {
            'name': 'BESS JSON Export',
            'description': 'Основной формат для обмена данными BESS',
            'supports_import': True,
            'supports_export': True
        },
        '.contam': {
            'name': 'CONTAM Project File',
            'description': 'Формат для экспорта в CONTAM',
            'supports_import': False,
            'supports_export': True  # В будущем
        }
    }
    
    @classmethod
    def get_format_info(cls, extension: str) -> Optional[Dict]:
        """Получение информации о формате по расширению"""
        return cls.SUPPORTED_FORMATS.get(extension.lower())
    
    @classmethod
    def get_supported_import_formats(cls) -> List[str]:
        """Список форматов, поддерживающих импорт"""
        return [ext for ext, info in cls.SUPPORTED_FORMATS.items() 
                if info['supports_import']]
    
    @classmethod
    def get_supported_export_formats(cls) -> List[str]:
        """Список форматов, поддерживающих экспорт"""
        return [ext for ext, info in cls.SUPPORTED_FORMATS.items() 
                if info['supports_export']]


# Функция для обратной совместимости (если где-то использовалось старое имя)
BessFileManager = FileManager  # Алиас для обратной совместимости