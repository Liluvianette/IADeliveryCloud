"""
ingestion/jira_ingest.py
Conecta con Jira API y descarga epics, stories, tasks y worklogs.
Requiere: JIRA_URL, JIRA_EMAIL, JIRA_TOKEN en variables de entorno o .env

Si jira.enabled = false en config.yml, genera datos simulados para desarrollo.
"""

import os
import json
import yaml
from pathlib import Path
from datetime import datetime, timedelta

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
# MODO REAL: conexión a Jira
# ──────────────────────────────────────────────

def fetch_from_jira(config: dict) -> dict:
    """Descarga issues y worklogs reales de Jira."""
    try:
        from jira import JIRA
    except ImportError:
        raise ImportError("Instala jira: pip install jira")

    url   = os.getenv("JIRA_URL",   config["jira"]["base_url"])
    email = os.getenv("JIRA_EMAIL", "")
    token = os.getenv("JIRA_TOKEN", "")

    if not all([url, email, token]):
        raise ValueError("Faltan credenciales Jira. Define JIRA_URL, JIRA_EMAIL, JIRA_TOKEN en .env")

    client  = JIRA(server=url, basic_auth=(email, token))
    results = {"issues": [], "worklogs": []}

    for project_key in config["jira"]["project_keys"]:
        print(f"  → Descargando issues de proyecto: {project_key}")
        issues = client.search_issues(
            f"project={project_key} AND updated >= -{config['git']['lookback_days']}d",
            maxResults=500,
            fields="summary,status,issuetype,story_points,assignee,created,updated,parent"
        )
        for issue in issues:
            results["issues"].append({
                "key":        issue.key,
                "summary":    issue.fields.summary,
                "type":       issue.fields.issuetype.name,
                "status":     issue.fields.status.name,
                "assignee":   getattr(issue.fields.assignee, "name", None),
                "points":     getattr(issue.fields, "story_points", None),
                "created":    issue.fields.created,
                "updated":    issue.fields.updated,
                "parent":     getattr(issue.fields, "parent", {}).get("key") if hasattr(issue.fields, "parent") else None,
            })

            worklogs = client.worklogs(issue.key)
            for wl in worklogs:
                results["worklogs"].append({
                    "issue_key":       issue.key,
                    "author":          wl.author.name,
                    "time_spent_sec":  wl.timeSpentSeconds,
                    "date":            wl.started,
                    "comment":         getattr(wl, "comment", ""),
                })

    return results


# ──────────────────────────────────────────────
# MODO SIMULADO: datos ficticios para desarrollo
# ──────────────────────────────────────────────

