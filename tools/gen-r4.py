#!/usr/bin/env python3
"""gen-r4 — render the three round-4 tracks. Run in the BACKGROUND and poll.

Lessons encoded here, all of which cost a previous round a track:
  * model ids are music-3.0 and music-2.6. music-01/music-02 are dead.
  * a 20 s probe times out on a HEALTHY account. Real renders take 61-101 s.
  * the returned URL expires in 24 h — download IMMEDIATELY.
  * save each track the moment it lands, never batch at the end. An
    instrumental killed mid-render on a previous round was lost that way.
  * retry at most twice. A third try is how a lane becomes a hang.
  * verify every file with `file -b`. HTTP 200 + status_code 0 is the floor,
    not the proof.

Usage:  python3 gen-r4.py --batch        # all three
        python3 gen-r4.py --slug c4-claim
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = "https://api.minimax.io/v1/music_generation"
MODEL = "music-3.0"                      # music-2.6 is the other live id
TIMEOUT = 900                            # instrumentals run long; 900 s not 120 s
MAX_TRIES = 3                            # 1 attempt + 2 retries, never more
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "music-r4")

TRACKS = [
    {
        "slug": "halyard-and-ledger",
        "shelf": "01-shanty",
        "genre": "sea shanty, male chorus, call and response, unaccompanied, sea shanty, "
                 "clanking capstan, 4/4, D minor",
        "lyrics": """[Verse One Lead]
One sound is not a chart, and one sound is not a chart at all
Two instruments or nothing, that's the whole of what we call

[Verse One Crew]
So haul the single reading up, let the taut wire be the sound
And when the second joins the line, both ends are on the ground

[Verse Two Lead]
What survives is bounded by what the looking carried down
Nothing downstream recovers what the looking never found

[Verse Two Crew]
So hold the ledger open boys, and let the columns show
The cell that kept the colour keeps the row that we must know

[Chorus Lead]
Hey the trace is not the claim, the trace is not the claim
Hey the seal is on the file, it never touched the game

[Chorus Crew]
One sound is not a chart boys, one sound is not a chart
Two instruments or nothing, or it never even starts

[Outro Crew]
Haul it up and call it sound
Haul it down and call it ground""",
    },
    {
        "slug": "nine-bars-to-town",
        "shelf": "02-country",
        "genre": "country, truck driver, warm baritone, Telecaster and pedal steel, "
                 "steady four to the floor, A key, 12 bar blues feel",
        "lyrics": """[Verse One]
The truck has a rattle, a dust on the rail
And a nine dollar night for the work of the whole
And the radio's hum is a low, low hum
And the county road runs like a ribbon of bone

[Chorus]
Nine bars and the ledger is closed
Nine bars and the number is whole
Nine bars and the value's exposed
Nine bars and the mile to the goal

[Verse Two]
My father said the ledger and the road were the same
Both of them are only what the looking claimed
One says what was spent and the other where it went
And the difference is a colour that the counting left

[Chorus]
Nine bars and the ledger is closed
Nine bars and the number is whole
Nine bars and the value's exposed
Nine bars and the mile to the goal

[Verse Three]
She said the money's a season, and seasons are short
And September is coming and I'm not the sort
To leave on a Sunday when the pull is the sum
So I take what the road gives and I give back to none

[Chorus]
Nine bars and the ledger is closed
Nine bars and the number is whole
Nine bars and the value's exposed
Nine bars and the mile to the goal

[Outro]
Nine bars and the radio's low
Nine bars and the headlights are showing
Nine bars and the year's running out
Nine bars and the night is still growing""",
    },
    {
        # the hard form: exactly 8 syllables per line, and the track that
        # carries the checkable claim.
        "slug": "one-hundredth-of-the-value",
        "shelf": "standalone",
        "genre": "spare solo piano and brushed kit, close mic, no reverb tail, "
                 "rubato, E flat major, very quiet, ends on a held single note",
        "lyrics": """[Verse One]
The colour is what you can see
The value is what you can read
Just one part in ninety is gone
The colour is one bit, so cheap

[Verse Two]
A hash is a perfect disguise
Sixty-four bits of even soup
The hash keeps no shape of the board
Sixty-four bits of noise that's all

[Verse Three]
Nothing made later brings it back
Nowhere down the line can it mend
It kept the shape it lost the paint
Now drop the colour keep the game

[Outro]
One part in ninety for the eye
The colour is what you can see
The value is what you can read
Now drop the colour keep the game""",
    },
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def post(payload, key):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())


def render(track, key, log):
    os.makedirs(OUT, exist_ok=True)
    mp3 = os.path.join(OUT, track["slug"] + ".mp3")
    for attempt in range(1, MAX_TRIES + 1):
        t0 = time.time()
        try:
            resp = post({
                "model": MODEL,
                "prompt": track["genre"],
                "lyrics": track["lyrics"],
                "output_format": "url",
            }, key)
        except Exception as e:                                   # noqa: BLE001
            log.append({"slug": track["slug"], "attempt": attempt, "error": repr(e)})
            print(f"[{track['slug']}] attempt {attempt}: transport error {e!r}", flush=True)
            continue
        br = resp.get("base_resp", {})
        if br.get("status_code") not in (0, None):
            log.append({"slug": track["slug"], "attempt": attempt, "base_resp": br})
            print(f"[{track['slug']}] attempt {attempt}: {br}", flush=True)
            continue
        url = resp.get("data", {}).get("audio")
        trace = resp.get("trace_id") or br.get("trace_id")
        if not url:
            log.append({"slug": track["slug"], "attempt": attempt, "no_url": True})
            continue
        # download IMMEDIATELY — the URL dies in 24 h
        with urllib.request.urlopen(url, timeout=120) as r, open(mp3, "wb") as f:
            f.write(r.read())
        # saved the moment it lands, not at the end of the batch
        ident = subprocess.run(["file", "-b", mp3], capture_output=True, text=True).stdout.strip()
        manifest = {
            "slug": track["slug"],
            "shelf": track["shelf"],
            "model": MODEL,
            "prompt": track["genre"],
            "lyrics": track["lyrics"],
            "trace_id": trace,
            "bytes": os.path.getsize(mp3),
            "sha256": sha256(mp3),
            "file": ident,
            "render_seconds": round(time.time() - t0, 1),
            "attempt": attempt,
        }
        with open(os.path.join(OUT, track["slug"] + ".manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"[{track['slug']}] OK trace_id={trace} {manifest['bytes']}B "
              f"{manifest['render_seconds']}s :: {ident}", flush=True)
        return manifest
    print(f"[{track['slug']}] FAILED after {MAX_TRIES} attempts — logged, moving on", flush=True)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", action="store_true")
    ap.add_argument("--slug")
    a = ap.parse_args()
    key = os.environ.get("MINIMAX_KEY", "")
    if not key:
        print("MINIMAX_KEY is not set. Exiting 1 — this is a credential failure, "
              "not a render failure. Nothing was attempted.", file=sys.stderr)
        return 1
    tracks = TRACKS
    if a.slug:
        tracks = [t for t in TRACKS if t["slug"] == a.slug]
    log = []
    for t in tracks:
        render(t, key, log)
    with open(os.path.join(OUT, "render-log.json"), "w") as f:
        json.dump(log, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
