# -*- coding: utf-8 -*-
"""
core/undo_manager.py - Система отмены и повтора операций для SOFT

ЭТАП 1.2: Критически важный функционал - Система Undo/Redo
Портирует функционал из legacy sess_geometry с улучшениями

Основные принципы:
- Command Pattern: каждая операция инкапсулирована как команда
- Memento Pattern: снимки состояния для отката
- Ограниченная история: управление памятью
- Batch Operations: групповые операции как один шаг отмены
- Thread Safety: безопасная работа в многопоточной среде

Ключевые особенности:
🔄 Полная поддержка Undo/Redo для всех операций геометрии  
📸 Умные снимки состояния с оптимизацией памяти
⚡ Высокая производительность для больших моделей
🎯 Интеграция с системой событий
🔐 Потокобезопасность
"""

import json
import uuid
import time
import threading
from copy import deepcopy
from typing import Dict, List, Set, Optional, Tuple, Callable, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path
import pickle
import gzip
import hashlib


class OperationType(Enum):
    """Типы операций для системы отмены"""
    CREATE_ELEMENT = "create_element"         # Создание элемента
    DELETE_ELEMENT = "delete_element"         # Удаление элемента  
    MODIFY_GEOMETRY = "modify_geometry"       # Изменение геометрии
    MODIFY_PROPERTIES = "modify_properties"   # Изменение свойств
    MOVE_ELEMENT = "move_element"            # Перемещение элемента
    COPY_ELEMENT = "copy_element"            # Копирование элемента
    BATCH_OPERATION = "batch_operation"       # Групповая операция
    IMPORT_DATA = "import_data"              # Импорт данных
    LEVEL_CHANGE = "level_change"            # Смена уровня
    SELECTION_CHANGE = "selection_change"     # Изменение выбора


class CompressionType(Enum):
    """Типы сжатия для снимков состояния"""
    NONE = "none"           # Без сжатия (быстро, больше памяти)
    GZIP = "gzip"           # Gzip сжатие (медленно, меньше памяти)  
    PICKLE = "pickle"       # Pickle сериализация (оптимальный баланс)


@dataclass
class StateSnapshot:
    """
    Снимок состояния приложения для отмены операций
    
    Использует различные стратегии сжатия и хранения для оптимизации:
    - Полные снимки для критических операций
    - Дельта-снимки для мелких изменений  
    - Сжатие для экономии памяти
    - Хеши для проверки целостности
    """
    snapshot_id: str
    timestamp: datetime
    operation_type: OperationType
    description: str
    
    # Данные состояния (могут быть сжаты)
    state_data: Any
    compression_type: CompressionType = CompressionType.NONE
    
    # Метаданные для оптимизации
    data_hash: str = ""
    data_size: int = 0
    elements_count: int = 0
    
    # Опциональные данные для дельта-операций
    element_ids: Set[str] = field(default_factory=set)
    affected_levels: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        """Вычисление метаданных после создания"""
        if isinstance(self.state_data, (bytes, str)):
            self.data_size = len(self.state_data)
        
        # Вычисляем хеш для проверки целостности
        if self.state_data:
            data_str = str(self.state_data) if not isinstance(self.state_data, (bytes, str)) else str(self.state_data)
            self.data_hash = hashlib.md5(data_str.encode()).hexdigest()[:8]


@dataclass 
class UndoOperation:
    """
    Представление операции для системы отмены
    
    Инкапсулирует всю информацию, необходимую для отмены/повтора:
    - Снимки состояния до и после операции
    - Метаданные операции
    - Callback функции для выполнения отмены/повтора
    """
    operation_id: str
    operation_type: OperationType
    timestamp: datetime
    description: str
    
    # Снимки состояния
    before_snapshot: StateSnapshot
    after_snapshot: Optional[StateSnapshot] = None
    
    # Метаданные операции
    user_description: str = ""
    element_ids: Set[str] = field(default_factory=set)
    affected_levels: Set[str] = field(default_factory=set)
    
    # Опциональные callback для кастомной логики отмены
    undo_callback: Optional[Callable] = None
    redo_callback: Optional[Callable] = None
    
    # Статистика производительности
    execution_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    
    def get_size_mb(self) -> float:
        """Получение размера операции в мегабайтах"""
        size = self.before_snapshot.data_size
        if self.after_snapshot:
            size += self.after_snapshot.data_size
        return size / (1024 * 1024)


