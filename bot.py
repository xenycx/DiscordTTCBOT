import discord
from discord.ext import commands
import config
import asyncio
import logging
import sys

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger('discord')

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True

# Configure bot with proper timeout settings
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    chunk_guilds_at_startup=False,  # Reduce startup load
    heartbeat_timeout=150.0,        # Increase heartbeat timeout
    gateway_queue_size=512          # Increase gateway queue size
)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Error in {event}", exc_info=True)

@bot.event
async def on_connect():
    logger.info("Bot connected to Discord")

@bot.event
async def on_disconnect():
    logger.warning("Bot disconnected from Discord")

@bot.event
async def on_resumed():
    logger.info("Bot session resumed")

# Remove or comment out the problematic on_interaction event
# @bot.event
# async def on_interaction(interaction):
#     try:
#         await interaction
#     except Exception as e:
#         logging.error(f"Error handling interaction: {str(e)}", exc_info=True)

@bot.event
async def on_view_timeout(view):
    logger.info(f"View timed out: {view}")

@bot.tree.command(name="ping", description="დაყოვნების შემოწმება")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"დაყოვნება ({bot.latency*1000:.2f} მილიწამი)")

async def setup():
    bot.remove_command("help")  # Remove the default help command
    await bot.load_extension("cogs.stats")
    await bot.load_extension("cogs.stop")
    await bot.load_extension("cogs.buses")
    await bot.load_extension("cogs.bus")
    await bot.load_extension("cogs.stops")
    await bot.load_extension("cogs.help")
    await bot.load_extension("cogs.uptime")
    await bot.load_extension('cogs.ai')

async def main():
    max_retries = 5
    retry_delay = 5

    while True:
        try:
            async with bot:
                await setup()
                await bot.start(config.TOKEN)
        except discord.errors.ConnectionClosed:
            logger.warning("Connection closed, attempting to reconnect...")
            await asyncio.sleep(retry_delay)
        except discord.errors.GatewayNotFound:
            logger.error("Discord gateway not found, retrying in 5 seconds...")
            await asyncio.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            await asyncio.sleep(retry_delay)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")