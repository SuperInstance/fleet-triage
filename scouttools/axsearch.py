#!/usr/bin/env python3
"""arXiv API search + a strict 26xx-range existence checker.
Usage:
  axsearch.py search "abs terms" [max]
  axsearch.py id 2605.08442 2607.22000 ...
  axsearch.py idpage 2605.08442      # fetch the real abs page, report HTTP
"""
import sys, re, urllib.parse, urllib.request, time, gzip, io

UA = "Mozilla/5.0 (compatible; fleet-scout/1.0)"
def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return r.status, raw.decode("utf-8", "replace")

def search(q, mx=12):
    url = ("http://export.arxiv.org/api/query?search_query=" + urllib.parse.quote(q)
           + f"&start=0&max_results={mx}&sortBy=relevance")
    st, body = get(url)
    ents = re.findall(r"<entry>(.*?)</entry>", body, re.S)
    print(f"### arXiv query [{q}]  -> {len(ents)} hits")
    for e in ents:
        idm = re.search(r"<id>http://arxiv.org/abs/([^<]+)</id>", e)
        ti = re.sub(r"\s+", " ", re.search(r"<title>(.*?)</title>", e, re.S).group(1)).strip()
        pub = re.search(r"<published>(\d{4}-\d{2})", e).group(1)
        print(f"- [{idm.group(1)}] ({pub}) {ti[:170]}")
    return len(ents)

def byid(ids):
    url = ("http://export.arxiv.org/api/query?id_list=" + ",".join(ids)
           + "&max_results=100")
    st, body = get(url)
    ents = re.findall(r"<entry>(.*?)</entry>", body, re.S)
    found = {}
    for e in ents:
        i = re.search(r"<id>http://arxiv.org/abs/([^<]+)</id>", e).group(1)
        ti = re.sub(r"\s+", " ", re.search(r"<title>(.*?)</title>", e, re.S).group(1)).strip()
        found[i] = ti
    print(f"### arXiv id_list lookup of {len(ids)} ids -> {len(found)} returned")
    for i in ids:
        print(f"  {i}: {found.get(i, '*** NO ENTRY RETURNED ***')}")

def idpage(i):
    try:
        st, body = get("https://arxiv.org/abs/" + i)
        t = re.search(r'<meta name="citation_title" content="([^"]*)"', body)
        print(f"{i}: HTTP {st} | title={t.group(1) if t else '??'}")
    except Exception as ex:
        code = getattr(ex, "code", None)
        print(f"{i}: EXCEPTION {type(ex).__name__} code={code} {ex}")

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "search":
        search(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12)
    elif cmd == "id":
        byid(sys.argv[2:])
    elif cmd == "idpage":
        for i in sys.argv[2:]:
            idpage(i); time.sleep(1.5)
