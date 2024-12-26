import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
TOKEN = os.getenv('DISCORD_TOKEN')
API_KEY = os.getenv('API_KEY')
GUILD_ID = 778249748490223656  # Replace with your server ID

# API Configuration
LANG = 'ka'
DEBUG = True