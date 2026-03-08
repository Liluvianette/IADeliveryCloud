"""
ingestion/git_ingest.py
Analiza repositorios Git para extraer métricas de actividad por autor.
Soporta repos locales (modo offline) y GitHub API (modo real).

Si git.enabled = false en config.yml, genera datos simulados.
"""

import os
import json
import yaml
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


CONFIG_PATH = Path(__file__).parent.parent / "config.yml"
OUTPUT_PATH = Path(__file__).parent.parent / "output"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ──────────────────────────────────────────────
# MODO REAL: analiza repos locales con git log
# ──────────────────────────────────────────────

def analyze_local_repo(repo_path: str, lookback_days: int) -> list[dict]:
    """Extrae commits de un repo local usando git log."""
    since = (datetime.utcnow() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    cmd = [
        "git", "-C", repo_path, "log",
        f"--since={since}",
        "--format=%H|%ae|%an|%ad|%s",
        "--date=short"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "hash":    parts[0][:8],
                    "email":   parts[1],
                    "author":  parts[2],
                    "date":    parts[3],
                    "message": parts[4],
                    "repo":    Path(repo_path).name,
                })
        return commits
    except Exception as e:
        print(f"  ⚠️  Error analizando {repo_path}: {e}")
        return []


def fetch_from_github_api(config: dict) -> list[dict]:
    """Usa GitHub API para repos remotos."""
    try:
        import requests
    except ImportError:
        raise ImportError("Instala requests: pip install requests")

    token   = os.getenv("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}"} if token else {}
    commits = []
    since   = (datetime.utcnow() - timedelta(days=config["git"]["lookback_days"])).isoformat() + "Z"

    for repo in config["git"]["repos"]:
        url = f"https://api.github.com/repos/{repo}/commits"
        try:
            resp = requests.get(url, headers=headers, params={"since": since, "per_page": 100})
            for c in resp.json():
                if not isinstance(c, dict):
                    continue
                commits.append({
                    "hash":    c["sha"][:8],
                    "email":   c["commit"]["author"]["email"],
                    "author":  c["commit"]["author"]["name"],
                    "date":    c["commit"]["author"]["date"][:10],
                    "message": c["commit"]["message"].split("\n")[0],
                    "repo":    repo.split("/")[-1],
                })
        except Exception as e:
            print(f"  ⚠️  Error con repo {repo}: {e}")

    return commits


# ──────────────────────────────────────────────
# MODO SIMULADO
# ──────────────────────────────────────────────

def generate_mock_commits() -> list[dict]:
    """Genera commits ficticios realistas para desarrollo."""
    today   = datetime.utcnow()
    authors = {
        "cmendoza":  ("Carlos Méndoza",  "cmendoza@example.com"),
        "jmorales":  ("Jorge Morales",   "jmorales@example.com"),
        "lrodriguez":("Laura Rodríguez", "lrodriguez@example.com"),
        "aperez":    ("Ana Pérez",       "aperez@example.com"),
        "rcastillo": ("Rodrigo Castillo","rcastillo@example.com"),
    }
    templates = [
        ("infra-eks-platform",    ["cmendoza", "jmorales", "lrodriguez"], [
            "feat: add cluster autoscaler config",
            "fix: node group taints corrected",
            "chore: update terraform provider versions",
            "feat: implement spot instance support",
            "fix: RBAC permissions for monitoring namespace",
        ]),
        ("helm-charts-core",      ["cmendoza", "lrodriguez"], [
            "feat: add values override for staging",
            "fix: ingress annotations for ALB",
            "chore: bump chart versions",
        ]),
        ("github-actions-templates", ["lrodriguez", "aperez", "rcastillo"], [
            "feat: Python pipeline template v1",
            "feat: add SAST scan step",
            "fix: cache key collision on matrix builds",
            "feat: Node.js pipeline draft",
            "chore: update actions/checkout to v4",
        ]),
        ("security-policies",     ["rcastillo", "cmendoza"], [
            "feat: WAF managed rules - OWASP core",
            "feat: IAM policy least-privilege review",
            "fix: overly permissive S3 bucket policy",
            "docs: add compliance mapping NIST-800",
        ]),
    ]

    commits = []
    import random
    random.seed(42)

    for repo, active_authors, messages in templates:
        for i in range(random.randint(8, 20)):
            author_id        = random.choice(active_authors)
            name, email      = authors[author_id]
            days_ago         = random.randint(0, 29)
            commit_date      = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            commits.append({
                "hash":    f"{author_id[:2]}{i:04x}"[:8],
                "email":   email,
                "author":  name,
                "author_id": author_id,
                "date":    commit_date,
                "message": random.choice(messages),
                "repo":    repo,
            })

    return commits


def aggregate_by_author(commits: list[dict]) -> dict:
    """Agrupa métricas de commits por autor."""
    by_author = defaultdict(lambda: {
        "total_commits": 0,
        "repos": set(),
        "commits_by_week": defaultdict(int),
        "recent_messages": [],
    })

    for c in commits:
        aid = c.get("author_id") or c["email"]
        by_author[aid]["total_commits"] += 1
        by_author[aid]["repos"].add(c["repo"])
        week = c["date"][:7]   # YYYY-MM
        by_author[aid]["commits_by_week"][week] += 1
        if len(by_author[aid]["recent_messages"]) < 5:
            by_author[aid]["recent_messages"].append(c["message"])

    return {
        aid: {
            **data,
            "repos":           list(data["repos"]),
            "commits_by_week": dict(data["commits_by_week"]),
        }
        for aid, data in by_author.items()
    }


# ──────────────────────────────────────────────
# RUNNER
# ──────────────────────────────────────────────

def run() -> dict:
    print("📥 Ingesta Git...")
    config = load_config()

    if config["git"]["enabled"]:
        print("  → Modo: GitHub API real")
        commits = fetch_from_github_api(config)
    else:
        print("  → Modo: datos simulados (git.enabled = false)")
        commits = generate_mock_commits()

    by_author = aggregate_by_author(commits)

    output = {
        "generated_at":  datetime.utcnow().isoformat(),
        "mode":          "real" if config["git"]["enabled"] else "mock",
        "total_commits": len(commits),
        "lookback_days": config["git"]["lookback_days"],
        "commits":       commits,
        "by_author":     by_author,
    }

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "git_data.json"
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)

    print(f"  ✅ {len(commits)} commits de {len(by_author)} autores → {out_file}")
    return output


if __name__ == "__main__":
    run()
