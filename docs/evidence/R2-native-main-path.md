# R2 — Camino principal nativo con Nilo (2026-11-03, Claude)

Contrato aprobado por el usuario (Nilo; suelo de RAM 0,5 GiB). La política es la de [R1](R1-openkore-auto.md), ahora por personaje.

## Qué cambió

| Cambio | Commit |
| --- | --- |
| `run_r1.py --character tarin\|nilo`: Nilo con `runtime/r1-nilo/`, puerto 8773, registro y política propios (`config/r1-policy-nilo.json`, hechos leídos de la BD en solo lectura) | `decd764` |
| `scripts/freeze_p5.py`: c_177 conciliado con su resultado ya registrado (`failed/died`), **sin reenviarlo**; `events.jsonl` intacto; checkpoint y registro caducado archivados en `runtime/p5/evidence/frozen/`; `FROZEN.json` hace que `run_p5_background.py` se niegue a lanzar | `6603b7e` |
| Elección de campo por el planner, mapas peligrosos (`danger.json`, 3 niveles), huida más barata, `r1_flee` y `campaign` | `3375c80` |
| Ida al Job Changer con la ruta nativa (`lockMap prontera 153 190`); `first-job` ya no usa el viaje propio entre mapas | `8fd7367` |
| Congelado lo que R1 sustituye; `ARCHITECTURE` describe el camino principal R2 | `b777aa7` |
| Hechos de la clase sacados del resultado confirmado; solo cuentan los warps que carga el servidor | `4b1efbc` |

**Campo:**
- `field_options` ofrece campos a ≤ 3 saltos de Prontera por warps que el servidor pre-Renewal carga. Excluye los campos hostiles, los peligrosos y los que tienen agresivos no viables, y deja las 5 mejores opciones más la actual.
- El planner (Groq con respaldo Gemma) elige al empezar, al subir de nivel, al morir y al cambiar de clase. Si falla o llega tarde, se queda el campo actual o el mejor por puntuación.
- Cada decisión se aplica en el único punto de recarga y queda en `field-decisions.jsonl`.

**Huida:**
- `teleportAuto_hp` 25; manada de 5 dentro del campo validado (`teleportAuto_minAggressivesInLock`) y de 3 fuera.
- En `swordman-1` de Tarin, los 6 teletransportes se dispararon con HP del 37–66 %, es decir, por 3 agresivos débiles.
- Sin Fly Wing, `r1_flee` toma la ruta nativa hacia la ciudad con `attackOnRoute 0`.

**Rutas:**
- `routeweights` se recarga con `r1_reload`, porque `CalcMapRoute` lo lee en cada ruta. Un mapa peligroso se evita sin reiniciar el cliente.
- 79 mapas a los que solo llegan enlaces de Renewal (por ejemplo `s_atelier`) llevan peso 10 000.

Suite: 288 OK.

## En vivo

Antes de cada tanda: servicios activos, puertos 8770–8773 libres, RAM libre ≥ 9,5 GiB y GPU ≤ 4,1 GiB. Se avisó al usuario de cada prueba (Visitor, `@jumpto Nilo`).

| Tanda | Duración | Salida | Kills (/h) | EXP base/h | Muertes | Teletransportes | Fly Wing | Zeny |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `smoke-1` | 602 s | `time_budget` | 39 (233) | 896 | 0 | 0 | 9 → 9 | 1 161 → 3 429 |
| `long-1` (Novice) | 5 456 s | `job10_ready` y después fallo del supervisor | 390 (257) | 1 008 | 0 | 2 | 9 → 8 | 3 429 → 5 495 |
| `long-2` (Swordman) | 893 s | **parada por el usuario** | 57 (230) | 669 | 0 | 0 | 8 → 8 | 5 495 → 5 495 |

En todas: 0 intervenciones dentro de la tanda, 0 diálogos NPC fuera del abastecimiento, 0 eventos inesperados, 0 desconexiones. CPU 6–9 % de un núcleo y unos 99 MiB.

**Reaparición:** Nilo estaba muerto en `prt_fild04` desde P5. Al conectar entró vivo en su punto de guardado, `izlude` (el servidor lo había guardado ahí al desconectarse muerto). Desde allí `lockMap` lo llevó por portales a `prt_fild08`, Prontera y `prt_fild06`, y a los 117 s estaba cazando. No hubo ninguna muerte nueva en R1, así que la reaparición en vivo (`dcOnDeath 0`) y el registro en `danger.json` solo están probados con pruebas.

**Planner (`long-1`):**
- 4 decisiones por subida de nivel, todas de Groq y todas con recarga confirmada: `prt_fild06` → 08 → 05 → 01 → 06.
- Al cambiar de clase eligió `prt_fild00`.
- El temperamento `explorer` explica que prefiera campos nuevos.

**Job 10 → Swordman (aceptación de P5):**
1. En Job 10 con 0 puntos de habilidad, `watch` recargó el perfil hacia el Job Changer, y OpenKore llegó solo a Prontera (153,191).
2. `first-job` (puente, `--ai=manual`): `c_1 navigate` → `completed/arrived`; `c_2 first_job` → `completed/job_changed`, con «First Job Changer», `Swordman, Confirm` y `observed_job 1`. Zeny e inventario idénticos.
3. En la BD: clase 1, Base 13 / Job 1.

Nilo se creó en el tutorial, salió por NPC, entrenó y es Swordman, sin premios, recolocaciones ni `@` comandos.

## Fallos encontrados en vivo

- **Supervisor:** tras el cambio de clase, `campaign` leyó una muestra del observador anterior al paquete de clase. Vio «Novice» y terminó (`new_class_not_observed`). Ahora los hechos salen del resultado confirmado, con la orden `class-refit` (`4b1efbc`).
- **Portales de Renewal:** el planner llegó a recibir `ra_fild11` como opción, por `prontera → s_atelier → rachel`, un enlace que solo existe en `npc/re`. Corregido con los warps de rAthena (`4b1efbc`) antes de lanzar `long-2`.

## Aceptación

| Criterio | Estado |
| --- | --- |
| A1 perfil propio; Tarin sin cambios | ✔ |
| A2 c_177 conciliado sin reenviar; P5 congelado | ✔ |
| A3 reaparición y vuelta al campo | ✔ al conectar (muerte de P5); sin muerte nueva en R1 |
| A4 el planner elige campo al subir de nivel | ✔ 5 decisiones y 5 recargas confirmadas |
| A5 huida más barata | ✔ 2 teletransportes en 1,5 h (Tarin: 6 en 15 min); `r1_flee` solo en pruebas |
| A6 muerte → mapa peligroso | ✔ en pruebas; `prt_fild04` sembrado con la muerte de P5 |
| A7 Job 10 → Swordman | ✔ |
| A8 MTBI ≥ 4 h en una tanda | ✘ **no demostrado**: la más larga duró 1,5 h y la cortó un fallo del supervisor; `long-2` la paró el usuario a los 15 min |
| A9 retirada documentada | ✔ |

En total, Nilo jugó unas 1,9 h en R1 sin ninguna intervención en el juego.

Evidencia local, fuera de Git: `runtime/r1-nilo/evidence/{smoke-1,long-1,long-2}` y `runtime/p5/evidence/frozen/`.
