import utils, config
import re, requests, os, json, time
import concurrent.futures

parameters = "?fields[]=background&fields[]=moderated&fields[]=manga_status_id&fields[]=chap_count&fields[]=status_id"
api_url = "https://api.cdnlibs.org/api/manga/"
server_one = "https://img2.imglib.info"
server_compression = "https://img3.mixlib.me"


# M I N I --------------- F U N C
def get_slug_url(url):
    match = re.search(r'/manga/([^/?]+)', url)
    if match:
        return match.group(1)
    return None

def get_scanlateStatus(result_query_fields):
    return result_query_fields['data']['scanlateStatus']['label']

def get_status(result_query_fields):
    return result_query_fields['data']['status']['label']

def get_json(url):
    response = requests.get(url)
    data = response.json()
    return data

def get_num_vol(query_result, max_item_count):
    result = ()
    for i in range(0, max_item_count):
        vol = query_result["data"][i]['volume']
        num = query_result["data"][i]['number']
        result += ((vol, num),)
    return result

def get_chapter_images_url(query_result):
    return [f"{server_one}{p['url']}" for p in query_result['data']['pages']]

def get_titile_name(query_result):
    raw = query_result["data"]['rus_name']
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
    "Referer": "https://mangalib.org/"
}

def download_single_image(idx, image_url):
    ext = os.path.splitext(image_url.split("?")[0])[1][1:] or "jpg"
    filename = f"{idx}.{ext}"
    for attempt in range(1, config.max_attemp+1):
        try:
            resp = requests.get(image_url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            return filename, resp.content
        except requests.exceptions.RequestException as e:
            print(f"[{attempt}/{config.max_attemp}] ❌ Ошибка при загрузке {image_url}: {e}")
            time.sleep(3)
    print(f"⚠️ Не удалось скачать: {image_url}")
    return filename, None


#def download_images_to_memory(image_links):
    images = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(download_single_image, idx, url) for idx, url in enumerate(image_links, start=1)]
        for future in concurrent.futures.as_completed(futures):
            filename, data = future.result()
            if data:
                images[filename] = data
    return images

def download_images_to_memory(image_links):
    images = {}
    for idx, url in enumerate(image_links, start=1):
        filename, data = download_single_image(idx, url)
        if data:
            images[filename] = data
    return images


def download_and_save_chapter(url, manga_dir, vol, ch):
    print(f"⬇️ Загрузка главы: Том {vol}, Глава {ch}")
    query = get_json(url)
    image_links = get_chapter_images_url(query)
    images = download_images_to_memory(image_links)

    if len(images) != len(image_links):
        print(f"⚠️ Загружено {len(images)} из {len(image_links)}. Пропуск.")
        return

    archive_path = os.path.join(manga_dir, f"volume_{vol}__chapter_{ch}.zip")
    utils.save_images_as_zip(images, archive_path)
    print(f"✅ Сохранено: {archive_path}")


def save_status_json(slug,result_query_chapters, result_query_fields):
    data = {
            "rus_name":get_titile_name(result_query_fields),
            "slug_url":slug,
            "scanlateStatus": get_scanlateStatus(result_query_fields),
            "status":get_status(result_query_fields),
            "items_count":get_items_count(result_query_fields),
            "last_chapter_number":39.2,
            "last_chapter_date": "31.07.2025",
            "update_interval_in_day": 14
    }
    with open("manga.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)



def init(url):
    slug = get_slug_url(url)

    # Первые запросы
    query_chapters = f'{api_url}{slug}/chapters'
    query_fields = f'{api_url}{slug}{parameters}'

    result_query_chapters = get_json(query_chapters)
    result_query_fields = get_json(query_fields)

    max_count_item = get_items_count(result_query_fields)
    result_num_vol = get_num_vol(result_query_chapters, max_count_item)

    save_status_json(slug,result_query_chapters,result_query_fields)


    manga_title = get_titile_name(result_query_fields)
    manga_dir = os.path.join(config.download_directory, manga_title)
    os.makedirs(manga_dir, exist_ok=True)

    print(f"📘 Manga: {manga_title}, Глав: {len(result_num_vol)}")

    chapters_data = get_number_to_url(result_num_vol, slug)

    for vol, ch, api_link in chapters_data:
        if is_chapter_downloaded(manga_dir, vol, ch):
            print(f"✅ Пропуск: Том {vol} Глава {ch} уже скачана")
            continue
        download_and_save_chapter(api_link, manga_dir, vol, ch)

init("https://mangalib.me/ru/manga/183349--mankitsu-shitai-jouren-san?section=chapters")