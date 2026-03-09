# AGENT_CONTEXT — Cloud Delivery Intelligence Platform
> Pega este archivo al inicio de cualquier sesión con Claude en VS Code para retomar sin perder contexto.
> Última actualización: 2026-03-08

---

## ¿Qué es este proyecto?

Herramienta interna para una Tech Lead de DevOps. Visualiza capacidad del equipo, detecta riesgos, analiza carga y estima esfuerzo de nuevos proyectos.

**Arquitectura:** 100% estática — Python local genera JSONs → GitHub Pages sirve el dashboard. Sin servidor, sin base de datos.

---

## Repositorio y accesos

| Dato | Valor |
|---|---|
| Repo | https://github.com/Liluvianette/IADeliveryCloud |
| GitHub Pages | pendiente (GitHub Enterprise) |
| Jira | https://liluvianette.atlassian.net / liluvianette@gmail.com |
| Stack | Python 3.14, YAML, JSON, HTML/JS, Chart.js |

---

## Estructura de archivos

```
IADeliveryCloud/
├── .env                     ← NUNCA commitear
├── config.yml               ← jira/git/ai enabled flags
├── run.py                   ← orquestador principal
├── serve_local.py           ← python serve_local.py → localhost:8080
├── jira_diagnostico.py
├── data/
│   ├── team.yml
│   ├── projects.yml
│   └── discovery.md
├── ingestion/
│   ├── team_loader.py
│   ├── jira_ingest.py       ← GET /rest/api/3/search/jql
│   └── git_ingest.py        ← GitHub API v3
├── analysis/
│   ├── capacity_engine.py   → output/team_capacity.json
│   ├── risk_engine.py       → output/team_health.json
│   ├── skills_matrix.py     → output/skills_matrix.json
│   └── estimation_engine.py
├── ai/
│   ├── discovery_analyzer.py  ← modo mock
│   └── project_classifier.py  ← clasificador por reglas/keywords
├── agents/                  ← 4 agentes de análisis
│   ├── base_agent.py        ← clase base
│   ├── tech_lead.py         ← viabilidad de proyecto nuevo
│   ├── capacity_analyst.py  ← redistribución de carga
│   ├── risk_officer.py      ← mitigación de riesgos
│   └── estimator.py         ← estimación con fases + YAML
├── dashboard/
│   ├── index.html           ← dashboard dark-mode
│   ├── report.html          ← reporte ejecutivo HTML→PDF
│   └── data/*.json
└── output/*.json            ← fuente de verdad (generados por run.py)
```

---

## Comandos

```bash
# Siempre primero — genera los JSONs
python run.py --skip-ai

# Dashboard y reporte
python serve_local.py      # localhost:8080 y localhost:8080/report.html

# Clasificador
python ai/project_classifier.py --text "descripción" --title "Nombre"

# Agentes individuales (requieren output/*.json)
python agents/tech_lead.py --project "Nombre" --hours 200 --skills kubernetes,terraform
python agents/capacity_analyst.py
python agents/risk_officer.py --severity critica,alta
python agents/estimator.py                                  # interactivo
python agents/estimator.py --quick "Nombre" --type iac --complexity alto --team 3

# Orquestador consolidado (requiere output/*.json)
python run_agents.py                                        # capacity + risk + tech_lead
python run_agents.py --quick "Nombre" --type iac            # los 4 agentes (estimator rápido)
python run_agents.py --with-estimator                       # los 4 agentes (estimator interactivo)
python run_agents.py --agent capacity                       # solo 1 agente
python run_agents.py --agent risk --severity critica,alta
python run_agents.py --agent tech_lead --project "X" --hours 200 --skills k8s,tf
# → genera output/agents_report.json
```

---

## .env

```
JIRA_URL=https://liluvianette.atlassian.net
JIRA_EMAIL=liluvianette@gmail.com
JIRA_TOKEN=<token>
GITHUB_TOKEN=<token>
ANTHROPIC_API_KEY=       # fase futura Bedrock
```

---

## config.yml actual

```yaml
jira:
  enabled: true
  base_url: "https://liluvianette.atlassian.net"
  project_keys: []   # vacío = auto-descubre
  lookback_days: 30
git:
  enabled: true
  repos: []          # vacío = auto-descubre
  lookback_days: 30
ai:
  enabled: false
```

---

## Equipo (datos dummy — reemplazar con reales)

| ID | Nombre | Rol | Seniority | Disponibilidad |
|---|---|---|---|---|
| amartinez | Alejandro Martínez | Tech Lead Cloud | Senior | 70% |
| cvalencia | Carolina Valencia | Tech Lead DevSecOps | Senior | 75% |
| romena | Roberto Omena | DevOps Engineer | Semi-senior | 90% |
| lcastro | Lucía Castro | DevOps Engineer | Semi-senior | 85% |
| dquiroga | Diego Quiroga | DevOps Engineer | Junior | 90% |
| mfuentes | Mariana Fuentes | Cloud Engineer | Semi-senior | 80% (licencia) |

