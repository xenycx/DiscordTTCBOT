"""Async client for the TTC "PIS gateway" API.

Reverse-engineered from the official Tbilisi Transport app (Expo / Hermes bundle,
com.azry.wandio.ttc.android 3.1.3) and the transit.ttc.com.ge web client.

The gateway key is NOT static. The official clients read ``PIS_GATEWAY_KEY`` from
Firebase Remote Config; on a 401 they force a Remote Config refresh and retry.
This client mirrors that behaviour:

    1. ``API_KEY`` env override (if set)
    2. key published in transit.ttc.com.ge's ``__PROFILE`` config
    3. live Firebase Remote Config value (used when 1/2 get a 401)
    4. last known default shipped in the app's ``assets/app.config``

On a 401 the cached key is dropped, resolved again (once, behind a lock so many
concurrent failures cause one refresh), and the request is retried.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import time
from typing import Any, Callable, Iterable

import aiohttp

log = logging.getLogger("ttc.client")

WEB_URL = "https://transit.ttc.com.ge/"
BASE_URL = "https://transit.ttc.com.ge/pis-gateway/api"
USER_AGENT = "DiscordTTCBot/2.0 (+https://github.com/xenycx/DiscordTTCBOT)"

# Defaults observed in the shipped app (assets/app.config) and web __PROFILE.
DEFAULT_KEY = "c0a2f304-551a-4d08-b8df-2c53ecd57f9f"
DEFAULT_FIREBASE = {
    "apiKey": "AIzaSyDld_U2uKN7cR6dqMCq9kvSEzP6FRz9hl0",
    "projectId": "tbilisi-transit-production",
    "appId": "1:231390843413:web:6df202aa2ddbba89a4f41c",
}

KEY_TTL = 6 * 3600  # re-validate the key source every 6 hours
MODES = ("BUS", "SUBWAY", "GONDOLA")


class TTCError(Exception):
    """Raised when the TTC API cannot satisfy a request."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class _TTLCache:
    def __init__(self) -> None:
        self._data: dict[Any, tuple[float, Any]] = {}

    def get(self, key: Any) -> Any:
        hit = self._data.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        self._data.pop(key, None)
        return None

    def set(self, key: Any, value: Any, ttl: float) -> None:
        self._data[key] = (time.monotonic() + ttl, value)
        if len(self._data) > 2000:  # crude bound
            now = time.monotonic()
            self._data = {k: v for k, v in self._data.items() if v[0] > now}


