import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="დამხმარება")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="ხელმისაწვდომი ბრძანებები:", 
            color=discord.Color.blue()
            )
        embed.set_author(name="Tbilisi Transport Company", icon_url=self.bot.user.avatar.url)

        commands = self.bot.tree.get_commands()
        commands = sorted(commands, key=lambda x: x.name)
        
        for i, command in enumerate(commands):
            if i % 2 == 0 and i == len(commands) - 1:
                embed.add_field(name=f"/{command.name}", value=f"`{command.description or 'აღწერის გარეშე'}`", inline=True)
                embed.add_field(name="\u200b", value="\u200b", inline=True)
            else:
                embed.add_field(name=f"/{command.name}", value=f"`{command.description or 'აღწერის გარეშე'}`", inline=True)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))