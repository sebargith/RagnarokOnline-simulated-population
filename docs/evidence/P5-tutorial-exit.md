# P5.4 — muestra del tutorial (2026-11-01)

P5.4 sigue **incompleto**. Una sola muestra, detenida automáticamente tras dos
rechazos iguales; no se repitió. Nilo, cuenta 2000031 / char 150007, era inexistente
antes de `prepare`. Se creó en `new_2-1` (53,111), nivel 1, 48 puntos; la
repetición conservó Knife 1201 y Cotton Shirt 2301, equipados. Los casos de
inventario vacío, cuenta existente e interrupción son simulados en SQLite, no
se vació el inventario real. No se alteraron personajes ajenos.

## Muestra y diagnóstico

`python scripts/run_p2_cycle.py run --runtime ../runtime --agent p5 --p5 --seconds 480 --max-actions 100 --goal-kills 1`

- `c_1`: travel completado en 18,529 s; portal `new_2-1` → `new_2-2`,
  evidencia de posición calculada (100,26), destino (100,27), delta Zeny 0.
- `c_2` y `c_3`: navigate rechazado `already_at_destination`; el controlador
  bloqueó `two_consecutive_action_failures`, paso 1 (recepcionista).
- El snapshot mostraba posición (100,17), origen de movimiento, mientras el
  cálculo usado por la evidencia de llegada indicaba (100,26). El puente
  rechazó el destino porque `pos_to` era (100,27). Se cambió el snapshot para
  usar el cálculo de posición de OpenKore, con regresión reproducible; la
  corrección todavía no se ha ejecutado en vivo.
- No se observó diálogo NPC, decisión de destino, cambios de stats/habilidad o
  equipo, salida del tutorial ni kill. No se marca P5.4 completo.
- Antes de detener el cliente, `ready.pending_request_id=null`, `native_task=null`
  y `navigation=null`. SQL `check-save` tras detenerlo confirmó `new_2-2`
  (100,27), save `new_2-1` (53,111), nivel base/job 1, Zeny 0. Checkpoint
  bloqueado e historial conservados en `runtime/p5/cycle/tutorial.json`; eventos
  en `runtime/p5/cycle/events.jsonl` (ambos fuera de Git).

## Verificación y límites

`python -m unittest discover -s tests`: 213 OK; regresiones de creación,
interrupción, ramas/configuración de rAthena, rutas de suministro y builds.
El plugin Perl pasó `-c` con las rutas `src`, `src/deps` y `bridge/lib`.
Los primeros intentos de sintaxis sin rutas de dependencias fallaron; después
pasó con las rutas completas. Primer comando aislado de tests falló por una
ruta de importación; la suite discover completa pasó. Una consulta SQL de stats
falló por comillas; no modificó datos.

Se arrancaron solo MariaDB 22600 y login 40216, char 12516, map 31736, que
siguen activos; cliente Nilo detenido. Ollama ya escuchaba en 11434. GPU al inicio
2192 MiB; en la muestra 2176–2181 MiB, RAM libre >6 GiB. Roles y modelos sin
cambios. El cambio del snapshot afecta a observaciones generales del puente y
requiere validación viva. No reiniciar ni borrar el checkpoint para ocultar los
rechazos; revisar una recuperación explícita y segura antes de continuar.

## Recuperación y segunda muestra (2026-11-01)

El comando `python scripts/run_p2_cycle.py recover-receptionist --runtime ../runtime --agent p5`
exigió los rechazos originales y dos snapshots de una sesión nueva, separados
1025 ms, en new_2-2 (100,27), sin movimiento ni tarea, y preservó el historial.
La posición en reposo coincide con el guardado previo; no verifica interpolación
viva durante movimiento. El cálculo de OpenKore en reposo y movimiento se probó
con un recorrido simulado; el controlador pasa de travel a npc_script en tests.
`bridge_steps` también recibe la posición calculada; no se ha probado en vivo.

Se ejecutó la misma muestra `run --runtime ../runtime --agent p5 --p5 --seconds 480
--max-actions 100 --goal-kills 1`: terminó tras una acción, sin inferencias, con
`reward_mismatch:receptionist`. El servidor confirmó warp a new_1-2 (100,70)
y la opción Apply for training. El resultado incluyó inventario vacío justo
al warp frente a Knife y Cotton antes; una lectura posterior con inventory_ready
mostró ambos equipados. `talk_tick` finaliza inmediatamente al detectar warp y
`talk_snapshot` no espera inventory_ready: explicación consistente, no prueba de
que no existieran otros efectos. No se repitió el diálogo ni se alteró el paso.
Resultado y checkpoint: `runtime/p5/cycle/tutorial.json`, eventos en
`runtime/p5/cycle/events.jsonl`, fuera de Git. No hubo decisión, campo ni kill.

`python -m unittest discover -s tests`: 215 OK con el Python del proyecto y Perl
local, fuera del aislamiento. Un intento aislado quedó sin salida y se interrumpió;
el alias Python del sistema mostró error de instalación. Servicios de juego y
MariaDB existentes ya escuchaban; solo se inició Nilo. Antes de detenerlo una
lectura confirmó pending_request_id=null, native_task=null, navigation=null,
cola vacía, posición igual al destino y recuperación none. Ollama seguía activo. El cambio
no se probó en movimiento vivo; P5.4 sigue incompleto.
