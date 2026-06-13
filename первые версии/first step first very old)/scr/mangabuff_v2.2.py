import requests, time, os, re, asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


# Проверка для того, чтобы каждый раз не вызывать chapter_link_100
def number_of_chapter(url):
    number_of_chapters = 0
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        chapters_button = soup.find('button', attrs={'data-page': 'chapters'})

        # Извлекаем текст и находим количество глав
        if chapters_button:
            text = chapters_button.get_text()
            number_of_chapters = int(text.split('(')[-1].strip(')'))
            print(f"Number of chapters: {number_of_chapters}")
        else:
            print("Не найдены атрибуты")
    else:
        print(f"Ошибка при запросе страницы: {response.status_code}")

    return number_of_chapters

def manga_name(url):
    title_name = ""
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        title_name = soup.find('h1', class_='manga__name').get_text()


        title_name = re.sub(r'[<>:"/\\.|?*]', '', title_name).strip()
        title_name = title_name.strip()
    else:
        print(f"Ошибка при запросе страницы: {response.status_code}")

    return title_name


async def chapter_link_100(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url)
        await page.wait_for_selector('button.tabs__item[data-page="chapters"]', timeout=60000)
        await page.click('button.tabs__item[data-page="chapters"]')
        await page.wait_for_selector('a.chapters__item', timeout=60000)

        last_height = await page.evaluate("document.body.scrollHeight")

        while True:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            await page.wait_for_timeout(2000)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        chapter_tags = await page.query_selector_all('a.chapters__item')
        chapters = []
        for tag in chapter_tags:
            volume_tag = await tag.query_selector('div.chapters__volume')
            chapter_tag = await tag.query_selector('div.chapters__value')

            vol = await volume_tag.inner_text() if volume_tag else ''
            ch = await chapter_tag.inner_text() if chapter_tag else ''

            vol_number = re.search(r'\d+', vol)
            ch_number = re.search(r'\d+', ch)

            if vol_number and ch_number:
                chapters.append((vol_number.group(), ch_number.group()))

        await browser.close()
        return chapters

def chapter_link_99(url):
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

def chapter_picture_link(url):
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    reader_pages = soup.find('div', class_='reader__pages')
    img_tags = reader_pages.find_all('img') if reader_pages else []

    links = []
    for img in img_tags:
        if img.get('src'):
            links.append(img['src'])
        elif img.get('data-src'):
            links.append(img['data-src'])

    return links

def download_picture(volume, chapter, page, url_title_name, image_server_url, manga_name, download_dir=r"D:\Manga"):
    directory = os.path.join(download_dir, manga_name, f"volume_{volume}__chapter_{chapter}")
    file_path = os.path.join(directory, f"{page}.jpg")

    if os.path.exists(file_path):
        return True  
    

    chapter_url = f"{image_server_url}/manga/{url_title_name}/{volume}/{chapter}"

    # Попытки загрузки изображения с восстановлением соединения
    max_retries = 5
    for attempt in range(max_retries):
        try:
            links = chapter_picture_link(chapter_url)
            # Проверка, существует ли нужная страница
            if page - 1 < len(links):
                image_url = links[page - 1]
                os.makedirs(directory, exist_ok=True)  # Создаем директорию, если она не существует

                image_content = requests.get(image_url).content
                with open(file_path, "wb") as img_file:
                    img_file.write(image_content)
                print(f"Сохранено: {file_path}")
                return True
            else:
                print(f"Страница {page} не существует для тома {volume} главы {chapter}.")
                return False  # Глава есть, а страниц нет или платная
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при загрузке изображения {image_url}: {e}. Попытка {attempt + 1} из {max_retries}.")
            time.sleep(10)  # Ждем перед повторной попыткой

    print(f"Не удалось загрузить изображение {image_url} после {max_retries} попыток.")
    return False




def main():
    # Список манг для скачивания
    manga_list = [
        #"assasin-iz-armii-korolya-demonov-vnedrilsya-v-gruppu-geroya",
        #"ya-pererodilsya-v-romanticheskoi-rpg-kak-zlodei-neudachnik-i-proignoriruyu-originalnyi-syuzhet",
        #"vernuvshiisya-tanker-c-ranga-ne-umret",
        #"ochkarik-yanki",
        #"dochka-bossa-i-ee-nyanka",
        #"skazanie-hengdan",
        #"smert-otvergnutoi-ledi-nachalo-konca",
        #"ya-zlodei-gildmaster",
        #"nachnite-s-zhenskih-stazhirovok",
        #"imperatorskaya-gornichnaya",
        #"bitva-nekromantov"
        "zomgan"
        #"ledi-buntovshchica-ne-zhelaet-poddavatsya-vliyaniyu-navyazchivogo-princa"
    ]

    
    url_image_server = "https://mangabuff.ru"

    for url_title_name in manga_list:
        base_url = f"{url_image_server}/manga/{url_title_name}"
        chapters = []
        title_name = manga_name(base_url)

        print("Start: " + title_name)

        # Получаем количество глав и соответствующие номера
        if number_of_chapter(base_url) > 99:
            chapters = asyncio.run(chapter_link_100(base_url))
        else:
            chapters = chapter_link_99(base_url)

        # Проверка на существующие главы
        existing_chapters = len(os.listdir(os.path.join(r"D:\Manga", title_name))) if os.path.exists(os.path.join(r"D:\Manga", title_name)) else 0

        #не идеялен поскольку в будущем придется убрать для реализации обновления
        if existing_chapters >= len(chapters):
            print(f"All Chapter was downloaded\n")
            continue  # Пропускаем эту мангу и переходим к следующей

        # Загружаем изображения для каждой главы
        for vol, ch in chapters:
            print(f"Загрузка тома {vol}, главы {ch}")
            url = f"{base_url}/{vol}/{ch}"

            links = chapter_picture_link(url)

            # Загружаем каждую страницу
            for page in range(1, len(links) + 1):
                download_picture(vol, ch, page, url_title_name, url_image_server, title_name)

        print("Download was finish")

if __name__ == "__main__":
    main()