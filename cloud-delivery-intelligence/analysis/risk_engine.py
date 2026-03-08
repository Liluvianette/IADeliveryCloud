"""
analysis/risk_engine.py
Detecta riesgos en el equipo y proyectos.

Detecta:
- Single points of failure (SPOF) por skill
- Personas sobrecargadas
- Proyectos críticos sin backup
- Brechas de habilidades
- Proyectos sin líder disponible
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from collections import defaultdict


CONFIG_PATH   = Path(__file__).parent.parent / "config.yml"
PROJECTS_PATH = Path(__file__).parent.parent / "data" / "projects.yml"
OUTPUT_PATH   = Path(__file__).parent.parent / "output"


RISK_WEIGHTS = {
    "spof_critico":        10,
    "sobrecarga_critica":   9,
    "proyecto_sin_backup":  8,
    "sobrecarga_alta":      7,
    "brecha_skill":         6,
    "lider_sobrecargado":   5,
    "proyecto_riesgo":      4,
    "underload":            2,
}


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_projects():
    with open(PROJECTS_PATH) as f:
        return yaml.safe_load(f).get("projects", [])


def load_capacity():
    with open(OUTPUT_PATH / "team_capacity.json") as f:
        return json.load(f)


def detect_spof(team: list[dict], projects: list[dict]) -> list[dict]:
    """
    Detecta habilidades donde solo una persona del equipo tiene nivel avanzado (>=3).
    Si esa persona está sobrecargada o ausente: riesgo crítico.
    """
    risks = []
    skill_experts = defaultdict(list)

    for m in team:
        for skill, level in m.get("skills", {}).items():
            if level >= 3:
                skill_experts[skill].append({
                    "id":     m["id"],
                    "name":   m["name"],
                    "level":  level,
                    "load":   m.get("load_percent", 0),
                    "status": m.get("load_status", "unknown"),
                })

    for skill, experts in skill_experts.items():
        if len(experts) == 1:
            expert      = experts[0]
            is_critical = any(
                skill in p.get("required_skills", [])
                for p in projects if p["status"] == "activo"
            )
            severity = "critica" if is_critical else "media"
            risks.append({
                "type":        "spof",
                "severity":    severity,
                "weight":      RISK_WEIGHTS["spof_critico"] if is_critical else 5,
                "skill":       skill,
                "expert":      expert["name"],
                "load_status": expert["status"],
                "description": f"Solo {expert['name']} tiene expertise en '{skill}' (nivel {expert['level']}). " +
                               ("Usada en proyectos críticos activos." if is_critical else ""),
                "recommendation": f"Planificar knowledge transfer de '{skill}' a al menos un miembro más del equipo.",
            })

    return risks


def detect_overloads(team: list[dict]) -> list[dict]:
    """Detecta personas sobrecargadas."""
    risks = []
    for m in team:
        status = m.get("load_status", "normal")
        if status == "critico":
            risks.append({
                "type":        "sobrecarga",
                "severity":    "critica",
                "weight":      RISK_WEIGHTS["sobrecarga_critica"],
                "member":      m["name"],
                "load_percent": m["load_percent"],
                "description": f"{m['name']} tiene carga del {m['load_percent']*100:.0f}% — supera capacidad real.",
                "recommendation": "Reasignar tareas o posponer proyecto de menor severidad.",
            })
        elif status == "sobrecargado":
            risks.append({
                "type":        "sobrecarga",
                "severity":    "alta",
                "weight":      RISK_WEIGHTS["sobrecarga_alta"],
                "member":      m["name"],
                "load_percent": m["load_percent"],
                "description": f"{m['name']} tiene carga del {m['load_percent']*100:.0f}% — cerca del límite.",
                "recommendation": "Monitorear semanalmente. No asignar nuevos proyectos sin liberar carga.",
            })
    return risks


def detect_project_risks(projects: list[dict], team: list[dict]) -> list[dict]:
    """Detecta proyectos críticos con pocos integrantes o líderes sobrecargados."""
    risks    = []
    team_map = {m["id"]: m for m in team}

    for p in projects:
        if p["status"] != "activo":
            continue

        assignments = p.get("team_assignments", [])

        # Proyecto crítico con solo 1 persona
        if p["severity"] in ("critica", "alta") and len(assignments) == 1:
            risks.append({
                "type":        "proyecto_sin_backup",
                "severity":    "alta",
                "weight":      RISK_WEIGHTS["proyecto_sin_backup"],
                "project":     p["name"],
                "description": f"Proyecto '{p['name']}' (severidad {p['severity']}) tiene solo 1 persona asignada.",
                "recommendation": "Asignar al menos un segundo miembro para reducir riesgo de continuidad.",
            })

        # Líder sobrecargado
        lead_id = p.get("devops_lead")
        if lead_id and lead_id in team_map:
            lead = team_map[lead_id]
            if lead.get("load_status") in ("critico", "sobrecargado"):
                risks.append({
                    "type":        "lider_sobrecargado",
                    "severity":    "media",
                    "weight":      RISK_WEIGHTS["lider_sobrecargado"],
                    "project":     p["name"],
                    "lead":        lead["name"],
                    "description": f"El líder de '{p['name']}' ({lead['name']}) está sobrecargado ({lead['load_percent']*100:.0f}%).",
                    "recommendation": "Delegar responsabilidades de liderazgo o reducir carga del líder.",
                })

        # Riesgos declarados en el proyecto
        for risk_text in p.get("risks", []):
            risks.append({
                "type":        "riesgo_proyecto",
                "severity":    "media",
                "weight":      RISK_WEIGHTS["proyecto_riesgo"],
                "project":     p["name"],
                "description": risk_text,
                "recommendation": "Revisar mitigación con el equipo en próxima retro.",
            })

    return risks


def calculate_health_score(risks: list[dict]) -> dict:
    """
    Calcula un score de salud del equipo de 0 a 100.
    100 = equipo perfectamente saludable.
    """
    max_score     = 100
    total_penalty = sum(r["weight"] for r in risks)
    score         = max(0, max_score - total_penalty)

    if score >= 80:
        label = "saludable"
    elif score >= 60:
        label = "estable"
    elif score >= 40:
        label = "en riesgo"
    else:
        label = "crítico"

    return {"score": score, "label": label, "total_risks": len(risks)}


def run() -> dict:
    print("⚙️  Analizando riesgos y salud del equipo...")
    config   = load_config()
    projects = load_projects()
    capacity = load_capacity()
    team     = capacity["team"]

    risks = []
    risks += detect_spof(team, projects)
    risks += detect_overloads(team)
    risks += detect_project_risks(projects, team)

    # Ordenar por peso (más críticos primero)
    risks.sort(key=lambda r: r["weight"], reverse=True)

    health = calculate_health_score(risks)

    # Resumen por severidad
    by_severity = {"critica": 0, "alta": 0, "media": 0, "baja": 0}
    for r in risks:
        sev = r.get("severity", "baja")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    output = {
        "generated_at":  datetime.utcnow().isoformat(),
        "health_score":  health,
        "risks_by_severity": by_severity,
        "total_risks":   len(risks),
        "risks":         risks,
    }

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "team_health.json"
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✅ {len(risks)} riesgos detectados → {out_file}")
    print(f"     Health Score: {health['score']}/100 ({health['label']})")
    return output


if __name__ == "__main__":
    run()
