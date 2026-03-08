"""
analysis/capacity_engine.py
Motor principal de análisis de capacidad del equipo.

Calcula:
- Horas disponibles vs asignadas por persona
- Carga porcentual por persona y por proyecto
- Capacidad restante del equipo
- Quién puede aceptar trabajo nuevo
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from collections import defaultdict


CONFIG_PATH  = Path(__file__).parent.parent / "config.yml"
PROJECTS_PATH= Path(__file__).parent.parent / "data" / "projects.yml"
OUTPUT_PATH  = Path(__file__).parent.parent / "output"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_projects() -> list[dict]:
    with open(PROJECTS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f).get("projects", [])


def load_team() -> list[dict]:
    team_file = OUTPUT_PATH / "team_raw.json"
    with open(team_file, encoding="utf-8") as f:
        return json.load(f)["team"]


def calculate_allocated_hours(member_id: str, projects: list[dict]) -> tuple[float, list[dict]]:
    """
    Suma todas las horas que un miembro tiene asignadas en proyectos activos.
    Retorna (total_horas_asignadas, lista_de_asignaciones).
    
    allocation_percent indica qué % de su capacidad mensual está en ese proyecto.
    """
    allocations = []
    total = 0.0

    for project in projects:
        if project["status"] not in ("activo", "planificado"):
            continue

        for assignment in project.get("team_assignments", []):
            if assignment["member_id"] != member_id:
                continue

            pct   = assignment["allocation_percent"] / 100
            hours = pct * 160    # 160h base mensuales

            allocations.append({
                "project_id":   project["id"],
                "project_name": project["name"],
                "role":         assignment["role"],
                "allocation_percent": assignment["allocation_percent"],
                "allocated_hours":    round(hours, 1),
            })
            total += hours

    return round(total, 1), allocations


def compute_load_status(load_percent: float, config: dict) -> str:
    """Clasifica el nivel de carga de una persona."""
    overload  = config["team"]["overload_threshold"]
    critical  = config["team"]["critical_threshold"]

    if load_percent >= critical:
        return "critico"
    elif load_percent >= overload:
        return "sobrecargado"
    elif load_percent >= 0.60:
        return "cargado"
    elif load_percent >= 0.30:
        return "normal"
    else:
        return "bajo"


def run() -> dict:
    print("⚙️  Calculando capacidad del equipo...")
    config   = load_config()
    team     = load_team()
    projects = load_projects()

    team_results  = []
    project_loads = defaultdict(lambda: {
        "total_allocated_hours": 0.0,
        "members": []
    })

    for member in team:
        allocated, allocations = calculate_allocated_hours(member["id"], projects)
        available   = member["capacity"]["available_hours"]
        free_hours  = max(0.0, round(available - allocated, 1))
        load_pct    = round(allocated / available, 3) if available > 0 else 1.0
        status      = compute_load_status(load_pct, config)

        member_result = {
            **member,
            "allocated_hours": allocated,
            "free_hours":      free_hours,
            "load_percent":    load_pct,
            "load_status":     status,
            "projects":        allocations,
        }
        team_results.append(member_result)

        for a in allocations:
            pid = a["project_id"]
            project_loads[pid]["total_allocated_hours"] += a["allocated_hours"]
            project_loads[pid]["members"].append({
                "member_id":          member["id"],
                "member_name":        member["name"],
                "role":               a["role"],
                "allocation_percent": a["allocation_percent"],
                "allocated_hours":    a["allocated_hours"],
            })

    # ── Resumen del equipo
    total_available = sum(m["capacity"]["available_hours"] for m in team_results)
    total_allocated = sum(m["allocated_hours"] for m in team_results)
    team_load_pct   = round(total_allocated / total_available, 3) if total_available > 0 else 1.0
    free_capacity   = max(0.0, round(total_available - total_allocated, 1))

    overloaded  = [m["name"] for m in team_results if m["load_status"] in ("critico", "sobrecargado")]
    underloaded = [m["name"] for m in team_results if m["load_status"] == "bajo"]

    summary = {
        "total_available_hours":  round(total_available, 1),
        "total_allocated_hours":  round(total_allocated, 1),
        "total_free_hours":       free_capacity,
        "team_load_percent":      team_load_pct,
        "team_load_status":       compute_load_status(team_load_pct, config),
        "overloaded_members":     overloaded,
        "underloaded_members":    underloaded,
        "can_accept_new_project": free_capacity >= 40,   # al menos 40h libres en el equipo
        "estimated_free_manmonths": round(free_capacity / 160, 2),
    }

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "summary":      summary,
        "team":         team_results,
        "project_loads": dict(project_loads),
    }

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "team_capacity.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Capacidad calculada → {out_file}")
    print(f"     Carga del equipo: {team_load_pct*100:.1f}% | Horas libres: {free_capacity}h")
    if overloaded:
        print(f"  ⚠️  Sobrecargados: {', '.join(overloaded)}")

    return output


if __name__ == "__main__":
    # Requiere team_raw.json (ejecutar team_loader primero)
    from ingestion.team_loader import run as load_team_run
    load_team_run()
    run()