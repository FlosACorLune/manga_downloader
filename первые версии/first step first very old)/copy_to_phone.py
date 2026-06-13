import os
import subprocess

def run_command(command):
    """Выполняет команду и обрабатывает ошибки."""
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении команды {' '.join(command)}: {e}")

def create_remote_directory(dest_folder):
    """Создает папку на удаленном устройстве."""
    run_command(['adb', 'shell', 'mkdir', '-p', f'"{dest_folder}"'])

def compare_copy_to_device(src_folder, dest_folder):
    # Создаем целевую папку на устройстве
    create_remote_directory(dest_folder)

    # Получаем список файлов и папок на устройстве
    try:
        dest_items_output = subprocess.check_output(['adb', 'shell', 'ls', f'"{dest_folder}"']).decode('utf-8')
        dest_items = sorted(dest_items_output.splitlines())
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при получении списка файлов на устройстве: {e}")
        return

    # Получаем список файлов и папок на локальном компьютере
    src_items = sorted(os.listdir(src_folder))

    # Находим элементы, которые нужно скопировать
    items_to_copy = [item for item in src_items if item not in dest_items]

    # Копируем недостающие элементы на устройство
    for item in items_to_copy:
        src_path = os.path.join(src_folder, item)
        dest_path = os.path.join(dest_folder, item).replace('\\', '/')  # Заменяем обратные слэши на прямые

        if os.path.isdir(src_path):
            # Копируем папку
            run_command(['adb', 'push', src_path, dest_path])
            print(f"Скопирована папка: {src_path}")
        #elif os.path.isfile(src_path):
        #    # Копируем файл
        #    run_command(['adb', 'push', src_path, dest_path])
        #    print(f"Скопирован файл: {src_path}")

    # Проверяем существующие папки и рекурсивно копируем их содержимое
    for item in src_items:
        if item in dest_items:
            src_path = os.path.join(src_folder, item)
            dest_path = os.path.join(dest_folder, item).replace('\\', '/')  # Заменяем обратные слэши на прямые

            if os.path.isdir(src_path):
                compare_copy_to_device(src_path, dest_path)  # Рекурсивно проверяем подкаталоги

# Укажите пути к исходной и целевой папкам
source_folder = r"D:\Manga"
destination_folder = r"/storage/emulated/0/Amain/Manga"  # Путь на устройстве Android

print("start")
compare_copy_to_device(source_folder, destination_folder)
print("end")
