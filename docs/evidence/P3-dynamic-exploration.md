# P3 — exploración local dinámica

2026-10-31, checkout `codex/single-agent-plan`. La patrulla fija de seis
puntos se reemplazó en el ciclo persistente por candidatos generados desde
el mapa cargado por OpenKore. No se consultan entidades globales del servidor.

- Hasta 48 rayos de 20, 35 y 50 casillas desde la posición observada; se
  descartan bordes, celdas no caminables y líneas obstruidas con
  `Field::isWalkable` y `Field::checkPathFree`. Cada ruta conserva el ejecutor
  único `Task::Route`, validación de destino y timeout de 25 s.
- Se favorece la mayor distancia respecto de las últimas 24 posiciones de
  exploración, guardadas antes del envío. Se priorizan monstruos observados;
  resultados inciertos conservan el intent y las reglas existentes sin replay.
  Sin candidatos o sin el campo del puente se detiene con motivo explícito.
- Los límites del runner siguen siendo tiempo y acciones; dos fallos de acción
  consecutivos bloquean. No interviene el modelo para estas decisiones.
- Esta búsqueda solo considera rutas rectas libres, no prueba conectividad
  general ni cobertura completa; puede agotarse en zonas estrechas. Un portal
  interior no visible podría atravesarse; un cambio inesperado de mapa mantiene
  el tratamiento conservador de navegación. La muestra viva inferior valida
  un recorrido, sin demostrar cobertura general.

## Comprobaciones

- `& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' -m unittest discover -s tests -v`:
  115 OK. Incluye paredes, líneas bloqueadas, ausencia de candidatos, selección
  de áreas, prioridad del monstruo, reinicio e intención incierta. La primera
  versión del escenario combinó filtros que eliminaban todos los candidatos;
  se corrigió el escenario antes de la ejecución completa.
- `perl -c bridge/openkore/m1_bridge.pl`, con `PERL5LIB` apuntando a
  `vendor/openkore/src`, `src/deps` y `bridge/lib`: syntax OK (aviso de locale).
- `python -m compileall -q agent/solo_cycle.py tests/test_p3_exploration.py` y
  `git diff --check`: OK.
- Prueba de solo lectura con `Field->new(file => 'fields/prt_fild08.fld2.gz',
  loadWeightMap => 0)` y `M1Explore::candidates` desde (165,240): mapa 400×400,
  41 candidatos; hay candidatos a 50 casillas. No demuestra presencia de mobs.

## Bloqueo anterior, resuelto

La verificación anterior no realizó la muestra viva: no existían los PID registrados
29928, 29496, 51448, 24944, 30496, 60476 y 43560; no escuchaban los puertos
3306, 6900, 6121, 5121, 8765–8767 ni 8770. El registro compartido es histórico,
no evidencia de procesos activos. P1 tampoco tiene registro de proceso. No se
iniciaron ni reiniciaron servicios o clientes en esa verificación. Checkpoint
leído entonces: meta activa 6/8, sin intención pendiente.

## Muestra viva de 90a65af y nueva meta real (2026-10-31)

Se comprobó el host con Get-Process y Get-NetTCPConnection antes de iniciar
solo MariaDB y login/char/map existentes, usando m1.launch y wait_port sobre
3306/6900/6121/5121. Se conservó el registro previo; los PID históricos de M4
no se trataron como procesos vivos. No se ejecutó prepare/initialize, SQL de
preparación, cambios de configuración, fixtures, spawns ni recompensas.
La primera consulta CIM falló por acceso; la comprobación real y los comandos
de runtime funcionaron con ejecución autorizada fuera del sandbox.

Comandos ejecutados desde este checkout con el Python compartido:

```powershell
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/prepare_p1.py start --runtime 'D:/Ragnarok Agents/runtime'
# Harness por stdin, con exclusive(runtime/'p1/cycle.lock') y Bridge(sink=...):
# Runner(cycle, bridge, runtime/'p1/cycle').run(180, max_actions=12)
# Segundo harness: solo pump()/planning_tick() del Runner existente, máximo 100 s,
# una GoalPlanner/BoundedInference y cero llamadas a proposal() de juego.
& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' scripts/prepare_p1.py stop --runtime 'D:/Ragnarok Agents/runtime'
```

El primer harness usó las mismas clases del runner CLI y añadió captura local
de eventos; terminó por `complete` a los **30,641 s**, con **6 envíos**, 6→8
kills, sin intención pendiente y cero inferencias. No hubo segunda muestra de
juego ni cambio de código. Sesión: `1a193143698-db5c-39f979dc:1`.

| Petición | Acción | Resultado confirmado |
| --- | --- | --- |
| c_1 | attack | rejected/target_too_far; ninguna kill atribuida |
| c_2 | navigate (125,265) | completed/arrived; posición (126,265), 9353 ms |
| c_3 | attack M4 Poring | completed/killed, 55 daño, 5 golpes, HP48/57 |
| c_4 | take 909 | completed/picked_up, +1 Jellopy |
| c_5 | take 713 | completed/picked_up, +1 Empty Bottle |
| c_6 | attack M4 Poring | completed/killed, 55 daño, 4 golpes, HP40/57 |

Inicio vivo en prt_fild08 (175,240), HP57/57, Zeny13. Destino de exploración
(125,265), desde los candidatos locales; llegada confirmada a una casilla.
155 eventos y 32 snapshots; monstruos visibles en 29 snapshots, incluyendo
8 de los 9 de navegación. M4 Poring apareció con Tarin navegando en (169,246),
y Lunatic también fue visible. La ruta continuó hasta llegada antes del ataque
c_3: queda demostrado ese comportamiento, no una interrupción reactiva al ver
un monstruo. HP mínimo observado 40/57; cero eventos de muerte. Al completar:
(121,269), HP42/57, dos objetos añadidos; Apple sin consumir y Zeny sin cambio.
Los dos objetivos muertos se llamaban **M4 Poring**; esta muestra no demuestra
spawns naturales, peligro general ni progreso prolongado. Se recuperó del
rechazo inicial sin repetir la misma petición; no bloqueó la aceptación.

