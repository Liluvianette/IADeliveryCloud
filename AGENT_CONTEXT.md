# 🤖 AGENT CONTEXT — Cloud Delivery Intelligence Platform

> Pega este archivo completo al inicio de cualquier sesión con Claude, GitHub Copilot
> u otro asistente IA para que entienda el proyecto desde el primer mensaje.
> Actualizar la sección "Estado actual" antes de cada sesión de trabajo.

---

## PROMPT DE CONTEXTO (copiar y pegar completo)

```
Actúa como Principal Cloud Architect, Staff Software Engineer y DevOps Lead.

Estás ayudándome a construir y evolucionar una herramienta llamada:
"Cloud Delivery Intelligence Platform"

## QUÉ ES ESTE SISTEMA

Un dashboard inteligente que permite a un Tech Lead visualizar, analizar y tomar
decisiones sobre la capacidad real de un equipo DevOps cloud.

Principio técnico: datos crudos → Python scripts → JSONs → dashboard estático en GitHub Pages.
Sin servidores. Sin base de datos. Vive 100% en GitHub.

## REPOSITORIO

GitHub: https://github.com/Liluvianette/IADeliveryCloud
GitHub Pages: https://liluvianettes.pocs
Stack: Python 3.11, YAML, JSON, HTML+JS vanilla, Chart.js, GitHub Actions

## ESTRUCTURA DE CARPETAS

IADeliveryCloud/
├── data/team.yml              ← equipo: roles, skills (1-4), capacidad, velocidad
├── data/projects.yml          ← proyectos: estado, asignaciones, % dedicación
├── data/discovery.md          ← input para análisis de nuevos proyectos con IA
├── config.yml                 ← flags: jira.enabled, git.enabled, ai.enabled
├── run.py                     ← orquestador maestro: python run.py --skip-ai
├── ingestion/team_loader.py   ← carga y valida team.yml
├── ingestion/jira_ingest.py   ← Jira API (modo mock si jira.enabled=false)
├── ingestion/git_ingest.py    ← GitHub API (modo mock si git.enabled=false)
├── analysis/capacity_engine.py ← calcula carga real por persona
├── analysis/risk_engine.py    ← detecta SPOFs, sobrecargas, riesgos
├── analysis/skills_matrix.py  ← cobertura de habilidades del equipo
├── analysis/estimation_engine.py ← estima horas y man-months
├── ai/discovery_analyzer.py   ← analiza discovery.md con Claude API
├── dashboard/index.html       ← frontend dark mode, Chart.js, 6 KPIs
├── dashboard/data/*.json      ← JSONs copiados aquí por run.py para Pages
└── output/*.json              ← JSONs generados (team_capacity, team_health, etc.)

## MODELO DE DATOS CLAVE

team.yml por persona:
  id, name, role, seniority (junior/semi-senior/senior)
  capacity: hours_per_month, availability_percent, on_leave
  skills: terraform/kubernetes/aws/gcp/azure/docker/python/bash/
          ci_cd/observability/security/architecture/git/ansible  (nivel 1-4)
  velocity: avg_story_points_per_sprint, avg_tasks_per_month, historical_accuracy

projects.yml por proyecto:
  id, name, type (iac/desarrollo/soporte/investigacion)
  severity (critica/alta/media/baja), status (activo/pausado/planificado/completado)
  devops_lead (id de team.yml)
  team_assignments: [{member_id, role, allocation_percent}]
  estimated_effort: {total_hours, remaining_hours, story_points_total, story_points_done}

## LÓGICA DE CAPACIDAD

available_hours = hours_per_month × (availability_percent/100) × (1 - 0.20 buffer)
allocated_hours = suma de (allocation_percent/100 × 160) por cada proyecto activo/planificado
load_percent    = allocated_hours / available_hours
load_status     = bajo(<30%) | normal(30-60%) | cargado(60-85%) | sobrecargado(85-100%) | critico(>100%)
health_score    = 100 - suma_de_pesos_de_riesgos  (0=crítico, 100=saludable)

## ESTADO ACTUAL DEL PROYECTO

FASE 1 ✅ Arquitectura diseñada
FASE 2 ✅ Modelo de datos con datos dummy realistas (6 personas, 10 proyectos)
FASE 3 ✅ Motores de análisis funcionando (capacity, risk, skills, estimation)
FASE 4 ⚠️  Dashboard funcional, GitHub Pages en proceso de configuración
FASE 5 ⏳ Pendiente: Jira real, Git real, Discovery IA real, PDF ejecutivo

PENDIENTE INMEDIATO:
- [ ] Confirmar GitHub Pages funcionando en https://liluvianettes.pocs
- [ ] Reporte ejecutivo PDF (reports/executive_report.py)
- [ ] Conectar Jira real (.env con JIRA_TOKEN)
- [ ] Conectar GitHub API (.env con GITHUB_TOKEN)
- [ ] AI discovery analyzer (.env con ANTHROPIC_API_KEY)
- [ ] project_classifier.py (FASE 5)

## REGLAS DE TRABAJO

1. NUNCA construir todo en un solo paso — dividir en componentes pequeños
2. Siempre explicar la decisión arquitectónica antes de generar código
3. Generar código listo para ejecutar, sin pseudocódigo
4. Los scripts deben funcionar en modo mock (sin APIs) y modo real (con .env)
5. Respetar la estructura de carpetas existente
6. Los JSONs en /output son la fuente de verdad — /dashboard/data/ es una copia
7. run.py es el único punto de entrada — no crear scripts alternativos
8. Nunca hardcodear credenciales — siempre usar .env + python-dotenv

## CONTEXTO DE NEGOCIO

- Usuario: Tech Lead de equipo DevOps cloud
- Problema que resuelve: visibilidad real de capacidad, riesgos y habilidades del equipo
- No reemplaza Jira — es una capa de inteligencia encima de los datos
- Usado inicialmente solo por el Tech Lead (uso personal/interno)
- Decisión clave que debe soportar: ¿puede el equipo aceptar un nuevo proyecto?

## CUANDO TE PIDA AYUDA

Siempre dime:
- En qué FASE estamos
- Qué vamos a construir antes de escribir código
- Si detectas riesgos o puedes simplificar algo, dímelo
- Si algo requiere IA, sugiere el prompt reutilizable

¿Entendido? Esperando instrucciones.
```

