import asyncio
import os
import re
import utils
import httpx 
import config 

website = "mangalib.org"
parameters = "?fields[]=background&fields[]=moderated&fields[]=manga_status_id&fields[]=chap_count&fields[]=status_id"
api_url = "https://api.cdnlibs.org/api/manga/"
server_one = "https://img2.imglib.info"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://mangalib.org",
    "Referer": "https://mangalib.org/",
    "Site-Id": "1",
    "Client-Time-Zone": "Asia/Yekaterinburg",
}


def get_rus_titile_name(result_query_fields):
    raw = result_query_fields["data"]["rus_name"]
    return re.sub(r'[\\/:*?"<>|]', "", raw).strip().rstrip(".")

def get_number_to_url(result_num_vol, result_slug_url):
    return [
        (vol, num, f"{api_url}{result_slug_url}/chapter?number={num}&volume={vol}")
        for vol, num in result_num_vol
    ]

def is_chapter_downloaded(manga_dir, vol, ch):
    archive_path = os.path.join(manga_dir, f"volume_{vol}__chapter_{ch}.zip")
    return os.path.exists(archive_path)


async def fetch(client, url):
    response = await client.get(url, timeout=10.0)
    response.raise_for_status()
    return response.json()


async def download_single_image(client, idx, image_url):
    filename = None
    for attempt in range(1, config.ATTEMP + 1):
        try:
            resp = await client.get(image_url, timeout=10.0)
            resp.raise_for_status()
            
            data = resp.content
            ext = utils.get_image_type(data)
            filename = f"{idx}.{ext}"
            
            await asyncio.sleep(config.DELAY)
            return filename, data
        except Exception as e:
            print(f"[{attempt}/{config.ATTEMP}] ERROR - Ошибка при загрузке {image_url}: {e}")
            await asyncio.sleep(config.TIME_OUT)
            
    print(f"WARNING - Не удалось скачать: {image_url}")
    return filename, None

async def download_images_to_memory(client, image_links):
    images = {}
    sem = asyncio.Semaphore(config.WORKER)

    async def download_with_sem(idx, url):
        async with sem:
            return await download_single_image(client, idx, url)

    tasks = [
        asyncio.create_task(download_with_sem(idx, url))
        for idx, url in enumerate(image_links, start=1)
    ]
    
    for task in asyncio.as_completed(tasks):
        filename, data = await task
        if data:
            images[filename] = data
    return images

async def download_and_save_chapter(client, url, manga_dir, vol, ch):
    print(f"⬇️ Загрузка главы: Том {vol}, Глава {ch}")
    try:
        query = await fetch(client, url)
        image_links = [f"{server_one}{p['url']}" for p in query["data"]["pages"]]
        images = await download_images_to_memory(client, image_links)

        if len(images) != len(image_links):
            print(f"WARNING - Загружено {len(images)} из {len(image_links)}. Пропуск.")
            return

        archive_path = os.path.join(manga_dir, f"volume_{vol}__chapter_{ch}.zip")
        utils.save_images_as_zip(images, archive_path)
        print(f"INFO - Сохранено: {archive_path}")
    except Exception as e:
        print(f"ERROR - Критическая ошибка в главе {vol}-{ch}: {e}")


def get_num_vol(result_query_chapters, max_item_count):
    result = []

    actual_count = min(max_item_count, len(result_query_chapters["data"]))
    
    for i in range(actual_count):
        chapter = result_query_chapters["data"][i]
        if not chapter.get("branches"):
            continue
            
        branch = chapter["branches"][0]
        expired = branch.get("expired_type", 0)
        restricted = branch.get("restricted_view")
        moderation = branch.get("moderation", {})
        label = moderation.get("label")

        if label == "На модерации":
            continue
        if expired == 0 or (expired == 1 and restricted is None):
            result.append((chapter["volume"], chapter["number"]))
    return tuple(result)

async def init(links):
    async with httpx.AsyncClient(headers=HEADERS, http2=True) as client:
        for slug in links:
            try:
                query_chapters_url = f"{api_url}{slug}/chapters"
                query_fields_url = f"{api_url}{slug}{parameters}"

                result_query_chapters = await fetch(client, query_chapters_url)
                result_query_fields = await fetch(client, query_fields_url)

                max_count_item = result_query_fields["data"]["items_count"]["uploaded"]
                result_num_vol = get_num_vol(result_query_chapters, max_count_item)

                manga_title = get_rus_titile_name(result_query_fields)
                manga_dir = os.path.join(config.PATH, manga_title)
                os.makedirs(manga_dir, exist_ok=True)

                print(f"\nINFO - Manga: {manga_title}, Глав к скачиванию: {len(result_num_vol)}")
                chapters_data = get_number_to_url(result_num_vol, slug)

                for vol, ch, api_link in chapters_data:
                    if is_chapter_downloaded(manga_dir, vol, ch):
                        print(f"INFO - Пропуск: Том {vol} Глава {ch} уже скачана")
                        continue
                    await download_and_save_chapter(client, api_link, manga_dir, vol, ch)
            except Exception as e:
                print(f"ERROR - Ошибка при обработке тайтла {slug}: {e}")

# ---- RUN ----
if __name__ == "__main__":
    slugs = [
        "144725--betelang-byeongsaui-hwansaeng"
    ]
    asyncio.run(init(slugs))