class TTCClient:
    def __init__(self, locale: str = "ka", api_key: str | None = None,
                 on_key_change: Callable[[str | None, str, str], None] | None = None):
        self.locale = locale if locale in ("ka", "en") else "en"
        self._override_key = api_key or None
        self._key: str | None = None
        self._key_source = "none"
        self._key_expires = 0.0
        self._key_lock = asyncio.Lock()
        self._session: aiohttp.ClientSession | None = None
        self._cache = _TTLCache()
        self._firebase = dict(DEFAULT_FIREBASE)
        self._on_key_change = on_key_change
        self._rejected: dict[str, float] = {}  # key -> until (monotonic); keys that got a 401

    # ------------------------------------------------------------------ session
    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"User-Agent": USER_AGENT},
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    @property
    def key_source(self) -> str:
        return self._key_source

    # --------------------------------------------------------------- key logic
    def _set_key(self, key: str, source: str) -> None:
        old = self._key
        self._key, self._key_source = key, source
        self._key_expires = time.monotonic() + KEY_TTL
        if old != key:
            log.info("TTC API key in use from %s (…%s)", source, key[-6:])
            if old and self._on_key_change:
                try:
                    self._on_key_change(old, key, source)
                except Exception:  # pragma: no cover - logging hook only
                    log.exception("on_key_change hook failed")

    async def _key_from_web(self) -> str | None:
        s = await self.session()
        async with s.get(WEB_URL) as r:
            if r.status != 200:
                return None
            html = await r.text()
        m = re.search(r"__PROFILE\s*=\s*(\{.*?\})\s*</script>", html, re.S)
        if m:
            try:
                profile = json.loads(m.group(1))
                creds = profile.get("firebaseCredentials") or {}
                for k in ("apiKey", "projectId", "appId"):
                    if creds.get(k):
                        self._firebase[k] = creds[k]
                key = (profile.get("firebaseRemoteConfigDefaults") or {}).get("PIS_GATEWAY_KEY")
                if key:
                    return key
            except ValueError:
                pass
        m = re.search(r'"PIS_GATEWAY_KEY"\s*:\s*"([0-9a-fA-F-]{20,})"', html)
        return m.group(1) if m else None

    async def _key_from_remote_config(self) -> str | None:
        """Ask Firebase Remote Config for the live value, like the official app."""
        fb = self._firebase
        s = await self.session()
        raw = bytearray(os.urandom(17))
        raw[0] = 0b01110000 | (raw[0] & 0x0F)
        fid = base64.urlsafe_b64encode(bytes(raw)).decode()[:22]
        async with s.post(
            f"https://firebaseinstallations.googleapis.com/v1/projects/{fb['projectId']}/installations",
            headers={"x-goog-api-key": fb["apiKey"]},
            json={"fid": fid, "authVersion": "FIS_v2", "appId": fb["appId"], "sdkVersion": "w:0.6.4"},
        ) as r:
            if r.status != 200:
                log.debug("Firebase installation failed: HTTP %s", r.status)
                return None
            inst = await r.json()
        token = (inst.get("authToken") or {}).get("token")
        async with s.post(
            f"https://firebaseremoteconfig.googleapis.com/v1/projects/{fb['projectId']}"
            f"/namespaces/firebase:fetch?key={fb['apiKey']}",
            json={"sdk_version": "0.4.6", "app_instance_id": inst.get("fid", fid),
                  "app_instance_id_token": token, "app_id": fb["appId"], "language_code": "en-US"},
        ) as r:
            if r.status != 200:
                log.debug("Remote Config fetch failed: HTTP %s", r.status)
                return None
            data = await r.json()
        return (data.get("entries") or {}).get("PIS_GATEWAY_KEY")

    def _is_rejected(self, key: str | None) -> bool:
        until = self._rejected.get(key or "")
        return bool(until and until > time.monotonic())

    async def get_key(self, force: bool = False, bad_key: str | None = None) -> str:
        async with self._key_lock:
            if bad_key:
                self._rejected[bad_key] = time.monotonic() + 3600
            # Another coroutine already refreshed past the key that failed.
            if bad_key and self._key and self._key != bad_key and not self._is_rejected(self._key):
                return self._key
            if self._key and not force and not self._is_rejected(self._key) and time.monotonic() < self._key_expires:
                return self._key

            candidates: list[tuple[str, Any]] = []
            if self._override_key:
                candidates.append(("env API_KEY", lambda: self._override_key))
            web = ("transit.ttc.com.ge", self._key_from_web)
            rc = ("firebase-remote-config", self._key_from_remote_config)
            candidates += [rc, web] if force else [web, rc]

            for source, fn in candidates:
                try:
                    res = fn()
                    key = await res if asyncio.iscoroutine(res) else res
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
                    log.warning("Key source %s failed: %s", source, e)
                    continue
                if key and not self._is_rejected(key):
                    self._set_key(key, source)
                    return key

            if self._key and not self._is_rejected(self._key):
                self._key_expires = time.monotonic() + 300
                return self._key
            if not self._is_rejected(DEFAULT_KEY):
                self._set_key(DEFAULT_KEY, "built-in default")
                return DEFAULT_KEY
            # Everything was rejected recently; retry the newest candidate later.
            self._key_expires = time.monotonic() + 60
            return self._key or DEFAULT_KEY

    # ----------------------------------------------------------------- request
    async def _get(self, path: str, params: dict | None = None, ttl: float = 0) -> Any:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        cache_key = (path, tuple(sorted(params.items())))
        if ttl:
            hit = self._cache.get(cache_key)
            if hit is not None:
                return hit

        s = await self.session()
        key = await self.get_key()
        refreshed = False
        for attempt in range(3):
            try:
                async with s.get(f"{BASE_URL}{path}", params=params,
                                 headers={"X-api-key": key, "Accept": "application/json"}) as r:
                    if r.status == 401 and not refreshed:
                        log.warning("TTC API 401 for %s, refreshing key", path)
                        key = await self.get_key(force=True, bad_key=key)
                        refreshed = True
                        continue
                    if r.status >= 500 and attempt < 2:
                        await asyncio.sleep(0.7 * (attempt + 1))
                        continue
                    if r.status == 404:
                        raise TTCError("not found", 404)
                    if r.status != 200:
                        body = (await r.text())[:200]
                        raise TTCError(f"HTTP {r.status}: {body}", r.status)
                    data = await r.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < 2:
                    await asyncio.sleep(0.7 * (attempt + 1))
                    continue
                raise TTCError(f"network error: {e}") from e
            if ttl:
                self._cache.set(cache_key, data, ttl)
            return data
        raise TTCError("request failed after retries")

    # ------------------------------------------------------------------ stops
    async def stops(self) -> list[dict]:
        return await self._get("/v2/stops", {"locale": self.locale}, ttl=1800) or []

    async def stop(self, stop_id: str) -> dict:
        return await self._get(f"/v2/stops/{stop_id}", {"locale": self.locale}, ttl=600)

    async def stop_routes(self, stop_id: str) -> list[dict]:
        return await self._get(f"/v2/stops/{stop_id}/routes", {"locale": self.locale}, ttl=600) or []

    async def arrivals(self, stop_id: str, route_id: str | None = None, limit: int | None = None) -> list[dict]:
        return await self._get(
            f"/v2/stops/{stop_id}/arrival-times",
            {"locale": self.locale, "routeId": route_id, "maxNumberOfArrivalTimes": limit,
             "ignoreScheduledArrivalTimes": "false"},
            ttl=15,
        ) or []

    async def find_stop(self, query: str) -> dict | None:
        """Resolve a stop by exact id, code, or name."""
        q = query.strip().lower()
        stops = await self.stops()
        for st in stops:
            if str(st.get("id", "")).lower() == q or str(st.get("code") or "").lower() == q:
                return st
        for st in stops:
            if (st.get("name") or "").lower() == q:
                return st
        matches = self.search_stops(stops, query, 1)
        return matches[0] if matches else None

    @staticmethod
    def search_stops(stops: Iterable[dict], query: str, limit: int = 25) -> list[dict]:
        q = query.strip().lower()
        if not q:
            return [s for s in stops if s.get("code")][:limit]
        exact, prefix, contains = [], [], []
        for s in stops:
            code = str(s.get("code") or "").lower()
            name = (s.get("name") or "").lower()
            if code == q:
                exact.append(s)
            elif code.startswith(q) or name.startswith(q):
                prefix.append(s)
            elif q in code or q in name:
                contains.append(s)
        return (exact + prefix + contains)[:limit]

    # ----------------------------------------------------------------- routes
    async def routes(self, modes: Iterable[str] = MODES) -> list[dict]:
        return await self._get("/v3/routes", {"modes": ",".join(modes), "locale": self.locale}, ttl=1800) or []

    async def route(self, route_id: str) -> dict:
        return await self._get(f"/v3/routes/{route_id}", {"locale": self.locale}, ttl=600)

    async def route_stops(self, route_id: str, pattern_suffix: str) -> list[dict]:
        return await self._get(f"/v3/routes/{route_id}/stops",
                               {"patternSuffix": pattern_suffix, "locale": self.locale}, ttl=600) or []

    async def route_polylines(self, route_id: str, suffixes: list[str]) -> dict:
        return await self._get(f"/v3/routes/{route_id}/polylines",
                               {"patternSuffixes": ",".join(suffixes)}, ttl=3600) or {}

    async def route_positions(self, route_id: str, suffixes: list[str]) -> dict:
        return await self._get(f"/v3/routes/{route_id}/positions",
                               {"patternSuffixes": ",".join(suffixes)}, ttl=8) or {}

    async def route_schedule(self, route_id: str, pattern_suffix: str) -> Any:
        return await self._get(f"/v3/routes/{route_id}/schedule",
                               {"patternSuffix": pattern_suffix, "locale": self.locale}, ttl=600)

    async def find_route(self, query: str) -> dict | None:
        q = query.strip().lower()
        routes = await self.routes()
        for r in routes:
            if str(r.get("id", "")).lower() == q or str(r.get("shortName", "")).lower() == q:
                return r
        res = self.search_routes(routes, query, 1)
        return res[0] if res else None

    @staticmethod
    def search_routes(routes: Iterable[dict], query: str, limit: int = 25) -> list[dict]:
        q = query.strip().lower()
        if not q:
            return list(routes)[:limit]
        exact, prefix, contains = [], [], []
        for r in routes:
            short = str(r.get("shortName") or "").lower()
            long_ = (r.get("longName") or "").lower()
            if short == q:
                exact.append(r)
            elif short.startswith(q):
                prefix.append(r)
            elif q in long_ or q in short:
                contains.append(r)
        return (exact + prefix + contains)[:limit]

    # ---------------------------------------------------------------- geocode
    async def geocode(self, query: str) -> list[dict]:
        data = await self._get("/v2/geocode", {"query": query, "locale": self.locale}, ttl=3600)
        return (data or {}).get("features", []) if isinstance(data, dict) else (data or [])


def route_color(obj: dict | None, default: str = "#1f6feb") -> str:
    c = str((obj or {}).get("color") or "").strip().lstrip("#")
    return f"#{c}" if re.fullmatch(r"[0-9a-fA-F]{6}", c) else default


def stop_latlon(stop: dict) -> tuple[float, float] | None:
    s = stop.get("stop", stop)
    lat, lon = s.get("lat"), s.get("lon")
    if lat is None or lon is None:
        return None
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None
