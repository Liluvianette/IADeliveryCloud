"""
ai/discovery_analyzer.py
Analiza un archivo discovery.md usando Claude API para generar:
- Clasificación del proyecto
- Lista de actividades
- Estimación en horas y man-months
- Análisis de riesgos
- Skills requeridos

Requiere ANTHROPIC_API_KEY en .env
"""

import os
import json
import yaml
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


CONFIG_PATH    = Path(__file__).parent.parent / "config.yml"
DISCOVERY_PATH = Path(__file__).parent.parent / "data" / "discovery.md"
OUTPUT_PATH    = Path(__file__).parent.parent / "output"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_discovery() -> str:
    with open(DISCOVERY_PATH) as f:
        return f.read()


def load_team_context() -> str:
    """Carga contexto del equipo para que la IA personalice la estimación."""
    try:
        with open(OUTPUT_PATH / "team_capacity.json") as f:
            cap = json.load(f)
        summary = cap["summary"]
        return (
            f"El equipo tiene {summary['total_free_hours']}h libres este mes "
            f"({summary['estimated_free_manmonths']} man-months disponibles). "
            f"Carga actual del equipo: {summary['team_load_percent']*100:.0f}%."
        )
    except Exception:
        return "Contexto de equipo no disponible."


SYSTEM_PROMPT = """Eres un Principal Cloud Architect y DevOps Lead con 15 años de experiencia.
Tu tarea es analizar documentos de discovery de proyectos cloud y DevOps para generar 
estimaciones precisas y análisis de riesgos.

Siempre responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin markdown, 
sin bloques de código. Solo el JSON puro.

El JSON debe tener exactamente esta estructura:
{
  "project_name": "string",
  "project_type": "iac|desarrollo|soporte|investigacion",
  "severity": "baja|media|alta|critica",
  "complexity": "bajo|medio|alto|critico",
  "summary": "string — resumen ejecutivo en 2-3 oraciones",
  "technologies": ["lista", "de", "tecnologías"],
  "required_skills": ["lista", "de", "skills", "del", "equipo"],
  "activities": [
    {
      "name": "string",
      "description": "string",
      "estimated_hours": number,
      "category": "discovery|design|implementation|testing|deployment|documentation"
    }
  ],
  "totals": {
    "estimated_hours": number,
    "optimistic_hours": number,
    "pessimistic_hours": number,
    "man_months": number
  },
  "risks": [
    {
      "description": "string",
      "severity": "baja|media|alta|critica",
      "mitigation": "string"
    }
  ],
  "assumptions": ["lista de supuestos clave"],
  "recommendations": ["lista de recomendaciones estratégicas"],
  "confidence_level": "bajo|medio|alto",
  "confidence_reason": "string explicando el nivel de confianza"
}"""


def build_user_prompt(discovery_text: str, team_context: str) -> str:
    return f"""Analiza el siguiente documento de discovery de proyecto y genera la estimación detallada.

CONTEXTO DEL EQUIPO:
{team_context}

DOCUMENTO DE DISCOVERY:
{discovery_text}

Instrucciones específicas:
1. Identifica TODAS las actividades necesarias, incluyendo las implícitas (discovery técnico, 
   documentación, coordinación con otros equipos, testing, rollback plan, etc.)
2. Las horas estimadas deben ser realistas para un equipo DevOps senior/semi-senior
3. Incluye buffer de incertidumbre: optimista = -25%, pesimista = +35%
4. Los man-months se calculan asumiendo 128h efectivas/mes (160h * 80% de eficiencia)
5. Identifica riesgos técnicos Y riesgos de proceso/organizacional
6. Si el documento menciona restricciones de tiempo, considéralas en los riesgos

Responde SOLO con el JSON, sin texto adicional."""


