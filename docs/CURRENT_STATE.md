
# Estado actual

## R2 — camino principal nativo con Nilo (2026-11-03, Claude)

- **Resultado:** Nilo pasa a OpenKore `auto` (`run_r1.py --character nilo`, `runtime/r1-nilo/`, puerto 8773). [Evidencia](evidence/R2-native-main-path.md).
- **P5:** congelado. c_177 se concilió sin reenviarse y `FROZEN.json` impide relanzarlo.
- **P5 aceptado:**
  - Job 10 y después **Swordman** (`first_job` `completed/job_changed`; en la BD, clase 1);
  - la ida al Job Changer fue nativa.
- **En vivo:** 1,9 h en total, con 0 intervenciones y 0 muertes.
  - Planner: 5 decisiones de campo de Groq, todas con recarga confirmada.
  - Huida: 2 teletransportes en 1,5 h.
- **Pendiente:**
  - **MTBI ≥ 4 h, no demostrado.** La tanda más larga duró 1,5 h y la cortó un fallo del supervisor, ya corregido. La siguiente la paró el usuario a los 15 min.
  - Falta ver en vivo una muerte nueva y `r1_flee`.
- **Estado:** cliente detenido. Nilo es Swordman Base 13 / Job 3 en `prt_fild00`, con 5 495 Zeny y 8 Fly Wing. Suite: 288 OK.
- **Siguiente:** `run_r1.py campaign --character nilo --seconds 15300 --ram-min-gib 0.5`.

## R1 — OpenKore `auto` con configuración generada (2026-11-03, Claude)

- **Resultado:** **adoptar con cambios.** [Evidencia](evidence/R1-openkore-auto.md).
- **Prueba:** Tarin en el perfil `runtime/r1/`, con la política declarativa `config/r1-policy.json` traducida por `scripts/build_r1_profile.py`; observador de solo lectura y `scripts/run_r1.py`.
- **En vivo, 1 h:**
  - 0 intervenciones y 0 muertes;
  - 316 kills/h y 1 312 de EXP base/h (Base 5→11); P5 hacía 50–87 kills/h;
  - CPU al 5,9 % y 95 MiB.
- **Abastecimiento en vivo:** venta, compra de 3 Fly Wing y vuelta solo por portales, sin diálogos NPC.
- **`portalsLOS`:** coincide con nuestras zonas en el 99,96 % y acierta en `prt_castle`.
- **Pendiente:**
  - recalcular la política al subir de nivel;
  - umbral de venta del 25–30 %;
  - observar una muerte real;
  - tanda de ≥ 4 h.
- **Corregido:** OpenKore escribía portales y tiendas en `vendor/openkore/tables`; se restauraron y ahora el perfil R1 usa copias propias y `portalRecord 0`. P5 hereda `portalRecord 2`, sin comprobar.
- **Adoptado (usuario):** recálculo al subir de nivel con recarga confirmada (2 en vivo), venta al 30 % y parada en Job 10. La tanda larga se cortó por RAM (1,7 GiB libres) a los 782 s, con 0 intervenciones.
- **Job 10 alcanzado** (`long-2`, 29 min, con suelo de RAM de 0,5 GiB a petición del usuario): 0 intervenciones y 0 muertes; se paró sola por `job10_ready`.
- **Cambio de clase real:** `first_job` dio `completed/job_changed` con el paquete del servidor, y Tarin es **Swordman**. En `auto` (15 min): 0 intervenciones, Job 1→4 y SM_SWORD 3.
- **Estado al terminar:** cliente R1 detenido. Tarin es Swordman Base 14 / Job 4, 990 Zeny, en `prt_in`. Nilo sin tocar. Suite: 275 OK.
- **Siguiente:** elegir el campo con el planner al subir de nivel (`prt_fild06` se queda corto), ajustar la huida (6 alas en 15 min) y hacer una tanda de ≥ 4 h.

## P5.6 — alcanzabilidad a pie y tiempo de viaje (2026-11-02, Claude)

