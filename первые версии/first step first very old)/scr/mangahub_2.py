import requests, time, os, re, zipfile
from bs4 import BeautifulSoup
import utils, config

def title_name(soup):
    title = soup.find('div', class_='title_head_name')
    if title:
        return title.get_text(strip=True)
    else:
        raise ValueError("❌ Title not found. Возможно, изменился HTML-код страницы.")

def chapter_picture_link(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    reader_pages = soup.find('div', class_='pages_placer')
    img_tags = reader_pages.find_all('img') if reader_pages else []

    links = []
    for img in img_tags:
        if img.get('src'):
            links.append(img['src'])
        elif img.get('data-src'):
            links.append(img['data-src'])

    return links

def download_chapter_images_to_memory(chapter_links):
    images = {}
    max_retries = 10

    for idx, image_url in enumerate(chapter_links, start=1):
        ext = os.path.splitext(image_url.split("?")[0])[1][1:]
        ext = ext if ext else "webp"
        filename = f"{idx}.{ext}"

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(image_url, timeout=10)
                response.raise_for_status()
                images[filename] = response.content
                print(f"📥 В памяти: {filename}")
                break
            except requests.exceptions.RequestException as e:
                print(f"[{attempt}/{max_retries}] ❌ Ошибка при загрузке {image_url}: {e}")
                time.sleep(5)
        else:
            print(f"⚠️ Не удалось скачать: {image_url}")

    return images

def save_images_to_zip(images_dict, output_zip_path):
    with zipfile.ZipFile(output_zip_path, 'w', compression=zipfile.ZIP_STORED) as zipf:
        for name, data in sorted(images_dict.items()):
            zipf.writestr(name, data)

    print(f"📦 Архив сохранён: {output_zip_path}")

def extract_vol_ch(soup):
    all_chapters = []

    for tag in soup.find_all('div', class_='chapter_block_inner'):
        vol_tag = tag.find('div', class_='chapter_volume')
        ch_tag = tag.find('div', class_='chapter_number')

        vol_match = re.search(r'\d+', vol_tag.text) if vol_tag else None
        ch_match = re.search(r'\d+(?:\.\d+)?', ch_tag.text) if ch_tag else None

        volume = vol_match.group() if vol_match else None
        chapter = ch_match.group() if ch_match else None

        if volume and chapter:
            all_chapters.append((volume, chapter))

    return all_chapters

def chapter_already_downloaded(download_dir, manga_name, volume, chapter):
    archive_path = os.path.join(download_dir, manga_name, f"volume_{volume}__chapter_{chapter}.zip")
    return os.path.exists(archive_path)

def init(links):
    for link in links:
        soup = utils.page_request(link)
        manga_title = title_name(soup)

        print(f"📘 Manga: {manga_title}")

        manga_dir = os.path.join(config.download_directory, manga_title)
        os.makedirs(manga_dir, exist_ok=True)

        chapters = extract_vol_ch(soup)
        downloaded_archives = [
            name for name in os.listdir(manga_dir) if name.endswith(".zip")
        ]

        print(f"📂 Уже скачано архивов: {len(downloaded_archives)} / {len(chapters)}")

        for vol, ch in chapters:
            if chapter_already_downloaded(config.download_directory, manga_title, vol, ch):
                print(f"✅ Глава {vol}-{ch} уже загружена. Пропускаю.")
                continue

            archive_name = f"volume_{vol}__chapter_{ch}.zip"
            archive_path = os.path.join(manga_dir, archive_name)

            if os.path.exists(archive_path):
                print(f"✅ Пропуск: {archive_name} уже есть")
                continue

            print(f"⬇️ Загрузка главы: Том {vol}, Глава {ch}")
            chapter_url = f"{link}/v{vol}/c{ch}"
            chapter_links = chapter_picture_link(chapter_url)

            images_dict = download_chapter_images_to_memory(chapter_links)

            if len(images_dict) == len(chapter_links):
                save_images_to_zip(images_dict, archive_path)
            else:
                print(f"⚠️ Только {len(images_dict)} из {len(chapter_links)} изображений загружены. Пропуск архивации.")
