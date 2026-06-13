import zipfile
import re
from abc import abstractmethod
import httpx
from pathlib import Path
import subprocess
import config
import asyncio

class BaseParser:
    def __init__(self, client, semaphore):
        self.client = client
        self.semaphore = semaphore
        pass
    
    @abstractmethod
    async def fetchManga(self):
        pass
    
    @abstractmethod
    async def fetchMangaChapter(self):
        pass
    
    @abstractmethod
    async def fetchMangaChapterImage(self):
        pass
    
    @staticmethod
    def save_images_as_zip(images: dict, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as z:
            for name, data in sorted(images.items()):
                z.writestr(name, data)
    
    @staticmethod
    def save_image(image, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(image)
    
    async def fetchImage(self, client: httpx.AsyncClient, image_url, retries=3, backoff_factor=2):
        """Скачивает изображение с автоматическими повторными попытками при сбоях сети"""
        custom_timeout = httpx.Timeout(30.0, connect=10.0)
        
        for attempt in range(1, retries + 1):
            try:
                response = await client.get(image_url, timeout=custom_timeout)
                response.raise_for_status()
                return response.content
            except (httpx.HTTPStatusError, httpx.NetworkError, httpx.TimeoutException) as exc:
                if attempt == retries:
                    print(f"ERROR - All {retries} attempts failed for {image_url}: {exc}")
                    raise exc
                sleep_time = backoff_factor ** attempt
                print(f"WARNING - Attempt {attempt} failed ({exc}). Retrying in {sleep_time}s...")
                await asyncio.sleep(sleep_time)
    
    @staticmethod
    def get_clean_name(title: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "", title).strip().rstrip('.')
    

    async def save_cover(self, client: httpx.AsyncClient, covers: list, main_name):
        count = 0
        manga_folder = Path(config.PATH) / self.get_clean_name(main_name)
        
        for cover in covers:
            try:
                image_data = await self.fetchImage(client, cover)
                image_type = self.get_image_type(image_data)
                
                if config.USE_JXL and image_type in ("jpg", "png"):
                    try:
                        image_data = self.streaming_lossless_to_jxl(image_data)
                        image_type = "jxl"
                    except Exception as e:
                        print(f"WARNING - Unable to save in jxl: {e}. Save original format.")
                
                filename = f"cover.{image_type}" if count == 0 else f"cover ({count}).{image_type}"
                file_path = manga_folder / filename
                
                self.save_image(image_data, file_path)
                count += 1
                print(f"INFO - cover {count} saved")
            except Exception as e:
                print(f"ERROR - Failed to save cover {cover}: {e}")
            
            
    async def download_page(self, client, page_data, server_one, chapter_images):
        url = f"{server_one}{page_data['url']}"
        
        async with self.semaphore:
            try:
                content = await self.fetchImage(client, url)
                img_ext = self.get_image_type(content)
                
                if config.USE_JXL and img_ext in ("jpg", "png"):
                    try:
                        jxl_content = self.streaming_lossless_to_jxl(content)
                        content = jxl_content
                        img_ext = "jxl"
                    except RuntimeError as enc_err:
                        print(f"WARNING - Страница {page_data['slug']} имеет дефекты структуры ({enc_err}). "
                            f"Сохраняем в оригинальном формате .{img_ext}")
                
                img_name = f"{str(page_data['slug']).rjust(3,'0')}.{img_ext}"
                chapter_images[img_name] = content
                
            except Exception as e:
                print(f"ERROR - Не удалось скачать/обработать страницу {page_data['slug']}: {e}")
                
                
    async def save_chapter(self, client, slug, vol, ch, main_name, server_one, zip_path):
        """Скачивает и упаковывает одну главу манги"""
        a = await self.fetchMangaChapter(slug, vol, ch)
        chapter_images = {}
        
        if not a or 'data' not in a or 'pages' not in a['data']:
            print(f"ERROR - Pages not found for Vol {vol} Ch {ch}")
            return

        tasks = []
        for page in a['data']['pages']:
            task = self.download_page(client, page, server_one, chapter_images)
            tasks.append(task)
            
        await asyncio.gather(*tasks)
        
        if chapter_images:
            self.save_images_as_zip(chapter_images, zip_path)
            print(f"INFO - Chapter Vol {vol} Ch {ch} saved successfully.")
    
    @staticmethod            
    def get_image_type(data: bytes) -> str:
        if data.startswith(b"\xFF\xD8\xFF"):
            return "jpg"
        elif data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        elif data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            return "gif"
        elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "webp"
        elif data[4:12] == b"ftypavif" or data[4:12] == b"ftypavis":
            return "avif"
        elif data.startswith(b"\x00\x00\x00\x0cJXL \x0d\x0a\x87\x0a") or data.startswith(b"\xFF\x0A"):
            return "jxl"
        elif data.startswith(b"BM"):
            return "bmp"
        elif data.startswith(b"II*\x00") or data.startswith(b"MM\x00*"):
            return "tiff"
        elif data.startswith(b"8BPS"):
            return "psd"
        elif data.startswith(b"\x00\x00\x01\x00"):
            return "ico"
        elif data[4:12] == b"ftypheic" or data[4:12] == b"ftypmsf1":
            return "heic"
        return "unknown"
    
    @staticmethod
    def streaming_lossless_to_jxl(image_bytes: bytes) -> bytes:
        cmd = ['cjxl', '-', '-', '-e', '7', '-d', '0']
        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            jxl_bytes, stderr_data = process.communicate(input=image_bytes)
            if process.returncode != 0:
                error_msg = stderr_data.decode('utf-8', errors='ignore')
                raise RuntimeError(f"ERROR - encoding cjxl: {error_msg}")
            return jxl_bytes
        except FileNotFoundError:
            raise FileNotFoundError("cjxl not found in system")