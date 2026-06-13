import os
import json
import sys
from urllib.parse import urlparse
import re
import asyncio

import mangalib, senkuro
import config

JSON_FILE = config.JSON_FILE

def start():
    print("start")
    try:
        with open(JSON_FILE,'r',encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"{JSON_FILE} missed or empty")
        return  
    except json.JSONDecodeError:
        print(f"{JSON_FILE} corrupted or invalid JSON")
        return

    result = {}
    for domain, manga_list in data.items():
        result[domain] = [manga["slug"] for manga in manga_list if "slug" in manga]

    #добавить проверку что бы незаходить в каждую мангу и не была проблема с NoneType? 

    mangalib.init(result.get('mangalib.org'))
    asyncio.run(senkuro.main(result.get('senkuro.me')))


def import_manga() -> None:
    print("Input links (empty line for stop):")
    links = []
    while True:
        link = input()
        if not link:
            break
        links.append(link)

    # читаем старый JSON
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    for url in links:
        domain = urlparse(url).netloc
        match_obj = re.search(r'/manga/([^/?]+)', url)
        slug = match_obj.group(1) if match_obj else None
        if not slug:
            print(f"⚠️ Невозможно извлечь slug из URL: {url}")
            continue

        if domain not in data or not isinstance(data[domain], list):
            data[domain] = []

        if any(manga.get("slug") == slug for manga in data[domain]):
            print(f"+ [{domain}] Уже существует: {slug}, пропускаю.")
        else:
            data[domain].append({"slug": slug})
            print(f"- [{domain}] Добавлен: {slug}")

    # сохраняем JSON
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print("Готово")
    

def main():
    while True:
        print("1. start download")
        print("2. import manga")
        print("0. exit")
        
        Input = int(input("input: "))

        match Input:
            case 1:
                start()
            case 2:
                import_manga()
            case 0:
                sys.exit(0)

main()