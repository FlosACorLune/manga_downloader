import os
import re
import time
import requests
import concurrent.futures
import json
import zipfile
from bs4 import BeautifulSoup

download_directory = r"D:\Test2"
mangalist_file = "mangalist.txt"
isFinished = False #if False create folder, if True create ARCHIVE
max_attemp = 5
max_workers = 8




#mangahub.live -> mangahub.cc
JSON_FILE = "manga.json"
KEYS = ['mangalib.org','mangabuff.ru','mangahub.cc']

#cache requests
def get_soup(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup


#read file
def read_file_mangalist(download_dir):
    directory = os.path.join(download_dir)
    file_path = os.path.join(directory, mangalist_file)

    with open(file_path, 'r') as line:
        manga_list = [re.sub(r'\n', '', manga) for manga in line if not manga.startswith('#')]
    
    return manga_list

def get_slug_url(url):
    match = re.search(r'/manga/([^/?]+)', url)
    if match:
        return match.group(1)
    return None

def get_domain_from_url(url):
    match = re.search(r'https?://([^/]+)/', url)
    return match.group(1) if match else None

def add_slugs_from_file():
    manga_urls = read_file_mangalist(download_directory)

    # Загружаем или создаём JSON
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}

    for url in manga_urls:
        slug = get_slug_url(url)
        domain = get_domain_from_url(url)

        if not slug or not domain:
            print(f"⚠️ Пропуск (не удалось получить slug или домен): {url}")
            continue

        # Если сайта нет в JSON — создаём пустой список
        if domain not in data or not isinstance(data[domain], list):
            data[domain] = []

        # Проверяем дубликаты
        if any(m.get("slug_url") == slug for m in data[domain]):
            print(f"✅ {slug} уже есть в {domain}")
            continue

        # Добавляем запись
        new_manga = {
            "rus_name": None,
            "slug_url": slug,
            "scanlateStatus": None,
            "status": None,
            "items_count": None,
            "last_chapter_number": None,
            "last_available_chapter_number": None,
            "downloaded_item_count": None
        }

        data[domain].append(new_manga)
        print(f"➕ Добавлена манга {slug} в {domain}")

    # Сохраняем
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

#разделение по модулям
def route_link_from_json():
    if not os.path.exists(JSON_FILE):
        print("⚠️ Файл manga.json не найден")
        return {}

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    site_dict = {}

    # Проходим по сайтам (mangalib.org, mangabuff.ru, ...)
    for site, mangas in data.items():
        slugs = []
        for manga in mangas:
            slug = manga.get("slug_url")
            if slug:
                slugs.append(slug)

        if slugs:
            site_dict[site] = slugs

    return site_dict



#fast самое оптимальное в среднем 80~ в fastest тоже ~80. в normal уже 60.  
#архивация глав
def save_images_as_zip(images_dict, output_path):
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as zipf:
        for name, data in sorted(images_dict.items()):
            zipf.writestr(name, data)
    print(f"📦 Архив сохранён: {output_path}")


#архивация тайтал
def save_title_as_zip(final_archive,all_data):
    with zipfile.ZipFile(final_archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as zipf:
        for path, data in sorted(all_data.items()):
            zipf.writestr(path, data)
    print(f"✅ Все главы собраны в единый архив: {final_archive}")



def title_name(soup):
    # Пробуем новый вариант
    title_div = soup.find("div", class_="title_head_name")
    if title_div:
        raw_title = title_div.get_text(strip=True)
        clean_title = re.sub(r'[\\/:*?"<>|]', '', raw_title).strip().rstrip('.')
        return clean_title

    # Запасной вариант — вдруг верстка вернётся
    h1 = soup.find("h1")
    if h1:
        raw_title = h1.get_text(strip=True)
        clean_title = re.sub(r'[\\/:*?"<>|]', '', raw_title).strip().rstrip('.')
        return clean_title

    raise ValueError("❌ Название не найдено. Возможно, изменился HTML.")


def extract_image_links(soup):
    reader_pages = soup.find('div', class_='pages_placer')
    img_tags = reader_pages.find_all('img') if reader_pages else []
    return [img.get('src') or img.get('data-src') for img in img_tags if img.get('src') or img.get('data-src')]

def download_single_image(idx, image_url):
    ext = os.path.splitext(image_url.split("?")[0])[1][1:] or "webp"
    filename = f"{idx}.{ext}"
    
    for attempt in range(1, max_attemp+1):
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            return filename, response.content
        except requests.exceptions.RequestException as e:
            print(f"[{attempt}/{max_attemp}] ❌ Ошибка при загрузке {image_url}: {e}")
            time.sleep(5)
    print(f"⚠️ Не удалось скачать: {image_url}")
    return filename, None

def download_images_to_memory(image_links):
    images = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(download_single_image, idx, url) for idx, url in enumerate(image_links, start=1)]
        for future in concurrent.futures.as_completed(futures):
            filename, data = future.result()
            if data:
                images[filename] = data
    return images

