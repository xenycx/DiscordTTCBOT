import os
import discord
from discord.ext import commands
import config
import aiohttp
import json
import logging

logger = logging.getLogger('ai.cog')

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = config.API_KEY
        self.session = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    async def get_ai_analysis(self, stats_text: str) -> str:
        try:
            prompt = f"""
            მოცემულია სატრანსპორტო მონაცემები. უშუალოდ, როგორც ანალიტიკოსმა, ქართულად წარმოადგინე 3 ძირითადი დასკვნა, რომლებიც გამომდინარეობს ამ მონაცემებიდან. არ გამოიყენო წინასიტყვაობა.
            {stats_text}
            """

            async with self.session.post(
                url=f"{config.OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "HTTP-Referer": config.SITE_URL,
                    "X-Title": config.SITE_NAME,
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek/deepseek-r1:free",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a transportation data analyst specializing in public transport statistics."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
            ) as response:
                if response.status != 200:
                    logger.error(f"Analysis API error: {response.status}")
                    raise Exception(f"API Error {response.status}")
                
                result = await response.json()
                return result['choices'][0]['message']['content']

        except Exception as e:
            logger.error(f"Analysis error: {str(e)}")
            raise
        
    @discord.app_commands.command(
        name="analyze",
        description="ტრანსპორტის ანალიტიკა"
    )
    async def analyze_transport(self, interaction: discord.Interaction):
        await interaction.response.defer()
    
        try:
            logger.info(f"Starting analysis: {interaction.user.id}")
            async with self.session.get(
                'https://ttc.com.ge/api/passengers',
                headers={'X-Api-Key': self.api_key}
            ) as response:
                if response.status != 200:
                    raise Exception(f"API Error {response.status}")
                data = await response.json()
                stats_data = data['transactionsByTransportTypes']
            
            total_passengers = sum(count for count in stats_data.values())
            top_transport = sorted(stats_data.items(), key=lambda x: x[1], reverse=True)[:3]
            stats_text = (
                f"მგზავრების რაოდენობა: **{total_passengers}**\n"
                f"Top 3 ტრანსპორტები:\n" +
                "\n".join(f"- {mode}: **__{count}__**" for mode, count in top_transport)
            )
        
            analysis = await self.get_ai_analysis(stats_text)
            logger.info(f"Analysis complete: {interaction.user.id}")
            
            embed = discord.Embed(
                title="🚌 ტრანსპორტის ანალიზი",
                description=analysis,
                color=discord.Color.blue()
            )
            embed.add_field(
                name="სტატისტიკა",
                value=stats_text,
                inline=False
            )
            embed.set_footer(text="⚠️ ანალიზი შექმნილია ხელოვნური ინტელექტის გამოყენებით")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Analysis command error: {str(e)}")
            await interaction.followup.send("ანალიზის დროს მოხდა შეცდომა 😔")
    
    @discord.app_commands.command(
        name="stats",
        description="მგზავრების სტატისტიკა"
    )
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            logger.info(f"Getting stats: {interaction.user.id}")
            async with self.session.get(
                'https://ttc.com.ge/api/passengers',
                headers={'X-Api-Key': self.api_key}
            ) as response:
                if response.status != 200:
                    raise Exception(f"API Error {response.status}")
                data = await response.json()

            if not data or 'transactionsByTransportTypes' not in data:
                await interaction.followup.send("სტატისტიკის მიღება ვერ მოხდა 😔")
                return

            stats, total_passengers = self.format_stats(data['transactionsByTransportTypes'])
            embed = await self.create_stats_embed(stats, total_passengers)
            await interaction.followup.send(embed=embed)
            logger.info(f"Stats sent: {interaction.user.id}")

        except Exception as e:
            logger.error(f"Stats command error: {str(e)}")
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

    async def create_stats_embed(self, stats, total_passengers):
        embed = discord.Embed(
            title="📊 მგზავრების სტატისტიკა",
            description=stats,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"👥 მგზავრების რაოდენობა: {total_passengers:,}")
        embed.set_author(name="Tbilisi Transport Company", icon_url=self.bot.user.avatar.url)
        
        try:
            prompt = f"გაგვიზიარე ერთი საინტერესო ფაქტი საზოგადოებრივ ტრანსპორტზე. გაითვალისწინე რომ დღეს {total_passengers:,} ადამიანმა გამოიყენა ტრანსპორტი. პასუხი უნდა იყოს მოკლე, საინტერესო და მგზავრებთან დაკავშირებული. არ გამოიყენო წინასიტყვაობა"
            
            async with self.session.post(
                url=f"{config.OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "HTTP-Referer": config.SITE_URL,
                    "X-Title": config.SITE_NAME,
                    "Content-Type": "application/json"
                },
                json={
                    "model": "google/gemini-2.0-flash-thinking-exp:free",
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    fun_fact = result['choices'][0]['message']['content']
                    embed.add_field(name="⭐ Fun Fact", value=fun_fact, inline=False)
        except Exception as e:
            if config.DEBUG:
                print(f"Error generating fun fact: {e}")
        
        return embed

async def setup(bot):
    await bot.add_cog(Stats(bot))