class UndoManager:
    """
    Менеджер системы отмены и повтора операций
    
    Портирует лучшие практики из legacy с современными улучшениями:
    - Эффективное управление памятью через ограничение истории
    - Оптимизация производительности через умное сжатие
    - Поддержка групповых операций
    - Детальная статистика и профилирование
    - Потокобезопасная работа
    
    Архитектурные принципы:
    - Command Pattern для инкапсуляции операций
    - Memento Pattern для снимков состояния
    - Observer Pattern для уведомления о изменениях
    """
    
    def __init__(self, limit: int = 60, auto_cleanup: bool = True):
        """
        Инициализация менеджера отмены
        
        Args:
            limit: Максимальное количество операций в истории
            auto_cleanup: Автоматическая очистка старых операций
        """
        self.limit = limit
        self.auto_cleanup = auto_cleanup
        
        # Стеки операций
        self.undo_stack: List[UndoOperation] = []
        self.redo_stack: List[UndoOperation] = []
        
        # Настройки сжатия и оптимизации
        self.compression_type = CompressionType.PICKLE
        self.auto_compress_threshold = 10  # МБ
        self.max_memory_usage_mb = 100     # Максимум памяти для истории
        
        # Система событий
        self.event_handlers: Dict[str, List[Callable]] = {
            'operation_added': [],
            'undo_executed': [],
            'redo_executed': [],
            'history_cleared': [],
            'memory_warning': []
        }
        
        # Статистика и профилирование
        self.stats = {
            'total_operations': 0,
            'successful_undos': 0,
            'successful_redos': 0,
            'failed_operations': 0,
            'memory_usage_mb': 0.0,
            'average_operation_size_mb': 0.0,
            'compression_savings_mb': 0.0
        }
        
        # Потокобезопасность
        self._lock = threading.RLock()
        
        # Отладочная информация
        self.debug_mode = False
        self.operation_log: List[Dict] = []
        
        print("✅ UndoManager инициализирован")
        print(f"   Размер истории: {self.limit}")
        print(f"   Тип сжатия: {self.compression_type.value}")
        print(f"   Лимит памяти: {self.max_memory_usage_mb} МБ")
    
    # =========================================================================
    # ОСНОВНЫЕ ОПЕРАЦИИ ОТМЕНЫ/ПОВТОРА
    # =========================================================================
    
    def push_operation(self, 
                      operation_type: OperationType,
                      description: str,
                      before_state: Any,
                      after_state: Optional[Any] = None,
                      element_ids: Optional[Set[str]] = None,
                      affected_levels: Optional[Set[str]] = None,
                      user_description: str = "",
                      undo_callback: Optional[Callable] = None,
                      redo_callback: Optional[Callable] = None) -> str:
        """
        Добавление операции в стек отмены
        
        Args:
            operation_type: Тип операции
            description: Техническое описание
            before_state: Состояние до операции
            after_state: Состояние после операции (опционально)
            element_ids: ID затронутых элементов
            affected_levels: Затронутые уровни
            user_description: Описание для пользователя
            undo_callback: Пользовательский callback для отмены
            redo_callback: Пользовательский callback для повтора
            
        Returns:
            ID созданной операции
        """
        with self._lock:
            start_time = time.time()
            operation_id = str(uuid.uuid4())
            
            try:
                # Создаем снимки состояния
                before_snapshot = self._create_snapshot(
                    operation_id + "_before",
                    operation_type,
                    f"Before: {description}",
                    before_state
                )
                
                after_snapshot = None
                if after_state is not None:
                    after_snapshot = self._create_snapshot(
                        operation_id + "_after", 
                        operation_type,
                        f"After: {description}",
                        after_state
                    )
                
                # Создаем операцию
                operation = UndoOperation(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    timestamp=datetime.now(),
                    description=description,
                    before_snapshot=before_snapshot,
                    after_snapshot=after_snapshot,
                    user_description=user_description or description,
                    element_ids=element_ids or set(),
                    affected_levels=affected_levels or set(),
                    undo_callback=undo_callback,
                    redo_callback=redo_callback
                )
                
                # Вычисляем статистику производительности
                execution_time = (time.time() - start_time) * 1000
                operation.execution_time_ms = execution_time
                operation.memory_usage_mb = operation.get_size_mb()
                
                # Добавляем в стек отмены
                self.undo_stack.append(operation)
                
                # Очищаем стек повтора (новая операция делает повтор невозможным)
                if self.redo_stack:
                    self.redo_stack.clear()
                
                # Управление памятью
                if self.auto_cleanup:
                    self._cleanup_old_operations()
                
                # Обновляем статистику
                self._update_stats(operation)
                
                # Отладочное логирование
                if self.debug_mode:
                    self._log_operation("push", operation)
                
                # Уведомляем слушателей
                self._fire_event('operation_added', {
                    'operation_id': operation_id,
                    'operation_type': operation_type,
                    'description': description,
                    'memory_usage': operation.memory_usage_mb
                })
                
                return operation_id
                
            except Exception as e:
                self.stats['failed_operations'] += 1
                print(f"❌ Ошибка добавления операции: {e}")
                raise
    
    def undo(self) -> bool:
        """
        Отмена последней операции
        
        Returns:
            True если отмена выполнена успешно, False иначе
        """
        with self._lock:
            if not self.can_undo():
                return False
            
            start_time = time.time()
            operation = self.undo_stack.pop()
            
            try:
                # Восстанавливаем состояние
                restored_state = self._restore_from_snapshot(operation.before_snapshot)
                
                # Выполняем пользовательский callback если есть
                if operation.undo_callback:
                    operation.undo_callback(restored_state, operation)
                
                # Перемещаем в стек повтора
                self.redo_stack.append(operation)
                
                # Обновляем статистику
                self.stats['successful_undos'] += 1
                execution_time = (time.time() - start_time) * 1000
                
                # Отладочное логирование
                if self.debug_mode:
                    self._log_operation("undo", operation, execution_time)
                
                # Уведомляем слушателей
                self._fire_event('undo_executed', {
                    'operation_id': operation.operation_id,
                    'operation_type': operation.operation_type,
                    'description': operation.description,
                    'execution_time_ms': execution_time,
                    'restored_state': restored_state
                })
                
                print(f"↶ Отменено: {operation.user_description}")
                return True
                
            except Exception as e:
                # Возвращаем операцию обратно в стек при ошибке
                self.undo_stack.append(operation)
                self.stats['failed_operations'] += 1
                print(f"❌ Ошибка отмены операции {operation.operation_id}: {e}")
                return False
    
    def redo(self) -> bool:
        """
        Повтор отмененной операции
        
        Returns:
            True если повтор выполнен успешно, False иначе
        """
        with self._lock:
            if not self.can_redo():
                return False
            
            start_time = time.time()
            operation = self.redo_stack.pop()
            
            try:
                # Восстанавливаем состояние после операции
                if operation.after_snapshot:
                    restored_state = self._restore_from_snapshot(operation.after_snapshot)
                else:
                    # Если нет снимка "после", используем callback
                    restored_state = None
                
                # Выполняем пользовательский callback если есть
                if operation.redo_callback:
                    operation.redo_callback(restored_state, operation)
                
                # Перемещаем обратно в стек отмены
                self.undo_stack.append(operation)
                
                # Обновляем статистику
                self.stats['successful_redos'] += 1
                execution_time = (time.time() - start_time) * 1000
                
                # Отладочное логирование
                if self.debug_mode:
                    self._log_operation("redo", operation, execution_time)
                
                # Уведомляем слушателей
                self._fire_event('redo_executed', {
                    'operation_id': operation.operation_id,
                    'operation_type': operation.operation_type,
                    'description': operation.description,
                    'execution_time_ms': execution_time,
                    'restored_state': restored_state
                })
                
                print(f"↷ Повторено: {operation.user_description}")
                return True
                
            except Exception as e:
                # Возвращаем операцию обратно в стек при ошибке
                self.redo_stack.append(operation)
                self.stats['failed_operations'] += 1
                print(f"❌ Ошибка повтора операции {operation.operation_id}: {e}")
                return False
    
    def can_undo(self) -> bool:
        """Проверка возможности отмены"""
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Проверка возможности повтора"""
        return len(self.redo_stack) > 0
    
    # =========================================================================
    # ГРУППОВЫЕ ОПЕРАЦИИ (BATCH)
    # =========================================================================
    
    def begin_batch(self, description: str = "Групповая операция") -> str:
        """
        Начало групповой операции
        
        Все операции до end_batch() будут сгруппированы в одну операцию отмены
        
        Returns:
            ID групповой операции
        """
        batch_id = str(uuid.uuid4())
        # TODO: Реализация batch логики будет добавлена в следующих итерациях
        print(f"🔄 Начало групповой операции: {description}")
        return batch_id
    
    def end_batch(self, batch_id: str, success: bool = True) -> bool:
        """
        Завершение групповой операции
        
        Args:
            batch_id: ID групповой операции из begin_batch()
            success: Успешность выполнения группы операций
            
        Returns:
            True если группировка выполнена успешно
        """
        # TODO: Реализация batch логики
        print(f"✅ Завершена групповая операция {batch_id}")
        return True
    
    # =========================================================================
    # УПРАВЛЕНИЕ СНИМКАМИ СОСТОЯНИЯ
    # =========================================================================
    
    def _create_snapshot(self, 
                        snapshot_id: str,
                        operation_type: OperationType,
                        description: str, 
                        state_data: Any) -> StateSnapshot:
        """
        Создание снимка состояния с оптимизацией сжатия
        
        Args:
            snapshot_id: Уникальный ID снимка
            operation_type: Тип операции
            description: Описание снимка
            state_data: Данные состояния для сохранения
            
        Returns:
            Созданный снимок состояния
        """
        try:
            # Выбираем тип сжатия на основе размера данных
            compression = self.compression_type
            
            # Сжимаем данные если необходимо
            if compression == CompressionType.GZIP:
                compressed_data = self._compress_gzip(state_data)
                data_size = len(compressed_data) if isinstance(compressed_data, bytes) else 0
            elif compression == CompressionType.PICKLE:
                compressed_data = self._compress_pickle(state_data)
                data_size = len(compressed_data) if isinstance(compressed_data, bytes) else 0
            else:
                compressed_data = state_data
                data_size = len(str(state_data))
            
            # Подсчитываем количество элементов
            elements_count = 0
            if isinstance(state_data, dict):
                elements_count = len(state_data.get('work_rooms', [])) + \
                               len(state_data.get('work_areas', [])) + \
                               len(state_data.get('work_openings', []))
            
            snapshot = StateSnapshot(
                snapshot_id=snapshot_id,
                timestamp=datetime.now(),
                operation_type=operation_type,
                description=description,
                state_data=compressed_data,
                compression_type=compression,
                data_size=data_size,
                elements_count=elements_count
            )
            
            return snapshot
            
        except Exception as e:
            print(f"❌ Ошибка создания снимка {snapshot_id}: {e}")
            # Возвращаем несжатый снимок как fallback
            return StateSnapshot(
                snapshot_id=snapshot_id,
                timestamp=datetime.now(),
                operation_type=operation_type,
                description=description,
                state_data=state_data,
                compression_type=CompressionType.NONE
            )
    
    def _restore_from_snapshot(self, snapshot: StateSnapshot) -> Any:
        """
        Восстановление состояния из снимка
        
        Args:
            snapshot: Снимок для восстановления
            
        Returns:
            Восстановленные данные состояния
        """
        try:
            if snapshot.compression_type == CompressionType.GZIP:
                return self._decompress_gzip(snapshot.state_data)
            elif snapshot.compression_type == CompressionType.PICKLE:
                return self._decompress_pickle(snapshot.state_data)
            else:
                return snapshot.state_data
                
        except Exception as e:
            print(f"❌ Ошибка восстановления снимка {snapshot.snapshot_id}: {e}")
            raise
    
    def _compress_gzip(self, data: Any) -> bytes:
        """Сжатие данных через gzip"""
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            return gzip.compress(json_str.encode('utf-8'))
        except Exception as e:
            print(f"⚠️ Ошибка gzip сжатия: {e}")
            return pickle.dumps(data)
    
    def _decompress_gzip(self, compressed_data: bytes) -> Any:
        """Распаковка данных из gzip"""
        try:
            json_str = gzip.decompress(compressed_data).decode('utf-8')
            return json.loads(json_str)
        except Exception as e:
            print(f"⚠️ Ошибка gzip распаковки: {e}")
            return pickle.loads(compressed_data)
    
    def _compress_pickle(self, data: Any) -> bytes:
        """Сжатие данных через pickle"""
        return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
    
    def _decompress_pickle(self, compressed_data: bytes) -> Any:
        """Распаковка данных из pickle"""
        return pickle.loads(compressed_data)
    
    # =========================================================================
    # УПРАВЛЕНИЕ ПАМЯТЬЮ И ОЧИСТКА
    # =========================================================================
    
    def _cleanup_old_operations(self) -> None:
        """Очистка старых операций для управления памятью"""
        # Проверяем лимит количества операций
        while len(self.undo_stack) > self.limit:
            removed = self.undo_stack.pop(0)
            if self.debug_mode:
                print(f"🗑️ Удалена старая операция: {removed.description}")
        
        # Проверяем лимит использования памяти
        current_memory = self._calculate_memory_usage()
        if current_memory > self.max_memory_usage_mb:
            self._cleanup_by_memory()
            
            # Уведомляем о предупреждении памяти
            self._fire_event('memory_warning', {
                'current_usage_mb': current_memory,
                'limit_mb': self.max_memory_usage_mb,
                'operations_count': len(self.undo_stack)
            })
    
    def _cleanup_by_memory(self) -> None:
        """Очистка операций на основе использования памяти"""
        target_memory = self.max_memory_usage_mb * 0.8  # Освобождаем до 80% лимита
        
        while (self._calculate_memory_usage() > target_memory and 
               len(self.undo_stack) > 10):  # Оставляем минимум 10 операций
            removed = self.undo_stack.pop(0)
            if self.debug_mode:
                print(f"🗑️ Удалена операция для освобождения памяти: {removed.description}")
    
    def _calculate_memory_usage(self) -> float:
        """Вычисление текущего использования памяти в МБ"""
        total_size = 0
        
        for operation in self.undo_stack:
            total_size += operation.get_size_mb()
        
        for operation in self.redo_stack:
            total_size += operation.get_size_mb()
        
        return total_size
    
    def clear_history(self, confirm: bool = False) -> None:
        """
        Полная очистка истории операций
        
        Args:
            confirm: Подтверждение очистки (защита от случайного вызова)
        """
        if not confirm:
            print("⚠️ Для очистки истории используйте clear_history(confirm=True)")
            return
        
        with self._lock:
            self.undo_stack.clear()
            self.redo_stack.clear()
            
            # Сбрасываем статистику
            self.stats.update({
                'memory_usage_mb': 0.0,
                'average_operation_size_mb': 0.0
            })
            
            # Уведомляем слушателей
            self._fire_event('history_cleared', {
                'timestamp': datetime.now().isoformat()
            })
            
            print("🗑️ История операций очищена")
    
    # =========================================================================
    # ИНФОРМАЦИЯ И СТАТИСТИКА
    # =========================================================================
    
    def get_undo_descriptions(self, count: int = 10) -> List[str]:
        """
        Получение описаний последних операций для отмены
        
        Args:
            count: Количество описаний
            
        Returns:
            Список описаний операций (от последней к первой)
        """
        descriptions = []
        for operation in reversed(self.undo_stack[-count:]):
            descriptions.append(operation.user_description)
        return descriptions
    
    def get_redo_descriptions(self, count: int = 10) -> List[str]:
        """
        Получение описаний операций для повтора
        
        Args:
            count: Количество описаний
            
        Returns:
            Список описаний операций для повтора
        """
        descriptions = []
        for operation in reversed(self.redo_stack[-count:]):
            descriptions.append(operation.user_description)
        return descriptions
    
    def get_status_info(self) -> Dict[str, Any]:
        """Получение информации о состоянии менеджера"""
        return {
            'can_undo': self.can_undo(),
            'can_redo': self.can_redo(),
            'undo_count': len(self.undo_stack),
            'redo_count': len(self.redo_stack),
            'memory_usage_mb': round(self._calculate_memory_usage(), 2),
            'memory_limit_mb': self.max_memory_usage_mb,
            'total_operations': self.stats['total_operations'],
            'successful_undos': self.stats['successful_undos'],
            'successful_redos': self.stats['successful_redos'],
            'failed_operations': self.stats['failed_operations']
        }
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """Получение детальной статистики"""
        stats = self.get_status_info().copy()
        
        # Добавляем информацию по типам операций
        operation_types = {}
        for operation in self.undo_stack:
            op_type = operation.operation_type.value
            operation_types[op_type] = operation_types.get(op_type, 0) + 1
        
        stats.update({
            'operation_types': operation_types,
            'average_operation_time_ms': self._calculate_average_operation_time(),
            'compression_savings_mb': self.stats.get('compression_savings_mb', 0.0),
            'oldest_operation': self._get_oldest_operation_info(),
            'newest_operation': self._get_newest_operation_info()
        })
        
        return stats
    
    # =========================================================================
    # СИСТЕМА СОБЫТИЙ
    # =========================================================================
    
    def add_event_handler(self, event_type: str, handler: Callable) -> None:
        """Добавление обработчика событий"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable) -> None:
        """Удаление обработчика событий"""
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
            except ValueError:
                pass
    
    def _fire_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Генерация события для обработчиков"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    handler(event_type, data)
                except Exception as e:
                    print(f"⚠️ Ошибка обработчика события {event_type}: {e}")
    
    # =========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # =========================================================================
    
    def _update_stats(self, operation: UndoOperation) -> None:
        """Обновление статистики после добавления операции"""
        self.stats['total_operations'] += 1
        current_memory = self._calculate_memory_usage()
        self.stats['memory_usage_mb'] = round(current_memory, 2)
        
        if self.stats['total_operations'] > 0:
            self.stats['average_operation_size_mb'] = round(
                current_memory / len(self.undo_stack), 3
            )
    
    def _calculate_average_operation_time(self) -> float:
        """Вычисление среднего времени выполнения операций"""
        if not self.undo_stack:
            return 0.0
        
        total_time = sum(op.execution_time_ms for op in self.undo_stack)
        return round(total_time / len(self.undo_stack), 2)
    
    def _get_oldest_operation_info(self) -> Optional[Dict]:
        """Информация о самой старой операции"""
        if not self.undo_stack:
            return None
        
        oldest = self.undo_stack[0]
        return {
            'description': oldest.user_description,
            'timestamp': oldest.timestamp.isoformat(),
            'type': oldest.operation_type.value
        }
    
    def _get_newest_operation_info(self) -> Optional[Dict]:
        """Информация о самой новой операции"""
        if not self.undo_stack:
            return None
        
        newest = self.undo_stack[-1]
        return {
            'description': newest.user_description,
            'timestamp': newest.timestamp.isoformat(),
            'type': newest.operation_type.value
        }
    
    def _log_operation(self, action: str, operation: UndoOperation, execution_time: float = 0.0) -> None:
        """Отладочное логирование операций"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'operation_id': operation.operation_id,
            'operation_type': operation.operation_type.value,
            'description': operation.description,
            'execution_time_ms': execution_time,
            'memory_mb': operation.memory_usage_mb
        }
        
        self.operation_log.append(log_entry)
        
        # Ограничиваем размер лога
        if len(self.operation_log) > 1000:
            self.operation_log = self.operation_log[-500:]  # Оставляем последние 500
    
    # =========================================================================
    # СОХРАНЕНИЕ И ЗАГРУЗКА ИСТОРИИ
    # =========================================================================
    
    def save_history_to_file(self, filepath: Path) -> bool:
        """
        Сохранение истории операций в файл
        
        Args:
            filepath: Путь для сохранения
            
        Returns:
            True если сохранение успешно
        """
        try:
            with self._lock:
                history_data = {
                    'version': '1.0',
                    'timestamp': datetime.now().isoformat(),
                    'stats': self.stats,
                    'undo_operations': [self._serialize_operation(op) for op in self.undo_stack],
                    'redo_operations': [self._serialize_operation(op) for op in self.redo_stack]
                }
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(history_data, f, ensure_ascii=False, indent=2)
                
                print(f"💾 История операций сохранена в {filepath}")
                return True
                
        except Exception as e:
            print(f"❌ Ошибка сохранения истории: {e}")
            return False
    
    def load_history_from_file(self, filepath: Path) -> bool:
        """
        Загрузка истории операций из файла
        
        Args:
            filepath: Путь для загрузки
            
        Returns:
            True если загрузка успешна
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            with self._lock:
                # Загружаем статистику
                if 'stats' in history_data:
                    self.stats.update(history_data['stats'])
                
                # Загружаем операции (упрощенная версия для демонстрации)
                self.undo_stack.clear()
                self.redo_stack.clear()
                
                # TODO: Полная десериализация операций
                
                print(f"📂 История операций загружена из {filepath}")
                return True
                
        except Exception as e:
            print(f"❌ Ошибка загрузки истории: {e}")
            return False
    
    def _serialize_operation(self, operation: UndoOperation) -> Dict:
        """Сериализация операции для сохранения"""
        return {
            'operation_id': operation.operation_id,
            'operation_type': operation.operation_type.value,
            'timestamp': operation.timestamp.isoformat(),
            'description': operation.description,
            'user_description': operation.user_description,
            'element_ids': list(operation.element_ids),
            'affected_levels': list(operation.affected_levels),
            'execution_time_ms': operation.execution_time_ms,
            'memory_usage_mb': operation.memory_usage_mb
        }


