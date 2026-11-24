"""Read-only vector tiles for the U.S. power grid (OSM, ODbL).
Archive is base64 text for the repository's text-file release path. Decode once per
process; the zip holds simplified PBF tiles, no database, credentials or runtime writes.
"""
import base64
import functools
import io
import os
import zipfile

@functools.lru_cache(maxsize=1)
def archive(static):
    with open(os.path.join(static, "gridtiles.b64"), "rb") as f:
        return zipfile.ZipFile(io.BytesIO(base64.b64decode(f.read())))

def tile(static, z, x, y):
    if not (0 <= z <= 9 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        return 404, {"error": "tile not found"}
    try:
        data = archive(static).read(f"{z}/{x}/{y}.pbf")
    except KeyError:
        data = b""  # valid empty vector tile, outside the mapped footprint
    return 200, data, "application/vnd.mapbox-vector-tile"
