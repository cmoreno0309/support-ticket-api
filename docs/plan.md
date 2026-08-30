# plan.md — Diseño técnico

> Documento de **cómo**. Deriva de `spec.md`. Versión 0.1 — 28/08/2026.

---

## 1. Stack

| Componente | Elección |
|---|---|
| Lenguaje | Python 3.12 |
| Framework | Django 5.x + Django REST Framework |
| Auth | `djangorestframework-simplejwt` (JWT) + sesión para el admin |
| Filtros | `django-filter` |
| Documentación | `drf-spectacular` (OpenAPI 3 + Swagger UI) |
| BD | SQLite en desarrollo y tests; PostgreSQL vía Docker Compose |
| Tests | `pytest` + `pytest-django` |
| Formato | `ruff` (lint + format) |

## 2. Estructura del proyecto

```
support-desk/
├── config/                 # settings, urls, exception handler
├── users/                  # User custom con rol
├── tickets/
│   ├── models.py           # Ticket, TicketComment, TicketEvent
│   ├── services.py         # lógica de dominio (equivalente a @Service)
│   ├── exceptions.py       # errores de dominio
│   ├── serializers.py
│   ├── permissions.py
│   ├── filters.py
│   ├── views.py            # TicketViewSet + acciones
│   └── tests/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## 3. Modelo de datos

**users_user** (extiende `AbstractUser`)

| Campo | Tipo | Nota |
|---|---|---|
| id | int | pk |
| username, email, password, first_name, last_name | — | heredados |
| role | varchar(16) | `CUSTOMER` \| `AGENT` |

**tickets_ticket**

| Campo | Tipo | Nota |
|---|---|---|
| id | uuid | pk, no secuencial || reference | varchar(20) | `TCK-XXXXXXXX`, único, legible |
| subject | varchar(200) | requerido |
| description | text | requerido |
| priority | varchar(16) | choices |
| status | varchar(24) | choices, default `NEW` |
| created_by | fk users_user | `PROTECT`, related_name `tickets_created` |
| assigned_to | fk users_user | null, `SET_NULL`, related_name `tickets_assigned` |
| created_at / updated_at | datetime | auto |
| assigned_at / resolved_at / closed_at | datetime | null |

Índices: `status`, `priority`, `assigned_to`, `created_by`. Orden por `-created_at`.

**tickets_ticketcomment**

| Campo | Tipo |
|---|---|
| id | uuid pk |
| ticket | fk `CASCADE`, related_name `comments` |
| author | fk `PROTECT` |
| body | text |
| is_internal | bool, default `True` |
| created_at | datetime |

**tickets_ticketevent**

| Campo | Tipo |
|---|---|
| id | uuid pk |
| ticket | fk `CASCADE`, related_name `events` |
| actor | fk null `SET_NULL` |
| event_type | varchar(24) — `CREATED`, `STATUS_CHANGED`, `ASSIGNED`, `UNASSIGNED`, `PRIORITY_CHANGED`, `COMMENT_ADDED` |
| field / old_value / new_value | varchar(64), nullables |
| note | text, opcional |
| created_at | datetime |

Sin `update()` ni `delete()` expuestos: tabla append-only.

## 4. Contrato de API

Base: `/api/v1/`. Todo requiere `Authorization: Bearer <token>`.

| Método | Ruta | Rol | Códigos |
|---|---|---|---|
| POST | `/auth/token/` | público | 200, 401 |
| POST | `/auth/token/refresh/` | público | 200, 401 |
| GET | `/users/me/` | cualquiera | 200 |
| GET | `/agents/` | agente | 200, 403 |
| POST | `/tickets/` | cliente | 201, 400 |
| GET | `/tickets/` | cualquiera (filtrado por rol) | 200 |
| GET | `/tickets/{id}/` | autor o agente | 200, 404 |
| PATCH | `/tickets/{id}/` | agente (solo `priority`) | 200, 400, 403, 409 |
| POST | `/tickets/{id}/assign/` | agente | 200, 400, 403, 409 |
| POST | `/tickets/{id}/unassign/` | agente | 200, 403, 409 |
| POST | `/tickets/{id}/status/` | agente; el autor solo para `RESOLVED → CLOSED` | 200, 400, 403, 404, 409 |
| GET | `/tickets/{id}/comments/` | autor (públicos) o agente (todos) | 200 |
| POST | `/tickets/{id}/comments/` | autor (público) o agente | 201, 403, 409 |
| GET | `/tickets/{id}/history/` | autor o agente | 200 |

**Filtros en el listado:** `status`, `priority`, `assigned_to`, `unassigned=true`,
`created_after`, `created_before`; `search` sobre asunto y descripción;
`ordering` por `created_at`, `priority`, `status`. Paginación de 20.

**Ejemplo — cambio de estado**

```http
POST /api/v1/tickets/{id}/status/
{ "status": "IN_PROGRESS", "note": "Reproducido en QA" }
```

**Error de dominio (formato único)**

```json
{
  "error": {
    "code": "invalid_status_transition",
    "message": "No se puede pasar de NEW a RESOLVED.",
    "allowed": ["ASSIGNED", "IN_PROGRESS", "CLOSED"]
  }
}
```

## 5. Decisiones de diseño

Cada una va también en el README, en una sección corta. Es lo que te van a
preguntar en la entrevista.

**D-01 — Capa de servicios.** La lógica de dominio vive en `tickets/services.py`,
no en las vistas ni en los serializers. Las vistas validan entrada y traducen
errores; los servicios aplican reglas y escriben historial, dentro de
`transaction.atomic`. *Alternativa descartada:* poner todo en el `ModelViewSet`;
más corto, pero mezcla transporte con negocio y hace imposible testear reglas sin
HTTP.

**D-02 — Historial explícito.** Modelo `TicketEvent` propio en lugar de
`django-simple-history` o señales. Se registra el evento de negocio, no el diff de
la fila, y no hay efectos ocultos. *Alternativa descartada:* señales
`post_save`; magia difícil de rastrear y sin actor disponible.

**D-03 — Máquina de estados como dato, sensible al rol.** La tabla vive en el
modelo como un diccionario `TRANSITIONS` cuya clave es `(desde, hacia)` y cuyo
valor es el conjunto de roles que pueden ejecutar esa transición
(`{AGENT}`, `{AGENT, OWNER}`). No hay `if/elif` de estados ni de roles repartidos
por las vistas. La consulta se resuelve con dos preguntas separadas: *¿existe la
transición?* y *¿este usuario puede ejecutarla?*, que producen errores distintos
(ver D-04). *Alternativa descartada:* la tabla simple `desde → {hacia}` más
comprobaciones de rol en la vista; se rompe en cuanto una misma transición cambia
de dueño según quién la pida, como ocurre con `RESOLVED → CLOSED`.

**D-04 — `409 Conflict` para transiciones inválidas, `403` para transiciones
vedadas.** Si la transición no existe en la tabla, la petición está bien formada y
lo que falla es el estado del recurso: `409`. Si existe pero el rol no la tiene
permitida —un cliente intentando cerrar un ticket en `IN_PROGRESS`— el problema es
de autorización: `403`. `400` queda para errores de validación del payload.
Distinguir los tres es una señal de criterio.

**D-05 — Rol como campo, no como Group.** `role` en el modelo de usuario, con
propiedad `is_agent`. Más explícito y testeable para dos roles. Con más roles y
permisos finos, Groups sería lo correcto. *Nota:* el `AUTH_USER_MODEL` custom debe
definirse **antes** de la primera migración.

**D-06 — UUID como pk del ticket + `reference` legible.** El id no expone volumen
de negocio; la referencia sirve para hablar del caso con el cliente.

**D-07 — Aislamiento por queryset.** El filtrado por rol se hace en
`get_queryset()` (`visible_to(user)`), no comprobando permisos objeto por objeto.
Un ticket ajeno responde `404`, no `403`: no se revela su existencia.

**D-08 — `select_for_update` al cambiar estado.** Bloqueo de fila dentro de la
transacción para evitar que dos agentes hagan la misma transición a la vez. En
SQLite no aplica, en PostgreSQL sí; se documenta.

**D-09 — JWT.** `simplejwt` en lugar de `TokenAuthentication`, por tokens con
expiración y refresh. Sesión activa solo para el admin y el Swagger.

## 6. Estrategia de pruebas

- **Unitarias** sobre `services.py` y la tabla de transiciones: sin HTTP, rápidas.
- **De API** con `APIClient`, una por cada criterio de aceptación CA-01..CA-12.
- Fixtures en `conftest.py`: `customer`, `other_customer`, `agent`, `other_agent`,
  `ticket_new`, `ticket_assigned`, `ticket_closed`.
- Objetivo: que `pytest` corra en verde sin red ni servicios externos.

## 7. Entorno de desarrollo

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

La API queda en `http://localhost:8000/api/v1/` y la documentación en
`/api/schema/swagger-ui/`.

Con Docker Compose se levanta la app en el puerto 8000 y PostgreSQL en el 5433
por defecto, para no chocar con una instancia local en el 5432. El puerto y las
credenciales se configuran por variables de entorno (`.env.example`).

## 8. Riesgos técnicos

| Riesgo | Mitigación |
|---|---|
| Definir el modelo de usuario custom después de la primera migración obliga a rehacer el esquema | Es la primera tarea del plan de ejecución |
| Dos agentes cambiando el estado del mismo ticket a la vez | `select_for_update` dentro de la transacción (D-08) |
| Divergencia entre SQLite (tests) y PostgreSQL (Docker) | Sin SQL crudo ni tipos específicos de motor; el bloqueo de fila queda documentado como no efectivo en SQLite |
| Crecimiento de alcance fuera de lo pedido | La sección 7 de `spec.md` fija los límites de forma explícita |
