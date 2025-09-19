# -*- coding: utf-8 -*-
"""
app.py - Legacy/Fallback приложение BESS_Geometry

Этот файл содержит упрощенную версию приложения, которая служит "страховочной сеткой"
когда современная архитектура недоступна. Код демонстрирует важный принцип
программной инженерии: "всегда имейте план B".

Образовательная ценность: Этот подход показывает, как в профессиональной разработке
создаются системы с множественными уровнями отказоустойчивости. Даже если основная
функциональность недоступна, пользователь получает базовую работающую программу.

Архитектурные принципы:
- Минимальные зависимости (только стандартная библиотека Python)
- Простая, понятная структура кода
- Четкие сообщения об ограничениях функциональности
- Graceful degradation (корректная деградация возможностей)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
from pathlib import Path
from datetime import datetime
import traceback

class App:
    """
    Legacy приложение BESS_Geometry (упрощенная версия)
    
    Этот класс представляет собой "минимально жизнеспособный продукт" (MVP)
    для работы с файлами BESS. Он демонстрирует, как можно создать полезное
    приложение даже с ограниченными ресурсами.
    
    Философия дизайна: "Лучше простое работающее решение, чем сложное нерабочее"
    """
    
    def __init__(self):
        """
        Инициализация legacy приложения
        
        В отличие от современной версии, здесь мы используем максимально простой
        подход - создаем все компоненты в конструкторе без сложной проверки
        зависимостей. Это демонстрирует trade-off между простотой и гибкостью.
        """
        print("🔧 Инициализация Legacy приложения BESS_Geometry")
        
        # Создаем главное окно
        self.root = tk.Tk()
        self.root.title("BESS_Geometry (Legacy Mode)")
        self.root.geometry("1000x700")
        self.root.minsize(600, 400)
        
        # Простые переменные состояния
        self.current_file = None
        self.file_data = None
        
        # Создаем интерфейс
        self._create_interface()
        
        # Настраиваем обработку закрытия
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        print("✅ Legacy приложение готово к работе")
    
    def _create_interface(self):
        """
        Создание пользовательского интерфейса legacy приложения
        
        Здесь мы используем принцип "functional sufficiency" - создаем интерфейс,
        который обеспечивает основную функциональность без излишней сложности.
        Каждый элемент интерфейса имеет четкое назначение.
        """
        # Создаем меню (базовое, но функциональное)
        self._create_menu()
        
        # Создаем панель с предупреждением о режиме
        self._create_warning_panel()
        
        # Создаем основную рабочую область
        self._create_main_area()
        
        # Создаем строку состояния
        self._create_status_bar()
    
    def _create_menu(self):
        """Создание простого, но эффективного меню"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Меню "Файл" - только самое необходимое
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Открыть JSON...", command=self._open_file)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self._on_closing)
        
        # Меню "Справка"
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self._show_about)
        help_menu.add_command(label="Ограничения Legacy режима", command=self._show_limitations)
    
    def _create_warning_panel(self):
        """
        Создание панели предупреждения о режиме работы
        
        Этот элемент демонстрирует важный принцип UX дизайна: всегда информируйте
        пользователя о контексте работы программы. Пользователь должен понимать,
        в каком режиме работает приложение и какие у него ограничения.
        """
        warning_frame = tk.Frame(self.root, bg='#fff3cd', relief=tk.RAISED, bd=1)
        warning_frame.pack(fill=tk.X, padx=5, pady=2)
        
        warning_label = tk.Label(
            warning_frame,
            text="⚠️ LEGACY РЕЖИМ: Работает упрощенная версия приложения с ограниченной функциональностью",
            bg='#fff3cd',
            fg='#856404',
            font=('Arial', 9, 'bold'),
            pady=5
        )
        warning_label.pack()
        
        detail_label = tk.Label(
            warning_frame,
            text="Доступен только просмотр JSON файлов. Для полной функциональности установите все компоненты системы.",
            bg='#fff3cd',
            fg='#856404',
            font=('Arial', 8),
            pady=2
        )
        detail_label.pack()
    
    def _create_main_area(self):
        """
        Создание основной рабочей области
        
        В legacy режиме мы используем простую, но эффективную структуру:
        текстовая область с прокруткой для отображения содержимого файлов.
        Это демонстрирует принцип "form follows function" - форма следует функции.
        """
        # Создаем notebook для организации информации
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Вкладка "Содержимое файла"
        self.content_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.content_frame, text="Содержимое файла")
        
        # Текстовая область для отображения данных
        self.content_text = scrolledtext.ScrolledText(
            self.content_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),
            state=tk.DISABLED,
            bg='#f8f9fa'
        )
        self.content_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Вкладка "Анализ структуры"
        self.analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analysis_frame, text="Анализ структуры")
        
        self.analysis_text = scrolledtext.ScrolledText(
            self.analysis_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),
            state=tk.DISABLED,
            bg='#f0f8ff'
        )
        self.analysis_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Показываем приветственное сообщение
        self._show_welcome_message()
    
    def _create_status_bar(self):
        """Создание информативной строки состояния"""
        self.status_bar = tk.Label(
            self.root,
            text="Готов к работе - откройте JSON файл",
            relief=tk.SUNKEN,
            anchor=tk.W,
            padx=10,
            pady=3,
            bg='#f0f0f0'
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _show_welcome_message(self):
        """
        Отображение приветственного сообщения
        
        Хорошее приложение всегда "говорит" с пользователем, объясняя,
        что происходит и что нужно делать дальше. Это особенно важно
        в legacy режиме, когда функциональность ограничена.
        """
        welcome_text = """
╔══════════════════════════════════════════════════════════════╗
║                 BESS_GEOMETRY - LEGACY РЕЖИМ                ║
╚══════════════════════════════════════════════════════════════╝

Добро пожаловать в упрощенную версию BESS_Geometry!

🎯 ЧТО МОЖНО ДЕЛАТЬ В LEGACY РЕЖИМЕ:
• Открывать и просматривать JSON файлы экспорта BESS
• Анализировать структуру геометрических данных
• Получать статистику по элементам (помещения, отверстия)
• Просматривать метаданные проектов Revit

📋 КАК НАЧАТЬ РАБОТУ:
1. Нажмите "Файл" → "Открыть JSON..."
2. Выберите файл экспорта BESS из Revit (формат .json)
3. Изучите содержимое на вкладках

⚠️  ОГРАНИЧЕНИЯ LEGACY РЕЖИМА:
• Нет графического отображения планов
• Нет возможности редактирования
• Ограниченные возможности экспорта
• Упрощенная валидация данных

💡 ДЛЯ ПОЛНОЙ ФУНКЦИОНАЛЬНОСТИ:
Установите все компоненты системы BESS_Geometry для доступа
к современному интерфейсу с графическим редактором и полным
набором инструментов анализа.

Откройте JSON файл для начала работы!
        """
        
        self.content_text.config(state=tk.NORMAL)
        self.content_text.insert(tk.END, welcome_text)
        self.content_text.config(state=tk.DISABLED)
    
    def _open_file(self):
        """
        Открытие и обработка JSON файла
        
        Этот метод демонстрирует принцип "robust input handling" - как правильно
        обрабатывать пользовательский ввод с множественными уровнями проверки
        и информативными сообщениями об ошибках.
        """
        try:
            # Показываем диалог выбора файла
            filepath = filedialog.askopenfilename(
                title="Открыть JSON файл BESS",
                defaultextension=".json",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("BESS Export", "*.json"),
                    ("All files", "*.*")
                ],
                initialdir=os.path.expanduser("~/Desktop")
            )
            
            if not filepath:
                return
            
            # Обновляем статус
            self.status_bar.config(text="Загрузка файла...")
            self.root.update()
            
            # Загружаем и парсим JSON
            with open(filepath, 'r', encoding='utf-8') as f:
                self.file_data = json.load(f)
            
            self.current_file = filepath
            
            # Обновляем заголовок окна
            filename = os.path.basename(filepath)
            self.root.title(f"BESS_Geometry (Legacy) - {filename}")
            
            # Отображаем содержимое
            self._display_file_content()
            self._analyze_file_structure()
            
            # Обновляем статус
            self.status_bar.config(text=f"Загружен: {filename}")
            
            # Показываем сообщение об успехе
            messagebox.showinfo(
                "Файл загружен",
                f"JSON файл успешно загружен:\n{filename}\n\nПерейдите на вкладки для просмотра данных."
            )
            
        except json.JSONDecodeError as e:
            # Специфическая ошибка JSON
            error_msg = f"Ошибка формата JSON:\n{str(e)}\n\nФайл поврежден или имеет неправильный формат."
            messagebox.showerror("Ошибка формата", error_msg)
            self.status_bar.config(text="Ошибка: неправильный формат JSON")
            
        except FileNotFoundError:
            # Файл не найден
            messagebox.showerror("Ошибка", "Файл не найден или недоступен.")
            self.status_bar.config(text="Ошибка: файл не найден")
            
        except PermissionError:
            # Нет прав доступа
            messagebox.showerror("Ошибка", "Недостаточно прав для чтения файла.")
            self.status_bar.config(text="Ошибка: нет прав доступа")
            
        except Exception as e:
            # Все остальные ошибки
            error_msg = f"Неожиданная ошибка при загрузке файла:\n{str(e)}"
            messagebox.showerror("Ошибка", error_msg)
            self.status_bar.config(text="Ошибка загрузки файла")
            print(f"Детали ошибки: {traceback.format_exc()}")
    
    def _display_file_content(self):
        """
        Отображение содержимого файла в удобочитаемом формате
        
        Этот метод показывает, как можно представить сложные данные в понятном
        для пользователя виде. Мы используем иерархическое отображение с
        подсветкой важных разделов.
        """
        if not self.file_data:
            return
        
        self.content_text.config(state=tk.NORMAL)
        self.content_text.delete(1.0, tk.END)
        
        try:
            # Формируем структурированное представление данных
            content_lines = []
            content_lines.append("СОДЕРЖИМОЕ JSON ФАЙЛА BESS")
            content_lines.append("=" * 60)
            content_lines.append("")
            
            # Основная информация
            version = self.file_data.get('version', 'Неизвестна')
            content_lines.append(f"Версия формата: {version}")
            content_lines.append("")
            
            # Метаданные проекта
            meta = self.file_data.get('meta', {})
            if meta:
                content_lines.append("📋 МЕТАДАННЫЕ ПРОЕКТА:")
                content_lines.append(f"   Название документа: {meta.get('doc_title', 'Не указано')}")
                content_lines.append(f"   Путь к файлу: {meta.get('doc_full_path', 'Не указан')}")
                content_lines.append(f"   Время экспорта: {meta.get('export_time', 'Не указано')}")
                content_lines.append(f"   Директория: {meta.get('doc_dir', 'Не указана')}")
                content_lines.append("")
            
            # Уровни
            levels = self.file_data.get('levels', [])
            if levels:
                content_lines.append(f"🏢 УРОВНИ ({len(levels)}):")
                for level in levels:
                    name = level.get('name', 'Без названия')
                    elevation_ft = level.get('elevation_ft', 0)
                    elevation_m = level.get('elevation_m', 0)
                    content_lines.append(f"   • {name}: {elevation_m:.2f} м ({elevation_ft:.2f} фт)")
                content_lines.append("")
            
            # Помещения
            rooms = self.file_data.get('rooms', [])
            if rooms:
                content_lines.append(f"🏠 ПОМЕЩЕНИЯ ({len(rooms)}):")
                
                # Показываем первые 20 помещений
                for i, room in enumerate(rooms[:20]):
                    name = room.get('name', f'Помещение {i+1}')
                    level = room.get('params', {}).get('BESS_level', 'Неизвестно')
                    area = room.get('area_m2', 0)
                    content_lines.append(f"   • {name} (Уровень: {level}) - {area:.1f} м²")
                
                if len(rooms) > 20:
                    content_lines.append(f"   ... и еще {len(rooms) - 20} помещений")
                content_lines.append("")
            
            # Отверстия
            openings = self.file_data.get('openings', [])
            if openings:
                content_lines.append(f"🚪 ОТВЕРСТИЯ ({len(openings)}):")
                
                # Группируем по типам
                types_count = {}
                for opening in openings:
                    opening_type = opening.get('category', 'Неизвестно')
                    types_count[opening_type] = types_count.get(opening_type, 0) + 1
                
                for opening_type, count in sorted(types_count.items()):
                    content_lines.append(f"   • {opening_type}: {count}")
                
                content_lines.append("")
                
                # Показываем примеры отверстий
                content_lines.append("   Примеры:")
                for i, opening in enumerate(openings[:10]):
                    name = opening.get('name', f'Отверстие {i+1}')
                    opening_type = opening.get('category', 'Неизвестно')
                    level = opening.get('level', 'Неизвестно')
                    content_lines.append(f"     - {name} ({opening_type}, {level})")
                
                if len(openings) > 10:
                    content_lines.append(f"     ... и еще {len(openings) - 10} отверстий")
                content_lines.append("")
            
            # Дополнительная информация
            areas = self.file_data.get('areas', [])
            if areas:
                content_lines.append(f"📐 ОБЛАСТИ: {len(areas)}")
                content_lines.append("")
            
            content_lines.append("💡 ПОДСКАЗКА:")
            content_lines.append("   Перейдите на вкладку 'Анализ структуры' для получения")
            content_lines.append("   детальной технической информации о файле.")
            
            # Отображаем текст
            self.content_text.insert(tk.END, "\n".join(content_lines))
            
        except Exception as e:
            error_text = f"Ошибка при отображении содержимого:\n{str(e)}\n\nСырые данные JSON:\n\n"
            error_text += json.dumps(self.file_data, indent=2, ensure_ascii=False)
            self.content_text.insert(tk.END, error_text)
        
        self.content_text.config(state=tk.DISABLED)
    
    def _analyze_file_structure(self):
        """
        Анализ структуры файла для технических пользователей
        
        Этот метод демонстрирует принцип "progressive disclosure" - предоставляем
        базовую информацию для обычных пользователей и детальный технический
        анализ для экспертов.
        """
        if not self.file_data:
            return
        
        self.analysis_text.config(state=tk.NORMAL)
        self.analysis_text.delete(1.0, tk.END)
        
        try:
            analysis_lines = []
            analysis_lines.append("ТЕХНИЧЕСКИЙ АНАЛИЗ СТРУКТУРЫ ФАЙЛА")
            analysis_lines.append("=" * 60)
            analysis_lines.append(f"Время анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            analysis_lines.append("")
            
            # Общий анализ JSON структуры
            analysis_lines.append("📊 ОБЩАЯ СТАТИСТИКА:")
            analysis_lines.append(f"   Размер JSON: {len(json.dumps(self.file_data))} символов")
            analysis_lines.append(f"   Корневых элементов: {len(self.file_data)}")
            analysis_lines.append(f"   Ключи верхнего уровня: {list(self.file_data.keys())}")
            analysis_lines.append("")
            
            # Анализ версии и совместимости
            version = self.file_data.get('version', 'Неизвестна')
            analysis_lines.append("🔖 ВЕРСИЯ И СОВМЕСТИМОСТЬ:")
            analysis_lines.append(f"   Версия формата: {version}")
            
            if version.startswith('bess-export'):
                analysis_lines.append("   ✅ Корректный формат BESS экспорта")
                if version == 'bess-export-3.0':
                    analysis_lines.append("   ✅ Последняя версия формата")
                else:
                    analysis_lines.append("   ⚠️ Устаревшая версия формата")
            else:
                analysis_lines.append("   ❌ Неизвестный или некорректный формат")
            analysis_lines.append("")
            
            # Детальный анализ каждого раздела
            sections_info = [
                ('meta', 'Метаданные проекта'),
                ('levels', 'Уровни здания'),
                ('rooms', 'Помещения'),
                ('openings', 'Отверстия'),
                ('areas', 'Области')
            ]
            
            for section_key, section_name in sections_info:
                section_data = self.file_data.get(section_key)
                analysis_lines.append(f"📁 {section_name.upper()} ('{section_key}'):")
                
                if section_data is None:
                    analysis_lines.append("   ❌ Отсутствует")
                elif isinstance(section_data, list):
                    analysis_lines.append(f"   📊 Тип: Массив, элементов: {len(section_data)}")
                    if section_data:
                        # Анализируем структуру первого элемента
                        first_item = section_data[0]
                        if isinstance(first_item, dict):
                            keys = list(first_item.keys())
                            analysis_lines.append(f"   🔑 Поля элемента: {keys[:10]}{'...' if len(keys) > 10 else ''}")
                elif isinstance(section_data, dict):
                    analysis_lines.append(f"   📊 Тип: Объект, ключей: {len(section_data)}")
                    keys = list(section_data.keys())
                    analysis_lines.append(f"   🔑 Ключи: {keys[:10]}{'...' if len(keys) > 10 else ''}")
                else:
                    analysis_lines.append(f"   📊 Тип: {type(section_data).__name__}")
                
                analysis_lines.append("")
            
            # Проверка целостности данных
            analysis_lines.append("🔍 ПРОВЕРКА ЦЕЛОСТНОСТИ:")
            
            integrity_issues = []
            
            # Проверяем обязательные поля
            required_fields = ['version', 'meta']
            for field in required_fields:
                if field not in self.file_data:
                    integrity_issues.append(f"Отсутствует обязательное поле: {field}")
            
            # Проверяем структуру помещений
            rooms = self.file_data.get('rooms', [])
            if rooms:
                rooms_without_geometry = 0
                for room in rooms:
                    if 'outer_xy_m' not in room:
                        rooms_without_geometry += 1
                
                if rooms_without_geometry > 0:
                    integrity_issues.append(f"Помещений без геометрии: {rooms_without_geometry}")
            
            # Проверяем связность данных
            openings = self.file_data.get('openings', [])
            if openings and rooms:
                room_names = {room.get('name', '') for room in rooms}
                orphaned_openings = 0
                
                for opening in openings:
                    from_room = opening.get('from_room', '')
                    to_room = opening.get('to_room', '')
                    if from_room and from_room not in room_names:
                        orphaned_openings += 1
                    if to_room and to_room not in room_names:
                        orphaned_openings += 1
                
                if orphaned_openings > 0:
                    integrity_issues.append(f"Отверстий с некорректными связями: {orphaned_openings}")
            
            if integrity_issues:
                analysis_lines.append("   ⚠️ ОБНАРУЖЕНЫ ПРОБЛЕМЫ:")
                for issue in integrity_issues:
                    analysis_lines.append(f"     • {issue}")
            else:
                analysis_lines.append("   ✅ Структура данных корректна")
            
            analysis_lines.append("")
            
            # Рекомендации по использованию
            analysis_lines.append("💡 РЕКОМЕНДАЦИИ:")
            
            if version != 'bess-export-3.0':
                analysis_lines.append("   • Рекомендуется обновить плагин BESS до последней версии")
            
            if integrity_issues:
                analysis_lines.append("   • Проверьте исходный файл Revit на корректность")
                analysis_lines.append("   • Повторите экспорт после исправления проблем")
            
            total_elements = len(rooms) + len(openings) + len(self.file_data.get('areas', []))
            if total_elements > 1000:
                analysis_lines.append("   • Большой объем данных - рекомендуется использование")
                analysis_lines.append("     полной версии BESS_Geometry для обработки")
            
            analysis_lines.append("   • Для полного анализа используйте современную версию приложения")
            
            # Отображаем анализ
            self.analysis_text.insert(tk.END, "\n".join(analysis_lines))
            
        except Exception as e:
            error_text = f"Ошибка анализа структуры:\n{str(e)}\n\n{traceback.format_exc()}"
            self.analysis_text.insert(tk.END, error_text)
        
        self.analysis_text.config(state=tk.DISABLED)
    
    def _show_about(self):
        """Отображение информации о программе"""
        about_text = """
BESS_Geometry (Legacy Mode)
Building Energy Spatial System

Упрощенная версия системы для просмотра
геометрических данных зданий.

Версия: Legacy/Fallback
Режим работы: Только просмотр

Возможности Legacy режима:
• Открытие JSON файлов BESS
• Анализ структуры данных
• Просмотр метаданных проектов
• Базовая валидация файлов

Для полной функциональности установите
все компоненты системы BESS_Geometry.

Разработано для профессионального
использования в области проектирования
энергоэффективных зданий.
        """
        messagebox.showinfo("О программе", about_text)
    
    def _show_limitations(self):
        """Отображение информации об ограничениях Legacy режима"""
        limitations_text = """
ОГРАНИЧЕНИЯ LEGACY РЕЖИМА

Legacy режим активируется когда система не может
найти все необходимые компоненты для полной работы.

ЧТО НЕДОСТУПНО В LEGACY РЕЖИМЕ:

🚫 Графическое отображение:
   • Нет визуализации планов зданий
   • Нет интерактивного редактора
   • Нет масштабирования и навигации

🚫 Редактирование данных:
   • Нельзя изменять геометрию
   • Нет инструментов рисования
   • Нет операций с элементами

🚫 Расширенный анализ:
   • Нет анализа смежности помещений
   • Нет расчета площадей и объемов
   • Нет проверки геометрических ошибок

🚫 Экспорт данных:
   • Нет экспорта в CONTAM
   • Ограниченные возможности сохранения
   • Нет конвертации форматов

ЧТО НУЖНО ДЛЯ ПОЛНОЙ ФУНКЦИОНАЛЬНОСТИ:

✅ Установите недостающие модули:
   • file_manager.py
   • geometry_utils.py
   • performance.py
   • state.py
   • controllers/
   • ui/

✅ Проверьте структуру проекта
✅ Убедитесь в наличии всех зависимостей

После установки компонентов перезапустите
приложение для активации полного режима.
        """
        
        # Создаем окно с подробной информацией
        limitations_window = tk.Toplevel(self.root)
        limitations_window.title("Ограничения Legacy режима")
        limitations_window.geometry("500x600")
        limitations_window.transient(self.root)
        
        text_widget = scrolledtext.ScrolledText(
            limitations_window,
            wrap=tk.WORD,
            font=('Arial', 10),
            bg='#fff8dc'
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text_widget.insert(tk.END, limitations_text)
        text_widget.config(state=tk.DISABLED)
        
        # Кнопка закрытия
        close_button = tk.Button(
            limitations_window,
            text="Понятно",
            command=limitations_window.destroy,
            font=('Arial', 10),
            pady=5
        )
        close_button.pack(pady=10)
    
    def _on_closing(self):
        """Обработчик закрытия приложения"""
        self.root.destroy()
    
    def mainloop(self):
        """
        Запуск главного цикла приложения
        
        Этот метод обеспечивает совместимость с системой запуска,
        которая ожидает метод mainloop() от legacy приложения.
        """
        print("🚀 Запуск главного цикла Legacy приложения")
        
        try:
            self.root.mainloop()
            print("✅ Legacy приложение завершено корректно")
            
        except Exception as e:
            print(f"❌ Ошибка в Legacy приложении: {e}")
            raise

# Точка входа для прямого запуска
if __name__ == '__main__':
    """
    Прямой запуск legacy приложения для тестирования
    """
    print("🧪 Прямой запуск Legacy приложения BESS_Geometry")
    
    try:
        app = App()
        app.mainloop()
        
    except Exception as e:
        print(f"❌ Критическая ошибка Legacy приложения: {e}")
        traceback.print_exc()