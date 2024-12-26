import discord
from discord.ext import commands
import requests
import config

class Buses(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = config.API_KEY

    @discord.app_commands.command(name="buses", description="ყველა ავტობუსის ჩამონათვალი")
    async def buses(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            url = "https://transit.ttc.com.ge/pis-gateway/api/v3/routes?modes=BUS&locale=ka"
            headers = {"X-Api-Key": self.api_key}
            response = requests.get(url, headers=headers)
            data = response.json()

            if not data:
                await interaction.followup.send("ავტობუსების მოძებნა ვერ მოხერხდა 😔")
                return

            bus_list = [f"🚌 **__{bus['shortName']}__** - {bus['longName']}" for bus in data]
            pages = [bus_list[i:i+20] for i in range(0, len(bus_list), 20)]  # 20 buses per page

            embed = self.create_embed(pages[0], 1, len(pages))
            view = self.PaginationView(self, pages, 1, len(pages))
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message

        except Exception as e:
            if config.DEBUG:
                print(f"Error: {e}")
            await interaction.followup.send("შეცდომა მოხდა 😔")

    def create_embed(self, item_list, current_page, total_pages):
        embed = discord.Embed(title="Bus Routes", description="\n".join(item_list), color=discord.Color.blue())
        embed.set_footer(text=f"გვერდი {current_page} - {total_pages}-დან")
        return embed

    class PaginationView(discord.ui.View):
        def __init__(self, cog, pages, current_page, total_pages):
            super().__init__(timeout=30)  # Buttons will disappear after 60 seconds of inactivity
            self.cog = cog
            self.pages = pages
            self.current_page = current_page
            self.total_pages = total_pages
            self.message = None

            self.update_buttons()

        def update_buttons(self):
            self.children[0].disabled = self.current_page <= 1
            self.children[1].disabled = self.current_page >= self.total_pages

        @discord.ui.button(label="წინა", style=discord.ButtonStyle.primary)
        async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                if self.current_page > 1:
                    self.current_page -= 1
                    embed = self.cog.create_embed(self.pages[self.current_page - 1], self.current_page, self.total_pages)
                    self.update_buttons()
                    await interaction.response.edit_message(embed=embed, view=self)
            except Exception as e:
                print(f"Error in previous button handler: {e}")
                await interaction.response.send_message("შეცდომა მოხდა", ephemeral=True)

        @discord.ui.button(label="შემდეგი", style=discord.ButtonStyle.primary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                if self.current_page < self.total_pages:
                    self.current_page += 1
                    embed = self.cog.create_embed(self.pages[self.current_page - 1], self.current_page, self.total_pages)
                    self.update_buttons()
                    await interaction.response.edit_message(embed=embed, view=self)
            except Exception as e:
                print(f"Error in next button handler: {e}")
                await interaction.response.send_message("შეცდომა მოხდა", ephemeral=True)

        async def on_timeout(self):
            for child in self.children:
                child.disabled = True
            if self.message:
                await self.message.edit(view=self)

async def setup(bot):
    await bot.add_cog(Buses(bot))