**Estado dummy:** 171% carga · Health 0/100 · 28 riesgos. Intencional para probar todos los escenarios.

---

## Arquitectura de agentes

```python
# Todos heredan BaseAgent
class MiAgente(BaseAgent):
    def run(self, **kwargs) -> dict:
        self.load_all()   # carga output/*.json
        # lógica propia...
        return self.build_result(findings, recommendations, verdict, priority_actions)

# Contrato de salida uniforme
{
  "agent":            "nombre",
  "verdict":          "VIABLE | NO VIABLE | CONDICIONAL | CRÍTICO | MODERADO | SALUDABLE | ...",
  "findings":         [{ "severity": "critica|alta|media|baja|info", "title": "...", "detail": "..." }],
  "recommendations":  ["..."],
  "priority_actions": [{ "urgency": "inmediata|esta semana|este mes", "action": "...", "owner": "..." }],
  "ai_prompt":        "prompt completo listo para Bedrock/Claude — ya incluye todos los datos del equipo"
}
```

### Tech Lead Reviewer
- Evalúa si el equipo puede aceptar un proyecto nuevo
- Veredictos: VIABLE · CONDICIONAL · NO VIABLE
- Analiza: carga, skills, miembros disponibles, health score, déficit de horas

### Capacity Analyst
- Detecta desequilibrios y propone redistribución concreta
- Veredictos: SALUDABLE · MODERADO · CRÍTICO
- Analiza: sobrecargados (+100%), sub-utilizados (-50%), licencias, reasignaciones posibles

### Risk Officer
- Profundiza en riesgos y genera plan de mitigación
- Veredictos: BAJO RIESGO · MODERADO · ALTO RIESGO
- Analiza: riesgos por severidad, patrones recurrentes, SPOFs, estrategia por tipo

### Estimator
- Estimación detallada con breakdown por fases
- Veredictos: VIABLE · MODERADO · ALTO RIESGO
- Modificadores: legacy +35%, nueva tecnología +30%, compliance +25%, multi-ambiente +15%...
- Salida: horas, man-months, SPs, duración, fases, YAML listo para projects.yml

---

## Decisiones técnicas

| Decisión | Razón |
|---|---|
| `encoding="utf-8"` en todo open() | Windows cp1252 rompía acentos en YAML |
| Jira: GET /rest/api/3/search/jql | /search GET → 410 · POST /issue/search → 405 |
| Jira auth: /mypermissions | /myself → 401 en Jira free |
| GitHub: sin param `type` | Exclusivo con `affiliation` → 422 |
| `python -m pip` | Python 3.14 Windows lo requiere |
| Reporte: HTML→PDF | reportlab tenía problemas de layout; HTML+CSS más confiable |
| Agentes sin IA externa | Determinístico, sin internet, auditable |
| `ai_prompt` en cada agente | Listo para Bedrock — cero cambios en lógica |

---

## Roadmap

| Fase | Estado |
|---|---|
| 1–4: Arquitectura, Data, Engines, Dashboard | ✅ |
| 5A: Jira real | ✅ |
| 5B: GitHub API real | ✅ |
| 5C: Reporte HTML→PDF | ✅ |
| 5D: Project Classifier | ✅ |
| 6: Agentes (TechLead, Capacity, Risk, Estimator) | ✅ (probados 2026-03-08) |
| 7: AWS Bedrock IA | 🔒 on hold |
| 8: Datos reales del equipo | ⏳ |
| 9: GitHub Pages en GitHub Enterprise | ⏳ |
| 10: run_agents.py orquestador consolidado | ✅ (2026-03-08) |
| 10B: Agentes integrados en run.py Paso 10 + report.html | ✅ (2026-03-08) |

---

## Fase 7 — Cómo conectar Bedrock (cuando llegue el momento)

Agregar en `base_agent.py`:

```python
import boto3, json

def ask_bedrock(self, prompt: str) -> str:
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    })
    resp = client.invoke_model(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        body=body
    )
    return json.loads(resp["body"].read())["content"][0]["text"]
```

En cada agente, al final de `run()`:
```python
if config.get("ai", {}).get("enabled"):
    result["ai_analysis"] = self.ask_bedrock(result["ai_prompt"])
```

**El `ai_prompt` ya está construido con todos los datos del equipo. Cero cambios en la lógica de análisis.**

---

## Notas importantes

- Jira de prueba: 0 issues, pero conexión verificada y funcionando
- GitHub: encontró `Liluvianette/IADeliveryCloud`, 8 commits, 2 autores, 0 PRs
- Si los agentes dan error → primero `python run.py --skip-ai`
- En Windows: usar `python` (no `python3`) y `python -m pip` (no `pip`)
- El `report.html` para PDF: A4 vertical · márgenes mínimos · activar gráficos de fondo