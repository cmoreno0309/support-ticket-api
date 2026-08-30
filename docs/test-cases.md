# test-cases.md — Casos de prueba

> Deriva de los criterios de aceptación de `spec.md`. Cada caso indica precondición,
> acción, resultado esperado y de qué criterio proviene. Los marcados como
> *extensión* no están en los criterios: son bordes que conviene cubrir igual.

Actores usados en las precondiciones: `customer_a` (autor), `customer_b` (otro
cliente), `agent_1`, `agent_2`.

---

## 1. Autenticación y acceso

| ID | Precondición | Acción | Esperado |
|---|---|---|---|
| TC-001 | Sin token | `GET /tickets/` | `401` · RN-13 |
| TC-002 | Token expirado | `GET /tickets/` | `401` · extensión |
| TC-003 | Credenciales válidas | `POST /auth/token/` | `200` con `access` y `refresh` · extensión |
| TC-004 | Credenciales inválidas | `POST /auth/token/` | `401` · extensión |

## 2. Creación de solicitudes

| ID | Precondición | Acción | Esperado |
|---|---|---|---|
| TC-010 | `customer_a` autenticado | Crea con asunto, descripción y prioridad válidos | `201`, estado `NEW`, `assigned_to` nulo, `created_by = customer_a` · CA-01 |
| TC-011 | Igual que TC-010 | Consulta el historial del ticket recién creado | Un único evento `CREATED` con actor `customer_a` · CA-01 |
| TC-012 | `customer_a` autenticado | Crea sin asunto | `400`, no se persiste nada · CA-02 |
| TC-013 | `customer_a` autenticado | Crea con `priority = "URGENTE"` | `400` · CA-02 |
| TC-014 | `customer_a` autenticado | Crea enviando `status = "RESOLVED"` y `assigned_to` | Campos ignorados: el ticket queda `NEW` y sin asignar · extensión |
| TC-015 | `agent_1` autenticado | Crea una solicitud | `201`, con el agente como autor · extensión (decidir si se permite y documentarlo) |

## 3. Visibilidad y aislamiento

| ID | Precondición | Acción | Esperado |
|---|---|---|---|
| TC-020 | Un ticket de `customer_a` y otro de `customer_b` | `customer_a` lista tickets | Solo aparece el suyo · CA-03 |
| TC-021 | Ticket de `customer_b` | `customer_a` lo pide por id | `404`, no `403` · CA-03, D-07 |
| TC-022 | Tickets de ambos clientes | `agent_1` lista tickets | Ve los dos · CA-04 |
| TC-023 | Tickets en varios estados | `agent_1` filtra por `status=NEW` | Solo los que están en `NEW` · CA-04 |
| TC-024 | Tickets con y sin agente | `agent_1` filtra por `unassigned=true` | Solo los no asignados · CA-04 |
| TC-025 | 25 tickets visibles | `agent_1` lista sin parámetros | 20 resultados y enlace a la página siguiente · extensión |

## 4. Asignación

| ID | Precondición | Acción | Esperado |
|---|---|---|---|
| TC-030 | Ticket en `NEW` | `agent_1` lo asigna a `agent_2` | `200`, `assigned_to = agent_2`, estado `ASSIGNED` · CA-05 |
| TC-031 | Igual que TC-030 | Consulta el historial | Dos eventos: `ASSIGNED` y `STATUS_CHANGED` de `NEW` a `ASSIGNED` · CA-05 |
| TC-032 | Ticket en `NEW` | `agent_1` intenta asignarlo a `customer_b` | `400`, el ticket no cambia · CA-06, RN-06 |
| TC-033 | Ticket en `NEW` | `customer_a` intenta asignarlo | `403` · RN-02 |
| TC-034 | Ticket en `IN_PROGRESS` asignado a `agent_1` | `agent_2` se lo reasigna a sí mismo | `200`, el estado **no** cambia, queda evento de asignación · extensión |
| TC-035 | Ticket en `CLOSED` | `agent_1` intenta asignarlo | `409` · RN-05 |
| TC-036 | Ticket asignado | `agent_1` lo desasigna | `200`, `assigned_to` nulo, evento `UNASSIGNED` · extensión |

## 5. Transiciones de estado

