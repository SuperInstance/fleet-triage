#!/usr/bin/env python3
"""
d1_claim_baseline.py -- build the REPO-SIDE half of the claim-state diff.

Emits, per D1-claiming repo: the database_name/uuid the repo claims, and the
tables+columns its own SQL files declare. This is the `expected` side of the
diff that `cf_d1_readonly.py` will compare against live `sqlite_master` once a
credential exists.

READ-ONLY: opens .sql files for reading only. No network, no writes.

Usage: python3 d1_claim_baseline.py <repos-root> <out.json>
"""
import json
import os
import re
import sys

# CREATE TABLE [IF NOT EXISTS] name ( ... )  -- column block, paren-balanced
CREATE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"'`\[]?(?P<name>\w+)[\"'`\]]?\s*\(",
    re.I,
)
COLUMN = re.compile(
    r"^\s*(?P<name>[\"'`\[]?\w+[\"'`\]]?)\s+(?P<type>[A-Za-z][\w ]*?)\b"
    r"(?P<rest>.*)$"
)
# DDL that can actually mutate an existing table.
ALTER = re.compile(r"ALTER\s+TABLE\s+[\"'`\[]?(\w+)", re.I)


def balanced_block(text, open_idx):
    """Return the text inside the paren starting at open_idx, paren-balanced."""
    depth, i = 0, open_idx
    while i < len(text):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i]
        i += 1
    return text[open_idx + 1 :]


def split_top(block):
    """Split a column-definition block on top-level commas."""
    parts, depth, cur, i = [], 0, [], 0
    while i < len(block):
        c = block[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


TABLE_CONSTRAINT = re.compile(
    r"^\s*(PRIMARY|FOREIGN|UNIQUE|CHECK|CONSTRAINT)\b", re.I
)


def parse_schema(sql_text, source):
    tables, alters = [], []
    for m in ALTER.finditer(sql_text):
        alters.append(m.group(1))
    for m in CREATE.finditer(sql_text):
        block = balanced_block(sql_text, m.end() - 1)
        cols, constraints = [], []
        for part in split_top(block):
            if not part.strip():
                continue
            if TABLE_CONSTRAINT.match(part):
                constraints.append(" ".join(part.split())[:120])
                continue
            cm = COLUMN.match(part)
            if not cm:
                continue
            name = cm.group("name").strip("\"'`[]")
            ctype = " ".join(cm.group("type").split())
            rest = cm.group("rest") or ""
            attrs = []
            if not re.search(r"\bNOT\s+NULL\b", rest, re.I):
                attrs.append("NULLABLE")
            if re.search(r"\bPRIMARY\s+KEY\b", rest, re.I):
                attrs.append("PK")
            if re.search(r"\bUNIQUE\b", rest, re.I):
                attrs.append("UNIQUE")
            if re.search(r"\bDEFAULT\b", rest, re.I):
                d = re.search(r"\bDEFAULT\s+([^\s,]+)", rest, re.I)
                if d:
                    attrs.append("DEFAULT " + d.group(1))
            if re.search(r"\bGENERATED\s+ALWAYS\b", rest, re.I):
                attrs.append("GENERATED")
            if re.search(r"\bREFERENCES\b", rest, re.I):
                rf = re.search(r"REFERENCES\s+([\w.]+)", rest, re.I)
                if rf:
                    attrs.append("FK->" + rf.group(1))
            cols.append({
                "name": name,
                "type": ctype.upper(),
                "attrs": attrs,
            })
        tables.append({
            "table": m.group("name"),
            "source": source,
            "columns": cols,
            "constraints": constraints,
        })
    return tables, alters


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    out_path = sys.argv[2] if len(sys.argv) > 2 else "d1_claim_baseline.json"

    repos = []
    for d in sorted(os.listdir(root)):
        rp = os.path.join(root, d)
        if not os.path.isdir(rp) or d.startswith("."):
            continue
        # wrangler config
        db_name = db_id = None
        for cfg in ("wrangler.toml", "wrangler.jsonc", "wrangler.json",
                    "cloud/wrangler.toml"):
            cp = os.path.join(rp, cfg)
            if os.path.isfile(cp):
                t = open(cp, encoding="utf-8", errors="replace").read()
                if "d1_databases" not in t:
                    continue
                nm = re.search(r'"?database_name"?\s*[=:]\s*"([^"]*)"', t)
                idm = re.search(r'"?database_id"?\s*[=:]\s*"([^"]*)"', t)
                if nm:
                    db_name = nm.group(1)
                if idm:
                    db_id = idm.group(1)
                if db_name:
                    break
        # sql files
        tables, alters, sql_files = [], [], []
        for dp, dn, fn in os.walk(rp):
            dn[:] = [x for x in dn
                     if x not in (".git", "node_modules", "target", "dist",
                                  "build", "__pycache__")]
            for f in fn:
                if f.endswith(".sql"):
                    p = os.path.join(dp, f)
                    rel = os.path.relpath(p, rp)
                    sql_files.append(rel)
                    t = open(p, encoding="utf-8", errors="replace").read()
                    tt, aa = parse_schema(t, rel)
                    tables += tt
                    alters += [{"table": a, "source": rel} for a in aa]
        if not (db_name or tables):
            continue
        repos.append({
            "repo": d,
            "database_name": db_name,
            "database_id": db_id,
            "id_resolvable": bool(db_id),
            "sql_files": sorted(sql_files),
            "has_migration_dir": any(
                "migration" in s.lower() for s in sql_files),
            "n_migration_files": sum(
                1 for s in sql_files if "migration" in s.lower()),
            "tables": tables,
            "alters": alters,
            "n_columns": sum(len(t["columns"]) for t in tables),
        })

    doc = {
        "repo_root": os.path.abspath(root),
        "note": "REPO-SIDE CLAIM SET. Built by reading .sql and wrangler "
                "configs only. No database was contacted. 'id_resolvable': "
                "false means the repo names a database but supplies no UUID, "
                "so the claim cannot be matched to any live database.",
        "n_repos": len(repos),
        "n_tables": sum(len(r["tables"]) for r in repos),
        "n_columns": sum(r["n_columns"] for r in repos),
        "n_alters": sum(len(r["alters"]) for r in repos),
        "repos": repos,
    }
    with open(out_path, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"repos={len(repos)} tables={doc['n_tables']} "
          f"columns={doc['n_columns']} alters={doc['n_alters']}")
    print(f"wrote {out_path}")
    for r in repos:
        star = "" if r["id_resolvable"] else "   <-- ID NOT RESOLVABLE"
        print(f"  {r['repo']:<40} db={str(r['database_name']):<20} "
              f"mig={r['n_migration_files']:<2} "
              f"tbl={len(r['tables']):<3} col={r['n_columns']:<4}{star}")


if __name__ == "__main__":
    main()
