# P2a — viaje por portales caminables y diálogo NPC acotado

Fecha: 2026-10-31, Claude. Rama `codex/single-agent-plan` (`069626e`, `f4363f3`).
Alcance: primera entrega P2 del [plan](../NATIVE_AGENT_PLAN.md), con el contrato
aprobado por el usuario. No incluye Kafra ni transporte de pago, compra/venta,
respuestas de texto/número a NPC ni el ciclo de progreso completo de P2.

## Qué se implementó

- `bridge/lib/M1Travel.pm` (contrato puro, sin red ni globals):
  - `walk_graph` toma de la tabla de portales de OpenKore (`%portals_lut`) solo
    portales sin coste, sin pasos de diálogo, habilitados, sin grupo dinámico y
    entre mapas distintos. Kafra, warps NPC (incluso gratuitos), aeronaves y
    objetos de teletransporte quedan fuera.
  - `plan`: menos saltos (máx. 3; empate por nombre de mapa) y, en cada mapa, el
    portal más cercano a donde está o aparecerá el personaje; último tramo al destino.
  - `approach_cell`: la celda del portal suele ser no transitable en el GAT
    (`prt_fild08 170,378`), aunque el área del warp de rAthena la rodea; se camina
    a la celda transitable más cercana (≤2).
  - `leg_step`: un salto solo cuenta con el cambio de mapa observado; mapa fuera
    del plan → `unknown/unexpected_map`; junto al portal sin salto durante 5 s →
    `failed/portal_not_taken`; errores de ruta → `timeout|unreachable|blocked`.
  - `validate_talk`, `dialog_step`, `talk_outcome` para el diálogo.
- Puente (`m1_bridge.pl`), solo perfil nativo (`--ai=manual`):
  - `travel {map, x, y, timeout_s}`: rechaza `same_map_use_navigate`,
    `no_walk_route`, etc. antes de moverse. Acepta con el plan como evidencia
    (`accepted/walk_route_planned`). Cada tramo es un `Task::Route` del mismo mapa
    (`noMapRoute`); nunca encola `Task::MapRoute`. Eventos `travel_hop` y
    `travel_progress` (1 Hz). Final con tramos, saltos, `zeny_delta` y
    `map_route_seen`. Todo final distinto de la llegada detiene al personaje.
  - `npc_talk {x, y, choices, timeout_s}`: NPC visible en (x,y) a ≤5 celdas; no
    se mueve. Solo envía continuar (máx. 12 páginas), etiquetas de menú exactas
    declaradas antes (máx. 4) y cierre. Menú no previsto, número/texto o tienda →
    cancela la conversación con `failed/...`. `completed/conversation_closed` solo
    si Zeny, inventario y mapa no cambian; si cambian → `unknown/state_changed`.
    Transcripción ≤40 líneas, menús vistos y opciones elegidas.
  - Un solo ejecutor del diálogo: OpenKore crea su propia tarea `autotalk` cuando
    el NPC responde (con `autoTalkCont 1` pasaría páginas por su cuenta). Mientras
    hay un `npc_talk` del puente, esa tarea se elimina antes de iterar
    (`autotalk_suppressed` en la evidencia).
  - `cancel` y la retirada por HP bajo también terminan `travel`/`npc_talk`.
  - El snapshot añade `npcs` (≤16) y `ai_queue` (≤8).
- `scripts/p2_trip.py`: pasos fijos `travel:MAPA:X:Y` y `talk:X:Y[:Etiqueta|...]`,
  sin inferencia, nunca reenvía; se detiene en el primer fallo (un rechazo se
  registra y sigue). Evidencia en `runtime/p1/evidence/trip-*.json`.

## Comprobaciones ejecutadas

- `perl -c bridge/openkore/m1_bridge.pl`: OK.
- `python -m unittest discover -s tests`: 68 tests OK (61 previos + 7 de contrato
  en `tests/test_p2_travel.py` con el módulo Perl real: plan solo con portales
  caminables, límite de saltos, Kafra/NPC/dinámicos excluidos, celda de acceso,
  pasos de tramo, admisión y pasos de diálogo, cambios de estado no ocultados).
- Celdas comprobadas con `Field` de OpenKore: `prontera 157,31`, `prontera 156,22`
  y `prt_fild08 170,365` transitables; `prt_fild08 170,378` no.
- En vivo, con los 3 clientes M4-field activos en 8765–8767 sin tocarlos; sin
  reiniciar servidor ni base. Comando:
  `p2_trip.py --timeout 150 travel:prontera:157:31 talk:160:29:Cancel travel:prt_fild08:170:365 travel:geffen:120:100`

Ejecución final (`trip-1793459374.json`, tras las dos correcciones):

| Paso | Resultado | Evidencia confirmada |
|---|---|---|
| `prt_fild08` 170,365 → `prontera` 157,31 | `completed/arrived` en 4,4 s | salto a `prontera` (156,26) a 2,6 s; `pos_to` 157,31; Zeny Δ 0 |
| `npc_talk` South Gate-Guide (160,29), `["Cancel"]` | `completed/conversation_closed` en 2,1 s | 1 página, menú `City Guide./Remove Marks…/Notice/Cancel`, elegido `Cancel`, 10 líneas, sin cambios; autotalk suprimido 11 veces, sin tarea NPC restante |
| `prontera` → `prt_fild08` 170,365 | `completed/arrived` en 3,6 s | salto a `prt_fild08` (170,375) a 1,2 s; `pos_to` 170,365; Zeny Δ 0 |
| `travel` a `geffen` | `rejected/no_walk_route` | sin movimiento |

Colas de IA observadas en snapshots: solo `route` (nunca `mapRoute` ni `NPC`).
La Kafra de Prontera (151,29) estaba visible y no se usó. Zeny 0 al inicio y al
final. Inferencia: ninguna llamada. Cliente P1 detenido con `prepare_p1.py stop`.

La primera ejecución completa (`trip-1793459303.json`, desde 149,231: ida en
27,6 s) dio los mismos cuatro resultados, pero el log mostró la tarea `autotalk`
de OpenKore activa durante el diálogo; por eso se repitió tras corregirlo.

## Fallos encontrados y corregidos

1. `travel_evidence` terminaba en `{%{...}, ...}`, que Perl interpretó como bloque:
   devolvió `0` y abortó el cliente en el primer `travel_progress`. Ahora usa
   `return {...}` (igual en `talk_snapshot`).
2. Segundo ejecutor en diálogos: la tarea `autotalk` de OpenKore. Ahora se elimina
   mientras el puente conduce el diálogo.

## Límites

- `portal_not_taken`, `unexpected_map`, `unexpected_menu`, `input_not_allowed`,
  `shop_not_allowed` y `state_changed` solo se cubren con estados simulados.
- Un cambio de mapa que cambie de map-server pasaría por desconexión y se
  reportaría `unknown/game_disconnected`; aquí todos los mapas comparten servidor.
- El plan confía en `portals.txt` de OpenKore; un portal con requisitos de quest
  aparecería como `portal_not_taken`, no se predice.
- Fuera de `npc_talk`, un NPC que inicie diálogo solo sigue con el comportamiento
  normal de OpenKore.
- `position` del snapshot es el inicio del último tramo (1 Hz); la evidencia usa
  `pos_to` confirmado y la posición prevista.
