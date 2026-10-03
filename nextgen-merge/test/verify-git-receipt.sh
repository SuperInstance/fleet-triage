#!/usr/bin/env bash
# Re-derive every number in src/git-receipt.js from a fresh clone of the live
# repository, so a judge can check the receipt rather than trust it.
#
#   bash test/verify-git-receipt.sh
#
# Read-only against GitHub. Clones into a temp dir and deletes it.

set -uo pipefail
REPO=https://github.com/SuperInstance/quilt-tools
DIR=$(mktemp -d)
trap 'rm -rf "$DIR"' EXIT

echo "cloning $REPO ..."
git clone -q "$REPO" "$DIR" || { echo "clone failed"; exit 1; }
cd "$DIR" || exit 1
git fetch -q origin pull/32/head:pr32 pull/33/head:pr33 2>/dev/null

counts() {
  node --input-type=module -e "
    const m = await import('$DIR/experiments/referral_graph.seed.mjs');
    const e = m.SEED.edges;
    console.log(\`\${String(e.length).padStart(2)} edges  \${e.filter(x=>x.weight==='VERIFIED').length} VERIFIED  \${e.filter(x=>x.weight==='PENDING').length} PENDING\`);
  " 2>/dev/null || echo "  (seed.mjs not present at this commit)"
}

assert() {
  if [ "$2" = "$3" ]; then echo "  ok   $1: $2"; else echo "  FAIL $1: expected $3, got $2"; FAILED=1; fi
}
FAILED=0

echo
echo "commits and their edge counts:"
for c in 58e2a18 a98a5c5 7caf5a3 fb2e041 0101409; do
  git show "$c:experiments/referral_graph.seed.mjs" > /tmp/_s.mjs 2>/dev/null || continue
  n=$(node --input-type=module -e "
    const m=await import('/tmp/_s.mjs');
    const e=m.SEED.edges;
    console.log(e.length+'/'+e.filter(x=>x.weight==='VERIFIED').length+'/'+e.filter(x=>x.weight==='PENDING').length);
  " 2>/dev/null)
  echo "  $c  $n   (edges/VERIFIED/PENDING)"
done

echo
echo "assertions:"
for c in a98a5c5 7caf5a3 0101409; do
  git show "$c:experiments/referral_graph.pins.mjs" > /tmp/_p.mjs 2>/dev/null
  v=$(grep -o 'seedBooked === [0-9]*' /tmp/_p.mjs | head -1 | grep -o '[0-9]*$')
  echo "  $c pins.mjs asserts edges = $v"
done

# PR32 and PR33 must be true siblings off the shared parent.
p32=$(git rev-list --parents -n1 a98a5c5 | cut -d' ' -f2)
p33=$(git rev-list --parents -n1 7caf5a3 | cut -d' ' -f2)
assert "PR32 and PR33 share a parent" "$p32" "$p33"

# the naive merge
git checkout -q 58e2a18
git merge -q --no-edit a98a5c5 >/dev/null 2>&1
OUT=$(git merge --no-edit 7caf5a3 2>&1)
echo "$OUT" | grep -q CONFLICT && echo "  ok   git merge conflicts" || { echo "  FAIL expected conflicts"; FAILED=1; }
echo "$OUT" | grep -c '^CONFLICT' | xargs -I{} echo "  conflict hunks/files reported: {}"

# seed.mjs must have auto-merged — the silent half
git show :2:experiments/referral_graph.seed.mjs > /tmp/_ours.mjs 2>/dev/null
node --input-type=module -e "
  const m=await import('/tmp/_ours.mjs');
  console.log('  auto-merged seed.mjs edges =', m.SEED.edges.length, '(no conflict marker was asked for)');
" 2>/dev/null

# keep-both must not parse
python3 - <<'PY' > /tmp/_kb.mjs
import re
s=open('experiments/referral_graph.pins.mjs').read()
sys_out=re.sub(r'<<<<<<< HEAD\n(.*?)\n=======\n(.*?)\n>>>>>>> \S+\n', lambda m: m.group(1)+'\n'+m.group(2)+'\n', s, flags=re.S)
print(sys_out)
PY
if node --check /tmp/_kb.mjs >/dev/null 2>&1; then
  echo "  !! keep-both PARSED — the receipt's invalid-syntax claim no longer holds"
  FAILED=1
else
  echo "  ok   keep-both does not parse: $(node --check /tmp/_kb.mjs 2>&1 | grep -o 'SyntaxError.*' | head -1)"
  echo "  ok   brace balance: $(python3 -c "s=open('/tmp/_kb.mjs').read();print(s.count('{'),'open vs',s.count('}'),'close')")"
fi

echo
[ "$FAILED" = "0" ] && echo "receipt verified." || echo "RECEIPT MISMATCH — see FAIL lines above."
exit "$FAILED"
