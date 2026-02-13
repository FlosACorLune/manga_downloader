import os
import re
import time
import requests
import concurrent.futures
import zipfile
from bs4 import BeautifulSoup

import config


def get_soup(url):
    response = requests.get(url)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')

def extract_image_links(soup):
    reader_pages = soup.find('div', class_='pages_placer')
    img_tags = reader_pages.find_all('img') if reader_pages else []
    return [img.get('src') or img.get('data-src') for img in img_tags if img.get('src') or img.get('data-src')]


def download_single_image(idx, image_url):
    ext = os.path.splitext(image_url.split("?")[0])[1][1:] or "webp"
    filename = f"{idx}.{ext}"

    for attempt in range(1, config.ATTEMP + 1):
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            return filename, response.content
        except requests.exceptions.RequestException as e:
            print(f"[{attempt}/{config.ATTEMP}] Ошибка {image_url}: {e}")
            time.sleep(2)

    print(f"Не удалось скачать: {image_url}")
    return filename, None


def download_images_to_memory(image_links):
    images = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.WORKER) as executor:
        futures = [executor.submit(download_single_image, idx, url)
                   for idx, url in enumerate(image_links, start=1)]
        for future in concurrent.futures.as_completed(futures):
            filename, data = future.result()
            if data:
                images[filename] = data
    return images


def save_images_as_zip(images_dict, output_path):
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_STORED) as zipf:
        for name, data in sorted(images_dict.items()):
            zipf.writestr(name, data)
    print(f"ZIP сохранён: {output_path}")


def title_name(soup):
    title_div = soup.find("div", class_="title_head_name")
    if title_div:
        raw = title_div.get_text(strip=True)
    else:
        h1 = soup.find("h1")
        raw = h1.get_text(strip=True) if h1 else "Unknown"

    return re.sub(r'[\\/:*?"<>|]', '', raw).strip().rstrip('.')

def extract_vol_ch(soup):
    chapters = []
    for tag in soup.find_all('div', class_='chapter_block_inner'):
        vol_tag = tag.find('div', class_='chapter_volume')
        ch_tag = tag.find('div', class_='chapter_number')

        # Run regex only if tag exists and text is not empty
        volume_match = re.search(r'\d+', vol_tag.text) if vol_tag and vol_tag.text else None
        chapter_match = re.search(r'\d+(?:\.\d+)?', ch_tag.text) if ch_tag and ch_tag.text else None

        volume = volume_match.group() if volume_match else None
        chapter = chapter_match.group() if chapter_match else None

        if volume and chapter:
            chapters.append((volume, chapter))

    return chapters



def download_and_store_chapter(link, manga_dir, vol, ch):
    archive_name = f"volume_{vol}__chapter_{ch}.zip"
    archive_path = os.path.join(manga_dir, archive_name)

    if os.path.exists(archive_path):
        print(f"Пропуск: {archive_name} уже есть")
        return

    chapter_url = f"{link}/v{vol}/c{ch}"
    print(f"Скачивание: Том {vol}, Глава {ch}")

    soup = get_soup(chapter_url)
    image_links = extract_image_links(soup)
    images = download_images_to_memory(image_links)

    if len(images) != len(image_links):
        print(f"Глава неполная ({len(images)} из {len(image_links)}), пропуск")
        return

    save_images_as_zip(images, archive_path)


def init(links):
    for link in links:
        soup = get_soup(link)
        manga_title = title_name(soup)
        manga_dir = os.path.join(config.PATH, manga_title)

        print(f"Манга: {manga_title}")

        os.makedirs(manga_dir, exist_ok=True)

        chapters = extract_vol_ch(soup)
        print(f"Глав найдено: {len(chapters)}")

        for vol, ch in chapters:
            download_and_store_chapter(link, manga_dir, vol, ch)




slugs = [
    "https://mangahub.cc/manga/I-m-the-villainess-in-a-martial-arts-novel--but-I-m-the-strongest"
]

init(slugs)