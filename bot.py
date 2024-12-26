import discord
from discord.ext import commands
import config
import asyncio

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True  # Add this line

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="ping", description="Shows bot latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! ({bot.latency*1000:.2f}ms)")

async def setup():
    await bot.load_extension("cogs.stats")
    await bot.load_extension("cogs.station")
    await bot.load_extension("cogs.buses")  # Ensure this line is present

async def main():
    async with bot:
        await setup()
        await bot.start(config.TOKEN)

if __name__ == '__main__':
    asyncio.run(main())