def call_claude_api(prompt: str, system: str) -> str:
    """Llama a la API de Anthropic."""
    try:
        import anthropic
    except ImportError:
        raise ImportError("Instala el SDK: pip install anthropic")

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no está definida en .env")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def generate_mock_analysis() -> dict:
    """Análisis simulado para desarrollo sin API key."""
    return {
        "project_name": "Migración RDS PostgreSQL → Aurora Serverless v2",
        "project_type": "iac",
        "severity":     "alta",
        "complexity":   "alto",
        "summary": (
            "Migración de base de datos PostgreSQL 14 (2TB multi-tenant) a Aurora Serverless v2 "
            "con zero-downtime, réplicas cross-region y actualización de 6 microservicios en EKS. "
            "Proyecto de alta complejidad técnica con restricciones regulatorias y múltiples equipos involucrados."
        ),
        "technologies": [
            "AWS RDS PostgreSQL 14", "AWS Aurora PostgreSQL Serverless v2",
            "AWS DMS", "Amazon EKS", "Kubernetes", "Terraform", "GitHub Actions"
        ],
        "required_skills": ["aws", "terraform", "kubernetes", "ci_cd", "python"],
        "activities": [
            {"name": "Discovery técnico y auditoría del schema actual", "description": "Mapear schema, extensiones, stored procedures y dependencias.", "estimated_hours": 24, "category": "discovery"},
            {"name": "Diseño de arquitectura Aurora Serverless v2",     "description": "Definir configuración, sizing, parámetros y estrategia de réplicas.", "estimated_hours": 20, "category": "design"},
            {"name": "Módulo Terraform para Aurora Serverless",         "description": "Desarrollar y testear módulo IaC desde cero.", "estimated_hours": 32, "category": "implementation"},
            {"name": "Configuración AWS DMS",                           "description": "Setup de replication instance, endpoints y migration tasks.", "estimated_hours": 16, "category": "implementation"},
            {"name": "Configuración réplicas cross-region",             "description": "us-east-1 → us-west-2, failover y latency testing.", "estimated_hours": 16, "category": "implementation"},
            {"name": "Actualización de 6 microservicios (K8s Secrets)", "description": "Coordinar con 3 equipos. Actualizar Secrets y ConfigMaps. PR + review.", "estimated_hours": 24, "category": "implementation"},
            {"name": "Pruebas de migración en ambiente staging",        "description": "3 ensayos completos midiendo tiempo y validando integridad.", "estimated_hours": 24, "category": "testing"},
            {"name": "Benchmark de performance Aurora vs RDS",         "description": "Validar latencia, throughput y cold starts de Serverless.", "estimated_hours": 12, "category": "testing"},
            {"name": "Plan de rollback documentado y probado",          "description": "Procedimiento detallado y drill en staging.", "estimated_hours": 12, "category": "testing"},
            {"name": "Cutover a producción (ventana 4h)",               "description": "Ejecución del cutover real con monitoreo 24h post-migración.", "estimated_hours": 16, "category": "deployment"},
            {"name": "Documentación técnica y runbook operacional",     "description": "Arquitectura, procedimientos, troubleshooting.", "estimated_hours": 16, "category": "documentation"},
            {"name": "Coordinación inter-equipos y gestión de cambio",  "description": "Reuniones, aprobaciones, comunicaciones de cambio.", "estimated_hours": 16, "category": "discovery"},
        ],
        "totals": {
            "estimated_hours":   228,
            "optimistic_hours":  171,
            "pessimistic_hours": 308,
            "man_months":        1.78,
        },
        "risks": [
            {"description": "Incompatibilidad de extensiones PostgreSQL entre RDS y Aurora", "severity": "alta",   "mitigation": "Auditar extensiones en discovery. Probar en staging antes del cutover."},
            {"description": "Cold starts de Aurora Serverless degradan SLA en horas valle",  "severity": "media",  "mitigation": "Configurar ACU mínimo > 0. Evaluar si Serverless v2 es adecuado vs provisioned."},
            {"description": "Schema no documentado puede revelar dependencias ocultas",      "severity": "alta",   "mitigation": "Asignar 24h de discovery técnico antes de comprometer el plan."},
            {"description": "Resistencia de los 3 equipos a cambiar connection strings",     "severity": "media",  "mitigation": "Involucrar a los TLs de cada equipo desde el inicio. Usar feature flags."},
            {"description": "Ventana de mantenimiento de 4h puede ser insuficiente",         "severity": "critica","mitigation": "Validar tiempo real en 3 ensayos en staging. Tener plan B con ventana de 8h."},
        ],
        "assumptions": [
            "El equipo tendrá acceso completo a los 6 microservicios para modificar configuración",
            "Se puede crear ambiente staging con copia real de los 2TB de datos",
            "Los 3 equipos de desarrollo participarán activamente en sus ventanas asignadas",
            "El proceso de auditoría permite una ventana de 4h con logs continuos",
        ],
        "recommendations": [
            "Iniciar con un discovery técnico profundo de 2 semanas antes de commitear fechas",
            "Evaluar Aurora Serverless v2 vs Aurora Provisioned para el caso de uso específico",
            "Implementar blue/green deployment con Route 53 para reducir riesgo de cutover",
            "Asignar a Carlos Méndoza (AWS expert) como líder técnico del proyecto",
        ],
        "confidence_level": "medio",
        "confidence_reason": "El scope está razonablemente bien definido pero hay incógnitas importantes sobre el schema y las extensiones PostgreSQL que pueden ampliar significativamente el esfuerzo.",
    }


def run() -> dict:
    print("🤖 Analizando discovery con IA...")
    config = load_config()

    discovery_text = load_discovery()
    team_context   = load_team_context()

    if config["ai"]["enabled"]:
        print("  → Modo: Claude API real")
        try:
            user_prompt  = build_user_prompt(discovery_text, team_context)
            raw_response = call_claude_api(user_prompt, SYSTEM_PROMPT)
            # Limpiar posibles backticks residuales
            cleaned      = raw_response.strip().removeprefix("```json").removesuffix("```").strip()
            analysis     = json.loads(cleaned)
        except Exception as e:
            print(f"  ⚠️  Error con API: {e}. Usando análisis simulado.")
            analysis = generate_mock_analysis()
    else:
        print("  → Modo: análisis simulado (ai.enabled = false)")
        analysis = generate_mock_analysis()

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "mode":         "real" if config["ai"]["enabled"] else "mock",
        "source_file":  str(DISCOVERY_PATH),
        "analysis":     analysis,
    }

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "discovery_output.json"
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    name    = analysis.get("project_name", "?")
    hours   = analysis.get("totals", {}).get("estimated_hours", "?")
    mm      = analysis.get("totals", {}).get("man_months", "?")
    print(f"  ✅ '{name}': {hours}h / {mm} man-months → {out_file}")
    return output


if __name__ == "__main__":
    run()