- **Fallo corregido:** la tanda `resume-20261101-unique-1` se bloqueó porque c_384 planeó cruzar `prt_castle` hasta un portal al que no se llega andando desde la entrada.
- **Planificador:** el plan de viaje busca ahora por zonas transitables de cada mapa (`config/walk-zones.json`, generada desde OpenKore fijado) y cuenta las puertas internas del mismo mapa.
- **Sin ruta:** `rejected/no_walk_route` con su motivo.
- **Mismo criterio** para las opciones de campo, el abastecimiento y el tutorial.
- **Puertas internas:** se acepta el aterrizaje real del servidor dentro de la zona planeada (`eda1a07`).
- **Tiempo de viaje:** sale de la ruta, entre 30 y 300 s, en vez de 150 s fijos (`fae125e`).
- **Conciliación:** `reconcile-travel` retira un `travel` fallido, o un warp del mismo mapa, ya observados, sin reenviar nada.
- Suite: 253 OK. [Evidencia y límites](evidence/P5-walk-reachability.md).
- **En vivo (870 s, salida 0):**
  - Nilo salió de `prt_castle` por las dos puertas internas;
  - las revisiones de campo solo ofrecieron destinos alcanzables, y Groq eligió y luego mantuvo prt_fild00;
  - 136 → 148 kills; dos viajes de abastecimiento de ida y vuelta, de unos 220 s, todos `arrived`.
- **Después (`c5b636f`, `569b68f`, `a682e76`):**
  - las opciones de campo pesan lo que dura el abastecimiento (`supply_round_trip_s`, `hunt_share`);
  - un resultado que llega tarde se lee del puente al reanudar, sin reenviarlo. En vivo, c_56 se recuperó como `arrived` y Nilo pasó de 148 a 151 kills.
  - Esa ejecución la paró el guardián de GPU (15218 MiB usados por otros programas).
- **Revisión con el nuevo peso, en vivo:** Groq eligió prt_fild05 (abastecimiento de 88 s por trayecto); de 151 a 158 kills.
- **Estado al terminar:** `blocked` por `exploration_no_reachable_candidate`, sin acción en vuelo, 158 kills, en prt_fild05 (115,373).
  - Nilo entró explorando en una bolsa donde ningún candidato tiene línea recta libre.
  - Cliente 46148 vivo.
- **Pendiente:**
  - **Nilo murió** en prt_fild04: un Vocal y seis Rockers esclavos lo atacaron a la vez. Está blocked `travel:failed/died`, Base 9, 175 kills. Falta reaparecer y excluir los campos con apariciones raras que traen esclavos;
  - la carrera de arranque entre el cliente y el runner;
  - Job10 y el cambio de clase.

## P5.5 — campo por nivel durante el entrenamiento (2026-11-01, Claude)

- `01c4cd5`: `--train-first-job` sin `--no-inference` usa `P5Planning`. El campo se decide otra vez con `level_up`, `field_unsafe` y `periodic_review`; una petición cada vez y la caza sigue mientras tanto. Si el planner falla o vence, se mantiene el campo. Cada decisión guarda `facts`, motivo y `served_by`. `run_p5_background.py` usa el planner por defecto; `--no-inference` mantiene el modo anterior. Suite: 240 OK.
- En vivo, 870 s y 83 acciones, salida 0 por `time_budget`:
  - Groq pasó de prt_fild08 a prt_fild06 (puesta al día de nivel 2 a 7) y, en la subida real a Base 8, de prt_fild06 a prt_fild05;
  - 2 inferencias, 113→134 kills, sin muertes, retiradas ni resultados `unknown`.
  - [Evidencia y límites](evidence/P5-field-by-level.md).
- Estado al terminar: checkpoint `active/hunt`, sin acción en vuelo, Base 8 (57/200) / Job 6, Zeny 950, en prt_fild05 (130,298). El cliente 31704 sigue vivo y ocioso.
- No se ha visto en vivo el respaldo Gemma, un vencimiento, `field_unsafe` ni `periodic_review`. Las ventas frecuentes consumen mucho tiempo.

## Relevo a Claude — entrenamiento activo (2026-11-01)

- Código de referencia `f712bf0`. Lectura 2026-11-01 11:35:05 -03: Base7/Job6, kills107, HP74/78, Zeny416, prt_fild08 {'x': 62, 'y': 343}; fase hunt, cero inferencias.
- Checkpoint activo; acción pendiente en esa muestra: c_268 attack. Estos datos pueden cambiar.
- Wrapper2564, runner69208 y cliente31704 verificados activos a las 11:33:58 -03.
  Límite de la ejecución actual: 3570 s/600 acciones; resumen `runtime/p5/evidence/train-first-job-resume-4-summary.json`.
  Leer también `runtime/p5/cycle/status.json` y `state.json` antes de cualquier operación.
