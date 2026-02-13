#check first bytes is a webp or another. Отказавать от ext = [0] и тд
def get_image_type(data: bytes) -> str:
    """
    Определяет тип изображения по сигнатуре (magic bytes).
    Возвращает строку: 'jpg', 'png', 'gif', 'webp' или 'unknown'.
    """

    # JPEG: начинается с FF D8 FF
    if data.startswith(b"\xFF\xD8\xFF"):
        return "jpg"

    # PNG: начинается с 89 50 4E 47 0D 0A 1A 0A
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"

    # GIF: начинается с "GIF87a" или "GIF89a"
    elif data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif"

    # WEBP: RIFF....WEBP
    elif data.startswith(b"RIFF") and b"WEBP" in data[0:16]:
        return "webp"

    return "unknown"
