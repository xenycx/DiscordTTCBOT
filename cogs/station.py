import discord
from discord.ext import commands
import requests
import config

class Station(commands.Cog):
   def __init__(self, bot):
      self.bot = bot
      self.api_key = config.API_KEY

   @discord.app_commands.command(name="stopinfo", description="გაჩერების მისვლის დროების ნახვა")
   @discord.app_commands.describe(stop_no="გაჩერების ნომერი")
   async def stopinfo(self, interaction: discord.Interaction, stop_no: int):
      await interaction.response.defer()
      try:
         stop_info_url = f"https://transit.ttc.com.ge/pis-gateway/api/v2/stops/1:{stop_no}?locale={config.LANG}"
         arrivals_url = f"https://transit.ttc.com.ge/pis-gateway/api/v2/stops/1:{stop_no}/arrival-times?locale={config.LANG}"

         headers = {"X-Api-Key": self.api_key}
         stop_info = requests.get(stop_info_url, headers=headers).json()
         arrivals = requests.get(arrivals_url, headers=headers).json()

         if not stop_info or not arrivals:
            await interaction.followup.send("გაჩერება ვერ მოიძებნა ან მონაცემები არ არის ხელმისაწვდომი.")
            return

         response_lines = [f"🏁 გაჩერება #{stop_no} - {stop_info.get('name', 'უცნობი')}"]
         for arrival in sorted(arrivals, key=lambda x: x.get('realtimeArrivalMinutes', 999)):
            response_lines.append(self.format_arrival_time(arrival))

         await interaction.followup.send("\n".join(response_lines))

      except Exception as e:
         if config.DEBUG:
            print(f"შეცდომა: {e}")
         await interaction.followup.send("დაფიქსირდა შეცდომა 😔")

   def format_arrival_time(self, arrival):
      mode_emoji = {"BUS": "🚌", "METRO": "🚇", "MINIBUS": "🚐"}.get(arrival.get("vehicleMode", "BUS"), "🚌")
      minutes = arrival.get("realtimeArrivalMinutes", arrival.get("scheduledArrivalMinutes", "არ არის ხელმისაწვდომი"))
      time_text = f"{int(minutes)}წთ" if isinstance(minutes, (int, float)) and minutes > 0 else "მოდის"
      return f"{mode_emoji} {arrival.get('shortName', 'N/A')} → {arrival.get('headsign', 'უცნობი')}: {time_text}"

async def setup(bot):
   await bot.add_cog(Station(bot))