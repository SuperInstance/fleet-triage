#!/usr/bin/env bash
# lattice-cell — the crash matrix.
#
# "What happens if the Worker dies between execute and commit?" is the question
# that separates a demo from a design, and it cannot be answered by reasoning
# about the code. So: for every checkpoint, kill the process HARD (exit 137, no
# finally, no atexit) in a real subprocess, then read the substrate afterwards
# and write down what the lattice can and cannot tell.
#
# Each row is a claim about a design, and each row is measured, not asserted.
set -u
HERE=$(cd "$(dirname "$0")/.." && pwd)
WORK=${WORK:-/tmp/lattice-crash}
rm -rf "$WORK"; mkdir -p "$WORK"

fix() { # fix <dir>  — a bare repo pair with a real remote
  local d=$1; mkdir -p "$d"; git init -q --bare "$d/remote.git"
  git init -q "$d/cell"; cd "$d/cell"; git config user.email c@l; git config user.name cell
  git remote add origin "$d/remote.git"
  mkdir -p cells/alpha/dials; echo "0.4" > cells/alpha/dials/1; echo "0.0" > cells/alpha/dials/15
  git add -A; git commit -qm "seed"; git push -q origin main 2>/dev/null; git branch -M main; cd - >/dev/null
}

row() { # row <crashpoint>
  local cp=$1 d="$WORK/$1"
  fix "$d"
  local ledger="$d/ledger.json"
  LATTICE_CRASH_AT="$cp" node "$HERE/bin/lattice-cell" run --repo "$d/cell" --ledger "$ledger" \
      --cell alpha --intent "raise obstruction to 0.9" --base main \
      --post "dial:alpha:1 == 0.9" --obstruction 0.9 >/dev/null 2>&1
  local exitcode=$?
  local ledger_rows="-" tip="-" receipt="-" post="-" in_log="no"
  [ -f "$ledger" ] && ledger_rows=$(node -e "const L=require('node:fs');const r=Object.values(JSON.parse(L.readFileSync('$ledger'))).map(JSON.parse);const d=r.filter(x=>x.kind==='DISPATCH').length,o=r.filter(x=>x.kind==='OUTCOME');console.log(d+'/settled:'+o.map(x=>x.status).join(',')||'-')" 2>/dev/null || echo "-")
  tip=$(git -C "$d/cell" rev-parse --short HEAD 2>/dev/null)
  remote_tip=$(git -C "$d/remote.git" rev-parse --short main 2>/dev/null)
  did=$(git -C "$d/cell" log --all --format=%B 2>/dev/null | grep -c 'Dispatch-Id:' || true)
  printf '%-9s | %-4s | %-26s | %-7s | %-7s | %s\n' \
     "$cp" "$exitcode" "$ledger_rows" "$tip" "$remote_tip" "dispatch-ids-in-history:$did"
  echo "$cp|$ledger_rows|$tip|$remote_tip|$did" >> "$WORK/matrix.txt"
}

echo ""
echo "lattice-cell CRASH MATRIX — a hard kill (exit 137) at each checkpoint"
echo "======================================================================"
printf '%-9s | %-4s | %-26s | %-7s | %-7s | %s\n' CRASH EXIT LEDGER LOCAL_TIP REMOTE_TIP FRAME
echo "----------|------|----------------------------|---------|-----------|-----"
: > "$WORK/matrix.txt"
for cp in wake dispatch execute commit push outcome; do row "$cp"; done
echo ""
echo "----------------------------------------------------------------------"
echo "legend: LEDGER = dispatches/settled:<statuses>   LOCAL/REMOTE_TIP = short sha"
echo ""
