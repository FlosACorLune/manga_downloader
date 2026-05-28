import asyncio
import os
import httpx
import zipfile
import re
from dotenv import load_dotenv
import config
import utils

# Загрузка конфигурации
PATH = config.PATH
max_concurrent = config.WORKER
max_retries = config.ATTEMP
latency = config.TIME_OUT
load_dotenv()
SENKURO_TOKEN = os.getenv("SENKURO_TOKEN")

api_url = 'https://api.senkuro.me/graphql'
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
}

async def fetchManga(client: httpx.AsyncClient, slug: str):
    payload = {
        "operationName": "fetchManga",
        "variables": {"slug": slug},
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "6d8b28abb9a9ee3199f6553d8f0a61c005da8f5c56a88ebcf3778eff28d45bd5"
            }
        }
    }
    response = await client.post(api_url, json=payload)
    response.raise_for_status()
    return response.json()

def extract_info_fetchManga(data):
    manga = data['data']['manga']
    # Берем первую доступную ветку (branch)
    branch = manga['branches'][0]
    
    # Ищем русское название, если нет — берем первое доступное
    title_name = next((item["content"] for item in manga['titles'] if item["lang"] == "RU"), manga['titles'][0]['content'])
    
    return {
        "slug": manga['slug'],
        "title_name": title_name,
        "chapter_count": branch['chapters'],
        "branch_id": branch['id']
    }

async def fetchMangaChapter(client: httpx.AsyncClient, branch_id: str):
    after = None
    all_chapters = []

    while True:
        payload = {
            "operationName": "fetchMangaChapters",
            "variables": {
                "after": after,
                "branchId": branch_id,
                "number": None,
                "orderBy": {"direction": "ASC", "field": "NUMBER"}
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "8c854e121f05aa93b0c37889e732410df9ea207b4186c965c845a8d970bdcc12"
                }
            }
        }

        response = await client.post(api_url, json=payload)
        response.raise_for_status()
        data = response.json()

        chapters = data['data']['mangaChapters']['edges']
        all_chapters.extend(chapters)

        page_info = data['data']['mangaChapters']['pageInfo']
        if page_info['hasNextPage']:
            after = page_info['endCursor']
        else:
            break

    return {"data": {"mangaChapters": {"edges": all_chapters}}}

def extract_info_fetchMangaChapter(data) -> list:
    return [
        {
            'slug': edge['node']['slug'],
            'number': edge['node']['number'],
            'volume': edge['node']['volume']
        }
        for edge in data['data']['mangaChapters']['edges']
    ]

async def fetchMangaChapterImage(client: httpx.AsyncClient, slug: str):
    payload = {
        "operationName": "fetchMangaChapter",
        "variables": {"cdnQuality": "auto", "slug": slug},
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "8e166106650d3659d21e7aadc15e7e59e5def36f1793a9b15287c73a1e27aa50"
            }
        }
    }   
    response = await client.post(api_url, json=payload)
    response.raise_for_status()
    return response.json()

def extract_info_fetchMangaChapterImageOriginal(data):
    pages = data['data']['mangaChapter']['pages']
    return [page['image']['original']['url'] for page in pages]

def downloaded_chapter(title_name: str, download_dir: str) -> int:
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title_name).strip().rstrip('.')
    folder = os.path.join(download_dir, safe_title)
    if not os.path.isdir(folder):
        return 0
    return sum(1 for f in os.listdir(folder) if f.endswith(".zip") and f.startswith("volume_"))

async def download_chapter_images(image_urls, client: httpx.AsyncClient, max_concurrent=max_concurrent):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_image(url, idx):
        for attempt in range(1, max_retries + 1):
            try:
                async with semaphore:
                    response = await client.get(url, timeout=latency)
                    if response.status_code == 200:
                        content = response.content
                        ext = utils.get_image_type(content)
                        filename = f"{idx}.{ext}"
                        await asyncio.sleep(config.DELAY)
                        return filename, content
                    else:
                        print(f"⚠️ Попытка {attempt}: Ошибка {response.status_code} для {url}")
            except Exception as e:
                print(f"❌ Попытка {attempt}: Ошибка при скачивании {url}: {e}")

            if attempt < max_retries:
                await asyncio.sleep(latency)

        print(f"❌ Провалено после {max_retries} попыток: {url}")
        return None

    tasks = [fetch_image(url, idx) for idx, url in enumerate(image_urls, 1)]
    results = await asyncio.gather(*tasks)
    return {res[0]: res[1] for res in results if res}

async def save_images_as_zip(images: dict, title_name: str, volume: int, chapter: int):
    if not images:
        return

    safe_title = re.sub(r'[\\/*?:"<>|]', "", title_name).strip().rstrip('.')
    save_dir = os.path.join(PATH, safe_title)
    os.makedirs(save_dir, exist_ok=True)

    archive_name = f"volume_{volume}__chapter_{chapter}.zip"
    archive_path = os.path.join(save_dir, archive_name)

    if os.path.exists(archive_path):
        print(f"⏭️ Пропущено: {archive_name} уже существует.")
        return

    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_STORED) as zipf:
        for filename, data in images.items():
            zipf.writestr(filename, data)

    print(f"✅ Глава сохранена: {archive_path}")

def chapter_exists(title_name: str, volume: int, chapter: int) -> bool:
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title_name).strip().rstrip('.')
    archive_name = f"volume_{volume}__chapter_{chapter}.zip"
    return os.path.exists(os.path.join(PATH, safe_title, archive_name))

async def download_all_chapters(chapter_list, client, title_name):
    for ch in chapter_list:
        volume, number, slug = ch["volume"], ch["number"], ch["slug"]

        if chapter_exists(title_name, volume, number):
            print(f"⏭️ Пропущено: Том {volume} Глава {number}")
            continue

        try:
            image_data = await fetchMangaChapterImage(client, slug)
            image_urls = extract_info_fetchMangaChapterImageOriginal(image_data)
            images = await download_chapter_images(image_urls, client)
            await save_images_as_zip(images, title_name, volume, number)
        except Exception as e:
            print(f"💥 Ошибка в главе {number}: {e}")

async def main(slugs):
    # Используем один клиент для всех запросов (рекомендуется httpx)
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        for slug in slugs:
            try:
                manga_raw = await fetchManga(client, slug)
                manga_info = extract_info_fetchManga(manga_raw)
                
                title_name = manga_info['title_name']
                print(f"📖 Обработка: {title_name}")

                chapters_raw = await fetchMangaChapter(client, manga_info['branch_id'])
                chapter_list = extract_info_fetchMangaChapter(chapters_raw)

                server_count = len(chapter_list)
                local_count = downloaded_chapter(title_name, PATH)

                print(f"📊 Сервер: {server_count}, Локально: {local_count}")

                await download_all_chapters(chapter_list, client, title_name)

                final_count = downloaded_chapter(title_name, PATH)
                if final_count == server_count:
                    print(f"✅ Успешно скачано: {title_name} ({final_count}/{server_count})")
                else:
                    print(f"⚠️ Завершено с пропусками: {final_count}/{server_count}")

            except Exception as e:
                print(f"🛑 Критическая ошибка при обработке {slug}: {e}")

if __name__ == "__main__":
    slugs = ["kono-gomi-wo-nanto-yobu"]
    asyncio.run(main(slugs))