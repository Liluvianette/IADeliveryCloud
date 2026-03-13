#!/usr/bin/env python3
"""
run.py — Script maestro de Cloud Delivery Intelligence Platform

Orquesta toda la pipeline de análisis en orden:
  1. Ingestión (equipo, Jira, Git)
  2. Análisis (capacidad, riesgos, skills)
  3. IA (discovery de nuevos proyectos)
  4. Genera todos los JSONs para el dashboard

Uso:
  python run.py                  → pipeline completa
  python run.py --skip-ai        → sin llamada a API de IA
  python run.py --only-capacity  → solo capacidad
  python run.py --only-health    → solo salud del equipo
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def print_header():
    print("\n" + "═" * 60)
    print("  🚀 Cloud Delivery Intelligence Platform")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("═" * 60 + "\n")


def print_step(n: int, title: str):
    print(f"\n── Paso {n}: {title}")
    print("   " + "─" * 40)


def print_done(elapsed: float):
    print(f"\n{'═' * 60}")
    print(f"  ✅ Pipeline completada en {elapsed:.1f}s")
    print(f"  📁 JSONs generados en /output")
    print(f"  🌐 Abre dashboard/index.html en tu navegador")
    print("═" * 60 + "\n")


def run_full_pipeline(skip_ai: bool = False):
    start = time.time()
    print_header()

    # Asegurar que el directorio output existe
    Path("output").mkdir(exist_ok=True)

    # ── Paso 1: Cargar equipo
    print_step(1, "Cargando datos del equipo")
    sys.path.insert(0, str(Path(__file__).parent))
    from ingestion.team_loader import run as team_run
    team_run()

    # ── Paso 2: Ingestión Jira
    print_step(2, "Ingesta de Jira")
    from ingestion.jira_ingest import run as jira_run
    jira_run()

    # ── Paso 3: Ingestión Git
    print_step(3, "Análisis de repositorios Git")
    from ingestion.git_ingest import run as git_run
    git_run()

    # ── Paso 4: Identity resolver
    print_step(4, "Resolución de identidades")
    from analysis.identity_resolver import run as identity_run
    identity_run()

    # ── Paso 5: Motor de capacidad
    print_step(5, "Calculando capacidad del equipo")
    from analysis.capacity_engine import run as capacity_run
    capacity_run()

    # ── Paso 6: Activity Engine
    print_step(6, "Calculando actividad por persona")
    from analysis.activity_engine import run as activity_run
    activity_run()

    # ── Paso 7: Velocity Engine
    print_step(7, "Calculando velocidad y tendencias")
    from analysis.velocity_engine import run as velocity_run
    velocity_run()

    # ── Paso 8: Quarter Planner
    print_step(8, "Generando tabla MM del Quarter")
    from analysis.quarter_planner import run as quarter_run
    quarter_run()

    # ── Paso 9: Motor de riesgos
    print_step(9, "Analizando riesgos y salud del equipo")
    from analysis.risk_engine import run as risk_run
    risk_run()

    # ── Paso 10: Matriz de skills
    print_step(10, "Generando matriz de habilidades")
    from analysis.skills_matrix import run as skills_run
    skills_run()

    # ── Paso 11: Estimación (ejemplo)
    print_step(11, "Calculando estimación de referencia")
    from analysis.estimation_engine import run as estimation_run
    estimation_run(project_type="iac", complexity="medio")

    # ── Paso 12: Discovery con IA (opcional)
    if not skip_ai:
        print_step(12, "Analizando discovery con IA")
        from ai.discovery_analyzer import run as discovery_run
        discovery_run()
    else:
        print_step(12, "Discovery con IA [OMITIDO — --skip-ai]")

    # ── Paso 13: Copiar JSONs al dashboard
    print_step(13, "Sincronizando JSONs al dashboard")
    sync_outputs_to_dashboard()

    # ── Paso 14: Agentes de análisis (automáticos)
    print_step(14, "Ejecutando agentes de análisis")
    run_agents_auto()

    elapsed = time.time() - start
    print_done(elapsed)


def run_agents_auto():
    """
    Ejecuta los 3 agentes automáticos (sin input del usuario) y guarda
    agents_report.json en output/ y dashboard/data/.
    El estimator se omite aquí porque requiere datos de un proyecto concreto.
    """
    import json
    from datetime import datetime
    from agents.capacity_analyst import CapacityAnalyst
    from agents.risk_officer      import RiskOfficer
    from agents.tech_lead         import TechLeadReviewer

    results = {}
    try:
        results["capacity"]  = CapacityAnalyst().run()
        results["risk"]      = RiskOfficer().run()
        results["tech_lead"] = TechLeadReviewer().run()
    except Exception as e:
        print(f"  ⚠️  Agentes omitidos: {e}")
        return

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "verdicts": {k: v.get("verdict") for k, v in results.items()},
        "results":  results,
    }

    out_path  = Path("output") / "agents_report.json"
    dash_path = Path("dashboard") / "data" / "agents_report.json"

    for path in (out_path, dash_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    verdicts = report["verdicts"]
    print(f"  ✅ Agentes ejecutados — capacity: {verdicts.get('capacity')} · "
          f"risk: {verdicts.get('risk')} · tech_lead: {verdicts.get('tech_lead')}")
    print(f"  📄 agents_report.json generado")


def sync_outputs_to_dashboard():
    """
    Copia los JSONs de /output a /dashboard/data/ para que
    GitHub Pages pueda servirlos desde el mismo dominio.
    """
    import shutil
    src  = Path("output")
    dest = Path("dashboard") / "data"
    dest.mkdir(parents=True, exist_ok=True)

    copied = 0
    for json_file in src.glob("*.json"):
        shutil.copy2(json_file, dest / json_file.name)
        copied += 1

    print(f"  ✅ {copied} archivos copiados → dashboard/data/")


def main():
    parser = argparse.ArgumentParser(
        description="Cloud Delivery Intelligence Platform — Runner"
    )
    parser.add_argument("--skip-ai",       action="store_true", help="Omitir análisis de IA")
    parser.add_argument("--only-capacity", action="store_true", help="Solo calcular capacidad")
    parser.add_argument("--only-health",   action="store_true", help="Solo analizar salud del equipo")

    args = parser.parse_args()

    if args.only_capacity:
        print_header()
        sys.path.insert(0, str(Path(__file__).parent))
        from ingestion.team_loader    import run as team_run
        from analysis.capacity_engine import run as cap_run
        team_run()
        cap_run()
        sync_outputs_to_dashboard()

    elif args.only_health:
        print_header()
        sys.path.insert(0, str(Path(__file__).parent))
        from ingestion.team_loader  import run as team_run
        from analysis.capacity_engine import run as cap_run
        from analysis.risk_engine     import run as risk_run
        team_run()
        cap_run()
        risk_run()
        sync_outputs_to_dashboard()

    else:
        run_full_pipeline(skip_ai=args.skip_ai)


if __name__ == "__main__":
    main()
