"""
agents/tech_lead.py
Tech Lead Reviewer — analiza si un proyecto nuevo es viable para el equipo.

Uso:
    python agents/tech_lead.py
    python agents/tech_lead.py --project "Migrar Jenkins a GitHub Actions"
    python agents/tech_lead.py --project "Observabilidad centralizada" --hours 240 --skills ci_cd,kubernetes,observability
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.base_agent import BaseAgent


class TechLeadReviewer(BaseAgent):
    name:  str = "tech_lead"
    role:  str = "Tech Lead Reviewer"
    emoji: str = "👨‍💼"

    # Umbrales de decisión
    MAX_TEAM_LOAD      = 85.0   # % — si el equipo supera esto, no se acepta
    MAX_MEMBER_LOAD    = 90.0   # % — carga máxima por persona para asignar
    MIN_FREE_HOURS     = 40.0   # horas mínimas disponibles en el equipo
    MIN_HEALTH_SCORE   = 30     # health score mínimo para aceptar proyectos

    def run(self, new_project_hours: float = 0,
            required_skills: list = None,
            project_name: str = "Proyecto nuevo") -> dict:

        self.load_all()
        required_skills = required_skills or []

        findings         = []
        recommendations  = []
        priority_actions = []

        # ── 1. Carga actual del equipo ────────────────────
        team_load = self.team_load_pct()
        free_hours_total = self.summary.get("total_free_hours", 0) or 0

        if team_load > 100:
            findings.append({
                "severity": "critica",
                "title":    f"Equipo sobrecargado al {team_load:.0f}%",
                "detail":   f"El equipo opera {team_load - 100:.0f}% por encima de su capacidad real. "
                            f"Solo hay {free_hours_total:.0f}h libres vs las {new_project_hours:.0f}h requeridas."
            })
        elif team_load > self.MAX_TEAM_LOAD:
            findings.append({
                "severity": "alta",
                "title":    f"Carga del equipo en zona de riesgo ({team_load:.0f}%)",
                "detail":   f"El equipo está al {team_load:.0f}% de capacidad. "
                            f"Agregar más trabajo aumenta el riesgo de entregas tardías."
            })
        else:
            findings.append({
                "severity": "baja",
                "title":    f"Carga del equipo aceptable ({team_load:.0f}%)",
                "detail":   f"Hay {free_hours_total:.0f}h disponibles en el equipo."
            })

        # ── 2. Cobertura de skills requeridos ─────────────
        if required_skills:
            missing_skills      = []
            low_coverage_skills = []
            spof_required       = []

            for skill in required_skills:
                skill_data = self.skills.get(skill)
                if not skill_data:
                    missing_skills.append(skill)
                    continue
                cov = self.skill_coverage(skill_data)
                if cov < 30:
                    low_coverage_skills.append((skill, cov))
                if skill_data.get("is_spof"):
                    spof_required.append(skill)

            if missing_skills:
                findings.append({
                    "severity": "critica",
                    "title":    f"Skills no encontrados: {', '.join(missing_skills)}",
                    "detail":   "El equipo no tiene registrado dominio en estas habilidades. "
                                "Considera contratación externa o capacitación antes de comprometerse."
                })
                recommendations.append(
                    f"Evaluar contratación externa o consultoría para: {', '.join(missing_skills)}"
                )

            if low_coverage_skills:
                names = [f"{s} ({c:.0f}%)" for s, c in low_coverage_skills]
                findings.append({
                    "severity": "alta",
                    "title":    f"Baja cobertura en skills clave: {', '.join([s for s,_ in low_coverage_skills])}",
                    "detail":   f"Cobertura insuficiente: {', '.join(names)}. "
                                "Riesgo de cuello de botella durante la ejecución."
                })
                recommendations.append(
                    "Asignar al menos 2 personas con dominio en cada skill crítico antes de arrancar."
                )

            if spof_required:
                findings.append({
                    "severity": "alta",
                    "title":    f"Skills requeridos con SPOF: {', '.join(spof_required)}",
                    "detail":   "Solo hay 1 persona con dominio en estos skills. "
                                "Si esa persona no está disponible, el proyecto se detiene."
                })
                recommendations.append(
                    f"Incluir plan de transferencia de conocimiento para: {', '.join(spof_required)}"
                )
        else:
            findings.append({
                "severity": "info",
                "title":    "Sin skills especificados",
                "detail":   "No se indicaron skills requeridos. "
                            "Usa --skills para un análisis más preciso."
            })

        # ── 3. Miembros disponibles para absorber ─────────
        available_members = []
        overloaded_members = []

        for m in self.team:
            load = self.member_load_pct(m)
            free = self.free_hours(m)
            if m.get("on_leave"):
                continue
            if load > self.MAX_MEMBER_LOAD:
                overloaded_members.append(m["name"])
            elif free >= 16:  # al menos 2 días disponibles
                available_members.append({
                    "name":       m["name"],
                    "role":       m.get("role", ""),
                    "free_hours": round(free, 0),
                    "load_pct":   load,
                })

        if not available_members:
            findings.append({
                "severity": "critica",
                "title":    "Sin miembros disponibles para asignar",
                "detail":   f"Todos los miembros activos superan el {self.MAX_MEMBER_LOAD}% de carga. "
                            "No hay capacidad real para un proyecto adicional."
            })
        else:
            names = ", ".join([m["name"] for m in available_members])
            total_free = sum(m["free_hours"] for m in available_members)
            findings.append({
                "severity": "info",
                "title":    f"{len(available_members)} miembro(s) con capacidad disponible",
                "detail":   f"{names} — total {total_free:.0f}h libres combinadas."
            })

        # ── 4. Health Score ───────────────────────────────
        score = self.health_score
        if score < self.MIN_HEALTH_SCORE:
            findings.append({
                "severity": "critica",
                "title":    f"Health Score crítico ({score}/100)",
                "detail":   f"El equipo tiene {len(self.critical_risks())} riesgos críticos activos. "
                            "Agregar un proyecto empeorará la situación."
            })
            recommendations.append(
                "Resolver al menos los riesgos críticos existentes antes de comprometer nuevos proyectos."
            )
        elif score < 50:
            findings.append({
                "severity": "alta",
                "title":    f"Health Score bajo ({score}/100)",
                "detail":   "El equipo está en estado de estrés. "
                            "Considera si este es el momento adecuado."
            })

        # ── 5. Viabilidad de horas ────────────────────────
        if new_project_hours > 0:
            if free_hours_total >= new_project_hours:
                findings.append({
                    "severity": "baja",
                    "title":    f"Horas suficientes: {free_hours_total:.0f}h disponibles vs {new_project_hours:.0f}h requeridas",
                    "detail":   "El equipo tiene capacidad teórica para absorber el proyecto."
                })
            else:
                deficit = new_project_hours - free_hours_total
                findings.append({
                    "severity": "critica",
                    "title":    f"Déficit de {deficit:.0f}h para ejecutar el proyecto",
                    "detail":   f"Se necesitan {new_project_hours:.0f}h pero solo hay {free_hours_total:.0f}h disponibles. "
                                f"Faltan {deficit:.0f}h ({deficit/160*100:.0f}% de un mes-persona)."
                })
                recommendations.append(
                    f"Pausar o descalar {deficit/160:.1f} proyectos actuales para liberar capacidad, "
                    "o contratar un recurso temporal."
                )

        # ── 6. Proyectos activos críticos ─────────────────
        critical_active = [p for p in self.active_projects()
                           if p.get("severity") == "critica"]
        if len(critical_active) >= 2:
            names = ", ".join([p["name"] for p in critical_active[:3]])
            findings.append({
                "severity": "alta",
                "title":    f"{len(critical_active)} proyectos críticos en curso simultáneamente",
                "detail":   f"Proyectos críticos activos: {names}. "
                            "Agregar otro proyecto crítico multiplica el riesgo de entrega."
            })
            recommendations.append(
                "Revisar si alguno de los proyectos críticos activos puede pausarse o reducir su scope."
            )

        # ── Veredicto final ───────────────────────────────
        critical_findings = [f for f in findings if f["severity"] == "critica"]
        high_findings     = [f for f in findings if f["severity"] == "alta"]

        if len(critical_findings) >= 2:
            verdict = "NO VIABLE"
            recommendations.insert(0,
                f"NO se recomienda aceptar '{project_name}' en este momento. "
                "El equipo no tiene capacidad ni salud para absorberlo sin riesgo severo."
            )
            priority_actions.append({
                "urgency": "inmediata",
                "action":  "Comunicar a stakeholders que el equipo no puede aceptar el proyecto",
                "owner":   "Tech Lead"
            })
            priority_actions.append({
                "urgency": "esta semana",
                "action":  "Revisar proyectos activos y proponer qué pausar o descalar",
                "owner":   "Tech Lead + PMs"
            })
        elif len(critical_findings) == 1 or len(high_findings) >= 2:
            verdict = "CONDICIONAL"
            recommendations.insert(0,
                f"'{project_name}' puede aceptarse SOLO si se resuelven las condiciones marcadas como críticas/altas."
            )
            priority_actions.append({
                "urgency": "antes de arrancar",
                "action":  "Resolver o mitigar los hallazgos marcados en ROJO/NARANJA",
                "owner":   "Tech Lead"
            })
            if available_members:
                best = available_members[0]
                priority_actions.append({
                    "urgency": "antes de arrancar",
                    "action":  f"Asignar lead del proyecto a {best['name']} ({best['free_hours']:.0f}h disponibles)",
                    "owner":   "Tech Lead"
                })
        else:
            verdict = "VIABLE"
            recommendations.insert(0,
                f"'{project_name}' es viable. El equipo tiene capacidad y salud para absorberlo."
            )
            if available_members:
                top = available_members[:2]
                names = " y ".join([m["name"] for m in top])
                priority_actions.append({
                    "urgency": "próximos días",
                    "action":  f"Definir asignación formal. Candidatos sugeridos: {names}",
                    "owner":   "Tech Lead"
                })
            priority_actions.append({
                "urgency": "próximos días",
                "action":  "Actualizar projects.yml con el nuevo proyecto y asignaciones",
                "owner":   "Tech Lead"
            })

        # Prompt de referencia para IA real
        ai_prompt = f"""Actúa como Principal Tech Lead con 15 años de experiencia en equipos DevOps cloud.
