"""
analysis/skills_matrix.py
Genera la matriz de habilidades del equipo para visualización en el dashboard.
Identifica fortalezas, brechas y distribución de conocimiento.
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from collections import defaultdict


OUTPUT_PATH = Path(__file__).parent.parent / "output"


SKILL_LABELS = {
    "terraform":     "Terraform",
    "kubernetes":    "Kubernetes",
    "aws":           "AWS",
    "gcp":           "GCP",
    "azure":         "Azure",
    "docker":        "Docker",
    "python":        "Python",
    "bash":          "Bash/Shell",
    "ci_cd":         "CI/CD",
    "observability": "Observabilidad",
    "security":      "Seguridad Cloud",
    "architecture":  "Arquitectura",
    "git":           "Git",
    "ansible":       "Ansible",
}

LEVEL_LABELS = {1: "Básico", 2: "Intermedio", 3: "Avanzado", 4: "Experto"}


def run() -> dict:
    print("⚙️  Generando matriz de skills...")

    with open(OUTPUT_PATH / "team_raw.json") as f:
        team = json.load(f)["team"]

    skills_data = {}

    for skill_id, skill_label in SKILL_LABELS.items():
        members_with_skill = []
        level_distribution = defaultdict(int)
        total_level        = 0

        for m in team:
            level = m["skills"].get(skill_id, 0)
            if level > 0:
                members_with_skill.append({
                    "id":     m["id"],
                    "name":   m["name"],
                    "level":  level,
                    "label":  LEVEL_LABELS.get(level, "?"),
                })
                level_distribution[level] += 1
                total_level += level

        count         = len(members_with_skill)
        experts_count = sum(1 for m in members_with_skill if m["level"] >= 3)
        avg_level     = round(total_level / count, 2) if count > 0 else 0

        # Determinar si es SPOF (solo 1 experto)
        is_spof = experts_count == 1

        # Score de cobertura: qué tan distribuido está el conocimiento
        coverage_score = min(100, round((count / len(team)) * 100))

        skills_data[skill_id] = {
            "id":                skill_id,
            "label":             skill_label,
            "members":           members_with_skill,
            "member_count":      count,
            "experts_count":     experts_count,
            "avg_level":         avg_level,
            "coverage_score":    coverage_score,
            "is_spof":           is_spof,
            "level_distribution":dict(level_distribution),
        }

    # Ranking de skills por cobertura
    skills_sorted = sorted(
        skills_data.values(),
        key=lambda s: (s["coverage_score"], s["avg_level"]),
        reverse=True
    )

    output = {
        "generated_at":    datetime.utcnow().isoformat(),
        "total_skills":    len(skills_data),
        "total_members":   len(team),
        "spof_skills":     [s["id"] for s in skills_sorted if s["is_spof"]],
        "strong_skills":   [s["id"] for s in skills_sorted if s["coverage_score"] >= 60],
        "weak_skills":     [s["id"] for s in skills_sorted if s["coverage_score"] < 40],
        "skills":          skills_data,
        "skills_ranked":   [s["id"] for s in skills_sorted],
    }

    out_file = OUTPUT_PATH / "skills_matrix.json"
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    spof_count = len(output["spof_skills"])
    print(f"  ✅ {len(skills_data)} skills analizados | {spof_count} SPOFs detectados → {out_file}")
    return output


if __name__ == "__main__":
    run()
