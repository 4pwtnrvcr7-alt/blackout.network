#!/bin/bash
# Rebuild app/meshnet_static/lib.js (official Meshtastic JS, GPL-3.0-only) for the browser. Corresponding source for the GPL.
set -euo pipefail
OUT=$(cd "$(dirname "$0")/../.." && pwd)/app/meshnet_static/lib.js
W=$(mktemp -d); cd "$W"
npm init -y >/dev/null
npm install --silent @meshtastic/core@2.6.7 @meshtastic/transport-web-bluetooth@0.1.5 @meshtastic/transport-web-serial@0.2.5 esbuild@0.28.2
mkdir shims
echo 'export const hostname=()=>"browser";export default {hostname};' > shims/os.js
echo 'export const normalize=s=>s;export default {normalize};' > shims/path.js
echo 'export const formatWithOptions=(o,...a)=>a.map(x=>typeof x==="string"?x:(()=>{try{return JSON.stringify(x)}catch(e){return String(x)}})()).join(" ");export const types={isError:e=>e instanceof Error,isNativeError:e=>e instanceof Error};export const inspect=x=>String(x);export default {formatWithOptions,types,inspect};' > shims/util.js
cat > entry.js <<'JS'
import { MeshDevice } from "@meshtastic/core";
import { TransportWebBluetooth } from "@meshtastic/transport-web-bluetooth";
import { TransportWebSerial } from "@meshtastic/transport-web-serial";
window.BNMeshLib = { MeshDevice, TransportWebBluetooth, TransportWebSerial };
JS
npx esbuild entry.js --bundle --minify --format=iife --target=es2020 --legal-comments=eof --alias:os=./shims/os.js --alias:path=./shims/path.js --alias:util=./shims/util.js \
  --banner:js='/*! BLACKOUT.NETWORK build of @meshtastic/core 2.6.7 + transport-web-bluetooth 0.1.5 + transport-web-serial 0.2.5. GPL-3.0-only. Source: https://github.com/meshtastic/js (npm @meshtastic/*) and tools/meshtastic/build_lib.sh. See /api/mesh/LICENSES.txt */' \
  --outfile="$OUT"
echo "built $OUT"
