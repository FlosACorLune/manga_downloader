import asyncio
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv

import config
from BaseParser import BaseParser

load_dotenv()

MANGALIB_TOKEN = os.getenv("MANGALIB_TOKEN")


class MangaLib(BaseParser):
    
    def __init__(self, client, semaphore):
        super().__init__(client, semaphore)
        self.web_base = "mangalib.org"
        self.api_base = "https://api.cdnlibs.org/api/manga"
        self.server_one = "https://img2.imglib.info"
        self.parameters = "?fields[]=background&fields[]=eng_name&fields[]=otherNames&fields[]=summary&fields[]=releaseDate&fields[]=type_id&fields[]=caution&fields[]=views&fields[]=close_view&fields[]=rate_avg&fields[]=rate&fields[]=genres&fields[]=tags&fields[]=teams&fields[]=user&fields[]=franchise&fields[]=authors&fields[]=publisher&fields[]=userRating&fields[]=moderated&fields[]=metadata&fields[]=metadata.count&fields[]=metadata.close_comments&fields[]=manga_status_id&fields[]=chap_count&fields[]=status_id&fields[]=artists&fields[]=format"
        header = (
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Content-Type": "application/json",
                "Origin": self.web_base,
                "Referer": self.web_base,
                "Site-Id": "1",
                "Client-Time-Zone": "Asia/Yekaterinburg",
            }
        )
        if MANGALIB_TOKEN and MANGALIB_TOKEN.strip():
            header["Authorization"] = MANGALIB_TOKEN
        self.client.headers.update(header)


    async def fetchManga(self, url):
        response = await self.client.get(url)
        response.raise_for_status() 
        return response.json()
    
    
    async def fetchMangaChapter(self, slug, volume, chapter):
        chapter_url = f'{self.api_base}/{slug}/chapter?number={chapter}&volume={volume}'
        response = await self.client.get(chapter_url)
        return response.json()
        
    
    @staticmethod
    def get_vol_ch_date(result_query_chapters, overall_chapter_number):
        result = []
        for i in range(overall_chapter_number):
            chapter = result_query_chapters["data"][i]
            branch = chapter["branches"][0]

            expired = branch.get("expired_type", 0)
            restricted = branch.get("restricted_view")
            moderation = branch.get("moderation", {})
            label = moderation.get("label")

            if label == "На модерации":
                continue
            if expired == 0 or (expired == 1 and restricted is None):
                result.append((chapter["volume"], chapter["number"], branch['created_at']),)
        return tuple(result)
    
    @staticmethod
    def get_clean_summary(summary_data):
        if isinstance(summary_data, str):
            return summary_data
        
        if isinstance(summary_data, dict) and summary_data.get('type') == 'doc':
            try:
                texts = []
                for block in summary_data.get('content', []):
                    for item in block.get('content', []):
                        if item.get('type') == 'text':
                            texts.append(item.get('text', ''))
                return "\n".join(texts)
            except (KeyError, IndexError):
                return "Ошибка парсинга описания"
                
        return ""
    
    def url_assembly(self, result_get_vol_ch_date, result_slug_url):
        return [
            (vol, num, f"{self.api_base}{result_slug_url}/chapter?number={num}&volume={vol}")
            for vol, num in result_get_vol_ch_date
        ]
        
    @staticmethod
    def extract_cover_urls(cover_data: dict) -> list:
        """Извлекает URL обложек из ответа API, соблюдая приоритет качества"""
        urls = []

        if not cover_data or "data" not in cover_data:
            return urls
            
        for item in cover_data["data"]:
            cover = item.get("cover")
            if not cover:
                print("Doesn't have cover image")
                continue # <-- ИСПРАВЛЕНО: Вместо ухода из функции через return 1, просто идем дальше
                
            url = (
                cover.get("orig") or 
                cover.get("default") or
                cover.get("md") 
            )
            
            if url:
                urls.append(url)
                
        return urls
    
    
async def main(slugs):
    semaphore = asyncio.Semaphore(config.WORKER)
    timeout = httpx.Timeout(15.0, connect=15.0)
    
    async with httpx.AsyncClient(timeout=timeout, http2=True) as client:
        parser = MangaLib(client, semaphore)
        for slug in slugs:
            query_chapters = f"{parser.api_base}/{slug}/chapters"
            query_fields = f"{parser.api_base}/{slug}{parser.parameters}"
            query_cover = f"{parser.api_base}/{slug}/covers"
            
            result_query_chapters = await parser.fetchManga(query_chapters)
            result_query_fields = await parser.fetchManga(query_fields)
            result_query_cover = await parser.fetchManga(query_cover)
            
            overall_chapter_number = result_query_fields["data"]["items_count"]["uploaded"]
            result_get_vol_ch_date = parser.get_vol_ch_date(result_query_chapters, overall_chapter_number)
            
            avalaible_chapter_number = len(result_get_vol_ch_date)
            main_name = result_query_fields["data"]["rus_name"]
            other_name = result_query_fields['data']['otherNames']
            covers = parser.extract_cover_urls(result_query_cover)
            background = result_query_fields['data']['background']['url']
            age_restriction = result_query_fields['data']['ageRestriction']['label']
            model_type = result_query_fields['data']['type']['label']
            summary = parser.get_clean_summary(result_query_fields['data']['summary'])
            release_year = result_query_fields['data']['releaseDate']
            is_licenced = result_query_fields['data']['is_licensed']
            status = result_query_fields['data']['status']['label']
            scanlate_status = result_query_fields['data']['scanlateStatus']['label']
            teams = [item['slug'] for item in result_query_fields['data']['teams']]
            publisher = [item['slug'] for item in result_query_fields['data']['publisher']]
            
            print(f"INFO - start downloading {main_name}")
            await parser.save_cover(client, covers, main_name)
            
            print("INFO - starting download chapters...")
            
            for vol, ch, date in result_get_vol_ch_date:
                clean_manga_name = parser.get_clean_name(main_name)
                zip_path = Path(config.PATH) / clean_manga_name / f'volume_{vol}__chapter_{ch}.zip'
                
                if zip_path.exists():
                    print(f"INFO - Chapter Vol {vol} Ch {ch} already exists. Skipping.")
                    continue
                
                print(f"INFO - Downloading Vol {vol} Ch {ch}...")
                await parser.save_chapter(client, slug, vol, ch, main_name, parser.server_one)
            
slugs = [
    "8135--love-advice-from-the-great-duke-of-hell"
]
asyncio.run(main(slugs))