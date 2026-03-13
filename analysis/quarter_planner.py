"""
analysis/quarter_planner.py
Genera la tabla de Man-Months (MM) automática por Quarter.

Produce quarter_plan.json con:
- Tabla MM: persona × proyecto → MM asignados
- Resumen del equipo: MM disponibles, asignados, libres
- Indicadores de sobrecarga por persona
"""

import json
import yaml
from pathlib import Path
from datetime import datetime, date

CONFIG_PATH  = Path(__file__).parent.parent / "config.yml"
PROJECTS_PATH = Path(__file__).parent.parent / "data" / "projects.yml"
OUTPUT_PATH  = Path(__file__).parent.parent / "output"

HOURS_PER_MM = 160


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_projects_data():
    with open(PROJECTS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_team():
    with open(OUTPUT_PATH / "team_raw.json", encoding="utf-8") as f:
        return json.load(f)["team"]


def _parse_date(s):
    if isinstance(s, date):
        return s
    return datetime.strptime(s, "%Y-%m-%d").date()


def _months_in_quarter(start, end):
    """Calcula meses entre dos fechas."""
    delta = (end - start).days / 30.44
    return max(0.0, round(delta, 2))


def _months_remaining(q_end):
    """Meses restantes desde hoy hasta fin del Q."""
    today = date.today()
    if today >= q_end:
        return 0.0
    delta = (q_end - today).days / 30.44
    return max(0.0, round(delta, 2))


def _sprints_remaining(q_end, cadence_days=14):
    """Sprints restantes desde hoy hasta fin del Q."""
    today = date.today()
    if today >= q_end:
        return 0
    days_left = (q_end - today).days
    return max(0, days_left // cadence_days)


def run() -> dict:
    print("📊 Generando tabla MM del Quarter...")
    config = load_config()
    projects_data = load_projects_data()
    team = load_team()
    projects = projects_data.get("projects", [])

    # Datos del quarter
    quarter_info = projects_data.get("quarters", config.get("quarter", {}))
    q_name = quarter_info.get("current", "Q?")
    q_start = _parse_date(quarter_info.get("start_date", date.today().isoformat()))
    q_end = _parse_date(quarter_info.get("end_date", date.today().isoformat()))
    q_months = _months_in_quarter(q_start, q_end)
    q_months_remaining = _months_remaining(q_end)
    cadence = config.get("sprints", {}).get("cadence_days", 14)
    q_sprints_remaining = _sprints_remaining(q_end, cadence)

    # Construir tabla MM por persona
    mm_table = []
    team_total_available = 0.0
    team_total_allocated = 0.0

    for member in team:
        mid = member["id"]
        cap = member["capacity"]
        on_leave = member.get("on_leave", False)

        # MM disponibles en el Q (restantes)
        if on_leave:
            available_mm = 0.0
        else:
            monthly_hours = cap["hours_per_month"] * (cap["availability_percent"] / 100)
            available_mm = round((monthly_hours * q_months_remaining) / HOURS_PER_MM, 2)

        # Proyectos asignados
        member_projects = []
        allocated_mm_total = 0.0

        for project in projects:
            if project["status"] not in ("activo", "planificado"):
                continue
            for assignment in project.get("team_assignments", []):
                if assignment["member_id"] != mid:
                    continue
                alloc_pct = assignment["allocation_percent"]
                if alloc_pct <= 0:
                    continue
                # MM = allocation% × meses_restantes_Q
                mm = round((alloc_pct / 100) * q_months_remaining, 2)
                member_projects.append({
                    "id": project["id"],
                    "name": project["name"],
                    "type": project.get("type", ""),
                    "severity": project.get("severity", ""),
                    "role": assignment.get("role", ""),
                    "allocation_percent": alloc_pct,
                    "mm": mm,
                })
                allocated_mm_total += mm

        allocated_mm_total = round(allocated_mm_total, 2)
        free_mm = round(max(0.0, available_mm - allocated_mm_total), 2)
        load_pct = round((allocated_mm_total / available_mm * 100), 1) if available_mm > 0 else (999.0 if allocated_mm_total > 0 else 0.0)

        mm_table.append({
            "member_id": mid,
            "name": member["name"],
            "role": member["role"],
            "seniority": member.get("seniority", ""),
            "on_leave": on_leave,
            "available_mm": available_mm,
            "allocated_mm": allocated_mm_total,
            "free_mm": free_mm,
            "load_percent": load_pct,
            "overloaded": load_pct > 100,
            "projects": member_projects,
        })

        team_total_available += available_mm
        team_total_allocated += allocated_mm_total

    team_total_available = round(team_total_available, 2)
    team_total_allocated = round(team_total_allocated, 2)
    team_free = round(max(0.0, team_total_available - team_total_allocated), 2)
    team_load = round((team_total_allocated / team_total_available * 100), 1) if team_total_available > 0 else 0.0

    # Resumen por proyecto
    project_summary = []
    for project in projects:
        if project["status"] not in ("activo", "planificado"):
            continue
        proj_mm = 0.0
        proj_members = []
        for row in mm_table:
            for p in row["projects"]:
                if p["id"] == project["id"]:
                    proj_mm += p["mm"]
                    proj_members.append({"name": row["name"], "role": p["role"], "mm": p["mm"]})
        project_summary.append({
            "id": project["id"],
            "name": project["name"],
            "type": project.get("type", ""),
            "severity": project.get("severity", ""),
            "status": project["status"],
            "total_mm": round(proj_mm, 2),
            "members": proj_members,
        })

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "quarter": {
            "name": q_name,
            "start_date": q_start.isoformat(),
            "end_date": q_end.isoformat(),
            "total_months": q_months,
            "months_remaining": q_months_remaining,
            "sprints_remaining": q_sprints_remaining,
        },
        "mm_table": mm_table,
        "project_summary": project_summary,
        "team_summary": {
            "total_available_mm": team_total_available,
            "total_allocated_mm": team_total_allocated,
            "total_free_mm": team_free,
            "team_load_percent": team_load,
            "can_absorb_new_project": team_free >= 0.25,
            "max_absorbable_mm": team_free,
            "overloaded_count": sum(1 for m in mm_table if m["overloaded"]),
            "on_leave_count": sum(1 for m in mm_table if m["on_leave"]),
        },
    }

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "quarter_plan.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Tabla MM generada → {out_file}")
    print(f"     Quarter: {q_name} | {q_months_remaining} meses restantes | {q_sprints_remaining} sprints")
    print(f"     Equipo: {team_total_allocated} MM asignados / {team_total_available} MM disponibles ({team_load}%)")
    if team_free > 0:
        print(f"     Capacidad libre: {team_free} MM")
    else:
        print(f"     ⚠️  Sin capacidad libre — equipo al {team_load}%")

    return output


if __name__ == "__main__":
    run()
