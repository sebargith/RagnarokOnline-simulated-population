# P5.5 — campo de caza por nivel durante el entrenamiento

Fecha: 2026-11-01. Rama `codex/single-agent-plan`, código `01c4cd5`.

## Qué cambia

- `run_p2_cycle.py run --agent p5 --p5 --train-first-job`, sin `--no-inference`:
  - comprueba lo mismo que el modo sin inferencia (tutorial completo; build guardada que coincide con el destino; campo y `return_to`);
  - usa `P5Planning` con el servicio `planner`: Groq gpt-oss, con Gemma 4 12B de respaldo;
  - la build no se vuelve a pedir; el campo se decide otra vez con los disparadores de P5.3 (`level_up`, `field_unsafe` tras 3 retiradas, `periodic_review` cada 30 min).
- Lo que ya hacía `P5Planning` y se mantiene:
  - una sola petición en vuelo;
  - la caza sigue mientras el planner responde;
  - la decisión se aplica solo con el ciclo en `hunt`, sin acción en vuelo, en el propio campo y con percepción de ≤ 2,5 s;
  - antes de aplicarla, se comprueba otra vez que la opción siga ofrecida.
- **Fallos:** si el planner falla, vence (100 s) o devuelve algo inválido, se mantiene el campo (`kept_on_failure`) y la decisión queda fechada en el nivel actual. No se vuelve a preguntar hasta la siguiente subida o la revisión de 30 minutos. Si la petición lanza una excepción, se reintenta tras 60 s.
- **Nuevo en el registro:** cada decisión de `field_decisions` y cada evento `field_result` guarda `facts`, con el nivel base y de job, la clase, las stats, el HP máximo, la build, el mapa y el historial propio del campo actual (kills, `hunt_s`, retiradas). Se suman a lo que ya guardaba: disparador, temperamento, opciones con su puntuación, motivo, decisión, `served_by` y `degraded`.
- **Modo sin inferencia:** `--no-inference --train-first-job` queda igual. `scripts/run_p5_background.py` usa por defecto el planner, y `--no-inference` mantiene el modo anterior. El resumen guarda `mode`.

## Pruebas

- `tests/test_p5_field_by_level.py` (11):
  - mismo nivel: sin petición;
  - subida de nivel que mantiene el campo, con disparador, hechos y servidor;
  - subida de nivel que lo cambia y viaja;
  - petición pendiente que no se repite mientras sale una acción de juego;
  - vencimiento que mantiene el campo sin bloquear ni volver a preguntar;
  - inferencia fallida;
  - excepción con espera;
  - aplicación diferida mientras hay una acción en vuelo (respaldo Gemma `degraded` registrado);
  - el modo de entrenamiento construye el planner;
  - se exige un campo guardado y se rechaza `--intent`.
- `tests/test_p5_no_inference.py`: añade la comprobación de que el script de fondo solo pasa `--no-inference` cuando se pide. Las pruebas que comprueban que no se construye ningún planner ni servicio siguen igual.
- `python -m unittest discover -s tests`: 240 OK.

## En vivo (Nilo, cuenta 2000031)

- **Antes:**
  - checkpoint `active/hunt`, 113 kills, sin acción en vuelo, Base 7 (EXP 132/153) / Job 6, campo prt_fild08 decidido en nivel 2;
  - coincidía con el resumen resume-4 (salida 1 por el guardián de RAM);
  - RAM libre 13,2 GiB, GPU 1,7/16 GiB;
  - MariaDB, login, char, map, Ollama y SearXNG activos; cliente 31704 en 8771.
  - No se reinició nada ni se tocó la base de datos.
- **Comando:** `python scripts/run_p5_background.py --runtime ../runtime --summary ../runtime/p5/evidence/field-by-level-1/summary.json --seconds 900 --max-actions 150 --reuse-client`.
- **Resultado:**
  - salida 0 por `time_budget` (870 s); 83 acciones; 2 llamadas de inferencia;
  - checkpoint `active/hunt`, 134 kills (+21), sin acción en vuelo;
  - Base 8 (57/200) / Job 6, Zeny 433→950;
  - sin muertes, retiradas, `p5_error` ni `runner_error`;
  - cliente reutilizado y sin detener.
- **Decisión 1 (puesta al día, no una subida real):**
  - disparador `level_up` (decidido en 2, observado en 7), temperamento `explorer`;
  - opciones: prt_fild06 2,85; prt_fild05 2,28; prt_fild08 1,54; pay_fild04; moc_fild01; moc_fild02;
  - Groq, sin degradación, respondió en unos 2 s y eligió **prt_fild06**. Motivo: más EXP por golpe con un peligro parecido, y sin historial allí;
  - travel `arrived` en 60 s.
- **Subida real a Base 8** en prt_fild06, tras 4 kills allí y un `stat_up` de VIT confirmado.
  - La petición salió con el ciclo ocioso. El ciclo empezó entonces una venta en Prontera, y la respuesta llegó durante ese viaje.
  - Se aplicó unos 104 s después, al volver a prt_fild06 con el ciclo inactivo.
  - Opciones: prt_fild01 2,61; prt_fild05 2,28; prt_fild06 1,9; prt_fild08 1,54; moc_fild01; prt_fild04.
  - Groq, sin degradación, eligió **prt_fild05**. Motivo: campo sin visitar, con `viable_share` 0,94, peligro 0,05 y EXP por golpe 1,52. No eligió la opción de mayor puntuación; el código solo valida que sea una opción.
  - Travel `arrived` en 54 s; 17 kills en prt_fild05 hasta el final.
- **Otras acciones:** 21 kills, 22 recogidas, 17 travel `arrived`, 4 ventas, 9 exploraciones canceladas y confirmadas, y ningún resultado `unknown`.
- **Evidencia local fuera de Git:** `runtime/p5/evidence/field-by-level-1/`, con `summary.json`, `state-before/after.json`, `status-before/after.json`, `events-live.jsonl` y los logs.

## Límites

- Solo se han visto en vivo decisiones `level_up` de Groq. No se han visto el respaldo Gemma, un vencimiento, `field_unsafe` ni `periodic_review`; solo están probados con simulaciones.
- Una respuesta que llega durante un viaje de abastecimiento se aplica al volver al campo anterior. Eso cuesta un viaje de ida extra (aquí prt_fild06 → Prontera → prt_fild05).
- El motivo del modelo puede citar cifras que no se validan; solo se valida el `field_id`.
- Las ventas son frecuentes: 4 viajes a Prontera en 14,5 minutos, unos 50–75 s cada trayecto. Gran parte del tiempo se va en viajes. Queda fuera de este alcance.
- Sin cambio de clase ni prueba larga (paso 6).
