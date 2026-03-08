# 🗺️ ROADMAP — Cloud Delivery Intelligence Platform

> Documento vivo. Actualizar cada vez que se complete un hito.
> Última actualización: 2025-03-08

---

## 🎯 Visión del Proyecto

Crear un **tablero inteligente** que permita a un Tech Lead visualizar,
analizar y tomar decisiones sobre la capacidad real de un equipo DevOps cloud.

**Principio rector:** datos crudos → Python → JSONs → dashboard estático en GitHub Pages.
Sin servidores. Sin infraestructura adicional. Vive 100% en GitHub.

---

## 📊 Estado Actual por Componente

### Fuentes de Datos
| Componente | Estado | Archivo | Notas |
|---|---|---|---|
| Team Management | ✅ Funcional | `data/team.yml` | 6 personas, skills, capacidad, velocidad |
| Proyectos | ✅ Funcional | `data/projects.yml` | 10 proyectos, estados variados |
| Discovery | ✅ Plantilla lista | `data/discovery.md` | Requiere API key para análisis real |
| **Jira** | ⚠️ Mock | `ingestion/jira_ingest.py` | Código listo, falta `JIRA_TOKEN` en `.env` |
| **Git / GitHub** | ⚠️ Mock | `ingestion/git_ingest.py` | Código listo, falta `GITHUB_TOKEN` en `.env` |

### Motores de Análisis
| Componente | Estado | Archivo | Qué produce |
|---|---|---|---|
| Capacity Engine | ✅ Funcional | `analysis/capacity_engine.py` | `team_capacity.json` |
| Risk Engine | ✅ Funcional | `analysis/risk_engine.py` | `team_health.json` |
| Skills Matrix | ✅ Funcional | `analysis/skills_matrix.py` | `skills_matrix.json` |
| Estimation Engine | ✅ Funcional | `analysis/estimation_engine.py` | `estimation_example.json` |
| **Project Classifier** | ❌ Pendiente | `ai/project_classifier.py` | Clasificar tipo/complejidad auto |

### IA
| Componente | Estado | Archivo | Notas |
|---|---|---|---|
| Discovery Analyzer | ⚠️ Mock | `ai/discovery_analyzer.py` | Código listo, falta `ANTHROPIC_API_KEY` |
| Project Classifier | ❌ Pendiente | `ai/project_classifier.py` | FASE 5 |

### Dashboard
| Componente | Estado | Archivo | Notas |
|---|---|---|---|
| index.html | ✅ Funcional | `dashboard/index.html` | Dark mode, 6 KPIs, charts, skills |
| **GitHub Pages** | ⚠️ En deploy | `.github/workflows/deploy-pages.yml` | Workflow listo, configurando rama gh-pages |

### Reportes
| Componente | Estado | Archivo | Notas |
|---|---|---|---|
| **Executive PDF** | ❌ Pendiente | `reports/executive_report.py` | Siguiente después de Pages |

---

## 🚀 Fases de Construcción

### ✅ FASE 1 — Arquitectura del Sistema
- Diseño completo de la arquitectura estática
- Definición de estructura de carpetas
- Decisiones técnicas documentadas

### ✅ FASE 2 — Modelo de Datos
- `team.yml`: 6 personas con skills, capacidad, velocidad histórica
- `projects.yml`: 10 proyectos con estados, asignaciones, riesgos
- `config.yml`: configuración global del sistema
- `discovery.md`: plantilla para análisis de proyectos nuevos

### ✅ FASE 3 — Motores de Análisis
- `capacity_engine.py`: calcula carga real por persona y equipo
- `risk_engine.py`: detecta SPOFs, sobrecargas, proyectos sin backup
- `skills_matrix.py`: cobertura de habilidades del equipo
- `estimation_engine.py`: estima esfuerzo en horas y man-months
- `run.py`: orquestador maestro de toda la pipeline

### ⚠️ FASE 4 — Dashboard (90%)
- `dashboard/index.html`: dashboard completo funcional
- KPIs: carga, exceso, health score, riesgos, proyectos activos, man-months
- Banner de decisión: "El equipo PUEDE/NO puede aceptar nuevos proyectos"
- Lista de proyectos con estado, severidad, tipo, progreso
- Gráficas de carga y horas disponibles vs asignadas
- Heatmap de skills con niveles por persona
- **PENDIENTE**: Deploy en GitHub Pages confirmado y funcionando

