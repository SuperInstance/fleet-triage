#!/usr/bin/env python3
"""
gen.py — MiniMax music-3.0 renderer with manifest, sha256 and `file -b` verification.

RESTORED 2026-10-01 after the sandbox wipe that took /tmp/songs/ with it.
Reconstructed from verified facts, not from guessing. Every constant below is
one the orchestrator confirmed empirically; do not "fix" any of them by
intuition.

VERIFIED FACTS (do not re-derive):
  * Endpoint   POST https://api.minimax.io/v1/music_generation
  * Models     music-3.0, music-2.6      (music-01 / music-02 are DEAD: "invalid model")
  * Free tiers DISCONTINUED 2026-08-20. music-3.0 needs a paid / M-plan account.
  * A 20-second probe times out on a HEALTHY account. Real renders take 61-101s.
    It is not a hang. Generate in the background and poll. DEFAULT_TIMEOUT is
    deliberately generous for the same reason.
  * Instrumental: set is_instrumental=true and OMIT lyrics. With vocals, lyrics is required.
  * output_format "url"; the URL expires in 24h — DOWNLOAD IMMEDIATELY.
  * Instrumentals run long. One in round 2 was killed mid-render and lost.

USAGE
    export MINIMAX_KEY=...
    python3 gen.py --track halyard-and-ledger            # by slug, from TRACKS
    python3 gen.py --track foo --prompt "..." --lyrics-file L.txt
    python3 gen.py --batch                               # all TRACKS, sequentially

RETRY POLICY: no track is retried more than twice. A render that fails is logged
with its status and the lane moves on. Retrying is how lanes die.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ENDPOINT = "https://api.minimax.io/v1/music_generation"
DEFAULT_MODEL = "music-3.0"
DEFAULT_TIMEOUT = 900          # seconds; real renders 61-101s, instrumentals longer
MAX_RETRIES = 2
OUT_ROOT = Path(os.environ.get("SONGS_OUT", "/tmp/songs/renders"))

# ---------------------------------------------------------------- tracks

TRACKS = {
    "halyard-and-ledger": {
        "genre": "sea shanty",
        "prompt": (
            "A weathered sea shanty in 6/8, call-and-response between a lead voice "
            "and a crew of five. Fiddle, tin whistle, hand drums, unison hull "
            "rhythm. Salt-worn, workmanlike, not polished. 100 BPM feel."
        ),
        "lyrics": (
            "[Verse - Lead]\n"
            "One sound is not a chart\n"
            "Two instruments or nothing at all\n"
            "The log is written once\n"
            "The sea is owed a call\n\n"
            "[Response - Crew]\n"
            "Haul it up and call it sound\n"
            "Haul it down and call it less\n"
            "Then the tally, and call it done\n"
            "And the sea will call us less\n"
        ),
    },
    "bar-count-nine": {
        "genre": "country, 12-bar blues",
        "prompt": (
            "Slow country blues in a strict 12-bar, brushed snare, slide guitar, "
            "worn baritone. Sparse, dry, road-worn. Chorus repeats three times."
        ),
        "lyrics": (
            "[Verse]\n"
            "I wrote it down in county lines\n"
            "The rain came through in county lines\n"
            "And everything I carried\n"
            "Came only as far as the lines\n\n"
            "[Chorus - 12-bar, repeat x3]\n"
            "Nine bars of road and then the rain\n"
            "Nine bars and the river does not care\n"
            "Nine bars and the ledger closes\n"
            "Nine bars and the closing is the sound\n"
        ),
    },
    "limerick-of-the-fleet": {
        "genre": "folk, comic, narrative",
        "prompt": (
            "Dry narrative folk with a comic edge, acoustic guitar, upright bass, "
            "brushes. Unhurried, deadpan, a fable. The rhythm must be even and "
            "strongly accented so the five-line form lands."
        ),
        "lyrics": (
            "There once was a fleet that did run\n"
            "All claims checked, and none begun\n"
            "The evidence kept was sound\n"
            "Its ledger, pressed to the ground\n"
            "Which is how a whole fleet can be run\n"
            "\n"
            "(Down to the proof, and the proof to none.)\n"
        ),
    },
}

# ---------------------------------------------------------------- helpers


def die(msg):
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def key():
    k = os.environ.get("MINIMAX_KEY", "").strip()
    if not k:
        die(
            "MINIMAX_KEY is not set.\n"
            "  This is a known failure class in this project: STUBS.md records an\n"
            "  identical incident for GITHUB_TOKEN. Verify the variable is actually\n"
            "  exported before assuming the pipeline is broken.\n"
            "    export MINIMAX_KEY=<key>"
        )
    return k


def sha256_and_size(path):
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def verify_mp3(path):
    """file -b is the minimum proof. An HTTP 200 with status_code:0 is NOT proof."""
    try:
        out = subprocess.run(
            ["file", "-b", str(path)], capture_output=True, text=True, timeout=30
        ).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"file(1) unavailable: {e}", False
    # Require an actual MPEG/ADTS layer, not "ASCII text" or "data".
    ok = ("MPEG ADTS" in out or "MPEG Layer" in out or "Audio file" in out)
    return out, ok


# ---------------------------------------------------------------- render


def render(name, spec, model, out_root, instrumental=False):
    try:
        import requests
    except ImportError:
        die("python `requests` is not installed (pip install requests)")

    d = out_root / name
    d.mkdir(parents=True, exist_ok=True)
    mp3 = d / f"{name}.mp3"

    payload = {
        "model": model,
        "prompt": spec["prompt"],
        "output_format": "url",
        "audio_setting": {"format": "mp3", "sample_rate": 44100, "bitrate": 256000,
                           "channel": 2},
    }
    if instrumental:
        payload["is_instrumental"] = True          # and OMIT lyrics
    else:
        payload["lyrics"] = spec["lyrics"]         # required when not instrumental

    t0 = time.time()
    print(f"[{name}] POST {ENDPOINT} model={model} "
          f"timeout={DEFAULT_TIMEOUT}s ...", flush=True)
    try:
        r = requests.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"},
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
    except Exception as e:  # noqa: BLE001
        return {"track": name, "ok": False, "stage": "post",
                "error": f"{type(e).__name__}: {e}", "elapsed_s": round(time.time() - t0, 1)}

    elapsed = round(time.time() - t0, 1)
    if r.status_code != 200:
        return {"track": name, "ok": False, "stage": "post", "http_status": r.status_code,
                "body": r.text[:500], "elapsed_s": elapsed}

    body = r.json()
    base = body.get("base_resp") or {}
    if base.get("status_code", 0) != 0:
        return {"track": name, "ok": False, "stage": "base_resp",
                "status_code": base.get("status_code"),
                "status_msg": base.get("status_msg"), "elapsed_s": elapsed}

    trace_id = body.get("trace_id")
    url = None
    for k in ("audio", "url", "file_url"):
        v = body.get(k)
        if isinstance(v, str) and v.startswith("http"):
            url = v
            break
    if url is None:
        return {"track": name, "ok": False, "stage": "parse", "trace_id": trace_id,
                "error": f"no URL in response keys={list(body)}", "elapsed_s": elapsed}

    # URL expires in 24h — download NOW.
    try:
        with requests.get(url, stream=True, timeout=300) as ar:
            ar.raise_for_status()
            with open(mp3, "wb") as out:
                for chunk in ar.iter_content(1 << 20):
                    out.write(chunk)
    except Exception as e:  # noqa: BLE001
        return {"track": name, "ok": False, "stage": "download", "trace_id": trace_id,
                "error": f"{type(e).__name__}: {e}", "elapsed_s": elapsed}

    digest, size = sha256_and_size(mp3)
    ftype, is_mp3 = verify_mp3(mp3)
    manifest = {
        "track": name,
        "genre": spec.get("genre", ""),
        "model": model,
        "endpoint": ENDPOINT,
        "prompt": spec["prompt"],
        "lyrics": spec.get("lyrics", ""),
        "instrumental": instrumental,
        "trace_id": trace_id,
        "bytes": size,
        "sha256": digest,
        "file_b": ftype,
        "file_b_verified_mpeg": is_mp3,
        "render_seconds": elapsed,
        "source_url_expires_hours": 24,
    }
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    manifest["path"] = str(mp3)
    return {"track": name, "ok": is_mp3, "stage": "done", **manifest}
    if not is_mp3:
        return {"track": name, "ok": False, "stage": "verify", "trace_id": trace_id,
                "file_b": ftype, "bytes": size, "sha256": digest, "elapsed_s": elapsed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track")
    ap.add_argument("--prompt")
    ap.add_argument("--lyrics-file")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--instrumental", action="store_true")
    ap.add_argument("--batch", action="store_true")
    ap.add_argument("--out", default=str(OUT_ROOT))
    args = ap.parse_args()

    if not (args.track or args.batch):
        ap.error("need --track SLUG or --batch")

    if args.track and args.track not in TRACKS and not (args.prompt or args.lyrics_file):
        die(f"unknown track {args.track!r}; pass --prompt/--lyrics-file or use --batch")

    jobs = {}
    if args.batch:
        jobs = dict(TRACKS)
    else:
        spec = dict(TRACKS.get(args.track, {}))
        if args.prompt:
            spec["prompt"] = args.prompt
        if args.lyrics_file:
            spec["lyrics"] = Path(args.lyrics_file).read_text()
        if not spec.get("prompt"):
            die("--track given but no prompt available")
        jobs[args.track] = spec

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    results = []
    for name, spec in jobs.items():
        for attempt in range(1, MAX_RETRIES + 1):          # max 2 tries, ever
            res = render(name, spec, args.model, out_root, args.instrumental)
            if res.get("ok"):
                break
            print(f"[{name}] attempt {attempt}/{MAX_RETRIES} FAILED "
                  f"stage={res.get('stage')} {res.get('error') or res.get('status_msg')}",
                  flush=True)
            if attempt < MAX_RETRIES:
                time.sleep(5)
        results.append(res)
        print(f"[{name}] " + (f"OK trace_id={res.get('trace_id')} bytes={res.get('bytes')} "
                              f"sha256={res.get('sha256')}" if res.get("ok")
                              else "GAVE UP (logged, moving on)"), flush=True)

    log = out_root / "render-log.json"
    log.write_text(json.dumps(results, indent=2) + "\n")
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok}/{len(results)} rendered. log -> {log}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
