#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Показ реальной структуры проекта - что где находится
"""

import sys
from pathlib import Path

def show_tree(directory, prefix="", max_depth=3, current_depth=0):
    """Показывает дерево файлов"""
    if current_depth >= max_depth:
        return
        
    items = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        current_prefix = "└── " if is_last else "├── "
        print(f"{prefix}{current_prefix}{item.name}")
        
        if item.is_dir() and not item.name.startswith('.') and not item.name.startswith('__pycache__'):
            next_prefix = prefix + ("    " if is_last else "│   ")
            show_tree(item, next_prefix, max_depth, current_depth + 1)

def find_python_files():
    """Находит все Python файлы"""
    current_dir = Path.cwd()
    python_files = list(current_dir.rglob("*.py"))
    
    print(f"🐍 НАЙДЕНО {len(python_files)} PYTHON ФАЙЛОВ:")
    print("-" * 50)
    
    for py_file in sorted(python_files):
        rel_path = py_file.relative_to(current_dir)
        size = py_file.stat().st_size
        print(f"   📄 {rel_path} ({size} байт)")

def check_specific_files():
    """Проверяет конкретные файлы которые нужны"""
    current_dir = Path.cwd()
    
    files_to_find = [
        "main_controller.py",
        "geometry_operations.py", 
        "editing_modes.py",
        "core/architectural_tools.py",
        "core/shaft_manager.py",
        "core/bess_parameters.py",
        "core/integration_manager.py",
        "ui/contour_editor.py"
    ]
    
    print(f"\n🎯 ПОИСК КОНКРЕТНЫХ ФАЙЛОВ:")
    print("-" * 50)
    
    for target_file in files_to_find:
        file_path = current_dir / target_file
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"   ✅ {target_file} ({size} байт)")
        else:
            print(f"   ❌ {target_file} - НЕ НАЙДЕН")
            
            # Ищем файл с таким именем в других местах
            filename = Path(target_file).name
            found_elsewhere = list(current_dir.rglob(filename))
            if found_elsewhere:
                print(f"      🔍 Найден в других местах:")
                for alt_location in found_elsewhere:
                    rel_path = alt_location.relative_to(current_dir)
                    print(f"         📍 {rel_path}")

def main():
    """Главная функция"""
    current_dir = Path.cwd()
    
    print("📁 СТРУКТУРА ПРОЕКТА BESS_GEOMETRY")
    print("=" * 60)
    print(f"📍 Директория: {current_dir}")
    print(f"🐍 Python: {sys.version}")
    
    print(f"\n🌳 ДЕРЕВО ДИРЕКТОРИЙ:")
    print("-" * 50)
    show_tree(current_dir)
    
    find_python_files()
    check_specific_files()
    
    print(f"\n💡 ЕСЛИ ФАЙЛЫ ЕСТЬ, НО НЕ ИМПОРТИРУЮТСЯ:")
    print("-" * 50)
    print("   1. Проверьте __init__.py в каждой папке")
    print("   2. Запустите: python advanced_check.py")
    print("   3. Или добавьте в начало скрипта:")
    print("      import sys")
    print(f"      sys.path.insert(0, r'{current_dir}')")

if __name__ == '__main__':
    main()