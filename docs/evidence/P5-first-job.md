# P5.5 — carga y negativa del Job Changer (2026-11-01)

Regla personalizada aprobada: seis primeras clases clásicas, Novice normal Job 10 y puntos de habilidad gastados; sustituye las quests oficiales. No se probaron cambios exitosos de clase.

Antes del reinicio se consultaron dos veces los sockets establecidos en 5121 y el conteo SQL de personajes conectados: cero en ambas comprobaciones. Solo se reinició el map-server registrado (PID 31736 → 20924); login 40216, char 12516 y MariaDB 22600 permanecieron activos. El registro del nuevo arranque contiene carga de NPC y ready en 5121, sin errores de parser tras el inicio de carga de NPC. No se modificaron fixtures ni datos por SQL.

Prueba de 71,05 s y dos acciones: Nilo viajó de prt_fild08 (336,211) a prontera (153,192), y habló por `npc_talk` en (153,193). El NPC devolvió «Only a Novice at Job Level 10 with no unspent skill points may change.»; el diálogo se cerró con resultado completed y sin elecciones. El texto y coordenada identifican el NPC atendido. El snapshot incluía una entrada en esa coordenada; la lista de NPC del puente está truncada, de modo que no demuestra por sí sola ausencia absoluta de un segundo NPC superpuesto.

La observación antes/después conserva Novice clase 0, base2/job1, EXP base2/job1, cero puntos libres de stat y skill, Zeny 0 e inventario/equipo iguales; HP era 41 en ambas observaciones y después regeneró a 46. Cambió legítimamente la ubicación. La evidencia cruda local es `runtime/p5/evidence/first-job-live-1793538320.json` (fuera de Git).

Después se observaron dos snapshots separados con posición estable, sin tarea ni cola de movimiento, y ready sin petición pendiente. Se detuvo solo el cliente de Nilo; guardado prontera (153,192), base2/job1, Zeny0. Checkpoints tutorial completo paso9 y ciclo completo 1/1 permanecen sin inflight. Servicios de servidor y Ollama siguen activos.

## Límite detectado

El NPC percibido tenía nombre vacío en OpenKore, aunque el texto del diálogo identifica First Job Changer. El validador `first_job` actual exige el nombre resuelto antes de hablar: con esa observación rechazaría localmente incluso a un personaje elegible. No se relajó la identidad ni se simuló Job 10. Falta resolver y probar la identificación segura del NPC y el cambio real con requisitos cumplidos; también queda pendiente el entrenamiento acotado hacia Job 10.
