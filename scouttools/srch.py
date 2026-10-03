#!/usr/bin/env python3
"""Dual-source scout: arxiv.org HTML search + OpenAlex. Prints ids+titles, no claims."""
import sys, re, json, urllib.parse, urllib.request, time, gzip

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
def get(url, timeout=35):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return r.status, raw.decode("utf-8", "replace")

def ax(q, size=25):
    url = ("https://arxiv.org/search/?searchtype=all&query="
           + urllib.parse.quote(q) + f"&size={size}&start=0")
    st, body = get(url)
    m = re.search(r'of ([\d,]+) results', body)
    tot = m.group(1) if m else "?"
    # each result block
    blocks = re.findall(r'<li class="arxiv-result">(.*?)</li>', body, re.S)
    print(f"\n===== arXiv  q=[{q}]  total={tot}")
    for b in blocks[:size]:
        idm = re.search(r'arxiv.org/abs/([0-9]{4}\.[0-9]{4,5})', b)
        tim = re.search(r'<p class="title is-5 mathjax">\s*(.*?)\s*</p>', b, re.S)
        ti = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", tim.group(1))).strip() if tim else "?"
        dt = re.search(r'Submitted</span>\s*([^;<]*)', b)
        print(f"  [{idm.group(1) if idm else '??'}] {ti[:150]}"
              + (f"  ({dt.group(1).strip()})" if dt else ""))

def oa(q, n=8, extra=""):
    url = ("https://api.openalex.org/works?search=" + urllib.parse.quote(q)
           + f"&per-page={n}&mailto=fleetscout@example.org" + extra)
    st, body = get(url)
    d = json.loads(body)
    print(f"\n===== OpenAlex q=[{q}] count={d['meta']['count']}")
    for w in d["results"][:n]:
        au = w.get("authorships") or []
        a1 = (au[0]["author"]["display_name"] if au else "?")
        print(f"  {w.get('publication_year')} | {w.get('title','')[:120]}")
        print(f"      {a1} et al. | cited_by={w.get('cited_by_count')} | {w.get('doi') or w.get('id')}")

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "ax": ax(" ".join(sys.argv[2:]))
    elif mode == "oa": oa(" ".join(sys.argv[2:]))
    elif mode == "both":
        q = " ".join(sys.argv[2:]); ax(q); oa(q)
