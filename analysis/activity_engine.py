"""
analysis/activity_engine.py
Motor de actividad real por persona.

Correlaciona datos de Jira + GitHub por miembro del equipo usando
el identity resolver. Genera activity_data.json con:
- Sprint actual: issues en progreso, done, bloqueados
- Actividad GitHub: commits, PRs, reviews
- Planned vs actual (YAML allocation vs real Jira+GitHub activity)
- Blockers detectados
"""

import json
import yaml
from pathlib import Path
from datetime import datetime, timedelta

CONFIG_PATH = Path(__file__).parent.parent / "config.yml"
OUTPUT_PATH = Path(__file__).parent.parent / "output"


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(filename):
    path = OUTPUT_PATH / filename
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _days_since(date_str):
    """Días desde una fecha string hasta hoy."""
    if not date_str:
        return 999
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return (datetime.utcnow() - d).days
    except (ValueError, TypeError):
        return 999


def run() -> dict:
    print("📈 Calculando actividad por persona...")
    config = load_config()
    team_data = load_json("team_raw.json")
    jira_data = load_json("jira_data.json")
    git_data = load_json("git_data.json")
    capacity_data = load_json("team_capacity.json")

    team = team_data.get("team", [])
    issues = jira_data.get("issues", [])
    worklogs = jira_data.get("worklogs", [])
    commits = git_data.get("commits", [])
    pulls = git_data.get("pulls", [])
    reviews = git_data.get("reviews", [])
    cap_team = {m["id"]: m for m in capacity_data.get("team", [])}

    activity_config = config.get("activity", {})
    blocker_days = activity_config.get("blocker_threshold_days", 5)
    commit_hours = activity_config.get("commit_imputed_hours", 0.5)

    # Identity resolver
    from analysis.identity_resolver import load_resolver
    resolver = load_resolver()

    # Indexar issues por persona (via Jira assignee)
    issues_by_member = {}
    for issue in issues:
        mid = resolver.resolve_jira(
            assignee_name=issue.get("assignee"),
            assignee_email=issue.get("assignee_email")
        )
        if mid:
            issues_by_member.setdefault(mid, []).append(issue)

    # Indexar worklogs por persona
    worklogs_by_member = {}
    for wl in worklogs:
        mid = resolver.resolve_jira(
            assignee_name=wl.get("author"),
            assignee_email=wl.get("author_email")
        )
        if mid:
            worklogs_by_member.setdefault(mid, []).append(wl)

    # Indexar commits por persona
    commits_by_member = {}
    for c in commits:
        mid = resolver.resolve_github(login=c.get("login"), email=c.get("email"))
        if mid:
            commits_by_member.setdefault(mid, []).append(c)

    # Indexar PRs por persona
    pulls_by_member = {}
    for p in pulls:
        mid = resolver.resolve_github(login=p.get("author"))
        if mid:
            pulls_by_member.setdefault(mid, []).append(p)

    # Indexar reviews por persona
    reviews_by_member = {}
    for r in reviews:
        mid = resolver.resolve_github(login=r.get("reviewer"))
        if mid:
            reviews_by_member.setdefault(mid, []).append(r)

    # Construir actividad por persona
    members_activity = []

    for member in team:
        mid = member["id"]
        m_issues = issues_by_member.get(mid, [])
        m_worklogs = worklogs_by_member.get(mid, [])
        m_commits = commits_by_member.get(mid, [])
        m_pulls = pulls_by_member.get(mid, [])
        m_reviews = reviews_by_member.get(mid, [])

        # Sprint actual: issues por estado
        in_progress = []
        done = []
        todo = []
        blocked = []

        for issue in m_issues:
            cat = issue.get("status_category", "")
            entry = {
                "key": issue["key"],
                "summary": issue.get("summary", ""),
                "status": issue.get("status", ""),
                "points": issue.get("story_points"),
                "priority": issue.get("priority", ""),
                "updated": issue.get("updated", ""),
                "days_since_update": _days_since(issue.get("updated")),
                "sprint": issue.get("sprint"),
                "time_estimate_hours": issue.get("time_estimate_hours"),
                "time_spent_hours": issue.get("time_spent_hours"),
            }

            if cat == "Done":
                done.append(entry)
            elif cat == "In Progress":
                in_progress.append(entry)
                if entry["days_since_update"] >= blocker_days:
                    blocked.append({
                        **entry,
                        "days_stuck": entry["days_since_update"],
                        "reason": f"Sin movimiento hace {entry['days_since_update']} días",
                    })
            else:
                todo.append(entry)

        points_committed = sum((i.get("points") or 0) for i in m_issues)
        points_completed = sum((i.get("points") or 0) for i in m_issues
                               if i.get("status_category") == "Done")

        # GitHub activity
        prs_open = [
            {"number": p["number"], "title": p["title"], "repo": p["repo"],
             "created_at": p["created_at"], "age_days": _days_since(p["created_at"]),
             "jira_keys": p.get("jira_keys", [])}
            for p in m_pulls if p.get("state") == "open"
        ]
        prs_merged = [p for p in m_pulls if p.get("merged")]
        lead_times = [p["lead_time_hours"] for p in m_pulls
                      if p.get("lead_time_hours") is not None]
        avg_lead_time = round(sum(lead_times) / len(lead_times), 1) if lead_times else None

        recent_commits = sorted(m_commits, key=lambda c: c.get("date", ""), reverse=True)[:5]

        # Planned vs actual
        cap_member = cap_team.get(mid, {})
        planned_hours = cap_member.get("allocated_hours", 0)
        jira_hours = sum(wl.get("time_spent_hours", 0) for wl in m_worklogs)
        git_imputed = len(m_commits) * commit_hours
        actual_hours = round(jira_hours + git_imputed, 1)
        delta_hours = round(actual_hours - planned_hours, 1)

        if planned_hours > 0:
            actual_pct = round((actual_hours / planned_hours) * 100, 1)
            if actual_pct >= 90:
                assessment = "alineado"
            elif actual_pct >= 60:
                assessment = "sub-utilizado"
            else:
                assessment = "muy bajo"
        else:
            actual_pct = 0
            assessment = "sin asignacion" if actual_hours == 0 else "sin plan"

        members_activity.append({
            "member_id": mid,
            "name": member["name"],
            "role": member["role"],
            "on_leave": member.get("on_leave", False),
            "current_sprint": {
                "issues_in_progress": in_progress,
                "issues_done": done,
                "issues_todo": todo,
                "issues_blocked": blocked,
                "points_committed": points_committed,
                "points_completed": points_completed,
                "total_issues": len(m_issues),
            },
            "github_activity": {
                "commits_count": len(m_commits),
                "prs_open": prs_open,
                "prs_merged_count": len(prs_merged),
                "reviews_given": len(m_reviews),
                "avg_pr_lead_time_hours": avg_lead_time,
                "recent_commits": [
                    {"date": c["date"], "message": c["message"], "repo": c["repo"]}
                    for c in recent_commits
                ],
            },
            "planned_vs_actual": {
                "planned_hours": planned_hours,
                "actual_hours": actual_hours,
                "jira_hours": round(jira_hours, 1),
                "git_imputed_hours": round(git_imputed, 1),
                "delta_hours": delta_hours,
                "actual_percent": actual_pct,
                "assessment": assessment,
            },
            "blockers": blocked,
        })

    # Resumen del equipo
    total_blockers = sum(len(m["blockers"]) for m in members_activity)
    total_in_progress = sum(len(m["current_sprint"]["issues_in_progress"]) for m in members_activity)
    oldest_blocker = max(
        (b["days_stuck"] for m in members_activity for b in m["blockers"]),
        default=0
    )

    unresolved = resolver.get_unresolved()

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "team_activity": members_activity,
        "summary": {
            "total_members": len(members_activity),
            "total_issues_in_progress": total_in_progress,
            "total_blockers": total_blockers,
            "oldest_blocker_days": oldest_blocker,
            "members_with_blockers": sum(1 for m in members_activity if m["blockers"]),
        },
        "unresolved_identities": unresolved,
    }

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "activity_data.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Actividad calculada → {out_file}")
    print(f"     {len(members_activity)} miembros | {total_in_progress} issues en progreso | {total_blockers} blockers")
    if unresolved:
        print(f"  ⚠️  Identidades no resueltas: {unresolved}")

    return output


if __name__ == "__main__":
    run()
