# P1a — navegación nativa de un personaje normal

Fecha: 2026-10-31, Claude. Rama `codex/single-agent-plan`. Alcance: primera
entrega P1 del [plan](../NATIVE_AGENT_PLAN.md). No incluye combate, loot,
recuperación ni rutas entre mapas.

## Qué se implementó

- Perfil separado `runtime/p1/openkore/solo` (`scripts/prepare_p1.py`): cuenta
  nueva 2000030, personaje Tarin, novato nivel 1 con el inicio pre-Renewal de
  rAthena (`new_1-1` 53,111; Knife y Cotton Shirt equipados; 0 Zeny). Solo
  `INSERT`; no cambia otros personajes. Registro de procesos propio
  `runtime/p1/processes.json`, puerto de puente 8770.
- OpenKore arranca con `--ai=manual`: ejecuta tareas de ruta sin IA automática
  (sin atacar, deambular ni recoger). El puente aborta si el perfil nativo no
  está en modo manual.
- `navigate {map, x, y, timeout_s}`: valida con `bridge/lib/M1Navigation.pm` y
  encola `Task::Route` de OpenKore (mismo mapa, `noMapRoute`, sin ataque en ruta).
  Aceptar (`accepted/route_queued`) no es llegada. Publica `navigation_progress`
  a 1 Hz y un resultado final:
  - `completed/arrived` solo si el `pos_to` confirmado por el servidor es el
    destino y la posición prevista está a ≤1 celda;
  - `failed/timeout|unreachable|blocked` según el error de la tarea;
  - `cancelled/cancel_requested` mediante `cancel {target}`;
  - `unknown/...` ante desconexión, cambio de mapa, tarea perdida o fin fuera de destino.
  Todo final distinto de la llegada detiene al personaje en la celda prevista.
- Un solo dueño: en el perfil nativo, `move` paso a paso se rechaza siempre
  (`legacy_executor_disabled`); durante una ruta todo salvo `cancel` es `busy`.
  `attack/take/trade` siguen limitados al fixture M4. Los perfiles M1/M4 no cambian.
- `scripts/p1_nav.py`: runner que termina solo, sin inferencia, nunca reenvía
  y guarda un resumen acotado en `runtime/p1/evidence/`.

## Comprobaciones ejecutadas

- `perl -c bridge/openkore/m1_bridge.pl`: OK.
- `python -m unittest discover -s tests`: 57 tests OK (55 previos + 2 de
  contrato en `tests/test_p1_navigation.py`, con el módulo Perl real).
- En vivo, con los 3 clientes M4-field activos en 8765–8767 sin tocarlos:

| Caso | Resultado observado |
|---|---|
| destino no transitable (70,107) | `rejected/not_walkable` |
| 53,111 → 95,111 (42 celdas) | `completed/arrived` en 6,5 s; 7 progresos |
| 95,111 → 45,100, cancelar a 2 s | `cancelled` a 2,1 s; snapshot posterior quieto en 81–82 |
| `move` / 2º `navigate` durante ruta | `rejected/busy` |
| `cancel` a otra solicitud | `rejected/no_matching_navigation` (desde P1b: `no_matching_task`) |
| `navigate` a `prontera` | `rejected/cross_map_not_supported` |
| `move` en reposo | `rejected/legacy_executor_disabled` |
| ruta de ~6,7 s con `timeout_s` 5 | `failed/timeout` a 5,1 s; quieto en 68–69 |

Inferencia: ninguna llamada (el runner no importa ningún cliente de modelo).

## Fallos encontrados y corregidos

1. `Task::getError` exige estado DONE; llamarlo en cada tick abortó el cliente
   P1 en la primera ruta. Ahora solo se lee al terminar la tarea.
2. Tras `failed/timeout` el personaje seguía hasta el último paso enviado
   (91 → 101). Ahora todo final que no sea llegada lo detiene.

## Límites

- Desconexión: `unknown/game_disconnected` y limpieza de la ruta están en el
  código, pero no se probaron en vivo (requeriría cortar el servidor compartido).
- `blocked` y `unreachable` se cubren solo con estados simulados.
- El `position` del snapshot es el inicio del último tramo (`$char->{pos}`);
  la evidencia de navegación usa la posición prevista y `pos_to`.
- Rutas entre mapas aplazadas: el enrutador multi-mapa puede usar transporte
  NPC de pago y necesita su propia validación.
