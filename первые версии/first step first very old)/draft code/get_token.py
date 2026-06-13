import requests

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

    return {
        xsrf_token,
        session_token
    }

# Пример использования
url = 'https://mangabuff.ru/manga/znatok-yadov-iz-sychuanskogo-klana-tan'  # Замените на нужный URL
xsrf_token,session_token = get_tokens(url)
print(session_token)
