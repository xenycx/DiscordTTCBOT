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
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
    except Exception as e:
        logger.error(f"Sync failed: {e}")

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
    await bot.load_extension("cogs.stats")
    await bot.load_extension("cogs.stop")
    await bot.load_extension("cogs.buses")
    await bot.load_extension("cogs.bus")
    await bot.load_extension("cogs.stops")
    await bot.load_extension("cogs.help")
    await bot.load_extension("cogs.uptime")
    await bot.load_extension('cogs.ai')
    logger.info("Extensions loaded")

async def main():
    max_retries = 5
    retry_delay = 5

    while True:
        try:
            async with bot:
                await setup()
                await bot.start(config.TOKEN)
        except discord.errors.ConnectionClosed:
            logger.warning("Connection lost, reconnecting...")
            await asyncio.sleep(retry_delay)
        except discord.errors.GatewayNotFound:
            logger.error("Gateway error, retrying...")
            await asyncio.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Fatal: {str(e)}")
            await asyncio.sleep(retry_delay)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal: {str(e)}")