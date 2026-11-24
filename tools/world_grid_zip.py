import zipfile, os, base64, sys
z = zipfile.ZipFile("tiles.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9)
n = 0
for r, ds, fs in os.walk("tiles"):
    for f in fs:
        if f.endswith(".pbf"):
            p = os.path.join(r, f); z.write(p, os.path.relpath(p, "tiles")); n += 1
z.close()
b = base64.b64encode(open("tiles.zip", "rb").read())
print(n, "tiles", os.path.getsize("tiles.zip"), "zip", len(b), "b64")
