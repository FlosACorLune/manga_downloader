import re, requests, os, json, time, zipfile
import concurrent.futures
import signal

import config


stop_requested = False

def handle_stop(signum, frame):
    global stop_requested
    stop_requested = True
    print("\n🟥 Прерывание — сохранение текущего состояния...")

# Ctrl+C работает на всех ОС
signal.signal(signal.SIGINT, handle_stop)

# Ctrl+Z есть только в Unix, поэтому проверяем
if hasattr(signal, "SIGTSTP"):
    signal.signal(signal.SIGTSTP, handle_stop)


PATH = config.PATH
JSON_FILE = config.JSON_FILE
ATTEMP = config.ATTEMP
WORKER = config.WORKER


parameters = "?fields[]=background&fields[]=moderated&fields[]=manga_status_id&fields[]=chap_count&fields[]=status_id"
api_url = "https://api.cdnlibs.org/api/manga/"
server_one = "https://img2.imglib.info"
server_compression = "https://img3.mixlib.me"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://mangalib.org",
    "Referer": "https://mangalib.org/",
    "Site-Id": "1",
    "Client-Time-Zone": "Asia/Yekaterinburg",
}

# C A C H E json
def get_json(url):
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    return data


# M I N I --------------- F U N C

def get_titile_name(result_query_fields):
    raw = result_query_fields["data"]['rus_name']
    clean = re.sub(r'[\\/:*?"<>|]', '', raw).strip().rstrip('.')
    return clean

def get_items_count(query_result):
    return query_result["data"]['items_count']['uploaded']

def get_number_to_url(result_num_vol, result_slug_url):
    result = []
    for vol, num in result_num_vol:
        result.append((vol, num, f"{api_url}{result_slug_url}/chapter?number={num}&volume={vol}"))
    return result


def is_chapter_downloaded(manga_dir, vol, ch):
    archive_path = os.path.join(manga_dir, f"volume_{vol}__chapter_{ch}.zip")
    return os.path.exists(archive_path)


#############################################




def download_single_image(idx, image_url):
    ext = os.path.splitext(image_url.split("?")[0])[1][1:] or "jpg"
    filename = f"{idx}.{ext}"
    for attempt in range(1, ATTEMP+1):
        try:
            resp = requests.get(image_url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            return filename, resp.content
        except requests.exceptions.RequestException as e:
            print(f"[{attempt}/{ATTEMP}] ❌ Ошибка при загрузке {image_url}: {e}")
            time.sleep(3)
    print(f"⚠️ Не удалось скачать: {image_url}")
    return filename, None

def save_images_as_zip(images_dict, output_path):
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_STORED) as zipf:
        for name, data in sorted(images_dict.items()):
            zipf.writestr(name, data)
    print(f"📦 Архив сохранён: {output_path}")

def download_images_to_memory(image_links):
    images = {}
    with concurrent.futures.ThreadPoolExecutor(WORKER) as executor:
        futures = [executor.submit(download_single_image, idx, url) for idx, url in enumerate(image_links, start=1)]
        for future in concurrent.futures.as_completed(futures):
            filename, data = future.result()
            if data:
                images[filename] = data
    return images

#single thread
#def download_images_to_memory(image_links):
    images = {}
    for idx, url in enumerate(image_links, start=1):
        filename, data = download_single_image(idx, url)
        if data:
            images[filename] = data
    return images


def download_and_save_chapter(url, manga_dir, vol, ch):
    print(f"⬇️ Загрузка главы: Том {vol}, Глава {ch}")
    query = get_json(url)
    image_links = [f"{server_one}{p['url']}" for p in query['data']['pages']]
    images = download_images_to_memory(image_links)

    if len(images) != len(image_links):
        print(f"⚠️ Загружено {len(images)} из {len(image_links)}. Пропуск.")
        return

    archive_path = os.path.join(manga_dir, f"volume_{vol}__chapter_{ch}.zip")
    save_images_as_zip(images, archive_path)
    print(f"✅ Сохранено: {archive_path}")




#####################

def get_downloaded_item_count(result_query_fields):
    folder_path = os.path.join(PATH, get_titile_name(result_query_fields))
    
    # Если папки нет → вернуть None
    if not os.path.exists(folder_path):
        return None
    
    # Если это не папка → тоже None
    if not os.path.isdir(folder_path):
        return None
    
    # Считаем только .zip файлы
    zip_files = [f for f in os.listdir(folder_path) if f.endswith('.zip')]
    return len(zip_files)






