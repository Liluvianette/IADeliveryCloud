"""
agents/estimator.py
Estimator — refina estimaciones con preguntas clave y genera breakdown detallado.

Uso:
    python agents/estimator.py                          # modo interactivo
    python agents/estimator.py --quick "Migrar Jenkins" # estimación rápida sin preguntas
    python agents/estimator.py --json '{"name":"X","type":"iac","complexity":"alto","team_size":2}'
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.base_agent import BaseAgent


# Tabla base: tipo × complejidad → horas
EFFORT_TABLE = {
    "iac":          {"bajo": 80,  "medio": 200, "alto": 480},
    "desarrollo":   {"bajo": 60,  "medio": 160, "alto": 400},
    "soporte":      {"bajo": 40,  "medio": 100, "alto": 240},
    "investigacion":{"bajo": 30,  "medio": 60,  "alto": 120},
}

# Modificadores de ajuste
MODIFIERS = {
    "nueva_tecnologia":  1.30,  # +30% si el equipo no conoce la tecnología
    "dependencia_externa": 1.20, # +20% si depende de otro equipo
    "legacy_system":     1.35,  # +35% sistemas legacy/sin documentación
    "multi_ambiente":    1.15,  # +15% si hay que replicar en varios ambientes
    "alta_disponibilidad": 1.20,# +20% si requiere HA/DR
    "compliance":        1.25,  # +25% si hay requisitos regulatorios
    "equipo_junior":     1.20,  # +20% si el equipo es mayormente junior
    "documentacion":     1.10,  # +10% si requiere documentación formal
    "paralelo_produccion": 1.25,# +25% si corre en paralelo a producción
}

PHASES = {
    "iac": [
        ("Discovery y diseño",        0.15),
        ("Implementación IaC",         0.40),
        ("Testing y validación",       0.20),
        ("Documentación",              0.10),
        ("Go-live y estabilización",   0.15),
    ],
    "desarrollo": [
        ("Discovery y arquitectura",   0.15),
        ("Desarrollo core",            0.45),
        ("Testing y QA",               0.20),
        ("Integración y deploy",       0.10),
        ("Documentación y handoff",    0.10),
    ],
    "soporte": [
        ("Análisis y diagnóstico",     0.20),
        ("Implementación / fix",       0.40),
        ("Validación en ambientes",    0.25),
        ("Documentación",              0.15),
    ],
    "investigacion": [
        ("Definición de criterios",    0.15),
        ("Investigación y pruebas",    0.50),
        ("PoC / prototipo",            0.20),
        ("Informe y recomendaciones",  0.15),
    ],
}

QUESTIONS = [
    {
        "id":      "project_type",
        "text":    "Tipo de proyecto",
        "options": {"1": "iac", "2": "desarrollo", "3": "soporte", "4": "investigacion"},
        "display": "1) IaC/Infraestructura  2) Desarrollo  3) Soporte/Ops  4) Investigación/PoC",
    },
    {
        "id":      "complexity",
        "text":    "Complejidad estimada",
        "options": {"1": "bajo", "2": "medio", "3": "alto"},
        "display": "1) Baja  2) Media  3) Alta",
    },
    {
        "id":      "team_size",
        "text":    "¿Cuántas personas trabajarán en el proyecto?",
        "options": None,  # número libre
        "display": "Número de personas (ej: 2)",
    },
    {
        "id":      "nueva_tecnologia",
        "text":    "¿El equipo necesita aprender tecnologías nuevas?",
        "options": {"s": True, "n": False},
        "display": "s/n",
    },
    {
        "id":      "dependencia_externa",
        "text":    "¿Depende de otro equipo o proveedor externo?",
        "options": {"s": True, "n": False},
        "display": "s/n",
    },
    {
        "id":      "legacy_system",
        "text":    "¿Involucra sistemas legacy o sin documentación?",
        "options": {"s": True, "n": False},
        "display": "s/n",
    },
    {
        "id":      "multi_ambiente",
        "text":    "¿Debe replicarse en múltiples ambientes (dev/stg/prod)?",
        "options": {"s": True, "n": False},
        "display": "s/n",
    },
    {
        "id":      "alta_disponibilidad",
        "text":    "¿Requiere alta disponibilidad o disaster recovery?",
        "options": {"s": True, "n": False},
        "display": "s/n",
    },
    {
        "id":      "compliance",
        "text":    "¿Hay requisitos de compliance o auditoría?",
        "options": {"s": True, "n": False},
        "display": "s/n",
    },
]


class Estimator(BaseAgent):
    name:  str = "estimator"
    role:  str = "Estimator"
    emoji: str = "📐"

    def _ask_questions(self, project_name: str) -> dict:
        """Modo interactivo — hace preguntas al usuario."""
        print(f"\n{'═'*60}")
        print(f"  📐 Estimator — Proyecto: {project_name}")
        print(f"{'═'*60}")
        print("  Responde las siguientes preguntas para generar la estimación.\n")

        answers = {"project_name": project_name}

        for q in QUESTIONS:
            while True:
                print(f"  ❓ {q['text']}")
                print(f"     [{q['display']}]: ", end="")
                raw = input().strip().lower()

                if q["options"] is None:
                    # Número libre
                    try:
                        answers[q["id"]] = int(raw) if raw else 2
                        break
                    except ValueError:
                        print("     ⚠ Ingresa un número válido.")
                elif raw in q["options"]:
                    answers[q["id"]] = q["options"][raw]
                    break
                else:
                    valid = "/".join(q["options"].keys())
                    print(f"     ⚠ Opción inválida. Usa: {valid}")

        return answers

    def _compute(self, answers: dict) -> dict:
        """Calcula la estimación a partir de las respuestas."""
        ptype      = answers.get("project_type", "iac")
        complexity = answers.get("complexity",   "medio")
        team_size  = max(int(answers.get("team_size", 2)), 1)

        # Horas base
        base_hours = EFFORT_TABLE.get(ptype, EFFORT_TABLE["iac"]).get(complexity, 160)

        # Aplicar modificadores activos
        active_modifiers = {}
        total_modifier   = 1.0
        for mod_key, mod_val in MODIFIERS.items():
            if answers.get(mod_key):
                active_modifiers[mod_key] = mod_val
                total_modifier *= mod_val

        adjusted_hours = round(base_hours * total_modifier)
        hours_min      = round(adjusted_hours * 0.75)
        hours_max      = round(adjusted_hours * 1.35)
        man_months     = round(adjusted_hours / 128, 2)
        story_points   = round(adjusted_hours / 8)

        # Duración en semanas con el equipo dado
        hours_per_person_week = 32  # horas efectivas por persona/semana
        duration_weeks = round(adjusted_hours / (team_size * hours_per_person_week))
        duration_weeks = max(duration_weeks, 1)

        # Fases del proyecto
        phase_list = PHASES.get(ptype, PHASES["iac"])
        phases = [
            {
                "phase":       name,
                "pct":         pct,
                "hours":       round(adjusted_hours * pct),
                "weeks":       max(round(duration_weeks * pct), 1),
            }
            for name, pct in phase_list
        ]

        return {
            "project_type":       ptype,
            "complexity":         complexity,
            "team_size":          team_size,
            "base_hours":         base_hours,
            "active_modifiers":   active_modifiers,
            "total_modifier":     round(total_modifier, 2),
            "adjusted_hours":     adjusted_hours,
            "hours_range":        f"{hours_min}h – {hours_max}h",
            "man_months":         man_months,
            "story_points_total": story_points,
            "duration_weeks":     duration_weeks,
            "phases":             phases,
        }

    def _check_team_capacity(self, estimate: dict) -> dict:
        """Cruza la estimación contra la capacidad real del equipo."""
        free_hours = self.summary.get("total_free_hours", 0) or 0
        can_absorb = free_hours >= estimate["adjusted_hours"] * 0.8
        deficit    = max(estimate["adjusted_hours"] - free_hours, 0)
        return {
            "team_free_hours": free_hours,
            "can_absorb":      can_absorb,
            "deficit_hours":   deficit,
            "deficit_manmonths": round(deficit / 128, 1) if deficit > 0 else 0,
        }

    def run(self, answers: dict = None, project_name: str = "Proyecto nuevo",
            interactive: bool = True) -> dict:

        self.load_all()

        # Obtener respuestas
        if answers:
            answers["project_name"] = answers.get("project_name", project_name)
        elif interactive:
            answers = self._ask_questions(project_name)
        else:
            raise ValueError("Provee 'answers' o usa interactive=True")

        name     = answers.get("project_name", project_name)
        estimate = self._compute(answers)
        capacity = self._check_team_capacity(estimate)

        findings        = []
        recommendations = []
        priority_actions= []

        # ── Hallazgos de estimación ───────────────────────
        # Modificadores activos
        if estimate["active_modifiers"]:
            mod_names = list(estimate["active_modifiers"].keys())
            findings.append({
                "severity": "media",
                "title":    f"Factores de riesgo aplicados: +{round((estimate['total_modifier']-1)*100)}% al esfuerzo base",
                "detail":   f"Modificadores activos: {', '.join(mod_names)}. "
                            f"Base: {estimate['base_hours']}h → Ajustado: {estimate['adjusted_hours']}h."
            })

        # Capacidad del equipo
        if not capacity["can_absorb"]:
            findings.append({
                "severity": "alta",
                "title":    f"El equipo no tiene horas suficientes ({capacity['team_free_hours']:.0f}h disponibles)",
                "detail":   f"El proyecto necesita {estimate['adjusted_hours']}h pero hay "
                            f"{capacity['team_free_hours']:.0f}h libres. "
                            f"Déficit: {capacity['deficit_hours']:.0f}h ({capacity['deficit_manmonths']} man-months)."
            })
            recommendations.append(
                f"Para iniciar en este sprint necesitas {capacity['deficit_manmonths']} man-months adicionales. "
                "Opciones: (a) reducir scope, (b) aumentar team size, (c) liberar personas de otros proyectos."
            )
        else:
            findings.append({
                "severity": "baja",
                "title":    f"El equipo puede absorber el proyecto ({capacity['team_free_hours']:.0f}h disponibles)",
                "detail":   f"Hay suficiente capacidad para las {estimate['adjusted_hours']}h estimadas."
            })

        # Duración
        dur = estimate["duration_weeks"]
        if dur > 12:
            findings.append({
                "severity": "media",
                "title":    f"Proyecto de larga duración ({dur} semanas ≈ {dur//4} meses)",
                "detail":   "Proyectos de más de 12 semanas tienen mayor riesgo de scope creep y desmotivación. "
                            "Considera dividirlo en fases o MVPs."
            })
            recommendations.append(
                "Dividir en 2 fases de máximo 6 semanas cada una. "
                "Entregable concreto al final de cada fase."
            )
        elif dur > 6:
            findings.append({
                "severity": "baja",
                "title":    f"Duración manejable: {dur} semanas con {estimate['team_size']} persona(s)",
                "detail":   "Dentro del rango razonable para un proyecto DevOps de esta complejidad."
            })

        # Team size vs complejidad
        if estimate["complexity"] == "alto" and estimate["team_size"] < 2:
            findings.append({
                "severity": "alta",
                "title":    "Proyecto complejo con solo 1 persona asignada",
                "detail":   "Alta complejidad con equipo mínimo aumenta riesgo de bloqueo y SPOF en el proyecto."
            })
            recommendations.append(
                "Asignar al menos 2 personas para proyectos de alta complejidad. "
                "Una como lead, otra como backup/reviewer."
            )
            priority_actions.append({
                "urgency": "antes de arrancar",
                "action":  "Definir co-lead o backup para el proyecto",
                "owner":   "Tech Lead"
            })

        # Acciones base
        priority_actions.append({
            "urgency": "antes de arrancar",
            "action":  f"Crear ticket épica en Jira con {estimate['story_points_total']} SP total y fases definidas",
            "owner":   "Tech Lead"
        })
        priority_actions.append({
            "urgency": "antes de arrancar",
            "action":  "Agregar proyecto a data/projects.yml con el YAML generado",
            "owner":   "Tech Lead"
        })

        # ── Veredicto ─────────────────────────────────────
        critical_f = [f for f in findings if f["severity"] in ("critica", "alta")]
        if len(critical_f) >= 2:
            verdict = "ALTO RIESGO"
        elif critical_f:
            verdict = "MODERADO"
        else:
            verdict = "VIABLE"

        # ── YAML para projects.yml ────────────────────────
        yaml_block = f"""  - id: PROJ-NEW-{estimate['project_type'][:3].upper()}
    name: "{name}"
    type: {estimate['project_type']}
    severity: media
    status: planificado
    start_date: "TBD"
    end_date: "TBD"
    description: "Agregar descripción"
    devops_lead: "TBD"
    team_assignments: []
    required_skills: []
    estimated_effort:
      total_hours:         {estimate['adjusted_hours']}
      remaining_hours:     {estimate['adjusted_hours']}
      story_points_total:  {estimate['story_points_total']}
      story_points_done:   0
    notes: "Estimado por Estimator Agent — revisar antes de confirmar"
    # Duración estimada: {estimate['duration_weeks']} semanas con {estimate['team_size']} persona(s)"""

        # ── Prompt de IA ──────────────────────────────────
        mod_list = "\n".join([f"  - {k}: +{round((v-1)*100)}%" for k, v in estimate["active_modifiers"].items()]) or "  - Ninguno"
        phases_str = "\n".join([f"  {p['phase']}: {p['hours']}h (~{p['weeks']} semanas)" for p in estimate["phases"]])

        ai_prompt = f"""Actúa como Agile Coach y experto en estimación de proyectos DevOps/Cloud.
Revisa y refina la siguiente estimación técnica.

Proyecto: {name}
Tipo: {estimate['project_type']} | Complejidad: {estimate['complexity']}
Equipo: {estimate['team_size']} persona(s)

Estimación base:
- Horas base: {estimate['base_hours']}h
- Modificadores aplicados: +{round((estimate['total_modifier']-1)*100)}%
{mod_list}
- Total ajustado: {estimate['adjusted_hours']}h ({estimate['hours_range']})
- Duración: {estimate['duration_weeks']} semanas
- Story Points: {estimate['story_points_total']} SP

Fases propuestas:
{phases_str}

Proporciona:
1. Validación de la estimación (¿es razonable para el contexto?)
2. Riesgos de estimación que podrían inflar las horas reales
3. Desglose de Story Points por fase (sugerencia para el backlog)
4. Recomendaciones para el kick-off del proyecto
5. Preguntas adicionales al cliente/sponsor para refinar la estimación"""

        return self.build_result(
            findings, recommendations, verdict, priority_actions,
            extra={
                "project_name":  name,
                "estimate":      estimate,
                "capacity_check":capacity,
                "yaml_block":    yaml_block,
                "ai_prompt":     ai_prompt,
            }
        )

    def print_result(self, result: dict):
        """Override para incluir el breakdown de fases."""
        super().print_result(result)

        e = result.get("estimate", {})
        if not e:
            return

        print("  BREAKDOWN DE FASES:")
        print(f"  {'─'*54}")
        for phase in e.get("phases", []):
            bar = "█" * round(phase["pct"] * 20)
            print(f"  {phase['phase']:<35} {bar:<20} {phase['hours']}h / ~{phase['weeks']}sem")
        print(f"  {'─'*54}")
        print(f"  {'TOTAL':<35} {'':20} {e['adjusted_hours']}h")
        print(f"  Rango: {e['hours_range']}  ·  {e['man_months']} man-months  ·  {e['story_points_total']} SP")
        print(f"  Duración estimada: {e['duration_weeks']} semanas con {e['team_size']} persona(s)\n")

        cap = result.get("capacity_check", {})
        icon = "✅" if cap.get("can_absorb") else "⚠️ "
        print(f"  CAPACIDAD DEL EQUIPO: {icon}")
        print(f"  Horas libres del equipo: {cap.get('team_free_hours', 0):.0f}h")
        print(f"  Horas requeridas:        {e['adjusted_hours']}h")
        if not cap.get("can_absorb"):
            print(f"  Déficit:                 {cap.get('deficit_hours', 0):.0f}h ({cap.get('deficit_manmonths', 0)} man-months)")
        print()

        print("  YAML PARA projects.yml:")
        print("  " + "─"*54)
        for line in result["yaml_block"].split("\n"):
            print(f"  {line}")
        print("  " + "─"*54 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Estimator — genera estimación detallada con breakdown por fases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python agents/estimator.py                          # modo interactivo con preguntas
  python agents/estimator.py --quick "Migrar Jenkins" --type iac --complexity medio --team 2
  python agents/estimator.py --json '{"project_name":"X","project_type":"iac","complexity":"alto","team_size":3,"legacy_system":true}'
        """
    )
    parser.add_argument("--quick",      "-q", help="Nombre del proyecto (modo rápido sin preguntas)")
    parser.add_argument("--type",       "-t", default="iac",
                        choices=["iac","desarrollo","soporte","investigacion"])
    parser.add_argument("--complexity", "-c", default="medio",
                        choices=["bajo","medio","alto"])
    parser.add_argument("--team",       "-n", type=int, default=2)
    parser.add_argument("--json",       "-j", help="JSON con todas las respuestas")
    args = parser.parse_args()

    agent = Estimator()

    if args.json:
        answers = json.loads(args.json)
        result  = agent.run(answers=answers, interactive=False)
    elif args.quick:
        answers = {
            "project_name":   args.quick,
            "project_type":   args.type,
            "complexity":     args.complexity,
            "team_size":      args.team,
        }
        result = agent.run(answers=answers, interactive=False)
    else:
        name   = input("\n  Nombre del proyecto: ").strip() or "Proyecto nuevo"
        result = agent.run(project_name=name, interactive=True)

    agent.print_result(result)

    print("  💡 PROMPT PARA ANÁLISIS CON IA (Bedrock / Claude):")
    print("  " + "─"*56)
    for line in result["ai_prompt"].split("\n"):
        print(f"  {line}")
    print("  " + "─"*56 + "\n")