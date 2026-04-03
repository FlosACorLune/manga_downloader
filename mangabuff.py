import concurrent.futures
import os
import re
import time
import zipfile

import requests
from bs4 import BeautifulSoup

import config
import utils


def get_soup(url:str) -> BeautifulSoup:
    response = requests.get(url)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def save_images_as_zip(images: dict, output_path: str):
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED) as z:
        for name, data in sorted(images.items()):
            z.writestr(name, data)
    print("✔ ZIP:", output_path)


def title_name(soup):
    t = soup.find("h1", class_="manga__name")
    return re.sub(r"[\\/:*.?\"<>|]", "", t.get_text(strip=True))


def extract_vol_ch(soup):
    out = []
    for t in soup.find_all("a", class_="chapters__item"):
        v = t.find("div", class_="chapters__volume")
        c = t.find("div", class_="chapters__value")

        vol = v.find("span").text.strip() if v and v.find("span") else ""
        ch = c.find("span").text.strip() if c and c.find("span") else ""

        if vol and ch:
            out.append((vol, ch))
    return out


def extract_image_links(soup):
    box = soup.find("div", class_="reader__pages")
    imgs = box.find_all("img") if box is not None else []
    return [i.get("src") or i.get("data-src") for i in imgs]


def download_single_image(idx, url):
    for _ in range(config.ATTEMP):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.content
            ext = utils.get_image_type(data)
            filename = f"{idx}.{ext}"
            time.sleep(config.DELAY)
            return filename, data
        except requests.exceptions.RequestException as e:
            print(f"Ошибка скачивания ({url}): {e}")
            time.sleep(3)

    print("⚠ Не скачано:", url)
    return None, None



def download_images_to_memory(links):
    imgs = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.WORKER) as ex:
        futures = [
            ex.submit(download_single_image, i, u) for i, u in enumerate(links, 1)
        ]
        for f in concurrent.futures.as_completed(futures):
            try:
                name, data = f.result()
            except Exception as e:
                print("Task failed",e)
                continue
            if name and data:
                imgs[name] = data

    return imgs


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


def init(slugs):
    for slug in slugs:
        soup = get_soup(slug)
        title = title_name(soup)

        print("\n", title)

        manga_dir = os.path.join(config.PATH, title)
        os.makedirs(manga_dir, exist_ok=True)

        chapters = extract_vol_ch(soup)
        print("Глав:", len(chapters))

        for vol, ch in chapters:
            download_and_store_chapter(slug, manga_dir, vol, ch)

        print("Готово.\n")


slugs = [
    "https://mangabuff.ru/manga/vyzhit-v-seme-iskusnyh-otravitelei",
    "https://mangabuff.ru/manga/skazanie-hengdan"
         
         ]

init(slugs)
