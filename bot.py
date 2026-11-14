import discord
from discord.ext import commands
import config
import asyncio
import logging
import sys

# Simple logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger('discord')

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    chunk_guilds_at_startup=False,
    heartbeat_timeout=150.0,
    gateway_queue_size=512
)

@bot.event
async def on_ready():
    logger.info(f'Bot ready: {bot.user} ({bot.user.id})')

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Event error: {event}")

@bot.event
async def on_connect():
    logger.info("Connected")

@bot.event
async def on_disconnect():
    logger.warning("Disconnected")

@bot.event
async def on_resumed():
    logger.info("Session resumed")

@bot.event
async def on_view_timeout(view):
    logger.info("View timeout")

@bot.tree.command(name="ping", description="დაყოვნების შემოწმება")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"დაყოვნება ({bot.latency*1000:.2f} მილიწამი)")

async def setup():
    bot.remove_command("help")
    for ext in ("cogs.stats", "cogs.transit", "cogs.help", "cogs.uptime", "cogs.ai"):
        try:
            await bot.load_extension(ext)
        except Exception:
            logger.exception(f"Failed to load {ext}")
    logger.info("Extensions loaded")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
    except Exception as e:
        logger.error(f"Sync failed: {e}")

bot.setup_hook = setup

async def main():
    if not config.TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set (see 'env example')")
    # discord.py reconnects on its own; this only guards the initial login.
    async with bot:
        await bot.start(config.TOKEN, reconnect=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
