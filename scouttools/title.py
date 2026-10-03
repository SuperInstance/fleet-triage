import sys, json, urllib.request, urllib.parse, gzip
UA="Mozilla/5.0 Chrome/120"
def get(u):
    r=urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Encoding":"gzip"})
    with urllib.request.urlopen(r,timeout=35) as x:
        b=x.read()
        if x.headers.get("Content-Encoding")=="gzip": b=gzip.decompress(b)
        return b.decode("utf-8","replace")
for q in sys.argv[1:]:
    d=json.loads(get("https://api.openalex.org/works?search="+urllib.parse.quote(q)+"&per-page=5&mailto=f@e.org"))
    print(f"\n##### TITLE-QUERY [{q}]  count={d['meta']['count']}")
    for w in d["results"]:
        au=w.get("authorships") or []
        loc=(w.get("primary_location") or {}).get("source") or {}
        print(f"  {w.get('publication_year')} | {w.get('title')}")
        print(f"     {au[0]['author']['display_name'] if au else '?'} | cb={w.get('cited_by_count')} | {loc.get('display_name')} | {w.get('doi')}")
