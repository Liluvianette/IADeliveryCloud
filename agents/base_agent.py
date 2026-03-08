"""
agents/base_agent.py
Clase base para todos los agentes de análisis.
Todos los agentes heredan de BaseAgent.
"""

import json
from pathlib import Path
from datetime import datetime


OUTPUT_PATH = Path(__file__).parent.parent / "output"


class BaseAgent:
    name:  str = "base"
    role:  str = "Base Agent"
    emoji: str = "🤖"

    def __init__(self):
        self._data = {}

    # ── Carga de datos ────────────────────────────────────

    def _load(self, filename: str) -> dict:
        """Carga un JSON del directorio output/."""
        path = OUTPUT_PATH / filename
        if not path.exists():
            raise FileNotFoundError(
                f"No se encontró {filename}. "
                "Ejecuta primero: python run.py --skip-ai"
            )
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def load_all(self):
        """Carga todos los JSONs necesarios."""
        self._data["capacity"] = self._load("team_capacity.json")
        self._data["health"]   = self._load("team_health.json")
        self._data["skills"]   = self._load("skills_matrix.json")
        self._data["projects"] = self._load("projects_raw.json")
        try:
            self._data["git"]  = self._load("git_data.json")
        except FileNotFoundError:
            self._data["git"]  = {}
        try:
            self._data["jira"] = self._load("jira_data.json")
        except FileNotFoundError:
            self._data["jira"] = {}
        return self

    # ── Helpers de negocio ────────────────────────────────

    @property
    def summary(self) -> dict:
        return self._data["capacity"].get("summary", {})

    @property
    def team(self) -> list:
        return self._data["capacity"].get("team", [])

    @property
    def risks(self) -> list:
        return self._data["health"].get("risks", [])

    @property
    def health_score(self) -> int:
        h = self._data["health"].get("health_score", {})
        return h.get("score", 0) if isinstance(h, dict) else int(h or 0)

    @property
    def projects(self) -> list:
        return self._data["projects"].get("projects", [])

    @property
    def skills(self) -> dict:
        return self._data["skills"].get("skills", {})

    def team_load_pct(self) -> float:
        """Retorna carga del equipo en % (0-200+)."""
        return round(self.summary.get("team_load_percent", 0) * 100, 1)

    def member_load_pct(self, member: dict) -> float:
        return round((member.get("load_percent", 0) or 0) * 100, 1)

    def available_hours(self, member: dict) -> float:
        return (member.get("capacity") or {}).get("available_hours", 0)

    def free_hours(self, member: dict) -> float:
        alloc = member.get("allocated_hours", 0) or 0
        avail = self.available_hours(member)
        return max(avail - alloc, 0)

    def active_projects(self) -> list:
        return [p for p in self.projects if p.get("status") == "activo"]

    def critical_risks(self) -> list:
        return [r for r in self.risks if r.get("severity") == "critica"]

    def spof_skills(self) -> list:
        return [s for s, data in self.skills.items() if data.get("is_spof")]

    def skill_coverage(self, skill_data: dict) -> float:
        """Retorna coverage en 0-100, soportando coverage_score o coverage_percent."""
        return skill_data.get("coverage_score") or skill_data.get("coverage_percent") or 0

    # ── Output ────────────────────────────────────────────

    def build_result(self, findings: list, recommendations: list,
                     verdict: str, priority_actions: list,
                     extra: dict = None) -> dict:
        result = {
            "agent":            self.name,
            "role":             self.role,
            "timestamp":        datetime.now().isoformat(),
            "verdict":          verdict,
            "findings":         findings,
            "recommendations":  recommendations,
            "priority_actions": priority_actions,
        }
        if extra:
            result.update(extra)
        return result

    def print_result(self, result: dict):
        """Imprime el resultado en consola de forma legible."""
        verdict_icons = {
            "VIABLE":       "✅",
            "NO VIABLE":    "🚫",
            "CONDICIONAL":  "⚠️ ",
            "CRÍTICO":      "🔴",
            "MODERADO":     "🟡",
            "SALUDABLE":    "🟢",
            "BAJO RIESGO":  "🟢",
            "ALTO RIESGO":  "🔴",
        }
        icon = verdict_icons.get(result["verdict"], "📋")

        print(f"\n{'═'*60}")
        print(f"  {self.emoji} {self.role}")
        print(f"{'═'*60}")
        print(f"\n  Veredicto: {icon} {result['verdict']}\n")

        print("  HALLAZGOS:")
        for f in result["findings"]:
            sev = f.get("severity", "info")
            dot = {"critica":"🔴","alta":"🟠","media":"🟡","baja":"🟢","info":"ℹ️ "}.get(sev,"•")
            print(f"    {dot} {f['title']}")
            print(f"       {f['detail']}")

        print("\n  RECOMENDACIONES:")
        for i, r in enumerate(result["recommendations"], 1):
            print(f"    {i}. {r}")

        print("\n  ACCIONES PRIORITARIAS:")
        for i, a in enumerate(result["priority_actions"], 1):
            print(f"    {i}. [{a.get('urgency','—').upper()}] {a['action']}")
            if a.get("owner"):
                print(f"          → Responsable: {a['owner']}")

        print(f"\n{'═'*60}\n")

    def run(self, **kwargs) -> dict:
        """Sobrescribir en cada agente."""
        raise NotImplementedError