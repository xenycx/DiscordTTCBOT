import discord
from discord.ext import commands
import requests
import config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Stop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = config.API_KEY

    @discord.app_commands.command(name="stopinfo", description="გაჩერების ინფორმაცია")
    @discord.app_commands.describe(stop_no="გაჩერების ნომერი ან სახელი")
    async def stopinfo(self, interaction: discord.Interaction, stop_no: str):
        await interaction.response.defer()
        try:
            stop_info_url = f"https://transit.ttc.com.ge/pis-gateway/api/v2/stops?locale={config.LANG}"
            headers = {"X-Api-Key": self.api_key}
            stops_response = requests.get(stop_info_url, headers=headers).json()

            stop = next((stop for stop in stops_response if stop['code'] == stop_no or stop['name'] == stop_no), None)
            if not stop:
                await interaction.followup.send("გაჩერება ვერ მოიძებნა ან ინფორმაცია არ არის ხელმისაწვდომი **(ან ავტობუსები აღარ დადიან)**.")
                return

            stop_no = stop['code']
            stop_info_url = f"https://transit.ttc.com.ge/pis-gateway/api/v2/stops/1:{stop_no}?locale={config.LANG}"
            arrivals_url = f"https://transit.ttc.com.ge/pis-gateway/api/v2/stops/1:{stop_no}/arrival-times?locale={config.LANG}"

            stop_info = requests.get(stop_info_url, headers=headers).json()
            arrivals = requests.get(arrivals_url, headers=headers).json()

            if not stop_info or not arrivals:
                await interaction.followup.send("გაჩერება ვერ მოიძებნა ან ინფორმაცია არ არის ხელმისაწვდომი **(ან ავტობუსები აღარ დადიან)**.")
                return

            if not arrivals:
                await interaction.followup.send("ამ გაჩერებაზე ავტობუსები აღარ დადიან.")
                return

            embed = discord.Embed(title=f"🏁 გაჩერება #{stop_no} - {stop_info.get('name', 'Unknown')}", color=discord.Color.blue())
            arrival_texts = [self.format_arrival_time(arrival) for arrival in sorted(arrivals, key=lambda x: x.get('realtimeArrivalMinutes', 999))]
            embed.add_field(name="მომსვლელი ავტობუსები", value="\n".join(arrival_texts), inline=False)

            await interaction.followup.send(embed=embed)

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

    @stopinfo.autocomplete("stop_no")
    async def stop_no_autocomplete(self, interaction: discord.Interaction, current: str):
        stop_info_url = f"https://transit.ttc.com.ge/pis-gateway/api/v2/stops?locale={config.LANG}"
        headers = {"X-Api-Key": self.api_key}
        try:
            stops_response = requests.get(stop_info_url, headers=headers)
            stops_response.raise_for_status() 
            stops_data = stops_response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch stop info: {e}")
            return []

        stops = [stop for stop in stops_data if stop['code'] and stop['name'] and (current.lower() in stop['code'].lower() or current.lower() in stop['name'].lower())]
        return [discord.app_commands.Choice(name=f"{stop['code']} - {stop['name']}", value=stop['code']) for stop in stops[:25]]

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
    await bot.add_cog(Stop(bot))