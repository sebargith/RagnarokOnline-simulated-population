# R1 — OpenKore en modo `auto` con configuración generada (2026-11-03, Claude)

Prueba acotada de la recomendación R1 de la [revisión](../research/PROJECT_REVIEW-2026-11.md):
Python y la política deciden **qué** hacer y lo traducen a configuración; OpenKore
en `--ai=auto` decide **cómo**. Personaje: Tarin (cuenta 2000030), en un perfil nuevo
(`runtime/r1/`). No se tocaron Nilo (su cliente 46148 siguió vivo), el perfil P1,
la base de datos, rAthena, la configuración global de OpenKore ni el camino de P5.

## Qué se construyó

- **Política como datos** (`config/r1-policy.json`): 18 reglas `on` / `requires` / `do`, con la idea del lenguaje de estrategias de ragnarokoffline.app (anexo §7.2; sin copiar código).
- **Traductor determinista** (`scripts/build_r1_profile.py`): convierte las reglas en `config.txt`, `mon_control.txt`, `items_control.txt` y `routeweights.txt` a partir de la build, `p5-monsters.json`, `p5-fields.json`, `mob_skill_db` (invocadores) y las tiendas de rAthena. Las reglas sin equivalente nativo pasan al informe como huecos.
  - **Campo:** `lockMap prt_fild06`, `attackAuto 2`, `route_randomWalk 1`.
  - **`mon_control` por ID:** 6 monstruos se atacan siempre (viables y con EXP), 84 solo si atacan primero, 90 agresivos no viables con teletransporte si atacan (necesita Fly Wing) y 34 jefes o invocadores con teletransporte a 10 casillas.
  - **Rutas:** `route_maxWarpFee 0`; peso 10000 para NPC, `@go` y aeronave, y para 55 mapas con jefes, invocadores o amenazas raras (incluido `prt_fild04`, el del Vocal).
  - **Mantenimiento:** descanso al 45 % → 90 %, Apple/Red Herb por debajo del 35 %, venta al 40 % de peso en el Fruit Gardener y compra de Apple (desde 150 Zeny) y de Fly Wing (desde 300 Zeny, Tool Dealer de `prt_in`).
  - **Build:** `statsAddAuto_list` y `skillsAddAuto_list` (`raiseStat`/`raiseSkill`).
  - **Huida y muerte:** `teleportAuto_hp 30`, `teleportAuto_minAggressives 3`, `dcOnDeath 0`.
- **Observador de solo lectura** (`bridge/r1/r1_observer.pl`): escribe eventos y una muestra cada 5 s en `runtime/r1/observer/events.jsonl`. No envía paquetes ni comandos, y el perfil solo carga `r1_observer`, `raiseStat` y `raiseSkill` (nunca `m1_bridge`).
- **Lanzador y supervisor** (`scripts/run_r1.py`):
  - órdenes `preflight`, `prepare`, `start`, `watch`, `stop` y `report`;
  - paradas automáticas por RAM < 2 GiB, GPU ≥ 14 336 MiB, 3 muertes en 15 min, o Zeny o diálogo NPC fuera del abastecimiento;
  - la contraseña existente de Tarin se lee de `runtime/p1/secrets.json` sin mostrarla.
- **Pruebas:**
  - `tests/test_r1_profile.py`: cada regla produce sus claves y cada clave existe en el OpenKore fijado;
  - `tests/test_r1_runner.py`: métricas con eventos grabados y contrato del observador;
  - suite completa: 271 OK, antes de las dos correcciones de política, que tienen sus propias pruebas.

## Verificaciones que la revisión dejó abiertas

**`portalsLOS.txt`** (`scripts/check_portals_los.py`, sin conexión):
- coincide con `config/walk-zones.json` en 45 012 de 45 029 pares de portales del mismo mapa (99,96 %);
- en `prt_castle`, la entrada (102,16) solo llega a (82,29), (102,73) y (121,29), y **no** a la salida hacia `prt_gld` (102,181): es justo la trampa de c_384;
- las 17 diferencias (`moc_fild02`, `mjolnir_04`, `anthell02`, `dewata`) son todas casos en que OpenKore es más prudente y marca el par como inalcanzable.

