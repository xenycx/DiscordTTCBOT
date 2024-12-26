import discord
from discord.ext import commands
import requests
import config

class Stops(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = config.API_KEY

    @discord.app_commands.command(name="stops", description="გაჩერებების ჩამონათვალი და ინფორმაცია")
    @discord.app_commands.describe(search="ძებნა (არასავალდებულო)")
    async def stops(self, interaction: discord.Interaction, search: str = None):
        await interaction.response.defer()
        try:
            url = "https://transit.ttc.com.ge/pis-gateway/api/v2/stops?locale=ka"
            headers = {"X-Api-Key": self.api_key}
            response = requests.get(url, headers=headers)
            data = response.json()

            if not data:
                await interaction.followup.send("გაჩერებების ჩამონათვლის მიღება ვერ მოხდა 😔")
                return

            # Filter stops based on search term if provided
            stop_list = [f"🛑 {stop['code']} - {stop['name']}" for stop in data if not search or search.lower() in stop['code'].lower() or search.lower() in stop['name'].lower()]
            
            if not stop_list:
                await interaction.followup.send("გაჩერებები ვერ მოიძებნა 🔍")
                return

            # Split into pages (20 stops per page)
            pages = [stop_list[i:i+20] for i in range(0, len(stop_list), 20)]

            embed = self.create_embed(pages[0], 1, len(pages))
            view = self.PaginationView(self, pages, 1, len(pages), interaction, self.api_key, initial_pages=pages, is_search=False)
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message

        except requests.RequestException as e:
            if config.DEBUG:
                print(f"Request error: {e}")
            await interaction.followup.send("შეცდომა მოხდა 😔")
        except discord.errors.NotFound:
            if config.DEBUG:
                print("Interaction not found or timed out.")
        except Exception as e:
            if config.DEBUG:
                print(f"Unexpected error: {e}")
            await interaction.followup.send("შეცდომა მოხდა 😔")

    def create_embed(self, stop_list, current_page, total_pages):
        embed = discord.Embed(title="ავტობუსის გაჩერებები", description="\n".join(stop_list), color=discord.Color.blue())
        embed.set_footer(text=f"გვერდი {current_page} - {total_pages}-დან")
        return embed

    class PaginationView(discord.ui.View):
        def __init__(self, cog, pages, current_page, total_pages, interaction, api_key, initial_pages, is_search):
            super().__init__(timeout=60)
            self.cog = cog
            self.pages = pages
            self.current_page = current_page
            self.total_pages = total_pages
            self.message = None
            self.interaction = interaction
            self.api_key = api_key
            self.initial_pages = initial_pages
            self.is_search = is_search

            self.update_buttons()
            self.update_select_options()

        def update_buttons(self):
            self.children[0].disabled = self.current_page <= 1  # Previous button
            self.children[2].disabled = self.current_page >= self.total_pages  # Next button
            self.children[3].disabled = self.is_search  # Search button
            self.children[4].disabled = not self.is_search  # Main menu button

        def update_select_options(self):
            select = self.children[1]
            select.options = [
                discord.SelectOption(label=stop.split(" - ")[1], value=stop.split(" - ")[0].replace("🛑 ", ""))
                for stop in self.pages[self.current_page - 1]
            ]

        @discord.ui.button(label="წინა", style=discord.ButtonStyle.primary)
        async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                if self.current_page > 1:
                    self.current_page -= 1
                    embed = self.cog.create_embed(self.pages[self.current_page - 1], self.current_page, self.total_pages)
                    self.update_buttons()
                    self.update_select_options()
                    await interaction.response.edit_message(embed=embed, view=self)
            except Exception as e:
                print(f"Error in previous button handler: {e}")
                await interaction.response.send_message("შეცდომა მოხდა", ephemeral=True)

        @discord.ui.select(placeholder="აირჩიეთ გაჩერება", min_values=1, max_values=1, options=[])
        async def select_stop(self, interaction: discord.Interaction, select: discord.ui.Select):
            stop_code = select.values[0]
            await self.show_stop_info(interaction, stop_code)

        @discord.ui.button(label="ძიება", style=discord.ButtonStyle.secondary)
        async def search(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(self.cog.SearchModal(self.cog, self.pages, self.current_page, self.total_pages, self.message))

        @discord.ui.button(label="შემდეგი", style=discord.ButtonStyle.primary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                if self.current_page < self.total_pages:
                    self.current_page += 1
                    embed = self.cog.create_embed(self.pages[self.current_page - 1], self.current_page, self.total_pages)
                    self.update_buttons()
                    self.update_select_options()
                    await interaction.response.edit_message(embed=embed, view=self)
            except Exception as e:
                print(f"Error in next button handler: {e}")
                await interaction.response.send_message("შეცდომა მოხდა", ephemeral=True)

        @discord.ui.button(label="მთავარი მენიუ", style=discord.ButtonStyle.secondary)
        async def main_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                self.pages = self.initial_pages
                self.current_page = 1
                self.total_pages = len(self.pages)
                self.is_search = False
                embed = self.cog.create_embed(self.pages[0], self.current_page, self.total_pages)
                self.update_buttons()
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception as e:
                print(f"Error in main menu button handler: {e}")
                await interaction.response.send_message("შეცდომა მოხდა", ephemeral=True)

        async def show_stop_info(self, interaction: discord.Interaction, stop_code: str):
            try:
                stop_info_url = f"https://transit.ttc.com.ge/pis-gateway/api/v2/stops/1:{stop_code}?locale={config.LANG}"
                arrivals_url = f"https://transit.ttc.com.ge/pis-gateway/api/v2/stops/1:{stop_code}/arrival-times?locale={config.LANG}"
                headers = {"X-Api-Key": self.api_key}

                stop_info = requests.get(stop_info_url, headers=headers).json()
                arrivals = requests.get(arrivals_url, headers=headers).json()

                if not stop_info or not arrivals:
                    await interaction.response.send_message("გაჩერება ვერ მოიძებნა ან ინფორმაცია არ არის ხელმისაწვდომი (ან ავტობუსები აღარ დადიან).", ephemeral=True)
                    return

                if not arrivals:
                    await interaction.response.send_message("ამ გაჩერებაზე ავტობუსები აღარ დადიან.", ephemeral=True)
                    return

                embed = discord.Embed(title=f"🏁 გაჩერება #{stop_code} - {stop_info.get('name', 'Unknown')}", color=discord.Color.blue())
                arrival_texts = [self.cog.format_arrival_time(arrival) for arrival in sorted(arrivals, key=lambda x: x.get('realtimeArrivalMinutes', 999))]
                embed.add_field(name="მომსვლელი ავტობუსები", value="\n".join(arrival_texts), inline=False)

                await interaction.response.send_message(embed=embed, ephemeral=True)

            except requests.RequestException as e:
                if config.DEBUG:
                    print(f"Request error: {e}")
                await interaction.response.send_message("შეცდომა მოხდა 😔", ephemeral=True)
            except discord.errors.NotFound:
                if config.DEBUG:
                    print("Interaction not found or timed out.")
            except Exception as e:
                if config.DEBUG:
                    print(f"Unexpected error: {e}")
                await interaction.response.send_message("შეცდომა მოხდა 😔", ephemeral=True)

        async def on_timeout(self):
            for child in self.children:
                child.disabled = True
            if self.message:
                await self.message.edit(view=self)

    class SearchModal(discord.ui.Modal, title="ძიება"):
        search_input = discord.ui.TextInput(label="ძებნა", placeholder="გაჩერების კოდი ან სახელი")

        def __init__(self, cog, pages, current_page, total_pages, message):
            super().__init__()
            self.cog = cog
            self.pages = pages
            self.current_page = current_page
            self.total_pages = total_pages
            self.message = message

        async def on_submit(self, interaction: discord.Interaction):
            try:
                # First acknowledge the modal submission
                await interaction.response.defer()
                
                search_term = self.search_input.value
                stop_list = []
                for page in self.pages:
                    for stop in page:
                        if search_term.lower() in stop.lower():
                            stop_list.append(stop)

                if not stop_list:
                    await interaction.followup.send("გაჩერებები ვერ მოიძებნა 🔍", ephemeral=True)
                    return

                pages = [stop_list[i:i+20] for i in range(0, len(stop_list), 20)]
                embed = self.cog.create_embed(pages[0], 1, len(pages))
                view = self.cog.PaginationView(self.cog, pages, 1, len(pages), interaction, self.cog.api_key, initial_pages=self.pages, is_search=True)
                view.message = self.message

                # Use followup instead of edit directly
                await self.message.edit(embed=embed, view=view)

            except Exception as e:
                if config.DEBUG:
                    print(f"Search modal error: {e}")
                await interaction.followup.send("შეცდომა მოხდა, სცადეთ თავიდან", ephemeral=True)

    def format_arrival_time(self, arrival):
        mode_emoji = {"BUS": "🚌", "METRO": "🚇", "MINIBUS": "🚐"}.get(arrival.get("vehicleMode", "BUS"), "🚌")
        route = arrival.get("shortName", "Unknown Route")
        destination = arrival.get("headsign", "Unknown Destination")
        minutes = arrival.get("realtimeArrivalMinutes", arrival.get("scheduledArrivalMinutes", "N/A"))
        if isinstance(minutes, (int, float)) and minutes > 0:
            time_text = f"{int(minutes)} წთ ⏳"
        else:
            time_text = "მოდის ⌛"
        return f"{mode_emoji} - **__{route}__** -> {destination}: **__{time_text}__**"

async def setup(bot):
    await bot.add_cog(Stops(bot))