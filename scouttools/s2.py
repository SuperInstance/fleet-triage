import sys, json, urllib.request, urllib.parse, gzip, time
UA="Mozilla/5.0 Chrome/120"
def g(u,tries=5):
    for i in range(tries):
        try:
            r=urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Encoding":"gzip"})
            with urllib.request.urlopen(r,timeout=40) as x:
                b=x.read()
                if x.headers.get("Content-Encoding")=="gzip": b=gzip.decompress(b)
                return b.decode("utf-8","replace")
        except Exception as e:
            if i==tries-1: return json.dumps({"__err":str(e)})
            time.sleep(3*(i+1))
for q in sys.argv[1:]:
    u=("https://api.semanticscholar.org/graph/v1/paper/search?query="+urllib.parse.quote(q)
       +"&limit=8&fields=title,year,authors,externalIds,citationCount,venue,abstract")
    d=json.loads(g(u))
    if "__err" in d: print(f"\n##### S2 [{q}] ERROR {d['__err']}"); continue
    print(f"\n##### S2 [{q}]  total={d.get('total')}")
    for p in d.get("data",[]):
        au=(p.get("authors") or [{}])[0].get("name","?")
        ex=p.get("externalIds") or {}
        print(f"  {p.get('year')} | {p.get('title')}")
        print(f"     {au} | cb={p.get('citationCount')} | {p.get('venue','')[:50]} | arXiv:{ex.get('ArXiv','-')} doi:{ex.get('DOI','-')}")
        if p.get("abstract"): print("     ABS: "+p["abstract"][:400].replace("\n"," "))
    time.sleep(2)
