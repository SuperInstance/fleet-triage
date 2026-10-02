# scout-DOMAINS — tool-shaped names that were never resolved

**Lane:** SCOUT / DOMAINS · **Started:** 2026-10-02T17:05Z · **Stub written:** 2026-10-02T17:15Z
**Status:** STUB — 20+ names probed, one premise correction pending confirmation.
**Access:** `${GITHUB_TOKEN}` **is not set in this sandbox** (verified: `env | grep -i token` empty,
no `/root/.config/gh/hosts.yml`, no `.mavis` credential). Account-wide README + commit-message
sweep is therefore **NOT DONE** — everything below is from local trees. This is the single biggest
gap in this stub and it is the first thing to fix.

---

## 0. The correction, first, because it changes the shape of the whole scout

The incident brief says `typescript.ai` "was named as a tool to use *massively and continually*."

**`typescript.ai` does not appear anywhere in the corpus I can reach.** Zero occurrences across
8 project trees (`fleet-triage`, `superinstance-papers`, `constraint-theory-core`, `fleetlint`,
`fleet-kit`, `readme-verifier`, `quilt-score`, `narrator`). The string "massively and continually"
also does not appear; the three "massively" hits are all about GPU parallelism, not tools.

**And the API the fleet actually uses is alive.** The credential is `TYPESAFEAI_KEY`
(61 mentions in `fleet-triage`). The domain those scripts POST to is `api.typesafe.ai` —
not `typescript.ai`. I probed it:

```
POST https://api.typesafe.ai/v1/systemone
  -> HTTP 403  {"detail":{"error_type":"authentication_error",
             "message":"Must supply an API key! Check your request and try again."}}

GET  https://api.typesafe.ai/openapi.json  -> 200
  openapi 3.1.0 | title "TypeSafe" | version 0.2.0
  desc: "Ask yes/no questions, evaluate statements, select choices, or assign ratings
         to your content. Send your API key in the Authorization header as Bearer <API_KEY>.
         Use GET /v1/models to discover available model names."
  paths: POST /v1/systemone  |  GET /v1/models
```

That description is a verbatim match for what the fleet's experiments claim to have measured
("criteria + scale label arrays, 10 levels max … normalized score with per-index probabilities").

**So the parked page and the real service are two different domains that look like the same
thing.** `typescript.ai` is a GoDaddy aftermarket lander. `api.typesafe.ai` is a live, documented,
auth-gated API that is the actual thing the corpus was written against. The scout's framing —
"a name that looks like a service and resolves to a page for sale" — is true, but the failure
is **not** "the fleet built on a parked domain." It is closer to **"the fleet's own name for the
service drifted away from the service, and nobody noticed because a domain is not a path and
the live resolver has nothing to resolve it against."**

This is the same class as the 4,789 dangling `path:line` refs, not a new one. The instrument gap
is real; this instance of it has not yet been shown to have caused a build.

---

## 1. Method

- Harvest: walk `.md/.py/.ts/.js/.sh/.rs/.json/.yml/.toml`, extract domains by regex, **gate on
  line-level tool context** (`api|service|platform|tool|provider|endpoint|sdk|key|token|auth|
  host|url|base_url|curl|dashboard|portal|gateway|backend|proxy|registry|console|credential…`).
  Rationale: ungated extraction returned 3,346 candidates of which ~90% are code identifiers
  (`lease.id`, `tile.name`, `t.store`). Context gating is also literally the task's own criterion.
- Probe: real HTTPS request, read the **body** not just the status, follow redirects, record
  UTC timestamp per probe.
- Rate limit: 0.8 s between probes, 32 hosts, 32 s of wire time.

**Every row below is a probe, not an inference.** `PARKED` / `UNVERIFIABLE` / `LOGIN-WALL` /
`ALIVE` / `ALIVE-BEHIND-AUTH` are the classes.

---

## 2. First twenty probed names (plus the deep dives)

Batch timestamp window: **2026-10-02T17:06:53Z → 17:07:25Z**. Deep dive on `api.typesafe.ai`
at **17:13:18Z**.

