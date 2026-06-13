import os
import re
import time
import requests
import concurrent.futures

import utils, config


def title_name(soup):
    title = soup.find('div', class_='title_head_name')
    if not title:
        raise ValueError("❌ Название не найдено. Возможно, изменился HTML.")

    raw_title = title.get_text(strip=True)
    clean_title = re.sub(r'[\\/:*?"<>|]', '', raw_title).strip().rstrip('.')
    return clean_title

def extract_image_links(soup):
    reader_pages = soup.find('div', class_='pages_placer')
    img_tags = reader_pages.find_all('img') if reader_pages else []
    return [img.get('src') or img.get('data-src') for img in img_tags if img.get('src') or img.get('data-src')]

def download_single_image(idx, image_url):
    ext = os.path.splitext(image_url.split("?")[0])[1][1:] or "webp"
    filename = f"{idx}.{ext}"
    
    for attempt in range(1, config.max_attemp+1):
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            return filename, response.content
        except requests.exceptions.RequestException as e:
            print(f"[{attempt}/{config.max_attemp}] ❌ Ошибка при загрузке {image_url}: {e}")
            time.sleep(5)
    print(f"⚠️ Не удалось скачать: {image_url}")
    return filename, None

def download_images_to_memory(image_links):
    images = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(download_single_image, idx, url) for idx, url in enumerate(image_links, start=1)]
        for future in concurrent.futures.as_completed(futures):
            filename, data = future.result()
            if data:
                images[filename] = data
    return images

def extract_vol_ch(soup):
    chapters = []
    for tag in soup.find_all('div', class_='chapter_block_inner'):
        vol_tag, ch_tag = tag.find('div', class_='chapter_volume'), tag.find('div', class_='chapter_number')

        volume = re.search(r'\d+', vol_tag.text).group() if vol_tag else None
        chapter = re.search(r'\d+(?:\.\d+)?', ch_tag.text).group() if ch_tag else None

        if volume and chapter:
            chapters.append((volume, chapter))

    return chapters

def is_chapter_downloaded(download_dir, manga_name, volume, chapter):
    path = os.path.join(download_dir, manga_name, f"volume_{volume}__chapter_{chapter}.zip")
    return os.path.exists(path)

def download_and_store_chapter(link, manga_dir, manga_title, vol, ch, isFinished):
    archive_name = f"volume_{vol}__chapter_{ch}.zip"
    archive_path = os.path.join(manga_dir, archive_name)

    if not isFinished and os.path.exists(archive_path):
        print(f"✅ Пропуск: {archive_name} уже есть")
        return {}

    chapter_url = f"{link}/v{vol}/c{ch}"
    print(f"⬇️ Загрузка главы: Том {vol}, Глава {ch}")
    soup = utils.get_soup(chapter_url)
    image_links = extract_image_links(soup)
    images = download_images_to_memory(image_links)

    if len(images) != len(image_links):
        print(f"⚠️ Загружено {len(images)} из {len(image_links)}. Пропускаю.")
        return None

    if isFinished:
        return {f"{manga_title}/volume_{vol}__chapter_{ch}/{k}": v for k, v in images.items()}
    else:
        utils.save_images_as_zip(images, archive_path)
        return {}


def init(links):
    if config.mangalist_file == "mangalist_update.txt":
        config.isFinished = False
    else:
        config.isFinished = True

    for link in links:
        soup = utils.get_soup(link)
        manga_title = title_name(soup)
        manga_dir = os.path.join(config.download_directory, manga_title)
        final_archive = os.path.join(config.download_directory, f"{manga_title}__complete.zip")

        print(f"📘 Manga: {manga_title}")

        if config.isFinished and os.path.exists(final_archive):
            print(f"✅ Итоговый архив уже существует: {final_archive} — пропускаем загрузку")
            continue

        if not config.isFinished:
            os.makedirs(manga_dir, exist_ok=True)

        chapters = extract_vol_ch(soup)
        print(f"🔍 Найдено глав: {len(chapters)}")

        if not config.isFinished:
            downloaded_count = len([f for f in os.listdir(manga_dir) if f.endswith('.zip')])
            if not config.isFinished and downloaded_count == len(chapters):
                print(f"✅ Все главы уже скачаны: {downloaded_count}/{len(chapters)} — пропускаю мангу.")
                continue

        all_chapter_data = {}

        for vol, ch in chapters:
            if not config.isFinished and is_chapter_downloaded(config.download_directory, manga_title, vol, ch):
                print(f"✅ Глава {vol}-{ch} уже загружена. Пропускаю.")
                continue

            chapter_data = download_and_store_chapter(link, manga_dir, manga_title, vol, ch, config.isFinished)

            if chapter_data is None:
                if config.isFinished:
                    print("❌ Прерываю сборку общего архива — неполная глава.")
                    return
            else:
                all_chapter_data.update(chapter_data)

        if config.isFinished and all_chapter_data:
            utils.save_title_as_zip()
