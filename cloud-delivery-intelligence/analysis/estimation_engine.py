"""
analysis/estimation_engine.py
Calcula estimaciones de esfuerzo para nuevos proyectos basándose en
la velocidad histórica del equipo y perfiles de complejidad.

Genera estimaciones en: horas, story points, man-months.
"""

import json
import yaml
from pathlib import Path
from datetime import datetime


CONFIG_PATH   = Path(__file__).parent.parent / "config.yml"
OUTPUT_PATH   = Path(__file__).parent.parent / "output"


# Factores de complejidad por tipo de proyecto (multiplicador de horas base)
PROJECT_TYPE_FACTORS = {
    "iac":           1.0,
    "desarrollo":    1.2,
    "soporte":       0.8,
    "investigacion": 0.9,
}

# Factores de ajuste por riesgo
RISK_FACTORS = {
    "bajo":   0.9,
    "medio":  1.15,
    "alto":   1.35,
    "critico":1.60,
}

# Actividades estándar con horas base estimadas
ACTIVITY_TEMPLATES = {
    "iac": [
        {"activity": "Discovery técnico y análisis de requisitos",     "base_hours": 16},
        {"activity": "Diseño de arquitectura",                         "base_hours": 24},
        {"activity": "Review de arquitectura (RFC)",                   "base_hours": 8},
        {"activity": "Implementación IaC (Terraform/Ansible)",         "base_hours": 80},
        {"activity": "Configuración de pipelines CI/CD",               "base_hours": 24},
        {"activity": "Testing y validación en ambiente no-prod",       "base_hours": 16},
        {"activity": "Despliegue a producción + cutover",              "base_hours": 16},
        {"activity": "Documentación técnica",                          "base_hours": 16},
        {"activity": "Handoff y knowledge transfer",                   "base_hours": 8},
    ],
    "desarrollo": [
        {"activity": "Discovery y análisis funcional",                 "base_hours": 20},
        {"activity": "Diseño de solución",                             "base_hours": 24},
        {"activity": "Configuración de entornos",                      "base_hours": 16},
        {"activity": "Desarrollo e implementación",                    "base_hours": 120},
        {"activity": "Unit testing + integration testing",             "base_hours": 40},
        {"activity": "Code review y QA",                               "base_hours": 24},
        {"activity": "Despliegue y estabilización",                    "base_hours": 16},
        {"activity": "Documentación y runbook",                        "base_hours": 16},
    ],
    "soporte": [
        {"activity": "Análisis del problema / incident post-mortem",   "base_hours": 8},
        {"activity": "Remediación y fix",                              "base_hours": 24},
        {"activity": "Testing de fix en staging",                      "base_hours": 8},
        {"activity": "Despliegue hotfix",                              "base_hours": 4},
        {"activity": "Documentación del incidente",                    "base_hours": 4},
    ],
    "investigacion": [
        {"activity": "Definición de scope del POC",                    "base_hours": 8},
        {"activity": "Research y benchmarking",                        "base_hours": 24},
        {"activity": "Implementación del POC",                         "base_hours": 40},
        {"activity": "Evaluación de resultados",                       "base_hours": 16},
        {"activity": "Informe de recomendaciones",                     "base_hours": 16},
    ],
}


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_team_capacity():
    with open(OUTPUT_PATH / "team_capacity.json") as f:
        return json.load(f)


