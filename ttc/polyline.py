"""Google encoded-polyline decoder (precision 1e-5).

Matches the decoder shipped in the official TTC web/mobile clients, which is
used for the ``encodedValue`` field returned by ``/v3/routes/{id}/polylines``.
"""

from __future__ import annotations


def decode(encoded: str) -> list[tuple[float, float]]:
    """Return a list of ``(lat, lon)`` tuples."""
    points: list[tuple[float, float]] = []
    index = lat = lon = 0
    length = len(encoded or "")
    while index < length:
        for coord in range(2):
            shift = result = 0
            while True:
                if index >= length:
                    return points
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if coord == 0:
                lat += delta
            else:
                lon += delta
        points.append((lat * 1e-5, lon * 1e-5))
    return points
