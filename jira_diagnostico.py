"""
jira_diagnostico.py
Prueba los endpoints de Jira para encontrar cuáles funcionan
con tu instancia y token actual.

Uso: python jira_diagnostico.py
"""

import os, requests
from base64 import b64encode

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

URL   = os.getenv("JIRA_URL",   "https://liluvianette.atlassian.net")
EMAIL = os.getenv("JIRA_EMAIL", "")
TOKEN = os.getenv("JIRA_TOKEN", "")

creds   = b64encode(f"{EMAIL}:{TOKEN}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {creds}",
    "Accept":        "application/json",
    "Content-Type":  "application/json",
}

def test(label, method, endpoint, body=None):
    url = f"{URL}{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url, headers=HEADERS, timeout=15)
        else:
            r = requests.post(url, headers=HEADERS, json=body, timeout=15)

        icon = "✅" if r.status_code < 400 else "❌"
        print(f"  {icon} [{r.status_code}] {method} {endpoint}")

        if r.status_code < 400:
            data = r.json()
            # Mostrar preview útil
            if isinstance(data, list):
                print(f"       → lista con {len(data)} items")
                if data: print(f"       → primer item keys: {list(data[0].keys())[:5]}")
            elif isinstance(data, dict):
                keys = list(data.keys())[:6]
                print(f"       → keys: {keys}")
                if "values" in data:
                    print(f"       → values count: {len(data['values'])}")
                if "issues" in data:
                    print(f"       → issues count: {len(data['issues'])}, total: {data.get('total',0)}")
            return True, data
        else:
            try:
                print(f"       → {r.json()}")
            except Exception:
                print(f"       → {r.text[:120]}")
            return False, None

    except Exception as e:
        print(f"  💥 {method} {endpoint} → {e}")
        return False, None

print("\n" + "═"*60)
print("  🔍 Jira API Diagnóstico")
print(f"  URL:   {URL}")
print(f"  Email: {EMAIL}")
print("═"*60)

# ── 1. Verificar autenticación ──
print("\n1. Autenticación:")
ok, data = test("Myself",         "GET", "/rest/api/3/myself")
ok, data = test("Server info",    "GET", "/rest/api/3/serverInfo")

# ── 2. Proyectos ──
print("\n2. Proyectos:")
test("Projects v3 search",  "GET", "/rest/api/3/project/search?maxResults=10")
test("Projects v2",         "GET", "/rest/api/2/project")
test("Projects v3 list",    "GET", "/rest/api/3/project?maxResults=10")

# ── 3. Búsqueda de issues ──
print("\n3. Búsqueda de issues:")
jql_body = {"jql": "ORDER BY created DESC", "maxResults": 5,
            "fields": ["summary", "status", "assignee"]}
test("Search POST v3",       "POST", "/rest/api/3/issue/search",       jql_body)
test("Search POST v2",       "POST", "/rest/api/2/issue/search",       jql_body)
test("Search GET v3",        "GET",  "/rest/api/3/search?jql=ORDER+BY+created+DESC&maxResults=5")
test("Search GET v2",        "GET",  "/rest/api/2/search?jql=ORDER+BY+created+DESC&maxResults=5")

# ── 4. Si encontró proyectos, probar JQL con proyecto ──
print("\n4. Test con proyecto específico:")
test("Issues del proyecto",  "POST", "/rest/api/3/issue/search",
     {"jql": "project IS NOT EMPTY ORDER BY created DESC", "maxResults": 5,
      "fields": ["summary", "status", "issuetype", "assignee"]})

print("\n" + "═"*60)
print("  Diagnóstico completado.")
print("  Comparte el output completo para identificar el problema.")
print("═"*60 + "\n")

# ── 5. Endpoint correcto según migración oficial ──
print("\n5. Endpoint nuevo /search/jql:")
test("search/jql GET",  "GET",  "/rest/api/3/search/jql?jql=ORDER+BY+created+DESC&maxResults=5")

# ── 6. search/jql con filtro de fecha obligatorio ──
print("\n6. search/jql con filtro correcto:")
from datetime import datetime, timedelta
since = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
test("search/jql con fecha", "GET",
     f"/rest/api/3/search/jql?jql=updated+%3E%3D+%27{since}%27+ORDER+BY+updated+DESC&maxResults=5&fields=summary,status,assignee")

# ── 7. Verificar token con endpoint alternativo ──
print("\n7. Verificar token:")
test("Permissions",  "GET", "/rest/api/3/mypermissions?permissions=BROWSE_PROJECTS")
test("My filters",   "GET", "/rest/api/3/filter/my?maxResults=5")