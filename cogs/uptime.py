import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

class UptimeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.now(timezone.utc)

    @discord.app_commands.command(name="uptime", description="მუშაობის დრო")
    async def uptime(self, interaction: discord.Interaction):
        current_time = datetime.now(timezone.utc)
        uptime_delta = current_time - self.start_time

        days = uptime_delta.days
        hours = uptime_delta.seconds // 3600
        minutes = (uptime_delta.seconds % 3600) // 60
        seconds = uptime_delta.seconds % 60

        # Create the embed
        embed = discord.Embed(
            color=discord.Color.blue()
        )

        # Add bot's avatar and name as the author
        embed.set_author(name="Tbilisi Transport Company", icon_url=self.bot.user.avatar.url)

        # Add fields for Local time, Current uptime, and Start time
        embed.add_field(name="Local time", value=current_time.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
        embed.add_field(name="Current uptime", value=f"{days}d {hours}h {minutes}m {seconds}s", inline=True)
        embed.add_field(name="Start time", value=self.start_time.strftime("%Y-%m-%d %H:%M:%S"), inline=True)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(UptimeCog(bot))