- No interrumpir a Nilo/Visitor ni reenviar peticiones. El usuario observa en juego;
  no mantener un modelo vigilando. Si ya terminó, evaluar resumen/checkpoint primero.
- Cambios publicados: 4b05449 meta persistente/no-inference; d233b46 muestra larga y
  reutilización de cliente; 77ce3db navegación cercana; 9514703 conciliación estricta
  de ataque unknown sin atribuir kill; f712bf0 deduplicación y contradicciones.
- c_227 concilió cero golpes observados sin replay ni kill añadida; actor excluido.
  Hubo varios bloqueos/reanudaciones manuales: estabilidad prolongada no demostrada.
- Pruebas registradas: 227 suite antes de últimos arreglos; después 18 ciclo, 5 runner,
  7 first-job, 2 navegación y sintaxis Perl para sus cambios. No afirmar suite final completa.
- Job Changer cargado y negativa real Job1 comprobada. Resolución de identidad y
  cambio exitoso aún sin observar con un elegible. Tutorial completo ya demostrado.
- Siguiente: Claude lee estado fresco, preserva el proceso activo y revisa al terminar;
  nuevo alcance tras evaluación/aprobación. Ver [relevo](../HANDOFF.md).

## P5.5 — primera muestra de entrenamiento (2026-11-01)

- Muestra determinista agotó presupuesto: base3/job2, 11 kills acumuladas, 52 acciones, cero inferencias. La navegación c_52 quedó pendiente al cierre; se consultó su resultado retenido (arrived) y se concilió sin repetirla. El cliente Nilo siguió activo.
- Continuación autorizada por el usuario hasta una hora, para observar en juego. Consultar resumen y checkpoint antes de operar; no reiniciar servicios ni otros clientes.

## P5.5 — entrenamiento preparado para muestra (2026-11-01)

- Identificación del Job Changer solicita nombre al servidor para el actor exacto; cambios, nombre incorrecto o timeout se rechazan. Sin validación viva de esta corrección.
- Meta persistente de entrenamiento y modo explícito sin inferencia usan build y campo existentes; pruebas locales cubren reanudación, requisitos y bloqueo de resultado incierto. La muestra en segundo plano aún no constituye evidencia de éxito.
- Último estado verificado previo a la muestra: Nilo detenido en Prontera (153,192), Novice base2/job1; tutorial completo y ciclo 1/1 completo, sin inflight. Consultar resumen de la muestra antes de volver a iniciar al cliente.

## P5.5 — NPC cargado y negativa observada (2026-11-01)

- Job Changer personalizado cargado tras confirmar cero jugadores; rAthena arrancó sin errores de parser observados. Nilo Job 1 viajó y recibió la negativa real del NPC; clase, EXP, puntos, Zeny e inventario sin cambios. [Evidencia](evidence/P5-first-job.md).
- Límite: OpenKore observó nombre vacío en ese NPC; el validador `first_job` exige el nombre y podría rechazar a un elegible. Falta identificación segura y cambio real. Entrenamiento reanudable a Job 10 pendiente.
- Nilo detenido en prontera (153,192), base2/job1; tutorial completo y ciclo 1/1 completo, sin inflight. Servicios de servidor y Ollama activos.
- Siguiente: revisar resolución segura de identidad del NPC y plan de validación del cambio sin fabricar requisitos.

## P5.4 — tutorial y primera kill observados (2026-11-01)

- Conciliación específica de la recepcionista con dos snapshots frescos completos;
  resultado original conservado. El puente espera inventario estable tras warp o
  bloquea por incertidumbre. 216 tests OK y sintaxis Perl OK.
- Una muestra: tutorial completo, destino Swordsman/Izlude, build novice-swordman,
  campo prt_fild08 y kill 1/1; 11 acciones tutorial y 29 ciclo. Nombre del objetivo
  «M4 Poring» corresponde al alias compartido de Poring; el resultado no incluye
  ID de especie. [Evidencia y límites](evidence/P5-tutorial-exit.md).
- Nilo detenido, checkpoints completos sin inflight; snapshot prt_fild08 (336,211),
  HP38/46, base2/job1. Sin petición ni tarea al detenerlo. Servicios heredados activos.
- El principal evaluará el siguiente alcance; no iniciar P5.5 sin aprobación.