**Warps de pago o con diálogo:**
- **En código:** con `route_maxWarpFee 0` el presupuesto de `CalcMapRoute` es 0 y se descarta todo enlace con coste (`CalcMapRoute.pm:98-105,609`). `tables/portals_commands.txt` está vacío, así que la ruta no puede usar `@go`.
- **Warps NPC gratuitos:** cerca de la zona de prueba solo existen `prt_fild05`→`prt_sewb1`, `prontera`→`bat_room` e `izlude`→`moc_para01`, todos con peso 10000.
- **En vivo (fase de abastecimiento):** la ruta `prt_fild06` → Prontera (104,49) → `prt_in` (126,76) → Prontera → `prt_fild06` se hizo entera por portales. Hubo **0 diálogos NPC** y el Zeny solo cambió durante `sellAuto`/`buyAuto`.
- **Límite:** con 31 Zeny al empezar, ningún warp de pago era asequible, así que el vivo no distingue el efecto de `route_maxWarpFee`. Esa parte queda verificada en el código, no en el juego.

## Ejecuciones en vivo

**Preflight:** servicios del juego activos, P1 parado, 8772 libre, RAM libre ≥ 9,9 GiB y GPU 1 661–1 967 MiB. El usuario podía mirar con Visitor (`@hide`, `@jumpto Tarin`).

| Ejecución | Duración | Resultado |
| --- | --- | --- |
| `smoke-1` | ~2 min | Login y caza correctos. Dos fallos de política, corregidos en `5324f56` antes de medir: golpeaba Green Plant (0 EXP, 1 de daño por golpe), y los nombres de objetos llegan en coreano (tablas kRO), así que la curación pasó a usar IDs. |
| `hour-1` (medida) | 3 601 s, salida `time_budget` | Ver tabla siguiente. |
| `supply-check-1` | 80 s | Pausada por el usuario. |
| `supply-check-2` | 908 s, salida `time_budget` | Misma política, con venta al 15 % de peso para forzar el viaje. Login tardío (ver límites). En 328 s de juego: vendió, compró 3 Fly Wing (Zeny 31 → 1 350) y volvió a cazar (26 kills). Reparto del tiempo: caza 176 s, descanso 65, viaje 35, abastecimiento 51. |

**Hora medida (`hour-1`):**

| Métrica | R1 (Tarin, Base 5→11) | P5 actual (Nilo, `--ai=manual`) |
| --- | --- | --- |
| Intervenciones manuales | **0** | Un bloqueo cada ~15 min; tandas de 870 s relanzadas a mano |
| Muertes | 0 (no se pudo observar la reaparición) | 1 (Vocal); bloqueado sin reaparecer |
| Kills/h | **316** (157 Poring, 137 Lunatic, 22 Thief Bug Egg) | 87 (`field-by-level-1`: 21 en 870 s); 50 (`walk-reachability` intento 4: 12 en 870 s) |
| EXP base/h | **1 312** (Base 5→11, Job 4→8) | ~323 (Base 7→8 en 870 s) |
| Caza / descanso / viaje / abastecimiento | 2 603 / 998 / 0 / 0 s | 4 ventas en 14,5 min, de 50–75 s por trayecto (hasta 220 s desde `prt_fild00`) |
| Zeny e inventario | Zeny 31 → 31; botín acumulado al 19 % de peso; 0 eventos inesperados | — |
| Build | STR 11→19 (8 subidas de `raiseStat`); NV_BASIC 2→7 (`raiseSkill`, leído en la BD) | RPC `stat_up`/`skill_up` confirmadas una a una |
| Recursos | CPU 5,9 % de un núcleo; 95 MiB; RAM libre mínima 6,7 GiB; GPU sin cambios por el cliente (1 723–3 881 MiB, de otros programas) | — |

