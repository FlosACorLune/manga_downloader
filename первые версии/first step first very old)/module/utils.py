#utils.py

import requests, os, re, zipfile, config
from bs4 import BeautifulSoup




#cache requests
def get_soup(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup


#read file
def read_file_mangalist(download_dir):
    directory = os.path.join(download_dir)
    file_path = os.path.join(directory, config.mangalist_file)

    with open(file_path, 'r') as line:
        manga_list = [re.sub(r'\n', '', manga) for manga in line if not manga.startswith('#')]
    
    return manga_list



#разделение по модулям
def route_link(download_dir):
    urls = read_file_mangalist(download_dir)
    site_dict = {}
    for url in urls:
        domain_and_path = url[8:]
        slash_index = domain_and_path.find('/')
        if slash_index != -1:
            domain = domain_and_path[:slash_index]

        if domain not in site_dict:
            site_dict[domain] = []
        site_dict[domain].append(url)

    return site_dict


#fast самое оптимальное в среднем 80~ в fastest тоже ~80. в normal уже 60.  
#архивация глав
def save_images_as_zip(images_dict, output_path):
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as zipf:
        for name, data in sorted(images_dict.items()):
            zipf.writestr(name, data)
    print(f"📦 Архив сохранён: {output_path}")


#архивация тайтал
def save_title_as_zip(final_archive,all_data):
    with zipfile.ZipFile(final_archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as zipf:
        for path, data in sorted(all_data.items()):
            zipf.writestr(path, data)
    print(f"✅ Все главы собраны в единый архив: {final_archive}")