| ID | Precondición | Acción | Esperado |
|---|---|---|---|
| TC-040 | Ticket en `ASSIGNED` | `agent_1` lo pasa a `IN_PROGRESS` | `200`, evento con valor anterior y nuevo · CA-07 |
| TC-041 | Ticket en `NEW` | `agent_1` lo pasa a `RESOLVED` | `409` con código `invalid_status_transition`, el ticket conserva `NEW` · CA-08 |
| TC-042 | Ticket en `NEW` sin agente | `agent_1` lo pasa a `IN_PROGRESS` | `409`, falta agente asignado · RN-04 |
| TC-043 | Ticket en `IN_PROGRESS` | `customer_a` intenta pasarlo a `RESOLVED` | `403` · CA-11 |
| TC-044 | Ticket en `IN_PROGRESS` | `agent_1` lo pasa a `PENDING_CUSTOMER` y luego de vuelta a `IN_PROGRESS` | Ambas aceptadas, dos eventos · RN-03 |
| TC-045 | Ticket en `RESOLVED` | `agent_1` lo reabre a `IN_PROGRESS` | `200`, evento de reapertura · CA-13 |
| TC-046 | Ticket en `IN_PROGRESS` | `agent_1` envía `status = "PAUSADO"` | `400`, valor fuera del enum · extensión |
| TC-047 | Ticket en `IN_PROGRESS` | `agent_1` lo pasa a `IN_PROGRESS` | `409`, transición a sí mismo no declarada · extensión |
| TC-048 | Ticket en `RESOLVED` | Se pasa a `CLOSED` | `resolved_at` y `closed_at` quedan poblados · RN-11 |

## 6. Cierre

| ID | Precondición | Acción | Esperado |
|---|---|---|---|
| TC-050 | Ticket propio en `RESOLVED` | `customer_a` lo cierra | `200`, `CLOSED`, evento con `customer_a` como actor · CA-14 |
| TC-051 | Ticket propio en `IN_PROGRESS` | `customer_a` intenta cerrarlo | `403`, conserva su estado · CA-15, RN-14 |
| TC-052 | Ticket de `customer_b` en `RESOLVED` | `customer_a` intenta cerrarlo | `404` · CA-15 |
| TC-053 | Ticket en `PENDING_CUSTOMER` | `agent_1` lo cierra con motivo | `200`, `CLOSED`, la nota aparece en el historial · CA-16, RN-15 |
| TC-054 | Ticket en `PENDING_CUSTOMER` | `agent_1` lo cierra sin motivo | `400` · CA-16, RN-16 |
| TC-055 | Ticket en `RESOLVED` | `agent_1` lo cierra sin motivo | `200`: la nota solo es obligatoria al cerrar algo no resuelto · RN-16 |
| TC-056 | Ticket en `CLOSED` | `agent_1` intenta pasarlo a `IN_PROGRESS` | `409`, no hay reapertura · CA-09, RN-05 |
| TC-057 | Ticket en `CLOSED` | `agent_1` cambia la prioridad | `409` · RN-05 |

## 7. Comentarios

| ID | Precondición | Acción | Esperado |
|---|---|---|---|
| TC-060 | Ticket en `IN_PROGRESS` | `agent_1` agrega comentario interno | `201` · CA-10 |
| TC-061 | Existe el comentario interno de TC-060 | `agent_2` lista comentarios | Lo ve · CA-10 |
| TC-062 | Existe el comentario interno de TC-060 | `customer_a`, autor del ticket, lista comentarios | No aparece · CA-10, RN-08 |
| TC-063 | Ticket propio en `IN_PROGRESS` | `customer_a` comenta | `201`, el comentario se guarda como público aunque pida `is_internal=true` · RN-08 |
| TC-064 | Ticket de `customer_b` | `customer_a` intenta comentar | `404` · RN-10 |
| TC-065 | Ticket propio en `RESOLVED` | `customer_a` comenta su disconformidad | `201`: `RESOLVED` admite comentarios · CA-13, RN-08 |
| TC-066 | Ticket en `CLOSED` | Cualquiera intenta comentar | `409` · RN-05 |
| TC-067 | Ticket en `IN_PROGRESS` | `agent_1` envía un cuerpo vacío | `400` · extensión |

## 8. Historial

| ID | Precondición | Acción | Esperado |
|---|---|---|---|
| TC-070 | Ticket creado, asignado, en progreso y comentado | `agent_1` consulta el historial | Eventos en orden cronológico descendente, con actor y valores · CA-12 |
| TC-071 | Cualquier ticket | `POST` o `DELETE` sobre `/history/` | `405` · CA-12, RN-09 |
| TC-072 | Ticket de `customer_a` | `customer_a` consulta su historial | `200`: el historial es visible para el autor · RN-10 |
| TC-073 | Ticket en `RESOLVED` reabierto y vuelto a resolver | Consulta del historial | Refleja las dos transiciones en orden · CA-13 |
| TC-074 | Cualquier evento | Intento de modificar el actor de un evento vía API | No existe endpoint que lo permita · RN-09 |

