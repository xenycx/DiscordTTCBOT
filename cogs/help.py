import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

@discord.app_commands.command(name="help", description="ბრძანებების სრული სიის ჩვენება")
async def help(self, interaction: discord.Interaction):
    embed = discord.Embed(title="დახმარება", description="ხელმისაწვდომი ბრძანებები:", color=discord.Color.blue())
    for command in self.bot.tree.get_commands():
        embed.add_field(name=f"/{command.name}", value=command.description, inline=False)
    await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))