### ⏳ FASE 5 — Inteligencia de Proyectos
**Sub-fase 5A — Conectar fuentes reales:**
- Activar Jira real: definir `JIRA_URL`, `JIRA_EMAIL`, `JIRA_TOKEN` en `.env`
- Activar Git real: definir `GITHUB_TOKEN` en `.env`
- Activar IA real: definir `ANTHROPIC_API_KEY` en `.env`
- Cambiar flags en `config.yml`: `jira.enabled: true`, `git.enabled: true`, `ai.enabled: true`

**Sub-fase 5B — Reporte ejecutivo PDF:**
- `reports/executive_report.py`
- Contenido: estado del equipo, proyectos, capacidad, riesgos, recomendaciones
- Formato: PDF profesional con tablas y gráficas

**Sub-fase 5C — Project Classifier:**
- `ai/project_classifier.py`
- Clasifica automáticamente proyectos nuevos por tipo y complejidad
- Input: descripción en texto libre
- Output: tipo, severidad, skills requeridos, estimación preliminar

---

## 📋 Backlog Priorizado

### 🔴 Inmediato
1. Confirmar GitHub Pages funcionando con dominio `liluvianettes.pocs`
2. Probar dashboard en producción sin errores CORS

### 🟡 Próximo Sprint
3. Generar reporte ejecutivo PDF (`executive_report.py`)
4. Conectar Jira real (requiere credenciales)
5. Conectar GitHub API real (requiere token)

### 🟢 Futuro
6. `project_classifier.py` — clasificación automática con IA
7. Análisis de correlación Jira ↔ Git commits
8. Vista de timeline de proyectos (Gantt simple)
9. Alertas por email cuando health score baje de umbral
10. Export del discovery analysis a Jira (crear epic automáticamente)

---

## 🔑 Variables de Entorno Necesarias

Crear archivo `.env` en la raíz del proyecto:

```env
# Jira (para ingesta real)
JIRA_URL=https://tuorganizacion.atlassian.net
JIRA_EMAIL=tu@email.com
JIRA_TOKEN=tu_jira_api_token

# GitHub (para análisis de repos)
GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Anthropic (para discovery analyzer y project classifier)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

---

## 📁 Estructura de Archivos Críticos

```
IADeliveryCloud/
├── .env                          ← NUNCA subir a git
├── .gitignore                    ← .env está aquí
├── config.yml                    ← flags on/off de integraciones
├── run.py                        ← punto de entrada principal
├── serve_local.py                ← servidor local para probar sin CORS
├── CNAME                         ← dominio personalizado Pages
│
├── data/                         ← EDITAR SEMANALMENTE
│   ├── team.yml
│   ├── projects.yml
│   └── discovery.md
│
├── ingestion/                    ← conectores datos externos
│   ├── team_loader.py
│   ├── jira_ingest.py            ← activar con jira.enabled: true
│   └── git_ingest.py             ← activar con git.enabled: true
│
├── analysis/                     ← motores de cálculo
│   ├── capacity_engine.py
│   ├── risk_engine.py
│   ├── skills_matrix.py
│   └── estimation_engine.py
│
├── ai/                           ← módulos de inteligencia
│   ├── discovery_analyzer.py     ← activar con ai.enabled: true
│   └── project_classifier.py     ← PENDIENTE DE CONSTRUIR
│
├── reports/                      ← generación de reportes
│   └── executive_report.py       ← PENDIENTE DE CONSTRUIR
│
├── dashboard/                    ← frontend GitHub Pages
│   ├── index.html
│   ├── .nojekyll
│   └── data/                     ← JSONs copiados aquí por run.py
│
└── output/                       ← JSONs generados (fuente de verdad)
    ├── team_capacity.json
    ├── team_health.json
    ├── skills_matrix.json
    ├── projects_raw.json
    └── ...
```

---

## 🔄 Flujo de Trabajo Semanal (cuando esté completo)

```
1. Lunes: editar team.yml (cambios de disponibilidad, licencias)
2. Lunes: editar projects.yml (nuevos proyectos, cambios de estado)
3. Ejecutar: python run.py --skip-ai
4. Revisar dashboard en http://localhost:8080 (serve_local.py)
5. git add . && git commit -m "chore: weekly update" && git push
6. GitHub Actions regenera y despliega automáticamente
7. Dashboard live en https://liluvianettes.pocs
```
