# Support Ticket API

API REST para que agentes de soporte y clientes registren, asignen y resuelvan
solicitudes de soporte, con historial auditable de cada cambio. Ver
`docs/spec.md` (qué y por qué) y `docs/plan.md` (cómo) para el detalle
completo.

## Stack

Python 3.12, Django 5.2 + Django REST Framework, JWT (`simplejwt`),
`django-filter`, `drf-spectacular` (OpenAPI/Swagger). SQLite en desarrollo y
tests; PostgreSQL vía Docker Compose.

## Instalación local

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo       # opcional: usuarios y tickets de ejemplo
python manage.py runserver
```

La API queda en `http://localhost:8000/api/v1/`, la documentación interactiva
en `http://localhost:8000/api/schema/swagger-ui/` y el admin de Django en
`http://localhost:8000/admin/`.

Configuración por variables de entorno (ver `.env.example`): `SECRET_KEY`,
`DEBUG`, `ALLOWED_HOSTS`, y `DB_ENGINE=postgresql` + `DB_NAME`/`DB_USER`/
`DB_PASSWORD`/`DB_HOST`/`DB_PORT` para apuntar a PostgreSQL en vez de SQLite.
Sin `.env`, corre contra SQLite con valores por defecto.

## Instalación con Docker

```bash
docker compose up --build
```

Levanta la API en `http://localhost:8000/` contra PostgreSQL (expuesto también
en el host en el puerto `5433`, para no chocar con un Postgres local en el
`5432`). Las migraciones corren automáticamente al iniciar el contenedor. Para
cargar los datos de ejemplo dentro del contenedor:

```bash
docker compose exec api python manage.py seed_demo
```

## Credenciales de prueba

Generadas por `python manage.py seed_demo` (contraseña `demo12345` para
todas):

| Usuario | Rol |
|---|---|
| `agent_1`, `agent_2` | Agente |
| `customer_1`, `customer_2`, `customer_3` | Cliente |

El seed crea seis solicitudes, una en cada estado del ciclo de vida —
incluida una en `RESOLVED` a la espera de que el cliente la cierre y otra
`CLOSED` directamente por un agente con motivo—, cada una con su historial
generado a través de `tickets/services.py` (no insertado a mano), para que
sea coherente con lo que la API produciría en uso real.

Ver también `requests.http` para una colección de peticiones de ejemplo
contra los endpoints principales.

## Endpoints

Base `/api/v1/`. Todos requieren `Authorization: Bearer <access_token>`,
salvo la obtención del propio token.

| Método | Ruta | Rol | Códigos |
|---|---|---|---|
| POST | `/auth/token/` | público | 200, 401 |
| POST | `/auth/token/refresh/` | público | 200, 401 |
| GET | `/users/me/` | cualquiera | 200 |
| GET | `/agents/` | agente | 200, 403 |
| POST | `/tickets/` | cualquier autenticado* | 201, 400 |
| GET | `/tickets/` | cualquiera (filtrado por rol) | 200 |
| GET | `/tickets/{id}/` | autor o agente | 200, 404 |
| PATCH | `/tickets/{id}/` | agente (solo `priority`) | 200, 400, 403, 409 |
| POST | `/tickets/{id}/assign/` | agente | 200, 400, 403, 409 |
| POST | `/tickets/{id}/unassign/` | agente | 200, 403, 409 |
| POST | `/tickets/{id}/status/` | agente; el autor solo para `RESOLVED → CLOSED` | 200, 400, 403, 404, 409 |
| GET | `/tickets/{id}/comments/` | autor (públicos) o agente (todos) | 200 |
| POST | `/tickets/{id}/comments/` | autor (público) o agente | 201, 403, 409 |
| GET | `/tickets/{id}/history/` | autor o agente | 200, 405 en escritura |

`*` ver *Supuestos*: la creación no está restringida a `CUSTOMER` en el código.

**Filtros en `GET /tickets/`:** `status`, `priority`, `assigned_to`,
`unassigned=true`, `created_after`, `created_before`; `search` sobre asunto y
descripción; `ordering` por `created_at`, `priority`, `status`. Paginación de
20 resultados por página.

**Errores de dominio** (formato único, cualquier `DomainError`):

```json
{
  "error": {
    "code": "invalid_status_transition",
    "message": "No se puede pasar de NEW a RESOLVED.",
    "allowed": ["ASSIGNED", "IN_PROGRESS", "CLOSED"]
  }
}
```

## Decisiones de diseño

- **D-01 — Capa de servicios.** La lógica de negocio vive en
  `tickets/services.py`, no en las vistas. Las vistas validan entrada y
  delegan; los servicios aplican reglas y escriben historial dentro de
  `transaction.atomic`. Permite probar las reglas sin HTTP (`tests/test_services.py`).
