import os
from dotenv import load_dotenv
import logging.config
import json
from webhook_handler import DiscordWebhookHandler

# Load environment variables
load_dotenv()

# Configure logging
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s - %(name)s: %(message)s',
            'datefmt': '%H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple'
        },
        'webhook': {
            'class': 'webhook_handler.DiscordWebhookHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'webhook_url': os.getenv('DISCORD_WEBHOOK_URL')
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'bot.log',
            'level': 'DEBUG',
            'formatter': 'simple',
            'mode': 'a'
        }
    },
    'loggers': {
        'ai.cog': {
            'handlers': ['webhook'],
            'level': 'INFO',
            'propagate': False
        },
        'discord': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)

# Bot Configuration
TOKEN = os.getenv('DISCORD_TOKEN')
API_KEY = os.getenv('API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

# API Configuration
LANG = 'ka'
DEBUG = True

# OpenRouter Configuration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
SITE_URL = "https://github.com/xenyc1337/DiscordTTCBOT"
SITE_NAME = "TTC Discord Bot"

# API Timeouts (in seconds)
REQUEST_TIMEOUT = 60  # Increased timeout for image processing

# Default Model
DEFAULT_MODEL = "google/gemini-2.0-flash-exp:free"

# Model Categories
BASIC_MODELS = {
    "google/gemini-2.0-flash-exp:free": "Default fast response model",
    "google/gemini-2.0-pro-exp-02-05:free": "More capable model for complex tasks",
    "deepseek/deepseek-chat:free": "General purpose chat model"
}

THINKING_MODELS = {
    "deepseek/deepseek-r1:free": "Advanced reasoning and analysis",
    "google/gemini-2.0-flash-thinking-exp:free": "Quick analytical responses"
}