| # | Name | Status | Final URL / body says | Class |
|---|---|---|---|---|
| 1 | `typescript.ai` | 200 | 114 B JS shell → `/lander` → GoDaddy `forsale.godaddy.com` | **PARKED** |
| 2 | `api.typesafe.ai` (root) | 404 | `{"detail":"Not Found"}` — FastAPI, no route at `/` | ALIVE (misleading) |
| 2b | **`api.typesafe.ai/v1/systemone`** | **403** | `{"error_type":"authentication_error","message":"Must supply an API key!"}` | **ALIVE-BEHIND-AUTH** |
| 2c | `api.typesafe.ai/openapi.json` | 200 | OpenAPI 3.1.0, "TypeSafe" v0.2.0, 2 paths | **ALIVE / DOCUMENTED** |
| 2d | `api.typesafe.ai/docs` | 200 | FastAPI docs page | **ALIVE / DOCUMENTED** |
| 3 | `typesafe.ai` | 200 | Framer marketing site, title "Home - TypeSafe AI" | SITE (not API) |
| 3b | `typesafe.ai/v1/systemone` | 404 | Framer "Page Not Found" — confirms API is on `api.` only | CORRECT SPLIT |
| 4 | `typesafe-ai.github.io` | 200 | "TypeSafe AI" static page | SITE |
| 5 | `api.deepseek.com` | 401 | `Authentication Fails (governor)` | **ALIVE-BEHIND-AUTH** |
| 6 | `api.smolmachines.com` | 401 | empty body, `application/json` | **ALIVE-BEHIND-AUTH** |
| 7 | `smolmachines.com` | 200 | Vite SPA, no `<title>` | SITE (JS shell) |
| 8 | `polln.ai` | 200 | → `www.polln.ai`, "Polln — Knowledge that spreads" | SITE |
| 9 | `api.polln.ai` | — | `URLError` — **does not resolve** | **UNVERIFIABLE (DNS)** |
| 10 | `docs.polln.ai` | — | `URLError` — **does not resolve** | **UNVERIFIABLE (DNS)** |
| 11 | `cocapn.ai` | 200 | SEO landing page "How Multi-Agent AI Coordination Actually Works" | SITE (marketing) |
| 12 | `api.cocapn.ai` | 523 | "cocapn.ai \| 523: Origin is unreachable" | **DOWN (origin)** |
| 13 | `cocapn.com` | 200 | "cocapn.com · Phase 1 — a voice-first vessel" | SITE (half-built) |
| 14 | `superinstance.ai` | 200 | "🤖 SuperInstance AI" | SITE |
| 15 | `api.superinstance.ai` | 200 | "SuperInstance API" doc page | SITE (docs, not proven API) |
| 16 | `deckboss.ai` | 200 | **→ `deckboss.net`** (cross-domain redirect) | SITE |
| 17 | `deckboss.net` | 200 | "DeckBoss — Voice-first fishing logbook" | SITE |
| 18 | `dmlog.ai` | 200 | "dmlog.ai — Dungeon Master campaign tools" | SITE |
| 19 | `luciddreamer.ai` | 200 | "luciddreamer.ai — the substrate's dream home" | SITE |
| 20 | `evolink.ai` | 200 | Next.js marketing site, no title | SITE |
| 21 | `capitaine.ai` | 200 | **"capitaine.ai — reserved"**, `noindex` | **PARKED (self-declared)** |
| 22 | `capitaineai.com` | 200 | → `capitaine.ai` (same reserved page) | **PARKED** |
| 23 | `reallog.ai` | 200 | "reallog.ai — Real-world scene logger" | SITE |
| 24 | `kimi.ai` | 200 | → `www.kimi.ai`, "Kimi AI with K3" | SITE (real, 3rd party) |
| 25 | `exe.dev` | 200 | "exe.dev - ssh exe.dev" | SITE (real, 3rd party) |
| 26 | `mothquantum.com` | 200 | "MOTH" | SITE |
| 27 | **`moth.ai`** | 200 | **114 B JS shell → `/lander`** — byte-identical to #1 | **PARKED** |
| 28 | `agentreceipts.ai` | 200 | "Agent Receipts — cryptographic audit trails for AI agents" | SITE |
| 29 | `halfpixel.ai` | 200 | "Halfpixel — Real World Spatial Intelligence" | SITE |
| 30 | `api.wandb.ai` | 404 | `404 page not found` (Go) | UNVERIFIABLE (no root route) |
| 31 | `cloud.tensorlake.ai` | 200 | **→ `/login`** | **LOGIN WALL** |
| 32 | `gpt.fiftyone.ai` | 200 | → `try.fiftyone.ai/datasets/coco-demo/samples` | SITE (redirects off-name) |

### Provisional tally (n=32, of which 4 are deep-dive rows on one host)

- **ALIVE / documented / behind-auth: 4** — `api.typesafe.ai`, `api.deepseek.com`, `api.smolmachines.com`, `typesafe-ai.github.io`
- **PARKED: 3** — `typescript.ai`, `moth.ai`, `capitaine.ai` (+`capitaineai.com` → same)
- **UNVERIFIABLE: 3** — `api.polln.ai`, `docs.polln.ai` (NXDOMAIN), `api.wandb.ai` (404 at root)
- **LOGIN WALL: 1** — `cloud.tensorlake.ai`
- **DOWN: 1** — `api.cocapn.ai` (523, origin unreachable)
- **SITE, not an API: 18** — 200s that are marketing pages, Vite/Next.js shells, or SEO landings

**The honest headline: of 32 tool-shaped names, 4 are demonstrably real services.**
`SITE` is not a failure — a fleet that documents its own frontends is doing the right thing —
but **only 4 of 32 would survive an "is this a live endpoint" check**, and one of those 4 is the
one the incident was about, in a different spelling.

---

## 3. Classification by *how it was named* (the severity axis)

