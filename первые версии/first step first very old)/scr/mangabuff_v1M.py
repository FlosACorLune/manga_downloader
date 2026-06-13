import utils, config
import requests, time, os, re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

def number_of_chapter(soup):
    number_of_chapters = 0
    chapters_button = soup.find('button', attrs={'data-page': 'chapters'})
    if chapters_button:
        text = chapters_button.get_text()
        number_of_chapters = int(text.split('(')[-1].strip(')'))
    else:
        number_of_chapters = -1
    return number_of_chapters

def manga_name(soup):
    title_name = soup.find('h1', class_='manga__name').get_text()
    title_name = re.sub(r'[<>:"/\\.|?*]', '', title_name).strip()
    return title_name

#network->playload->chapter>100 
def manga_id(soup):
    manga_id = 0
    manga_div = soup.find("div", class_="manga")
    if manga_div and manga_div.has_attr("data-id"):
        manga_id = manga_div["data-id"]
    else:
        manga_id = -1
    return manga_id

def extract_vol_ch(soup):
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

def get_flat_chapter(soup):
    return extract_vol_ch(soup)

def get_lazy_loading_bypass_chapter(headers, cookies, payload, url = 'https://mangabuff.ru/chapters/load'):
    response = requests.post(url, headers=headers, cookies=cookies, json=payload)
    response.raise_for_status()
    data = response.json()
    html = data.get("html") or data.get("content", "")
    soup = BeautifulSoup(html, "html.parser")
    return extract_vol_ch(soup)


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


def download_picture(volume, chapter, page, link, manga_name, download_dir):
    directory = os.path.join(download_dir, manga_name, f"volume_{volume}__chapter_{chapter}")
    file_path = os.path.join(directory, f"{page}.jpg")

    if os.path.exists(file_path):
        return True  
    
    chapter_url = f"{link}/{volume}/{chapter}"

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


def download_chapter_images_parallel(vol, ch, url_title_name, manga_name, links, download_dir, max_workers):
    def task(page_num):
        try:
            return download_picture(vol, ch, page_num, url_title_name, manga_name, download_dir)
        except Exception as e:
            print(f"Error in task for volume {vol}, chapter {ch}, page {page_num}: {e}")
            return False

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(task, page_num + 1) for page_num in range(len(links))]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error while processing future: {e}")


def get_tokens(url):
    # Выполняем GET-запрос к указанному URL
    response = requests.get(url)
    response.raise_for_status()  # Проверка на ошибки

    # Извлекаем токены из заголовков
    cookies = response.cookies
    xsrf_token = cookies.get('XSRF-TOKEN')
    session_token = cookies.get('mangabuff_session')

    # Убираем символы %3D из токенов, если они есть
    if xsrf_token:
        xsrf_token = xsrf_token.replace('%3D', '')
    elif session_token:
        session_token = session_token.replace('%3D', '')

    return {
        'xsrf_token': xsrf_token,
        'session_token': session_token
    }

def init(links):
    chapters=[]

    for link in links:
        soup = utils.get_soup(link)
        title_name_result = manga_name(soup)
        number_of_chapter_result = number_of_chapter(soup)


        print(f'Start downloading: {title_name_result}')
        print(f'Total chapter: {number_of_chapter_result}')

        manga_path = os.path.join(config.download_directory, title_name_result)
        if os.path.exists(manga_path):
            existing_chapters = len(os.listdir(manga_path))
        else:
            existing_chapters = 0
        print("Downloaded chapter: " + str(existing_chapters))

        chapters = get_flat_chapter(soup)

        if number_of_chapter_result > 100: 
            tokens = get_tokens(link)
            xsrf_token = tokens['xsrf_token']
            session_token = tokens['session_token']
            manga_id_result = manga_id(soup)

            headers = {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "X-XSRF-TOKEN": xsrf_token 
            }

            cookies = {
                "XSRF-TOKEN": xsrf_token,
                "mangabuff_session": session_token
            }

            payload = {
                "manga_id": manga_id_result
            }

            chapters += get_lazy_loading_bypass_chapter(headers,cookies,payload)


        if existing_chapters == len(chapters):
            print(f"All Chapter was downloaded\n")
            continue
        else:
            for vol, ch in chapters:
                print(f"Загрузка тома {vol}, главы {ch}")
                url = f"{link}/{vol}/{ch}"

                chapter_links = chapter_picture_link(url)

                download_chapter_images_parallel(
                    vol, ch, link, title_name_result, chapter_links, config.download_directory, max_workers=4
                    )

        print("Mangabuff download was finish\n")

    return