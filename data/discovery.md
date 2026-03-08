# Discovery: [Nombre del Proyecto Aquí]

> **Instrucciones**: Completa este archivo cuando aparezca un proyecto nuevo.
> El sistema lo analizará automáticamente para generar estimaciones y clasificación.

---

## 1. Contexto General

**Cliente / Stakeholder**: Equipo de Producto - Fintech Squad
**Fecha de solicitud**: 2025-03-10
**Urgencia percibida**: Alta
**Descripción breve**:

Necesitamos migrar nuestra base de datos RDS PostgreSQL (actual: 2TB, multi-tenant)
a Aurora PostgreSQL Serverless v2, con zero-downtime y sin pérdida de datos.
Adicionalmente se requiere configurar réplicas de lectura cross-region (us-east-1 → us-west-2)
y actualizar todas las connection strings en 6 microservicios desplegados en EKS.

---

## 2. Objetivos

- Migrar RDS PostgreSQL 14 → Aurora PostgreSQL Serverless v2
- Zero downtime durante la migración
- Réplicas de lectura cross-region habilitadas
- Actualizar configuración en 6 microservicios (Kubernetes Secrets + ConfigMaps)
- Documentar el proceso de rollback
- Validar performance post-migración con benchmarks

---

## 3. Tecnologías Mencionadas

- AWS RDS PostgreSQL 14
- AWS Aurora PostgreSQL Serverless v2
- AWS DMS (Database Migration Service)
- Amazon EKS
- Kubernetes (Secrets, ConfigMaps)
- Terraform (para infraestructura Aurora)
- GitHub Actions (para automatización del cutover)

---

## 4. Restricciones Conocidas

- Ventana de mantenimiento máxima: 4 horas (domingo 2am - 6am)
- No se puede tocar el schema de base de datos
- Los 6 microservicios pertenecen a 3 equipos distintos (coordinación requerida)
- Existe un proceso de auditoría activo: los logs de BD no pueden interrumpirse
- Budget aprobado: $15,000 USD para infraestructura adicional temporal

---

## 5. Riesgos Percibidos (desde el cliente)

- Pérdida de datos durante migración
- Degradación de performance en Aurora Serverless (cold starts)
- Incompatibilidad de extensiones PostgreSQL
- Resistencia de equipos a cambiar connection strings

---

## 6. Información Adicional

El equipo de producto tiene deadline para Q2 (30 de junio).
Ya existe un Terraform module para RDS pero no para Aurora Serverless.
No existe documentación del schema actual; será necesario hacer discovery técnico primero.

---

*Este archivo será analizado por el AI module del sistema para generar:*
- *Clasificación de proyecto*
- *Lista de actividades*
- *Estimación en horas y man-months*
- *Análisis de riesgos*
- *Skills requeridos*
