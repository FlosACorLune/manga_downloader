import requests
from bs4 import BeautifulSoup

slug = "vsevedushchii-chitatel"
url = f"https://mangabuff.ru/manga/{slug}"

response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")

manga_div = soup.find("div", class_="manga")

if manga_div and manga_div.has_attr("data-id"):
    manga_id = manga_div["data-id"]
    print(f"✅ manga_id найден: {manga_id}")
else:
    print("❌ Не удалось найти manga_id")
