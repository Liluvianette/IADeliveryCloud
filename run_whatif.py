#!/usr/bin/env python3
"""
run_whatif.py — Simulador rápido "¿Y si meto este proyecto?"

Uso:
  python run_whatif.py                          → simula data/incoming_project.yml
  python run_whatif.py --file otro_proyecto.yml → simula archivo específico

Requisitos: Ejecutar run.py primero para generar los JSONs base.
"""

import sys
import argparse
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="What-If Calculator")
    parser.add_argument("--file", type=str, default=None,
                        help="Ruta al YAML del proyecto a simular")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  🔮 Cloud Delivery Intelligence — What-If Calculator")
    print("═" * 60 + "\n")

    # Verificar que existen los JSONs necesarios
    output = Path("output")
    required = ["team_raw.json", "team_capacity.json", "quarter_plan.json"]
    missing = [f for f in required if not (output / f).exists()]

    if missing:
        print(f"  ❌ Faltan archivos: {', '.join(missing)}")
        print("  → Ejecuta 'python run.py --skip-ai' primero")
        sys.exit(1)

    sys.path.insert(0, str(Path(__file__).parent))
    from analysis.what_if_calculator import run as whatif_run

    result = whatif_run(incoming_path=args.file)

    if result:
        print("\n" + "─" * 60)
        v = result["verdict"]
        symbol = {"VIABLE": "✅", "CONDICIONAL": "⚠️", "NO VIABLE": "❌"}.get(v, "❓")
        print(f"  {symbol} VEREDICTO: {v}")

        impact = result.get("impact_on_team", {})
        before = impact.get("before", {})
        after = impact.get("after", {})
        print(f"\n  Impacto en el equipo:")
        print(f"    Carga: {before.get('team_load_pct', 0)}% → {after.get('team_load_pct', 0)}%")
        print(f"    MM libres: {before.get('free_mm', 0)} → {after.get('free_mm', 0)}")

        if result.get("best_fit_members"):
            print(f"\n  Mejores candidatos:")
            for m in result["best_fit_members"][:3]:
                print(f"    • {m['name']} — skill match: {m['skill_match']}% | "
                      f"carga actual: {m['current_load_pct']}%")

        if result.get("alternatives"):
            print(f"\n  Alternativas:")
            for alt in result["alternatives"]:
                print(f"    → {alt}")

        print("\n" + "═" * 60 + "\n")


if __name__ == "__main__":
    main()
