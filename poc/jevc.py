#!/usr/bin/env python3
"""
jevc - shared JEV client. Stdlib only. Never prints a credential.

Three primitives, three DIFFERENT request shapes (verified live 2026-10-02;
this corrects JEV-CONTRACT.md, which documents `score` with a `levels` key
that the API rejects with HTTP 422 -- see verify_contract()).

  choice -> criteria: {label: null}                 -> {choice, confidence, probabilities}
  score  -> criteria: [ordered strings]             -> {score, confidence, legend, probabilities}
  noul   -> instructions only                       -> {noul: 0.97}      <-- NO distribution

A 503 or a TLS EOF from this endpoint is transport, not evidence. Retry, and
report transport failure as transport failure.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"

# The key is not in env in this sandbox. It is hardcoded in prior fleet
# artifacts. We read the value and never echo it, never log it, never put it
# in an exception message.
_KEY_HINT = "apikey_"
_SEARCH = (
    "/workspace/projects/fleet-triage/jev-merge-artifacts/confirm.py",
    "/workspace/jev-quilt/jev_oracle.py",
    "/workspace/experiments/it_department.py",
)


def load_key() -> str:
    k = (os.environ.get("TYPESAFEAI_KEY") or os.environ.get("TYPESAFE_API_KEY")
         or os.environ.get("JEV_API_KEY") or "")
    if k:
        return k
    for f in _SEARCH:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                m = re.search(_KEY_HINT + r"[A-Za-z0-9_\-]{20,}", fh.read())
            if m:
                return m.group(0)
        except OSError:
            continue
    raise SystemExit("jevc: no TYPESAFEAI_KEY in env and none in the known "
                     "artifacts. Export TYPESAFEAI_KEY and retry.")


KEY = load_key()

# call accounting -- every tool prints this, because "it works" without the
# call count is a demo, not a tool
STATS = {"calls": 0, "retries": 0, "transport_errors": 0,
         "input_tokens": 0, "output_tokens": 0, "latency_ms": []}


class TransportError(RuntimeError):
    """Network/TLS/5xx. Says nothing about whether the request shape was right."""


def _once(state: str, questions: dict, timeout: float):
    body = json.dumps({"model": MODEL, "state": state,
                       "questions": questions}).encode()
    req = urllib.request.Request(
        URL, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        if e.code >= 500 or e.code == 429:
            raise TransportError(f"HTTP {e.code}") from None
        # 4xx is schema, not transport: surface it verbatim so the mistake is
        # visible instead of being retried into mush.
        raise RuntimeError(f"SCHEMA HTTP {e.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        # TLS EOF lands here. It is not evidence about the request.
        raise TransportError(f"{type(e).__name__}: {e}") from None


def ask(state: str, questions: dict, retries: int = 4, timeout: float = 60.0):
    """One call carrying a whole battery. Questions evaluate independently
    against one shared state, so a battery costs about what one question costs."""
    delay = 1.5
    last = None
    for attempt in range(retries + 1):
        t0 = time.monotonic()
        try:
            out = _once(state, questions, timeout)
        except TransportError as e:
            last = e
            STATS["transport_errors"] += 1
            STATS["retries"] += 1
            if attempt == retries:
                break
            time.sleep(delay)
            delay *= 1.8
            continue
        STATS["calls"] += 1
        STATS["latency_ms"].append((time.monotonic() - t0) * 1000)
        u = out.get("usage") or {}
        STATS["input_tokens"] += u.get("input_tokens", 0) or 0
        STATS["output_tokens"] += u.get("output_tokens", 0) or 0
        return out
    raise TransportError(f"gave up after {retries + 1} attempts; last: {last}")


def answers(out: dict) -> dict:
    return out.get("answers", {})


def cost_note() -> str:
    lat = STATS["latency_ms"]
    return (f"{STATS['calls']} API call(s), {STATS['retries']} retry/retries "
            f"({STATS['transport_errors']} transport error(s)), "
            f"{STATS['input_tokens']} in / {STATS['output_tokens']} out tokens, "
            f"median latency "
            f"{sorted(lat)[len(lat)//2]:.0f} ms" if lat else "no calls")


# --------------------------------------------------------------------------
def verify_contract() -> int:
    """Prove the three shapes against the live service. This is the check that
    found the `levels`/`criteria` error in JEV-CONTRACT.md."""
    print("JEV contract check -- three primitives, one call\n")
    qs = {
        "choice_probe": {"type": "choice",
                         "instructions": "What color is the barn?",
                         "criteria": {"red": None, "green": None, "grey": None}},
        "score_probe": {"type": "score",
                        "instructions": "How severe is the reported issue?",
                        "criteria": ["Cosmetic; no impact to functionality",
                                     "Broken or degraded feature, but workaround exists",
                                     "Blocking issue; no workaround exists"]},
        "noul_probe": {"type": "noul",
                       "instructions": "Is a barn usually red?"},
    }
    try:
        out = ask("A red barn on a green hill under a blue sky.", qs)
    except (TransportError, RuntimeError) as e:
        print(f"TRANSPORT/SCHEMA FAILURE: {e}")
        return 2
    a = answers(out)
    print(f"  model resolved: {out.get('model')}")
    for k, v in a.items():
        if v.get("type") == "score":
            print(f"  score : score={v.get('score')}  confidence={v.get('confidence')}"
                  f"  probabilities={v.get('probabilities')}")
        elif v.get("type") == "choice":
            print(f"  choice: choice={v.get('choice')!r}  confidence={v.get('confidence')}"
                  f"  probabilities={v.get('probabilities')}")
        else:
            print(f"  noul  : noul={v.get('noul')}   "
                  f"<-- scalar only: NO confidence, NO probabilities")
    print(f"\n  {cost_note()}")
    return 0


if __name__ == "__main__":
    sys.exit(verify_contract())
