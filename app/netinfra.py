"""Read-only vector tiles for the world power grid, 220 kV and up (OSM via Overture Maps base/infrastructure, ODbL).
Archive is base64 text for the repository's text-file release path, split into ordered parts gridtiles.b64.0, .1, ...
Decode once per process; the zip holds simplified PBF tiles z0-8, no database, credentials or runtime writes.
"""
import base64
import functools
import io
import os
import re
import zipfile

MAXZ = 8

@functools.lru_cache(maxsize=1)
def archive(static):
    parts = sorted((int(m.group(1)), f) for f in os.listdir(static) for m in [re.fullmatch(r"gridtiles\.b64\.(\d+)", f)] if m)
    raw = b"".join(open(os.path.join(static, f), "rb").read() for _, f in parts)   # split to stay under the push size limit
    return zipfile.ZipFile(io.BytesIO(base64.b64decode(raw)))

def tile(static, z, x, y):
    if not (0 <= z <= 9 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        return 404, {"error": "tile not found"}
    if z > MAXZ:
        return 404, {"error": "tile not found"}   # the client overzooms z8 tiles
    try:
        data = archive(static).read(f"{z}/{x}/{y}.pbf")
    except KeyError:
        data = b""  # valid empty vector tile, outside the mapped footprint
    return 200, data, "application/vnd.mapbox-vector-tile"
