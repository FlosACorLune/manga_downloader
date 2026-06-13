
import requests, time, os, re, zipfile
from bs4 import BeautifulSoup
import utils, config

def title_name(soup):
    title = soup.find('div', class_='title_head_name')
    if title:
        text = title.get_text(strip=True)
    else:
        print("Title name does not find. Code error or changed page code.")
    return text


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


def download_chapter_images(chapter_links, volume, chapter, manga_name, download_dir):
    directory = os.path.join(download_dir, manga_name, f"volume_{volume}__chapter_{chapter}")
    os.makedirs(directory, exist_ok=True)

    max_retries = 5

    for idx, image_url in enumerate(chapter_links, start=1):
        ext = os.path.splitext(image_url.split("?")[0])[1][1:]
        if not ext:
            ext = "webp"
        file_path = os.path.join(directory, f"{idx}.{ext}")

        if os.path.exists(file_path):
            print(f"✅ Уже скачано: {file_path}")
            continue

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(image_url, timeout=10)
                response.raise_for_status()

                with open(file_path, 'wb') as f:
                    f.write(response.content)

                print(f"📥 Сохранено: {file_path}")
                break
            except requests.exceptions.RequestException as e:
                print(f"[{attempt}/{max_retries}] ❌ Ошибка при загрузке {image_url}: {e}")
                time.sleep(5)
        else:
            print(f"⚠️ Не удалось скачать: {image_url}")

    # Проверка полноты загрузки
    downloaded_images = [
        name for name in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, name))
    ]

    if len(downloaded_images) == len(chapter_links):
        print("✅ Все изображения загружены. Создание архива...")

        zip_name = os.path.join(download_dir, manga_name, f"volume_{volume}__chapter_{chapter}.zip")
        with zipfile.ZipFile(zip_name, 'w') as zipf:
            for img_file in sorted(downloaded_images):
                full_path = os.path.join(directory, img_file)
                arcname = os.path.basename(full_path)
                zipf.write(full_path, arcname)

        print(f"📦 Архив создан: {zip_name}")

        # Можно удалить исходную папку, если не нужна
        # import shutil
        # shutil.rmtree(directory)
    else:
        print(f"⚠️ Загружено только {len(downloaded_images)} из {len(chapter_links)}. Архив НЕ создан.")



def extract_vol_ch(soup):

    all_chapters = []

    for tag in soup.find_all('div', class_='chapter_block_inner'):
        vol_tag = tag.find('div', class_='chapter_volume')
        ch_tag = tag.find('div', class_='chapter_number')

        vol_match = re.search(r'\d+', vol_tag.text) if vol_tag else None
        ch_match = re.search(r'\d+(?:\.\d+)?', ch_tag.text) if ch_tag else None

        volume = (vol_match.group()) if vol_match else None
        chapter = (ch_match.group()) if ch_match else None

        all_chapters.append((volume, chapter))
    
    return all_chapters



def init(links):
    chapters = []

    for link in links:
        soup = utils.page_request(link)
        title_name_result = title_name(soup)
        
        print(f'Start downloading: {title_name_result}')
        
        manga_path = os.path.join(config.download_directory, title_name_result)
        if os.path.exists(manga_path):
            existing_chapters = len(os.listdir(manga_path))
        else:
            existing_chapters = 0
        print("Downloaded chapter: " + str(existing_chapters))

        chapters = extract_vol_ch(soup)


        if existing_chapters == len(chapters):
            print(f"All Chapter was downloaded\n")
            continue
        else:
            for vol, ch in chapters:
                print(f"Загрузка тома {vol}, главы {ch}")
                url = f"{link}/v{vol}/c{ch}"
                chapter_links = chapter_picture_link(url)
                
                download_chapter_images(chapter_links,vol,ch,title_name_result,config.download_directory)
                