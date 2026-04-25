"""Diagnostic: show entity counts and samples from the current Jarvis workspace DB."""
import sqlite3
from pathlib import Path

db = Path.home() / "Jarvis" / "app" / "jarvis.db"
conn = sqlite3.connect(db)

print("=== NOTE COUNT ===")
rows = conn.execute("SELECT COUNT(*) FROM notes").fetchone()
print(f"  Total notes: {rows[0]}")

print("\n=== GRAPH NODES BY TYPE ===")
for row in conn.execute(
    "SELECT type, COUNT(*) as n FROM graph_nodes GROUP BY type ORDER BY n DESC"
).fetchall():
    print(f"  {row[0]:<20} {row[1]}")

print("\n=== GRAPH EDGES BY TYPE ===")
for row in conn.execute(
    "SELECT type, COUNT(*) as n FROM graph_edges GROUP BY type ORDER BY n DESC"
).fetchall():
    print(f"  {row[0]:<25} {row[1]}")

print("\n=== SAMPLE PERSON NODES ===")
for row in conn.execute(
    "SELECT id, label FROM graph_nodes WHERE type='person' LIMIT 30"
).fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== SAMPLE ORG NODES ===")
for row in conn.execute(
    "SELECT id, label FROM graph_nodes WHERE type='organization' LIMIT 20"
).fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== NOTE TYPES (folder breakdown) ===")
for row in conn.execute(
    "SELECT folder, COUNT(*) as n FROM notes GROUP BY folder ORDER BY n DESC"
).fetchall():
    print(f"  {row[0]:<30} {row[1]}")

conn.close()
