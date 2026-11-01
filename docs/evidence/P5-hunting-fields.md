# P5 paso 3 — campos de caza según nivel y peligro

Fecha: 2026-11-01. Rama `codex/single-agent-plan`. Commits:
- `a3c2a3a`: tablas;
- `586de19`: caza, planner e integración;
- `6553c7e`: prompt compacto y espera tras error.

## Qué se implementó

### Conocimiento legítimo

Las dos tablas las genera [build_p5_hunting.py](../../scripts/build_p5_hunting.py) desde datos públicos con versión fijada: rAthena `d4b8e7b` y OpenKore `e0b04ee`. Al regenerarlas sale el mismo resultado, y una prueba lo comprueba.

- **[p5-monsters.json](../../config/p5-monsters.json):** 214 monstruos con nivel, HP, ATK mín./máx., DEF, si son agresivos, si pueden atacar, si son jefe, velocidad, retardo de ataque y EXP. La agresividad sale del tipo de IA de `mob.hpp` más los `Modes` de `mob_db.yml`.
- **[p5-fields.json](../../config/p5-fields.json):** 144 campos.
  - Spawns de los scripts de campo pre-re que carga el servidor, con los raros marcados (reaparición ≥ 10 min).
  - Salidas por portales gratuitos, con el mismo filtro que `M1Travel::walk_graph`.
  - Por cada mapa vecino, un punto de entrada caminable: 10 pasos desde la llegada del portal hacia el centro, leído del `.fld2` de OpenKore.
  - No se lee `npc/custom` (fixture M4) ni nada del servidor en vivo.

### Peligro y objetivos

[hunting.py](../../agent/hunting.py) es determinista y no usa modelo.

- **Perfil propio:** ATK de estado (STR, DEX, LUK) más ATK del arma, DEF del equipo, DEF blanda por VIT, HP máximo y nivel.
- **Estimación por monstruo:** golpes para matarlo y HP perdido por kill. Supone un intervalo de ataque propio de 1500 ms, porque el ASPD no se observa, e ignora hit/flee, habilidades y elementos.
- **Viable si se cumple todo:**
  - no es jefe;
  - nivel ≤ el propio + 5;
  - ≤ 12 golpes;
  - pérdida ≤ 50 % del HP máximo, o ≤ 25 % si es agresivo;
  - el historial no lo ha marcado como demasiado fuerte: 2 o más retiradas o muertes que superen un tercio de los encuentros.
- **Caza:** ataca el viable más cercano. Un monstruo que no está en la tabla no se ataca.

### Opciones de campo

- **Condiciones de una opción:**
  - ≤ 3 saltos;
  - ida y vuelta a Prontera también en ≤ 3 saltos;
  - al menos un monstruo común viable;
  - ningún agresivo no viable entre los comunes (los raros se listan como `rare_threats`);
  - sin muerte propia en la última hora;
  - con punto de entrada.
- El campo actual siempre aparece y se marca `unsafe` si corresponde. El máximo es de 6 opciones.
- **Temperamento por personaje:** fijo según el nombre (`prudent`, `ambitious` o `explorer`); a Tarin le toca `prudent`.
  - `prudent` puntúa EXP por golpe × (1 − peligro);
  - `ambitious` puntúa solo la EXP;
  - `explorer` multiplica por 1,5 los campos que no ha cazado.
- **Desempates:** las opciones a menos del 10 % de la mejor se ordenan con una semilla del personaje. Así, personajes iguales no eligen siempre lo mismo.

### Planner y runner

- **`FieldPlanner`** ([goal_planner.py](../../agent/goal_planner.py)):
  - esquema cerrado con `field_id` del enum y motivo de ≤ 200 caracteres;
  - el prompt (unos 2000 caracteres) no lleva el nombre del personaje;
  - una petición cada vez, con plazo;
  - si falla, vence o la respuesta no es válida, se mantiene el campo.
- **`SoloCycle`** ([solo_cycle.py](../../agent/solo_cycle.py)):
  - caza en `field.id` en lugar del `prt_fild08` fijo; los checkpoints antiguos lo conservan;
  - en la fase `hunt` aplica primero `build_policy.next_action`;
  - un `failed` o `rejected` de stat, habilidad o equipo pausa la build hasta el siguiente nivel; un `unknown` bloquea sin reenviar;
  - guarda su historial: kills y retiradas por monstruo y por campo, muertes y segundos de caza;
  - pide una decisión de campo cuando no la hay, al subir de nivel base, tras 3 retiradas o cada 30 minutos.