## P5 paso 4 — estado histórico previo a la prueba en vivo (2026-11-01)

- `d64b41e`: `scripts/prepare_p5.py` (Nilo, cuenta 2000031, puerto 8771, `runtime/p5/`, solo INSERT;
  aún no ejecutado), `npc_script` en el puente (etiquetas declaradas, único texto el nombre propio,
  éxito solo con el warp del servidor), `config/p5-tutorial.json` desde `novice.txt` (22 preguntas),
  `agent/tutorial.py`, `DestinationPlanner` (solo Izlude/Swordsman y Prontera/Acolyte; resto
  `no_supply_route`) y `run_p2_cycle.py run --agent p5 --p5`. Suite: 207 OK.
- **Corrección del relevo, verificada por Codex:** no hay defecto de stats iniciales.
  PACKETVER 20130807 usa la rama >=20120307 de `char_clif.cpp` (stats a 1), y
  `char.cpp` toma `start_status_points=48`. Pares de stats/0 puntos corresponden
  solo a PACKETVER <20120307. No aplicar el cambio propuesto por el relevo anterior.
- Revisión independiente: `prepare_p5.py` repone items si un personaje existente queda
  sin inventario; vincular equipo inicial solo a creación nueva antes de ejecutar prepare.
- Sigue faltando la build `novice-acolyte` si se ofrece Prontera/Acolyte.
- Último estado registrado por Claude: juego parado; SearXNG/Ollama disponibles.
  Verificar procesos/puertos antes de arrancar servicios existentes; autorización rutinaria vigente.
- Siguiente: Chat 12, coherencia del perfil/destinos y prueba acotada de P5.4 en vivo.

## P5 paso 3 — campos de caza según nivel y peligro (2026-11-01)

- Tablas públicas generadas y reproducibles: 214 monstruos (`config/p5-monsters.json`) y 144 campos
  con spawns, portales gratuitos y punto de entrada (`config/p5-fields.json`), desde rAthena y OpenKore fijados.
- `agent/hunting.py`: peligro estimado, objetivos viables, aprendizaje por retiradas y muertes, opciones
  de campo validadas, temperamento por personaje y desempate con semilla. `FieldPlanner` elige con un motivo;
  si falla, se mantiene el campo. `run_p2_cycle.py run --p5` integra la build, la caza y el campo. Suite: 188 OK.
- En vivo con Tarin: Groq eligió prt_fild06 (`prudent`, «lowest danger»). Travel llegó en 64 s,
  5 kills viables ahí, venta en Prontera y vuelta a prt_fild06; 14/14 kills, sin muertes. Cliente P1 detenido.
  [Evidencia y límites](evidence/P5-hunting-fields.md).
- Pendiente: sin subida de nivel en vivo, el reparto de puntos dentro del runner solo está probado
  con simulaciones; tampoco se han visto en vivo retiradas, muertes ni un cambio de campo por nivel.
  Siguiente: revisión del orquestador; luego, P5 paso 4.

## P5 paso 2 — stats, habilidades y equipo (2026-10-31)

- Acciones nativas `stat_up`, `skill_up`, `equip` y `unequip` (contrato en `M1Progress.pm`), admitidas
  con el estado observado y completadas solo con el paquete del servidor (`00BC`, `010E`, `0999`/`099A`).
  Tabla de requisitos de equipo generada desde rAthena pre-re (122 objetos). Política local
  determinista (`agent/build_policy.py`), tres builds (`config/p5-builds.json`) y macro-meta
  `BuildPlanner` que solo elige o mantiene una build; si falla, la build se mantiene. Suite: 166 OK.
- En vivo con Tarin (`a8052d5`): Groq eligió `novice-swordman` en 2,16 s; Knife desequipado y reequipado;
  STR 5→11 (12→0 puntos) y NV_BASIC 0→2, 10/10 acciones confirmadas. Cliente P1 detenido.
  [Evidencia y límites](evidence/P5-stats-equipment.md).
- Pendiente: en vivo no se vio un rechazo ni un equipo nuevo mejor; la política todavía no
  está en el runner continuo. Siguiente: revisión del orquestador; luego, P5 paso 3.

## P5 paso 1 — funciones planner/chat y evaluación (2026-10-31)

