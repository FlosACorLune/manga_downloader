import requests, os, asyncio, re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright



# проверка для того что бы каждый раз не вызывать chapter_link_100
def number_of_chapter(url):
    number_of_chapters = 0

    response = requests.get(url)

 
    if response.status_code == 200:

        soup = BeautifulSoup(response.text, 'html.parser')

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


def manga_name(url):
    title_name = 0
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        title_name = soup.find('h1',  class_ = 'manga__name').get_text()
    else:
        print(f"Ошибка при запросе страницы: {response.status_code}")

    return title_name

#нужен когда больше 100 глав из за динамической загрузки js-ом страниц
#в теории вроде можно обойтись только через requests fetch/xhr 
async def chapter_link_100(url):

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

            # Извлекаем только номера томов и глав в формате "n m"
            vol_number = re.search(r'\d+', vol)
            ch_number = re.search(r'\d+', ch)

            if vol_number and ch_number:
                chapters.append((vol_number.group(), ch_number.group()))

        await browser.close()

        return chapters



def chapter_link_99(url): #функция для получения кортежи тома и глав 
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

    return chapters


def chapter_picture_link(url): #функция для получения ссылок на изображения
    # Выполняем GET-запрос
    response = requests.get(url)
    response.raise_for_status()  # Проверяем на ошибки

    # Парсим HTML
    soup = BeautifulSoup(response.text, 'html.parser')

    # Находим все элементы с классом "reader__pages" и собираем ссылки на изображения
    reader_pages = soup.find('div', class_='reader__pages')
    img_tags = reader_pages.find_all('img') if reader_pages else []

    # Извлекаем ссылки из атрибутов src и data-src какого хуя у них разные не знаю
    links = []
    for img in img_tags:
        if img.get('src'):
            links.append(img['src'])
        elif img.get('data-src'):
            links.append(img['data-src'])

    return links


def download_picture(volume, chapter, page, title_name, image_server_url, manga_name, download_dir=r"D:\Manga"):
    # Формируем путь для сохранения изображений
    directory = os.path.join(download_dir, manga_name, f"volume_{volume}__chapter_{chapter}")
    file_path = os.path.join(directory, f"{page}.jpg")

    # Проверка на существование файла
    if os.path.exists(file_path):
        return True  # Файл уже существует

    chapter_url = f"{image_server_url}/manga/{title_name}/{volume}/{chapter}"

    try:
        links = chapter_picture_link(chapter_url)
    except requests.exceptions.HTTPError as e:
        print(f"Ошибка при получении главы {chapter} тома {volume}: {e}")
        return False

    # Проверка, существует ли нужная страница
    if page - 1 < len(links):
        image_url = links[page - 1]
        os.makedirs(directory, exist_ok=True)  # Создаем директорию, если она не существует

        try:
            image_content = requests.get(image_url).content
            with open(file_path, "wb") as img_file:
                img_file.write(image_content)
            print(f"Сохранено: {file_path}")
            return True
        except Exception as e:
            print(f"Ошибка при загрузке изображения {image_url}: {e}")
            return False
    else:
        print(f"Страница {page} не существует для тома {volume} главы {chapter}.")
        return False  # Глава есть, а страниц нет или платная






### TASKS ###
# реализовать/вести список который я могу запустить и обновить все манги

# реализовать вход в аккаунт для обхода блокировки при 18+ контенте
#   if class="error-404" sign in account
#<div class="container">
#    <p class="error-404">Доступ ограничен 18+</p>
#    <p>Эта страница содержит "взрослый" контент, просматривать который могут только <a href="/reg">авторизованные</a> пользователи.</p>
#</div>

#реализовать восстанавление подк при прерывании соеденения

def main():
    url_title_name = "ya-pererodilsya-v-romanticheskoi-rpg-kak-zlodei-neudachnik-i-proignoriruyu-originalnyi-syuzhet"
    url_image_server = "https://mangabuff.ru"
    base_url = f"{url_image_server}/manga/{url_title_name}"
    chapters = []
    title_name = manga_name(base_url)

    print("Начинается скачивание: " + title_name)

    # Получаем количество глав и соответствующие номера
    if number_of_chapter(base_url) > 99:
        chapters = asyncio.run(chapter_link_100(base_url))
    else:
        chapters = chapter_link_99(base_url)

    # Загружаем изображения для каждой главы
    for vol, ch in chapters:
        print(vol, ch)

        url = f"{base_url}/{vol}/{ch}"

        links = chapter_picture_link(url)

        # Загружаем каждую страницу
        for page in range(1, len(links) + 1):
            download_picture(vol, ch, page, url_title_name, url_image_server, title_name)

    print("Загрузка завершена.")


if __name__ == "__main__":
    main()