# SDD — Destilador de Ofertas Laborales («JobDistiller»)

> **Versión:** 1.0 · Julio 2026 · **Autor:** Luis Barra + Claude
> **Tipo:** Software Design Document, listo para ejecutar con Claude Code.
> **Decisiones ya tomadas por Luis:** fuentes internacionales Y LATAM desde el MVP · salida doble (dashboard web + digest Gmail) · núcleo en **Python** + dashboard en **JS**.
> *(Nombre en clave `JobDistiller` — alternativas si prefieres: `ChambaRadar`, `JobLens`, `Destilador`. Decidir antes del primer commit.)*

---

## 1. Problema y objetivo

Luis busca roles de desarrollo (remoto ideal, Perú o exterior) y hoy revisar portales es manual, repetitivo y sin criterio consistente. El sistema debe **recolectar ofertas de múltiples fuentes, normalizarlas, puntuarlas según los "pesos" del perfil de Luis y entregarle solo lo relevante**, en dos canales: un dashboard web con gráficos y un digest por Gmail.

**Objetivo medible del MVP:** correr un comando y, en < 2 minutos, tener un dashboard con las ofertas de los últimos 30 días de ≥ 4 fuentes, ordenadas por score personalizado, con desglose visible de por qué cada oferta puntúa lo que puntúa.

### 1.1 No-objetivos del MVP (explícitos, para no inflar alcance)
- **NO** postulación automática.
- **NO** scraping de LinkedIn (prohibido por sus ToS y bloqueado activamente; riesgo de baneo de cuenta).
- **NO** adecuación automática del CV por oferta → es el **módulo post-MVP M1** (sección 8), diseñado desde ya para respetar la regla de Luis: *sugerir sin mentir*.
- **NO** múltiples usuarios/perfiles. Esto es una herramienta personal (aunque el diseño no lo impide a futuro).

---

## 2. Arquitectura general

```
┌────────────┐   ┌────────────┐   ┌─────────┐   ┌──────────┐   ┌─────────────────┐
│  ADAPTERS   │ → │ NORMALIZER │ → │ DEDUPE  │ → │  SCORER  │ → │     STORE       │
│ (1 x fuente)│   │ (schema    │   │ (hash + │   │ (pesos   │   │  SQLite +       │
│             │   │  común)    │   │ fuzzy)  │   │  YAML)   │   │  export JSON    │
└────────────┘   └────────────┘   └─────────┘   └──────────┘   └────────┬────────┘
                                                                        │
                                                    ┌───────────────────┴───────────┐
                                                    ▼                               ▼
                                            ┌───────────────┐              ┌───────────────┐
                                            │ DASHBOARD (JS) │              │ DIGEST (Gmail) │
                                            │ estático, lee  │              │ top-N nuevas   │
                                            │ export JSON    │              │ vía MCP/SMTP   │
                                            └───────────────┘              └───────────────┘
```

**Principio rector:** el núcleo Python es un **pipeline de lotes** (se ejecuta, procesa, termina — sin servidores corriendo). El dashboard es un **sitio estático** que lee un JSON exportado: cero backend que mantener, deployable gratis en Netlify (territorio que Luis ya domina).

### 2.1 Estructura del repositorio

```
jobdistiller/
├── core/                        # Python
│   ├── adapters/                # un archivo por fuente
│   │   ├── base.py              # clase abstracta BaseAdapter
│   │   ├── remoteok.py · hn_hiring.py · adzuna.py
│   │   ├── getonboard.py · computrabajo.py
│   ├── models.py                # dataclass Offer + validación
│   ├── normalizer.py            # limpieza y mapeo al schema común
│   ├── dedupe.py                # exactos (hash) + difusos (similitud)
│   ├── scorer.py                # motor de pesos
│   ├── store.py                 # SQLite (histórico) + export JSON
│   ├── digest.py                # arma el email (HTML) del digest
│   └── cli.py                   # entrada: fetch / score / export / digest / run
├── dashboard/                   # JS (Vite + vanilla JS + Chart.js)
│   ├── index.html · src/
│   └── public/data/offers.json  # ← lo escribe el pipeline
├── config/
│   ├── profile.yaml             # LOS PESOS (el corazón configurable)
│   └── sources.yaml             # fuentes on/off, API keys por env vars
├── tests/                       # pytest: adapters con fixtures, scorer, dedupe
├── .github/workflows/daily.yml  # cron opcional (Fase 4)
├── .env.example · requirements.txt · README.md
```

---

## 3. Modelo de datos

