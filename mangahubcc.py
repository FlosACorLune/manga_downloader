import os
import re
import asyncio
import httpx
from bs4 import BeautifulSoup

import config
import utils

semaphore = asyncio.Semaphore(config.WORKER)

async def get_soup(client, url):
    response = await client.get(url, follow_redirects=True)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')

def extract_image_links(soup):
    reader_pages = soup.find('div', class_='pages_placer')
    img_tags = reader_pages.find_all('img') if reader_pages else []
    return [img.get('src') or img.get('data-src') for img in img_tags if img.get('src') or img.get('data-src')]

async def download_single_image(client, idx, image_url):
    ext = os.path.splitext(image_url.split("?")[0])[1][1:] or "webp"
    filename = f"{idx}.{ext}"

    async with semaphore:
        for attempt in range(1, config.ATTEMP + 1):
            try:
                response = await client.get(image_url, timeout=20)
                response.raise_for_status()
                return filename, response.content

            except httpx.HTTPError as e:
                print(f"[{attempt}/{config.ATTEMP}] Ошибка {image_url}: {e}")
                if attempt < config.ATTEMP:
                    await asyncio.sleep(2)
    
    print(f"Не удалось скачать: {image_url}")
    return filename, None

async def download_images_to_memory(client, image_links):
    tasks = [download_single_image(client, idx, url) for idx, url in enumerate(image_links, start=1)]
    
    results = await asyncio.gather(*tasks)
    
    return {filename: data for filename, data in results if data}

def title_name(soup):
    title_div = soup.find("div", class_="title_head_name")
    raw = title_div.get_text(strip=True) if title_div else (soup.find("h1").get_text(strip=True) if soup.find("h1") else "Unknown")
    return re.sub(r'[\\/:*?"<>|]', '', raw).strip().rstrip('.')

def extract_vol_ch(soup):
    chapters = []
    for tag in soup.find_all('div', class_='chapter_block_inner'):
        vol_tag = tag.find('div', class_='chapter_volume')
        ch_tag = tag.find('div', class_='chapter_number')

        volume_match = re.search(r'\d+', vol_tag.text) if vol_tag else None
        chapter_match = re.search(r'\d+(?:\.\d+)?', ch_tag.text) if ch_tag else None

        if volume_match and chapter_match:
            chapters.append((volume_match.group(), chapter_match.group()))
    return chapters

async def download_and_store_chapter(client, link, manga_dir, vol, ch):
    archive_name = f"volume_{vol}__chapter_{ch}.zip"
    archive_path = os.path.join(manga_dir, archive_name)

    if os.path.exists(archive_path):
        print(f"Пропуск: {archive_name}")
        return

    chapter_url = f"{link}/v{vol}/c{ch}"
    print(f"Скачивание: Том {vol}, Глава {ch}")

    try:
        soup = await get_soup(client, chapter_url)
        image_links = extract_image_links(soup)
        images = await download_images_to_memory(client, image_links)

        if len(images) != len(image_links):
            print(f"Глава неполная ({len(images)}/{len(image_links)}), пропуск")
            return

        utils.save_images_as_zip(images, archive_path)
    except Exception as e:
        print(f"Ошибка при обработке главы {vol} {ch}: {e}")

async def init(links):
    async with httpx.AsyncClient(http2=True, limits=httpx.Limits(max_connections=100)) as client:
        for link in links:
            soup = await get_soup(client, link)
            manga_title = title_name(soup)
            manga_dir = os.path.join(config.PATH, manga_title)

            print(f"Манга: {manga_title}")
            os.makedirs(manga_dir, exist_ok=True)

            chapters = extract_vol_ch(soup)
            print(f"Глав найдено: {len(chapters)}")

            for vol, ch in chapters:
                await download_and_store_chapter(client, link, manga_dir, vol, ch)

if __name__ == "__main__":
    slugs = ["https://mangahub.cc/manga/I-m-the-villainess-in-a-martial-arts-novel--but-I-m-the-strongest"]
    asyncio.run(init(slugs))