## 9. Reglas de dominio sin HTTP

Estos casos se prueban directamente contra `services.py`, sin cliente de API.

| ID | Caso | Esperado |
|---|---|---|
| TC-080 | Tabla de transiciones: toda clave `(desde, hacia)` tiene al menos un rol | Ninguna entrada vacía |
| TC-081 | `CLOSED` no aparece como origen en ninguna clave | Confirmado |
| TC-082 | Transición inexistente | Lanza `InvalidStatusTransition` |
| TC-083 | Transición existente ejecutada por un rol no autorizado | Lanza `TransitionNotAllowedForRole`, distinta de la anterior |
| TC-084 | Error de dominio dentro de `change_status` | La transacción se revierte: ni cambio de estado ni evento |
| TC-085 | `create_ticket` invocado dos veces | Referencias `TCK-…` distintas |

## 10. Flujos completos (end-to-end)

Cada uno es **un solo test** que recorre la vida entera de una solicitud. No
repiten lo que ya cubren los casos anteriores: lo que verifican es la
**secuencia** —que el historial cuente la historia correcta, en el orden correcto,
con el actor correcto en cada paso—. Es lo que ningún caso aislado puede detectar.

### TC-100 — Camino feliz: el cliente cierra

| # | Actor | Acción | Estado resultante |
|---|---|---|---|
| 1 | `customer_a` | Crea la solicitud | `NEW` |
| 2 | `agent_1` | La toma para sí | `ASSIGNED` |
| 3 | `agent_1` | Empieza a trabajarla | `IN_PROGRESS` |
| 4 | `agent_1` | Agrega un comentario interno con el diagnóstico | `IN_PROGRESS` |
| 5 | `agent_1` | La marca resuelta con nota de lo que hizo | `RESOLVED` |
| 6 | `customer_a` | Revisa y la cierra | `CLOSED` |

**Verificaciones finales:** estado `CLOSED`; `assigned_to = agent_1`;
`resolved_at` y `closed_at` poblados y en ese orden; el historial contiene
exactamente siete eventos —creación, asignación, cambio a `ASSIGNED`, cambio a
`IN_PROGRESS`, comentario, cambio a `RESOLVED`, cambio a `CLOSED`—; el actor del
último es `customer_a` y el de los cinco anteriores es `agent_1`; el comentario
interno del paso 4 no aparece cuando `customer_a` lista comentarios.

### TC-101 — Disconformidad: el cliente reclama y se reabre

| # | Actor | Acción | Estado resultante |
|---|---|---|---|
| 1 | `customer_a` | Crea la solicitud | `NEW` |
| 2 | `agent_1` | La asigna y la trabaja | `IN_PROGRESS` |
| 3 | `agent_1` | La marca resuelta | `RESOLVED` |
| 4 | `customer_a` | Comenta que faltó parte del problema | `RESOLVED` |
| 5 | `agent_1` | La reabre | `IN_PROGRESS` |
| 6 | `agent_1` | Vuelve a resolverla | `RESOLVED` |
| 7 | `customer_a` | La cierra | `CLOSED` |

**Verificaciones finales:** el historial registra **dos** entradas a `RESOLVED` y
la reapertura entre ambas; `resolved_at` corresponde a la segunda resolución, no a
la primera; el comentario del paso 4 es público y visible para ambos actores; el
paso 4 no altera el estado.

### TC-102 — Sin respuesta: el agente cierra

| # | Actor | Acción | Estado resultante |
|---|---|---|---|
| 1 | `customer_a` | Crea la solicitud | `NEW` |
| 2 | `agent_1` | La asigna y pide información al cliente | `PENDING_CUSTOMER` |
| 3 | `agent_1` | Cierra por falta de respuesta, indicando el motivo | `CLOSED` |
| 4 | `customer_a` | Intenta comentar | `409` |

**Verificaciones finales:** estado `CLOSED` sin haber pasado por `RESOLVED`;
`resolved_at` nulo y `closed_at` poblado; el motivo del cierre aparece en el
historial; ninguna acción posterior modifica la solicitud.

---

## 11. Pendiente de decisión

- **Concurrencia (TC-090).** Dos agentes ejecutan la misma transición a la vez;
  se espera que una gane y la otra reciba `409`. Requiere PostgreSQL y ejecución
  con hilos: en SQLite el bloqueo de fila no aplica. Se documenta como probado a
  mano, o se omite declarándolo en el README.
