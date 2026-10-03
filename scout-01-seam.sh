#!/usr/bin/env bash
# SEAM: tensor-midi — the shipped .swmidi writer and the shipped .swmidi reader
# disagree on byte 0. Repo self-certifies 515/515 green while 0/32 of its own
# committed artifact decodes. Run from the repo root.
cd "$(dirname "$0")" 2>/dev/null
R=/workspace/projects/fleet-triage/repos/tensor-midi
echo "=== 1. the repo's test suite (this is the number CI publishes) ==="
(cd $R && node --test tests/*.test.js game-engine/*.test.js 2>&1 | tail -4)
echo
echo "=== 2. decode the repo's own committed artifact with the repo's own decoder ==="
(cd $R && node --input-type=module -e "
import {decodeStream} from './src/swmidi.js';
import fs from 'fs';
const b=new Uint8Array(fs.readFileSync('output/relay-bridge-fix.swmidi'));
try { console.log('decoded', decodeStream(b).length, 'events'); }
catch(e){ console.log('FAILS:', e.message); }" 2>/dev/null)
echo
echo "=== 3. the two writers, side by side, same event ==="
grep -n "buf\[0\] = status" $R/capture.js
grep -n "view.setUint8(0," $R/src/swmidi.js
