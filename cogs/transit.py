"""Live Tbilisi transit commands: arrivals, routes, live vehicle maps, nearby, alerts."""

from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from ttc import TTCClient, TTCError
from ttc.client import route_color, stop_latlon
from ttc.maprender import Line, MapRenderer, MapScene, Pin, Stop, Vehicle
from ttc.polyline import decode

log = logging.getLogger("cogs.transit")

MODE_EMOJI = {"BUS": "🚌", "SUBWAY": "🚇", "METRO": "🚇", "GONDOLA": "🚡", "MINIBUS": "🚐"}
MODE_NAME = {"BUS": "ავტობუსი", "SUBWAY": "მეტრო", "GONDOLA": "საბაგირო", "MINIBUS": "მიკროავტობუსი"}
ERR = "⚠️ TTC-ის სერვერთან დაკავშირება ვერ მოხერხდა. სცადე ცოტა ხანში."


def _color_int(hex_color: str) -> int:
    return int(hex_color.lstrip("#"), 16)


def _mins(a: dict) -> int | None:
    for k in ("realtimeArrivalMinutes", "scheduledArrivalMinutes"):
        v = a.get(k)
        if isinstance(v, (int, float)):
            return int(v)
    return None


def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


def _stop_title(st: dict) -> str:
    code = st.get("code")
    return f"{st.get('name', '?')} [{code}]" if code else st.get("name", "?")


def _pattern_label(p: dict, fallback: str) -> str:
    return p.get("headsign") or p.get("name") or p.get("destination") or fallback


@dataclass
class Watch:
    user_id: int
    stop: dict
    route: dict
    minutes: int
    expires: float
    channel_id: int | None


