import sys,re,urllib.parse,urllib.request,gzip,time
UA="Mozilla/5.0 (X11; Linux x86_64) Chrome/120"
def g(u):
    r=urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Encoding":"gzip"})
    with urllib.request.urlopen(r,timeout=40) as x:
        b=x.read()
        if x.headers.get("Content-Encoding")=="gzip": b=gzip.decompress(b)
        return b.decode("utf-8","replace")
st=sys.argv[1]  # all | abstract | title
for q in sys.argv[2:]:
    u=("https://arxiv.org/search/?searchtype="+st+"&query="+urllib.parse.quote(q)
       +"&size=25&start=0")
    try: body=g(u)
    except Exception as e: print(f"\n##### arXiv[{st}] [{q}] ERR {e}"); continue
    m=re.search(r'of ([\d,]+) results',body); tot=m.group(1) if m else "?"
    blocks=re.findall(r'<li class="arxiv-result">(.*?)</li>',body,re.S)
    print(f"\n##### arXiv[{st}] q=[{q}] total={tot}")
    for b in blocks:
        idm=re.search(r'arxiv.org/abs/([0-9]{4}\.[0-9]{4,5})',b)
        tim=re.search(r'<p class="title is-5 mathjax">\s*(.*?)\s*</p>',b,re.S)
        ti=re.sub(r"\s+"," ",re.sub(r"<[^>]+>","",tim.group(1))).strip() if tim else "?"
        ab=re.search(r'<span class="abstract-full[^"]*">(.*?)</span>',b,re.S)
        abt=re.sub(r"\s+"," ",re.sub(r"<[^>]+>","",ab.group(1))).strip()[:260] if ab else ""
        print(f"  [{idm.group(1) if idm else '??'}] {ti[:130]}")
        if abt: print(f"      {abt}")
    time.sleep(1.5)
