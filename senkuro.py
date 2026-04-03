import asyncio
import os
import aiohttp
import zipfile
import re
from dotenv import load_dotenv
import config
import utils


PATH = config.PATH
max_concurrent = config.WORKER
max_retries = config.ATTEMP
latency = config.TIME_OUT
load_dotenv()
SENKURO_TOKEN = os.getenv("SENKURO_TOKEN")

api_url = 'https://api.senkuro.me/graphql'
#api_url = 'https://api.senkognito.com/graphql'
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
    "authorization": SENKURO_TOKEN
}

async def fetchManga(session, slug):
    PAYLOAD_MANGA = {
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
    async with session.post(api_url, json=PAYLOAD_MANGA,headers=HEADERS) as response:
        return await response.json()

def extract_info_fetchManga(data):
    manga = data['data']['manga']
    branch = data['data']['manga']['branches'][0]

    return {
        "slug": manga['slug'],
        "title_name": next(item["content"] for item in manga['titles'] if item["lang"] == "RU"),
        "chapter_count": branch['chapters'],
        "branch_id": branch['id']
    }


async def fetchMangaChapter(session, branch_id: str):
    after = None
    all_chapters = []

    while True:
        PAYLOAD_CHAPTER = {
            "operationName": "fetchMangaChapters",
            "variables": {
                "after": after,
                "branchId": branch_id,
                "number": None,
                "orderBy": {
                    "direction": "ASC",
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

        async with session.post(api_url, json=PAYLOAD_CHAPTER, headers=HEADERS) as response:
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

def extract_info_fetchMangaChapter(data) -> list:
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
    PAYLOAD_IMAGE = {
        "operationName": "fetchMangaChapter",
        "variables": {
            "cdnQuality": "auto",
            "slug": slug
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "8e166106650d3659d21e7aadc15e7e59e5def36f1793a9b15287c73a1e27aa50"
            }
        }
    }   
    async with session.post(api_url, json=PAYLOAD_IMAGE, headers=HEADERS) as response:
            return await response.json()

def extract_info_fetchMangaChapterImageOriginal(data):
    pages = data['data']['mangaChapter']['pages']
    list = []
    for page in pages:
        list.append(page['image']['original']['url'])
    return list


#общ функция
def downloaded_chapter(title_name: str, download_dir: str) -> int:
    folder = os.path.join(download_dir, title_name)
    if not os.path.isdir(folder):
        return 0

    # Считаем только ZIP файлы с главами
    return sum(
        1 for file in os.listdir(folder)
        if file.endswith(".zip") and file.startswith("volume_")
    )


async def download_chapter_images(image_urls, session, max_concurrent=max_concurrent, max_retries=max_retries):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_image(url, idx):
        for attempt in range(1, max_retries + 1):
            try:
                async with semaphore:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            ext = utils.get_image_type(data)
                            filename = f"{idx}.{ext}"       
                                                 
                            await asyncio.sleep(config.DELAY)
                            
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


async def save_images_as_zip(images: dict, title_name: str, volume: int, chapter: int):
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
    save_dir = os.path.join(PATH, safe_title)
    archive_name = f"volume_{volume}__chapter_{chapter}.zip"
    archive_path = os.path.join(save_dir, archive_name)
    return os.path.exists(archive_path)


async def download_all_chapters(chapter_list, session, title_name, max_concurrent=5):
    for ch in chapter_list:
        volume = ch["volume"]
        number = ch["number"]
        chapter_slug = ch["slug"]

        # Проверяем, есть ли глава локально
        if chapter_exists(title_name, volume, number):
            print(f"⏭️ Пропущено: volume {volume} chapter {number} уже скачана.")
            continue

        # Получаем image_urls
        image_data = await fetchMangaChapterImage(session, chapter_slug)
        image_urls = extract_info_fetchMangaChapterImageOriginal(image_data)

        # Скачиваем изображения этой главы
        images = await download_chapter_images(image_urls, session, max_concurrent)

        # Сохраняем главу отдельно
        await save_images_as_zip(images, title_name, volume, number)


async def main(slugs):
    for slug in slugs:
        async with aiohttp.ClientSession() as session:
            fetchManga_data = await fetchManga(session, slug)
            fetchManga_ = extract_info_fetchManga(fetchManga_data)

            branch_id = fetchManga_['branch_id']
            title_name = fetchManga_['title_name']

            # Список глав с сервера
            fetchMangaChapter_data = await fetchMangaChapter(session, branch_id)
            chapter_list = extract_info_fetchMangaChapter(fetchMangaChapter_data)

            server_count = len(chapter_list)
            local_count = downloaded_chapter(title_name, PATH)

            print(f"📊 На сервере {server_count} глав, локально {local_count}")

            # Скачиваем только недостающие
            await download_all_chapters(chapter_list, session, title_name)

            # Проверка после скачивания
            final_count = downloaded_chapter(title_name, PATH)
            if final_count == server_count:
                print(f"✅ Все {final_count}/{server_count} глав скачаны: {title_name}")
            else:
                print(f"⚠️ Недостающие главы остались: {final_count}/{server_count} скачано")




slugs = [
    "today-is-a-woman-day",
    #"akuyaku-reijou-to-kichiku-kishi",
    #"reverend-insanity-2025",
    #"eiketsu-no-do-m-juuzoku-keiken-chiito-tte-ari",
    #"akuyaku-reijou-slow-life-wo-enjoy-shitai-yatto-konyaku-haki-sareta-noni-dai-2-ouji-ga-meccha-stalker-shitekurun-desu-kedo",
    "wo-de-shifu-mei-dao-daxian-cai-tupo",
    "my-bias-gets-on-the-last-train",
    "star-fostered-swordmaster",
    "segye-choegoui-enjinieo",
    "i-will-die-soon", #завершен
    "the-girl-downstairs",
    "legend-of-the-holy-sword",
    "emperor-hunt",
    "she-s-hopeless",
    "couple-breaker",
    "escort-warrior", #завершен
    "agdang-i-sal-aganeun-beob",
    "musamanlihaeng",
    "delusion", #завершен
    "gijamae",
    "black-innocence-diary", #завершен
    "the-war-of-corpses",
    "everyone-loves-her",
    "unemployed-gye-baek-soon",
    "the-road-of-karma", #завершен
    "the-marshal-king",
    "ghostblade",
    "peulreieo",
    "deo-bogseo", #завершен
    "yeobchongsonyeon", #завершен
    "seuwiteu-hom", #завершен
    "hulejasig", #завершен
    "cheonchijeonneung", #finished
    "my-office-noona-s-stories", 
    "ssaumdokak", #finished
    "the-knight-king-who-returned-with-a-god",
    "the-old-prisoner-lives-in-solitude",
    "the-returned-c-rank-tank-won-t-die",
    "fated-to-be-loved-by-villains"
]

slugs = [
    "full-metal-panic-comic-mission"
]


asyncio.run(main(slugs))