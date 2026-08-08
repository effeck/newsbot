import os
import logging
import asyncio
import re
from typing import Dict, List, Optional
from datetime import datetime
from gigachat import GigaChat
from gigachat.models import ChatCompletionResponse

logger = logging.getLogger(__name__)


class AIProcessor:
    def __init__(self) -> None:
        # Получаем ключ GigaChat из переменных окружения
        self.credentials = os.getenv("GIGACHAT_CREDENTIALS")
        self.model = os.getenv("GIGACHAT_MODEL", "GigaChat")
        self.temperature = float(os.getenv("GIGACHAT_TEMPERATURE", 0.7))
        # Увеличиваем до 3000 токенов для длинных постов (до 500 слов)
        self.max_tokens = int(os.getenv("GIGACHAT_MAX_TOKENS", 3000))
        self.verify_ssl = os.getenv("GIGACHAT_VERIFY_SSL", "false").lower() == "true"

        if not self.credentials:
            logger.critical("GIGACHAT_CREDENTIALS не найден в настройках!")
            raise ValueError("GIGACHAT_CREDENTIALS is required")

        # Инициализация клиента GigaChat
        self.client = GigaChat(
            credentials=self.credentials,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            verify_ssl_certs=self.verify_ssl,
        )
        logger.info(f"AIProcessor инициализирован с моделью: {self.model}")

    async def process_content(self, entry: Dict, ch_settings: Dict) -> str:
        """
        Обрабатывает новость через GigaChat с журналистским промптом.
        """
        try:
            # Получаем текст новости
            title = entry.get('title', 'Новость')
            content = entry.get('content', '')

            # Очистка контента от лишних HTML-тегов
            clean_content = self._clean_html(content)
            if not clean_content or len(clean_content) < 50:
                logger.warning(f"Контент новости слишком короткий: {len(clean_content)} символов")
                return await self._fallback_format(title, clean_content)

            logger.info(f"Обработка новости: {title[:50]}... Длина контента: {len(clean_content)}")

            # Обновлённый журналистский промпт (200–500 слов, с фото)
            prompt = f"""
Ты — профессиональный журналист, пишешь для Telegram-канала. Твоя задача — сделать развёрнутый, живой и информативный пост из новостного текста.

Требования:
1. **Заголовок** (жирный, <b>) — короткий, яркий, привлекающий внимание.
2. **Вступление** (3–4 предложения) — введи в тему, объясни, почему это важно.
3. **Основная часть** (5–7 предложений) — раскрой суть события: что произошло, кто участники (имена, должности), где, когда, детали.
4. **Цитата или прямая речь** — если есть, обязательно добавь.
5. **Заключение** (2–3 предложения) — вывод, прогноз или вопрос к читателям.
6. **Общая длина** — от 200 до 500 слов. Ответ должен быть содержательным, без воды.
7. В конце — хэштеги (2–3) и @infinewss.

Важно:
- Сохрани все факты, цифры, даты, имена.
- Пиши нейтрально, но живо, без канцелярита.
- Если есть ссылка на источник — укажи её.

Исходный текст новости:
{clean_content}
"""
            # Отправляем запрос в GigaChat
            response = await asyncio.to_thread(
                self.client.chat,
                prompt
            )

            if response and response.choices and len(response.choices) > 0:
                result = response.choices[0].message.content.strip()
                logger.info(f"GigaChat успешно обработал новость (токенов: {response.usage.total_tokens})")
                # Не обрезаем результат, чтобы сохранить длину
                return result
            else:
                logger.warning("GigaChat вернул пустой ответ")
                return await self._fallback_format(title, clean_content)

        except Exception as e:
            logger.error(f"Ошибка при обработке контента: {str(e)}", exc_info=True)
            return await self._fallback_format(title, content)

    async def _fallback_format(self, title: str, content: str) -> str:
        """
        Резервное форматирование, если AI недоступен.
        """
        try:
            # Обрезаем слишком длинный контент
            if len(content) > 600:
                content = content[:600] + "..."

            # Улучшенное резервное форматирование
            if content.strip():
                result = f"📰 {title}\n\n{content}\n\n#новости @infinewss"
            else:
                result = f"📰 {title}\n\n#новости @infinewss"
            return result[:1500]

        except Exception as e:
            logger.error(f"Ошибка в резервном форматировании: {str(e)}")
            return f"📰 {title}\n\n#новости @infinewss"

    def _clean_html(self, text: str) -> str:
        """
        Удаляет HTML-теги из текста.
        """
        if not text:
            return ""

        # Удаляем HTML-теги
        clean = re.sub(r'<[^>]+>', ' ', text)
        # Удаляем лишние пробелы
        clean = re.sub(r'\s+', ' ', clean)
        # Удаляем ссылки
        clean = re.sub(r'https?://\S+', '', clean)
        return clean.strip()
