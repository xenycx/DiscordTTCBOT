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

            stats = self.format_stats(data['transactionsByTransportTypes'])
            await interaction.followup.send(content=stats)

        except Exception as e:
            if config.DEBUG:
                print(f"Error in stats command: {e}")
            await interaction.followup.send("შეცდომა მოხდა 😔")

    def format_stats(self, stats):
        total = sum(stats.values())
        sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
        
        response = ["📊 მგზავრების სტატისტიკა:"]
        for transport, count in sorted_stats:
            if count > 0:
                percentage = (count / total) * 100
                response.append(f"🔸 {transport}: {count:,} ({percentage:.1f}%)")
        
        response.append(f"\n👥 მგზავრების რაოდენობა: {total:,}")
        return "\n".join(response)

async def setup(bot):
    await bot.add_cog(Stats(bot))