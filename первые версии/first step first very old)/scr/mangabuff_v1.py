import requests
import os
from bs4 import BeautifulSoup

#v1 первая версия можно сказать тестовая/простотип сделанная под мангабафф смотря на структуру mangalib_parser_by_zaqwer101

manga_name = "imperatorskaya-gornichnaya"
image_server_url = "https://mangabuff.ru"

def chapter_url(url):
    # Выполняем GET-запрос
    response = requests.get(url)
    response.raise_for_status()  # Проверяем на ошибки

    # Парсим HTML
    soup = BeautifulSoup(response.text, 'html.parser')

    # Находим все элементы с классом "reader__pages" и собираем ссылки на изображения
    reader_pages = soup.find('div', class_='reader__pages')
    img_tags = reader_pages.find_all('img') if reader_pages else []

    # Извлекаем ссылки из атрибутов src и data-src
    links = []
    for img in img_tags:
        if img.get('src'):
            links.append(img['src'])
        elif img.get('data-src'):
            links.append(img['data-src'])

    return links

def get_page(volume, chapter, page):
    # Формируем путь для сохранения изображений
    directory = f"{manga_name}/volume_{volume}/chapter_{chapter}/"
    file = f"{directory}{page}.jpg"

    if os.path.exists(file):
        return True  # Файл уже существует

    page_url = f"{image_server_url}/manga/{manga_name}/{volume}/{chapter}"

    try:
        # Получаем ссылки на изображения
        links = chapter_url(page_url)
    except requests.exceptions.HTTPError as e:
        print(f"Ошибка при получении главы {chapter} тома {volume}: {e}")
        return False  # Если не удалось получить ссылки

    # Проверяем, есть ли нужная страница
    if page - 1 < len(links):
        image_url = links[page - 1]
        if not os.path.isdir(directory):
            os.makedirs(directory)
        # Загружаем изображение
        image_content = requests.get(image_url).content
        with open(file, "wb") as img_file:
            img_file.write(image_content)
        print(f"Сохранено: {file}")
        return True
    else:
        return False  # Страница не существует

volume = 1
chapter = 1
page = 1

while True:
    while True:
        status = get_page(volume, chapter, page)
        if status:
            page += 1
        else:
            break

    # Проверяем наличие следующей главы
    next_chapter_url = f"{image_server_url}/manga/{manga_name}/{volume}/{chapter + 1}"
    try:
        response = requests.get(next_chapter_url)
        response.raise_for_status()  # Проверяем на ошибки
        chapter += 1  # Переходим к следующей главе
        page = 1  # Сбрасываем страницу на 1
    except requests.exceptions.HTTPError:
        # Если следующей главы нет, проверяем наличие следующего тома
        next_volume_url = f"{image_server_url}/manga/{manga_name}/{volume + 1}/1"
        try:
            response = requests.get(next_volume_url)
            response.raise_for_status()  # Проверяем на ошибки
            volume += 1  # Переходим к следующему тому
            chapter = 1  # Сбрасываем главу на 1
            page = 1  # Сбрасываем страницу на 1
        except requests.exceptions.HTTPError:
            print(f"Глава {chapter} и том {volume} не найдены. Завершение.")
            break  # Если следующего тома нет, выходим из цикла

print("Загрузка завершена.")
