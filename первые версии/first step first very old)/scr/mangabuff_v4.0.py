import requests, time, os, re, asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from concurrent.futures import ThreadPoolExecutor, as_completed

#добавлено пареллельное скачивание картинок

#T A S K      F O R     F U T U R E  
#иногда случаются ошибки со стороны сервера когда у него битая ссылка
#добавить проверку каринок если они меньше 1кб то удалить и скачать заново пока мы еще не вышли из главы

def number_of_chapter(url):
    number_of_chapters = 0
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        chapters_button = soup.find('button', attrs={'data-page': 'chapters'})

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


    max_retries = 5
    for attempt in range(max_retries):
        try:
            links = chapter_picture_link(chapter_url)

            if page - 1 < len(links):
                image_url = links[page - 1]
                os.makedirs(directory, exist_ok=True)  

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



def download_chapter_images_parallel(vol, ch, url_title_name, url_image_server, manga_name, links, max_workers=5, download_dir=r"D:\Manga"):
    def task(page_num):
        return download_picture(vol, ch, page_num, url_title_name, url_image_server, manga_name, download_dir)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(task, page_num + 1) for page_num in range(len(links))]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Ошибка при загрузке страницы: {e}")

def r_manga_list(download_dir=r'D:\Manga'):
    directory = os.path.join(download_dir)
    file_path = os.path.join(directory, "mangalist.txt")

    with open(file_path, 'r') as line:
        manga_list = [re.sub(r'\n', '', manga) for manga in line if not manga.startswith('#')]
    
    return manga_list


def main():

    manga_list = r_manga_list()
    url_image_server = "https://mangabuff.ru"
    manga_directory = r"D:\Manga"


    for url_title_name in manga_list:
        base_url = f"{url_image_server}/manga/{url_title_name}"
        chapters = []
        title_name = manga_name(base_url)

        print("Start: " + title_name)


        if number_of_chapter(base_url) > 99:
            chapters = asyncio.run(chapter_link_100(base_url))
        else:
            chapters = chapter_link_99(base_url)



        manga_path = os.path.join(manga_directory, title_name)
        if os.path.exists(manga_path):
            existing_chapters = len(os.listdir(manga_path))
        else:
            existing_chapters = 0
        print("Number of downloaded chapter: " + str(existing_chapters))

        #возможно в будущем если я не заброшу развитие проекта то Я переработаю всю структуру и сделаю обновдение более лучше

        if existing_chapters == len(chapters):
            print(f"All Chapter was downloaded\n")
            continue
        else:
            for vol, ch in chapters:
                print(f"Загрузка тома {vol}, главы {ch}")
                url = f"{base_url}/{vol}/{ch}"

                links = chapter_picture_link(url)
                download_chapter_images_parallel(
                    vol, ch, url_title_name, url_image_server, title_name, links, max_workers=4
                    )

        print("Download was finish")

if __name__ == "__main__":
    main()