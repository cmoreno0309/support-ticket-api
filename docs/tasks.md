# tasks.md — Plan de ejecución

> Deriva de `spec.md` y `plan.md`. Cada tarea indica qué produce y cuál es su
> criterio de "hecho". Los hitos son secuenciales; cada uno cierra con `pytest` en
> verde y un commit.

## Convenciones

- Las tareas se ejecutan en orden: hay dependencias reales entre hitos.
- Al cerrar un hito: `pytest`, `ruff check .` y commit con el nombre del hito.
- No se agregan dependencias ni funcionalidad fuera de lo definido en `plan.md`.
- Si una regla de `spec.md` resulta ambigua, se implementa la interpretación más
  conservadora y se declara en `README.md` -> *Supuestos*.
- Mensajes de error de dominio en español; código, campos e identificadores en
  inglés.

---

## Hito 1 — Esqueleto del proyecto

- [ ] **T-01** Proyecto Django, entorno virtual y `requirements.txt` con las
      dependencias de `plan.md` §1.
      *Hecho:* el servidor de desarrollo levanta.
- [ ] **T-02** App `users` con `User(AbstractUser)`, campo `role` y propiedad
      `is_agent`. `AUTH_USER_MODEL` configurado **antes** de la primera migración.
      *Hecho:* `migrate` corre limpio sobre una base vacía.
- [ ] **T-03** Settings: DRF (JWT, `IsAuthenticated` por defecto, paginación 20,
      filtros, `drf-spectacular`), base de datos por variables de entorno,
      `TIME_ZONE`.
      *Hecho:* `/api/schema/swagger-ui/` carga.
- [ ] **T-04** Endpoints de autenticación (`token`, `refresh`), `/users/me/` y
      `/agents/`.
      *Hecho:* se obtiene un token válido y `me` devuelve el rol del usuario.

## Hito 2 — Dominio

- [ ] **T-05** `tickets/models.py`: enums `Priority` y `Status`, tabla
      tabla `TRANSITIONS` con clave `(desde, hacia)` y roles autorizados, modelos
      `Ticket`, `TicketComment` y `TicketEvent`,
      manager con `visible_to(user)`, generación de `reference`, migración y
      registro en el admin.
- [ ] **T-06** `tickets/exceptions.py`: `DomainError` y subclases con `code` y
      `status_code` (`InvalidStatusTransition` -> 409, `TransitionNotAllowedForRole`
      -> 403, `TicketClosed` -> 409, `NotAnAgent` -> 400, `TicketNotAssigned` -> 409,
      `CloseReasonRequired` -> 400).
- [ ] **T-07** `config/exceptions.py`: handler que traduce `DomainError` al
      formato de error único definido en `plan.md` §4.
      *Hecho:* un error de dominio devuelve `{"error": {...}}` con su código.
- [ ] **T-08** `tickets/services.py`: `create_ticket`, `assign_ticket`,
      `unassign_ticket`, `change_status`, `change_priority` y `add_comment`. Cada
      una dentro de `transaction.atomic`, con `select_for_update` y registro del
      evento correspondiente. Implementa RN-01 a RN-16, incluidos el cierre por
      parte del autor desde `RESOLVED` y el cierre por parte del agente con motivo
      obligatorio.
      *Hecho:* el ciclo de vida completo se ejecuta desde el shell, sin HTTP.
- [ ] **T-09** Tests unitarios de los servicios y de la tabla de transiciones,
      cubriendo las dos preguntas por separado: transición inexistente y
      transición existente vedada por rol.

## Hito 3 — Capa de API

- [ ] **T-10** Serializers: creación, listado, detalle, cambio de estado,
      asignación, comentario y evento de historial.
- [ ] **T-11** `permissions.py`: `IsAgent` e `IsTicketOwnerOrAgent`. La
      autorización de una transición concreta se resuelve en el servicio, contra la
      tabla, no en la clase de permisos.
- [ ] **T-12** `filters.py`, búsqueda y ordenamiento según `plan.md` §4.
- [ ] **T-13** `TicketViewSet` con `get_queryset().visible_to(user)` y las acciones
      `assign`, `unassign`, `status`, `comments` e `history`. Las vistas validan
      entrada y delegan en los servicios; no contienen reglas de negocio.
      *Hecho:* el flujo completo es ejecutable desde Swagger.
- [ ] **T-14** Visibilidad de comentarios internos según rol (RN-08).

## Hito 4 — Verificación

- [ ] **T-15** Tests de API: uno por cada criterio de aceptación CA-01 a CA-16.
      *Hecho:* la suite completa en verde, sin advertencias.
- [ ] **T-16** Comando `seed_demo`: dos agentes, tres clientes y un conjunto de
      tickets en distintos estados con historial coherente, incluyendo al menos uno
      resuelto a la espera del cierre del cliente y uno cerrado por el agente con
      motivo.
- [ ] **T-17** `Dockerfile` y `docker-compose.yml` con PostgreSQL.
      *Hecho:* `docker compose up` levanta la API contra Postgres.

## Hito 5 — Entrega

- [ ] **T-18** `README.md`: descripción, instalación local y con Docker,
      credenciales de prueba, tabla de endpoints, decisiones de diseño (D-01 a
      D-09 en versión resumida), supuestos y alcance excluido con su justificación.
- [ ] **T-19** `ruff check . --fix`, `.gitignore` revisado, sin código muerto y sin
      credenciales ni `SECRET_KEY` reales en el repositorio.
- [ ] **T-20** Historial de commits ordenado por hito y colección de peticiones de
      ejemplo (`requests.http` o Postman).
