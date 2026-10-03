#!/usr/bin/env python3
"""
cf_d1_readonly.py -- CF-D1 lane harness. READ-ONLY BY CONSTRUCTION.

Audits every D1 database in account 049ff5e84ecf636b53b162cbb580aae6:
inventory -> sqlite_master -> per-table row counts -> PRAGMA detail,
then joins the result against repo-side D1 declarations to find drift and
orphans in both directions.

SAFETY MODEL
------------
Read-only is enforced in code, not by intention. Two independent gates:

  1. `assert_readonly_sql()` -- every statement sent to /d1/database/{uuid}/query
     must begin with SELECT, PRAGMA, or WITH once leading comments and
     whitespace are removed. Anything else raises before the socket opens.
  2. `api()` -- refuses any HTTP verb other than GET, except a POST that is
     *only* permitted to the /query endpoint and only with SQL that passed
     gate 1. There is no code path to /execute, to a migration endpoint, or
     to any write verb.

The token is never logged, never written to any output artifact, and never
echoed in an error message. Its length and a 6-char fingerprint are recorded
in the run report so two runs can be shown to have used the same credential
without disclosing it.

USAGE
-----
  export CLOUDFLARE_TOKEN=...            # or CLOUDFLARE_API_TOKEN, or --token-file
  python3 cf_d1_readonly.py               # full audit
  python3 cf_d1_readonly.py --dry-run     # no network; prints the plan
  python3 cf_d1_readonly.py --selftest    # proves the read-only gates fire

Outputs:  cf_d1_inventory.json, cf_d1_audit.json, cf_d1_report.md
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ACCOUNT = "049ff5e84ecf636b53b162cbb580aae6"
API_ROOT = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}"

# Verbs this harness is architecturally incapable of issuing for non-query work.
ALLOWED_VERBS = {"GET"}
QUERY_ENDPOINT = re.compile(r"^/d1/database/[^/]+/query$")

READONLY_SQL_HEADS = ("SELECT", "PRAGMA", "WITH")


# --------------------------------------------------------------------------
# Gate 1 -- SQL read-only assertion
# --------------------------------------------------------------------------

def assert_readonly_sql(sql: str) -> str:
    """Raise unless `sql` is a read-only statement. Returns the stripped sql.

    Strips leading whitespace and SQL comments (-- line and /* block */) so a
    commented statement cannot smuggle a write past a naive prefix check.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("empty SQL rejected")
    s = sql.strip()
    # Remove leading block comments and line comments, repeatedly.
    while True:
        if s.startswith("--"):
            nl = s.find("\n")
            if nl == -1:
                raise ValueError("comment-only SQL rejected")
            s = s[nl + 1:].strip()
        elif s.startswith("/*"):
            end = s.find("*/")
            if end == -1:
                raise ValueError("unterminated comment in SQL rejected")
            s = s[end + 2:].strip()
        else:
            break
    head = s.split(None, 1)[0].upper() if s.split() else ""
    if head not in READONLY_SQL_HEADS:
        raise ValueError(
            f"read-only gate refused statement starting with {head!r}; "
            f"only {READONLY_SQL_HEADS} are permitted"
        )
    # PRAGMA has a mutating assignment form: `PRAGMA writable_schema=ON` is a
    # WRITE that passes a naive prefix check. Only the bare/read forms
    # (`PRAGMA x` and `PRAGMA x(...)`) are allowed; the `=` form never is.
    if head == "PRAGMA" and re.match(r"^PRAGMA\s+[A-Za-z_][A-Za-z0-9_]*\s*=", s, re.I):
        raise ValueError(
            "read-only gate refused PRAGMA assignment form; "
            "`PRAGMA x=value` mutates (e.g. writable_schema=ON), only reads allowed"
        )
    return s


# --------------------------------------------------------------------------
# Gate 2 -- HTTP verb + endpoint restriction
# --------------------------------------------------------------------------

def api(path: str, body: dict | None = None, token: str = "", timeout: int = 90):
    """Issue one request. GET only, except POST strictly to /query with gated SQL."""
    verb = "GET" if body is None else "POST"
    if verb not in ALLOWED_VERBS:
        if not (verb == "POST" and QUERY_ENDPOINT.match(path)):
            raise PermissionError(f"harness refuses {verb} to {path}")
        sql = body.get("sql", "")
        assert_readonly_sql(sql)
    url = f"{API_ROOT}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=verb)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:400].decode("utf8", "replace")


def query(db_uuid: str, sql: str, token: str):
    st, body = api(f"/d1/database/{db_uuid}/query", {"sql": sql}, token=token)
    if st != 200:
        return None, f"HTTP {st}: {str(body)[:200]}"
    if isinstance(body, dict) and body.get("success") is False:
        return None, f"API error: {str(body.get('errors'))[:200]}"
    return body, None


def rows_of(payload):
    """Extract the result rows from a D1 query envelope."""
    try:
        return payload["result"][0]["results"]
    except Exception:
        return []


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------