- Adaptador compatible con OpenAI y servicio por función (`planner`/`chat`) con
  cola, límites y respaldo propios; `chat` solo local. Fallo o 429 de la nube:
  error explícito, el runner sigue y las siguientes peticiones usan el respaldo
  local marcadas `degraded`. Claves por entorno o `runtime/secrets/model-keys.env`.
- Banco grabado de 13 casos (metas, informe determinista, P4). Groq gpt-oss-120b:
  100 % JSON, 96 % coherencia, ~0,8 s. 9B actual 77 %; 9B con think no termina
  (bucle hasta agotar tokens). Gemini 3.6 Flash gratis: 503 y 429 tras 21 llamadas.
  Gemma 4 12B local: 85 %, ~0,6 s, pico GPU 11,5 GiB; mejor respaldo local que el 9B.
  [Evidencia](evidence/P5-model-eval.md). Sin pruebas en vivo del juego.
- **Decisión del usuario aplicada (`4fb70b1`):** planner Groq gpt-oss con esquema y
  respaldo Gemma 4 12B; chat Gemma 4 12B local (ctx 8192, temperatura 0,7). Un solo
  modelo local cargado (11.529 MiB). Metas, comunidad, M3 y mecánicas usan las
  funciones. Llamada real: Groq 0,81 s; Gemma saludo 11,7 s en frío. Suite 149 OK.
- Pendiente: revisión humana del chat con Gemma. Siguiente: P5 paso 2.

## P5 — nueva dirección del usuario (2026-10-31 15:50)