- **D-02 — Historial explícito.** `TicketEvent` es un modelo propio que
  registra el evento de negocio (no un diff de fila vía señales), con actor
  siempre disponible. Es append-only: la API solo expone `GET` sobre él.
- **D-03 — Máquina de estados como dato.** `TRANSITIONS` en
  `tickets/models.py` mapea `(desde, hacia)` al conjunto de roles que pueden
  ejecutar esa transición. Nada de `if/elif` de estados o roles repartido por
  las vistas.
- **D-04 — `409` vs `403` vs `400`.** Transición inexistente en la tabla →
  `InvalidStatusTransition` (409, el recurso no lo permite). Transición
  existente pero vedada al rol del actor → `TransitionNotAllowedForRole`
  (403, problema de autorización). Errores de payload → `400`.
- **D-05 — Rol como campo.** `User.role` con propiedad `is_agent`, en vez de
  `django.contrib.auth.Group`. Más simple y testeable para dos roles.
  `AUTH_USER_MODEL` quedó definido antes de la primera migración.
- **D-06 — UUID + `reference` legible.** El id (UUID) no expone volumen de
  negocio; `reference` (`TCK-XXXXXXXX`) sirve para hablar del caso con el
  cliente.
- **D-07 — Aislamiento por queryset.** `Ticket.objects.visible_to(user)`
  filtra en el queryset, no permiso por permiso. Un ticket ajeno da `404`, no
  `403`: no revela su existencia. `IsTicketOwnerOrAgent` es la comprobación de
  objeto que acompaña a ese filtrado, no lo reemplaza.
- **D-08 — `select_for_update`.** Cada función de `services.py` bloquea la
  fila del ticket dentro de la transacción antes de mutarla, para evitar que
  dos agentes ejecuten la misma transición a la vez. No tiene efecto en
  SQLite (usado en tests); si aplica en PostgreSQL. No hay un test
  automatizado de concurrencia (requiere hilos + Postgres): queda como
  limitación conocida, documentada también en `docs/test-cases.md` §11.
- **D-09 — JWT.** `simplejwt` en vez de `TokenAuthentication`, por tokens con
  expiración y refresh. La sesión de Django solo se usa para el admin y para
  el botón "Authorize" de Swagger si se prueba con navegador.

## Supuestos

- **¿Quién puede crear una solicitud?** La tabla de endpoints de `plan.md`
  marca `POST /tickets/` como acción de "cliente", pero el código no restringe
  el rol de quien crea: cualquier usuario autenticado puede hacerlo, y queda
  como autor. Es la interpretación más simple del caso marcado como abierto
  en `docs/test-cases.md` (TC-015); si se quisiera restringir a `CUSTOMER`,
  es un permiso adicional en `TicketViewSet.get_permissions()` para la acción
  `create`.
- **Alta de usuarios.** Los usuarios los crea un administrador (Django admin
  o `createsuperuser`); no hay autoregistro. Se entrega `seed_demo` como
  comando de datos de prueba.
- **Autoasignación.** Un agente puede asignarse una solicitud a sí mismo; es
  el caso normal, no un caso especial.
- **Cierre de una solicitud.** El agente declara la resolución (`RESOLVED`);
  el cliente autor cierra desde ahí, o un agente cierra desde cualquier
  estado no final en cualquier momento (RN-14/RN-15).
- **No hay reapertura desde `CLOSED`.** Es un estado final sin salida. Un
  cierre equivocado por parte del cliente es irreversible: limitación
  conocida y deliberada (spec.md §8, pregunta 4).

## Fuera de alcance

Excluidos deliberadamente del proyecto (detalle y justificación en
`docs/spec.md` §7):

- Interfaz de usuario — la API se explora vía Swagger y el admin de Django.
- Notificaciones por correo o push.
- SLA, tiempos de respuesta y escalamiento automático.
- Cierre automático por inactividad — es un criterio operativo del equipo,
  no una regla del sistema; el filtro por fecha del listado alcanza para que
  un agente encuentre los casos antiguos y los cierre a mano.
- Derivación entre solicitudes — si un reclamo excede el alcance del caso
  original, el agente pide abrir uno nuevo por comentario; no se modela un
  vínculo entre solicitudes.
- Archivos adjuntos — la evidencia de resolución se registra como nota del
  cambio de estado, en el historial.
- Multi-tenant / organizaciones.
- Búsqueda avanzada o full-text más allá del filtro simple por asunto y
  descripción.

## Tests

```bash
pytest            # 22 tests: unitarios de dominio + de API por cada CA-01..CA-16
ruff check .
```

`tickets/tests/test_transitions.py` y `test_services.py` prueban
`services.py` y la tabla de transiciones sin HTTP. `test_api.py` cubre cada
criterio de aceptación de `docs/spec.md` §6 con `APIClient`.
