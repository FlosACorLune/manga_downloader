import asyncio
import os
import re
import httpx
from bs4 import BeautifulSoup

import config
import utils

semaphore = asyncio.Semaphore(config.WORKER)

async def get_soup(client: httpx.AsyncClient, url: str) -> BeautifulSoup:
    response = await client.get(url)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def title_name(soup: BeautifulSoup) -> str:
    t = soup.find("h1", class_="manga__name")
    if not t:
        return "Unknown_Manga"
    return re.sub(r"[\\/:*.?\"<>|]", "", t.get_text(strip=True))


def extract_vol_ch(soup: BeautifulSoup) -> list:
    out = []
    for t in soup.find_all("a", class_="chapters__item"):
        v = t.find("div", class_="chapters__volume")
        c = t.find("div", class_="chapters__value")

        vol = v.find("span").text.strip() if v and v.find("span") else ""
        ch = c.find("span").text.strip() if c and c.find("span") else ""

        if vol and ch:
            out.append((vol, ch))
    return out


async def download_single_image(client: httpx.AsyncClient, idx: int, url: str):
    async with semaphore:
        for attempt in range(1, config.ATTEMP + 1):
            try:
                response = await client.get(url, timeout=20)
                response.raise_for_status()
                
                data = response.content
                ext = utils.get_image_type(data)
                filename = f"{idx}.{ext}"
                
                if config.DELAY > 0:
                    await asyncio.sleep(config.DELAY)
                return filename, data
                
            except httpx.HTTPError as e:
                print(f"Попытка {attempt}/{config.ATTEMP} ошибка ({url}): {e}")
                if attempt < config.ATTEMP:
                    await asyncio.sleep(attempt * 1.1)
        
        print(f"Не удалось скачать: {url}")
        return None, None


async def download_and_store_chapter(client: httpx.AsyncClient, base_url: str, manga_dir: str, vol: str, ch: str):
    archive = os.path.join(manga_dir, f"volume_{vol}__chapter_{ch}.zip")

    if os.path.exists(archive):
        print(f"Пропуск (уже есть): Том {vol} Глава {ch}")
        return

    chapter_url = f"{base_url}/{vol}/{ch}"
    print(f"Обработка главы: {vol}-{ch}")

    try:
        soup = await get_soup(client, chapter_url)
        box = soup.find("div", class_="reader__pages")
        imgs_tags = box.find_all("img") if box else []
        links = [i.get("src") or i.get("data-src") for i in imgs_tags if i.get("src") or i.get("data-src")]

        if not links:
            print(f"Ссылки не найдены в главе {vol}-{ch}")
            return

        tasks = [download_single_image(client, i, u) for i, u in enumerate(links, 1)]
        results = await asyncio.gather(*tasks)

        data_map = {name: data for name, data in results if name and data}

        if len(data_map) == len(links):
            utils.save_images_as_zip(data_map, archive)
            print(f"Сохранено: Том {vol} Глава {ch}")
        else:
            print(f"Глава {vol}-{ch} скачана не полностью ({len(data_map)}/{len(links)})")

    except Exception as e:
        print(f"Ошибка в главе {vol}-{ch}: {e}")


async def process_manga(client: httpx.AsyncClient, slug_url: str):
    try:
        soup = await get_soup(client, slug_url)
        title = title_name(soup)
        
        print(f"\n=== {title} ===")
        manga_dir = os.path.join(config.PATH, title)
        os.makedirs(manga_dir, exist_ok=True)

        chapters = extract_vol_ch(soup)
        print(f"Найдено глав: {len(chapters)}")

        for vol, ch in chapters:
            await download_and_store_chapter(client, slug_url, manga_dir, vol, ch)
            
    except Exception as e:
        print(f"Ошибка при обработке манги {slug_url}: {e}")


async def main():
    slugs = [
        "https://mangabuff.ru/manga/vyzhit-v-seme-iskusnyh-otravitelei",
        "https://mangabuff.ru/manga/skazanie-hengdan"
    ]

    limits = httpx.Limits(max_connections=config.WORKER, max_keepalive_connections=10)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    async with httpx.AsyncClient(headers=headers, limits=limits, follow_redirects=True) as client:
        for slug in slugs:
            await process_manga(client, slug)
        
    print("\n🚀 Все задачи выполнены.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass