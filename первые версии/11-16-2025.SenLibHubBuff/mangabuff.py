import os
import re
import time
import requests
import concurrent.futures
from bs4 import BeautifulSoup
import  zipfile

download_directory = r"D:\Manga"
max_attemp = 5
max_workers = 8


def get_soup(url):
    resp = requests.get(url)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, 'html.parser')

def get_slug_url(url):
    m = re.search(r'/manga/([^/?]+)', url)
    return m.group(1) if m else None


def get_domain_from_url(url):
    m = re.search(r'https?://([^/]+)/', url)
    return m.group(1) if m else None


# ---------- Загрузка ----------

def save_images_as_zip(images: dict, output_path: str):
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_STORED) as z:
        for name, data in sorted(images.items()):
            z.writestr(name, data)
    print("✔ ZIP:", output_path)


def title_name(soup):
    t = soup.find('h1', class_='manga__name')
    if not t:
        raise ValueError("Название не найдено")
    return re.sub(r'[\\/:*?\"<>|]', '', t.get_text(strip=True)).rstrip('.')


def extract_vol_ch(soup):
    out = []
    for t in soup.find_all('a', class_='chapters__item'):
        v = t.find('div', class_='chapters__volume')
        c = t.find('div', class_='chapters__value')

        vol = v.find('span').text.strip() if v and v.find('span') else ''
        ch = c.find('span').text.strip() if c and c.find('span') else ''

        if vol and ch:
            out.append((vol, ch))
    return out


def extract_image_links(soup):
    box = soup.find('div', class_='reader__pages')
    imgs = box.find_all('img') if box else []
    return [i.get('src') or i.get('data-src') for i in imgs]


def download_single_image(idx, url):
    ext = os.path.splitext(url.split("?")[0])[1][1:] or "webp"
    fname = f"{idx}.{ext}"

    for att in range(max_attemp):
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return fname, r.content
        except:
            time.sleep(3)

    print("⚠ Не скачано:", url)
    return fname, None


def download_images_to_memory(links):
    imgs = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(download_single_image, i, u) for i, u in enumerate(links, 1)]
        for f in concurrent.futures.as_completed(futures):
            name, data = f.result()
            if data:
                imgs[name] = data
    return imgs


def is_chapter_downloaded(base, title, vol, ch):
    p = os.path.join(base, title, f"volume_{vol}__chapter_{ch}.zip")
    return os.path.exists(p)


def download_and_store_chapter(url, manga_dir, vol, ch):
    archive = os.path.join(manga_dir, f"volume_{vol}__chapter_{ch}.zip")

    if os.path.exists(archive):
        print("✔ Уже есть:", archive)
        return

    chapter_url = f"{url}/{vol}/{ch}"
    print("→", chapter_url)

    soup = get_soup(chapter_url)
    imgs = extract_image_links(soup)
    data = download_images_to_memory(imgs)

    if len(data) != len(imgs):
        print("⚠ Пропуск: неполная глава")
        return

    save_images_as_zip(data, archive)



# ---------- Главная ----------

def init(links):
    for link in links:
        soup = get_soup(link)
        title = title_name(soup)

        print("\n📘", title)

        manga_dir = os.path.join(download_directory, title)
        os.makedirs(manga_dir, exist_ok=True)

        chapters = extract_vol_ch(soup)
        print("Глав:", len(chapters))

        for vol, ch in chapters:
            if is_chapter_downloaded(download_directory, title, vol, ch):
                print(f"✔ Пропуск {vol}-{ch}")
                continue

            download_and_store_chapter(link, manga_dir, vol, ch)

        print("Готово.\n")