def estimate_project(
    project_type: str,
    complexity: str = "medio",
    extra_activities: list[dict] = None,
    team_skills_match: float = 1.0,   # 1.0 = equipo tiene todos los skills, <1 = brecha
) -> dict:
    """
    Genera estimación completa para un proyecto dado su tipo y complejidad.
    
    Args:
        project_type: iac | desarrollo | soporte | investigacion
        complexity:   bajo | medio | alto | critico
        extra_activities: actividades adicionales específicas del proyecto
        team_skills_match: factor de penalización por brecha de habilidades

    Returns:
        dict con actividades, horas y man-months estimados
    """
    type_factor = PROJECT_TYPE_FACTORS.get(project_type, 1.0)
    risk_factor = RISK_FACTORS.get(complexity, 1.0)

    activities = ACTIVITY_TEMPLATES.get(project_type, ACTIVITY_TEMPLATES["iac"]).copy()
    if extra_activities:
        activities += extra_activities

    # Aplicar factores a cada actividad
    for act in activities:
        raw      = act["base_hours"]
        adjusted = raw * type_factor * risk_factor * (1 / team_skills_match)
        act["estimated_hours"]    = round(adjusted, 1)
        act["optimistic_hours"]   = round(adjusted * 0.75, 1)
        act["pessimistic_hours"]  = round(adjusted * 1.35, 1)

    total_hours      = sum(a["estimated_hours"]   for a in activities)
    optimistic_hours = sum(a["optimistic_hours"]  for a in activities)
    pessimistic_hours= sum(a["pessimistic_hours"] for a in activities)

    hours_per_month = 160 * (1 - 0.20)   # con buffer de overhead
    man_months      = round(total_hours / hours_per_month, 2)

    return {
        "project_type":      project_type,
        "complexity":        complexity,
        "type_factor":       type_factor,
        "risk_factor":       risk_factor,
        "activities":        activities,
        "totals": {
            "estimated_hours":    round(total_hours, 1),
            "optimistic_hours":   round(optimistic_hours, 1),
            "pessimistic_hours":  round(pessimistic_hours, 1),
            "man_months":         man_months,
            "man_months_optimistic":   round(optimistic_hours / hours_per_month, 2),
            "man_months_pessimistic":  round(pessimistic_hours / hours_per_month, 2),
        }
    }


def check_team_can_absorb(estimated_hours: float, capacity: dict) -> dict:
    """
    Evalúa si el equipo puede absorber el nuevo proyecto con la capacidad libre.
    """
    free_hours   = capacity["summary"]["total_free_hours"]
    free_months  = capacity["summary"]["estimated_free_manmonths"]
    project_mm   = estimated_hours / (160 * 0.8)

    can_absorb   = free_hours >= estimated_hours
    months_needed= round(project_mm, 2)
    shortfall    = max(0, round(estimated_hours - free_hours, 1))

    if can_absorb:
        recommendation = "El equipo puede absorber el proyecto con la capacidad actual."
    elif shortfall < 40:
        recommendation = f"Faltan ~{shortfall}h. Posible con pequeños ajustes de carga."
    else:
        recommendation = f"Faltan {shortfall}h. Se requiere contratar, extender plazos o reducir alcance."

    return {
        "can_absorb":          can_absorb,
        "free_hours_available":free_hours,
        "hours_required":      estimated_hours,
        "shortfall_hours":     shortfall,
        "months_needed":       months_needed,
        "recommendation":      recommendation,
    }


def run(project_type="iac", complexity="medio") -> dict:
    """Genera un ejemplo de estimación con los parámetros dados."""
    print(f"⚙️  Calculando estimación: tipo={project_type}, complejidad={complexity}...")
    config   = load_config()
    capacity = load_team_capacity()

    estimation = estimate_project(project_type=project_type, complexity=complexity)
    absorption = check_team_can_absorb(estimation["totals"]["estimated_hours"], capacity)

    output = {
        "generated_at":  datetime.utcnow().isoformat(),
        "input": {
            "project_type": project_type,
            "complexity":   complexity,
        },
        "estimation":  estimation,
        "absorption":  absorption,
    }

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "estimation_example.json"
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    total  = estimation["totals"]["estimated_hours"]
    mm     = estimation["totals"]["man_months"]
    absorb = "✅ SÍ puede" if absorption["can_absorb"] else "❌ NO puede"
    print(f"  ✅ Estimación: {total}h = {mm} man-months | {absorb} absorber → {out_file}")
    return output


if __name__ == "__main__":
    run(project_type="iac", complexity="alto")
