# spec.md — Support Request Management System

> Documento de **qué** y **por qué**. No contiene decisiones de implementación.
> Estado: borrador para revisión. Versión 0.1 — 28/08/2026.

---

## 1. Problema

Los agentes internos de soporte necesitan un lugar único donde revisar, asignar y
resolver las incidencias que reportan los clientes. Hoy no existe ese registro,
por lo que no hay trazabilidad de quién atendió qué ni de cómo evolucionó cada
incidencia.

## 2. Objetivo

Exponer una API REST que permita registrar solicitudes de soporte y gestionarlas
durante todo su ciclo de vida, dejando registro auditable de cada cambio.

## 3. Actores

| Actor | Descripción | Qué puede hacer |
|---|---|---|
| **Cliente** (`CUSTOMER`) | Usuario que reporta una incidencia | Crear solicitudes, ver **solo las suyas**, comentar públicamente en ellas, cerrar las que el agente ya dio por resueltas |
| **Agente** (`AGENT`) | Personal interno de soporte | Ver todas las solicitudes, asignarlas, cambiar estado, comentar internamente, ver historial |
| **Administrador** | Agente con permisos de Django admin | Todo lo anterior + gestión de usuarios |

## 4. Conceptos del dominio

### 4.1 Solicitud de soporte (Ticket)

Incidencia reportada por un cliente. Contiene asunto, descripción, prioridad,
estado, autor y, opcionalmente, el agente asignado.

