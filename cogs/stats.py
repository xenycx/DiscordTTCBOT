import discord
from discord.ext import commands
import config
import requests
import os
from groq import Groq

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = config.API_KEY
        self.groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

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
        embed.set_author(name="Tbilisi Transport Company", icon_url=self.bot.user.avatar.url)
        
        try:
            completion = self.groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {
                        "role": "system",
                        "content": "Provide interesting, lesser-known facts or useful tips about public transportation. Include statistics, safety tips, environmental impact, or historical facts. Use markdown formatting for emphasis."
                    },
                    {
                        "role": "user", 
                        "content": f"Share one interesting fact or tip about public transportation. Consider that {total_passengers:,} people used public transport today. Keep it under 30 words and make it engaging."
                    }
                ],
                temperature=0.8,
                max_tokens=70,
                top_p=0.95,
                stream=False
            )
            ai_comment = completion.choices[0].message.content
            embed.add_field(name="⭐ Fun Fact ", value=ai_comment, inline=False)
        except Exception as e:
            if config.DEBUG:
                print(f"Error generating AI comment: {e}")
        
        return embed

async def setup(bot):
    await bot.add_cog(Stats(bot))