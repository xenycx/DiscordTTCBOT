"""Static map rendering for Discord embeds.

Draws route lines, stops and live vehicles on top of raster map tiles
(OpenStreetMap by default). No API key is needed; tiles are cached on disk and
the required attribution is drawn on every image.
"""

from __future__ import annotations

import asyncio
import io
import logging
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("ttc.map")

# Default: OpenStreetMap standard tiles (free, attribution required, cache + UA
# required by https://operations.osmfoundation.org/policies/tiles/).
# Override with TILE_URL / TILE_SIZE / TILE_ATTRIBUTION, e.g. a MapTiler or
# Mapbox raster URL with your own key for heavier use.
TILE_URL = os.getenv("TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
TILE_SIZE = int(os.getenv("TILE_SIZE", "256"))
ATTRIBUTION = os.getenv("TILE_ATTRIBUTION", "© OpenStreetMap contributors")
CACHE_DIR = Path(os.getenv("TILE_CACHE_DIR", "cache/tiles"))
USER_AGENT = "DiscordTTCBot/2.0 (+https://github.com/xenycx/DiscordTTCBOT)"
SS = 2  # supersampling factor for smooth overlays

_FONT_DIR = Path(__file__).resolve().parent / "fonts"  # bundled Noto (SIL OFL 1.1)
_FONT_CANDIDATES = {
    "georgian": [
        str(_FONT_DIR / "NotoSansGeorgian-Bold.ttf"),
        "/usr/share/fonts/noto/NotoSansGeorgian-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansGeorgian-Bold.ttf",
    ],
    "latin": [
        str(_FONT_DIR / "NotoSans-Bold.ttf"),
        "/usr/share/fonts/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
}
_font_cache: dict[tuple[str, int], ImageFont.ImageFont] = {}
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200d]")


def _is_geo(ch: str) -> bool:
    return "\u10a0" <= ch <= "\u10ff" or "\u1c90" <= ch <= "\u1cbf" or "\u2d00" <= ch <= "\u2d2f"


def _font(kind: str, size: int) -> ImageFont.ImageFont:
    ck = (kind, size)
    if ck not in _font_cache:
        font = None
        for p in _FONT_CANDIDATES[kind] + _FONT_CANDIDATES["latin"]:
            if os.path.exists(p):
                font = ImageFont.truetype(p, size)
                break
        if font is None:
            log.warning("No %s font found; map labels may show boxes. Expected %s", kind, _FONT_DIR)
            font = ImageFont.load_default(size)
        _font_cache[ck] = font
    return _font_cache[ck]


def _runs(text: str, size: int) -> list[tuple[str, ImageFont.ImageFont]]:
    """Split text into runs so Georgian and Latin/symbols use fonts that have the glyphs."""
    text = _EMOJI.sub("", text).strip()
    runs: list[tuple[str, ImageFont.ImageFont]] = []
    for ch in text:
        kind = "georgian" if _is_geo(ch) else ("latin" if not ch.isspace() or not runs else None)
        if kind is None:  # spaces join the current run
            runs[-1] = (runs[-1][0] + ch, runs[-1][1])
            continue
        f = _font(kind, size)
        if runs and runs[-1][1] is f:
            runs[-1] = (runs[-1][0] + ch, f)
        else:
            runs.append((ch, f))
    return runs


def text_width(d: ImageDraw.ImageDraw, text: str, size: int) -> float:
    return sum(d.textlength(t, font=f) for t, f in _runs(text, size))


def draw_text(d: ImageDraw.ImageDraw, x: float, y: float, text: str, size: int, fill, align: str = "l") -> tuple:
    """Draw text vertically centred on y. align: l (x = left edge) or m (x = centre). Returns bbox."""
    w = text_width(d, text, size)
    cx = x - w / 2 if align == "m" else x
    for t, f in _runs(text, size):
        d.text((cx, y), t, font=f, fill=fill, anchor="lm")
        cx += d.textlength(t, font=f)
    left = x - w / 2 if align == "m" else x
    return left, y - size * 0.62, left + w, y + size * 0.62


def _fit_tile(img: Image.Image) -> Image.Image:
    return img if img.size == (TILE_SIZE, TILE_SIZE) else img.resize((TILE_SIZE, TILE_SIZE), Image.LANCZOS)


# ------------------------------------------------------------------ projection
def _world(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = TILE_SIZE * (2 ** z)
    x = (lon + 180.0) / 360.0 * n
    lat = max(min(lat, 85.0511), -85.0511)
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def _hex(c: str, alpha: int = 255) -> tuple[int, int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), alpha


def _contrast(c: str) -> tuple[int, int, int, int]:
    r, g, b, _ = _hex(c)
    return (20, 20, 20, 255) if (0.299 * r + 0.587 * g + 0.114 * b) > 160 else (255, 255, 255, 255)


# ---------------------------------------------------------------- scene model
@dataclass
class Line:
    points: list[tuple[float, float]]
    color: str = "#1f6feb"
    width: float = 6
    faded: bool = False


@dataclass
class Stop:
    lat: float
    lon: float
    color: str = "#1f6feb"
    label: str | None = None
    highlight: bool = False


@dataclass
class Vehicle:
    lat: float
    lon: float
    heading: float | None = None
    color: str = "#1f6feb"
    label: str | None = None


@dataclass
class Pin:
    lat: float
    lon: float
    color: str = "#e5534b"
    label: str | None = None


@dataclass
class MapScene:
    title: str | None = None
    subtitle: str | None = None
    lines: list[Line] = field(default_factory=list)
    stops: list[Stop] = field(default_factory=list)
    vehicles: list[Vehicle] = field(default_factory=list)
    pins: list[Pin] = field(default_factory=list)
    width: int = 1200
    height: int = 800
    max_zoom: int = 17

    def all_points(self) -> list[tuple[float, float]]:
        pts = [p for ln in self.lines for p in ln.points]
        pts += [(s.lat, s.lon) for s in self.stops]
        pts += [(v.lat, v.lon) for v in self.vehicles]
        pts += [(p.lat, p.lon) for p in self.pins]
        return pts


# ------------------------------------------------------------------- renderer
class MapRenderer:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._sem = asyncio.Semaphore(8)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _tile(self, z: int, x: int, y: int) -> Image.Image:
        n = 2 ** z
        x %= n
        if y < 0 or y >= n:
            return Image.new("RGB", (TILE_SIZE, TILE_SIZE), (232, 232, 232))
        path = CACHE_DIR / str(z) / str(x) / f"{y}.png"
        if path.exists():
            try:
                return _fit_tile(Image.open(path).convert("RGB"))
            except OSError:
                path.unlink(missing_ok=True)
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15),
                                                  headers={"User-Agent": USER_AGENT})
        url = TILE_URL.format(s="abc"[(x + y) % 3], z=z, x=x, y=y)
        async with self._sem:
            try:
                async with self._session.get(url) as r:
                    if r.status != 200:
                        raise aiohttp.ClientError(f"HTTP {r.status}")
                    data = await r.read()
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                log.warning("tile %s/%s/%s failed: %s", z, x, y, e)
                return Image.new("RGB", (TILE_SIZE, TILE_SIZE), (232, 232, 232))
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
        except OSError:
            return Image.new("RGB", (TILE_SIZE, TILE_SIZE), (232, 232, 232))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return _fit_tile(img)

    def _fit_zoom(self, pts, w, h, pad, max_zoom) -> int:
        if len(pts) < 2:
            return min(16, max_zoom)
        for z in range(max_zoom, 9, -1):
            xs, ys = zip(*(_world(la, lo, z) for la, lo in pts))
            if max(xs) - min(xs) <= w - 2 * pad and max(ys) - min(ys) <= h - 2 * pad:
                return z
        return 10

    async def render(self, scene: MapScene) -> io.BytesIO:
        W, H = scene.width, scene.height
        pts = scene.all_points()
        if not pts:
            pts = [(41.7151, 44.8271)]  # Tbilisi centre
        top_pad = 110 if scene.title else 50
        z = self._fit_zoom(pts, W, H - top_pad + 50, 70, scene.max_zoom)
        xs, ys = zip(*(_world(la, lo, z) for la, lo in pts))
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2 - (top_pad - 50) / 2
        x0, y0 = cx - W / 2, cy - H / 2

        # --- base map
        base = Image.new("RGB", (W, H), (232, 232, 232))
        tx0, ty0 = int(x0 // TILE_SIZE), int(y0 // TILE_SIZE)
        tx1, ty1 = int((x0 + W) // TILE_SIZE), int((y0 + H) // TILE_SIZE)
        coords = [(tx, ty) for tx in range(tx0, tx1 + 1) for ty in range(ty0, ty1 + 1)]
        tiles = await asyncio.gather(*(self._tile(z, tx, ty) for tx, ty in coords))
        for (tx, ty), img in zip(coords, tiles):
            base.paste(img, (int(tx * TILE_SIZE - x0), int(ty * TILE_SIZE - y0)))
        # soften the basemap so overlays pop
        base = Image.blend(base, Image.new("RGB", (W, H), (255, 255, 255)), 0.18)

        # --- overlay (supersampled)
        ov = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        def px(lat, lon):
            x, y = _world(lat, lon, z)
            return (x - x0) * SS, (y - y0) * SS

        for ln in sorted(scene.lines, key=lambda l: not l.faded):
            if len(ln.points) < 2:
                continue
            xy = [px(la, lo) for la, lo in ln.points]
            w = int(ln.width * SS)
            if ln.faded:
                d.line(xy, fill=_hex(ln.color, 110), width=max(2, w // 2), joint="curve")
            else:
                d.line(xy, fill=(255, 255, 255, 235), width=w + 4 * SS, joint="curve")
                d.line(xy, fill=_hex(ln.color), width=w, joint="curve")

        for st in scene.stops:
            x, y = px(st.lat, st.lon)
            r = (9 if st.highlight else 5) * SS
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 255),
                      outline=_hex(st.color), width=(4 if st.highlight else 2) * SS)
            if st.highlight:
                r2 = 4 * SS
                d.ellipse((x - r2, y - r2, x + r2, y + r2), fill=_hex(st.color))

        for v in scene.vehicles:
            x, y = px(v.lat, v.lon)
            r = 13 * SS
            if v.heading is not None:
                a = math.radians(v.heading)
                tip = (x + math.sin(a) * r * 2.2, y - math.cos(a) * r * 2.2)
                left = (x + math.sin(a - 0.55) * r * 1.05, y - math.cos(a - 0.55) * r * 1.05)
                right = (x + math.sin(a + 0.55) * r * 1.05, y - math.cos(a + 0.55) * r * 1.05)
                d.polygon([tip, left, right], fill=(33, 38, 45, 255), outline=(255, 255, 255, 255), width=2 * SS)
            d.ellipse((x - r - 2 * SS, y - r - 2 * SS, x + r + 2 * SS, y + r + 2 * SS), fill=(255, 255, 255, 255))
            d.ellipse((x - r, y - r, x + r, y + r), fill=_hex(v.color))
            if v.label:
                draw_text(d, x, y, v.label, (11 if len(v.label) > 2 else 13) * SS, _contrast(v.color), "m")

        for p in scene.pins:
            x, y = px(p.lat, p.lon)
            r = 11 * SS
            d.polygon([(x, y), (x - r * 0.8, y - r * 1.6), (x + r * 0.8, y - r * 1.6)], fill=_hex(p.color))
            d.ellipse((x - r, y - r * 2.6, x + r, y - r * 0.6), fill=_hex(p.color), outline=(255, 255, 255, 255), width=2 * SS)

        ov = ov.resize((W, H), Image.LANCZOS)
        img = base.convert("RGBA")
        img.alpha_composite(ov)
        d = ImageDraw.Draw(img)

        # --- labels (drawn at 1x on top for crisp text)
        def label(x, y, text, color="#222222"):
            w = text_width(d, text, 15)
            d.rounded_rectangle((x - 5, y - 12, x + w + 5, y + 12), radius=5, fill=(255, 255, 255, 230))
            draw_text(d, x, y, text, 15, color)

        def to_px(lat, lon):
            x, y = _world(lat, lon, z)
            return x - x0, y - y0

        for st in scene.stops:
            if st.label:
                x, y = to_px(st.lat, st.lon)
                label(x + 13, y, st.label, st.color)
        for p in scene.pins:
            if p.label:
                x, y = to_px(p.lat, p.lon)
                label(x + 14, y - 22, p.label, p.color)

        # --- title card
        if scene.title:
            tw = text_width(d, scene.title, 26)
            sw = text_width(d, scene.subtitle, 16) if scene.subtitle else 0
            bw = int(max(tw, sw)) + 32
            bh = 72 if scene.subtitle else 48
            d.rounded_rectangle((16, 16, 16 + bw, 16 + bh), radius=10, fill=(255, 255, 255, 238),
                                outline=(0, 0, 0, 40))
            draw_text(d, 32, 39, scene.title, 26, (25, 25, 25))
            if scene.subtitle:
                draw_text(d, 32, 68, scene.subtitle, 16, (90, 90, 90))

        # --- attribution
        aw = text_width(d, ATTRIBUTION, 12)
        d.rectangle((W - aw - 12, H - 20, W, H), fill=(255, 255, 255, 200))
        draw_text(d, W - aw - 6, H - 10, ATTRIBUTION, 12, (70, 70, 70))

        out = io.BytesIO()
        img.convert("RGB").save(out, "PNG", optimize=True)
        out.seek(0)
        return out
