import requests, os, asyncio, re, requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

#v1 первая версия можно сказать тестовая/простотип сделанная под мангабафф воруя структуру mangalib_parser_by_zaqwer101
#v2.0 изначално делал через selenium и этот код очень часто менялся из за чего часть истории потерено. Но потом ии порекомендовал playwright что был быстрым по сравнению selenium

# проверка для того что бы каждый раз не вызывать get_chapter_numbers
def chapter_count(url):
    number_of_chapters = 0
    # Выполняем GET-запрос к странице
    response = requests.get(url)

    # Проверяем, успешен ли запрос
    if response.status_code == 200:
        # Создаем объект BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Находим кнопку с главами
        chapters_button = soup.find('button',  attrs={'data-page': 'chapters'})

        # Извлекаем текст и находим количество глав
        if chapters_button:
            text = chapters_button.get_text()
            # Извлекаем число из текста
            number_of_chapters = int(text.split('(')[-1].strip(')'))
            print(number_of_chapters)
        else:
            print("Do not found attrs")
    else:
        print(f"Ошибка при запросе страницы: {response.status_code}")

    return number_of_chapters



#нужен когда больше 100 глав из за динамической загрузки js-ом страниц
async def get_chapter_count_100(url):

    async with async_playwright() as p:
        # Запускаем браузер
        browser = await p.chromium.launch(headless=False)  # Установите headless=True, если не хотите видеть браузер
        page = await browser.new_page()
        
        # Открываем страницу
        await page.goto(url)

        # Кликаем на кнопку "Главы"
        await page.wait_for_selector('button.tabs__item[data-page="chapters"]', timeout=60000)
        await page.click('button.tabs__item[data-page="chapters"]')

        # Ждем появления элемента глав
        await page.wait_for_selector('a.chapters__item', timeout=60000)

        # Прокручиваем страницу вниз, чтобы загрузить все главы
        last_height = await page.evaluate("document.body.scrollHeight")

        while True:
            # Прокручиваем вниз
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            await page.wait_for_timeout(2000)  # Ждем, пока загрузится новый контент

            # Проверяем, загружены ли новые элементы
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break  # Если высота не изменилась, выходим из цикла
            last_height = new_height

        # Получаем номера томов и глав
        chapter_tags = await page.query_selector_all('a.chapters__item')
        chapters = []
        for tag in chapter_tags:
            volume_tag = await tag.query_selector('div.chapters__volume')
            chapter_tag = await tag.query_selector('div.chapters__value')

            vol = await volume_tag.inner_text() if volume_tag else ''
            ch = await chapter_tag.inner_text() if chapter_tag else ''

            # Извлекаем только номера томов и глав
            # Сохраняем только номера в формате "n m"
            vol_number = re.search(r'\d+', vol)
            ch_number = re.search(r'\d+', ch)

            if vol_number and ch_number:
                chapters.append((vol_number.group(), ch_number.group()))

        
        #with open('chapter_numbers.txt', 'w', encoding='utf-8') as file:
        #    for vol, ch in chapters:
        #        print(f"{vol} {ch}")
        #        file.write(f"{vol} {ch}\n")
        #print(f"Номера успешно сохранены в 'chapter_numbers.txt'. Найдено {len(chapters)} записей.")

        # Закрываем браузер
        await browser.close()

        return chapters

def get_chapter_picture(url): #функция для получения ссылок на изображения
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




def get_page(volume, chapter, page, manga_name, image_server_url):
    # Формируем путь для сохранения изображений
    directory = f"{manga_name}/volume_{volume}/chapter_{chapter}/"
    file = f"{directory}{page}.jpg"

    if os.path.exists(file):
        return True  # Файл уже существует

    page_url = f"{image_server_url}/manga/{manga_name}/{volume}/{chapter}"

    try:
        # Получаем ссылки на изображения
        links = get_chapter_picture(page_url)
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





#
def get_chapter_links(url):
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

    extracted_links = []
    for link in links:
        match = re.search(r'/(\d+)/(\d+)/(.*)', link)  # Ищем нужную часть ссылки
        if match:
            extracted_links.append(match.group(3))  # Добавляем только часть после volume/chapter/

    
    # Сохраняем ссылки в файл
    #with open('links.txt', 'w') as file:
    #    for link in extracted_links:
    #        file.write(link + '\n')   
    #print(f"Ссылки успешно сохранены в 'links.txt'. Найдено {len(links)} ссылок.")

    return extracted_links



def get_chapter_numbers(url): #функция для получения кортежи тома и глав 
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    chapter_tags = soup.find_all('a', class_='chapters__item')

    chapters = []
    for tag in chapter_tags:
        volume_tag = tag.find('div', class_='chapters__volume')
        chapter_tag = tag.find('div', class_='chapters__value')

        vol = volume_tag.find('span').text.strip() if volume_tag and volume_tag.find('span') else ''
        ch = chapter_tag.find('span').text.strip() if chapter_tag and chapter_tag.find('span') else ''

        if vol and ch:
            chapters.append((vol, ch))

    # Сохраняем только цифры в файл
    #with open('chapter_numbers.txt', 'w', encoding='utf-8') as file:
    #    for vol, ch in chapters:
    #        print(f"{vol} {ch}")
    #        file.write(f"{vol} {ch}\n")
    #print(f"Номера успешно сохранены в 'chapter_numbers.txt'. Найдено {len(chapters)} записей.")

    return chapters



### TASKS ###
# реализовать список который я могу запустить и обновить все манги
# реализовать вход в аккаунт для обхода блокировки при 18+ контенте
#   if class="error-404" sign in account
#<div class="container">
#    <p class="error-404">Доступ ограничен 18+</p>
#    <p>Эта страница содержит "взрослый" контент, просматривать который могут только <a href="/reg">авторизованные</a> пользователи.</p>
#</div>

def check_update():
    
    return 0

def main():
    manga_name = "ya-zlodei-gildmaster"
    image_server_url = "https://mangabuff.ru"

    chapters = []

    # Получаем количество глав и соответствующие номера
    if chapter_count(f"{image_server_url}/manga/{manga_name}") > 99:
        chapters = asyncio.run(get_chapter_count_100(f"{image_server_url}/manga/{manga_name}"))
    else:
        chapters = get_chapter_numbers(f"{image_server_url}/manga/{manga_name}")

    # Загружаем изображения для каждой главы
    for vol, ch in chapters:
        print(vol, ch)
        # Формируем URL для получения изображений
        url = f"{image_server_url}/manga/{manga_name}/{vol}/{ch}"

        # Получаем количество страниц в главе
        links = get_chapter_picture(url)

        # Загружаем каждую страницу
        for page in range(1, len(links) + 1):
            get_page(vol, ch, page, manga_name, image_server_url)

    print("Загрузка завершена.")


if __name__ == "__main__":
    main()