def generate_mock_data() -> dict:
    """Genera datos Jira ficticios realistas para desarrollo sin conexión."""
    today = datetime.utcnow()

    issues = [
        {"key": "CLOUD-101", "summary": "Diseñar arquitectura EKS",       "type": "Epic",  "status": "Done",        "assignee": "cmendoza",  "points": 13, "parent": None},
        {"key": "CLOUD-102", "summary": "Configurar node groups",          "type": "Story", "status": "Done",        "assignee": "cmendoza",  "points": 8,  "parent": "CLOUD-101"},
        {"key": "CLOUD-103", "summary": "Implementar cluster autoscaler",  "type": "Story", "status": "In Progress", "assignee": "jmorales",  "points": 5,  "parent": "CLOUD-101"},
        {"key": "CLOUD-104", "summary": "Configurar Prometheus + Grafana", "type": "Story", "status": "In Progress", "assignee": "jmorales",  "points": 8,  "parent": "CLOUD-101"},
        {"key": "CLOUD-105", "summary": "Setup Helm charts core apps",     "type": "Story", "status": "To Do",       "assignee": "lrodriguez","points": 5,  "parent": "CLOUD-101"},
        {"key": "DEVOPS-50", "summary": "Pipeline template Python",        "type": "Story", "status": "Done",        "assignee": "lrodriguez","points": 3,  "parent": None},
        {"key": "DEVOPS-51", "summary": "Pipeline template Node.js",       "type": "Story", "status": "In Progress", "assignee": "aperez",    "points": 3,  "parent": None},
        {"key": "DEVOPS-52", "summary": "Configurar SAST en pipelines",    "type": "Task",  "status": "To Do",       "assignee": "rcastillo", "points": 5,  "parent": None},
        {"key": "SEC-10",    "summary": "Configurar AWS WAF rules",        "type": "Story", "status": "In Progress", "assignee": "rcastillo", "points": 8,  "parent": None},
        {"key": "SEC-11",    "summary": "Revisar políticas IAM",           "type": "Story", "status": "To Do",       "assignee": "rcastillo", "points": 5,  "parent": None},
        {"key": "OPS-200",   "summary": "Incident - DB latency spike",     "type": "Bug",   "status": "Done",        "assignee": "jmorales",  "points": None, "parent": None},
        {"key": "OPS-201",   "summary": "Incident - Memory leak en pod",   "type": "Bug",   "status": "Done",        "assignee": "jmorales",  "points": None, "parent": None},
    ]

    for issue in issues:
        issue["created"] = (today - timedelta(days=45)).isoformat()
        issue["updated"] = (today - timedelta(days=2)).isoformat()

    worklogs = [
        {"issue_key": "CLOUD-102", "author": "cmendoza",  "time_spent_sec": 14400, "date": (today - timedelta(days=10)).isoformat(), "comment": "Configuración inicial"},
        {"issue_key": "CLOUD-103", "author": "jmorales",  "time_spent_sec": 10800, "date": (today - timedelta(days=8)).isoformat(),  "comment": ""},
        {"issue_key": "CLOUD-104", "author": "jmorales",  "time_spent_sec": 18000, "date": (today - timedelta(days=5)).isoformat(),  "comment": "Dashboards iniciales"},
        {"issue_key": "CLOUD-105", "author": "lrodriguez", "time_spent_sec": 7200, "date": (today - timedelta(days=3)).isoformat(),  "comment": ""},
        {"issue_key": "DEVOPS-50", "author": "lrodriguez", "time_spent_sec": 10800, "date": (today - timedelta(days=12)).isoformat(),"comment": "Template listo"},
        {"issue_key": "DEVOPS-51", "author": "aperez",    "time_spent_sec": 7200,  "date": (today - timedelta(days=4)).isoformat(),  "comment": ""},
        {"issue_key": "SEC-10",    "author": "rcastillo", "time_spent_sec": 21600, "date": (today - timedelta(days=6)).isoformat(),  "comment": "Reglas WAF base"},
        {"issue_key": "OPS-200",   "author": "jmorales",  "time_spent_sec": 5400,  "date": (today - timedelta(days=15)).isoformat(), "comment": "Resolved - query slow"},
        {"issue_key": "OPS-201",   "author": "jmorales",  "time_spent_sec": 3600,  "date": (today - timedelta(days=9)).isoformat(),  "comment": "Memory limit ajustado"},
    ]

    return {"issues": issues, "worklogs": worklogs}


# ──────────────────────────────────────────────
# RUNNER
# ──────────────────────────────────────────────

def run() -> dict:
    print("📥 Ingesta Jira...")
    config = load_config()

    if config["jira"]["enabled"]:
        print("  → Modo: Jira API real")
        data = fetch_from_jira(config)
    else:
        print("  → Modo: datos simulados (jira.enabled = false)")
        data = generate_mock_data()

    data["generated_at"] = datetime.utcnow().isoformat()
    data["mode"]         = "real" if config["jira"]["enabled"] else "mock"

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "jira_data.json"
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    issues_count   = len(data["issues"])
    worklogs_count = len(data["worklogs"])
    print(f"  ✅ {issues_count} issues, {worklogs_count} worklogs → {out_file}")
    return data


if __name__ == "__main__":
    run()