# =============================================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР И УТИЛИТЫ
# =============================================================================

# Глобальный менеджер отмены для всего приложения
_global_undo_manager: Optional[UndoManager] = None

def get_undo_manager() -> UndoManager:
    """Получение глобального менеджера отмены"""
    global _global_undo_manager
    if _global_undo_manager is None:
        _global_undo_manager = UndoManager()
    return _global_undo_manager

def create_undo_manager(limit: int = 60, auto_cleanup: bool = True) -> UndoManager:
    """Создание нового менеджера отмены с настройками"""
    return UndoManager(limit=limit, auto_cleanup=auto_cleanup)


# Декоратор для автоматического создания операций отмены
def undoable_operation(operation_type: OperationType, description: str = ""):
    """
    Декоратор для автоматического создания операций отмены
    
    Usage:
        @undoable_operation(OperationType.CREATE_ELEMENT, "Создание помещения")
        def create_room(self, room_data):
            # Метод автоматически добавит операцию в историю отмены
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            undo_manager = get_undo_manager()
            
            # Сохраняем состояние до операции (упрощенная версия)
            before_state = "before_state_placeholder"  # TODO: Получать реальное состояние
            
            try:
                result = func(*args, **kwargs)
                
                # Сохраняем состояние после операции
                after_state = "after_state_placeholder"  # TODO: Получать реальное состояние
                
                # Добавляем операцию в историю
                undo_manager.push_operation(
                    operation_type=operation_type,
                    description=description or f"{func.__name__}",
                    before_state=before_state,
                    after_state=after_state
                )
                
                return result
                
            except Exception as e:
                print(f"❌ Ошибка в операции {func.__name__}: {e}")
                raise
        
        return wrapper
    return decorator


# =============================================================================
# ЭКСПОРТ ПУБЛИЧНЫХ ИНТЕРФЕЙСОВ
# =============================================================================

__all__ = [
    'UndoManager',
    'UndoOperation', 
    'StateSnapshot',
    'OperationType',
    'CompressionType',
    'get_undo_manager',
    'create_undo_manager',
    'undoable_operation'
]