import re, os, zipfile
import asyncio
import aiohttp

import config


website = 'mangalib.org'
parameters = "?fields[]=background&fields[]=moderated&fields[]=manga_status_id&fields[]=chap_count&fields[]=status_id"
api_url = "https://api.cdnlibs.org/api/manga/"
server_one = "https://img2.imglib.info"
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

# ---- UTILS ----
def get_rus_titile_name(result_query_fields):
    raw = result_query_fields["data"]['rus_name']
    return re.sub(r'[\\/:*?"<>|]', '', raw).strip().rstrip('.')

def get_number_to_url(result_num_vol, result_slug_url):
    return [(vol, num, f"{api_url}{result_slug_url}/chapter?number={num}&volume={vol}") for vol, num in result_num_vol]

def is_chapter_downloaded(manga_dir, vol, ch):
    archive_path = os.path.join(manga_dir, f"volume_{vol}__chapter_{ch}.zip")
    return os.path.exists(archive_path)

# ---- ASYNC FETCH ----
async def fetch(session, url):
    async with session.get(url, headers=HEADERS, timeout=10) as response:
        response.raise_for_status()
        return await response.json()

# ---- DOWNLOAD ----
async def download_single_image(session, idx, image_url):
    filename = f"{idx}.jpg"
    for attempt in range(1, config.ATTEMP + 1):
        try:
            async with session.get(image_url, headers=HEADERS, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.read()
                print(filename)
                return filename, data
        except Exception as e:
            print(f"[{attempt}/{config.ATTEMP}] ❌ Ошибка при загрузке {image_url}: {e}")
            await asyncio.sleep(config.TIME_OUT)
    print(f"⚠️ Не удалось скачать: {image_url}")
    return filename, None

def save_images_as_zip(images_dict, output_path):
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_STORED) as zipf:
        for name, data in sorted(images_dict.items()):
            zipf.writestr(name, data)
    print(f"📦 Архив сохранён: {output_path}")

async def download_images_to_memory(session, image_links):
    images = {}
    sem = asyncio.Semaphore(config.WORKER)
    async def download_with_sem(idx, url):
        async with sem:
            return await download_single_image(session, idx, url)

    tasks = [asyncio.create_task(download_with_sem(idx, url)) for idx, url in enumerate(image_links, start=1)]
    for task in asyncio.as_completed(tasks):
        filename, data = await task
        if data:
            images[filename] = data
    return images

async def download_and_save_chapter(session, url, manga_dir, vol, ch):
    print(f"⬇️ Загрузка главы: Том {vol}, Глава {ch}")
    query = await fetch(session, url)
    image_links = [f"{server_one}{p['url']}" for p in query['data']['pages']]
    images = await download_images_to_memory(session, image_links)

    if len(images) != len(image_links):
        print(f"⚠️ Загружено {len(images)} из {len(image_links)}. Пропуск.")
        return

    archive_path = os.path.join(manga_dir, f"volume_{vol}__chapter_{ch}.zip")
    save_images_as_zip(images, archive_path)
    print(f"✅ Сохранено: {archive_path}")

# ---- PROCESS ----
def get_num_vol(result_query_chapters, max_item_count):
    result = ()
    for i in range(max_item_count):
        chapter = result_query_chapters['data'][i]
        branch = chapter['branches'][0]

        expired = branch.get('expired_type', 0)
        restricted = branch.get('restricted_view')
        moderation = branch.get('moderation', {})
        label = moderation.get('label')

        if label == "На модерации":
            continue
        if expired == 0 or (expired == 1 and restricted is None):
            result += ((chapter['volume'], chapter['number']),)
    return result

# ---- COUNT DOWNLOADED ---- 
def get_downloaded_item_count(result_query_fields): 
    folder_path = os.path.join(config.PATH, get_rus_titile_name(result_query_fields)) 
    if not os.path.isdir(folder_path): 
        return 0 
    return sum(1 for f in os.listdir(folder_path) if f.endswith('.zip'))

# ---- INIT DOWNLOAD ----
async def init(links):

    async with aiohttp.ClientSession() as session:
        for slug in links:
            query_chapters = f'{api_url}{slug}/chapters'
            query_fields = f'{api_url}{slug}{parameters}'

            result_query_chapters = await fetch(session, query_chapters)
            result_query_fields = await fetch(session, query_fields)

            max_count_item = result_query_fields["data"]['items_count']['uploaded']
            result_num_vol = get_num_vol(result_query_chapters, max_count_item)

            manga_title = get_rus_titile_name(result_query_fields)
            manga_dir = os.path.join(config.PATH, manga_title)
            os.makedirs(manga_dir, exist_ok=True)


            print(f"📘 Manga: {manga_title}, Глав: {len(result_num_vol)}")
            chapters_data = get_number_to_url(result_num_vol, slug)

            for vol, ch, api_link in chapters_data:
                if is_chapter_downloaded(manga_dir, vol, ch):
                    print(f"✅ Пропуск: Том {vol} Глава {ch} уже скачана")
                    continue
                await download_and_save_chapter(session, api_link, manga_dir, vol, ch)

# ---- RUN ----
slugs = [
    "222308--mujigaeleul-boneun-cheonjaemabeobsa"
]


asyncio.run(init(slugs))