- El 9B no basta para decidir e informar. Se adoptan dos funciones de modelo
  (planificador inteligente, conversador local) y la meta de progreso autónomo
  desde nivel 1 hasta primera clase; luego comunidad. [Plan P5](NATIVE_AGENT_PLAN.md#p5--progresión-autónoma-desde-nivel-1).
- Modelo configurado sin cambios hasta evaluar. Hallazgo: `config/m2-operating.json`
  limita al 9B (num_ctx 2048, num_predict 160, think false, temperature 0.7).
- Relevo único en `HANDOFF.md` de este checkout; el de la raíz se borró por atrasado.
- Siguiente: P5 paso 1 en sesión propia (adaptador y evaluación de candidatos).

## P4 — SearXNG restaurado, calidad pendiente (2026-10-31)

- Docker iniciado por el usuario; contenedor SearXNG activo en 8080. Dos consultas
  reales con 9B devolvieron fuentes, pero ninguna respuesta factual sustentada:
  categoría demasiado amplia y fragmento ambiguo. [Evidencia](evidence/P4-public-mechanics.md).
- Siguiente: mejorar selección y evidencia útil con pruebas reproducibles; P4
  sigue incompleto y la interfaz standalone no está conectada al planner.

## P4 — estado anterior al reintento (2026-10-31)

- Consulta standalone con 9B y categorías públicas cerradas; una búsqueda como
  máximo, fuentes externas fechadas y caché en memoria por 24 h. No está conectada
  al planner ni al runner y no ejecuta acciones. P4 sigue incompleto.
- Ollama respondió; SearXNG no: Docker Desktop se intentó iniciar, pero el motor
  Linux no respondió y el contenedor existente no pudo verificarse. Muestra real
  del 9B sobre peso/regeneración terminó en `SearchUnavailable`, fallback explícito.
- `python -m unittest discover -s tests -v`: 127 OK. Evidencia y límites:
  [P4](evidence/P4-public-mechanics.md). Próximo paso: reparar el backend Docker
  existente y comprobar una consulta real con fuentes antes de integrar al planner.
- Chat 10 aceptado por el principal: 9/9 completo, sin intención pendiente;
  cancelación viva y latencia no medidas, carrera de llegada bloquea conservadoramente.


## P3 — cobertura de integración del runner (2026-10-31)

- `60023ce` aceptado por revisión del orquestador e independiente. Cinco pruebas
  nuevas con puente simulado; suite completa 123 OK. Cubren cancelación, orden
  inverso, snapshot posterior, reinicio, fallos y carrera de llegada.
- Sin runtime ni servicios tocados en este cierre. Último checkpoint vivo 9/9
  completo; cancelación real y latencia siguen sin demostrar.
- Siguiente: revisión del chat principal. [Evidencia](evidence/P3-dynamic-exploration.md).

## P3 — reacción de exploración y meta completada (2026-10-31)

- Interrupción determinista implementada y 118 tests OK; requiere las dos
  confirmaciones y snapshot posterior. Incertidumbre bloquea sin replay.
- Muestra única: ataque inmediato confirmado, 8→9/9; sin ruta ni cancelación
  real observada. P1 detenido sin petición pendiente. No se inició otra meta.
- Servicios existentes activos; M4 detenido. [Evidencia y límites](evidence/P3-dynamic-exploration.md).
- Siguiente: revisión del chat principal; la latencia y cancelación viva siguen
  sin medir. No repetir muestras ni crear metas fuera del alcance de la entrega vigente.

## P3 — estado histórico: exploración viva y nueva meta del 9B verificadas (2026-10-31)

- `90a65af` validado en una muestra: límite 180 s/12 acciones, fin por complete
  a los 30,641 s y 6 envíos. Tarin 6→8 kills; una ruta arrived, dos recogidas,
  un ataque rechazado por distancia, cero muertes e inferencia durante la caza.
- Ruta prt_fild08 (175,240)→destino (125,265), llegada observada (126,265).
  Monstruos visibles en 8/9 snapshots de navegación; el controlador terminó
  la ruta antes de atacar. HP mínimo 40/57. [Evidencia y límites](evidence/P3-dynamic-exploration.md).
- Una propuesta real del 9B: hunt/additional_kills=1, goal_saved 9, 13,094 s;
  cero acciones de juego. Checkpoint entonces activo **8/9**, sin intención
  pendiente; historial de operaciones conservado y meta 8 añadida al historial.
- P1 detenido tras lectura fresca sin tarea; prt_fild08 (121,269), HP57/57,
  Zeny13. Inventario conservado, con +1 Jellopy (909) y +1 Empty Bottle (713).
- Se iniciaron solo los servicios existentes ausentes: MariaDB PID50024,
  login40760, char55704, map36528. Quedan activos; Ollama ya estaba disponible,
  ahora con el 9B cargado (GPU observada 9800 MiB). M4 no se inició ni reinició.
- Raw fuera de Git: `runtime/p1/evidence/p3-live-1793468925/`. Sin cambios de
  código ni preparación de DB, fixtures, spawns o recompensas en esta entrega.
  Los dos objetivos muertos se llamaban M4 Poring; no demuestra spawns naturales
  ni autonomía general. Se mantienen límites de rayos e historial de intentos.
- Revisión del chat principal: run-result y planning-result confirman la muestra
  y meta 8/9. Aceptada la integración local con los límites descritos.
- Siguiente entrega: Chat 10, respuesta a objetivos elegibles durante exploración
  con cancelación confirmada; conservar 8/9 e historial. Nuevos chats: Terra 6.1 medio.

## P3 — límite de búsqueda observado (2026-10-31 14:02)

- Una prueba de 14 acciones terminó sin encontrar monstruos visibles; meta
  real 6/8, sin intención pendiente y P1 detenido. La revisión delegada encontró
  que la patrulla repite seis posiciones sin ampliar cobertura. La lista vacía
  es solo percepción local, no prueba ausencia global ni fallo del servidor.
- Antes de verificar una nueva meta del 9B, mejorar exploración local y probar
  una muestra breve. [Evidencia](evidence/P3-search-limitation.md).

## P3 — continuación verificada con 9B real (2026-10-31 13:57)

- e05d6fc integra --intent, una admisión, propuestas restringidas por capacidades
  actuales y aplicación validada sobre el mismo objeto bajo el bloqueo del runner.
- Prueba real: modelo 9B seleccionado propuso continuar; resultado continued,
  goal8, kills6, una acción completada, sin intención pendiente. P1 detenido.
- 111 tests OK. Nuevas metas tras completar la actual: probadas con simulación,
  aún no en vivo. [Evidencia y comandos](evidence/P3-goal-boundary.md).
- Fallo anterior de permisos resuelto mediante aprobación autorizada.
  Documentación P2 pendiente confirmada en 9cd0354; publicación en curso.
- Snapshot final prt_fild08 161,277, HP57/57, Zeny13. No se alteraron servicios
  ni otros clientes. Mantener checkpoint 6/8, límites y modelo existentes.

## Registro anterior
Actualizado: 2026-10-31 13:24 (America/Santiago), Codex.

## Avance — circuito individual real (2026-10-31 13:41)

- Meta acumulada 8: Tarin 4→6 kills, cliente P1 detenido; objetivo activo
  6/8, sin intención pendiente. Continuó tras vender y comprar.
- Caza/loot → Prontera → venta cinco objetos (+18 Zeny) → compra Apple
  (−15 Zeny) → regreso a prt_fild08: resultados y deltas confirmados.
  [Evidencia y límites](evidence/P2e-live-supply.md).
- La ruta c_14 seguía activa al acabar el límite; una consulta de solo lectura
  recuperó completed/arrived sin reenvío antes de detener P1.
- 99 tests OK. `ac845da` corrige el script anterior para detenerse ante
  rechazos. Revisión de tienda delegada, sin otros procesos tocados.
- P2 demuestra el ciclo individual en este mapa y tienda; autonomía general,
  selección de peligro y operación prolongada siguen sin demostrarse.

## Dirección y checkout

- Un jugador normal primero; rAthena pre-Renewal y ejecución OpenKore nativa.
  9B local para objetivos/conversación y SearXNG para conocimiento, después.
  [Plan](NATIVE_AGENT_PLAN.md), [guía](USER_GUIDE.txt), [relevo](../HANDOFF.md).
- Continuar en `D:/Ragnarok Agents/m4-continuous`, rama `codex/single-agent-plan`.
  La raíz está en `codex/web-search` con WIP: es entrada al proyecto, no checkout
  de implementación. Se sincronizó su HANDOFF, que seguía atrasado en P1b.
- Claude dejó P1, P2a y P2b en commits hasta `500b542`, sin WIP en este checkout.
  Registro entrante AI Relay actualizado correctamente: 12 conversaciones,
  3 actualizadas. No se seleccionó ninguna conversación por fecha.

## Entregado y evidencia

- P1: navegar, atacar, recoger, respawn y recuperación local sin inferencia.
  [Navegación](evidence/P1a-native-navigation.md), [combate](evidence/P1b-native-combat.md).
- P2a: portales caminables gratuitos y diálogo NPC acotado, sin MapRoute.
  [Evidencia](evidence/P2a-portal-travel-npc.md).
- P2b: política de abastecimiento y venta/compra NPC con conciliación exacta.
  [Evidencia](evidence/P2b-npc-supply.md).
- P2c, primera entrega, commit `67c35eb`: usar Apple durante descanso, con
  paquete propio confirmado y disminución exacta de una unidad. Registro previo
  al envío en `runtime/p1/openkore/solo/healing-state.json`; timeout, reinicio
  incierto o fallo del registro bloquean uso adicional. No se repite el envío.
  [Evidencia y límites](evidence/P2c-local-healing.md).
- Verificación de este paso: 81 tests OK (4 nuevos), sintaxis Perl OK y
  compileall del runner/tests OK; git diff --check OK. El primer intento de
  tests aislado falló al cargar Perl (WinError 623); la suite elevada pasó.
- Una sola caza real, 91,3 s: 3 kills, 1 recogida, 0 muertes propias, Apple 1→0
  confirmada, 0 llamadas de inferencia. Final de la muestra: base 4/job 2,
  prt_fild08 (174,246), 22/57 HP, descansando. Ese HP es de fin de muestra,
  no del cierre del cliente, que permaneció descansando hasta detenerlo.
- Raw: `D:/Ragnarok Agents/runtime/p1/evidence/hunt-1793461320.json`, fuera de Git.

## Procesos y datos compartidos

- P2d persistente implementado, `1238a3d` y `3463953`: objetivo, fase,
  intención antes del envío y consulta de resultado sin replay. 94 tests OK;
  revisión delegada de solo lectura y correcciones de sesión/inventario.
  [Evidencia y comandos](evidence/P2d-persistent-cycle.md).
- Estado actual del piloto: objetivo 2/2 completo, sin intención pendiente.
  Tres procesos sucesivos: envío y cierre, consulta/continuación, cierre del
  objetivo con cero acciones nuevas. Dos kills, dos recogidas, cero muertes
  propias e inferencia. Snapshot final prt_fild08 156,243, 57/57 HP,
  base4/job3, 10 Zeny. Cliente P1 detenido al terminar.
- Estado persistente: `runtime/p1/cycle/state.json`; eventos/status acotados
  en esa carpeta. Copia congelada en `runtime/p1/evidence/cycle-1793463752`.
  Cambio de boot/sesión, caché perdida o resultado incierto bloquean; no borrar
  checkpoint para repetir una operación. El objetivo cumplido no se reinicia.
- El bloque P2c anterior conserva el estado de su prueba, no el estado actual.

- Tarin, cuenta 2000030, perfil P1 solo, manual, puente 8770: detenido tras esta
  prueba con prepare_p1.py stop. No se preparó/resetearon sus datos ni se añadió
  HP, objetos o experiencia. La Apple comprada por Claude se consumió.
- Antes de arrancar se verificaron los tres clientes m4-field vivos: PID
  30496/60476/43560, ai=off, puertos 8765–8767. No se tocaron. No ejecutar
  prepare_m4.py contra esos perfiles.
- rAthena/MariaDB/Ollama: heredados en ejecución; no reiniciados. SearXNG,
  último estado conocido offline. No se volvió a comprobar su backend.
- Visitor mantiene el grupo local Observer (20), puesto por Claude con permiso;
  conf/import/groups.yml fuera de Git. No se alteró esta configuración.
- Todos los checkouts comparten runtime, DB, GPU y puertos. Mantener recursos
  fijados: RAM libre ≥2 GiB, GPU ≤14336 MiB; modelo Qwen3.5 9B Q6_K existente.
- WIP preservado: raíz (config/m2-candidates.json, fixtures/m2-scenarios.json,
  fixtures/m2-grounding-probes-v2.json), m3-worktree (diálogo/run/tests) y
  m4-field (documentación Chat 07). No mezclar ni limpiar.
- Las demos M3/M4 conservan evidencia histórica en docs/evidence; no equivalen
  a progreso general. Naturalidad, prueba larga y escala a cinco aplazadas.

## Avance — conciliación y llegada diferida (2026-10-31 13:36)

- `31196aa`: conciliar únicamente navigate terminado con
  `unknown/route_ended_off_target`: sesión nueva y dos snapshots frescos,
  separados y estables, misma identidad/mapa, sin tarea ni movimiento.
  Conserva el resultado unknown, registra posición sin afirmar llegada y replantea.
  No aplica a compras, ventas, recogidas ni ataques inciertos.
- Primera ruta conciliada en prt_fild08 130,225; continuación logró kill 3,
  pero otra ruta devolvió el mismo unknown. Se revisó el diseño antes de repetir.
- En el segundo caso Task::Route terminó con destino establecido pero posición
  aún en movimiento. `c9077df` espera hasta 5 s en ese caso y solo confirma
  llegada si la posición llega; la primera ruta tenía destino distinto, por lo
  que la espera no se aplica. 98 tests OK; sintaxis Perl OK.
- Segunda ruta conciliada desde una sesión nueva en 170,280. Continuación:
  una acción de ataque, meta completa 4/4, sin replay ni inferencia; snapshot
  170,287, 41/57 HP, 10 Zeny. Cliente P1 detenido.
- La continuación no ejecutó una ruta tras la reparación, por tanto el tiempo
  de espera nuevo solo está verificado por tests, no por navegación real.
  Tampoco se activó abastecimiento; la prueba integrada de tienda sigue pendiente.
- Evidencia fuera de Git: `runtime/p1/evidence/cycle-reconcile-1793464544`.
  Revisión delegada independiente del puente; sin otros procesos tocados.

## Avance histórico — nuevo objetivo y ruta incierta

Commit `4d31c1e`: `set-goal --target-kills N` asigna una meta acumulada
solo tras completar la anterior, sin intención pendiente. Repetir la misma
meta es idempotente; conserva las últimas 24 operaciones y 24 objetivos.
96 tests OK; revisión delegada de condiciones de reinicio.

Prueba real: meta 2→4 guardada; tres rutas completadas, cuarta terminó
`unknown/route_ended_off_target`. Checkpoint `runtime/p1/cycle/state.json`
bloqueado, kills 2/4, intención c_4 conservada, última posición 131,226,
57/57 HP. No llegó a la tienda. Cliente P1 detenido; no borrar el checkpoint.

Próximo paso: inspeccionar la causa y diseñar conciliación segura de navegación
incierta desde observaciones frescas, sin repetir operaciones financieras.
Validar la recuperación antes de continuar el abastecimiento integrado.

## Pendientes y próxima acción

El checkpoint vigente es 9/9 completo, sin intención pendiente. Peligro general, SearXNG y
comportamiento prolongado siguen pendientes. No repetir operaciones inciertas.
