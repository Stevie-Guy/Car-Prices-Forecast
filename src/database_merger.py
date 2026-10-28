#!/usr/bin/env python3
"""
database_merger.py - combina oricate fisiere SQLite (.db) cu aceeasi structura
intr-un singur fisier si elimina randurile duplicate.

Exemple:
    python database_merger.py cars.db cars2.db cars3.db
    python database_merger.py cars.db cars2.db -o rezultat.db
    python database_merger.py *.db -o merged.db
    python database_merger.py folder_cu_db/            (toate .db din folder)
"""

import argparse
import glob
import os
import sqlite3
import sys


def q(name):
    """Citeaza un identificator SQL."""
    return '"' + name.replace('"', '""') + '"'


def collect_inputs(items, output):
    """Expandeaza foldere / wildcard-uri si pastreaza ordinea, fara dubluri."""
    files = []
    for item in items:
        if os.path.isdir(item):
            found = sorted(glob.glob(os.path.join(item, "*.db")))
        elif any(ch in item for ch in "*?["):
            found = sorted(glob.glob(item))
        else:
            found = [item]
        files.extend(found)

    out_abs = os.path.abspath(output)
    result, seen = [], set()
    for f in files:
        a = os.path.abspath(f)
        if a == out_abs or a in seen:
            continue
        if not os.path.isfile(f):
            print(f"[!] Nu exista: {f} (ignorat)")
            continue
        seen.add(a)
        result.append(f)
    return result


def user_tables(conn, schema="main"):
    rows = conn.execute(
        f"SELECT name, sql FROM {schema}.sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid"
    ).fetchall()
    return rows


def user_indexes(conn, schema="main"):
    return conn.execute(
        f"SELECT name, sql FROM {schema}.sqlite_master "
        "WHERE type='index' AND sql IS NOT NULL ORDER BY rowid"
    ).fetchall()


def table_columns(conn, table, schema="main"):
    """Returneaza (toate coloanele, coloana id auto-generata sau None)."""
    info = conn.execute(f"PRAGMA {schema}.table_info({q(table)})").fetchall()
    cols = [r[1] for r in info]
    pks = [r for r in info if r[5] > 0]
    auto_id = None
    # PRIMARY KEY simplu de tip INTEGER = alias pentru rowid (ex. AUTOINCREMENT):
    # valorile difera intre fisiere, deci nu trebuie comparate/copiate.
    if len(pks) == 1 and (pks[0][2] or "").upper() == "INTEGER":
        auto_id = pks[0][1]
    return cols, auto_id


def merge(inputs, output):
    if os.path.exists(output):
        os.remove(output)

    out = sqlite3.connect(output)
    out.execute("PRAGMA foreign_keys = OFF")

    # 1) Creeaza structura (tabele + indexuri) din toate fisierele
    for path in inputs:
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        existing = {r[0] for r in user_tables(out)}
        for name, sql in user_tables(src):
            if name not in existing:
                out.execute(sql)
        existing_idx = {r[0] for r in user_indexes(out)}
        for name, sql in user_indexes(src):
            if name not in existing_idx:
                try:
                    out.execute(sql)
                except sqlite3.OperationalError:
                    pass
        src.close()
    out.commit()

    # 2) Copiaza datele
    stats = {t[0]: {"read": 0} for t in user_tables(out)}
    for path in inputs:
        out.execute("ATTACH DATABASE ? AS src", (path,))
        src_tables = {r[0] for r in user_tables(out, "src")}
        for table in stats:
            if table not in src_tables:
                print(f"[!] {path}: lipseste tabela '{table}'")
                continue
            out_cols, auto_id = table_columns(out, table)
            src_cols, _ = table_columns(out, table, "src")
            cols = [c for c in out_cols if c in src_cols and c != auto_id]
            missing = [c for c in out_cols if c not in src_cols and c != auto_id]
            if missing:
                print(f"[!] {path}.{table}: coloane lipsa {missing} (raman NULL)")
            if not cols:
                continue
            col_sql = ", ".join(q(c) for c in cols)
            n = out.execute(f"SELECT COUNT(*) FROM src.{q(table)}").fetchone()[0]
            stats[table]["read"] += n
            # OR IGNORE: sare peste randurile care incalca PRIMARY KEY / UNIQUE
            out.execute(
                f"INSERT OR IGNORE INTO main.{q(table)} ({col_sql}) "
                f"SELECT {col_sql} FROM src.{q(table)}"
            )
        out.commit()
        out.execute("DETACH DATABASE src")

    # 3) Elimina duplicatele exacte (comparand toate coloanele, fara id-ul auto)
    for table in stats:
        cols, auto_id = table_columns(out, table)
        cmp_cols = [c for c in cols if c != auto_id]
        if not cmp_cols:
            continue
        group_sql = ", ".join(q(c) for c in cmp_cols)
        out.execute(
            f"DELETE FROM {q(table)} WHERE rowid NOT IN "
            f"(SELECT MIN(rowid) FROM {q(table)} GROUP BY {group_sql})"
        )
        stats[table]["final"] = out.execute(
            f"SELECT COUNT(*) FROM {q(table)}"
        ).fetchone()[0]
    out.commit()
    out.execute("VACUUM")
    out.close()
    return stats


def main():
    ap = argparse.ArgumentParser(
        description="Combina mai multe fisiere SQLite cu aceeasi structura si elimina duplicatele."
    )
    ap.add_argument(
        "inputs",
        nargs="+",
        help="fisiere .db, foldere sau wildcard-uri (numar nelimitat)",
    )
    ap.add_argument(
        "-o",
        "--output",
        default="merged.db",
        help="fisierul rezultat (implicit: merged.db)",
    )
    args = ap.parse_args()

    inputs = collect_inputs(args.inputs, args.output)
    if not inputs:
        sys.exit("Niciun fisier de intrare valid.")

    print(f"Combin {len(inputs)} fisiere in '{args.output}':")
    for f in inputs:
        print(f"  - {f}")

    stats = merge(inputs, args.output)

    print("\nRezultat:")
    for table, s in stats.items():
        removed = s["read"] - s.get("final", 0)
        print(
            f"  {table}: {s['read']} randuri citite -> {s.get('final', 0)} "
            f"pastrate ({removed} duplicate eliminate)"
        )
    print(f"\nGata: {args.output}")


if __name__ == "__main__":
    main()
