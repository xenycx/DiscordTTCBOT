import discord
from discord.ext import commands
import requests
import config

class Buses(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = config.API_KEY

    @discord.app_commands.command(name="buses", description="List all bus routes")
    async def buses(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            url = "https://transit.ttc.com.ge/pis-gateway/api/v3/routes?modes=BUS&locale=ka"
            headers = {"X-Api-Key": self.api_key}
            response = requests.get(url, headers=headers)
            data = response.json()

            if not data:
                await interaction.followup.send("Could not fetch bus routes 😔")
                return

            bus_list = [f"🚌 {bus['shortName']} - {bus['longName']}" for bus in data]
            pages = [bus_list[i:i+20] for i in range(0, len(bus_list), 20)]  # 20 buses per page

            embed = self.create_embed(pages[0], 1, len(pages))
            view = self.PaginationView(pages, 1, len(pages))
            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            if config.DEBUG:
                print(f"Error: {e}")
            await interaction.followup.send("An error occurred 😔")

    def create_embed(self, bus_list, current_page, total_pages):
        embed = discord.Embed(title="Bus Routes", description="\n".join(bus_list), color=discord.Color.blue())
        embed.set_footer(text=f"Page {current_page} of {total_pages}")
        return embed

    class PaginationView(discord.ui.View):
        def __init__(self, pages, current_page, total_pages):
            super().__init__()
            self.pages = pages
            self.current_page = current_page
            self.total_pages = total_pages

        @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
        async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page > 1:
                self.current_page -= 1
                embed = Buses.create_embed(self, self.pages[self.current_page - 1], self.current_page, self.total_pages)
                await interaction.response.edit_message(embed=embed, view=self)

        @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page < self.total_pages:
                self.current_page += 1
                embed = Buses.create_embed(self, self.pages[self.current_page - 1], self.current_page, self.total_pages)
                await interaction.response.edit_message(embed=embed, view=self)

async def setup(bot):
    await bot.add_cog(Buses(bot))