def extract_vol_ch(soup):
    chapters = []
    for tag in soup.find_all('div', class_='chapter_block_inner'):
        vol_tag, ch_tag = tag.find('div', class_='chapter_volume'), tag.find('div', class_='chapter_number')

        volume = re.search(r'\d+', vol_tag.text).group() if vol_tag else None
        chapter = re.search(r'\d+(?:\.\d+)?', ch_tag.text).group() if ch_tag else None

        if volume and chapter:
            chapters.append((volume, chapter))

    return chapters

def is_chapter_downloaded(download_dir, manga_name, volume, chapter):
    path = os.path.join(download_dir, manga_name, f"volume_{volume}__chapter_{chapter}.zip")
    return os.path.exists(path)

def download_and_store_chapter(link, manga_dir, manga_title, vol, ch, isFinished):
    archive_name = f"volume_{vol}__chapter_{ch}.zip"
    archive_path = os.path.join(manga_dir, archive_name)

    if not isFinished and os.path.exists(archive_path):
        print(f"✅ Пропуск: {archive_name} уже есть")
        return {}

    chapter_url = f"{link}/v{vol}/c{ch}"
    print(f"⬇️ Загрузка главы: Том {vol}, Глава {ch}")
    soup = get_soup(chapter_url)
    image_links = extract_image_links(soup)
    images = download_images_to_memory(image_links)

    if len(images) != len(image_links):
        print(f"⚠️ Загружено {len(images)} из {len(image_links)}. Пропускаю.")
        return None

    if isFinished:
        return {f"{manga_title}/volume_{vol}__chapter_{ch}/{k}": v for k, v in images.items()}
    else:
        save_images_as_zip(images, archive_path)
        return {}


JSON_FILE = "manga.json"

def load_links_from_json(json_path=JSON_FILE, domain="mangahub.live"):
    """Загружает список ссылок на мангу из локального JSON."""
    if not os.path.exists(json_path) or os.stat(json_path).st_size == 0:
        print(f"⚠️ Файл {json_path} пуст или не существует.")
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if domain not in data or not isinstance(data[domain], list):
        print(f"⚠️ В JSON нет данных для домена {domain}")
        return []
    print(data[domain])
    print(domain)

    links = []
    for manga in data[domain]:
        if "url" in manga:
            links.append(manga["url"])
        elif "slug" in manga:
            links.append(f"https://{domain}/manga/{manga['slug']}")
    return links


def init_from_json():
    """Читает ссылки из JSON и передает их в init()."""
    links = load_links_from_json()
    if not links:
        print("⚠️ Нет ссылок для загрузки.")
        return

    init(links)  # вызываем твою существующую функцию init()



def init(links):


    for link in links:
        soup = get_soup(link)
        manga_title = title_name(soup)
        manga_dir = os.path.join(download_directory, manga_title)
        final_archive = os.path.join(download_directory, f"{manga_title}__complete.zip")

        print(f"📘 Manga: {manga_title}")

        if isFinished and os.path.exists(final_archive):
            print(f"✅ Итоговый архив уже существует: {final_archive} — пропускаем загрузку")
            continue

        if not isFinished:
            os.makedirs(manga_dir, exist_ok=True)

        chapters = extract_vol_ch(soup)
        print(f"🔍 Найдено глав: {len(chapters)}")

        if not isFinished:
            downloaded_count = len([f for f in os.listdir(manga_dir) if f.endswith('.zip')])
            if not isFinished and downloaded_count == len(chapters):
                print(f"✅ Все главы уже скачаны: {downloaded_count}/{len(chapters)} — пропускаю мангу.")
                continue

        all_chapter_data = {}

        for vol, ch in chapters:
            if not isFinished and is_chapter_downloaded(download_directory, manga_title, vol, ch):
                print(f"✅ Глава {vol}-{ch} уже загружена. Пропускаю.")
                continue

            chapter_data = download_and_store_chapter(link, manga_dir, manga_title, vol, ch, isFinished)

            if chapter_data is None:
                if isFinished:
                    print("❌ Прерываю сборку общего архива — неполная глава.")
                    return
            else:
                all_chapter_data.update(chapter_data)

        if isFinished and all_chapter_data:
            save_title_as_zip()
