import discord
from discord.ext import commands
import config
import requests

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = config.API_KEY

    @discord.app_commands.command(
        name="stats",
        description="მგზავრების სტატისტიკა"
    )
    async def stats(self, interaction: discord.Interaction):
        """Get current passenger statistics"""
        await interaction.response.defer()
        
        try:
            url = 'https://ttc.com.ge/api/passengers'
            headers = {'X-Api-Key': self.api_key}
            
            response = requests.get(url, headers=headers)
            data = response.json()

            if not data or 'transactionsByTransportTypes' not in data:
                await interaction.followup.send("სტატისტიკის მიღება ვერ მოხდა 😔")
                return

            stats, total_passengers = self.format_stats(data['transactionsByTransportTypes'])
            embed = self.create_embed(stats, total_passengers)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            if config.DEBUG:
                print(f"Error in stats command: {e}")
            await interaction.followup.send("შეცდომა მოხდა 😔")

    def format_stats(self, stats):
        total = sum(stats.values())
        sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
        
        response = []
        for transport, count in sorted_stats:
            if count > 0:
                percentage = (count / total) * 100
                response.append(f"🔸 {transport}: {count:,} ({percentage:.1f}%)")
        
        return "\n".join(response), total

    def create_embed(self, stats, total_passengers):
        embed = discord.Embed(title="📊 მგზავრების სტატისტიკა", description=stats, color=discord.Color.blue())
        embed.set_footer(text=f"👥 მგზავრების რაოდენობა: {total_passengers:,}")
        return embed

async def setup(bot):
    await bot.add_cog(Stats(bot))