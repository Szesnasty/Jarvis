"""Quick smoke test for the generated Jira XML fixture.

Run from the backend/ directory:
    python3 scripts/check_jira_fixture.py
"""
import sys
from pathlib import Path

# Allow running from repo root or from backend/.
HERE = Path(__file__).resolve()
REPO = HERE.parents[1]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from services.jira_ingest import detect_format, iter_xml_issues as _iter_xml_items

p = BACKEND / "tests/fixtures/jira/large-export.xml"
fmt = detect_format(p, "xml")
print(f"Detected format: {fmt}")

issues = list(_iter_xml_items(p))
print(f"Parsed issues: {len(issues)}")

types: dict = {}
for i in issues:
    types[i.issue_type] = types.get(i.issue_type, 0) + 1
print(f"By type: {types}")
print(f"Epic links: {sum(1 for i in issues if i.epic_key)}")
print(f"Parents:    {sum(1 for i in issues if i.parent_key)}")
print(f"Sprints:    {sum(1 for i in issues if i.sprints)}")
print(f"Links:      {sum(len(i.links) for i in issues)}")
print(f"Comments:   {sum(len(i.comments) for i in issues)}")

s = issues[10]
print()
print("Sample issue:")
print(f"  key={s.issue_key}  type={s.issue_type}  status={s.status}")
print(f"  title={s.title[:80]}")
print(f"  epic={s.epic_key}  parent={s.parent_key}  sprints={len(s.sprints)}")
print(f"  labels={s.labels}")
print(f"  components={s.components}")
print(f"  links={[(l.target_key, l.link_type) for l in s.links][:3]}")
