import discord
from discord.ext import commands
import config
import requests
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = config.API_KEY
        
        # Configure Google AI
        self.client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        self.google_search_tool = Tool(
            google_search=GoogleSearch()
        )
        
    @discord.app_commands.command(
        name="analyze",
        description="ტრანსპორტის ანალიტიკა"
    )
    async def analyze_transport(self, interaction: discord.Interaction):
        await interaction.response.defer()
    
        try:
            # Fetch current stats
            url = 'https://ttc.com.ge/api/passengers'
            headers = {'X-Api-Key': self.api_key}
            response = requests.get(url, headers=headers)
            data = response.json()['transactionsByTransportTypes']
            
            # Format data for analysis
            total_passengers = sum(count for count in data.values())
            top_transport = sorted(data.items(), key=lambda x: x[1], reverse=True)[:3]
            stats_text = (
                f"მგზავრების რაოდენობა: **{total_passengers}**\n"
                f"Top 3 ტრანსპორტები:\n" +
                "\n".join(f"- {mode}: **__{count}__**" for mode, count in top_transport)
            )
        
            # Query Google AI
            prompt = f"""
            მოცემულია სატრანსპორტო მონაცემები. უშუალოდ, როგორც ანალიტიკოსმა, ქართულად წარმოადგინე 3 ძირითადი დასკვნა, რომლებიც გამომდინარეობს ამ მონაცემებიდან. არ გამოიყენო წინასიტყვაობა.
            {stats_text}
            """
            
            response = await self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=600,
                    response_modalities=["TEXT"],
                    tools=[self.google_search_tool]
                )
            )
            
            analysis = response.candidates[0].content.parts[0].text
            
            # Create embed response
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
            embed.set_footer(text="⚠️ სტატისტიკა შექმნილია ხელოვნური ინტელექტის გამოყენებით")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            if config.DEBUG:
                print(f"Error in analyze command: {e}")
            await interaction.followup.send("ანალიზის დროს მოხდა შეცდომა 😔")
    
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
            embed = await self.create_embed(stats, total_passengers)
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

    async def create_embed(self, stats, total_passengers):
        embed = discord.Embed(title="📊 მგზავრების სტატისტიკა", description=stats, color=discord.Color.blue())
        embed.set_footer(text=f"👥 მგზავრების რაოდენობა: {total_passengers:,}")
        embed.set_author(name="Tbilisi Transport Company", icon_url=self.bot.user.avatar.url)
        
        try:
            prompt = f"გაგვიზიარე ერთი საინტერესო ფაქტი საზოგადოებრივ ტრანსპორტზე. გაითვალისწინე რომ დღეს {total_passengers:,} ადამიანმა გამოიყენა ტრანსპორტი. პასუხი უნდა იყოს მოკლე, საინტერესო და მგზავრებთან დაკავშირებული. არ გამოიყენო წინასიტყვაობა"
            
            response = await self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.6,
                    max_output_tokens=200,
                    response_modalities=["TEXT"],
                    tools=[self.google_search_tool]
                )
            )
            ai_comment = response.candidates[0].content.parts[0].text
            embed.add_field(name="⭐ Fun Fact ", value=ai_comment, inline=False)
        except Exception as e:
            if config.DEBUG:
                print(f"Error generating AI comment: {e}")
        
        return embed

async def setup(bot):
    await bot.add_cog(Stats(bot))