**Prioridades:** `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.

**Estados y ciclo de vida:**

| Estado | Significado |
|---|---|
| `NEW` | Recién creada, sin agente asignado |
| `ASSIGNED` | Tiene agente responsable, aún no se trabaja |
| `IN_PROGRESS` | El agente está trabajando en ella |
| `PENDING_CUSTOMER` | Esperando información del cliente |
| `RESOLVED` | Solución entregada, pendiente de cierre |
| `CLOSED` | Terminada. Estado final |

**Transiciones permitidas:** cada transición define además qué rol puede
ejecutarla.

| Desde | Hacia | Quién |
|---|---|---|
| `NEW` | `ASSIGNED`, `IN_PROGRESS` | Agente |
| `ASSIGNED` | `IN_PROGRESS`, `PENDING_CUSTOMER` | Agente |
| `IN_PROGRESS` | `PENDING_CUSTOMER`, `RESOLVED` | Agente |
| `PENDING_CUSTOMER` | `IN_PROGRESS`, `RESOLVED` | Agente |
| `RESOLVED` | `IN_PROGRESS` (reapertura) | Agente |
| `RESOLVED` | `CLOSED` | **Autor de la solicitud** o agente |
| cualquier estado no final | `CLOSED` | Agente |
| `CLOSED` | — | — |

### 4.2 Comentario

Nota asociada a una solicitud. Puede ser **interna** (visible solo para agentes)
o **pública** (visible también para el cliente autor de la solicitud).

### 4.3 Evento de historial

Registro inmutable de un cambio sobre la solicitud. Lo genera el sistema, nunca
el cliente de la API. Tipos: creación, cambio de estado, asignación,
desasignación, cambio de prioridad, comentario agregado.

---

## 5. Reglas de negocio

| ID | Regla |
|---|---|
| **RN-01** | Toda solicitud nace en estado `NEW`, sin agente asignado. El autor es siempre el usuario autenticado. |
| **RN-02** | Los cambios de estado los ejecuta un agente, con una única excepción: el autor de la solicitud puede pasarla de `RESOLVED` a `CLOSED` (RN-14). |
| **RN-03** | Un cambio de estado debe respetar la tabla de transiciones. Una transición no permitida se rechaza y **no** modifica la solicitud. Si la transición existe pero el rol del solicitante no puede ejecutarla, se rechaza por permisos, no por estado. |
| **RN-04** | No se puede pasar a `IN_PROGRESS` ni a `RESOLVED` si la solicitud no tiene agente asignado. |
| **RN-05** | `CLOSED` es final: no admite cambios de estado, asignación, prioridad ni nuevos comentarios. No hay reapertura desde `CLOSED`. |
| **RN-06** | Solo se puede asignar a un usuario con rol `AGENT`. |
| **RN-07** | Asignar una solicitud en `NEW` la mueve automáticamente a `ASSIGNED`. Se registran ambos eventos. |
| **RN-08** | Los comentarios internos solo pueden ser creados y leídos por agentes. Un cliente solo puede crear comentarios públicos y solo en sus propias solicitudes. Una solicitud en `RESOLVED` **sí** admite comentarios: es el canal por el que el cliente manifiesta disconformidad. |
| **RN-09** | El historial es de solo lectura vía API y se genera automáticamente: un evento por cada cambio, con actor, valor anterior, valor nuevo y fecha. |
| **RN-10** | Un cliente solo accede a las solicitudes que él creó. Un agente accede a todas. |
| **RN-11** | Al entrar en `RESOLVED` se registra la fecha de resolución; al entrar en `CLOSED`, la de cierre. |
| **RN-12** | La prioridad solo puede modificarla un agente, y el cambio queda en el historial. El asunto y la descripción no se editan después de creada la solicitud. |
| **RN-13** | Todos los endpoints requieren autenticación. No hay acceso anónimo. |
| **RN-14** | El autor de una solicitud puede cerrarla únicamente cuando está en `RESOLVED`. Desde cualquier otro estado, el cierre le está vedado. Nunca puede cerrar una solicitud ajena. |
| **RN-15** | Un agente puede cerrar una solicitud desde cualquier estado no final, sin requerir que pase antes por `RESOLVED`. Es la salida para casos sin respuesta del cliente, duplicados o fuera de alcance. |
| **RN-16** | Todo cambio de estado admite una nota opcional que queda en el historial. En un cierre ejecutado por un agente sobre una solicitud no resuelta, la nota es obligatoria: es el motivo del cierre. |

---

## 6. Criterios de aceptación

Cada criterio se traduce en al menos un test automatizado.

**CA-01 — Creación**
Dado un cliente autenticado, cuando crea una solicitud con asunto, descripción y
prioridad válidos, entonces se devuelve `201`, la solicitud queda en `NEW`, sin
agente, con él como autor, y el historial contiene un evento de creación.

**CA-02 — Validación de entrada**
Dado un cliente autenticado, cuando envía una solicitud sin asunto o con una
prioridad inexistente, entonces se devuelve `400` y no se crea nada.

**CA-03 — Aislamiento por rol**
Dado un cliente con una solicitud propia y otra ajena, cuando lista solicitudes,
entonces solo ve la propia; al pedir la ajena por id recibe `404`.

**CA-04 — Visibilidad del agente**
Dado un agente, cuando lista solicitudes, entonces ve las de todos los clientes y
puede filtrar por estado, prioridad y agente asignado.

**CA-05 — Asignación**
Dado un agente y una solicitud en `NEW`, cuando la asigna a otro agente, entonces
la solicitud queda `ASSIGNED` con ese responsable y el historial suma un evento de
asignación y uno de cambio de estado.

**CA-06 — Asignación inválida**
Cuando se intenta asignar una solicitud a un usuario con rol `CUSTOMER`, entonces
se devuelve `400` y la solicitud no cambia.

**CA-07 — Transición válida**
Dado un agente y una solicitud `ASSIGNED`, cuando la pasa a `IN_PROGRESS`,
entonces se devuelve `200`, el estado cambia y queda un evento con estado anterior
y nuevo.

**CA-08 — Transición inválida**
Dada una solicitud en `NEW`, cuando un agente intenta pasarla directamente a
`RESOLVED`, entonces se devuelve `409`, con un código de error identificable, y la
solicitud conserva su estado.

**CA-09 — Estado final**
Dada una solicitud `CLOSED`, cualquier intento de cambiar estado, asignar o
comentar devuelve `409`.

**CA-10 — Comentario interno**
Dado un agente, cuando agrega un comentario interno, entonces se devuelve `201`;
al listar comentarios, el agente lo ve y el cliente autor de la solicitud no.

**CA-11 — Permisos de cliente**
Cuando un cliente intenta cambiar el estado de su propia solicitud, entonces se
devuelve `403`.

**CA-12 — Historial**
Dada una solicitud creada, asignada, movida a `IN_PROGRESS` y comentada, cuando se
consulta el historial, entonces devuelve los eventos en orden cronológico
descendente con actor y valores; y cualquier intento de escribir sobre el
historial devuelve `405`.

**CA-13 — Disconformidad y reapertura**
Dada una solicitud en `RESOLVED`, cuando el cliente autor agrega un comentario
público y un agente la devuelve a `IN_PROGRESS`, entonces ambas acciones se
aceptan y el historial refleja el comentario y las dos transiciones de estado.

**CA-14 — Cierre por el cliente**
Dada una solicitud propia en `RESOLVED`, cuando el cliente autor la cierra,
entonces se devuelve `200`, la solicitud queda `CLOSED` con fecha de cierre, y el
evento de historial registra al cliente como actor.

**CA-15 — Cierre prematuro por el cliente**
Dada una solicitud propia en `IN_PROGRESS`, cuando el cliente intenta cerrarla,
entonces se rechaza y la solicitud conserva su estado. Sobre una solicitud ajena
en `RESOLVED`, el intento devuelve `404`.

**CA-16 — Cierre por el agente**
Dada una solicitud en `PENDING_CUSTOMER`, cuando un agente la cierra indicando el
motivo, entonces se devuelve `200`, queda `CLOSED` y la nota aparece en el
historial. Si el agente omite el motivo, se devuelve `400`.

---

## 7. Fuera de alcance

Se excluyen explícitamente, y así se documenta en el README:

- Interfaz de usuario (la API se explora vía Swagger y Django admin).
- Notificaciones por correo o push.
- SLA, tiempos de respuesta y escalamiento automático.
- **Cierre automático por inactividad.** La inactividad es un criterio operativo
  del equipo, no una regla que codifique el sistema: el agente cierra a mano y el
  filtro por fecha del listado le permite encontrar los casos antiguos. La
  evolución natural sería una tarea programada que cierre lo que lleva N días en
  `RESOLVED` o `PENDING_CUSTOMER` sin actividad.
- **Derivación entre solicitudes.** Cuando un reclamo excede el alcance del caso
  original, el agente responde por comentario y pide abrir una solicitud nueva.
  Es procedimiento del equipo; no se modela un vínculo entre solicitudes.
- Archivos adjuntos. La evidencia de la resolución se registra como nota del
  cambio de estado, que queda en el historial.
- Multi-tenant / organizaciones.
- Búsqueda avanzada o full-text más allá de un filtro simple.

## 8. Preguntas abiertas

1. ¿El cliente se autoregistra o los usuarios los crea un administrador?
   → **Asumido:** los crea un administrador; se entrega un comando de datos de prueba.
2. ¿Un agente puede autoasignarse?
   → **Asumido:** sí, es el caso normal.
3. ¿Quién da por terminada una solicitud?
   → **Resuelto:** el agente declara la resolución; el cierre lo hace el cliente
   sobre una solicitud ya resuelta, o el agente en cualquier momento. Ver RN-14 y
   RN-15.
4. ¿Se puede reabrir una solicitud cerrada?
   → **Asumido:** no. `RESOLVED` se reabre; `CLOSED` no. Un cierre equivocado por
   parte del cliente es irreversible: limitación conocida, declarada en el README.

Los supuestos van declarados en el README como parte de la entrega.
