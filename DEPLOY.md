# Guía de Deploy — GitHub Pages

## Opción A: Probar localmente ahora (sin CORS)
```bash
python serve_local.py
# Abre automáticamente http://localhost:8080
```

## Opción B: Subir a GitHub Pages (permanente)

### Paso 1 — Crear repositorio en GitHub
1. Ve a https://github.com/new
2. Nombre sugerido: `cloud-delivery-intelligence`
3. Visibilidad: **Private** (recomendado — tiene datos del equipo)
4. NO inicialices con README (ya tenemos uno)
5. Clic en **Create repository**

### Paso 2 — Subir el código desde tu PC
Abre una terminal en la carpeta del proyecto y ejecuta:

```bash
git init
git add .
git commit -m "feat: initial Cloud Delivery Intelligence Platform"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/cloud-delivery-intelligence.git
git push -u origin main
```

### Paso 3 — Activar GitHub Pages
1. Ve a tu repo → **Settings** → **Pages** (barra izquierda)
2. En **Source**: selecciona `Deploy from a branch`
3. En **Branch**: selecciona `main` y carpeta `/dashboard`
4. Clic en **Save**
5. Espera 2-3 minutos
6. Tu dashboard estará en:
   `https://TU_USUARIO.github.io/cloud-delivery-intelligence/`

### Paso 4 — Flujo de actualización semanal
```bash
# 1. Edita data/team.yml o data/projects.yml en VSCode
# 2. Regenera los JSONs:
python run.py --skip-ai

# 3. Sube los cambios:
git add .
git commit -m "chore: actualización semanal capacidad"
git push
# GitHub Pages se actualiza automáticamente en ~1 minuto
```

## ¿Repo privado o público?
- **Privado**: nadie puede ver tus datos. Necesitas GitHub Pro para Pages privado
  (alternativa: usar GitHub Actions para generar y subir solo el dashboard)
- **Público**: GitHub Pages gratis, pero los YAMLs con datos del equipo son visibles

## Solución para repo privado + Pages gratis
El GitHub Action incluido en `.github/workflows/generate-dashboard.yml`
ya está configurado para esto: genera los JSONs y los commitea automáticamente.
