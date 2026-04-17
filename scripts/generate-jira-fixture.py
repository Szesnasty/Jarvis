#!/usr/bin/env python3
"""Generate a realistic large Jira Cloud XML export for testing.

Produces a Jira RSS-style XML that matches the parser in
backend/services/jira_ingest.py:
- <rss><channel><item>...</item>... </channel></rss>
- 2 projects (PROJ, OPS)
- Epics, Stories, Tasks, Sub-tasks, Bugs, Spikes
- Issue links (blocks/relates/duplicates)
- Sprint customfield, Epic Link customfield
- Comments
- Labels & components

Usage:
    python scripts/generate-jira-fixture.py [output.xml] [--issues N]

Defaults to 120 issues across 2 projects.
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape


SEED = 42
random.seed(SEED)

PROJECTS = [
    {"key": "PROJ", "name": "Product Platform"},
    {"key": "OPS", "name": "Operations & Infrastructure"},
]

ISSUE_TYPES_NON_EPIC = ["Story", "Task", "Bug", "Sub-task", "Spike"]
STATUSES = [
    ("To Do", "new"),
    ("In Progress", "indeterminate"),
    ("In Review", "indeterminate"),
    ("Blocked", "indeterminate"),
    ("Done", "done"),
    ("Cancelled", "done"),
]
PRIORITIES = ["Lowest", "Low", "Medium", "High", "Highest"]
ASSIGNEES = [
    "Anna Kowalska", "Bartek Nowak", "Chloé Martin", "Daniel O'Brien",
    "Eva Schmidt", "Felipe Costa", "Grace Liu", "Hiro Tanaka",
    "Iwona Lewandowska", "Jakub Wiśniewski",
]
REPORTERS = ASSIGNEES + ["Product Owner", "QA Lead", "SRE On-call"]
COMPONENTS = {
    "PROJ": ["frontend", "backend", "api", "auth", "billing", "analytics"],
    "OPS": ["k8s", "ci-cd", "monitoring", "networking", "security", "db"],
}
LABEL_POOL = [
    "tech-debt", "needs-design", "spike", "customer-request", "p1",
    "performance", "security", "ux", "ci", "flaky", "regression",
    "refactor", "documentation", "Q1", "Q2",
]
LINK_TYPES = [
    ("Blocks", "is blocked by", "blocks"),
    ("Relates", "relates to", "relates to"),
    ("Duplicate", "is duplicated by", "duplicates"),
    ("Cloners", "is cloned by", "clones"),
]

EPIC_TITLES = {
    "PROJ": [
        "Multi-tenant Workspace",
        "Realtime Collaboration",
        "Self-serve Onboarding",
        "Billing v2",
        "Mobile Companion App",
    ],
    "OPS": [
        "Kubernetes Migration",
        "Observability Overhaul",
        "Zero-Downtime Deploys",
        "Compliance: SOC 2 Type II",
    ],
}

STORY_TEMPLATES = [
    "As a {role}, I want to {action} so that {benefit}",
    "Allow {role} to {action}",
    "Improve {area}: {action}",
    "Refactor {area} for {benefit}",
    "Add {feature} to {area}",
    "Investigate {issue} in {area}",
    "Fix {issue} affecting {role}",
]
ROLES = ["admin", "end user", "developer", "support agent", "billing manager", "guest user"]
ACTIONS = [
    "filter results by tag", "export reports as CSV", "invite teammates by email",
    "configure SSO with Okta", "rotate API keys without downtime",
    "see activity history per workspace", "bulk-update statuses",
    "schedule recurring jobs", "preview changes before publish",
    "throttle outbound webhooks",
]
BENEFITS = [
    "I can move faster", "the team has visibility", "we reduce support load",
    "we meet compliance requirements", "we save costs", "users trust the system",
]
AREAS = [
    "search pipeline", "auth flow", "checkout", "notifications service",
    "graph indexer", "rate limiter", "sync engine", "migration scripts",
    "embedding cache", "websocket layer",
]
ISSUES_TXT = [
    "intermittent 502s", "memory leak under load", "stale cache after rollback",
    "race condition in worker pool", "TLS handshake timeouts",
    "duplicate webhook deliveries", "broken pagination on cold cache",
    "drift between primary and replica", "OOM in batch job",
    "slow queries on indexed columns",
]
FEATURES = [
    "audit log", "dark mode", "keyboard shortcuts", "API rate-limit headers",
    "structured logging", "feature flags", "E2E test suite", "PII redaction",
    "OpenTelemetry tracing", "graceful shutdown",
]

DESCRIPTION_TEMPLATES = [
    # Bug/incident style
    "h2. Context\n\n"
    "We noticed {issue} in the {area} affecting {role} across the {env} environment. "
    "Impact started around {date}, correlating with the {release} release. At peak we observed "
    "roughly {error_rate}% error rate on the affected endpoints, with users reporting slow "
    "response times and occasional 5xx errors. Support ticket volume doubled during the "
    "incident window.\n\n"
    "h2. Reproduction steps\n\n"
    "# Open the {area} in a clean session on {env}\n"
    "# Trigger the flow that calls {endpoint}\n"
    "# Apply moderate load (~{qps} req/s sustained for 5 minutes)\n"
    "# Observe latency spike and intermittent {issue}\n\n"
    "h2. Acceptance criteria\n\n"
    "* {issue} reproduced locally with a deterministic test harness\n"
    "* Root cause identified and captured in a short RFC\n"
    "* Regression test added that fails on main before the fix and passes after\n"
    "* Dashboards in Grafana updated so we'd detect this before customers do\n"
    "* Runbook entry in {area} runbook references this ticket\n\n"
    "h2. Technical notes\n\n"
    "Initial investigation points at {suspect}. We should check the latest changes "
    "in {area} that touched the {endpoint} handler. {assignee} already pulled flamegraphs "
    "from {env}; they're attached in the incident channel.\n\n"
    "h2. Links\n\n"
    "* Incident channel: #inc-{key-lower}\n"
    "* Related dashboards: Grafana > {area} > Overview\n"
    "* Previous similar issue: see linked tickets\n\n"
    "*Estimated effort:* {est} story points. Discussed in the {date} sync. Owner: {assignee}.",

    # Product/story style
    "h2. Goal\n\n"
    "Enable {role} to {action}, so that {benefit}. Today this is painful because users "
    "have to work around it by chaining multiple manual steps, which creates support load "
    "and makes the product feel inconsistent.\n\n"
    "h2. User story\n\n"
    "> As a {role},\n"
    "> I want to {action},\n"
    "> so that {benefit}.\n\n"
    "h2. Acceptance criteria\n\n"
    "* The {area} exposes a first-class UI for this action\n"
    "* Feature is gated behind a feature flag `{flag}` rolled out at 5% → 25% → 100%\n"
    "* Empty-state, loading, success and error paths are all covered\n"
    "* Copy reviewed by the product writer and available in English + Polish\n"
    "* Telemetry: at least one success event and one failure event tracked\n\n"
    "h2. Out of scope\n\n"
    "* Mobile parity (tracked separately)\n"
    "* Bulk operations on more than 100 items\n"
    "* Admin-level permissions for this action\n\n"
    "h2. Open questions\n\n"
    "# Do we need an audit trail entry for every use of this action?\n"
    "# Should failure notifications go to the user, the admin, or both?\n"
    "# What's the expected rate limit? Current proposal: {qps} per user per minute.\n\n"
    "h2. Design & references\n\n"
    "* Figma: _{area} v2 → {feature}_ frame\n"
    "* Linked OKR: _Reduce time-to-value for new accounts_\n"
    "* Related RFC: RFC-{rfc_num} ({area} {feature})\n\n"
    "*Estimated effort:* {est} story points. Target sprint: the one after kickoff.",

    # Task/implementation style
    "h2. Summary\n\n"
    "Tracking implementation work for {feature} in the {area}. This is part of the "
    "broader effort to {benefit}. The current implementation is a stop-gap from the "
    "{release} release and needs to be replaced before we onboard the next cohort.\n\n"
    "h2. Plan\n\n"
    "# Audit current behavior and write down the invariants we want to preserve\n"
    "# Draft a short RFC (RFC-{rfc_num}) covering data model, API contract, rollback path\n"
    "# Implement behind the `{flag}` feature flag with a kill switch\n"
    "# Cover new code with unit + integration tests; target ≥ 80% branch coverage\n"
    "# Roll out to the beta cohort (~{beta_pct}% of MAU) for 14 days\n"
    "# GA after 14 days of stability and no new P1 incidents\n\n"
    "h2. Technical design notes\n\n"
    "We considered three approaches:\n\n"
    "|| Option || Pros || Cons || Decision ||\n"
    "| Extend existing {area} | fastest to ship, reuses patterns | couples us to legacy code |  |\n"
    "| Extract a dedicated service | clean seams, independent scaling | infra cost, more on-call |  |\n"
    "| Use a SaaS primitive | least effort | vendor lock-in, PII concerns | rejected |\n\n"
    "Default pick: **extend existing {area}** unless profiling on staging shows we can't hit "
    "the {qps} req/s target with p95 latency under 200ms.\n\n"
    "h2. Risks & mitigations\n\n"
    "* **Data migration:** writes double-written during rollout. Backfill job gated by flag.\n"
    "* **On-call load:** new dashboards + runbook entries land in the same PR as the feature.\n"
    "* **Rollback:** feature flag flip restores old path within seconds.\n\n"
    "*Estimated effort:* {est} story points. Dependencies: platform team's IAM work.",

    # Spike style
    "h2. Spike goal\n\n"
    "Evaluate options for {feature} in the {area} and land with a clear recommendation. "
    "Current pain: {issue} is surfacing in {env} at ~{error_rate}% rate, and ad-hoc fixes "
    "aren't sticking. We need a durable direction before committing engineering time.\n\n"
    "h2. Questions to answer\n\n"
    "# What's the smallest viable change that would reduce {issue} by at least 50%?\n"
    "# Can we reuse something from the {area} or do we need new infra?\n"
    "# What's the operational cost (on-call, observability, cost per request)?\n"
    "# Are there open-source projects we should evaluate before building?\n\n"
    "h2. Options considered\n\n"
    "|| Option || Pros || Cons || Est. effort ||\n"
    "| Build in-house | full control, fits our stack | maintenance cost, longer ship time | {est} pts |\n"
    "| Use OSS ({oss}) | faster to prototype, active community | tuning required, unclear SLAs | {est_small} pts |\n"
    "| SaaS ({saas}) | least upfront effort | vendor lock-in, PII and compliance | {est_xs} pts |\n"
    "| Do nothing | zero cost | pain persists, risk escalates | n/a |\n\n"
    "h2. Validation plan\n\n"
    "* Prototype the top option in a throwaway branch\n"
    "* Run load test at {qps} req/s for 30 minutes on staging\n"
    "* Collect p50/p95/p99 latency and memory + CPU usage\n"
    "* Share findings in the {date} architecture review\n\n"
    "h2. Output\n\n"
    "* Short ADR (architecture decision record) in `/docs/adr/`\n"
    "* Follow-up tickets with sized estimates\n"
    "* If we decide to build, a tracking Epic\n\n"
    "*Time-box:* 3 working days. Owner: {assignee}.",

    # Epic-like cross-cutting task
    "h2. Mission\n\n"
    "Consolidate how {role} interact with {feature} across the {area}. Today the experience "
    "is fragmented because this surface has accumulated 3+ years of ad-hoc additions. "
    "Our goal is a coherent design with clear contracts, measurable adoption, and a migration "
    "path that doesn't leave old integrations stranded.\n\n"
    "h2. Success metrics\n\n"
    "* Adoption: ≥ 40% of active accounts using the new surface within 60 days of GA\n"
    "* Support load: −30% tickets tagged `{area}` within 90 days\n"
    "* Performance: p95 latency on the hot path ≤ 150ms\n"
    "* Reliability: no new P1 incidents attributed to this work in the first two quarters\n\n"
    "h2. Workstreams\n\n"
    "# **API & data model** – new contract, versioning, deprecation policy\n"
    "# **UX** – redesign of the primary flow, empty/loading/error states\n"
    "# **Migration** – dual-write, backfill, cutover, cleanup\n"
    "# **Observability** – dashboards, SLOs, on-call runbook\n"
    "# **Enablement** – docs for internal teams + external API consumers\n\n"
    "h2. Non-goals\n\n"
    "* Rewriting the underlying storage layer\n"
    "* Adding new surface-level features during migration\n"
    "* Mobile parity in phase 1\n\n"
    "h2. Timeline (target)\n\n"
    "* Week 1–2: discovery + RFC-{rfc_num}\n"
    "* Week 3–6: build behind `{flag}` flag\n"
    "* Week 7: internal dogfood\n"
    "* Week 8–9: beta at {beta_pct}% of MAU\n"
    "* Week 10: GA + announcement\n\n"
    "*Estimated effort:* {est} story points total across squads. Primary contact: {assignee}.",
]

COMMENT_BODIES = [
    "Bumping priority — customer escalation came in this morning.",
    "Reproduced locally on commit abc123. Working on a fix in branch fix/{key-lower}.",
    "Tagging {assignee} for review. Looks good apart from the missing test.",
    "Discussed offline. We'll defer this until after the migration.",
    "Pushed a draft PR — would appreciate eyes on the lock acquisition order.",
    "Closing as duplicate of related ticket — same root cause.",
    "Verified in staging. Ready for production rollout.",
    "This is blocked on the platform team finishing the new IAM roles.",
]


def now_utc() -> datetime:
    return datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)


def fmt_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def random_dt(days_back: int) -> datetime:
    offset = timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return now_utc() - offset


def pick_status(issue_type: str) -> tuple[str, str]:
    if issue_type == "Epic":
        # Epics tend to stay open longer
        return random.choices(
            STATUSES, weights=[1, 4, 2, 1, 2, 1], k=1
        )[0]
    return random.choices(STATUSES, weights=[3, 4, 2, 1, 5, 1], k=1)[0]


_ENVS = ["staging", "production", "canary", "eu-west-1", "us-east-1"]
_RELEASES = ["v4.12", "v4.13-rc1", "v5.0-beta", "v5.1", "v5.2-hotfix"]
_SUSPECTS = [
    "a lock ordering change landed two weeks ago",
    "the recently introduced connection-pool tuning",
    "an undocumented assumption about clock monotonicity",
    "the migration job that runs every night at 02:00 UTC",
    "a third-party SDK upgrade that altered retry semantics",
]
_ENDPOINTS = [
    "POST /api/v2/workspaces", "GET /api/v2/search", "POST /api/v1/auth/token",
    "PATCH /api/v2/billing/subscription", "POST /api/v1/webhooks/dispatch",
]
_OSS = ["OpenTelemetry Collector", "LiteFS", "Keda", "Loki", "Temporal", "Vector.dev"]
_SAAS = ["Datadog", "Vercel", "Cloudflare Workers", "Auth0", "Stripe Billing"]


def fill_template(template: str, *, key: str, assignee: str) -> str:
    return template.format(
        role=random.choice(ROLES),
        action=random.choice(ACTIONS),
        benefit=random.choice(BENEFITS),
        area=random.choice(AREAS),
        issue=random.choice(ISSUES_TXT),
        feature=random.choice(FEATURES),
        date=random_dt(30).strftime("%Y-%m-%d"),
        assignee=assignee,
        est=random.choice([3, 5, 8, 13, 21]),
        est_small=random.choice([2, 3, 5]),
        est_xs=random.choice([1, 2, 3]),
        env=random.choice(_ENVS),
        release=random.choice(_RELEASES),
        error_rate=random.choice([0.5, 1.2, 2.4, 4.8, 7.1, 12.5]),
        qps=random.choice([50, 100, 250, 500, 1000, 2500]),
        endpoint=random.choice(_ENDPOINTS),
        suspect=random.choice(_SUSPECTS),
        flag=f"{random.choice(['rollout', 'experiment', 'ff'])}_{key.lower()}",
        rfc_num=random.randint(100, 999),
        beta_pct=random.choice([5, 10, 15, 25]),
        oss=random.choice(_OSS),
        saas=random.choice(_SAAS),
        **{"key-lower": key.lower()},
    )


class IssueData:
    __slots__ = (
        "key", "project_key", "issue_type", "title", "description",
        "status", "status_cat", "priority", "assignee", "reporter",
        "created", "updated", "due", "labels", "components",
        "epic_key", "parent_key", "sprint", "links", "comments",
    )

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def build_issues(total: int) -> list[IssueData]:
    issues: list[IssueData] = []
    counters: dict[str, int] = {p["key"]: 0 for p in PROJECTS}

    def next_key(project_key: str) -> str:
        counters[project_key] += 1
        return f"{project_key}-{counters[project_key]}"

    # 1. Create epics first.
    epics_by_project: dict[str, list[IssueData]] = {p["key"]: [] for p in PROJECTS}
    for proj in PROJECTS:
        for title in EPIC_TITLES[proj["key"]]:
            key = next_key(proj["key"])
            assignee = random.choice(ASSIGNEES)
            status, cat = pick_status("Epic")
            created = random_dt(180)
            epic = IssueData(
                key=key,
                project_key=proj["key"],
                issue_type="Epic",
                title=f"[Epic] {title}",
                description=(
                    f"h2. Goal\n\n"
                    f"Deliver _{title}_ for the *{proj['name']}* area. This epic consolidates the "
                    "cross-team work needed to reach a coherent, measurable outcome. Today the experience "
                    "is fragmented across three teams and two codebases, and there is no single owner "
                    "for the end-to-end user journey. Shipping this as an epic lets us align incentives "
                    "and track progress against a single definition of done.\n\n"
                    "h2. Context\n\n"
                    "Customer research over the last two quarters keeps surfacing the same pain points: "
                    "setup is confusing, the middle of the flow drops users, and the finish state doesn't "
                    "feel rewarding. Support tickets tagged with this area have grown roughly 35% "
                    "quarter-over-quarter, and the NPS for this surface sits 12 points below the product average. "
                    "Existing workarounds rely on internal scripts that we want to retire.\n\n"
                    "h2. Success metrics\n\n"
                    "* Adoption: > 40% of MAU touch the new surface within 60 days of GA\n"
                    "* Reliability: zero P1 incidents attributed to this work during rollout\n"
                    "* Support: −30% tickets tagged with this area 90 days after GA\n"
                    "* Performance: p95 latency on the primary flow stays under 200ms\n"
                    "* Satisfaction: CSAT for this surface improves by at least 10 points\n\n"
                    "h2. Non-goals\n\n"
                    "* Rewriting the underlying storage layer\n"
                    "* Adding unrelated features to the same surface during migration\n"
                    "* Mobile parity in phase 1 — tracked under a separate epic\n\n"
                    "h2. Workstreams\n\n"
                    "# **Discovery & design** – validated prototypes, research debriefs, spec\n"
                    "# **Platform work** – API contract, data model, feature-flag scaffolding\n"
                    "# **UX delivery** – redesigned flows, empty/loading/error states, i18n\n"
                    "# **Migration** – dual-write, backfill job, cutover runbook, cleanup\n"
                    "# **Observability** – dashboards, SLOs, alerting, on-call runbook entry\n"
                    "# **Enablement** – internal docs, external API reference, support FAQ\n\n"
                    "h2. Risks & dependencies\n\n"
                    "* Platform team's IAM roles refactor must land before migration cutover\n"
                    "* Billing team owns one upstream integration that will need a new webhook\n"
                    "* Legal review is on the critical path for any PII handling changes\n"
                    "* Data team needs to backfill 3 historical tables (scheduled, ~2 weeks)\n\n"
                    "h2. Timeline (target)\n\n"
                    "* Week 1–2: discovery, research synthesis, RFC drafting\n"
                    "* Week 3–6: build behind feature flag, internal dogfood\n"
                    "* Week 7–8: beta at 10% → 25% of MAU with guardrail metrics\n"
                    "* Week 9: GA announcement, enablement content published\n"
                    "* Week 10+: deprecate legacy code path, delete dead code\n\n"
                    "Tracked stories and tasks are linked under this epic. Open questions and "
                    "weekly status updates live in the pinned thread in #epic channel."
                ),
                status=status,
                status_cat=cat,
                priority=random.choice(PRIORITIES),
                assignee=assignee,
                reporter=random.choice(REPORTERS),
                created=created,
                updated=created + timedelta(days=random.randint(0, 60)),
                due=created + timedelta(days=random.randint(60, 180)) if random.random() < 0.6 else None,
                labels=random.sample(LABEL_POOL, k=random.randint(1, 3)),
                components=random.sample(COMPONENTS[proj["key"]], k=random.randint(1, 2)),
                epic_key=None,
                parent_key=None,
                sprint=None,
                links=[],
                comments=[],
            )
            issues.append(epic)
            epics_by_project[proj["key"]].append(epic)

    # 2. Generate sprints.
    sprints = []
    for i in range(1, 9):
        start = now_utc() - timedelta(days=14 * (9 - i))
        end = start + timedelta(days=13)
        state = "CLOSED" if i <= 6 else ("ACTIVE" if i == 7 else "FUTURE")
        sprints.append({
            "id": 1000 + i,
            "name": f"Sprint {i} – {start.strftime('%Y-%m-%d')}",
            "state": state,
            "startDate": fmt_iso(start),
            "endDate": fmt_iso(end),
        })

    # 3. Fill remaining issues.
    remaining = total - len(issues)
    for _ in range(remaining):
        proj = random.choice(PROJECTS)
        key = next_key(proj["key"])
        # Subtasks need a parent — only ~10% subtasks, rest stories/tasks/bugs/spikes.
        itype = random.choices(
            ISSUE_TYPES_NON_EPIC,
            weights=[40, 30, 18, 8, 4],
            k=1,
        )[0]

        assignee = random.choice(ASSIGNEES) if random.random() < 0.85 else None
        reporter = random.choice(REPORTERS)
        status, cat = pick_status(itype)
        created = random_dt(150)
        updated = created + timedelta(days=random.randint(0, 90))
        due = updated + timedelta(days=random.randint(7, 60)) if random.random() < 0.3 else None

        # Title.
        template = random.choice(STORY_TEMPLATES)
        title = template.format(
            role=random.choice(ROLES),
            action=random.choice(ACTIONS),
            benefit=random.choice(BENEFITS),
            area=random.choice(AREAS),
            issue=random.choice(ISSUES_TXT),
            feature=random.choice(FEATURES),
        )
        if itype == "Bug":
            title = f"[Bug] {title}"
        elif itype == "Spike":
            title = f"[Spike] {title}"

        description = fill_template(
            random.choice(DESCRIPTION_TEMPLATES),
            key=key,
            assignee=assignee or "the assignee",
        )

        # Epic link (~70% of stories/tasks/bugs/spikes).
        epic_key = None
        if itype != "Sub-task" and epics_by_project[proj["key"]] and random.random() < 0.7:
            epic_key = random.choice(epics_by_project[proj["key"]]).key

        # Parent for sub-tasks.
        parent_key = None
        if itype == "Sub-task":
            candidates = [
                i for i in issues
                if i.project_key == proj["key"] and i.issue_type in {"Story", "Task"}
            ]
            if candidates:
                parent_key = random.choice(candidates).key
            else:
                # Fall back to Task if no parent candidate exists yet.
                itype = "Task"

        # Sprint (~80% have at least one).
        sprint = None
        if random.random() < 0.8:
            sprint = random.choice(sprints)

        labels = random.sample(LABEL_POOL, k=random.randint(0, 4))
        components = random.sample(
            COMPONENTS[proj["key"]],
            k=random.randint(0, 2),
        )

        # Comments.
        comments = []
        for _ in range(random.randint(0, 4)):
            body_template = random.choice(COMMENT_BODIES)
            body = body_template.format(
                assignee=random.choice(ASSIGNEES),
                **{"key-lower": key.lower()},
            )
            comments.append({
                "author": random.choice(REPORTERS),
                "created": created + timedelta(
                    days=random.randint(0, max(1, (updated - created).days))
                ),
                "body": body,
            })

        issues.append(IssueData(
            key=key,
            project_key=proj["key"],
            issue_type=itype,
            title=title,
            description=description,
            status=status,
            status_cat=cat,
            priority=random.choice(PRIORITIES),
            assignee=assignee,
            reporter=reporter,
            created=created,
            updated=updated,
            due=due,
            labels=labels,
            components=components,
            epic_key=epic_key,
            parent_key=parent_key,
            sprint=sprint,
            links=[],
            comments=comments,
        ))

    # 4. Add some cross-issue links.
    non_epics = [i for i in issues if i.issue_type != "Epic"]
    for issue in non_epics:
        if random.random() < 0.35:
            n_links = random.choices([1, 2, 3], weights=[6, 3, 1], k=1)[0]
            for _ in range(n_links):
                target = random.choice(non_epics)
                if target.key == issue.key:
                    continue
                link_name, inward_desc, outward_desc = random.choice(LINK_TYPES)
                # Decide direction: store on issue side as outbound; the
                # parser handles both directions via inward/outward.
                direction = random.choice(["outward", "inward"])
                issue.links.append({
                    "name": link_name,
                    "direction": direction,
                    "description": outward_desc if direction == "outward" else inward_desc,
                    "target_key": target.key,
                })

    return issues


def render_xml(issues: list[IssueData]) -> str:
    def esc(s: str | None) -> str:
        return escape(s or "")

    def render_links(links):
        if not links:
            return ""
        # Group by (name, direction).
        groups: dict[tuple[str, str, str], list[str]] = {}
        for l in links:
            groups.setdefault(
                (l["name"], l["direction"], l["description"]), []
            ).append(l["target_key"])
        out = ["    <issuelinks>"]
        for (name, direction, desc), targets in groups.items():
            out.append(f'      <issuelinktype id="100{abs(hash(name)) % 100}">')
            out.append(f"        <name>{esc(name)}</name>")
            wrapper = "outwardlinks" if direction == "outward" else "inwardlinks"
            out.append(f'        <{wrapper} description="{esc(desc)}">')
            for t in targets:
                out.append(
                    f'          <issuelink><issuekey>{esc(t)}</issuekey></issuelink>'
                )
            out.append(f"        </{wrapper}>")
            out.append("      </issuelinktype>")
        out.append("    </issuelinks>")
        return "\n".join(out)

    def render_comments(comments):
        if not comments:
            return ""
        out = ["    <comments>"]
        for c in comments:
            out.append(
                f'      <comment author="{esc(c["author"])}" '
                f'created="{fmt_iso(c["created"])}">'
                f'{esc(c["body"])}</comment>'
            )
        out.append("    </comments>")
        return "\n".join(out)

    def render_customfields(issue: IssueData):
        rows = ["    <customfields>"]
        if issue.epic_key:
            rows.append(
                '      <customfield id="customfield_10014" '
                'key="com.pyxis.greenhopper.jira:gh-epic-link">'
            )
            rows.append("        <customfieldname>Epic Link</customfieldname>")
            rows.append("        <customfieldvalues>")
            rows.append(
                f"          <customfieldvalue>{esc(issue.epic_key)}</customfieldvalue>"
            )
            rows.append("        </customfieldvalues>")
            rows.append("      </customfield>")
        if issue.sprint:
            sp = issue.sprint
            sprint_blob = (
                "com.atlassian.greenhopper.service.sprint.Sprint@deadbeef"
                f"[id={sp['id']},rapidViewId=1,state={sp['state']},"
                f"name={sp['name']},startDate={sp['startDate']},"
                f"endDate={sp['endDate']},completeDate=,sequence={sp['id']}]"
            )
            rows.append(
                '      <customfield id="customfield_10020" '
                'key="com.atlassian.jira.plugin.system.customfieldtypes:sprint">'
            )
            rows.append("        <customfieldname>Sprint</customfieldname>")
            rows.append("        <customfieldvalues>")
            rows.append(
                f"          <customfieldvalue>{esc(sprint_blob)}</customfieldvalue>"
            )
            rows.append("        </customfieldvalues>")
            rows.append("      </customfield>")
        rows.append("    </customfields>")
        return "\n".join(rows)

    def render_item(issue: IssueData) -> str:
        parts = [
            "  <item>",
            f"    <title>[{esc(issue.key)}] {esc(issue.title)}</title>",
            f"    <link>https://example.atlassian.net/browse/{esc(issue.key)}</link>",
            f'    <project key="{esc(issue.project_key)}" id="100{ord(issue.project_key[0])}">'
            f"{esc(next(p['name'] for p in PROJECTS if p['key'] == issue.project_key))}</project>",
            f"    <key id=\"{abs(hash(issue.key)) % 100000}\">{esc(issue.key)}</key>",
            f"    <summary>{esc(issue.title)}</summary>",
            f"    <type id=\"{abs(hash(issue.issue_type)) % 20}\" "
            f'iconUrl="https://example.atlassian.net/icon-{esc(issue.issue_type)}.svg">'
            f"{esc(issue.issue_type)}</type>",
            f'    <priority id="{PRIORITIES.index(issue.priority) + 1}">'
            f"{esc(issue.priority)}</priority>",
            f"    <status id=\"{abs(hash(issue.status)) % 20}\">{esc(issue.status)}</status>",
            f"    <statusCategory id=\"1\" key=\"{esc(issue.status_cat)}\" "
            f"colorName=\"blue-gray\">{esc(issue.status_cat.title())}</statusCategory>",
            f"    <reporter username=\"{esc(issue.reporter)}\">{esc(issue.reporter)}</reporter>",
            f"    <assignee username=\"{esc(issue.assignee or 'Unassigned')}\">"
            f"{esc(issue.assignee or 'Unassigned')}</assignee>",
            f"    <created>{fmt_iso(issue.created)}</created>",
            f"    <updated>{fmt_iso(issue.updated)}</updated>",
        ]
        if issue.due:
            parts.append(f"    <due>{fmt_iso(issue.due)}</due>")
        parts.append(
            f"    <description>{esc(issue.description)}</description>"
        )
        if issue.parent_key:
            parts.append(
                f"    <parent id=\"{abs(hash(issue.parent_key)) % 100000}\">"
                f"{esc(issue.parent_key)}</parent>"
            )
        if issue.labels:
            parts.append("    <labels>")
            for l in issue.labels:
                parts.append(f"      <label>{esc(l)}</label>")
            parts.append("    </labels>")
        if issue.components:
            for c in issue.components:
                parts.append(f"    <component>{esc(c)}</component>")
        cf = render_customfields(issue)
        if cf:
            parts.append(cf)
        links_xml = render_links(issue.links)
        if links_xml:
            parts.append(links_xml)
        comments_xml = render_comments(issue.comments)
        if comments_xml:
            parts.append(comments_xml)
        parts.append("  </item>")
        return "\n".join(parts)

    header = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<rss version=\"0.92\">\n"
        "<channel>\n"
        "  <title>Your Company JIRA</title>\n"
        "  <link>https://example.atlassian.net</link>\n"
        "  <description>An XML representation of a search request</description>\n"
        "  <language>en-us</language>\n"
        f"  <build-info><version>1001.0.0-SNAPSHOT</version>"
        f"<build-number>100279</build-number>"
        f"<build-date>{now_utc().strftime('%d-%m-%Y')}</build-date></build-info>\n"
    )
    body = "\n".join(render_item(i) for i in issues)
    footer = "\n</channel>\n</rss>\n"
    return header + body + footer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        nargs="?",
        default="backend/tests/fixtures/jira/large-export.xml",
        help="Output XML path (default: backend/tests/fixtures/jira/large-export.xml)",
    )
    parser.add_argument(
        "--issues",
        type=int,
        default=120,
        help="Total number of issues to generate (default: 120)",
    )
    args = parser.parse_args()

    issues = build_issues(args.issues)
    xml = render_xml(issues)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml, encoding="utf-8")

    counts: dict[str, int] = {}
    for i in issues:
        counts[i.issue_type] = counts.get(i.issue_type, 0) + 1
    proj_counts: dict[str, int] = {}
    for i in issues:
        proj_counts[i.project_key] = proj_counts.get(i.project_key, 0) + 1
    link_total = sum(len(i.links) for i in issues)
    comment_total = sum(len(i.comments) for i in issues)

    print(f"Wrote {out} ({out.stat().st_size / 1024:.1f} KB)")
    print(f"  Total issues: {len(issues)}")
    print(f"  By type:      {counts}")
    print(f"  By project:   {proj_counts}")
    print(f"  Links:        {link_total}")
    print(f"  Comments:     {comment_total}")


if __name__ == "__main__":
    main()