- **`run_p2_cycle.py run --p5`:** `P5Planning` pide la build una vez si no existe y luego las decisiones de campo.
  - Mientras espera la respuesta, el juego sigue.
  - La decisión se aplica con el ciclo inactivo, una percepción de ≤ 2,5 s y revalidando que la opción siga ofrecida.
  - Un error de petición espera 60 s antes de reintentar.

## Pruebas

- `python -m unittest discover -s tests -p test_p5_hunting.py`: 22 OK. Cubren:
  - danger con monstruos reales;
  - reglas y agresividad;
  - aprendizaje;
  - opciones sintéticas: alcance, campo arriesgado, muerte reciente, temperamento y semilla;
  - regeneración idéntica de las tablas;
  - planner válido, inválido, fallido o fuera de plazo, y presupuesto del prompt;
  - ciclo: build primero, pausa, `unknown`, viaje, vuelta tras abastecerse, muerte, checkpoint antiguo;
  - runner con puente simulado: decisión, viaje y fallo que mantiene el campo;
  - espera tras error.
- `python -m unittest discover -s tests`: 188 OK.

## Integración en vivo (Tarin, cuenta 2000030)

- **Antes:**
  - servicios activos: MariaDB 3306, login 6900, char 6121, map 5121;
  - puerto 8770 libre y ningún OpenKore abierto;
  - checkpoint 9/9 completo, copiado en `runtime/p1/evidence/p5-fields-1793530794/`;
  - `set-goal --target-kills 14`, `prepare_p1.py start` y, al terminar, `stop`.
  - No se tocaron la base de datos ni los servicios.
- **Primer intento (sin acciones de juego):**
  - El prompt superaba `max_prompt_chars` 5000 y se reintentaba en cada tick. Corregido con un prompt compacto y la espera de 60 s.
  - El protector cortó por GPU > 14 GiB: la ocupaba ComfyUI, ajeno al proyecto. El usuario la liberó.
- **Ejecución:** `python scripts/run_p2_cycle.py run --runtime ../runtime --p5 --seconds 300 --max-actions 40`.
  - Resultado: `complete`, 14/14 kills, 19 acciones, 1 llamada de inferencia.
- **Decisión:**
  - disparador `no_decision`, temperamento `prudent`;
  - opciones en orden: prt_fild05 (0,303), prt_fild06 (0,277), prt_fild08 (0,167), pay_fild04, prt_fild04 y moc_fild01;
  - Groq gpt-oss, sin degradación, eligió **prt_fild06**;
  - motivo: «lowest danger rating (0.25) among the reachable fields, matching the character's preference for safer hunting…». La cifra 0,25 la puso el modelo; el código solo valida que el campo sea una opción.
- **Viaje:** `travel` a prt_fild06 (33,185) por prontera, `arrived` en 64,3 s en (33,186), con dos saltos confirmados y 0 zeny.
- **Caza en prt_fild06:** 5 kills confirmados, todos de monstruos viables: Poring ×2 (OpenKore lo etiqueta "M4 Poring" por la caché compartida, pero es el 1002 del campo), Lunatic ×2 y Thief Bug Egg ×1. Se recogió el botín.
  - Hubo una exploración cancelada dos veces al aparecer un objetivo; ambas cancelaciones quedaron confirmadas.
  - HP mínimo observado: 40/63. Sin retiradas ni muertes.
- **Abastecimiento:** el inventario pidió vender. Travel a prontera, `npc_sell sold` y travel de vuelta a **prt_fild06** (el campo elegido, no prt_fild08), con llegada a (32,206).
- **Build:** sin puntos libres y sin subida de nivel (EXP base 0→24/77), así que la política no envió acciones. El reparto de puntos dentro del runner solo está cubierto por pruebas.
- **Historial guardado:** prt_fild06 con 5 kills en 27,8 s de acciones de caza; monstruos 1002, 1063 y 1048. Evidencia en `events-live.jsonl`, `state-after.json` y `status-after.json`, fuera de Git.

## Límites

- El peligro es una estimación simple, no el cálculo exacto. No se ha visto en vivo una retirada, una muerte, el aprendizaje que excluye un monstruo ni un cambio de campo por subida de nivel.
- `hunt_s` solo suma la duración de las acciones de caza, no la espera entre ellas, así que los kills/min salen altos.
- Sin subida de nivel en vivo no hubo reparto de puntos en el runner.
- Solo se ha visto una decisión en vivo. La variedad entre personajes (temperamento y semilla) solo está probada con perfiles simulados.
- El motivo del modelo puede citar cifras inexactas: no se valida su contenido, solo el `field_id`.
- La muerte sigue bloqueando el ciclo (`character_dead`) y no hay recuperación automática tras ella.
