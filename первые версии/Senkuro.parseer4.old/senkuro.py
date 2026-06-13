import asyncio
import os
import aiohttp
import json
import io
import zipfile
import re
import urllib.parse

import config

JSON_FILE = config.JSON_FILE
PATH = config.PATH
max_concurrent = 5
max_retries = 3
latency = 10 #in seconds


api_url = 'https://api.senkuro.me/graphql'
domain = "senkuro.me"
headers = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
}



async def fetchManga(session, slug):
    payload = {
        "operationName": "fetchManga",
        "variables": {
            "slug": slug
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "6d8b28abb9a9ee3199f6553d8f0a61c005da8f5c56a88ebcf3778eff28d45bd5"
            }
        }
    }
    async with session.post(api_url, json=payload,headers=headers) as response:
        return await response.json()

def extract_info_fetchManga(data):
    manga = data['data']['manga']
    branch = data['data']['manga']['branches'][0]

    return {
        "slug": manga['slug'],
        "title_name": next(item["content"] for item in manga['titles'] if item["lang"] == "RU"),
        "chapter_count": branch['chapters'],
        "translitionStatus": manga['translitionStatus'],
        "status": manga['status'],
        "branch_id": branch['id']
    }


async def fetchMangaChapter(session, branch_id: str):
    after = None
    all_chapters = []

    while True:
        payload = {
            "operationName": "fetchMangaChapters",
            "variables": {
                "after": after,
                "branchId": branch_id,
                "number": None,
                "orderBy": {
                    "direction": "DESC",
                    "field": "NUMBER"
                }
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "8c854e121f05aa93b0c37889e732410df9ea207b4186c965c845a8d970bdcc12"
                }
            }
        }

        async with session.post(api_url, json=payload, headers=headers) as response:
            data = await response.json()

            chapters = data['data']['mangaChapters']['edges']
            all_chapters.extend(chapters)

            page_info = data['data']['mangaChapters']['pageInfo']
            if page_info['hasNextPage']:
                after = page_info['endCursor']
            else:
                break

    return {
        "data": {
            "mangaChapters": {
                "edges": all_chapters
            }
        }
    }

def extract_info_fetchMangaChapter(data):
    result = []
    edges = data['data']['mangaChapters']['edges']

    for edge in edges:
        node = edge['node']
        result.append({
            'slug': node['slug'],
            'number': node['number'],
            'volume': node['volume']
        })
    
    return result


async def fetchMangaChapterImage(session, slug):
    payload = {
        "operationName": "fetchMangaChapter",
        "variables": {
            "cdnQuality": "auto",
            "slug": slug
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash":   "320a2637126c71ccdbce6af04325fe2f5878cc7adf9e90d06bdd6752f9bbb14e"
            }
        }
    }   
    async with session.post(api_url, json=payload, headers=headers) as response:
            return await response.json()

def extract_info_fetchMangaChapterImageOriginal(data):
    pages = data['data']['mangaChapter']['pages']
    list = []
    for page in pages:
        list.append(page['image']['original']['url'])
    return list


#общ функция
def downloaded_chapter(title_name: str, download_dir: str) -> int:
    # Путь к общему архиву
    complete_zip_path = os.path.join(download_dir, f"{title_name}__complete.zip")
    if os.path.isfile(complete_zip_path):
        try:
            with zipfile.ZipFile(complete_zip_path, 'r') as zipf:
                chapter_dirs = set()
                for name in zipf.namelist():
                    parts = name.split('/')
                    # Ищем: title_name/volume_X__chapter_Y/
                    if len(parts) >= 2 and parts[0] == title_name:
                        chapter_folder = parts[1]
                        if chapter_folder.startswith("volume_") and "__chapter_" in chapter_folder:
                            chapter_dirs.add(chapter_folder)
                return len(chapter_dirs)
        except Exception as e:
            print(f"⚠️ Не удалось прочитать общий архив: {e}")
            return 0

    # Если общего архива нет — ищем отдельные архивы
    folder = os.path.join(download_dir, title_name)
    if not os.path.isdir(folder):
        return 0

    return sum(
        1 for file in os.listdir(folder)
        if file.endswith(".zip") and file.startswith("volume_")
    )

def sanitize_filename(name):
    # Заменяет все недопустимые символы на "_"
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().rstrip('.')

async def download_chapter_images(image_urls, session, title_name, volume, chapter, max_concurrent=max_concurrent, max_retries=max_retries):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_image(url, idx):
        for attempt in range(1, max_retries + 1):
            try:
                async with semaphore:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".jpg"
                            filename = f"{title_name}/volume_{volume}__chapter_{chapter}/{idx}{ext}"
                            #print(f"📥 Скачиваю {filename}")
                            return filename, data
                        else:
                            print(f"⚠️ Попытка {attempt}: не удалось скачать {url} (status {resp.status})")
            except Exception as e:
                print(f"❌ Попытка {attempt}: ошибка при скачивании {url}: {e}")


            if attempt < max_retries:
                print(f"🔁 Повторная попытка через {latency} секунд...")
                await asyncio.sleep(latency)

        print(f"❌ Провалено после {max_retries} попыток: {url}")
        return None

    tasks = [fetch_image(url, idx) for idx, url in enumerate(image_urls, 1)]
    results = await asyncio.gather(*tasks)

    return {
        filename: data for result in results if result
        for filename, data in [result]
    }


