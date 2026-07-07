# JobDistiller — Sistema de filtrado de ofertas laborales

> **Versión:** 1.0 · Julio 2026 · Un pipeline Python que recolecta ofertas de múltiples fuentes, las puntúa según tu perfil, y las entrega en un dashboard web + email diario.

## Problema

Buscar trabajo remoto revisando múltiples portales es manual, repetitivo y sin criterio. **JobDistiller** automatiza eso: tú defines tus pesos, el sistema puntúa todas las ofertas, y ves solo lo relevante.

## Arquitectura

```
Adapters (5 fuentes)
    ↓
Normalizer (schema común)
    ↓
Dedupe (exacto + fuzzy)
    ↓
Scorer (tu perfil → score)
    ↓
SQLite (histórico + export JSON)
    ↓
├→ Dashboard JS (gráficos, tabla)
└→ Email digest (diario)
```

## Setup

### Requisitos
- Python 3.11+
- Node.js 18+ (para dashboard)
- `.env` con secretos (copiar `.env.example`)

### Instalación

```bash
# Python
python -m venv .venv
source .venv/Scripts/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Dashboard
cd dashboard && npm install && cd ..
```

### Configuración

1. **`config/profile.yaml`** — Define tus pesos:
   - `hard_filters`: descarta sin puntuar
   - `weights`: suma ponderada 0-100
   - `my_stack`: core/secondary/learning
   - `salary_curve`: piso y techo USD/mes

2. **`config/sources.yaml`** — Activa/desactiva fuentes:
   - RemoteOK (pública)
   - Getonboard (LATAM tech)
   - Adzuna (requiere key)
   - HN Hiring
   - Computrabajo (Perú)

3. **`.env`** — Secretos (NUNCA commitear):
   ```
   ADZUNA_APP_ID=...
   ADZUNA_APP_KEY=...
   GMAIL_ADDRESS=...
   GMAIL_APP_PASSWORD=...
   DIGEST_TO=your@email.com
   ```

## Uso

### Correr pipeline (fetch → score → export)
```bash
python -m core.cli run
# Produce: dashboard/public/data/offers.json
```

### Enviar digest por email
```bash
python -m core.cli digest
# Requiere GMAIL_ADDRESS, GMAIL_APP_PASSWORD, DIGEST_TO en .env
```

### Dashboard local (dev)
```bash
cd dashboard && npm run dev
# Abre http://localhost:5173
```

### Build dashboard para producción
```bash
cd dashboard && npm run build
# Produce: dashboard/dist/ (listo para Netlify)
```

## Tests

```bash
pytest tests/ -v
```

## Flujo diario (automático en GitHub Actions)

1. **8:00 AM Lima** (cron scheduled):
   - Corre pipeline (fetch all sources)
   - Normaliza y puntúa
   - Exporta JSON
   - Build dashboard
   - Commitea cambios
   - Envía email digest con top 10

2. **Netlify** despliega automáticamente `dashboard/dist/`

## Piezas clave

| Módulo | Responsabilidad |
|--------|-----------------|
| `core/models.py` | Dataclasses Offer + RawOffer |
| `core/normalizer.py` | Heurísticas (stack, seniority, inglés) |
| `core/scorer.py` | Motor de pesos con breakdown |
| `core/dedupe.py` | Exacto (hash) + fuzzy (similitud) |
| `core/store.py` | SQLite (histórico) + JSON export |
| `core/adapters/` | 5 adapters con reintentos |
| `core/cli.py` | Orquestación pipeline |
| `core/digest.py` | HTML email template |
| `dashboard/src/` | JS: tabla, filtros, 4 gráficos |

## Secrets en GitHub (para CI/CD automático)

```
ADZUNA_APP_ID
ADZUNA_APP_KEY
GMAIL_ADDRESS
GMAIL_APP_PASSWORD
DIGEST_TO
NETLIFY_AUTH_TOKEN
NETLIFY_SITE_ID
```

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Fuente cae | Adapter fallido no detiene pipeline; se loguea en `runs` |
| Cambios en HTML | Computrabajo (scraping) es adapter aislado; otros son APIs estables |
| Rate limit | Throttle explícito por adapter; caché de 12h |
| API keys expuestas | Solo `.env` (en gitignore); CI/CD usa Secrets |

## Post-MVP (M1, M2, ...)

- **M1:** Asistente de CV (brechas + sugerencias)
- **M2:** Scoring semántico (embeddings)
- **M3:** Alertas Telegram
- **M4:** Multi-perfil (compartir con colegas)

---

**Construido con:** Python 3.12 · SQLite · Vite · Chart.js · GitHub Actions  
**Autor:** Luis Barra + Claude  
**Licencia:** MIT

