"""
agents/risk_officer.py
Risk Officer — profundiza en riesgos y genera plan de mitigación concreto.

Uso:
    python agents/risk_officer.py
    python agents/risk_officer.py --severity critica
    python agents/risk_officer.py --severity alta,media
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.base_agent import BaseAgent


class RiskOfficer(BaseAgent):
    name:  str = "risk_officer"
    role:  str = "Risk Officer"
    emoji: str = "🛡️"

    # Días estimados para mitigar según severidad
    MITIGATION_DAYS = {
        "critica": 3,
        "alta":    7,
        "media":   14,
        "baja":    30,
    }

    # Tipos de riesgo → estrategia de mitigación por defecto
    MITIGATION_STRATEGIES = {
        "sobrecarga":         "Redistribuir carga o contratar recurso temporal. Revisar scope de proyectos activos.",
        "spof":               "Sesión de knowledge transfer esta semana. Documentar runbooks. Rotar responsabilidades.",
        "skill_gap":          "Plan de capacitación en 30 días. Evaluar consultoría externa para el corto plazo.",
        "burnout":            "Reducir carga al 80% para la persona afectada. Revisión 1:1 semanal con manager.",
        "deuda_tecnica":      "Reservar 20% del sprint para deuda técnica. Registrar en backlog priorizado.",
        "falta_cobertura":    "Definir backup para cada rol crítico. Documentar procedimientos de escalación.",
        "proyecto_en_riesgo": "Revisar scope y deadline con stakeholders. Definir MVP mínimo entregable.",
        "dependencia":        "Mapear dependencias externas. Establecer SLA con equipos dependientes.",
        "seguridad":          "Realizar revisión de seguridad urgente. Escalar a equipo de InfoSec.",
        "general":            "Analizar causa raíz. Definir owner y fecha de resolución en próxima reunión.",
    }

    def _get_strategy(self, risk: dict) -> str:
        rtype = risk.get("type", "general").lower()
        # Buscar estrategia por tipo exacto o más cercano
        for key in self.MITIGATION_STRATEGIES:
            if key in rtype or rtype in key:
                return self.MITIGATION_STRATEGIES[key]
        return self.MITIGATION_STRATEGIES["general"]

    def _estimate_effort(self, risk: dict) -> str:
        sev = risk.get("severity", "media")
        days = self.MITIGATION_DAYS.get(sev, 14)
        if days <= 3:
            return f"~{days} días (urgente)"
        elif days <= 7:
            return f"~{days} días"
        else:
            return f"~{days} días (planificado)"

    def run(self, filter_severity: list = None) -> dict:
        self.load_all()

        findings        = []
        recommendations = []
        priority_actions= []

        all_risks = self.risks
        score     = self.health_score
        by_sev    = self._data["health"].get("risks_by_severity", {})

        # Filtrar por severidad si se especificó
        if filter_severity:
            risks_to_analyze = [r for r in all_risks
                                if r.get("severity") in filter_severity]
        else:
            risks_to_analyze = all_risks

        if not risks_to_analyze:
            findings.append({
                "severity": "baja",
                "title":    "Sin riesgos detectados para los filtros aplicados",
                "detail":   "El equipo está en buenas condiciones o no hay datos suficientes."
            })
            return self.build_result(findings, recommendations, "BAJO RIESGO", priority_actions,
                                     extra={"total_risks": 0, "health_score": score, "ai_prompt": ""})

        # ── 1. Panorama general ───────────────────────────
        total    = len(all_risks)
        critical = by_sev.get("critica", 0)
        high     = by_sev.get("alta", 0)
        medium   = by_sev.get("media", 0)
        low      = by_sev.get("baja", 0)

        findings.append({
            "severity": "critica" if critical >= 3 else "alta" if critical >= 1 else "media",
            "title":    f"Panorama de riesgos: {total} detectados",
            "detail":   f"🔴 {critical} críticos  🟠 {high} altos  🟡 {medium} medios  🟢 {low} bajos. "
                        f"Health Score actual: {score}/100."
        })

        # ── 2. Plan de mitigación por riesgo ─────────────
        mitigation_plan = []
        order = {"critica": 0, "alta": 1, "media": 2, "baja": 3}
        sorted_risks = sorted(risks_to_analyze,
                              key=lambda r: order.get(r.get("severity", "media"), 2))

        for risk in sorted_risks:
            sev      = risk.get("severity", "media")
            strategy = self._get_strategy(risk)
            effort   = self._estimate_effort(risk)

            findings.append({
                "severity": sev,
                "title":    risk.get("title") or risk.get("type", "Riesgo"),
                "detail":   f"{risk.get('description', '')} → {risk.get('recommendation', '')}"
            })

            mitigation_plan.append({
                "risk":     risk.get("title") or risk.get("type"),
                "severity": sev,
                "strategy": strategy,
                "effort":   effort,
                "owner":    self._suggest_owner(risk),
            })

        # ── 3. Hallazgos de segundo orden ─────────────────
        # Riesgos agrupados por tipo para detectar patrones
        type_counts = {}
        for r in all_risks:
            t = r.get("type", "general")
            type_counts[t] = type_counts.get(t, 0) + 1

        top_type = max(type_counts, key=type_counts.get) if type_counts else None
        if top_type and type_counts[top_type] >= 3:
            findings.append({
                "severity": "alta",
                "title":    f"Patrón detectado: {type_counts[top_type]} riesgos del tipo '{top_type}'",
                "detail":   "La concentración de riesgos del mismo tipo indica un problema estructural, "
                            "no incidentes aislados. Requiere intervención sistémica."
            })
            recommendations.append(
                f"El tipo de riesgo '{top_type}' es recurrente — "
                "abordar la causa raíz en lugar de mitigar síntomas uno a uno."
            )

        # SPOFs detectados en skills
        spofs = self.spof_skills()
        if spofs:
            findings.append({
                "severity": "alta",
                "title":    f"{len(spofs)} skill(s) con SPOF: {', '.join(spofs)}",
                "detail":   "Si la persona con dominio único no está disponible, "
                            "proyectos que requieran ese skill se detienen completamente."
            })
            recommendations.append(
                f"Plan de knowledge transfer para skills SPOF: {', '.join(spofs)}. "
                "Objetivo: al menos 2 personas con nivel ≥ 2 en cada skill crítico."
            )
            priority_actions.append({
                "urgency": "esta semana",
                "action":  f"Agendar sesiones de KT para: {', '.join(spofs)}",
                "owner":   "Tech Lead"
            })

        # ── 4. Recomendaciones sistémicas ────────────────
        if critical >= 3:
            recommendations.append(
                "Con 3+ riesgos críticos simultáneos, convocar una sesión de war room "
                "esta semana con todo el equipo para priorizar y asignar owners."
            )
            priority_actions.append({
                "urgency": "inmediata",
                "action":  "War room de riesgos — priorizar los top 3 críticos",
                "owner":   "Tech Lead + Manager"
            })

        if score < 30:
            recommendations.append(
                "Health Score por debajo de 30 — comunicar situación a management "
                "y bloquear nuevos proyectos hasta subir a 50+."
            )
            priority_actions.append({
                "urgency": "esta semana",
                "action":  "Briefing a management sobre estado crítico del equipo",
                "owner":   "Tech Lead"
            })

        # Acciones por riesgo crítico
        for m in mitigation_plan:
            if m["severity"] in ("critica", "alta"):
                priority_actions.append({
                    "urgency": "inmediata" if m["severity"] == "critica" else "esta semana",
                    "action":  f"[{m['risk']}] {m['strategy'][:80]}",
                    "owner":   m["owner"]
                })

        # ── Veredicto ─────────────────────────────────────
        if critical >= 3 or score < 20:
            verdict = "ALTO RIESGO"
        elif critical >= 1 or high >= 3:
            verdict = "MODERADO"
        else:
            verdict = "BAJO RIESGO"

        # ── Prompt de IA ──────────────────────────────────
        top5 = sorted_risks[:5]
        risk_lines = "\n".join([
            f"  {i+1}. [{r.get('severity','?').upper()}] {r.get('title') or r.get('type','')} — {r.get('description','')[:80]}"
            for i, r in enumerate(top5)
        ])

        ai_prompt = f"""Actúa como Risk Manager senior especializado en equipos de ingeniería DevOps/Cloud.