async def handle_chapter(images: dict, title_name: str, volume: int, chapter: int, 
                         is_complete: bool, collected_images: dict = None):
    safe_title = sanitize_filename(title_name)
    save_dir = os.path.join(PATH, safe_title)
    os.makedirs(save_dir, exist_ok=True)

    if is_complete:
        # Собираем все главы в память
        collected_images.update(images)
        print(f"📦 Глава {volume}-{chapter} добавлена в общий архив")
    else:
        # Сохраняем в отдельный архив
        archive_name = f"volume_{volume}__chapter_{chapter}.zip"
        archive_path = os.path.join(save_dir, archive_name)

        if os.path.exists(archive_path):
            print(f"⏭️ Пропущено: {archive_name} уже существует.")
            return

        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, 'w', zipfile.ZIP_STORED) as zipf:
            for filename, data in images.items():
                zipf.writestr(filename, data)

        with open(archive_path, 'wb') as f:
            f.write(archive_bytes.getvalue())

        print(f"✅ Глава сохранена: {archive_path}")

async def download_all_chapters(chapter_list, session, title_name, fetchManga_, max_concurrent=5):
    is_complete = (
        fetchManga_.get('status') == 'FINISHED' and 
        fetchManga_.get('translitionStatus') == 'FINISHED'
    )

    collected_images = {} if is_complete else None

    for ch in chapter_list:
        volume = ch["volume"]
        number = ch["number"]
        chapter_slug = ch["slug"]

        # Получаем image_urls прямо здесь
        image_data = await fetchMangaChapterImage(session, chapter_slug)
        image_urls = extract_info_fetchMangaChapterImageOriginal(image_data)

        # Скачиваем изображения этой главы
        images = await download_chapter_images(image_urls, session,title_name, volume, number, max_concurrent)

        # Сохраняем главу (отдельно или в общий архив)
        await handle_chapter(images, title_name, volume, number, is_complete, collected_images)

    # Если манга завершена — архивируем всё в один файл
    if is_complete:
        safe_title = sanitize_filename(title_name)
        archive_path = os.path.join(PATH, f"{safe_title}__complete.zip")

        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, 'w', zipfile.ZIP_STORED) as zipf:
            for filename, data in collected_images.items():
                zipf.writestr(filename, data)

        with open(archive_path, 'wb') as f:
            f.write(archive_bytes.getvalue())

        print(f"🎉 Вся манга сохранена в один архив: {archive_path}")



def update_manga_json(slug, fetchManga_data, domain):
    if not os.path.exists(JSON_FILE) or os.stat(JSON_FILE).st_size == 0:
        data = {}
    else:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    
    if domain not in data or not isinstance(data[domain], list):
        data[domain] = []

    info = fetchManga_data['data']['manga']
    title_name = next(item["content"] for item in info['titles'] if item["lang"] == "RU")

    new_data = {
        "title_name": title_name,
        "slug": info['slug'],
        "translitionStatus": info['translitionStatus'],
        "status": info['status'],
        "available_chapters": info['branches'][0]['chapters'],
        "downloaded_chapter": downloaded_chapter(title_name, PATH)
    }

    found = False
    for manga in data[domain]:
        if manga.get("slug") == slug:
            found = True
            print(f"✅ Найдено совпадение: {manga['slug']}. Обновляю данные.")
            manga.update(new_data)
            break

    if not found:
        print(f"➕ Добавляю новую мангу: {new_data['title_name']}")
        data[domain].append(new_data)

    # Сохранение
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    return

def isDownload(slug, domain):
    if not os.path.exists(JSON_FILE) or os.stat(JSON_FILE).st_size == 0:
        data = {}
    else:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    if domain not in data or not isinstance(data[domain], list):
        data[domain] = []

    for manga in data[domain]:
        if manga.get("slug") == slug and manga.get('chapter_count')==manga.get('downloaded_chapter'):
            return True
    return False
            
async def main(slugs):
    if slugs == None:
        return
    for slug in slugs:
        async with aiohttp.ClientSession() as session:
            fetchManga_data = await fetchManga(session, slug)
            fetchManga_ = extract_info_fetchManga(fetchManga_data)

            branch_id = fetchManga_['branch_id']
            title_name = fetchManga_['title_name']

            fetchMangaChapter_data = await fetchMangaChapter(session, branch_id)
            chapter_list = extract_info_fetchMangaChapter(fetchMangaChapter_data)

            #update_manga_json(slug, fetchManga_data, domain)

            if isDownload(slug, domain):
                print(f"✅ Все {fetchManga_['chapter_count']} глав(ы) «{fetchManga_['title_name']}» уже скачены.")
                continue

            await download_all_chapters(chapter_list, session, title_name, fetchManga_)

            # Обновление json после скачивания
            update_manga_json(slug, fetchManga_data, domain)
