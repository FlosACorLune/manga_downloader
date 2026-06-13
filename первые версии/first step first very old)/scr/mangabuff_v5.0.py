import requests, time, os, re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

#v4.0 добавлено пареллельное скачивание картинок
#v5.0 избавление от симуляции браузера через token

#известные проблемы
#там где есть 18+ плашка пока нельзя скачать ибо нужно авторизовываться

#T A S K      F O R     F U T U R E  
#иногда случаются ошибки со стороны сервера когда у него битая ссылка
#Иногда картинки не отображаются, причина по которой оно не показывало или вызывало ошибка было в том что я не правильно сохранял формат. PNG в JPG например. 


#cache requests
def page_request(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup

def number_of_chapter(soup):
    number_of_chapters=0
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

def manga_id(soup):
    manga_id = 0
    manga_div = soup.find("div", class_="manga")
    if manga_div and manga_div.has_attr("data-id"):
        manga_id = manga_div["data-id"]
    else:
        manga_id = -1
    return manga_id

def get_flat_chapter(soup):
    links = [a['href'] for a in soup.find_all('a', class_='chapters__item', href=True)]
    links= extract_vol_ch(links)
    return links


def r_manga_list(download_dir):
    directory = os.path.join(download_dir)
    file_path = os.path.join(directory, "mangalist.txt")

    with open(file_path, 'r') as line:
        manga_list = [re.sub(r'\n', '', manga) for manga in line if not manga.startswith('#')]

    return manga_list

def extract_vol_ch(links):
    volumes_and_chapters = []

    # Регулярное выражение для поиска формата "том/глава"
    pattern = re.compile(r'(\d+)/(\d+)')

    for link in links:
        match = pattern.search(link)
        if match:
            volume = match.group(1)  # Первая группа - том
            chapter = match.group(2)  # Вторая группа - глава
            volumes_and_chapters.append((volume, chapter))

    return volumes_and_chapters

def get_lazy_loading_bypass_chapter(headers, cookies, payload, url = 'https://mangabuff.ru/chapters/load'):
    response = requests.post(url, headers=headers, cookies=cookies, json=payload)
    response.raise_for_status()
    data = response.json()
    html = data.get("html") or data.get("content", "")
    soup = BeautifulSoup(html, "html.parser")
    links = [a['href'] for a in soup.find_all('a', class_='chapters__item', href=True)]
    links= extract_vol_ch(links)
    return links

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


def download_picture(volume, chapter, page, url_title_name, image_server_url, manga_name, download_dir):
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


def download_chapter_images_parallel(vol, ch, url_title_name, url_image_server, manga_name, links, download_dir, max_workers):
    def task(page_num):
        return download_picture(vol, ch, page_num, url_title_name, url_image_server, manga_name, download_dir)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(task, page_num + 1) for page_num in range(len(links))]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Ошибка при загрузке страницы: {e}")


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
    if session_token:
        session_token = session_token.replace('%3D', '')

    return {
        'xsrf_token': xsrf_token,
        'session_token': session_token
    }


def main():
    manga_directory = r"D:\Manga"
    website = 'https://mangabuff.ru'
    url_title_name = r_manga_list(manga_directory)
    chapters = []

    for title_name in url_title_name:
        url_manga_path = f'{website}/manga/{title_name}'
        soup = page_request(url_manga_path)
        title_name_result = manga_name(soup)
        number_of_chapter_result = number_of_chapter(soup)
        

        print('Start downloading ' + title_name_result)
        print('Total chapter: ' + str(number_of_chapter_result))

        manga_path = os.path.join(manga_directory, title_name_result)
        if os.path.exists(manga_path):
            existing_chapters = len(os.listdir(manga_path))
        else:
            existing_chapters = 0
        print("Downloaded chapter: " + str(existing_chapters))


        chapters = get_flat_chapter(soup)

        if number_of_chapter_result > 100: 
            tokens = get_tokens(url_manga_path)
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
                url = f"{url_manga_path}/{vol}/{ch}"

                links = chapter_picture_link(url)

                download_chapter_images_parallel(
                    vol, ch, title_name, website, title_name_result, links, manga_directory, max_workers=4
                    )

        print("Download was finish")
    


if __name__ == "__main__":
    main()