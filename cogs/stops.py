import discord
from discord.ext import commands
import requests
import config

class Stops(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = config.API_KEY

    @discord.app_commands.command(name="stops", description="List all bus stops")
    async def stops(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            url = "https://transit.ttc.com.ge/pis-gateway/api/v2/stops?locale=ka"
            headers = {"X-Api-Key": self.api_key}
            response = requests.get(url, headers=headers)
            data = response.json()

            if not data:
                await interaction.followup.send("Could not fetch bus stops 😔")
                return

            stop_list = [f"🛑 {stop['code']} - {stop['name']}" for stop in data if stop['code']]
            pages = [stop_list[i:i+20] for i in range(0, len(stop_list), 20)]  # 20 stops per page

            embed = self.create_embed(pages[0], 1, len(pages))
            view = self.PaginationView(pages, 1, len(pages))
            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            if config.DEBUG:
                print(f"Error: {e}")
            await interaction.followup.send("An error occurred 😔")

    def create_embed(self, stop_list, current_page, total_pages):
        embed = discord.Embed(title="Bus Stops", description="\n".join(stop_list), color=discord.Color.blue())
        embed.set_footer(text=f"Page {current_page} of {total_pages}")
        return embed

    class PaginationView(discord.ui.View):
        def __init__(self, pages, current_page, total_pages):
            super().__init__(timeout=60)  # Buttons will disappear after 60 seconds of inactivity
            self.pages = pages
            self.current_page = current_page
            self.total_pages = total_pages

        @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
        async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page > 1:
                self.current_page -= 1
                embed = Stops.create_embed(self, self.pages[self.current_page - 1], self.current_page, self.total_pages)
                await interaction.response.edit_message(embed=embed, view=self)

        @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page < self.total_pages:
                self.current_page += 1
                embed = Stops.create_embed(self, self.pages[self.current_page - 1], self.current_page, self.total_pages)
                await interaction.response.edit_message(embed=embed, view=self)

        async def on_timeout(self):
            for child in self.children:
                child.disabled = True
            await self.message.edit(view=self)

async def setup(bot):
    await bot.add_cog(Stops(bot))