### 3.1 Schema común de oferta (`models.py`)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | str | hash de `source + url` |
| `source` | str | `remoteok`, `getonboard`, etc. |
| `title`, `company`, `url` | str | obligatorios; sin url válida se descarta |
| `location` | str | texto libre normalizado |
| `remote` | enum | `remote` / `hybrid` / `onsite` / `unknown` |
| `salary_min`, `salary_max` | int·nullable | SIEMPRE convertido a USD/mes para comparar (tabla de conversión en config; PEN, USD anual→mensual, etc.) |
| `stack` | list[str] | tags técnicos extraídos (título + descripción + tags de la fuente), normalizados a minúsculas canónicas (`node.js`→`nodejs`) |
| `seniority` | enum | `junior` / `mid` / `senior` / `lead` / `unknown` — heurística por keywords |
| `english_required` | enum | `none` / `basic` / `conversational` / `advanced` / `unknown` — heurística por frases ("fluent English", "inglés avanzado") |
| `description` | str | texto plano, recortado a 5 000 chars |
| `posted_at`, `fetched_at` | datetime | si la fuente no da fecha → `fetched_at` y flag `date_estimated` |
| `score`, `score_breakdown` | float, dict | calculados; el breakdown guarda el aporte de CADA criterio (transparencia total) |

### 3.2 Persistencia
SQLite (`data/offers.db`), tabla única `offers` + tabla `runs` (log de cada ejecución: fuente, cantidad, errores). Regla: **nunca se borra**, las ofertas viejas se marcan `stale` — el histórico es un activo (permite gráfico de tendencias en el dashboard).

---

## 4. Los pesos (`config/profile.yaml`) — el corazón del sistema

Filosofía: **dos niveles**. *Filtros duros* (descartan sin puntuar) y *pesos blandos* (suman/restan). Todo editable sin tocar código.

```yaml
# ====== FILTROS DUROS (si falla uno, la oferta se descarta) ======
hard_filters:
  exclude_title_keywords: [".NET lead", "iOS", "Android nativo"]  # ejemplos
  max_seniority: senior          # descarta lead/principal
  min_salary_usd_month: null     # null = no filtrar por sueldo aún
  exclude_english: [advanced]    # descarta si EXIGE inglés avanzado

# ====== PESOS BLANDOS (score = suma ponderada, normalizado 0-100) ======
weights:
  stack_match:      { weight: 35 }   # % de coincidencia con my_stack
  remote:           { weight: 20, values: { remote: 1.0, hybrid: 0.4, onsite: 0.0, unknown: 0.3 } }
  salary:           { weight: 15 }   # curva: bajo piso=0, sobre techo=1
  seniority_fit:    { weight: 10, values: { junior: 0.6, mid: 1.0, senior: 0.7, unknown: 0.5 } }
  latam_friendly:   { weight: 10 }   # menciona LATAM/GMT-5/español = 1
  english_fit:      { weight: 5,  values: { none: 1.0, basic: 1.0, conversational: 0.5, advanced: 0.0, unknown: 0.7 } }
  freshness:        { weight: 5 }    # decay lineal 30 días

my_stack:
  core:      [php, codeigniter, javascript, mysql]     # x1.0
  secondary: [laravel, vue, sql, postgresql, git, nginx] # x0.6
  learning:  [python, react, astro, nestjs]             # x0.3

salary_curve: { floor_usd_month: 600, ceiling_usd_month: 3000 }
```

**Reglas del scorer:**
1. `stack_match` = Σ(matches × factor de nivel) / Σ(stack de la oferta), con mínimo garantizado si matchea ≥ 2 core.
2. El breakdown se guarda SIEMPRE: el dashboard muestra "Score 78 = stack 31 + remote 20 + salario 12 + …". Sin cajas negras — es la manera de que Luis calibre sus propios pesos iterando.
3. Los pesos deben sumar 100 (el CLI valida y avisa si no).

---

## 5. Adapters de fuentes (MVP: 5)

Contrato común (`BaseAdapter`): `fetch() -> list[RawOffer]`, con rate-limit propio, reintentos (3, backoff), y fixtures de test grabados (para no depender de la red en CI).

| # | Fuente | Método | Riesgo/Nota |
|---|---|---|---|
| 1 | **Remote OK** | API JSON pública (`remoteok.com/api`) | Estable; exige atribución y User-Agent identificado |
| 2 | **HN Who's Hiring** | API de Algolia (hilos mensuales) | Parsing de texto libre → heurísticas de extracción; calidad variable pero joyas remotas |
| 3 | **Adzuna** | API oficial con key gratuita | Cubre múltiples países; registrar app en su portal |
| 4 | **Getonboard** | API pública documentada | LA fuente LATAM tech por excelencia; sueldos frecuentes |
| 5 | **Computrabajo (PE)** | Scraping HTML (requests + BeautifulSoup) | El más frágil: respetar robots.txt, throttle 1 req/2s, User-Agent honesto, y aceptar que puede romperse (por eso es UN adapter aislado, no el sistema) |

Regla arquitectónica: **una fuente caída jamás tumba el pipeline** — se loguea en `runs` y se continúa.

---

## 6. Salidas

