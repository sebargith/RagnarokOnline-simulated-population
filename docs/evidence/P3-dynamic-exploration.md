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
  el tratamiento conservador de navegación. El recorrido no se ha probado vivo.

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

## Estado vivo

No se realizó la muestra viva: en esta sesión no existían los PID registrados
29928, 29496, 51448, 24944, 30496, 60476 y 43560; no escuchaban los puertos
3306, 6900, 6121, 5121, 8765–8767 ni 8770. El registro compartido es histórico,
no evidencia de procesos activos. P1 tampoco tiene registro de proceso. No se
iniciaron ni reiniciaron servicios o clientes. Checkpoint leído: meta activa 6/8,
sin intención pendiente. Próximo paso: con servicios disponibles, verificar
su estado y realizar una única muestra acotada del nuevo recorrido, revisando
resultados e intención pendiente antes de detener P1.
