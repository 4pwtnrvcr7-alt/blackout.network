"""World power grid (pt1815u, Nov 24 2026), step 1: pull OSM power lines/cables/substations >=220 kV and hydro plants/dams from the
Overture Maps base/infrastructure GeoParquet (release 2026-11-18.0, anonymous S3, no account) into raw.jsonl. Data (c) OpenStreetMap contributors, ODbL.
Step 2: tools/world_grid_build.py -> grid.geojsonseq; step 3: tippecanoe -q -z8 -Z0 -l grid --no-tile-compression -e tiles --simplification=4
--no-tile-stats --drop-smallest-as-needed -M 400000 -P grid.geojsonseq; step 4: tools/world_grid_zip.py, then split base64 into app/netmap_static/gridtiles.b64.N (2.6 MB parts)."""
import pyarrow.fs as pf, pyarrow.parquet as pq, pyarrow.compute as pc, re, json, sys, time, concurrent.futures as cf, collections
fs = pf.S3FileSystem(anonymous=True, region="us-west-2")
sel = fs.get_file_info(pf.FileSelector("overturemaps-us-west-2/release/2026-11-18.0/theme=base/type=infrastructure"))
files = sorted(x.path for x in sel if x.path.endswith(".parquet"))
WANT = {"power_line", "cable", "substation", "plant", "generator", "dam"}
classes = collections.Counter()
def kv(v):
    m = 0
    for x in re.split(r"[;,]", v or ""):
        try: m = max(m, int(float(x.strip())) // 1000)
        except ValueError: pass
    return m
def job(fi, rg):
    p = pq.ParquetFile(files[fi], filesystem=fs)
    t = p.read_row_group(rg, columns=["subtype", "class"])
    cl = t.column("class").to_pylist(); st = t.column("subtype").to_pylist()
    cc = collections.Counter(c for c, s in zip(cl, st) if s == "power")
    idx = [i for i, c in enumerate(cl) if c in WANT]
    out = []
    if idx:
        t2 = p.read_row_group(rg, columns=["source_tags", "geometry", "class"]).take(idx)
        for tags, g, c in zip(t2.column("source_tags").to_pylist(), t2.column("geometry").to_pylist(), t2.column("class").to_pylist()):
            d = dict(tags or [])
            if c in ("power_line", "cable", "substation") and kv(d.get("voltage")) < 220: continue
            if c in ("plant", "generator", "dam") and not (d.get("plant:source") == "hydro" or d.get("generator:source") == "hydro" or c == "dam"): continue
            if c == "generator": continue
            keep = {k: d[k] for k in ("voltage", "name", "ref", "operator", "plant:output:electricity", "plant:source", "waterway", "name:en", "wikidata", "start_date", "line", "location", "frequency", "circuits", "cables") if k in d}
            out.append((c, keep, g.hex()))
    return cc, out
jobs = []
for fi, f in enumerate(files):
    n = pq.ParquetFile(f, filesystem=fs).metadata.num_row_groups
    jobs += [(fi, r) for r in range(n)]
print("row groups", len(jobs), file=sys.stderr)
t = time.time(); done = 0
with open("raw.jsonl", "w") as o, cf.ThreadPoolExecutor(24) as ex:
    for cc, out in ex.map(lambda a: job(*a), jobs):
        classes.update(cc); done += 1
        for r in out: o.write(json.dumps(r) + "\n")
        if done % 200 == 0: print(done, round(time.time() - t), file=sys.stderr, flush=True)
print(classes.most_common(), file=sys.stderr)