Analiza los riesgos del equipo y genera un plan de mitigación detallado y accionable.

Estado actual:
- Health Score: {score}/100
- Total de riesgos: {total} ({critical} críticos, {high} altos, {medium} medios)
- Skills con SPOF: {', '.join(spofs) if spofs else 'ninguno'}

Top 5 riesgos prioritarios:
{risk_lines}

Genera:
1. Análisis de causa raíz de los 3 riesgos más críticos
2. Plan de mitigación a 30 días con hitos semanales
3. Matriz de riesgos: probabilidad × impacto
4. Métricas para saber cuándo el riesgo está bajo control
5. Recomendación de comunicación hacia management"""

        return self.build_result(
            findings, recommendations, verdict, priority_actions,
            extra={
                "total_risks":      total,
                "critical_count":   critical,
                "health_score":     score,
                "mitigation_plan":  mitigation_plan,
                "spof_skills":      spofs,
                "ai_prompt":        ai_prompt,
            }
        )

    def _suggest_owner(self, risk: dict) -> str:
        rtype = risk.get("type", "").lower()
        if "seguridad" in rtype or "security" in rtype:
            return "Tech Lead DevSecOps"
        if "capacidad" in rtype or "carga" in rtype or "burnout" in rtype:
            return "Manager + Tech Lead"
        if "skill" in rtype or "conocimiento" in rtype:
            return "Tech Lead"
        if "proyecto" in rtype or "entrega" in rtype:
            return "Tech Lead + PM"
        return "Tech Lead"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Risk Officer — analiza riesgos y genera plan de mitigación"
    )
    parser.add_argument("--severity", "-s", default="",
                        help="Filtrar por severidad: critica, alta, media, baja (separadas por coma)")
    args = parser.parse_args()

    filter_sev = [s.strip() for s in args.severity.split(",") if s.strip()] or None

    agent  = RiskOfficer()
    result = agent.run(filter_severity=filter_sev)
    agent.print_result(result)

    print("  💡 PROMPT PARA ANÁLISIS CON IA (Bedrock / Claude):")
    print("  " + "─"*56)
    for line in result["ai_prompt"].split("\n"):
        print(f"  {line}")
    print("  " + "─"*56 + "\n")