class Transit(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api = TTCClient(locale=config.LANG, api_key=config.API_KEY or None,
                             on_key_change=self._key_changed)
        self.maps = MapRenderer()
        self.watches: list[Watch] = []
        self.watch_loop.start()

    async def cog_unload(self):
        self.watch_loop.cancel()
        await self.api.close()
        await self.maps.close()

    def _key_changed(self, old: str, new: str, source: str):
        logging.getLogger("ai.cog").warning(f"TTC API key rotated (…{old[-6:]} → …{new[-6:]}) via {source}")

    # ================================================================ helpers
    def _arrivals_embed(self, stop: dict, arrivals: list[dict], route_filter: str | None = None) -> discord.Embed:
        mode = stop.get("vehicleMode", "BUS")
        e = discord.Embed(
            title=f"{MODE_EMOJI.get(mode, '🚏')} {_stop_title(stop)}",
            color=0x1F6FEB,
            timestamp=discord.utils.utcnow(),
        )
        if not arrivals:
            e.description = "ამ გაჩერებაზე ახლო მომავალში ტრანსპორტი არ მოდის. 💤"
        else:
            lines = []
            for a in sorted(arrivals, key=lambda x: _mins(x) if _mins(x) is not None else 999)[:20]:
                m = _mins(a)
                live = "📡" if a.get("realtime") else "🕒"
                when = "**ახლა მოდის**" if m is not None and m <= 0 else f"**{m} წთ**" if m is not None else "—"
                sched = a.get("scheduledArrivalMinutes")
                extra = f" *(განრ. {sched})*" if a.get("realtime") and isinstance(sched, (int, float)) and sched != m else ""
                lines.append(f"{MODE_EMOJI.get(a.get('vehicleMode', 'BUS'), '🚌')} `{a.get('shortName', '?'):>4}` → "
                             f"{a.get('headsign', '?')} · {when} {live}{extra}")
            e.description = "\n".join(lines)
        if route_filter:
            e.set_author(name=f"ფილტრი: მარშრუტი {route_filter}")
        e.set_footer(text="📡 რეალური დრო · 🕒 განრიგით · TTC")
        return e

    async def _stop_map(self, stop: dict) -> discord.File | None:
        here = stop_latlon(stop)
        if not here:
            return None
        nearby = [s for s in await self.api.stops() if s.get("id") != stop.get("id") and stop_latlon(s)
                  and _haversine(here, stop_latlon(s)) < 450]
        scene = MapScene(title=stop.get("name", ""), subtitle=f"გაჩერება #{stop.get('code', '')}",
                         width=1000, height=700, max_zoom=17)
        scene.stops = [Stop(*stop_latlon(s), color="#8b949e", label=s.get("code")) for s in nearby[:25]]
        scene.stops.append(Stop(*here, color="#e5534b", highlight=True))
        return discord.File(await self.maps.render(scene), filename="stop.png")

    async def _route_view_payload(self, route_id: str, suffix: str | None):
        route = await self.api.route(route_id)
        patterns = route.get("patterns") or []
        suffixes = [p["patternSuffix"] for p in patterns if p.get("patternSuffix")]
        suffix = suffix or route.get("defaultPatternSuffix") or (suffixes[0] if suffixes else None)
        if not suffix:
            raise TTCError("route has no patterns")
        color = route_color(route)
        mode = route.get("mode") or route.get("vehicleMode") or "BUS"

        stops = await self.api.route_stops(route_id, suffix)
        try:
            polylines = await self.api.route_polylines(route_id, suffixes)
        except TTCError:
            polylines = {}
        try:
            positions = await self.api.route_positions(route_id, suffixes)
        except TTCError:
            positions = {}

        current = next((p for p in patterns if p.get("patternSuffix") == suffix), {})
        last_stop = stops[-1].get("name") if stops else None
        first_stop = stops[0].get("name") if stops else None
        heading_to = _pattern_label(current, last_stop or suffix)

        scene = MapScene(title=f"{route.get('shortName', '')} — {route.get('longName', '')}"[:70],
                         subtitle=f"მიმართულება: {heading_to}", max_zoom=16)
        for s in suffixes:
            pts = decode(((polylines or {}).get(s) or {}).get("encodedValue", ""))
            if pts:
                scene.lines.append(Line(pts, color=color, width=7, faded=(s != suffix)))
        for i, st in enumerate(stops):
            ll = stop_latlon(st)
            if ll:
                edge = i in (0, len(stops) - 1)
                scene.stops.append(Stop(*ll, color=color, highlight=edge,
                                        label=st.get("name") if edge else None))
        vehicles = (positions or {}).get(suffix) or []
        for v in vehicles:
            if v.get("lat") is not None and v.get("lon") is not None:
                scene.vehicles.append(Vehicle(float(v["lat"]), float(v["lon"]), v.get("heading"), color=color,
                                              label=str(route.get("shortName", ""))[:3]))

        e = discord.Embed(
            title=f"{MODE_EMOJI.get(mode, '🚌')} {route.get('shortName', '?')} · {route.get('longName', '')}",
            color=_color_int(color),
            timestamp=discord.utils.utcnow(),
        )
        e.add_field(name="მიმართულება", value=f"{first_stop or '?'} → **{heading_to}**", inline=False)
        e.add_field(name="გაჩერებები", value=str(len(stops)))
        e.add_field(name="ხაზზე ახლა", value=f"{len(vehicles)} {MODE_EMOJI.get(mode, '🚌')}")
        e.add_field(name="ტიპი", value=MODE_NAME.get(mode, mode))
        next_stop_ids = {v.get("nextStopId") for v in vehicles}
        if stops and next_stop_ids:
            approaching = [st.get("name") for st in stops if st.get("id") in next_stop_ids][:6]
            if approaching:
                e.add_field(name="ტრანსპორტი უახლოვდება", value="\n".join(f"• {n}" for n in approaching), inline=False)
        e.set_image(url="attachment://route.png")
        e.set_footer(text="განახლდა")
        file = discord.File(await self.maps.render(scene), filename="route.png")
        return route, suffix, stops, e, file

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        log.exception("command %s failed", interaction.command and interaction.command.name, exc_info=error)
        msg = "😔 შეცდომა მოხდა. სცადე თავიდან."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass

    # ============================================================ autocomplete
    async def stop_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            stops = await self.api.stops()
        except TTCError:
            return []
        return [app_commands.Choice(name=_stop_title(s)[:100], value=str(s.get("id")))
                for s in TTCClient.search_stops(stops, current, 25) if s.get("id")]

    async def route_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            routes = await self.api.routes()
        except TTCError:
            return []
        return [app_commands.Choice(
            name=f"{MODE_EMOJI.get(r.get('mode', 'BUS'), '')} {r.get('shortName', '')} — {r.get('longName', '')}"[:100],
            value=str(r.get("id")))
            for r in TTCClient.search_routes(routes, current, 25) if r.get("id")]

    # ================================================================ commands
    @app_commands.command(name="stop", description="🚏 გაჩერებაზე მომავალი ტრანსპორტი რეალურ დროში")
    @app_commands.describe(stop="გაჩერების ნომერი ან სახელი", route="მხოლოდ ეს მარშრუტი (არასავალდებულო)")
    @app_commands.autocomplete(stop=stop_autocomplete, route=route_autocomplete)
    async def stop_cmd(self, interaction: discord.Interaction, stop: str, route: str | None = None):
        await interaction.response.defer()
        try:
            st = await self.api.find_stop(stop)
            if not st:
                return await interaction.followup.send(f"❌ გაჩერება `{stop}` ვერ მოიძებნა.")
            arrivals = await self.api.arrivals(st["id"], route_id=route)
        except TTCError as e:
            log.warning("stop %s failed: %s", stop, e)
            return await interaction.followup.send(ERR)
        r_name = None
        if route:
            r = await self.api.find_route(route)
            r_name = r.get("shortName") if r else route
        view = StopView(self, st, route, r_name, interaction.user.id)
        view.message = await interaction.followup.send(embed=self._arrivals_embed(st, arrivals, r_name), view=view)

    @app_commands.command(name="bus", description="🗺️ მარშრუტის რუკა ცოცხალი ტრანსპორტით")
    @app_commands.describe(route="მარშრუტის ნომერი (მაგ. 37, M1)")
    @app_commands.autocomplete(route=route_autocomplete)
    async def bus_cmd(self, interaction: discord.Interaction, route: str):
        await interaction.response.defer()
        try:
            r = await self.api.find_route(route)
            if not r:
                return await interaction.followup.send(f"❌ მარშრუტი `{route}` ვერ მოიძებნა.")
            full, suffix, stops, embed, file = await self._route_view_payload(r["id"], None)
        except TTCError as e:
            log.warning("route %s failed: %s", route, e)
            return await interaction.followup.send(ERR)
        view = RouteView(self, full, suffix, stops)
        view.message = await interaction.followup.send(embed=embed, file=file, view=view)

    @app_commands.command(name="routes", description="📋 ყველა მარშრუტის სია")
    @app_commands.describe(mode="ტრანსპორტის ტიპი")
    @app_commands.choices(mode=[app_commands.Choice(name="🚌 ავტობუსი", value="BUS"),
                                app_commands.Choice(name="🚇 მეტრო", value="SUBWAY"),
                                app_commands.Choice(name="🚡 საბაგირო", value="GONDOLA")])
    async def routes_cmd(self, interaction: discord.Interaction, mode: str | None = None):
        await interaction.response.defer()
        try:
            routes = await self.api.routes([mode] if mode else ("BUS", "SUBWAY", "GONDOLA"))
        except TTCError:
            return await interaction.followup.send(ERR)

        def sort_key(r):
            m = re.match(r"(\d+)", str(r.get("shortName", "")))
            return (0, int(m.group(1)), "") if m else (1, 0, str(r.get("shortName", "")))

        rows = [f"{MODE_EMOJI.get(r.get('mode', mode or 'BUS'), '🚌')} **{r.get('shortName', '?')}** — {r.get('longName', '')}"
                for r in sorted(routes, key=sort_key)]
        await Paginator.send(interaction, f"📋 მარშრუტები ({len(rows)})", rows, per_page=20)

    @app_commands.command(name="stops", description="🔎 გაჩერებების ძებნა")
    @app_commands.describe(query="სახელი ან ნომერი")
    async def stops_cmd(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        try:
            stops = await self.api.stops()
        except TTCError:
            return await interaction.followup.send(ERR)
        found = TTCClient.search_stops(stops, query, 200)
        if not found:
            return await interaction.followup.send(f"❌ `{query}` — ვერაფერი მოიძებნა.")
        rows = [f"{MODE_EMOJI.get(s.get('vehicleMode', 'BUS'), '🚏')} `{s.get('code') or '—':>5}` {s.get('name', '')}" for s in found]
        await Paginator.send(interaction, f"🔎 „{query}“ — {len(rows)} გაჩერება", rows, per_page=20,
                             footer="დეტალებისთვის: /stop <ნომერი>")

    @app_commands.command(name="nearby", description="📍 უახლოესი გაჩერებები მისამართთან ან კოორდინატებთან")
    @app_commands.describe(place="მისამართი/ადგილი, ან კოორდინატები: 41.7151, 44.8271")
    async def nearby_cmd(self, interaction: discord.Interaction, place: str):
        await interaction.response.defer()
        m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*", place)
        try:
            if m:
                here, label = (float(m.group(1)), float(m.group(2))), place
            else:
                feats = await self.api.geocode(place)
                feat = next((f for f in feats if (f.get("geometry") or {}).get("coordinates")), None)
                if not feat:
                    return await interaction.followup.send(f"❌ ადგილი „{place}“ ვერ მოიძებნა.")
                lon, lat = feat["geometry"]["coordinates"][:2]
                here = (float(lat), float(lon))
                props = feat.get("properties") or {}
                label = props.get("name") or props.get("label") or place
            stops = await self.api.stops()
        except TTCError:
            return await interaction.followup.send(ERR)
        ranked = sorted(((s, _haversine(here, stop_latlon(s))) for s in stops if stop_latlon(s) and s.get("code")),
                        key=lambda x: x[1])[:8]
        if not ranked or ranked[0][1] > 5000:
            return await interaction.followup.send("❌ ახლოს გაჩერება ვერ მოიძებნა (თბილისის ფარგლებს გარეთ?).")
        e = discord.Embed(title=f"📍 {label}", color=0xE5534B, description="\n".join(
            f"`{i + 1}.` {MODE_EMOJI.get(s.get('vehicleMode', 'BUS'), '🚏')} **{s.get('name')}** `#{s.get('code')}` — "
            f"{int(d)} მ (~{max(1, round(d / 80))} წთ ფეხით)" for i, (s, d) in enumerate(ranked)))
        scene = MapScene(title=label[:60], subtitle="უახლოესი გაჩერებები", width=1000, height=700, max_zoom=17)
        scene.pins.append(Pin(*here, label="შენ"))
        scene.stops = [Stop(*stop_latlon(s), color="#1f6feb", label=f"{i + 1}. #{s.get('code')}")
                       for i, (s, _) in enumerate(ranked)]
        file = discord.File(await self.maps.render(scene), filename="nearby.png")
        e.set_image(url="attachment://nearby.png")
        e.set_footer(text="არრივალებისთვის: /stop <ნომერი>")
        await interaction.followup.send(embed=e, file=file)

    @app_commands.command(name="watch", description="🔔 შეგატყობინებ DM-ში, როცა ტრანსპორტი გაჩერებას მიუახლოვდება")
    @app_commands.describe(stop="გაჩერება", route="მარშრუტი", minutes="რამდენი წუთით ადრე შეგატყობინო (1-30)")
    @app_commands.autocomplete(stop=stop_autocomplete, route=route_autocomplete)
    async def watch_cmd(self, interaction: discord.Interaction, stop: str, route: str,
                        minutes: app_commands.Range[int, 1, 30] = 5):
        await interaction.response.defer(ephemeral=True)
        try:
            st, rt = await self.api.find_stop(stop), await self.api.find_route(route)
        except TTCError:
            return await interaction.followup.send(ERR, ephemeral=True)
        if not st or not rt:
            return await interaction.followup.send("❌ გაჩერება ან მარშრუტი ვერ მოიძებნა.", ephemeral=True)
        mine = [w for w in self.watches if w.user_id == interaction.user.id]
        if len(mine) >= 3:
            return await interaction.followup.send("❌ მაქსიმუმ 3 აქტიური შეხსენება. გამოიყენე /unwatch.", ephemeral=True)
        self.watches.append(Watch(interaction.user.id, st, rt, minutes, time.time() + 3600,
                                  interaction.channel_id))
        await interaction.followup.send(
            f"🔔 შეგატყობინებ, როცა **{rt.get('shortName')}** იქნება ≤ **{minutes} წთ**-ში "
            f"გაჩერებასთან **{_stop_title(st)}**. (აქტიურია 1 საათი)", ephemeral=True)

    @app_commands.command(name="unwatch", description="🔕 ყველა შენი შეხსენების გაუქმება")
    async def unwatch_cmd(self, interaction: discord.Interaction):
        before = len(self.watches)
        self.watches = [w for w in self.watches if w.user_id != interaction.user.id]
        await interaction.response.send_message(f"🔕 გაუქმდა {before - len(self.watches)} შეხსენება.", ephemeral=True)

    @app_commands.command(name="apistatus", description="🩺 TTC API-ის მდგომარეობა")
    async def apistatus_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        t = time.perf_counter()
        try:
            n = len(await self.api.stops())
            ok = f"✅ მუშაობს · {n} გაჩერება · {(time.perf_counter() - t) * 1000:.0f} ms"
        except TTCError as e:
            ok = f"❌ {e}"
        await interaction.followup.send(f"{ok}\n🔑 გასაღების წყარო: `{self.api.key_source}`", ephemeral=True)

    # ================================================================== watch
    @tasks.loop(seconds=30)
    async def watch_loop(self):
        now = time.time()
        self.watches = [w for w in self.watches if w.expires > now]
        for w in list(self.watches):
            try:
                arrivals = await self.api.arrivals(w.stop["id"], route_id=w.route.get("id"))
            except TTCError:
                continue
            soon = [m for m in (_mins(a) for a in arrivals) if m is not None and m <= w.minutes]
            if not soon:
                continue
            self.watches.remove(w)
            msg = (f"🔔 **{w.route.get('shortName')}** მოდის **{min(soon)} წთ**-ში → "
                   f"**{_stop_title(w.stop)}**! 🏃")
            try:
                user = self.bot.get_user(w.user_id) or await self.bot.fetch_user(w.user_id)
                await user.send(msg)
            except discord.HTTPException:
                ch = self.bot.get_channel(w.channel_id) if w.channel_id else None
                if ch:
                    try:
                        await ch.send(f"<@{w.user_id}> {msg}")
                    except discord.HTTPException:
                        pass

    @watch_loop.before_loop
    async def _before_watch(self):
        await self.bot.wait_until_ready()


# ===================================================================== views
class StopView(discord.ui.View):
    def __init__(self, cog: Transit, stop: dict, route_id: str | None, route_name: str | None, owner: int):
        super().__init__(timeout=600)
        self.cog, self.stop, self.route_id, self.route_name = cog, stop, route_id, route_name
        self.message: discord.Message | None = None

    @discord.ui.button(label="განახლება", emoji="🔄", style=discord.ButtonStyle.primary)
    async def refresh(self, interaction: discord.Interaction, _):
        try:
            arrivals = await self.cog.api.arrivals(self.stop["id"], route_id=self.route_id)
        except TTCError:
            return await interaction.response.send_message(ERR, ephemeral=True)
        await interaction.response.edit_message(embed=self.cog._arrivals_embed(self.stop, arrivals, self.route_name),
                                                view=self)

    @discord.ui.button(label="რუკა", emoji="🗺️", style=discord.ButtonStyle.secondary)
    async def map(self, interaction: discord.Interaction, _):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            f = await self.cog._stop_map(self.stop)
        except TTCError:
            f = None
        if not f:
            return await interaction.followup.send("რუკა მიუწვდომელია.", ephemeral=True)
        await interaction.followup.send(file=f, ephemeral=True)

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class RouteView(discord.ui.View):
    def __init__(self, cog: Transit, route: dict, suffix: str, stops: list[dict]):
        super().__init__(timeout=600)
        self.cog, self.route, self.suffix, self.stops = cog, route, suffix, stops
        self.message: discord.Message | None = None
        patterns = route.get("patterns") or []
        if len(patterns) <= 1:
            self.remove_item(self.swap)

    async def _redraw(self, interaction: discord.Interaction, suffix: str):
        await interaction.response.defer()
        try:
            self.route, self.suffix, self.stops, embed, file = await self.cog._route_view_payload(self.route["id"], suffix)
        except TTCError:
            return await interaction.followup.send(ERR, ephemeral=True)
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="მიმართულება", emoji="🔁", style=discord.ButtonStyle.primary)
    async def swap(self, interaction: discord.Interaction, _):
        patterns = self.route.get("patterns") or []
        cur = next((p for p in patterns if p.get("patternSuffix") == self.suffix), {})
        other = next((p for p in patterns if p.get("directionId") != cur.get("directionId")), None) \
            or next((p for p in patterns if p.get("patternSuffix") != self.suffix), None)
        if other:
            await self._redraw(interaction, other["patternSuffix"])

    @discord.ui.button(label="განახლება", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, _):
        await self._redraw(interaction, self.suffix)

    @discord.ui.button(label="გაჩერებები", emoji="📋", style=discord.ButtonStyle.secondary)
    async def stop_list(self, interaction: discord.Interaction, _):
        rows = [f"`{i + 1:>2}.` `{s.get('code') or '—':>5}` {s.get('name', '')}" for i, s in enumerate(self.stops)]
        await Paginator.send(interaction, f"📋 {self.route.get('shortName')} — გაჩერებები", rows,
                             per_page=20, ephemeral=True)

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class Paginator(discord.ui.View):
    def __init__(self, title: str, rows: list[str], per_page: int, footer: str | None):
        super().__init__(timeout=300)
        self.title, self.footer = title, footer
        self.pages = [rows[i:i + per_page] for i in range(0, len(rows), per_page)] or [["—"]]
        self.page = 0
        self.message: discord.Message | None = None
        self._sync()

    def embed(self) -> discord.Embed:
        e = discord.Embed(title=self.title, description="\n".join(self.pages[self.page]), color=0x1F6FEB)
        e.set_footer(text=f"გვერდი {self.page + 1}/{len(self.pages)}" + (f" · {self.footer}" if self.footer else ""))
        return e

    def _sync(self):
        self.prev.disabled = self.page == 0
        self.next.disabled = self.page >= len(self.pages) - 1

    @classmethod
    async def send(cls, interaction: discord.Interaction, title: str, rows: list[str], per_page: int = 20,
                   footer: str | None = None, ephemeral: bool = False):
        view = cls(title, rows, per_page, footer)
        if len(view.pages) == 1:
            view = None
        emb = (view or cls(title, rows, per_page, footer)).embed()
        kwargs = {"embed": emb, "ephemeral": ephemeral}
        if view:
            kwargs["view"] = view
        if interaction.response.is_done():
            msg = await interaction.followup.send(**kwargs, wait=True)
        else:
            await interaction.response.send_message(**kwargs)
            msg = await interaction.original_response()
        if view:
            view.message = msg

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary)
    async def prev(self, interaction: discord.Interaction, _):
        self.page -= 1
        self._sync()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, _):
        self.page += 1
        self._sync()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Transit(bot))
