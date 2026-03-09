#!/usr/bin/env python3
"""
run_agents.py — Orquestador consolidado de agentes de análisis
Cloud Delivery Intelligence Platform

Ejecuta los agentes de análisis y muestra un resumen consolidado de veredictos.
Guarda los resultados en output/agents_report.json.

Uso:
  python run_agents.py                                       # capacity + risk + tech_lead
  python run_agents.py --quick "Nombre" --type iac           # los 4 agentes (estimator rápido)
  python run_agents.py --with-estimator                      # los 4 agentes (estimator interactivo)
  python run_agents.py --agent capacity                      # solo Capacity Analyst
  python run_agents.py --agent risk --severity critica,alta  # solo Risk Officer con filtro
  python run_agents.py --agent tech_lead --project "X" --hours 200 --skills k8s,tf
  python run_agents.py --agent estimator --quick "X" --type iac --complexity alto --team 3
"""

import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

# Asegurar que el directorio raíz esté en el path para imports
sys.path.insert(0, str(Path(__file__).parent))

# Windows cp1252 no soporta los caracteres Unicode usados en los prints
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


OUTPUT_PATH = Path(__file__).parent / "output"

VERDICT_ICONS = {
    "SALUDABLE":    "🟢",
    "MODERADO":     "🟡",
    "CRÍTICO":      "🔴",
    "BAJO RIESGO":  "🟢",
    "ALTO RIESGO":  "🔴",
    "VIABLE":       "✅",
    "CONDICIONAL":  "⚠️ ",
    "NO VIABLE":    "🚫",
}


# ── Helpers de presentación ────────────────────────────────────────────────

def print_header():
    print("\n" + "═" * 60)
    print("  🤖 Cloud Delivery Intelligence — Agentes de Análisis")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("═" * 60 + "\n")


def print_step(n: int, title: str):
    print(f"\n── Paso {n}: {title}")
    print("   " + "─" * 40)


def print_done(elapsed: float, report_path: Path = None):
    print(f"\n{'═' * 60}")
    print(f"  ✅ Análisis completado en {elapsed:.1f}s")
    if report_path:
        print(f"  📄 Reporte guardado en {report_path}")
    print("═" * 60 + "\n")


def print_consolidated_summary(results: dict):
    """Imprime tabla de veredictos de todos los agentes ejecutados."""
    print("\n" + "═" * 60)
    print("  📋 RESUMEN CONSOLIDADO DE VEREDICTOS")
    print("═" * 60 + "\n")

    agent_labels = {
        "capacity":  "Capacity Analyst",
        "risk":      "Risk Officer",
        "tech_lead": "Tech Lead Reviewer",
        "estimator": "Estimator",
    }

    for key, label in agent_labels.items():
        if key not in results:
            continue
        verdict = results[key].get("verdict", "—")
        icon = VERDICT_ICONS.get(verdict, "❓")
        print(f"  {icon}  {label:<26} {verdict}")

    print(f"\n{'═' * 60}\n")


# ── Guardado de reporte ────────────────────────────────────────────────────

