import discord
from discord.ext import commands
import requests
import config

class BusRoute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = config.API_KEY

    @discord.app_commands.command(name="busroute", description="List all stops for a given bus route")
    @discord.app_commands.describe(bus_id="Bus ID")
    async def busroute(self, interaction: discord.Interaction, bus_id: str):
        await interaction.response.defer()
        try:
            # Set default patternSuffix to 1:01
            pattern_suffix = "1:01"
            stops_url = f"https://transit.ttc.com.ge/pis-gateway/api/v3/routes/{bus_id}/stops?patternSuffix={pattern_suffix}&locale=ka"
            headers = {"X-Api-Key": self.api_key}
            stops_response = requests.get(stops_url, headers=headers)
            
            if stops_response.status_code != 200:
                await interaction.followup.send(f"Failed to fetch bus stops for the selected route. Status code: {stops_response.status_code}")
                if config.DEBUG:
                    print(f"Request URL: {stops_url}")
                    print(f"Request Headers: {headers}")
                    print(f"Response Status Code: {stops_response.status_code}")
                    print(f"Response Content: {stops_response.content}")
                return
            
            stops_data = stops_response.json()

            if not stops_data:
                await interaction.followup.send("Could not fetch bus stops for the selected route 😔")
                return

            stop_list = [f"🛑 {stop['code']} - {stop['name']}" for stop in stops_data]
            pages = [stop_list[i:i+20] for i in range(0, len(stop_list), 20)]  # 20 stops per page

            embed = self.create_embed(pages[0], 1, len(pages))
            view = self.PaginationView(self, pages, 1, len(pages))
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message

        except Exception as e:
            if config.DEBUG:
                print(f"Error: {e}")
                print(f"Response content: {stops_response.content}")
            await interaction.followup.send("An error occurred 😔")

    @busroute.autocomplete("bus_id")
    async def bus_id_autocomplete(self, interaction: discord.Interaction, current: str):
        url = "https://transit.ttc.com.ge/pis-gateway/api/v3/routes?modes=BUS&locale=ka"
        headers = {"X-Api-Key": self.api_key}
        response = requests.get(url, headers=headers)
        data = response.json()

        routes = [route for route in data if current.lower() in route['shortName'].lower() or current.lower() in route['longName'].lower()]
        return [discord.app_commands.Choice(name=f"{route['shortName']} - {route['longName']}", value=route['id']) for route in routes[:25]]

    def create_embed(self, item_list, current_page, total_pages):
        embed = discord.Embed(title="Bus Stops", description="\n".join(item_list), color=discord.Color.blue())
        embed.set_footer(text=f"Page {current_page} of {total_pages}")
        return embed

    class PaginationView(discord.ui.View):
        def __init__(self, cog, pages, current_page, total_pages):
            super().__init__(timeout=60)  # Buttons will disappear after 60 seconds of inactivity
            self.cog = cog
            self.pages = pages
            self.current_page = current_page
            self.total_pages = total_pages
            self.message = None

            self.update_buttons()

        def update_buttons(self):
            self.children[0].disabled = self.current_page <= 1
            self.children[1].disabled = self.current_page >= self.total_pages

        @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
        async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                if self.current_page > 1:
                    self.current_page -= 1
                    embed = self.cog.create_embed(self.pages[self.current_page - 1], self.current_page, self.total_pages)
                    self.update_buttons()
                    await interaction.response.edit_message(embed=embed, view=self)
            except Exception as e:
                print(f"Error in previous button handler: {e}")
                await interaction.response.send_message("An error occurred while handling the previous button.", ephemeral=True)

        @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                if self.current_page < self.total_pages:
                    self.current_page += 1
                    embed = self.cog.create_embed(self.pages[self.current_page - 1], self.current_page, self.total_pages)
                    self.update_buttons()
                    await interaction.response.edit_message(embed=embed, view=self)
            except Exception as e:
                print(f"Error in next button handler: {e}")
                await interaction.response.send_message("An error occurred while handling the next button.", ephemeral=True)

        async def on_timeout(self):
            for child in self.children:
                child.disabled = True
            if self.message:
                await self.message.edit(view=self)

async def setup(bot):
    await bot.add_cog(BusRoute(bot))