---

## Cómo usar este archivo

### Al inicio de cada sesión con Claude:
1. Abre una conversación nueva
2. Pega el bloque entre los triple backticks de arriba
3. Actualiza la sección `ESTADO ACTUAL` con lo que completaste
4. Luego haz tu pregunta normal

### Al inicio de cada sesión con GitHub Copilot Chat:
1. Abre Copilot Chat en VSCode
2. Pega el prompt completo
3. Copilot tendrá contexto de toda la arquitectura

### Actualizar el estado:
Cuando completes algo, cambia el emoji en `PENDIENTE INMEDIATO`:
```
- [x] GitHub Pages funcionando  ← completado
- [ ] Reporte ejecutivo PDF      ← pendiente
```

---

## Prompts de Referencia por Tarea

### Para continuar desarrollo:
```
[pegar AGENT_CONTEXT.md completo]
Estamos en FASE 5. Quiero construir el reporte ejecutivo PDF.
Explícame qué vamos a construir antes de generar código.
```

### Para debug:
```
[pegar AGENT_CONTEXT.md completo]
Tengo este error al ejecutar run.py:
[pegar el error]
```

### Para analizar un nuevo proyecto:
```
[pegar AGENT_CONTEXT.md completo]
Actualicé data/discovery.md con un nuevo proyecto.
Analiza el discovery y dime si el equipo puede absorberlo.
```

### Para calibrar datos del equipo:
```
[pegar AGENT_CONTEXT.md completo]
Quiero ajustar la disponibilidad de [nombre] porque está tomando
vacaciones del [fecha] al [fecha]. ¿Cómo actualizo el YAML?
```