# S A V E S 

def update_manga_json(slug, result_query_chapters, result_query_fields, result_num_vol):
    # Если файла нет - создаём пустую структуру
    if not os.path.exists(JSON_FILE):
        data = {"mangalib.org": []}
    else:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    # ✅ Проверка на существование ключа "mangalib.org"
    if "mangalib.org" not in data or not isinstance(data["mangalib.org"], list):
        data["mangalib.org"] = []

    # Новая запись
    new_data = {
        "rus_name": get_titile_name(result_query_fields),
        "slug": slug,
        "scanlateStatus": result_query_fields['data']['scanlateStatus']['label'],
        "status": result_query_fields['data']['status']['label'],
        "available_chapters": get_items_count(result_query_fields),
        "downloaded_chapter": get_downloaded_item_count(result_query_fields)
    }

    # Проверка, есть ли манга уже в списке
    found = False
    for manga in data["mangalib.org"]:
        if manga.get("slug") == slug:
            found = True
            print(f"✅ Найдено совпадение: {get_titile_name(result_query_fields)}. Обновляю данные.")
            manga.update(new_data)
            break

    if not found:
        print(f"➕ Добавляю новую мангу: {new_data['rus_name']}")
        data["mangalib.org"].append(new_data)

    # Сохранение
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_num_vol(result_query_chapters, max_item_count):
    result = ()

    for i in range(max_item_count):
        chapter = result_query_chapters['data'][i]
        branch = chapter['branches'][0]  # Берем первую ветку

        expired = branch.get('expired_type', 0)
        restricted = branch.get('restricted_view')
        moderation = branch.get('moderation', {})
        label = moderation.get('label')

        # 1️⃣ Пропуск глав на модерации
        if label == "На модерации":
            continue

        # 2️⃣ Бесплатная глава
        if expired == 0:
            vol = chapter['volume']
            num = chapter['number']
            result += ((vol, num),)
            continue

        # 3️⃣ Временно платная, но стала бесплатной
        if expired == 1 and restricted is None:
            vol = chapter['volume']
            num = chapter['number']
            result += ((vol, num),)
            continue

    return result

def load_slugs_from_json(json_path=JSON_FILE, domain="mangalib.org"):
    """Загружает список slug из JSON."""
    if not os.path.exists(json_path) or os.stat(json_path).st_size == 0:
        print(f"⚠️ Файл {json_path} пуст или не существует")
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if domain not in data or not isinstance(data[domain], list):
        print(f"⚠️ В JSON нет домена {domain}")
        return []

    return [manga["slug"] for manga in data[domain] if "slug" in manga]




def init(links):
    global stop_requested
    for link in links:
        slug = link

        # Первые запросы
        query_chapters = f'{api_url}{slug}/chapters'
        query_fields = f'{api_url}{slug}{parameters}'

        result_query_chapters = get_json(query_chapters)
        result_query_fields = get_json(query_fields)
        max_count_item = get_items_count(result_query_fields)
        result_num_vol = get_num_vol(result_query_chapters, max_count_item)
        update_manga_json(slug, result_query_chapters,result_query_fields,result_num_vol)

        manga_title = get_titile_name(result_query_fields)
        manga_dir = os.path.join(PATH, manga_title)
        os.makedirs(manga_dir, exist_ok=True)

        print(f"📘 Manga: {manga_title}, Глав: {len(result_num_vol)}")

        chapters_data = get_number_to_url(result_num_vol, slug)

        for vol, ch, api_link in chapters_data:
            if stop_requested:
                print("⏹️ Прерывание загрузки пользователем.")
                try:
                    update_manga_json(slug, result_query_chapters,result_query_fields,result_num_vol)
                except Exception as e:
                    print(f"⚠️ Ошибка при сохранении прогресса: {e}")
                
                stop_requested = False
                return
            if is_chapter_downloaded(manga_dir, vol, ch):
                print(f"✅ Пропуск: Том {vol} Глава {ch} уже скачана")
                continue
            download_and_save_chapter(api_link, manga_dir, vol, ch)