Analiza si el equipo puede aceptar el proyecto "{project_name}" dadas estas condiciones:

- Carga actual del equipo: {team_load:.0f}%
- Health Score: {score}/100
- Horas disponibles: {free_hours_total:.0f}h
- Horas requeridas: {new_project_hours:.0f}h
- Skills requeridos: {', '.join(required_skills) if required_skills else 'no especificados'}
- Miembros disponibles: {', '.join([m['name'] for m in available_members]) if available_members else 'ninguno'}
- Riesgos críticos activos: {len(self.critical_risks())}
- Proyectos activos críticos: {len(critical_active)}

Proporciona:
1. Veredicto (VIABLE / NO VIABLE / CONDICIONAL) con justificación
2. Condiciones que deben cumplirse antes de arrancar
3. Propuesta de asignación concreta (quién lidera, quién apoya)
4. Riesgos principales del proyecto dado el estado del equipo
5. Recomendación al sponsor del proyecto"""

        return self.build_result(
            findings, recommendations, verdict, priority_actions,
            extra={
                "project_name":      project_name,
                "new_project_hours": new_project_hours,
                "required_skills":   required_skills,
                "available_members": available_members,
                "team_load_pct":     team_load,
                "health_score":      score,
                "ai_prompt":         ai_prompt,
            }
        )


# ── CLI ───────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tech Lead Reviewer — analiza viabilidad de un proyecto nuevo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python agents/tech_lead.py
  python agents/tech_lead.py --project "Migrar Jenkins a GitHub Actions" --hours 176
  python agents/tech_lead.py --project "Observabilidad" --hours 240 --skills observability,kubernetes,aws
        """
    )
    parser.add_argument("--project", "-p", default="Proyecto nuevo",
                        help="Nombre del proyecto a evaluar")
    parser.add_argument("--hours",   "-H", type=float, default=0,
                        help="Horas estimadas del proyecto")
    parser.add_argument("--skills",  "-s", default="",
                        help="Skills requeridos separados por coma (ej: kubernetes,terraform,aws)")
    args = parser.parse_args()

    skills_list = [s.strip() for s in args.skills.split(",") if s.strip()]

    agent  = TechLeadReviewer()
    result = agent.run(
        project_name      = args.project,
        new_project_hours = args.hours,
        required_skills   = skills_list,
    )
    agent.print_result(result)

    # Mostrar el prompt de IA al final (para uso manual con Copilot/Claude)
    print("  💡 PROMPT PARA ANÁLISIS CON IA (pega esto en VS Code Copilot o Claude):")
    print("  " + "─"*56)
    for line in result["ai_prompt"].split("\n"):
        print(f"  {line}")
    print("  " + "─"*56 + "\n")