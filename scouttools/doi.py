import sys, json, urllib.request, urllib.parse, gzip
UA="Mozilla/5.0 (X11; Linux x86_64) Chrome/120"
def get(u):
    r=urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Encoding":"gzip"})
    with urllib.request.urlopen(r,timeout=35) as x:
        b=x.read()
        if x.headers.get("Content-Encoding")=="gzip": b=gzip.decompress(b)
        return b.decode("utf-8","replace")
for d in sys.argv[1:]:
    try:
        w=json.loads(get("https://api.openalex.org/works/doi:"+urllib.parse.quote(d)+"?mailto=f@e.org"))
        au=w.get("authorships") or []
        print(f"OK  {d}\n    {w.get('title')}\n    {w.get('publication_year')} | {au[0]['author']['display_name'] if au else '?'} et al | cited_by={w.get('cited_by_count')} | venue={(w.get('primary_location') or {}).get('source',{}) and ((w.get('primary_location') or {}).get('source') or {}).get('display_name')}")
        ab=w.get("abstract_inverted_index")
        if ab:
            L=[None]*(max(max(v) for v in ab.values())+1)
            for k,vs in ab.items():
                for v in vs: L[v]=k
            print("    ABS: "+" ".join(L)[:700])
    except Exception as e:
        print(f"FAIL {d}: {e}")
