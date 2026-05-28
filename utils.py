import zipfile


def get_image_type(data: bytes) -> str:
    if data.startswith(b"\xFF\xD8\xFF"):
        return "jpg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    elif data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    elif data.startswith(b"\x00\x00\x00\x0cJXL \x0d\x0a\x87\x0a") or data.startswith(b"\xFF\x0A"):
        return "jxl"
    return "unknown"

def save_images_as_zip(images: dict, output_path: str):
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED) as z:
        for name, data in sorted(images.items()):
            z.writestr(name, data)
    
def convert_jpg_to_jxl(images: dict):
    print()

def convert_png_to_jxl(images: dict):
    print()