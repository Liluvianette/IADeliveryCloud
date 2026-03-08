"""
agents/capacity_analyst.py
Capacity Analyst — detecta desequilibrios de carga y recomienda redistribución.

Uso:
    python agents/capacity_analyst.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.base_agent import BaseAgent


class CapacityAnalyst(BaseAgent):
    name:  str = "capacity_analyst"
    role:  str = "Capacity Analyst"
    emoji: str = "📊"

    OVERLOAD_THRESHOLD   = 1.0   # ratio — 100%
    UNDERLOAD_THRESHOLD  = 0.5   # ratio — 50%
    IDEAL_LOAD_MIN       = 0.65
    IDEAL_LOAD_MAX       = 0.85

    def run(self) -> dict:
        self.load_all()

        findings        = []
        recommendations = []
        priority_actions= []

        team_load = self.team_load_pct()
        members   = self.team

        # ── 1. Mapa de carga individual ───────────────────
        overloaded   = []
        underloaded  = []
        ideal        = []
        on_leave     = []

        for m in members:
            lp = (m.get("load_percent") or 0)
            if m.get("on_leave"):
                on_leave.append(m)
            elif lp > self.OVERLOAD_THRESHOLD:
                overloaded.append(m)
            elif lp < self.UNDERLOAD_THRESHOLD:
                underloaded.append(m)
            else:
                ideal.append(m)

        # ── 2. Hallazgo: sobrecarga global ────────────────
        if team_load > 120:
            findings.append({
                "severity": "critica",
                "title":    f"Sobrecarga severa del equipo ({team_load:.0f}%)",
                "detail":   f"{len(overloaded)} de {len(members)} personas superan el 100% de carga. "
                            f"Riesgo alto de burnout, errores y abandono."
            })
        elif team_load > 100:
            findings.append({
                "severity": "alta",
                "title":    f"Equipo por encima de su capacidad ({team_load:.0f}%)",
                "detail":   f"{len(overloaded)} persona(s) sobrecargadas. "
                            "La calidad de entrega está en riesgo."
            })
        elif team_load > self.IDEAL_LOAD_MAX * 100:
            findings.append({
                "severity": "media",
                "title":    f"Carga elevada pero manejable ({team_load:.0f}%)",
                "detail":   "El equipo opera en el límite superior del rango saludable."
            })
        else:
            findings.append({
                "severity": "baja",
                "title":    f"Carga del equipo en rango saludable ({team_load:.0f}%)",
                "detail":   f"El equipo opera entre {self.IDEAL_LOAD_MIN*100:.0f}% y {self.IDEAL_LOAD_MAX*100:.0f}% — zona óptima."
            })

        # ── 3. Detalle por persona sobrecargada ───────────
        for m in overloaded:
            lp    = (m.get("load_percent") or 0) * 100
            alloc = m.get("allocated_hours", 0) or 0
            avail = self.available_hours(m)
            excess= alloc - avail
            projs = m.get("projects", [])
            top_proj = sorted(projs, key=lambda p: -p.get("allocation_percent", 0))[:2]
            top_names = ", ".join([f"{p['project_id']} ({p['allocation_percent']}%)" for p in top_proj])

            findings.append({
                "severity": "critica" if lp > 130 else "alta",
                "title":    f"{m['name']} sobrecargado al {lp:.0f}%",
                "detail":   f"Tiene {alloc:.0f}h asignadas sobre {avail:.0f}h disponibles "
                            f"(exceso: {excess:.0f}h). Proyectos principales: {top_names}."
            })

        # ── 4. Personas sub-utilizadas ────────────────────
        for m in underloaded:
            lp   = (m.get("load_percent") or 0) * 100
            free = self.free_hours(m)
            findings.append({
                "severity": "media",
                "title":    f"{m['name']} sub-utilizado ({lp:.0f}% de carga)",
                "detail":   f"Tiene {free:.0f}h disponibles sin asignar. "
                            "Capacidad que podría redistribuirse."
            })

        # ── 5. Licencias activas ──────────────────────────
        if on_leave:
            names = ", ".join([m["name"] for m in on_leave])
            findings.append({
                "severity": "media",
                "title":    f"{len(on_leave)} persona(s) de licencia: {names}",
                "detail":   "Su carga asignada debe estar cubierta por el resto del equipo."
            })

        # ── 6. Propuesta de redistribución ───────────────
        redistribution = []
        if overloaded and (underloaded or ideal):
            absorbers = sorted(
                [m for m in (underloaded + ideal) if not m.get("on_leave")],
                key=lambda m: self.free_hours(m),
                reverse=True
            )

            for sobrecargado in overloaded:
                projs = sobrecargado.get("projects", [])
                # Buscar proyectos reasignables (no los más críticos)
                reasignables = [p for p in sorted(projs, key=lambda x: x.get("allocation_percent", 0))
                                if p.get("allocation_percent", 0) <= 30][:1]

                for proj in reasignables:
                    for absorber in absorbers:
                        free = self.free_hours(absorber)
                        needed = round(proj["allocation_percent"] / 100 * self.available_hours(sobrecargado))
                        if free >= needed * 0.8:
                            redistribution.append({
                                "from":        sobrecargado["name"],
                                "to":          absorber["name"],
                                "project":     proj["project_id"],
                                "hours":       needed,
                                "feasible":    True,
                            })
                            break

        if redistribution:
            lines = [
                f"{r['from']} → {r['to']}: proyecto {r['project']} ({r['hours']:.0f}h)"
                for r in redistribution
            ]
            findings.append({
                "severity": "info",
                "title":    f"{len(redistribution)} reasignación(es) posible(s) detectadas",
                "detail":   " | ".join(lines)
            })
            recommendations.append(
                "Redistribución sugerida: " + "; ".join(lines)
            )
            for r in redistribution:
                priority_actions.append({
                    "urgency": "esta semana",
                    "action":  f"Mover participación en {r['project']} de {r['from']} a {r['to']} ({r['hours']:.0f}h)",
                    "owner":   "Tech Lead"
                })

        # ── 7. Recomendaciones generales ─────────────────
        free_manmonths = self.summary.get("estimated_free_manmonths", 0) or 0

        if len(overloaded) >= 3:
            recommendations.append(
                "Considerar contratación de 1 recurso temporal para reducir presión en los próximos 2 meses."
            )
            priority_actions.append({
                "urgency": "este mes",
                "action":  "Abrir requisición de recurso temporal / consultor DevOps",
                "owner":   "Manager"
            })

        if underloaded:
            names = ", ".join([m["name"] for m in underloaded])
            recommendations.append(
                f"{names} tienen capacidad libre — evaluar asignarles deuda técnica o capacitación."
            )

        if on_leave:
            recommendations.append(
                "Revisar que los proyectos de personas en licencia tienen sustituto definido."
            )
            priority_actions.append({
                "urgency": "inmediata",
                "action":  "Confirmar cobertura de proyectos de personas en licencia",
                "owner":   "Tech Lead"
            })

        if free_manmonths > 0.5:
            recommendations.append(
                f"El equipo tiene {free_manmonths:.1f} man-months libres — "
                "oportunidad para atacar deuda técnica o capacitación."
            )

        # ── Veredicto ─────────────────────────────────────
        critical = [f for f in findings if f["severity"] == "critica"]
        high     = [f for f in findings if f["severity"] == "alta"]

        if len(critical) >= 2:
            verdict = "CRÍTICO"
        elif critical or len(high) >= 2:
            verdict = "MODERADO"
        else:
            verdict = "SALUDABLE"

        # ── Prompt de IA ──────────────────────────────────
        member_summary = "\n".join([
            f"  - {m['name']} ({m['role']}): {(m.get('load_percent') or 0)*100:.0f}% carga, "
            f"{self.free_hours(m):.0f}h libres"
            for m in members
        ])

        ai_prompt = f"""Actúa como Capacity Planning Manager con experiencia en equipos DevOps de alto rendimiento.
