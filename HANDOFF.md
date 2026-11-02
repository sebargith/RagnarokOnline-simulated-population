# Relevo — Ragnarok Agents
Actualizado: 2026-11-02 por Claude (alcanzabilidad a pie y tiempo de viaje).
Referencia: codex/single-agent-plan, código fae125e; documentos en commit siguiente.
## Preflight 2026-11-01
- No se lanzó otra ejecución: GPU 14991–15130 MiB, sobre el límite 14336 MiB; RAM libre 2,83 GiB. No se tocaron procesos.
- El estado de la muestra anterior no es una observación actual; proceso 31704, puerto y locks no quedaron confirmados desde este entorno.
- Al retomar: comprobar recursos, controlador, identidad/puerto/locks y checkpoint fresco antes de lanzar.
## Lanzamiento 2026-11-01
- Ejecución en curso al inicio: wrapper PID 5484 (lanzador 11596), cliente 31704 reutilizado; planner por defecto, 3600 s/600 acciones (runner 3570 s).
- Preflight: RAM 12,60 GiB, GPU 1449 MiB, locks libres, Nilo confirmado y checkpoint sin inflight.
- Resumen y logs: runtime/p5/evidence/resume-20261101-unique-1/. Resultado no evaluado; revisar resumen al retomar.
## Alcanzabilidad a pie 2026-11-02 (Claude)
- Resultado de resume-20261101-unique-1: bloqueado a los 5 minutos con c_384 `travel:failed/unreachable` en prt_castle (102,20); corregido.
- **Cambios:**
  - e574b18 rutas por zonas transitables (`config/walk-zones.json`, `scripts/build_walk_zones.py`); opciones de campo y abastecimiento alcanzables;
  - eda1a07 puertas internas por zona;
  - fae125e tiempo de viaje según la ruta (30–300 s) y `navigate` dentro del mismo mapa;
  - 80c13c2/38034e7 `reconcile-travel`.
- **En vivo:** dos reinicios del cliente aprobados por el usuario (ahora PID 46148). En 870 s salió del castillo, quedó en prt_fild00, de 136 a 148 kills y abastecimiento a unos 220 s.
- **Final:** active/return con c_56 travel en vuelo: consultar el resultado retenido, no reenviar. Evidencia: runtime/p5/evidence/walk-reachability-1/.
- **Pendiente:**
  - coste del abastecimiento en la elección de campo;
  - carrera de arranque (`Listen => 1` en el puente frente a `wait_port`): reutilizar el cliente o arrancarlo antes con `prepare_p5.py start`.
## Objetivo actual
Nilo entrena legítimamente hasta Job10 y primera clase con NPC gratuito en Prontera.
## Estado comprobado (muestra, no estado permanente)
- Checkout D:/Ragnarok Agents/m4-continuous; único HANDOFF vigente. Preservar WIP raíz.
- Lectura 2026-11-01 11:35:05 -03: Base7/Job6, kills107, HP74/78, Zeny416, prt_fild08 {'x': 62, 'y': 343}.
- status=active, fase=hunt, inference_calls=0.
- Acción pendiente en checkpoint: c_268 attack; consultar estado fresco al retomar.
- Wrapper2564, runner69208, cliente31704 verificados activos 11:33:58 -03.
- Revisión de Claude: la ejecución resume-4 TERMINÓ (runner_exit_code 1, ~410 s de 3600)
  porque el guardián cortó con RAM libre < 2 GiB. Checkpoint coherente: active/hunt, kills 113,
  Base7/Job6, Zeny 433, sin inflight. Cliente 31704 seguía vivo y ocioso.
- Resumen runtime/p5/evidence/train-first-job-resume-4-summary.json; límite3570s/600acciones.
- Tutorial completo. goal_kills=1 es histórico: train-first-job sigue hasta clase,
  no se detiene al superar una kill. No resetearlo ni reenviar inflight.
## Avances
- 01c4cd5: train_first_job con planner de campo por defecto (level_up, campo inseguro, 30 min);
  --no-inference conserva el modo determinista. Suite 240 OK. En vivo, 870 s: Groq
  prt_fild08→prt_fild06 (puesta al día de nivel 2 a 7) y prt_fild06→prt_fild05 en la subida real
  a Base 8; kills 113→134, sin incidencias. Ver docs/evidence/P5-field-by-level.md.
  Final: active/hunt, sin inflight, Base8/Job6, Zeny950, prt_fild05; cliente 31704 ocioso.
- Job Changer para seis primeras clases, Job>=10 y puntos gastados; sin extras.
- NPC cargado y rechazo Job1 observado. Éxito real/identidad aún sin validar en elegible.
- 4b05449 entrenamiento reanudable/no-inference; d233b46 ejecución larga/reúso cliente.
- 77ce3db trata rutas terminadas cerca sin afirmar llegada exacta.
- 9514703 concilia ataque unknown con cero golpes observados, sin sumar kill y
  excluyendo actor; resultado incierto original conservado. f712bf0 deduplica resultados.
- Reanudaciones manuales tras bloqueos; NO acredita operación larga sin intervención.
## Validación y límites
- 227 tests antes de últimos fixes; después 18 ciclo,5 runner,7 first-job,2 navegación
  y sintaxis Perl según registros del chat14. No suite completa final por el principal.
- Prueba larga resume-4 terminada por el guardián de RAM; reanudar requiere RAM libre ≥ 2 GiB.
## Decisiones vigentes
- No interrumpir entrenamiento ni Visitor. No tocar otros clientes/servicios ni secretos.
- Entrenamiento con planner de campo (pocas llamadas); --no-inference para pruebas deterministas. Sin monitor LLM/polling continuo.
- Groq planner y Gemma4 12B respaldo/chat se conservan para uso normal.
- Principal revisa informes y propone siguiente alcance para aprobación del usuario.
## Próxima acción
Leer resumen/status/state actuales ANTES de operar (último: runtime/p5/evidence/walk-reachability-1/summary.json).
Reanudar con run_p5_background.py --reuse-client (planner por defecto). Pendiente: Job10 y cambio de clase,
ventas frecuentes, Gemma/vencimiento en vivo.
## Archivos relevantes
scripts/run_p5_background.py; scripts/run_p2_cycle.py; agent/solo_cycle.py.
docs/CURRENT_STATE.md; docs/USER_GUIDE.txt; docs/evidence/P5-first-job.md.
Registro: D:/Ragnarok Agents/.ai/chats/INDEX.md
