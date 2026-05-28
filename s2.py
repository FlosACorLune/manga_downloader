import asyncio
import os
import httpx
import zipfile
import re
from dotenv import load_dotenv
import config
import utils
import subprocess
import tempfile


PATH = config.PATH
CJXL_PATH = "cjxl"
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

async def transcode_to_jxl(image_data: bytes, ext: str) -> bytes:
    if ext.lower() == 'jxl':
        return image_data

    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as infile, \
         tempfile.NamedTemporaryFile(suffix=".jxl", delete=False) as outfile:
        
        infile_name = infile.name
        outfile_name = outfile.name
        
        try:
            infile.write(image_data)
            infile.flush()
            infile.close()
            outfile.close()

            command = [CJXL_PATH, infile_name, outfile_name]
            if ext.lower() in ['jpg', 'jpeg']:
                command.extend(["-d", "0", "--effort", "7"])
            elif ext.lower() == 'png':
                command.extend(["-d", "0", "--effort", "7"])

            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                print(f"❌ Ошибка cjxl: {stderr.decode()}")
                return image_data

            with open(outfile_name, "rb") as f:
                return f.read()
        finally:
            for temp_file in [infile_name, outfile_name]:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

async def fetchManga(client: httpx.AsyncClient, slug: str):
    payload = {
        "operationName": "fetchManga",
        "variables": {"slug": slug},
        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": "6d8b28abb9a9ee3199f6553d8f0a61c005da8f5c56a88ebcf3778eff28d45bd5"}}
    }
    response = await client.post(api_url, json=payload)
    response.raise_for_status()
    return response.json()

def extract_info_fetchManga(data):
    manga = data['data']['manga']
    branch = manga['branches'][0]
    title_name = next((item["content"] for item in manga['titles'] if item["lang"] == "RU"), manga['titles'][0]['content'])
    return {"slug": manga['slug'], "title_name": title_name, "branch_id": branch['id']}

async def fetchMangaChapter(client: httpx.AsyncClient, branch_id: str):
    after, all_chapters = None, []
    while True:
        payload = {
            "operationName": "fetchMangaChapters",
            "variables": {"after": after, "branchId": branch_id, "orderBy": {"direction": "ASC", "field": "NUMBER"}},
            "extensions": {"persistedQuery": {"version": 1, "sha256Hash": "8c854e121f05aa93b0c37889e732410df9ea207b4186c965c845a8d970bdcc12"}}
        }
        response = await client.post(api_url, json=payload)
        data = response.json()
        all_chapters.extend(data['data']['mangaChapters']['edges'])
        page_info = data['data']['mangaChapters']['pageInfo']
        if not page_info['hasNextPage']: break
        after = page_info['endCursor']
    return all_chapters

async def fetchMangaChapterImage(client: httpx.AsyncClient, slug: str):
    payload = {
        "operationName": "fetchMangaChapter",
        "variables": {"cdnQuality": "auto", "slug": slug},
        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": "8e166106650d3659d21e7aadc15e7e59e5def36f1793a9b15287c73a1e27aa50"}}
    }
    response = await client.post(api_url, json=payload)
    return response.json()

async def download_chapter_images(image_urls, client: httpx.AsyncClient):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_image(url, idx):
        for attempt in range(1, max_retries + 1):
            try:
                async with semaphore:
                    response = await client.get(url, timeout=latency)
                    if response.status_code == 200:
                        content = response.content
                        ext = utils.get_image_type(content)
                        
                        if ext in ['jpg', 'jpeg', 'png']:
                            content = await transcode_to_jxl(content, ext)
                            filename = f"{idx:03}.jxl"
                        else:
                            filename = f"{idx:03}.{ext}"
                        
                        return filename, content
            except Exception as e:
                if attempt == max_retries: print(f"❌ Провал {url}: {e}")
            await asyncio.sleep(latency)
        return None

    tasks = [fetch_image(url, idx) for idx, url in enumerate(image_urls, 1)]
    results = await asyncio.gather(*tasks)
    return {res[0]: res[1] for res in results if res}

async def save_images_as_zip(images: dict, title_name: str, volume: int, chapter: int):
    if not images: return
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title_name).strip().rstrip('.')
    save_dir = os.path.join(PATH, safe_title)
    os.makedirs(save_dir, exist_ok=True)
    archive_path = os.path.join(save_dir, f"volume_{volume}__chapter_{chapter}.zip")
    
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_STORED) as zipf:
        for filename, data in sorted(images.items()):
            zipf.writestr(filename, data)
    print(f"✅ Глава сохранена: {archive_path}")

async def main(slugs):
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20.0) as client:
        for slug in slugs:
            try:
                manga_data = await fetchManga(client, slug)
                info = extract_info_fetchManga(manga_data)
                print(f"📖 Обработка: {info['title_name']}")

                chapters = await fetchMangaChapter(client, info['branch_id'])
                for edge in chapters:
                    node = edge['node']
                    if os.path.exists(os.path.join(PATH, info['title_name'], f"volume_{node['volume']}__chapter_{node['number']}.zip")):
                        continue

                    print(f"🚀 Качаю главу {node['number']}...")
                    img_data = await fetchMangaChapterImage(client, node['slug'])
                    urls = [p['image']['original']['url'] for p in img_data['data']['mangaChapter']['pages']]
                    images = await download_chapter_images(urls, client)
                    await save_images_as_zip(images, info['title_name'], node['volume'], node['number'])
            except Exception as e:
                print(f"🛑 Ошибка на {slug}: {e}")

if __name__ == "__main__":
    asyncio.run(main(["toshi-to-mahou-wa-kiss-shidai"]))