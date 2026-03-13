"""
analysis/velocity_engine.py
Motor de velocidad y tendencias.

Agrupa story points completados por sprint (o por semana si no hay sprints).
Calcula rolling average, trend y burn rate.
Genera velocity_data.json.
"""

import json
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

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


def _determine_trend(values):
    """Determina tendencia: improving, stable, declining."""
    if len(values) < 2:
        return "insufficient_data"
    recent = values[-2:]
    earlier = values[:-2] if len(values) > 2 else values[:1]
    avg_recent = sum(recent) / len(recent)
    avg_earlier = sum(earlier) / len(earlier)
    if avg_earlier == 0:
        return "stable"
    ratio = avg_recent / avg_earlier
    if ratio >= 1.15:
        return "improving"
    elif ratio <= 0.85:
        return "declining"
    return "stable"


def _group_by_sprint(issues):
    """Agrupa issues por sprint name."""
    by_sprint = defaultdict(lambda: {"committed": 0, "completed": 0, "issues": 0, "done": 0})
    for issue in issues:
        sprint = issue.get("sprint")
        if not sprint:
            continue
        sprint_name = sprint.get("name", "Sin Sprint") if isinstance(sprint, dict) else str(sprint)
        points = issue.get("story_points") or 0
        by_sprint[sprint_name]["committed"] += points
        by_sprint[sprint_name]["issues"] += 1
        if issue.get("status_category") == "Done":
            by_sprint[sprint_name]["completed"] += points
            by_sprint[sprint_name]["done"] += 1
    return dict(by_sprint)


def _group_by_week(issues):
    """Agrupa issues por semana (fallback si no hay sprints)."""
    by_week = defaultdict(lambda: {"committed": 0, "completed": 0, "issues": 0, "done": 0})
    for issue in issues:
        date_str = issue.get("resolved") or issue.get("updated") or issue.get("created")
        if not date_str:
            continue
        try:
            d = datetime.strptime(date_str[:10], "%Y-%m-%d")
            week_start = d - timedelta(days=d.weekday())
            week_key = week_start.strftime("Sem %Y-%m-%d")
        except ValueError:
            continue
        points = issue.get("story_points") or 0
        by_week[week_key]["committed"] += points
        by_week[week_key]["issues"] += 1
        if issue.get("status_category") == "Done":
            by_week[week_key]["completed"] += points
            by_week[week_key]["done"] += 1
    return dict(by_week)


def run() -> dict:
    print("📉 Calculando velocidad y tendencias...")
    config = load_config()
    jira_data = load_json("jira_data.json")
    team_data = load_json("team_raw.json")

    issues = jira_data.get("issues", [])
    team = team_data.get("team", [])

    from analysis.identity_resolver import load_resolver
    resolver = load_resolver()

    # Agrupar por sprint o por semana
    sprint_data = _group_by_sprint(issues)
    has_sprints = len(sprint_data) > 0

    if has_sprints:
        periods = sprint_data
        period_type = "sprint"
    else:
        periods = _group_by_week(issues)
        period_type = "week"

    # Velocity del equipo
    period_list = []
    completed_values = []
    for name, data in sorted(periods.items()):
        completion_rate = round(
            (data["completed"] / data["committed"] * 100) if data["committed"] > 0 else 0, 1
        )
        period_list.append({
            "name": name,
            "committed": data["committed"],
            "completed": data["completed"],
            "issues_total": data["issues"],
            "issues_done": data["done"],
            "completion_rate": completion_rate,
        })
        completed_values.append(data["completed"])

    avg_velocity = round(sum(completed_values) / len(completed_values), 1) if completed_values else 0
    trend = _determine_trend(completed_values)

    # Velocity por persona
    by_member = {}
    issues_by_member = defaultdict(list)
    for issue in issues:
        mid = resolver.resolve_jira(
            assignee_name=issue.get("assignee"),
            assignee_email=issue.get("assignee_email")
        )
        if mid:
            issues_by_member[mid].append(issue)

    for member in team:
        mid = member["id"]
        m_issues = issues_by_member.get(mid, [])
        if not m_issues:
            by_member[mid] = {
                "name": member["name"],
                "periods": [],
                "avg_velocity": 0,
                "trend": "insufficient_data",
            }
            continue

        if has_sprints:
            m_periods = _group_by_sprint(m_issues)
        else:
            m_periods = _group_by_week(m_issues)

        m_period_list = []
        m_completed = []
        for name, data in sorted(m_periods.items()):
            m_period_list.append({
                "name": name,
                "committed": data["committed"],
                "completed": data["completed"],
            })
            m_completed.append(data["completed"])

        by_member[mid] = {
            "name": member["name"],
            "periods": m_period_list,
            "avg_velocity": round(sum(m_completed) / len(m_completed), 1) if m_completed else 0,
            "trend": _determine_trend(m_completed),
        }

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "period_type": period_type,
        "team_velocity": {
            "periods": period_list,
            "avg_velocity": avg_velocity,
            "trend": trend,
            "total_periods": len(period_list),
        },
        "by_member": by_member,
    }

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "velocity_data.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Velocidad calculada → {out_file}")
    print(f"     Tipo: {period_type} | {len(period_list)} períodos | Avg: {avg_velocity} pts | Trend: {trend}")

    return output


if __name__ == "__main__":
    run()