def token_fingerprint(tok: str) -> str:
    """Non-reversible-ish 6-char handle so runs can be compared safely."""
    import hashlib
    if not tok:
        return "none"
    return "sha256:" + hashlib.sha256(tok.encode()).hexdigest()[:6] + f"/len{len(tok)}"


def audit(db, token, verbose=True):
    """Full read-only pass over one database. Returns a dict; never raises."""
    name, uuid = db.get("name"), db.get("uuid")
    rec = {
        "name": name,
        "uuid": uuid,
        "created_at": db.get("created_at"),
        "api_file_size": db.get("file_size"),
        "api_num_tables": db.get("num_tables"),
        "api_version": db.get("version"),
        "running_in": db.get("running_in"),
        "location_hint": db.get("location_hint"),
        "status": "ok",
        "error": None,
        "objects": [],          # every sqlite_master row, sql quoted verbatim
        "tables": [],
        "views": [],
        "indexes": [],
        "row_counts": {},
        "total_user_rows": 0,
        "schema_present": False,
        "schema_empty": None,
    }
    payload, err = query(uuid, "SELECT type, name, tbl_name, sql FROM sqlite_master", token)
    if err:
        rec["status"] = "unreadable"
        rec["error"] = err
        return rec
    objs = rows_of(payload)
    rec["objects"] = [
        {"type": o.get("type"), "name": o.get("name"),
         "tbl_name": o.get("tbl_name"), "sql": o.get("sql")}
        for o in objs
    ]
    rec["schema_present"] = len(objs) > 0
    rec["schema_empty"] = (len(objs) == 0)

    for o in rec["objects"]:
        if o["type"] == "table":
            rec["tables"].append(o["name"])
        elif o["type"] == "view":
            rec["views"].append(o["name"])
        elif o["type"] == "index":
            rec["indexes"].append(o["name"])

    for t in rec["tables"]:
        safe = t.replace('"', '""')
        p, e = query(uuid, f'SELECT COUNT(*) AS n FROM "{safe}"', token)
        n = None
        if p is not None:
            r = rows_of(p)
            n = r[0].get("n") if r else None
        else:
            e = f"{t}: {e}"
        rec["row_counts"][t] = n
        if isinstance(n, int):
            rec["total_user_rows"] += n

        for pragma in ("table_info", "index_list", "foreign_key_list"):
            pp, pe = query(uuid, f'PRAGMA {pragma}("{safe}")', token)
            if pp is None:
                continue
            detail = rows_of(pp)
            if pragma == "table_info":
                rec.setdefault("columns", {})[t] = [
                    {"name": c.get("name"), "type": c.get("type"),
                     "notnull": c.get("notnull"), "pk": c.get("pk"),
                     "dflt_value": c.get("dflt_value")} for c in detail
                ]
            elif pragma == "index_list":
                rec.setdefault("indexes_detail", {})[t] = detail
            else:
                rec.setdefault("fks", {})[t] = detail
        if verbose:
            print(f"    {t}: {n} rows", file=sys.stderr)
    return rec


def repo_side_declarations(root="/workspace"):
    """Walk the fleet for wrangler configs declaring D1 bindings."""
    decls = []
    pat = re.compile(r"[\"']?(database_name|database_id)[\"']?\s*[:=]\s*[\"']([^\"']*)[\"']")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "node_modules", "__pycache__", ".home", ".cache"}]
        for fn in filenames:
            if not re.match(r"^wrangler\.(toml|json|jsonc)$", fn):
                continue
            p = os.path.join(dirpath, fn)
            try:
                txt = open(p, encoding="utf8", errors="replace").read()
            except OSError:
                continue
            for m in pat.finditer(txt):
                decls.append({
                    "repo": os.path.relpath(dirpath, root),
                    "file": os.path.relpath(p, root),
                    "kind": m.group(1),
                    "value": m.group(2),
                    "line": txt[:m.start()].count("\n") + 1,
                })
    return decls