### 6.1 Dashboard (JS — Vite + vanilla + Chart.js)
Estático, lee `offers.json`. Vistas del MVP:
1. **Tabla rankeada** — score con barra de desglose al expandir, filtros client-side (fuente, remote, score mínimo, texto), link directo a postular.
2. **Gráficos** — (a) distribución de scores, (b) ofertas por fuente, (c) demanda de stack (frecuencia de tags — *side effect valioso: le dice a Luis qué estudiar*), (d) tendencia semanal (del histórico SQLite).
3. **Vista "nuevas desde mi última visita"** (localStorage del último acceso).

Deploy: Netlify (gratis). El pipeline termina copiando `offers.json` al dashboard.

### 6.2 Digest por Gmail
`cli.py digest`: toma las ofertas **nuevas** (no enviadas antes — flag `notified` en DB) con score ≥ umbral configurable, arma HTML compacto (top 10: título, empresa, score+desglose mini, link) y envía.
- **Vía A (preferida):** MCP de Gmail desde Claude Code / configuración MCP local.
- **Vía B (fallback sin MCP):** SMTP de Gmail con App Password (variable de entorno, jamás commiteada).
El módulo `digest.py` genera el HTML; el envío es intercambiable (A o B) tras una interfaz `Sender`.

---

## 7. Plan de construcción por fases (formato compatible con Claude Code)

> Mismas convenciones del plan de DesignSpec Kit: tareas atómicas, Dep, DoD, un commit por tarea.

**FASE 0 — Setup (30 min):** repo `jobdistiller` · venv Python 3.11+ · `requirements.txt` (requests, beautifulsoup4, pyyaml, pytest) · estructura de carpetas · `.env.example` · `.gitignore` (¡data/, .env!) · primer commit.

**FASE 1 — Núcleo sin red (el orden importa: primero lo testeable):**
1-01 `models.py` (dataclass + validación) → 1-02 `profile.yaml` real de Luis + loader con validación de suma=100 → 1-03 `scorer.py` con tests unitarios (5 ofertas sintéticas cubriendo extremos) → 1-04 `dedupe.py` (hash exacto + fuzzy por `title+company` similitud > 0.85) con tests → 1-05 `store.py` SQLite + export JSON.
**DoD de fase:** `pytest` verde sin tocar internet.

**FASE 2 — Adapters (uno por tarea, con fixture grabado):**
2-01 base.py + remoteok → 2-02 getonboard → 2-03 adzuna (registrar key) → 2-04 hn_hiring → 2-05 computrabajo → 2-06 `cli.py run` end-to-end.
**DoD de fase:** `python -m core.cli run` produce `offers.json` con ofertas reales de ≥ 4 fuentes.

**FASE 3 — Dashboard JS:**
3-01 scaffold Vite → 3-02 tabla rankeada + desglose → 3-03 filtros → 3-04 los 4 gráficos → 3-05 deploy Netlify.
**DoD:** URL pública funcionando con datos reales.

**FASE 4 — Digest + automatización:**
4-01 `digest.py` HTML → 4-02 sender SMTP → 4-03 sender MCP (si disponible) → 4-04 GitHub Action cron diario 8:00 am Lima (corre pipeline, commitea offers.json, Netlify auto-deploya, envía digest).
**DoD:** Luis despierta con el digest en su bandeja sin tocar nada.

**FASE 5 — Cierre profesional:** README bilingüe con GIF · screenshots al portafolio · bullet XYZ al CV ("Construí un pipeline en Python que agrega y puntúa ofertas de 5 fuentes con sistema de pesos configurable, dashboard en JS y digest automático diario") · pin en GitHub.

---

## 8. Post-MVP

- **M1 — Asistente de adecuación de CV (la idea original de Luis):** dado el JSON de una oferta + el CV maestro, generar un reporte de brechas y sugerencias de reordenamiento/ énfasis usando SOLO experiencia real (regla dura anti-invención: cada sugerencia debe citar de qué parte del CV maestro sale). Vía API de Claude o como prompt manual.
- **M2 — Scoring semántico:** similitud de embeddings entre descripción y perfil (mejora sobre keywords).
- **M3 — Alertas Telegram** (API más simple que WhatsApp).
- **M4 — Multi-perfil** (compartirlo con colegas).

## 9. Riesgos

1. **Computrabajo cambia su HTML** → adapter aislado, test con fixture avisa, el resto sigue.
2. **Extracción de sueldo/inglés imprecisa** → son heurísticas; el breakdown visible permite detectar errores y ajustar; campo `unknown` siempre neutro, nunca castiga en silencio.
3. **Rate limits / baneos** → throttle por adapter, User-Agent honesto, caché de 12h (no re-fetchear lo mismo el mismo día).
4. **API keys en el repo** → solo env vars; `.env` en gitignore desde la Fase 0; GitHub Action usa Secrets.
5. **Scope creep** → todo lo que no esté en secciones 5-6 es post-MVP por definición.