Hubo dos intentos de teletransporte por HP bajo sin tener alas («You don't have the Teleport skill or a Fly Wing»). Sobrevivió las dos veces. El HP mínimo observado fue del 35 %.

La comparación es orientativa: distinto personaje y nivel, y EXP por kill distinta. La diferencia de kills/h (×3,6–6) y la ausencia de bloqueos superan con creces ese sesgo.

**Evidencia local, fuera de Git:** `runtime/r1/evidence/{smoke-1,hour-1,supply-check-1,supply-check-2}`. En `hour-1/` están los ficheros generados, con la contraseña ocultada.

## Huecos y límites

- **Huecos que la política declaró y OpenKore no cubre:**
  - huir sin alas (`leave_pack_no_wings`): no hay huida para cuerpo a cuerpo, y `routeWeights` solo se carga al iniciar;
  - recalcular al subir de nivel (`refit_on_level`): la viabilidad de `mon_control` se calculó en Base 5. Tarin llegó a Base 11 sin que se recalculara, y el campo y los objetivos siguen siendo los de entonces.
- **Muerte y reaparición** (`dcOnDeath 0`, vuelta por `lockMap`): no se observaron porque no hubo muertes. Solo están verificadas en el código (`CoreLogic.pm:1200`).
- **Escritura en tablas fijadas (corregido):** en vivo, OpenKore grabó portales (`portalRecord 2`, valor por defecto) y precios de tienda en `vendor/openkore/tables/portals.txt` y `npc_shops.txt`, y 3 pruebas de regeneración de P5 fallaron por eso. Se guardó el diff en `runtime/r1/evidence/vendor-tables-written-by-r1.patch` y se restauraron los dos archivos con `git checkout`. Ahora el perfil lleva `portalRecord 0` y copias propias de esas dos tablas, y la suite vuelve a dar 271 OK. El perfil P5 hereda `portalRecord 2` de la plantilla común, así que puede tener el mismo riesgo; no se ha comprobado.
- **Login tardío en `supply-check-2`:** 34 «Timeout on Character Server» seguidos, unos 9,5 min, tras la pausa. OpenKore reconectó solo. No se determinó la causa: el char-server solo registró el intento que entró.
- **Descanso:** ocupa el 28 % de la hora (45 % → 90 %). Es un umbral prudente, que se puede ajustar en la política.
- **Venta al 40 %:** hace pocos viajes, pero en 1 h no llegó a vender, y sin Zeny no hay alas. Se propone un 25–30 %.
- **Nombres de monstruos:** `tables/monsters.txt` del entorno nombra «M4 Poring» al 1002. `mon_control` usa IDs y no le afecta.
- **Muestra pequeña:** una hora con un solo personaje y un campo de nivel bajo. No acredita el MTBI ≥ 4 h de R2 ni campos con más peligro.

## Conclusión: **adoptar con cambios**

OpenKore en `auto` con la configuración generada entrenó 1 h sin intervención, sin muertes y sin warps de pago ni diálogos, rindió 3,6–6 veces más kills/h que el ciclo actual y resolvió viaje, venta y compra por sí solo. Los cambios necesarios son de política y sincronización, no de un ejecutor propio:

1. **Recalcular al subir de nivel:** el planner regenera el perfil con nuevos hechos y aplica `reload` (o reinicia el cliente) en un único punto sincronizado.
2. **Umbral de venta del 25–30 %,** y comprar Fly Wing en cuanto haya Zeny, para que la huida reactiva funcione.
3. **Comprobar una muerte real:** reaparición y vuelta al campo, y registrar el mapa como peligroso.
4. **Tanda larga** (≥ 4 h, MTBI de R2) antes de llevar a Nilo a este ejecutor.

**Partes del ejecutor propio que se podrían retirar del camino principal** si los puntos 1 y 3 salen bien:
- `M1Travel` (rutas propias), `agent/walk.py`, `config/walk-zones.json` y `scripts/build_walk_zones.py` como ruta (se pueden conservar como comprobación cruzada de `portalsLOS`);
- la exploración (`M1Explore` y la exploración de `solo_cycle`) y la elección de objetivos en Python;
- las fases `to_shop`/`sell`/`buy`/`return` (`p2_supply.decide`, `M1Supply`);
- `recovery_tick` y `M1Healing`;
- las RPC `stat_up`/`skill_up` de la build;
- el parámetro `avoid` propuesto.

**El puente se conserva** para el tutorial, el Job Changer, el comercio y las compraventas que haya que conciliar.

## Adopción (2026-11-03, aprobada por el usuario)

**Cambios hechos sobre el perfil R1** (`861c8db`, `f13dbda`). El camino de P5 y Nilo siguen sin cambios.

- **Recálculo al subir de nivel:**
  - el supervisor regenera los archivos del perfil con los hechos observados (nivel, stats, HP máximo y equipo puesto);
  - `bridge/r1/r1_reload.pl` los aplica con la recarga nativa (`Misc::parseReload`) y lo confirma con un evento `reloaded`;
  - si la recarga falla o no se confirma en 60 s, la tanda se para. El hueco `refit_on_level` queda cerrado.
- **Venta** al 30 % de peso.
- **Parada en Job 10:** `watch` se detiene con `job10_ready` cuando el Novice tiene Job 10 y 0 puntos de habilidad, que es la regla del Job Changer propio. El cambio de clase sigue por el puente conciliado y aún no está conectado a R1.
- **Suite:** 275 OK en 3 de 4 ejecuciones. Hubo 1 error único que no se repitió ni se pudo capturar, con la RAM del equipo baja en ese momento.

**Tanda larga `long-1`** (`runtime/r1/evidence/long-1/`), con objetivo de 4 h y parada en Job 10:

| Métrica | Resultado |
| --- | --- |
| Salida | `ram_guard` a los 782 s: RAM libre mínima de 1,7 GiB por otros programas del usuario; el cliente usaba 94 MiB |
| Intervenciones / muertes | 0 / 0 |
| Kills/h / EXP base/h / EXP job/h | 387 / 1 758 / 805 (84 kills; Base 11→12, Job 8 a 256/268) |
| Recálculos en vivo | 2 confirmados (Base 11 y Base 12). Pasó de 6 a 12 objetivos viables en el OpenKore fijado (Pupa entra en `prt_fild06`) |
| Build | STR 19→20 y después VIT 5→6, en el orden de la build |
| Zeny / eventos inesperados / diálogos NPC | 1 350 sin cambios / 0 / 0 |
| CPU | 6,7 % de un núcleo |

**Sigue pendiente:**
- MTBI ≥ 4 h: no demostrado, porque la tanda la cortó la RAM del equipo y no el bot;
- llegar a Job 10 y el paso al Job Changer: parar el modo `auto`, ejecutar `first_job` con el puente y regenerar la política para Swordman;
- observar una muerte real.

Relanzar solo con RAM libre ≥ 2 GiB.

**Tanda `long-2`** (`runtime/r1/evidence/long-2/`). A petición del usuario, el suelo de RAM se bajó a 0,5 GiB (`--ram-min-gib`, `f5273db`); la RAM libre mínima fue de 4,14 GiB.

| Métrica | Resultado |
| --- | --- |
| Salida | `job10_ready` a los 1 720 s, sola |
| Intervenciones / muertes / desconexiones | 0 / 0 / 0 |
| Kills/h / EXP base/h / EXP job/h | 350 / 1 498 / 728 (167 kills; Base 12→14, Job 8→10) |
| Recálculos en vivo | 2 confirmados (Base 12 y 13); 12 objetivos viables |
| Build | VIT 6→11; NV_BASIC 9 y 0 puntos de habilidad (leído en la BD) |
| Zeny / eventos inesperados / diálogos NPC | 1 350 sin cambios / 0 / 0 |
| Reparto del tiempo | caza 1 655 s, descanso 65 s |
| CPU / RAM del cliente | 8,0 % de un núcleo / 95 MiB |

**Estado al terminar:** Tarin es Novice Base 14 / Job 10 en `prt_fild06`, sin puntos de habilidad. Cumple las condiciones del Job Changer, y el cliente R1 está detenido.

En total, R1 ha sumado unas 1,7 h de juego sin ninguna intervención (1 h + 13 min + 29 min), en tres tandas que terminaron por presupuesto de tiempo, RAM del equipo y Job 10. El MTBI ≥ 4 h en una sola tanda sigue sin demostrarse.

**Siguiente:** el paso al Job Changer. El modo `auto` está detenido; falta ejecutar `first_job` con el puente conciliado, en el perfil manual de Tarin, eligiendo Swordman. Después, regenerar la política para Swordman y volver al modo `auto`.

## Cambio de clase a Swordman (2026-11-03, aprobado por el usuario)

**Ejecución:** `scripts/run_r1.py first-job --job Swordman`. Arranca el perfil R1 de Tarin en `--ai=manual` con `m1_bridge` (puerto 8772 y token propio, sin tocar P1), lo lleva junto al NPC y envía **una** petición `first_job`. Solo se da por cambiada la clase con el paquete del servidor, nunca reenviando la petición.

- **Intento 1** (`first-job-1`): el puente no abrió el puerto, porque su lista de puertos acababa en 8771. Se corrigió en `8dcc497`. No se envió nada.
- **Intento 2** (`first-job-2`): la cola de eventos del cliente se llenó durante el viaje (el script no la vaciaba) y el paso se abortó. Se corrigió en `83e20c9`. El viaje `c_1` llegó a aceptarse, pero no se envió `first_job`.
- **Intento 3** (`first-job-3`):
  - `c_1 navigate` → `completed/arrived` en Prontera (153,190);
  - `c_2 first_job` → `accepted/npc_name_requested` → `accepted/talk_sent` → **`completed/job_changed`**, con «First Job Changer» resuelto por el servidor, la elección `Swordman, Confirm` y `observed_job 1 = expected_job 1`;
  - Zeny e inventario idénticos antes y después;
  - en la BD: clase 1, Base 14 / Job 1, 0 puntos de habilidad.

Es el primer cambio de clase real con un personaje elegible en el proyecto. En P5 solo se había visto la negativa del NPC.

**Vuelta al modo `auto` como Swordman** (`swordman-1`, 904 s, `dc61122`). Los hechos de la política son ahora Swordman Base 14; hay 15 objetivos viables y en `prt_fild06` ya lo son todos.

| Métrica | Resultado |
| --- | --- |
| Salida | `time_budget` |
| Intervenciones / muertes / diálogos NPC / eventos inesperados | 0 / 0 / 0 / 0 |
| Kills/h / EXP base/h / EXP job/h | 203 / 1 771 / 581 (51 kills; Job 1→4) |
| Habilidades | SM_SWORD 0→3 con `raiseSkill` (leído en la BD) |
| Rutas | Prontera → `prt_fild06` al arrancar, y 2 viajes al Tool Dealer (`prt_in`), todos por portales |
| Huida | 6 teletransportes reactivos con Fly Wing por HP bajo o varios agresivos; las alas se repusieron solas (Zeny 1 350 → 990) |
| Reparto del tiempo | caza 342 s, descanso 296, viaje 100, abastecimiento 166 |
| CPU / RAM del cliente | 7,4 % de un núcleo / 99 MiB |

**Ajustes pendientes:**
- `prt_fild06` se queda corto para un Swordman de Base 14: elegir campo es tarea del planner y la política aún lo fija;
- los teletransportes son caros y frecuentes (6 en 15 min, 360 Zeny); hay que revisar `teleportAuto_hp` y `teleportAuto_minAggressives`, o el campo;
- el descanso ocupa el 33 % del tiempo.

Estas tandas de R1 nunca escribieron en las tablas fijadas de OpenKore.
