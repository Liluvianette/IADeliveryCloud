"""
analysis/what_if_calculator.py
Simulador "¿Y si meto este proyecto nuevo?"

Evalúa si el equipo puede absorber un proyecto nuevo dados:
- La capacidad actual del equipo (quarter_plan.json)
- Las habilidades requeridas
- El esfuerzo estimado

Genera what_if_result.json con veredicto, impacto y alternativas.
"""

import json
import yaml
from pathlib import Path
from datetime import datetime

CONFIG_PATH   = Path(__file__).parent.parent / "config.yml"
PROJECTS_PATH = Path(__file__).parent.parent / "data" / "projects.yml"
INCOMING_PATH = Path(__file__).parent.parent / "data" / "incoming_project.yml"
OUTPUT_PATH   = Path(__file__).parent.parent / "output"

HOURS_PER_MM = 160


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_quarter_plan():
    with open(OUTPUT_PATH / "quarter_plan.json", encoding="utf-8") as f:
        return json.load(f)


def load_team_capacity():
    with open(OUTPUT_PATH / "team_capacity.json", encoding="utf-8") as f:
        return json.load(f)


def load_incoming_project(path=None):
    p = path or INCOMING_PATH
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _skill_match_score(member_skills, required_skills):
    """Calcula qué tan bien un miembro cubre los skills requeridos (0-100)."""
    if not required_skills:
        return 100
    matched = 0
    for skill in required_skills:
        level = member_skills.get(skill, 0)
        if level >= 3:
            matched += 1.0
        elif level >= 2:
            matched += 0.6
        elif level >= 1:
            matched += 0.3
    return round((matched / len(required_skills)) * 100, 1)


def _find_best_fit_members(quarter_plan, capacity_data, required_skills):
    """Encuentra los miembros más adecuados para el proyecto."""
    team_cap = {m["id"]: m for m in capacity_data["team"]}
    results = []

    for row in quarter_plan["mm_table"]:
        mid = row["member_id"]
        if row["on_leave"]:
            continue
        cap_member = team_cap.get(mid, {})
        skills = cap_member.get("skills", {})
        score = _skill_match_score(skills, required_skills)

        results.append({
            "id": mid,
            "name": row["name"],
            "role": row["role"],
            "seniority": row.get("seniority", ""),
            "skill_match": score,
            "current_load_pct": row["load_percent"],
            "free_mm": row["free_mm"],
            "available_mm": row["available_mm"],
        })

    # Ordenar por skill match (desc), luego por free_mm (desc)
    results.sort(key=lambda x: (-x["skill_match"], -x["free_mm"]))
    return results


def _generate_alternatives(quarter_plan, project_mm, required_skills):
    """Genera alternativas si el proyecto no cabe."""
    alternatives = []
    projects_data = quarter_plan.get("project_summary", [])

    # Alternativa 1: Posponer proyectos de baja severidad
    low_priority = [p for p in projects_data
                    if p["severity"] in ("baja", "media") and p["status"] == "activo"]
    for lp in low_priority:
        if lp["total_mm"] >= 0.25:
            alternatives.append(
                f"Posponer '{lp['name']}' (severidad {lp['severity']}) "
                f"→ libera {lp['total_mm']} MM"
            )

    # Alternativa 2: Contratar recurso temporal
    alternatives.append(
        f"Contratar recurso temporal ({project_mm} MM) para cubrir el proyecto"
    )

    # Alternativa 3: Iniciar en próximo Q
    q_name = quarter_plan["quarter"]["name"]
    # Generar nombre del próximo Q
    try:
        parts = q_name.split("-")
        q_num = int(parts[0][1])
        year = int(parts[1])
        if q_num >= 4:
            next_q = f"Q1-{year + 1}"
        else:
            next_q = f"Q{q_num + 1}-{year}"
    except (ValueError, IndexError):
        next_q = "siguiente Quarter"
    alternatives.append(f"Iniciar en {next_q} cuando termine algún proyecto activo")

    # Alternativa 4: Reducir alcance
    alternatives.append(
        f"Reducir alcance a {round(project_mm * 0.5, 2)} MM "
        f"(MVP con las actividades más críticas)"
    )

    return alternatives