def save_report(results: dict) -> Path:
    """Guarda agents_report.json en output/ y dashboard/data/."""
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "verdicts": {k: v.get("verdict") for k, v in results.items()},
        "results": results,
    }
    out_path  = OUTPUT_PATH / "agents_report.json"
    dash_path = Path(__file__).parent / "dashboard" / "data" / "agents_report.json"

    for path in (out_path, dash_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    return out_path


# ── Ejecución de agentes ───────────────────────────────────────────────────

def run_capacity() -> dict:
    from agents.capacity_analyst import CapacityAnalyst
    agent = CapacityAnalyst()
    result = agent.run()
    agent.print_result(result)
    return result


def run_risk(filter_severity: list = None) -> dict:
    from agents.risk_officer import RiskOfficer
    agent = RiskOfficer()
    result = agent.run(filter_severity=filter_severity)
    agent.print_result(result)
    return result


def run_tech_lead(project_name: str = "Proyecto nuevo",
                  hours: float = 0,
                  skills: list = None) -> dict:
    from agents.tech_lead import TechLeadReviewer
    agent = TechLeadReviewer()
    result = agent.run(
        project_name=project_name,
        new_project_hours=hours,
        required_skills=skills or [],
    )
    agent.print_result(result)
    return result


def run_estimator(quick: str = None, project_type: str = "iac",
                  complexity: str = "medio", team: int = 2,
                  interactive: bool = False) -> dict:
    from agents.estimator import Estimator
    agent = Estimator()

    if quick:
        answers = {
            "project_name": quick,
            "project_type": project_type,
            "complexity":   complexity,
            "team_size":    team,
        }
        result = agent.run(answers=answers, interactive=False)
    else:
        # Modo interactivo
        name = input("\n  Nombre del proyecto para estimación: ").strip() or "Proyecto nuevo"
        result = agent.run(project_name=name, interactive=True)

    agent.print_result(result)
    return result


# ── Modos de ejecución ────────────────────────────────────────────────────

def run_all(quick: str = None, project_type: str = "iac",
            complexity: str = "medio", team: int = 2,
            with_estimator: bool = False) -> dict:
    """Ejecuta los agentes diagnósticos (+ estimator si se pide)."""
    start = time.time()
    print_header()
    results = {}

    try:
        print_step(1, "Capacity Analyst — Distribución de carga")
        results["capacity"] = run_capacity()

        print_step(2, "Risk Officer — Riesgos y mitigación")
        results["risk"] = run_risk()

        print_step(3, "Tech Lead Reviewer — Viabilidad de nuevos proyectos")
        results["tech_lead"] = run_tech_lead()

        if quick or with_estimator:
            print_step(4, "Estimator — Estimación de esfuerzo")
            results["estimator"] = run_estimator(
                quick=quick,
                project_type=project_type,
                complexity=complexity,
                team=team,
            )

    except FileNotFoundError as e:
        print(f"\n  ❌ {e}")
        print("  👉 Ejecuta primero: python run.py --skip-ai\n")
        return {}
    except Exception as e:
        print(f"\n  ❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return {}

    print_consolidated_summary(results)
    report_path = save_report(results)

    elapsed = time.time() - start
    print_done(elapsed, report_path)
    return results


def run_single(agent_name: str, **kwargs):
    """Ejecuta un solo agente."""
    start = time.time()
    print_header()

    try:
        if agent_name == "capacity":
            run_capacity()

        elif agent_name == "risk":
            sev_str = kwargs.get("severity", "")
            filter_sev = [s.strip() for s in sev_str.split(",") if s.strip()] or None
            run_risk(filter_severity=filter_sev)

        elif agent_name == "tech_lead":
            skills_str = kwargs.get("skills", "")
            run_tech_lead(
                project_name=kwargs.get("project", "Proyecto nuevo"),
                hours=float(kwargs.get("hours", 0)),
                skills=[s.strip() for s in skills_str.split(",") if s.strip()],
            )

        elif agent_name == "estimator":
            run_estimator(
                quick=kwargs.get("quick"),
                project_type=kwargs.get("type", "iac"),
                complexity=kwargs.get("complexity", "medio"),
                team=int(kwargs.get("team", 2)),
            )

        else:
            print(f"  ❌ Agente desconocido: '{agent_name}'")
            print("  Opciones válidas: capacity, risk, tech_lead, estimator")
            return

    except FileNotFoundError as e:
        print(f"\n  ❌ {e}")
        print("  👉 Ejecuta primero: python run.py --skip-ai\n")
        return
    except Exception as e:
        print(f"\n  ❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return

    elapsed = time.time() - start
    print_done(elapsed)


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Cloud Delivery Intelligence — Orquestador de Agentes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python run_agents.py                                       # 3 agentes automáticos
  python run_agents.py --quick "API Gateway" --type iac      # 4 agentes, estimator rápido
  python run_agents.py --with-estimator                      # 4 agentes, estimator interactivo
  python run_agents.py --agent capacity
  python run_agents.py --agent risk --severity critica,alta
  python run_agents.py --agent tech_lead --project "X" --hours 200 --skills k8s,tf
  python run_agents.py --agent estimator --quick "X" --type desarrollo --complexity alto --team 3
        """,
    )

    # Selección de agente único
    parser.add_argument(
        "--agent", "-a",
        choices=["capacity", "risk", "tech_lead", "estimator"],
        help="Ejecutar solo este agente",
    )

    # Flags para Risk Officer
    parser.add_argument(
        "--severity", "-s", default="",
        help="[risk] Filtrar severidades: critica,alta,media,baja",
    )

    # Flags para Tech Lead
    parser.add_argument("--project", "-p", default="Proyecto nuevo",
                        help="[tech_lead] Nombre del proyecto a evaluar")
    parser.add_argument("--hours", "-H", type=float, default=0,
                        help="[tech_lead] Horas estimadas del proyecto")
    parser.add_argument("--skills", default="",
                        help="[tech_lead] Skills requeridos: skill1,skill2")

    # Flags para Estimator
    parser.add_argument("--quick", "-q",
                        help="Nombre del proyecto para estimador en modo rápido")
    parser.add_argument("--type", "-t", default="iac",
                        choices=["iac", "desarrollo", "soporte", "investigacion"],
                        help="[estimator] Tipo de proyecto")
    parser.add_argument("--complexity", "-c", default="medio",
                        choices=["bajo", "medio", "alto"],
                        help="[estimator] Complejidad del proyecto")
    parser.add_argument("--team", "-n", type=int, default=2,
                        help="[estimator] Número de personas en el equipo")

    # Incluir estimator en modo interactivo al correr todos
    parser.add_argument("--with-estimator", action="store_true",
                        help="Incluir Estimator interactivo al ejecutar todos los agentes")

    args = parser.parse_args()

    if args.agent:
        run_single(
            args.agent,
            severity=args.severity,
            project=args.project,
            hours=args.hours,
            skills=args.skills,
            quick=args.quick,
            type=args.type,
            complexity=args.complexity,
            team=args.team,
        )
    else:
        run_all(
            quick=args.quick,
            project_type=args.type,
            complexity=args.complexity,
            team=args.team,
            with_estimator=args.with_estimator,
        )


if __name__ == "__main__":
    main()
