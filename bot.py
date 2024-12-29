import discord
from discord.ext import commands
import config
import asyncio

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True

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

async def main():
    async with bot:
        await setup()
        await bot.start(config.TOKEN)

if __name__ == '__main__':
    asyncio.run(main())