def calculate_what_if(incoming, quarter_plan=None, capacity_data=None):
    """
    Ejecuta la simulación what-if para un proyecto nuevo.

    Args:
        incoming: dict con name, type, estimated_effort_hours, required_skills, activities
        quarter_plan: datos del quarter (se carga si no se pasa)
        capacity_data: datos de capacidad (se carga si no se pasa)
    """
    if quarter_plan is None:
        quarter_plan = load_quarter_plan()
    if capacity_data is None:
        capacity_data = load_team_capacity()

    project_name = incoming.get("name", "Proyecto Nuevo")
    project_type = incoming.get("type", "iac")
    severity = incoming.get("severity", "media")
    required_skills = incoming.get("required_skills", [])

    # Calcular esfuerzo total
    activities = incoming.get("activities", [])
    if activities:
        total_hours = sum(a.get("hours", 0) for a in activities)
    else:
        total_hours = incoming.get("estimated_effort_hours", 0)

    project_mm = round(total_hours / HOURS_PER_MM, 2)

    # Estado actual del equipo
    team_summary = quarter_plan["team_summary"]
    free_mm = team_summary["total_free_mm"]
    current_load = team_summary["team_load_percent"]
    overloaded_now = team_summary["overloaded_count"]

    # Veredicto
    if free_mm >= project_mm:
        verdict = "VIABLE"
        reason = f"Equipo tiene {free_mm} MM libres — suficiente para {project_mm} MM"
    elif free_mm >= project_mm * 0.5:
        verdict = "CONDICIONAL"
        reason = (f"Equipo tiene {free_mm} MM libres pero necesita {project_mm} MM. "
                  f"Posible con ajustes de carga o alcance reducido.")
    else:
        verdict = "NO VIABLE"
        reason = (f"Equipo al {current_load}% — solo {free_mm} MM libres, "
                  f"necesita {project_mm} MM")

    # Best fit members
    best_fit = _find_best_fit_members(quarter_plan, capacity_data, required_skills)

    # Calcular impacto si se agrega
    new_allocated = team_summary["total_allocated_mm"] + project_mm
    new_load = round((new_allocated / team_summary["total_available_mm"]) * 100, 1) if team_summary["total_available_mm"] > 0 else 999.0

    # Simular asignación a best-fit members
    best_fit_with_impact = []
    remaining_mm = project_mm
    for member in best_fit:
        if remaining_mm <= 0:
            break
        assignable = min(member["free_mm"], remaining_mm)
        if assignable <= 0 and member["skill_match"] < 50:
            continue
        new_member_load = member["current_load_pct"] + (
            (assignable / member["available_mm"] * 100) if member["available_mm"] > 0 else 0
        )
        best_fit_with_impact.append({
            **member,
            "assignable_mm": round(assignable, 2),
            "load_if_added": round(new_member_load, 1),
        })
        remaining_mm -= assignable

    # Alternativas
    alternatives = []
    if verdict != "VIABLE":
        alternatives = _generate_alternatives(quarter_plan, project_mm, required_skills)

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "incoming_project": {
            "name": project_name,
            "type": project_type,
            "severity": severity,
            "total_hours": total_hours,
            "total_mm": project_mm,
            "required_skills": required_skills,
            "activities": activities,
        },
        "verdict": verdict,
        "reason": reason,
        "best_fit_members": best_fit_with_impact[:5],
        "impact_on_team": {
            "before": {
                "team_load_pct": current_load,
                "allocated_mm": team_summary["total_allocated_mm"],
                "free_mm": free_mm,
                "overloaded_count": overloaded_now,
            },
            "after": {
                "team_load_pct": new_load,
                "allocated_mm": round(new_allocated, 2),
                "free_mm": round(max(0, free_mm - project_mm), 2),
                "overloaded_count": overloaded_now + sum(
                    1 for m in best_fit_with_impact
                    if m.get("load_if_added", 0) > 100 and m["current_load_pct"] <= 100
                ),
            },
        },
        "alternatives": alternatives,
    }


def run(incoming_path=None) -> dict:
    print("🔮 Ejecutando simulación What-If...")

    path = incoming_path or INCOMING_PATH
    if not Path(path).exists():
        print(f"  ⚠️  No se encontró {path}")
        print("  → Crea data/incoming_project.yml con el proyecto a simular")
        return {}

    incoming = load_incoming_project(path)
    result = calculate_what_if(incoming)

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "what_if_result.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    v = result["verdict"]
    mm = result["incoming_project"]["total_mm"]
    name = result["incoming_project"]["name"]
    print(f"  ✅ Simulación completada → {out_file}")
    print(f"     Proyecto: {name} ({mm} MM)")
    print(f"     Veredicto: {v}")
    print(f"     Razón: {result['reason']}")
    if result["alternatives"]:
        print(f"     Alternativas: {len(result['alternatives'])} sugeridas")

    return result


if __name__ == "__main__":
    run()