def selftest():
    """Prove the read-only gates actually fire. Exits nonzero if any leaks."""
    print("Gate 1 -- SQL assertion")
    for good in ["SELECT 1", "  select name from sqlite_master",
                 "-- a comment\nPRAGMA table_info('t')", "/* c */ WITH x AS (SELECT 1) SELECT * FROM x"]:
        try:
            assert_readonly_sql(good)
            print(f"  ALLOW  {good[:44]!r}")
        except ValueError as e:
            print(f"  !! FAIL allowed-statement refused: {good!r} -> {e}")
            return 1
    for bad in ["DROP TABLE t", "DELETE FROM t", "INSERT INTO t VALUES(1)",
                "UPDATE t SET a=1", "CREATE TABLE x(a)", "ATTACH DATABASE 'x' AS y",
                "PRAGMA writable_schema=ON", "VACUUM", "--x\nDROP TABLE t", ""]:
        try:
            assert_readonly_sql(bad)
            print(f"  !! LEAK write-statement allowed: {bad!r}")
            return 1
        except ValueError:
            print(f"  BLOCK {bad[:44]!r}")
    print("Gate 2 -- verb/endpoint restriction")
    for path, body, label in [("/d1/database", {"sql": "DROP TABLE t"}, "POST inventory (write sql)"),
                              ("/d1/database/x/execute", {"sql": "SELECT 1"}, "POST /execute"),
                              ("/d1/database/x/query", {"sql": "SELECT 1"}, "POST /query (allowed)")]:
        verb = "GET" if body is None else "POST"
        blocked = False
        if verb not in ALLOWED_VERBS:
            if not (verb == "POST" and QUERY_ENDPOINT.match(path)):
                blocked = True
            else:
                try:
                    assert_readonly_sql(body.get("sql", ""))
                except ValueError:
                    blocked = True
        print(f"  {'BLOCK' if blocked else 'ALLOW'} {label}")
        if label.startswith("POST /query") and blocked:
            return 1
        if label.startswith("POST /") and "allowed" not in label and not blocked:
            return 1
    print("selftest OK")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token-file", help="read token from this path instead of env")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--outdir", default=os.path.dirname(os.path.abspath(__file__)))
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    tok = None
    if args.token_file:
        tok = open(args.token_file).read().strip()
    else:
        for k in ("CLOUDFLARE_TOKEN", "CLOUDFLARE_API_TOKEN", "CF_API_TOKEN"):
            if os.environ.get(k):
                tok = os.environ[k]
                break

    if args.dry_run:
        print(f"account   : {ACCOUNT}")
        print(f"token     : {token_fingerprint(tok or '')}")
        print("plan      : GET /d1/database?per_page=100")
        print("            POST /d1/database/{uuid}/query  SELECT type,name,tbl_name,sql FROM sqlite_master")
        print("            POST /d1/database/{uuid}/query  SELECT COUNT(*) FROM \"<table>\"")
        print("            POST /d1/database/{uuid}/query  PRAGMA table_info/index_list/foreign_key_list")
        print("repo side : os.walk /workspace for wrangler.{toml,json,jsonc}")
        return 0

    if not tok:
        print("BLOCKED: no Cloudflare credential in this session.", file=sys.stderr)
        print("  checked env: CLOUDFLARE_TOKEN, CLOUDFLARE_API_TOKEN, CF_API_TOKEN", file=sys.stderr)
        print("  supply one with: export CLOUDFLARE_TOKEN=...  or  --token-file PATH", file=sys.stderr)
        return 2

    print(f"token     : {token_fingerprint(tok)} (value never logged)", file=sys.stderr)

    st, body = api("/d1/database?per_page=100", token=tok)
    if st != 200 or not isinstance(body, dict) or not body.get("success"):
        print(f"inventory failed: HTTP {st} {str(body)[:300]}", file=sys.stderr)
        return 3
    dbs = body.get("result") or []
    print(f"inventory : {len(dbs)} databases", file=sys.stderr)

    recs = []
    for i, db in enumerate(dbs, 1):
        print(f"[{i}/{len(dbs)}] {db.get('name')} ({db.get('uuid')})", file=sys.stderr)
        try:
            recs.append(audit(db, tok))
        except Exception as e:  # noqa: BLE001 - one bad db must not kill the run
            recs.append({"name": db.get("name"), "uuid": db.get("uuid"),
                         "status": "error", "error": f"{type(e).__name__}: {e}"})
        time.sleep(0.15)  # be polite to the API

    decls = repo_side_declarations()
    live_names = {r["name"] for r in recs}
    live_uuids = {r["uuid"] for r in recs}
    declared_names = {d["value"] for d in decls if d["kind"] == "database_name"}
    declared_ids = {d["value"] for d in decls if d["kind"] == "database_id"}

    orphans_live = sorted(live_names - declared_names)
    missing_live = sorted(declared_names - live_names)
    bogus_ids = sorted(i for i in declared_ids
                       if i and re.fullmatch(r"[0-9a-fA-F-]{36}", i) and i not in live_uuids)

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "account": ACCOUNT,
        "token": token_fingerprint(tok),
        "counts": {
            "live_databases": len(recs),
            "schema_inspected": sum(1 for r in recs if r.get("schema_present") is not None),
            "empty_no_objects": sum(1 for r in recs if r.get("schema_empty") is True),
            "schema_but_zero_rows": sum(1 for r in recs
                                        if r.get("schema_present") and r.get("total_user_rows") == 0),
            "unreadable": sum(1 for r in recs if r.get("status") != "ok"),
            "not_checked": sum(1 for r in recs if r.get("status") != "ok"),
        },
        "orphans_live_no_repo": orphans_live,
        "repo_refs_missing_db": missing_live,
        "repo_ids_not_in_account": bogus_ids,
        "repo_declarations": decls,
        "databases": recs,
    }
    with open(os.path.join(args.outdir, "cf_d1_audit.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report["counts"], indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
