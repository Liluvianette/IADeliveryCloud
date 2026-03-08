"""
ingestion/team_loader.py
Carga, valida y normaliza el archivo data/team.yml.
Genera la base de datos interna del equipo usada por los motores de análisis.
"""

import yaml
import json
from pathlib import Path
from datetime import datetime


CONFIG_PATH = Path(__file__).parent.parent / "config.yml"
TEAM_PATH   = Path(__file__).parent.parent / "data" / "team.yml"
OUTPUT_PATH = Path(__file__).parent.parent / "output"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def load_team() -> list[dict]:
    with open(TEAM_PATH, "r") as f:
        raw = yaml.safe_load(f)
    return raw.get("team", [])


def calculate_available_hours(member: dict, config: dict) -> float:
    """Calcula horas reales disponibles descontando buffer y disponibilidad."""
    base_hours     = member["capacity"]["hours_per_month"]
    availability   = member["capacity"]["availability_percent"] / 100
    buffer         = config["team"]["capacity_buffer"]
    on_leave       = member["capacity"].get("on_leave", False)

    if on_leave:
        return 0.0

    return round(base_hours * availability * (1 - buffer), 1)


def validate_member(member: dict) -> list[str]:
    """Retorna lista de errores de validación."""
    errors = []
    required = ["id", "name", "role", "capacity", "skills"]
    for field in required:
        if field not in member:
            errors.append(f"Campo requerido ausente: '{field}'")

    cap = member.get("capacity", {})
    if cap.get("hours_per_month", 0) <= 0:
        errors.append("hours_per_month debe ser > 0")
    if not (0 <= cap.get("availability_percent", 0) <= 100):
        errors.append("availability_percent debe estar entre 0 y 100")

    return errors


def normalize_team(raw_team: list[dict], config: dict) -> list[dict]:
    """Normaliza y enriquece cada miembro con métricas calculadas."""
    normalized = []

    for member in raw_team:
        if not member.get("active", True):
            continue

        errors = validate_member(member)
        if errors:
            print(f"  ⚠️  {member.get('id', '?')} tiene errores: {errors}")
            continue

        available_hours = calculate_available_hours(member, config)

        normalized.append({
            "id":               member["id"],
            "name":             member["name"],
            "role":             member["role"],
            "seniority":        member.get("seniority", "unknown"),
            "email":            member.get("email", ""),
            "active":           member.get("active", True),
            "on_leave":         member["capacity"].get("on_leave", False),
            "capacity": {
                "hours_per_month":      member["capacity"]["hours_per_month"],
                "availability_percent": member["capacity"]["availability_percent"],
                "available_hours":      available_hours,
            },
            "skills":           member.get("skills", {}),
            "velocity": {
                "avg_story_points_per_sprint": member.get("velocity", {}).get("avg_story_points_per_sprint", 0),
                "avg_tasks_per_month":         member.get("velocity", {}).get("avg_tasks_per_month", 0),
                "historical_accuracy":         member.get("velocity", {}).get("historical_accuracy", 0.75),
            },
            "notes":            member.get("notes", ""),
            # Campos que el capacity_engine llenará
            "allocated_hours":  0.0,
            "free_hours":       available_hours,
            "load_percent":     0.0,
            "projects":         [],
        })

    return normalized


def run() -> list[dict]:
    print("📥 Cargando equipo...")
    config = load_config()
    raw    = load_team()
    team   = normalize_team(raw, config)

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "team_raw.json"
    with open(out_file, "w") as f:
        json.dump({
            "generated_at": datetime.utcnow().isoformat(),
            "total_members": len(team),
            "team": team
        }, f, indent=2, ensure_ascii=False)

    print(f"  ✅ {len(team)} miembros cargados → {out_file}")
    return team


if __name__ == "__main__":
    run()


def export_projects_raw():
    """Exporta projects.yml como JSON para consumo del dashboard."""
    import json, yaml
    from pathlib import Path
    from datetime import datetime

    proj_path = Path(__file__).parent.parent / "data" / "projects.yml"
    out_path  = Path(__file__).parent.parent / "output"

    with open(proj_path) as f:
        data = yaml.safe_load(f)

    out_path.mkdir(exist_ok=True)
    with open(out_path / "projects_raw.json", "w") as f:
        json.dump({
            "generated_at": datetime.utcnow().isoformat(),
            "projects": data.get("projects", [])
        }, f, indent=2, ensure_ascii=False)
    print("  ✅ projects_raw.json generado")
