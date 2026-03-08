# ⚡ Cloud Delivery Intelligence Platform

Dashboard inteligente para visualizar, analizar y estimar la capacidad real de un equipo DevOps cloud.

## Estructura

```
cloud-delivery-intelligence/
├── data/                    ← Edita estos archivos manualmente
│   ├── team.yml             ← Equipo, roles, capacidad, skills
│   ├── projects.yml         ← Proyectos activos y planificados
│   └── discovery.md         ← Nuevo proyecto a analizar
├── ingestion/               ← Conectores a fuentes de datos
│   ├── team_loader.py
│   ├── jira_ingest.py
│   └── git_ingest.py
├── analysis/                ← Motores de análisis
│   ├── capacity_engine.py
│   ├── risk_engine.py
│   ├── estimation_engine.py
│   └── skills_matrix.py
├── ai/                      ← Análisis con IA
│   └── discovery_analyzer.py
├── dashboard/               ← Frontend estático (GitHub Pages)
│   ├── index.html
│   └── data/                ← JSONs copiados aquí para el dashboard
├── output/                  ← JSONs generados por la pipeline
├── run.py                   ← Script maestro
├── config.yml               ← Configuración global
└── requirements.txt
```

## Inicio Rápido

### 1. Clonar e instalar

```bash
git clone https://github.com/TU_USER/cloud-delivery-intelligence
cd cloud-delivery-intelligence
pip install -r requirements.txt
```

### 2. Ejecutar la pipeline (modo simulado, sin APIs)

```bash
python run.py --skip-ai
```

### 3. Ver el dashboard

Abre `dashboard/index.html` en tu navegador.

## Comandos

```bash
# Pipeline completa (requiere .env con API keys)
python run.py

# Sin análisis de IA
python run.py --skip-ai

# Solo recalcular capacidad
python run.py --only-capacity

# Solo analizar salud del equipo
python run.py --only-health
```

## Configurar APIs (opcional)

Crea un archivo `.env` en la raíz:

```env
# Jira
JIRA_URL=https://tuorganizacion.atlassian.net
JIRA_EMAIL=tu@email.com
JIRA_TOKEN=tu_jira_api_token

# GitHub (para análisis de repos)
GITHUB_TOKEN=ghp_...

# Anthropic (para análisis de discovery con IA)
ANTHROPIC_API_KEY=sk-ant-...
```

Luego activa las integraciones en `config.yml`:

```yaml
jira:
  enabled: true
  project_keys: ["DEVOPS", "CLOUD"]

git:
  enabled: true
  repos: ["tu-org/repo-1", "tu-org/repo-2"]

ai:
  enabled: true
```

## GitHub Pages

1. Ve a Settings → Pages en tu repositorio
2. Selecciona `main` branch y carpeta `/dashboard`
3. Tu dashboard estará en: `https://TU_USER.github.io/cloud-delivery-intelligence/`

El GitHub Action incluido regenera el dashboard automáticamente cuando haces push de cambios a `/data`.

## Flujo de trabajo semanal

1. Edita `data/team.yml` si hay cambios de disponibilidad
2. Edita `data/projects.yml` si hay proyectos nuevos o cambios de estado
3. Ejecuta `python run.py --skip-ai`
4. Haz push → GitHub Pages se actualiza automáticamente

## Analizar un proyecto nuevo

1. Edita `data/discovery.md` con la información del proyecto
2. Asegúrate de tener `ANTHROPIC_API_KEY` en `.env` y `ai.enabled: true` en `config.yml`
3. Ejecuta `python run.py`
4. El análisis estará en `output/discovery_output.json`

## Fases del proyecto

- ✅ FASE 1: Arquitectura del sistema
- ✅ FASE 2: Modelo de datos
- ✅ FASE 3: Motores de análisis
- ✅ FASE 4: Dashboard
- ✅ FASE 5: Inteligencia de proyectos

---

*Construido con Python + GitHub Pages. Sin servidores, sin infraestructura adicional.*
