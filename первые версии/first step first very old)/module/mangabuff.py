import os
import re
import time
import requests
import concurrent.futures
from bs4 import BeautifulSoup

import utils, config

def title_name(soup):
    title = soup.find('h1', class_='manga__name')
    if not title:
        raise ValueError("❌ Название не найдено. Возможно, изменился HTML.")

    raw_title = title.get_text(strip=True)
    return re.sub(r'[\\/:*?\"<>|]', '', raw_title).strip().rstrip('.')

def get_title_status(soup):
    links = soup.find_all('a', class_='manga__middle-link')
    for link in links:
        href = link.get('href', '')
        if 'status_id[]=' in href:
            start = href.find('status_id[]=')
            id_str = href[start + len('status_id[]='):]
            id_value = id_str.split('&')[0]
            return int(id_value)

def extract_vol_ch(soup):
    chapters = []
    for tag in soup.find_all('a', class_='chapters__item'):
        vol_tag = tag.find('div', class_='chapters__volume')
        ch_tag = tag.find('div', class_='chapters__value')

        vol = vol_tag.find('span').text.strip() if vol_tag and vol_tag.find('span') else ''
        ch = ch_tag.find('span').text.strip() if ch_tag and ch_tag.find('span') else ''

        if vol and ch:
            chapters.append((vol, ch))
    return chapters

def get_lazy_loaded_chapters(soup, link):
    chapters_button = soup.find('button', attrs={'data-page': 'chapters'})
    if not chapters_button:
        return []

    count = int(chapters_button.get_text().split('(')[-1].strip(')'))
    if count <= 100:
        return []

    def extract(soup):
        return extract_vol_ch(soup)

    manga_div = soup.find("div", class_="manga")
    manga_id = manga_div["data-id"] if manga_div and manga_div.has_attr("data-id") else None
    if not manga_id:
        return []

    tokens = get_tokens(link)
    headers = {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-XSRF-TOKEN": tokens['xsrf_token']
    }
    cookies = {
        "XSRF-TOKEN": tokens['xsrf_token'],
        "mangabuff_session": tokens['session_token']
    }
    payload = {"manga_id": manga_id}

    resp = requests.post("https://mangabuff.ru/chapters/load", headers=headers, cookies=cookies, json=payload)
    resp.raise_for_status()

    html = resp.json().get("html") or resp.json().get("content", '')
    return extract(BeautifulSoup(html, "html.parser"))

def get_tokens(url):
    response = requests.get(url)
    response.raise_for_status()
    cookies = response.cookies
    return {
        'xsrf_token': cookies.get('XSRF-TOKEN', '').replace('%3D', ''),
        'session_token': cookies.get('mangabuff_session', '').replace('%3D', '')
    }

def extract_image_links(soup):
    reader_pages = soup.find('div', class_='reader__pages')
    img_tags = reader_pages.find_all('img') if reader_pages else []
    return [img.get('src') or img.get('data-src') for img in img_tags if img.get('src') or img.get('data-src')]

def download_single_image(idx, image_url):
    ext = os.path.splitext(image_url.split("?")[0])[1][1:] or "webp"
    filename = f"{idx}.{ext}"
    for attempt in range(1, config.max_attemp + 1):
        try:
            resp = requests.get(image_url, timeout=10)
            resp.raise_for_status()
            return filename, resp.content
        except requests.exceptions.RequestException as e:
            print(f"[{attempt}/{config.max_attemp}] ❌ Ошибка при загрузке {image_url}: {e}")
            time.sleep(5)
    print(f"⚠️ Не удалось скачать: {image_url}")
    return filename, None

def download_images_to_memory(image_links):
    images = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(download_single_image, idx, url) for idx, url in enumerate(image_links, 1)]
        for future in concurrent.futures.as_completed(futures):
            filename, data = future.result()
            if data:
                images[filename] = data
    return images

def is_chapter_downloaded(download_dir, manga_name, volume, chapter):
    path = os.path.join(download_dir, manga_name, f"volume_{volume}__chapter_{chapter}.zip")
    return os.path.exists(path)

def download_and_store_chapter(link, manga_dir, manga_title, vol, ch, mode):
    archive_name = f"volume_{vol}__chapter_{ch}.zip"
    archive_path = os.path.join(manga_dir, archive_name)

    if mode == 2 and os.path.exists(archive_path):
        print(f"✅ Пропуск: {archive_name} уже есть")
        return {}

    chapter_url = f"{link}/{vol}/{ch}"
    print(f"⬇️ Загрузка главы: Том {vol}, Глава {ch}")
    soup = utils.get_soup(chapter_url)
    image_links = extract_image_links(soup)
    images = download_images_to_memory(image_links)

    if len(images) != len(image_links):
        print(f"⚠️ Загружено {len(images)} из {len(image_links)}. Пропускаю.")
        return None

    if mode == 1:
        return {f"{manga_title}/volume_{vol}__chapter_{ch}/{k}": v for k, v in images.items()}
    else:
        utils.save_images_as_zip(images, archive_path)
        return {}

def init(links):
    for link in links:
        soup = utils.get_soup(link)
        manga_title = title_name(soup)
        manga_dir = os.path.join(config.download_directory, manga_title)
        final_archive = os.path.join(config.download_directory, f"{manga_title}__complete.zip")

        print(f"📘 Manga: {manga_title}")
        os.makedirs(manga_dir, exist_ok=True)

        status_mode = get_title_status(soup)

        # ✅ Если статус неизвестен (None), используем режим 2 (отдельные главы)
        if status_mode is None:
            status_mode = 2

        chapters = extract_vol_ch(soup)
        chapters += get_lazy_loaded_chapters(soup, link)
        print(f"🔍 Найдено глав: {len(chapters)}")

        all_data = {}

        for vol, ch in chapters:
            if status_mode == 2 and is_chapter_downloaded(config.download_directory, manga_title, vol, ch):
                print(f"✅ Глава {vol}-{ch} уже загружена. Пропускаю.")
                continue

            result = download_and_store_chapter(link, manga_dir, manga_title, vol, ch, status_mode)

            if result is None:
                if status_mode == 1:
                    print("❌ Прерываю сборку общего архива — неполная глава.")
                    return
            else:
                all_data.update(result)

        if status_mode == 1 and all_data:
            utils.dave_title_as_zip(final_archive, all_data)
        print("✅ Загрузка завершена\n")
