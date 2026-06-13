import os
import shutil

def compare_copy_to_disk(src_folder, dest_folder):
    # Получаем список подкаталогов и файлов в исходной и целевой папках
    src_items = sorted(os.listdir(src_folder))  # Сортируем элементы
    dest_items = sorted(os.listdir(dest_folder))  # Сортируем элементы

    # Находим элементы, которые нужно скопировать
    items_to_copy = [item for item in src_items if item not in dest_items]

    # Копируем недостающие элементы
    for item in items_to_copy:
        src_path = os.path.join(src_folder, item)
        dest_path = os.path.join(dest_folder, item)

        if os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path)
            print(f"Скопирована папка: {src_path}")
        elif os.path.isfile(src_path):
            shutil.copy2(src_path, dest_path)
            print(f"Скопирован файл: {src_path}")

    # Проверяем существующие папки и рекурсивно копируем их содержимое
    for item in src_items:
        if item in dest_items:
            src_path = os.path.join(src_folder, item)
            dest_path = os.path.join(dest_folder, item)

            if os.path.isdir(src_path):
                compare_copy_to_disk(src_path, dest_path)  # Рекурсивно проверяем подкаталоги

# Укажите пути к исходной и целевой папкам
source_folder = r"D:\Manga"
destination_folder = r"E:\My Files\Manga"

compare_copy_to_disk(source_folder, destination_folder)
print("All files and folders checked and copied")