Después se verificó Ollama 0.40.12 y el digest configurado del 9B
`77beda99ef49a70c129557ba3d6a35fc8cb829fce36cfda6f9ea60bb5221ee6f`.
Una sola intención real: `The previous goal is complete. Set a new hunt goal
for one additional confirmed kill.` El segundo harness usó las funciones P3
existentes bajo el bloqueo; resultado en 13,094 s: propuesta
`{"type":"hunt","additional_kills":1}`, `goal_saved`, `goal_kills:9`.
Una inferencia y **cero acciones de juego**. Se comprobó igualdad del historial
de operaciones antes/después, kills=8 e inflight=null; goal_history conserva
2/2, 4/4 y añade 8/8. Checkpoint actual **activo 8/9**.

Lectura fresca previa a detener P1: sin tarea ni petición pendiente, prt_fild08
(121,269), HP57/57, Zeny13. Inventario: objeto915×1, Apple512×1, Knife1201×1,
Cotton Shirt2301×1, Jellopy909×1 y Empty Bottle713×1. La curación histórica
confirmada en healing-state no se reinterpretó como un nuevo consumo.

Servicios que quedan activos: MariaDB50024, login40760, char55704, map36528;
Ollama25416 ya existía y conserva el 9B cargado con keep_alive=5m. GPU observada
tras inferencia: 9800 MiB; RAM libre antes: 11228553216 bytes. Son muestras,
no mediciones de pico. P1 detenido con su helper; ningún cliente M4 iniciado,
detenido ni reiniciado. No se tocaron los otros procesos Python del host.

Raw fuera de Git: `D:/Ragnarok Agents/runtime/p1/evidence/p3-live-1793468925/`:
`bridge-events.jsonl`, `run-result.json`, `state-before.json`, `state.json`,
`status.json`, `events.jsonl`, `planning-bridge-events.jsonl`,
`planning-result.json`, `after-planning-state.json`, `after-planning-events.jsonl`,
`model-verified.json`, `resources-after-inference.json`, `final-observation.json`,
`processes-before.json`, `services-started.json` y `services-final.json`.

Los 115 tests del apartado anterior corresponden al cambio de implementación;
esta entrega solo valida runtime y actualiza documentos. No se repitió la suite.
`git diff --check`, enlaces internos de los cuatro documentos y aserciones
contra los JSON de muestra/meta/checkpoint/servicios finales: OK.
Siguiente acción: revisión del chat principal. Se mantienen los límites de
rayos rectos 20/35/50 e historial de destinos intentados; no se afirma cobertura
confirmada a partir de ese historial ni se amplía el alcance a P4/población.


## Reacción durante exploración (2026-10-31)

La ruta de exploración se marca en el checkpoint antes del envío. Un snapshot
actual de la misma tarea nativa puede activar una sola cancelación si muestra
un monstruo vivo, no reclamado por otro jugador, no omitido y si HP y
recuperación permiten actuar. El puente calcula elegibilidad con las mismas
observaciones de combate; este valida otra vez al atacar. La cancelación y la
ruta tienen IDs separados persistidos: se esperan `cancelled/cancel_requested`
y `completed/navigation_cancelled`, en cualquier orden. Un resultado distinto,
inaccesible, sesión distinta o plazo agotado conserva el bloqueo sin reenvío.
Tras ambas confirmaciones se exige snapshot posterior y se replantea; el destino
o monstruo puede haber desaparecido. Hay cinco segundos antes de otra
interrupción y el límite de acciones incluye la cancelación. Viajes, tienda y
aproximaciones no llevan la marca. La recuperación nativa sigue teniendo prioridad.
La observación depende del intervalo de snapshots y del ciclo del runner: no
se midió latencia viva de interrupción y no se promete instantaneidad.

Comprobación: `& 'D:/Ragnarok Agents/.venv/Scripts/python.exe' -m unittest
discover -s tests -v` fuera del sandbox: 118 OK. El primer intento dentro del
sandbox falló con WinError 5/623; la primera suite autorizada reveló dos errores
en mocks de sesión, corregidos antes de repetirla. `perl -c
bridge/openkore/m1_bridge.pl` con PERL5LIB `../vendor/openkore/src`,
`../vendor/openkore/src/deps`, `bridge/lib`: syntax OK; compileall y
`git diff --check` OK. Las pruebas cubren confirmaciones, desaparición,
cancelación incierta, tareas distintas y recuperación; no miden tiempos reales.

Única muestra: `prepare_p1.py start`, `run_p2_cycle.py run --runtime
'D:/Ragnarok Agents/runtime' --seconds 120 --max-actions 8`, sin intención,
y `prepare_p1.py stop`. Monstruo visible al inicio: c_1 attack,
completed/killed M4 Poring, 5541 ms en puente, 4 golpes y 59 daño; 8→9/9,
una acción, cero inferencias. No se inició ruta ni cancelación, por lo que la
prueba viva no demuestra la interrupción ni su latencia. No se creó otra meta.
Lectura antes de detener: sin petición ni tarea, prt_fild08 (118,272), HP63/63.
Raw: `runtime/p1/evidence/p3-interrupt-20261031/`. Puertos finales 3306, 6900,
6121 y 5121 activos; 8770 y 8765–8767 sin escucha. No se reiniciaron servicios.
