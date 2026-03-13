"""
ingestion/jira_ingest.py
Jira Cloud API v3 — usa /rest/api/3/search/jql (endpoint actual 2025+)

.env:
  JIRA_URL=https://liluvianette.atlassian.net
  JIRA_EMAIL=liluvianette@gmail.com
  JIRA_TOKEN=tu_api_token

config.yml:
  jira:
    enabled: true
    project_keys: []
    lookback_days: 30
"""

import os, json, yaml, requests
from base64 import b64encode
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


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Cliente Jira ──────────────────────────────────────────

class JiraClient:
    def __init__(self, base_url, email, token):
        self.base = base_url.rstrip("/")
        creds     = b64encode(f"{email}:{token}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {creds}",
            "Accept":        "application/json",
            "Content-Type":  "application/json",
        }

    def get(self, endpoint, params=None):
        url  = f"{self.base}/rest/api/3/{endpoint}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def verify_auth(self):
        """
        Verifica auth usando /mypermissions (más compatible que /myself en Jira Cloud free).
        """
        try:
            data = self.get("mypermissions", {"permissions": "BROWSE_PROJECTS"})
            perms = data.get("permissions", {})
            can_browse = perms.get("BROWSE_PROJECTS", {}).get("havePermission", False)
            if can_browse:
                print(f"  → Autenticado ✅ (BROWSE_PROJECTS: OK)")
            else:
                print(f"  → Autenticado pero sin permiso BROWSE_PROJECTS — revisa los permisos del proyecto")
            return True
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                raise ValueError(
                    "Token inválido o expirado.\n"
                    "  1. Ve a: https://id.atlassian.com/manage-profile/security/api-tokens\n"
                    "  2. Crea un nuevo token\n"
                    "  3. Actualiza JIRA_TOKEN en tu .env"
                )
            raise

    def get_projects(self):
        try:
            data = self.get("project/search", {"maxResults": 50})
            return data.get("values", [])
        except Exception as e:
            print(f"  ⚠️  No se pudieron listar proyectos: {e}")
            return []

    def search_issues(self, jql, fields, max_results=500):
        """
        GET /rest/api/3/search/jql — endpoint actual Jira Cloud (2025+)
        Requiere filtro de fecha en el JQL (Jira rechaza queries sin restricción).
        """
        all_issues = []
        next_page  = None

        while True:
            params = {
                "jql":        jql,
                "maxResults": min(100, max_results - len(all_issues)),
                "fields":     ",".join(fields),
            }
            if next_page:
                params["nextPageToken"] = next_page

            resp = requests.get(
                f"{self.base}/rest/api/3/search/jql",
                headers=self.headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data      = resp.json()
            issues    = data.get("issues", [])
            all_issues.extend(issues)
            next_page = data.get("nextPageToken")

            if not issues or not next_page:
                break

        return all_issues

    def get_worklogs(self, issue_key):
        try:
            data = self.get(f"issue/{issue_key}/worklog")
            return data.get("worklogs", [])
        except Exception:
            return []


# ── Normalización ─────────────────────────────────────────

def _parse_sprint_field(sprint_raw):
    """Extrae nombre y estado del sprint desde customfield_10020."""
    if not sprint_raw:
        return None
    # sprint_raw puede ser lista de objetos o strings
    sprint = sprint_raw[-1] if isinstance(sprint_raw, list) else sprint_raw
    if isinstance(sprint, dict):
        return {
            "name": sprint.get("name", ""),
            "state": sprint.get("state", ""),
            "id": sprint.get("id"),
        }
    if isinstance(sprint, str):
        # Formato legacy: "com.atlassian.greenhopper...name=Sprint 5,state=ACTIVE..."
        import re
        name_match = re.search(r"name=([^,\]]+)", sprint)
        state_match = re.search(r"state=([^,\]]+)", sprint)
        return {
            "name": name_match.group(1) if name_match else "",
            "state": state_match.group(1).lower() if state_match else "",
            "id": None,
        }
    return None


def normalize_issue(issue):
    f   = issue.get("fields", {})
    assignee = f.get("assignee") or {}
    parent   = f.get("parent")   or {}
    points   = (f.get("customfield_10016") or
                f.get("customfield_10028") or None)
    sprint   = _parse_sprint_field(f.get("customfield_10020"))

    time_estimate_sec = f.get("timeestimate") or 0
    time_spent_sec = f.get("timespent") or 0
    time_original_sec = f.get("timeoriginalestimate") or 0

    return {
        "key":             issue["key"],
        "summary":         f.get("summary", ""),
        "type":            f.get("issuetype", {}).get("name", ""),
        "status":          f.get("status", {}).get("name", ""),
        "status_category": f.get("status", {}).get("statusCategory", {}).get("name", ""),
        "assignee":        assignee.get("displayName", "Sin asignar"),
        "assignee_email":  assignee.get("emailAddress", ""),
        "story_points":    points,
        "priority":        f.get("priority", {}).get("name", ""),
        "created":         (f.get("created")        or "")[:10],
        "updated":         (f.get("updated")         or "")[:10],
        "resolved":        (f.get("resolutiondate")  or "")[:10] or None,
        "duedate":         (f.get("duedate")         or "")[:10] or None,
        "parent_key":      parent.get("key"),
        "labels":          f.get("labels", []),
        "project_key":     issue["key"].split("-")[0],
        "sprint":          sprint,
        "time_estimate_hours":  round(time_estimate_sec / 3600, 2) if time_estimate_sec else None,
        "time_spent_hours":     round(time_spent_sec / 3600, 2) if time_spent_sec else None,
        "time_original_hours":  round(time_original_sec / 3600, 2) if time_original_sec else None,
    }


def normalize_worklog(issue_key, wl):
    author = wl.get("author", {})
    try:
        comment = (wl.get("comment") or {}).get("content", [{}])[0]\
                   .get("content", [{}])[0].get("text", "")
    except Exception:
        comment = ""
    return {
        "issue_key":        issue_key,
        "author":           author.get("displayName", ""),
        "author_email":     author.get("emailAddress", ""),
        "time_spent_sec":   wl.get("timeSpentSeconds", 0),
        "time_spent_hours": round(wl.get("timeSpentSeconds", 0) / 3600, 2),
        "date":             (wl.get("started") or "")[:10],
        "comment":          comment,
    }


def compute_metrics(issues, worklogs):
    by_assignee = defaultdict(lambda: {"issues":0,"points":0,"hours":0.0,"done":0})
    by_status   = defaultdict(int)
    by_type     = defaultdict(int)
    by_project  = defaultdict(lambda: {"issues":0,"points":0})

    for i in issues:
        a = i["assignee"]
        by_assignee[a]["issues"] += 1
        by_assignee[a]["points"] += i["story_points"] or 0
        if i["status_category"] == "Done":
            by_assignee[a]["done"] += 1
        by_status[i["status"]]             += 1
        by_type[i["type"]]                 += 1
        by_project[i["project_key"]]["issues"] += 1
        by_project[i["project_key"]]["points"] += i["story_points"] or 0

    for w in worklogs:
        by_assignee[w["author"]]["hours"] += w["time_spent_hours"]

    tp = sum(i["story_points"] or 0 for i in issues)
    dp = sum(i["story_points"] or 0 for i in issues if i["status_category"] == "Done")

    return {
        "by_assignee": dict(by_assignee),
        "by_status":   dict(by_status),
        "by_type":     dict(by_type),
        "by_project":  dict(by_project),
        "totals": {
            "issues":             len(issues),
            "worklogs":           len(worklogs),
            "total_points":       tp,
            "done_points":        dp,
            "completion_pct":     round(dp/tp*100, 1) if tp else 0,
            "total_hours_logged": round(sum(w["time_spent_hours"] for w in worklogs), 1),
        },
    }


# ── Modo real ─────────────────────────────────────────────

def fetch_from_jira(config):
    url   = os.getenv("JIRA_URL",   config["jira"].get("base_url", ""))
    email = os.getenv("JIRA_EMAIL", "")
    token = os.getenv("JIRA_TOKEN", "")

    if not all([url, email, token]):
        raise ValueError("Faltan JIRA_URL, JIRA_EMAIL o JIRA_TOKEN en .env")

    client   = JiraClient(url, email, token)
    client.verify_auth()   # ← falla rápido si el token es inválido

    project_keys = list(config["jira"].get("project_keys", []))
    lookback     = int(config["jira"].get("lookback_days", 30))
    since_date   = (datetime.utcnow() - timedelta(days=lookback)).strftime("%Y-%m-%d")

    if not project_keys:
        print("  → Descubriendo proyectos...")
        projects     = client.get_projects()
        project_keys = [p["key"] for p in projects]
        print(f"  → Proyectos: {project_keys if project_keys else '(ninguno creado aún)'}")

    # JQL robusto
    if project_keys:
        keys_str = ", ".join(project_keys)
        jql = f"project IN ({keys_str}) AND updated >= '{since_date}' ORDER BY updated DESC"
    else:
        jql = f"updated >= '{since_date}' ORDER BY updated DESC"

    print(f"  → JQL: {jql}")

    fields = [
        "summary","status","issuetype","assignee",
        "customfield_10016","customfield_10028","customfield_10020",
        "created","updated","resolutiondate","parent","labels","priority",
        "duedate","timeestimate","timespent","timeoriginalestimate",
    ]

    raw_issues = client.search_issues(jql, fields)
    print(f"  → {len(raw_issues)} issues. Descargando worklogs...")

    issues   = [normalize_issue(i) for i in raw_issues]
    worklogs = []
    for idx, issue in enumerate(raw_issues):
        for wl in client.get_worklogs(issue["key"]):
            worklogs.append(normalize_worklog(issue["key"], wl))
        if (idx + 1) % 10 == 0:
            print(f"  → {idx+1}/{len(raw_issues)} procesados...")

    return {
        "source":        "jira_real",
        "jira_url":      url,
        "project_keys":  project_keys,
        "lookback_days": lookback,
        "issues":        issues,
        "worklogs":      worklogs,
        "metrics":       compute_metrics(issues, worklogs),
    }


# ── Modo mock ─────────────────────────────────────────────

def generate_mock_data():
    today = datetime.utcnow()
    def d(days): return (today - timedelta(days=days)).strftime("%Y-%m-%d")

    sprint_active = {"name": "Sprint 5", "state": "active", "id": 5}
    sprint_prev   = {"name": "Sprint 4", "state": "closed", "id": 4}

    issues = [
        {"key":"CDIP-1","summary":"Setup EKS cluster",          "type":"Story","status":"Done",       "status_category":"Done",       "assignee":"Alejandro Martínez","assignee_email":"amartinez@empresa.com","story_points":8, "priority":"High",    "created":d(40),"updated":d(10),"resolved":d(10),"duedate":d(-5),"parent_key":None,    "labels":["infra"],   "project_key":"CDIP","sprint":sprint_prev,"time_estimate_hours":16,"time_spent_hours":18,"time_original_hours":16},
        {"key":"CDIP-2","summary":"Configurar node groups",      "type":"Story","status":"Done",       "status_category":"Done",       "assignee":"Roberto Omena",     "assignee_email":"romena@empresa.com",   "story_points":5, "priority":"High",    "created":d(35),"updated":d(8), "resolved":d(8), "duedate":d(-3),"parent_key":"CDIP-1","labels":[],          "project_key":"CDIP","sprint":sprint_prev,"time_estimate_hours":10,"time_spent_hours":12,"time_original_hours":10},
        {"key":"CDIP-3","summary":"Cluster autoscaler",          "type":"Story","status":"In Progress","status_category":"In Progress","assignee":"Roberto Omena",     "assignee_email":"romena@empresa.com",   "story_points":5, "priority":"High",    "created":d(20),"updated":d(2), "resolved":None, "duedate":d(-2),"parent_key":"CDIP-1","labels":[],          "project_key":"CDIP","sprint":sprint_active,"time_estimate_hours":8,"time_spent_hours":4,"time_original_hours":10},
        {"key":"CDIP-4","summary":"Prometheus + Grafana",        "type":"Story","status":"In Progress","status_category":"In Progress","assignee":"Lucía Castro",      "assignee_email":"lcastro@empresa.com",  "story_points":8, "priority":"High",    "created":d(18),"updated":d(1), "resolved":None, "duedate":d(-5),"parent_key":None,    "labels":["obs"],     "project_key":"CDIP","sprint":sprint_active,"time_estimate_hours":16,"time_spent_hours":5,"time_original_hours":16},
        {"key":"SEC-1", "summary":"Auditoría IAM",               "type":"Story","status":"In Progress","status_category":"In Progress","assignee":"Carolina Valencia", "assignee_email":"cvalencia@empresa.com","story_points":13,"priority":"Critical","created":d(25),"updated":d(1), "resolved":None, "duedate":d(-7),"parent_key":None,    "labels":["security"],"project_key":"SEC","sprint":sprint_active,"time_estimate_hours":24,"time_spent_hours":10,"time_original_hours":24},
        {"key":"SEC-2", "summary":"Configurar AWS WAF",          "type":"Task", "status":"To Do",     "status_category":"To Do",      "assignee":"Carolina Valencia", "assignee_email":"cvalencia@empresa.com","story_points":5, "priority":"High",    "created":d(10),"updated":d(1), "resolved":None, "duedate":d(-10),"parent_key":"SEC-1", "labels":["security"],"project_key":"SEC","sprint":sprint_active,"time_estimate_hours":8,"time_spent_hours":None,"time_original_hours":8},
        {"key":"DEV-1", "summary":"Pipeline template Python",    "type":"Story","status":"Done",       "status_category":"Done",       "assignee":"Roberto Omena",     "assignee_email":"romena@empresa.com",   "story_points":3, "priority":"Medium",  "created":d(30),"updated":d(12),"resolved":d(12),"duedate":None,"parent_key":None,    "labels":["ci-cd"],   "project_key":"DEV","sprint":sprint_prev,"time_estimate_hours":6,"time_spent_hours":5,"time_original_hours":6},
        {"key":"DEV-2", "summary":"Pipeline template Node.js",   "type":"Story","status":"In Progress","status_category":"In Progress","assignee":"Diego Quiroga",     "assignee_email":"dquiroga@empresa.com", "story_points":3, "priority":"Medium",  "created":d(15),"updated":d(2), "resolved":None, "duedate":d(-3),"parent_key":None,    "labels":["ci-cd"],   "project_key":"DEV","sprint":sprint_active,"time_estimate_hours":6,"time_spent_hours":2,"time_original_hours":6},
        {"key":"DEV-3", "summary":"SAST en pipelines",           "type":"Task", "status":"To Do",     "status_category":"To Do",      "assignee":"Diego Quiroga",     "assignee_email":"dquiroga@empresa.com", "story_points":5, "priority":"High",    "created":d(8), "updated":d(1), "resolved":None, "duedate":d(-8),"parent_key":"DEV-2", "labels":["security"],"project_key":"DEV","sprint":sprint_active,"time_estimate_hours":10,"time_spent_hours":None,"time_original_hours":10},
        {"key":"OPS-1", "summary":"Incident: latencia RDS",      "type":"Bug",  "status":"Done",       "status_category":"Done",       "assignee":"Alejandro Martínez","assignee_email":"amartinez@empresa.com","story_points":None,"priority":"Critical","created":d(5),"updated":d(4),"resolved":d(4), "duedate":None,"parent_key":None,    "labels":["incident"],"project_key":"OPS","sprint":None,"time_estimate_hours":None,"time_spent_hours":3,"time_original_hours":None},
    ]
    worklogs = [
        {"issue_key":"CDIP-1","author":"Alejandro Martínez","author_email":"amartinez@empresa.com","time_spent_sec":28800,"time_spent_hours":8.0, "date":d(15),"comment":"Diseño arquitectura"},
        {"issue_key":"CDIP-2","author":"Roberto Omena",     "author_email":"romena@empresa.com",   "time_spent_sec":21600,"time_spent_hours":6.0, "date":d(12),"comment":""},
        {"issue_key":"CDIP-3","author":"Roberto Omena",     "author_email":"romena@empresa.com",   "time_spent_sec":14400,"time_spent_hours":4.0, "date":d(5), "comment":"En progreso"},
        {"issue_key":"CDIP-4","author":"Lucía Castro",      "author_email":"lcastro@empresa.com",  "time_spent_sec":18000,"time_spent_hours":5.0, "date":d(3), "comment":"Dashboards base"},
        {"issue_key":"SEC-1", "author":"Carolina Valencia", "author_email":"cvalencia@empresa.com","time_spent_sec":36000,"time_spent_hours":10.0,"date":d(7), "comment":"200 políticas revisadas"},
        {"issue_key":"DEV-1", "author":"Roberto Omena",     "author_email":"romena@empresa.com",   "time_spent_sec":10800,"time_spent_hours":3.0, "date":d(14),"comment":"Template completo"},
        {"issue_key":"DEV-2", "author":"Diego Quiroga",     "author_email":"dquiroga@empresa.com", "time_spent_sec":7200, "time_spent_hours":2.0, "date":d(4), "comment":""},
        {"issue_key":"OPS-1", "author":"Alejandro Martínez","author_email":"amartinez@empresa.com","time_spent_sec":10800,"time_spent_hours":3.0, "date":d(5), "comment":"Query index faltante"},
    ]
    return {"source":"mock","issues":issues,"worklogs":worklogs,"metrics":compute_metrics(issues,worklogs)}


# ── Runner ────────────────────────────────────────────────

def run():
    print("📥 Ingesta Jira...")
    config = load_config()

    if config["jira"]["enabled"]:
        print("  → Modo: Jira API real")
        try:
            data = fetch_from_jira(config)
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
            print("  → Fallback a datos mock")
            data = generate_mock_data()
    else:
        print("  → Modo: mock (jira.enabled = false)")
        data = generate_mock_data()

    data["generated_at"] = datetime.utcnow().isoformat()
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "jira_data.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    m = data["metrics"]["totals"]
    print(f"  ✅ {m['issues']} issues | {m['worklogs']} worklogs | {m['total_hours_logged']}h → {out_file}")
    return data


if __name__ == "__main__":
    run()