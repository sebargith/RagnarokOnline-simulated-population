# P5 paso 2 — stats, habilidades y equipo

Fecha: 2026-10-31. Rama `codex/single-agent-plan`; implementación `a8052d5`.

## Qué se implementó

- **Acciones del puente** (solo en el perfil nativo, `--ai=manual`): `stat_up {stat}`,
  `skill_up {skill}`, `equip {name_id}`, `unequip {name_id}`, con `timeout_s` 5–30.
  Contrato puro en [M1Progress.pm](../../bridge/lib/M1Progress.pm) y conexión en
  [m1_bridge.pl](../../bridge/openkore/m1_bridge.pl).
- **Admisión con el estado observado:**
  - puntos libres ≥ coste del stat, y stat < 99;
  - la habilidad está en la lista del servidor con su marca `up` y queda ≥ 1 punto;
  - el objeto está en el inventario, sin equipar, identificado y es equipable;
  - la clase, el nivel base y el sexo cumplen la tabla de requisitos.

  `cancel` no se admite sobre estas acciones: el paquete ya salió.
- **Resultado** solo con el paquete del servidor (PACKETVER 20130807):
  - stat: `00BC` con `ok` y el valor anterior +1 (OpenKore no lee el byte `ok`; el puente lo lee del paquete crudo);
  - habilidad: `010E` con el nivel anterior +1;
  - equipo: `0999` / `099A` con flag 0 = éxito. OpenKore marca un objeto como desequipado aunque el servidor lo rechace, así que manda el flag.

  Si el servidor rechaza, el resultado es `failed server_refused`; si vence el plazo, `unknown result_not_confirmed`, sin reenvío.
- **Snapshot:** nuevo bloque `progress` (clase, sexo, stats con su coste, puntos y habilidades);
  en el inventario se añaden `location` e `identified`.
- **Tabla de requisitos** [p5-equipment.json](../../config/p5-equipment.json) (122 objetos), generada por
  [build_p5_equipment.py](../../scripts/build_p5_equipment.py) desde `item_db_equip.yml` pre-re, con el commit de
  rAthena fijado. Incluye el equipo inicial y el que venden las tiendas NPC: es la información de la
  descripción del objeto. El resto del equipo (botín raro) se rechaza como `equipment_requirements_unknown`.
- **Política local** [build_policy.py](../../agent/build_policy.py), determinista y sin modelo:
  - stats en orden estricto, guardando los puntos si el siguiente objetivo no se puede pagar;
  - habilidades en orden, saltando las que el servidor no lista o no deja subir;
  - en cada ranura equipa algo solo si es estrictamente mejor (ATK para el arma, DEF para el resto) y lo admitido por las mismas reglas que el puente;
  - deja en paz las ranuras con objetos desconocidos y no toca los accesorios.
- **Builds** [p5-builds.json](../../config/p5-builds.json): `novice-swordman`, `novice-archer` y
  `novice-thief`, todas con NV_BASIC 9 primero.
- **Macro-meta** `BuildPlanner` / `apply_build` en [goal_planner.py](../../agent/goal_planner.py):
  - el esquema solo admite ids de la lista y un motivo de ≤ 200 caracteres;
  - el prompt lleva solo hechos del juego, sin el nombre del personaje;
  - un fallo, un vencimiento o una respuesta inválida conservan la build;
  - aplicarla exige una percepción reciente y que la build no haya cambiado entretanto;
  - la build queda fija tras el cambio de clase;
  - la elección se guarda en `runtime/p1/cycle/build.json` con su motivo y sus hechos.

## Pruebas

- `python -m unittest tests.test_p5_progress tests.test_p5_build`: 17 OK (módulo Perl real con
  estados grabados; política y planner con un servicio simulado).
- `python -m unittest discover -s tests`: 166 OK.

## Integración en vivo (Tarin, cuenta 2000030)

- **Antes de arrancar:** servicios activos (MariaDB 3306, login 6900, char 6121, map 5121), puerto 8770
  libre y ningún OpenKore corriendo. `scripts/prepare_p1.py start`; al terminar, `stop`.
  No se tocó la base de datos ni ningún servicio.
- **Pasada de observación:** nivel base 5 / job 3, Novice, 12 puntos de stat, 2 de habilidad,
  todos los stats a 5, NV_BASIC 0, Knife y Cotton Shirt equipados.
- **Ejecución:** `python scripts/p5_progress.py --runtime ../runtime --plan --cycle-equip 1201 --max-actions 30`
  (evidencia en `runtime/p1/evidence/p5-progress-1793490525.json`, fuera de Git; 23,4 s).
  - **Planner:** Groq gpt-oss, una llamada de 2,16 s, sin degradación.
    Resultado: `choose_build novice-swordman`, motivo: «All stats are equal and free points are available;
    a Swordman build can allocate STR/VIT…».
  - **Knife:** desequipado con `099A` (flag 0, ubicación 2) y reequipado con `0999` (flag 0, ubicación 2).
  - **Stats:** 6 × `stat_up str`, cada uno con `00BC` ok y el valor +1: STR 5→11 y puntos 12→0
    (coste 2 por punto en este tramo).
  - **Habilidades:** 2 × `skill_up NV_BASIC`, con `010E`: nivel 0→2 y puntos 2→0.
  - **Final:** la política queda inactiva con `saving_points_for_str,no_skill_points,nothing_better_to_equip`.
    10/10 acciones completadas; ninguna rechazada ni incierta.

## Límites

- En vivo no se vieron un rechazo del servidor, un vencimiento del plazo ni un equipo nuevo mejor:
  esos caminos solo están cubiertos por pruebas. Ni subir una habilidad de primera clase ni
  equipar un objeto de la tabla distinto del Knife se ha comprobado en vivo.
- Si el servidor ignora en silencio una subida de habilidad, el resultado es `unknown` y la política se bloquea
  (conservador; requiere revisión).
- La política todavía no está conectada al runner continuo (`run_p2_cycle`): hoy se ejecuta con `p5_progress.py`
  entre tramos de juego. Conectarla queda para cuando se integren los pasos siguientes.
- Los nombres de objeto del snapshot salen de las tablas coreanas del cliente: el planner los recibe así.
