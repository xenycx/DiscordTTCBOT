import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="დამხმარე ბრძანება")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="ხელმისაწვდომი ბრძანებები:", color=discord.Color.blue())
        for command in self.bot.tree.get_commands():
            embed.add_field(name=f"/{command.name}", value=command.description or "არწერის გარეშე", inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))