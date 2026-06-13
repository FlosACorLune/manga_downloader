import requests
from bs4 import BeautifulSoup


#url = "https://mangabuff.ru/manga/vsevedushchii-chitatel"
#response = requests.get(url)
#response.raise_for_status()
#soup = BeautifulSoup(response.text, 'html.parser')
#links = [a['href'] for a in soup.find_all('a', class_='chapters__item', href=True)]
#for link in links:
#    print(link)
#input(print('stop'))








def get_tokens(url):
    # Выполняем GET-запрос к указанному URL
    response = requests.get(url)
    response.raise_for_status()  # Проверка на ошибки

    # Извлекаем токены из заголовков
    cookies = response.cookies
    xsrf_token = cookies.get('XSRF-TOKEN')
    session_token = cookies.get('mangabuff_session')

    # Убираем символы %3D из токенов, если они есть
    if xsrf_token:
        xsrf_token = xsrf_token.replace('%3D', '')
    if session_token:
        session_token = session_token.replace('%3D', '')

    print("X Token: " + xsrf_token)
    print("S Token: " + session_token)

    return {
        'xsrf_token': xsrf_token,
        'session_token': session_token
    }



url = "https://mangabuff.ru/chapters/load"
url_manga_path = 'https://mangabuff.ru/manga/vliyatelnaya-ledi'

tokens = get_tokens(url_manga_path)
xsrf_token = tokens['xsrf_token']
session_token = tokens['session_token']

headers = {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "X-XSRF-TOKEN": xsrf_token 
    #"x-csrf-token": csrf_token_header  # можешь убрать, если не нужен
}

cookies = {
    "XSRF-TOKEN": xsrf_token,
    "mangabuff_session": session_token
}

payload = {
    "manga_id": 1307
}

response = requests.post(url, headers=headers, cookies=cookies, json=payload)

if response.ok:
    data = response.json()
    html = data.get("html") or data.get("content", "")
    soup = BeautifulSoup(html, "html.parser")
    chapter_tags = soup.find_all("a", class_="chapters__item")

    with open("chapter_links.txt", "w", encoding="utf-8") as f:
        for tag in chapter_tags:
            full_url = "https://mangabuff.ru" + tag['href']
            f.write(full_url + "\n")
            print(full_url)

    print(f"✅ Сохранено {len(chapter_tags)} ссылок в chapter_links.txt")
else:
    print("❌ Ошибка:", response.status_code, response.text)