Analiza la distribución de carga del equipo y propón una redistribución óptima.

Estado del equipo:
- Carga promedio: {team_load:.0f}%
- Sobrecargados: {len(overloaded)} personas
- Sub-utilizados: {len(underloaded)} personas
- En licencia: {len(on_leave)} personas
- Man-months libres: {free_manmonths:.1f}

Detalle por persona:
{member_summary}

Proporciona:
1. Diagnóstico de la distribución actual (¿es sostenible?)
2. Plan concreto de redistribución (quién cede qué, a quién)
3. Proyectos candidatos para pausar o reducir scope
4. Recomendaciones para prevenir burnout en las personas sobrecargadas
5. Acciones para las próximas 2 semanas"""

        return self.build_result(
            findings, recommendations, verdict, priority_actions,
            extra={
                "overloaded_count":  len(overloaded),
                "underloaded_count": len(underloaded),
                "on_leave_count":    len(on_leave),
                "redistribution":    redistribution,
                "team_load_pct":     team_load,
                "free_manmonths":    free_manmonths,
                "ai_prompt":         ai_prompt,
            }
        )


if __name__ == "__main__":
    agent  = CapacityAnalyst()
    result = agent.run()
    agent.print_result(result)

    print("  💡 PROMPT PARA ANÁLISIS CON IA:")
    print("  " + "─"*56)
    for line in result["ai_prompt"].split("\n"):
        print(f"  {line}")
    print("  " + "─"*56 + "\n")