| Class | Where it lives | Count (so far) | Severity | Why |
|---|---|---|---|---|
| **A. In a paper / methodology section** | `superinstance-papers/*.md` methods blocks | **0 found** | — | would be the worst; none yet |
| **B. In a runnable script with a live-call guard** | `fleet-triage/org_scratch/qtx/experiments/*.mjs` | **1 host** (`api.typesafe.ai`) | **HIGH if it breaks** | scripts `exit 2` loudly without the key — the best-behaved failure mode in the whole scout |
| **C. In a repo README** | `fleet-triage/readmes/*.readme` etc. | 6 (`smolmachines`, `deckboss`, `cocapn`, `polln`, `luciddreamer`, `halfpixel`) | MEDIUM | a reader builds against it |
| **D. In an agent brief / scratch note** | `org_scratch/*/MEMORY.md`, `CREDENTIALS.md` | **3** (`DEEPSEEK_API_KEY` 137, `DEEPINFRA_API_KEY` 67, `GROQ_API_KEY` 41) | MEDIUM | an agent treats it as a tool it may use |
| **E. In a commit message** | not yet reached — **no token, no local commit corpus** | **0 / unknown** | UNKNOWN | biggest blind spot |
| **F. Named in an orchestrator brief only** | this task | **1** (`typescript.ai`) | **none, so far** | zero corpus support |

Class F is where the incident lives, and it is the *only* class with **zero** corroborating
occurrences in the fleet's own writing. That is a real result and it cuts against the premise.

---

## 4. The worst one

Not the most numerous — there is no "most numerous," every finding here is n=1 or n=3.

**Worst: `api.typesafe.ai` as cited in `fleet-triage/org_scratch/qtx/experiments/API_LIMITS_R1.md:9`**
— because it is a **methodology document whose entire empirical basis is one unauthenticated-
from-here endpoint**, and the corpus contains numbers derived from it that a reader would take
as findings:

> "Wire baseline (verified live earlier today, S1/S2/S3): `POST https://api.typesafe.ai/v1/systemone`"
> and, in `experiments/README.md`: "Run: `TYPESAFEAI_KEY=… node experiments/s1-triagedesk-live.mjs`
> (12 live calls, ~3¢ total). **Result (2026-09-25 09:1x CST): 12/12 live, 5/5 pins green.**"

Downstream of that claim sit **named scientific findings** with a receipt chain:
"floor/ceiling collapse … the scale has effectively ~3 usable rungs",
"adjacent continuum gaps = 0,4,5,0,0 levels", "H3 SUPPORTED strongly".

**Why this is the worst and not `typescript.ai`:** those findings are the kind of thing that gets
*believed and built on* — they are specific, quantitative, pre-registered, hash-chained, and
read like data. `typescript.ai` is a parked page nobody has ever cited. One of the two is a live
service; the other is not in the corpus at all. **I have not found evidence that anything was
built on the parked domain, and I have found strong evidence that real work was built on the
live one — which is the opposite failure: a real service, unversioned, whose receipts expire
the moment the key or the route does.**

**The timestamp is the whole point.** `typesafe.ai` self-describes as *Framer, Published
Sep 28, 2026*. The corpus's live runs are dated 2026-09-25 — **three days before the marketing
site was last published**, and the API is on a different host from the site. Every receipt in
`experiments/out/` is a claim about a service version we can no longer name, on a host with no
versioned contract, reachable only with a key nobody in this sandbox holds. Those receipts are
**four days old and already un-replayable by me.**

---

## 5. What this implies about the rest (honest count, no padding)

- I probed **32** tool-shaped names. **4 are live services.** I am not going to call the other 28
  "defects" — most are real fleet frontends that 200 because they should.
- The *pattern* is one sentence: **the fleet is good at documenting things it built and bad at
  recording the version/contract of things it consumed.** Every `SITE` row above is a thing the
  fleet owns. Every `ALIVE` row is a thing it borrows. There is **no place in the corpus where a
  borrowed service's version or contract is pinned next to the finding it produced.**
- Therefore the honest generalization is: `typescript.ai` is probably not a one-off; it is
  probably the *shape* of a gap that will show up as a citation with no version. **But I have
  one confirmed instance and zero corpus support for the specific claim in the brief**, and I am
  reporting that rather than manufacturing a pattern around it.

---

## 6. Next probes (in priority order)

1. **Restore `${GITHUB_TOKEN}`** → sweep all account READMEs + **commit messages** (Class E,
   currently unknown). This is the only way to close the "how was it named" distribution.
2. Probe the `/v1/models` route of `api.typesafe.ai` with no key — does it leak the model list
   (i.e. is the oracle still there, just gated)? Determines whether receipts are re-replayable.
3. `NXDOMAIN` check on `api.polln.ai` / `docs.polln.ai` — is `polln.ai` split into a dead
   sub-domain pair while `www.polln.ai` is alive? That would be a **second** live-service drift.
4. Check whether `qtx` receipts in `experiments/out/` carry a **service version**. If they do not,
   that is the finding, and it is the one worth escalating.

---
*Stub. Probes are real and timestamped; the API_LIMITS_R1 claim is quoted from
`fleet-triage/org_scratch/qtx/experiments/`. No writes outside this file; no pushes.*
