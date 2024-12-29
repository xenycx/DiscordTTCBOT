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

        embed = discord.Embed(
            color=discord.Color.blue()
        )

        embed.set_author(name="Tbilisi Transport Company", icon_url=self.bot.user.avatar.url)

        embed.add_field(name="ლოკალური დრო", value=current_time.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
        embed.add_field(name="მუშაობის დრო", value=f"{days}დ {hours}სთ {minutes}წთ {seconds}წმ", inline=True)
        embed.add_field(name="ამუშავების დრო", value=self.start_time.strftime("%Y-%m-%d %H:%M:%S"), inline=True)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(UptimeCog(bot))
