import feedparser
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import hashlib
import logging
import chardet

logger = logging.getLogger(__name__)


class RSSParser:
    def __init__(self):
        self.session = None
        # Заголовок User-Agent для обхода блокировок
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def parse_feed(self, url: str, last_guid: Optional[str] = None) -> List[Dict]:
        try:
            # Загружаем RSS с заголовками
            if self.session:
                async with self.session.get(url, timeout=10) as response:
                    if response.status != 200:
                        logger.warning(f"Ошибка загрузки RSS {url}: статус {response.status}")
                        return []
                    raw_content = await response.read()
                    # Определяем кодировку
                    detected = chardet.detect(raw_content)
                    encoding = detected.get('encoding', 'utf-8') if detected else 'utf-8'
                    try:
                        content = raw_content.decode(encoding)
                    except UnicodeDecodeError:
                        # Если не получилось, пробуем KOI8-R (популярная кодировка для OpenNet)
                        try:
                            content = raw_content.decode('koi8-r')
                        except:
                            content = raw_content.decode('utf-8', errors='ignore')
            else:
                # fallback
                feed = feedparser.parse(url)
                content = None

            if content:
                feed = feedparser.parse(content)
            else:
                feed = feedparser.parse(url)

            if not feed.entries:
                logger.info(f"В RSS {url} нет записей")
                return []

            new_entries = []
            for entry in feed.entries[:20]:  # берём до 20 записей
                entry_id = entry.get('id', entry.get('link', ''))

                if last_guid and entry_id == last_guid:
                    break

                parsed_entry = self.parse_entry(entry)
                if parsed_entry:
                    new_entries.append(parsed_entry)

            logger.info(f"Из RSS {url} получено {len(new_entries)} новых записей")
            return new_entries
        except Exception as e:
            logger.error(f"Ошибка парсинга RSS {url}: {e}")
            return []

    def parse_entry(self, entry) -> Optional[Dict]:
        try:
            content = self.extract_content(entry)
            media = self.extract_media(entry)

            # Убираем обязательное требование медиа
            return {
                'guid': entry.get('id', entry.get('link', '')),
                'title': entry.get('title', 'No title'),
                'link': entry.get('link', ''),
                'content': content,
                'media': media,  # может быть пустым списком
                'published': entry.get('published_parsed', None),
                'author': entry.get('author', ''),
                'tags': [tag.term for tag in entry.get('tags', [])][:5]
            }
        except Exception as e:
            logger.warning(f"Ошибка парсинга записи: {e}")
            return None

    def extract_content(self, entry) -> str:
        content = ''

        # Пробуем получить текст из разных полей
        if 'content' in entry:
            content = entry.content[0].value
        elif 'summary' in entry:
            content = entry.summary
        elif 'description' in entry:
            content = entry.description

        # Очищаем HTML
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        # Убираем лишние пробелы
        text = ' '.join(text.split())

        # Если текст слишком длинный, обрезаем (но оставляем достаточно)
        if len(text) > 10000:
            text = text[:10000] + '...'
        return text

    def extract_media(self, entry) -> List[str]:
        media_urls = []

        if 'enclosures' in entry:
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image'):
                    media_urls.append(enclosure.href)

        if 'media_content' in entry:
            for media in entry.media_content:
                if media.get('type', '').startswith('image'):
                    media_urls.append(media['url'])

        if 'media_thumbnail' in entry:
            for thumb in entry.media_thumbnail:
                if thumb.get('url'):
                    media_urls.append(thumb['url'])

        # Если есть HTML-контент, ищем картинки
        if 'content' in entry and not media_urls:
            try:
                soup = BeautifulSoup(entry.content[0].value, 'html.parser')
                for img in soup.find_all('img')[:3]:
                    src = img.get('src')
                    if src and src.startswith('http'):
                        media_urls.append(src)
            except:
                pass

        return list(dict.fromkeys(media_urls))[:1]

    async def download_image(self, url: str) -> Optional[bytes]:
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    content = await response.read()
                    if len(content) < 5000000:
                        return content
        except Exception as e:
            logger.error(f"Ошибка скачивания изображения {url}: {e}")
        return None
