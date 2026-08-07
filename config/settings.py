import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot.db")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# GigaChat (российский ИИ)
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")

# Groq больше не используется, но оставлено для совместимости (можно удалить)
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# GROQ_MODELS = [...]
# DEFAULT_AI_MODEL = ...

RSS_CHECK_INTERVAL = 3600
MAX_CHANNELS_PER_USER = 5
MAX_RSS_PER_CHANNEL = 10
DEFAULT_POST_INTERVAL = 7200
MAX_QUEUE_SIZE = 50
