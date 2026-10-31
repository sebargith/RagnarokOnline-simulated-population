# P2d — ciclo individual y reanudación sin replay

Fecha: 2026-10-31. Base `7c8ac17`; puente `1238a3d`, controlador `3463953`.

## Entrega

- `agent/solo_cycle.py`: objetivo persistente de kills confirmadas, caza/loot,
  recuperación local y abastecimiento necesario con las capacidades P1/P2.
  Piloto Tarin/prt_fild08 y Fruit Gardener ya conocidos; no navegación ni economía
  general de todo Ragnarok.
- `scripts/run_p2_cycle.py`: un proceso con bloqueo exclusivo, checkpoint antes
  de enviar y logs rotativos acotados. Tiempo 1..3600 s, presupuesto opcional de
  acciones. El proceso termina solo; no requiere inferencia ni chat por tick.
- Archivo `runtime/p1/cycle/state.json`: objetivo, fase, progreso confirmado,
  intención en vuelo y últimas 24 operaciones. Escritura con flush/fsync y reemplazo.
- Consulta autenticada `query_result`, sesión e ID exactos: solo lectura de la
  caché nativa, sin admisión de ID, paquetes de juego ni reenvío. Cambio de
  sesión, caché perdida, plazo vencido o resultado incierto bloquean el objetivo.
  No inferimos una compra o kill a partir de ausencia del objeto/monstruo.
- Resultados terminales aislados por sesión y snapshot posterior al resultado
  antes de otra decisión. Espera inicial desde inventario listo +1,5 s; rechaza
  inventario truncado. Recalcula necesidad y presupuesto tras vender.
- Solo completed con razón prevista avanza. Dos fallos ordinarios consecutivos
  paran; recuperación espera al puente. Muerte o recuperación agotada bloquean.
- Recursos totales: RAM libre ≥2 GiB, GPU ≤14336 MiB. Telemetría inválida termina
  este runner; no se permiten nuevas acciones sin medición válida.
- status usa archivos, sin competir por el socket; revisar antigüedad de su
  heartbeat, pues un archivo no prueba por sí solo que el proceso esté vivo.

## Revisión delegada y verificación

Un agente hizo revisión de solo lectura, sin escrituras ni procesos. Señaló
pérdida de resultados tras cerrar socket, rechazo tratado como éxito, observación
anterior a la venta, colisión de ID entre sesiones e inventario inicial parcial.
Se incorporaron pruebas y barreras para esos casos.

Comandos realmente ejecutados desde D:/Ragnarok Agents/m4-continuous:

- Python compartido: `D:/Ragnarok Agents/.venv/Scripts/python.exe`.
- `python -m unittest discover -s tests -p test_p2_cycle.py -v`: pasó durante
  desarrollo. Una suite intermedia falló por un NameError al ubicar la espera de
  inventario; corregido antes de la prueba real.
- `python -m unittest discover -s tests`: **94 OK**, 4,968 s, versión final.
  13 nuevas pruebas: circuito simulado, reload, ack duplicado, caché perdida,
  cambio de sesión, buy/sell incierto, fallo de escritura, observación posterior,
  rechazo de ruta, recuperación e inventario incompleto. Sin servicios de juego.
- `perl -c bridge/openkore/m1_bridge.pl`, PERL5LIB con OpenKore `src`,
  `src/deps` y el `bridge/lib` del checkout: syntax OK, con aviso de locale.
- `python -m compileall -q agent/solo_cycle.py scripts/run_p2_cycle.py tests/test_p2_cycle.py`: OK.
- `git diff --check`: OK.

## Prueba real de cierre y reanudación

Con los tres clientes m4-field existentes sin tocar y sin reiniciar servicios:

1. `python scripts/prepare_p1.py start --runtime 'D:/Ragnarok Agents/runtime'`.
2. `python scripts/run_p2_cycle.py run --runtime 'D:/Ragnarok Agents/runtime' --seconds 20 --goal-kills 2 --pause-after-send`.
   Envió exactamente un ataque c_1 y cerró el socket dejando intención persistida.
3. `python scripts/run_p2_cycle.py run --runtime 'D:/Ragnarok Agents/runtime' --seconds 100 --max-actions 4`.
   Consultó c_1: completed/killed Lunatic, cinco golpes y 63 de daño.
   No lo volvió a enviar. Continuó con c_2 take, c_3 navigate, c_4 attack
   (Pupa, 28 golpes/444 daño) y c_5 take. Terminó por presupuesto de acciones.
4. `python scripts/run_p2_cycle.py run --runtime 'D:/Ragnarok Agents/runtime' --seconds 10 --max-actions 1`.
   Resultado complete, 2/2 kills, cero nuevas acciones, sin intención pendiente.
5. `python scripts/prepare_p1.py stop --runtime 'D:/Ragnarok Agents/runtime'`.
6. `python scripts/run_p2_cycle.py status --runtime 'D:/Ragnarok Agents/runtime'`:
   leyó complete sin conectarse al cliente detenido.

Sin muertes ni inferencia. Dos drops recogidos (Clover y Chrysalis). Último
snapshot: prt_fild08 156,243, 57/57 HP, base4/job3, 10 Zeny.
Última muestra de recursos: RAM libre 12139257856 bytes, GPU 1684 MiB;
no es una medición de capacidad prolongada.

La prueba real precede a dos ajustes finales de administración: PID/antigüedad
de status y eliminación de escritura redundante del checkpoint en espera.
La suite final pasó después; el mecanismo de juego/reanudación no cambió.

## Evidencia congelada y límites

Fuera de Git: `runtime/p1/evidence/cycle-1793463752/`.

| Archivo | SHA-256 |
| --- | --- |
| events.jsonl | 0e67dbf95af335011ae0be357291968259503fb75d7e5054e483d27bf85fc6cb |
| state.json | ea887ec54da1deeb60d46d7c1ac6f4e96a68c8d04f059c20349108351b8d1314 |
| status.json | 64c6296bde9394a9a6d308cedaa4bc3258d53a14d0f754590cec10962979f2c5 |

El circuito completo de tiendas está probado con estados reproducibles; esta
ejecución real no necesitó tienda (10 Zeny, botín debajo del umbral).
No acredita circuito completo vivo, supervivencia general ni autonomía prolongada.
La caché es de un arranque del plugin: perderla bloquea, no reconstruye
automáticamente operaciones financieras desconocidas. Conservar checkpoint.
El objetivo completado permanece completado; --goal-kills solo inicializa
uno nuevo y no reemplaza el existente. Falta una interfaz para asignar otro
objetivo sin borrar historial. Selección de peligro y descubrimiento de tiendas
siguen pendientes, al igual que P3/P4.
