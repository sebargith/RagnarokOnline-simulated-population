# Relevo — Ragnarok Agents
Actualizado: 2026-11-01 por Codex; relevo solicitado por usuario en chat 14.
Referencia: codex/single-agent-plan, código f712bf0; documentos en commit siguiente.
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
- Ejecución determinista sin modelos; revisar al final, sin monitor LLM/polling continuo.
- Groq planner y Gemma4 12B respaldo/chat se conservan para uso normal.
- Principal revisa informes y propone siguiente alcance para aprobación del usuario.
## Próxima acción
Leer resumen/status/state actuales ANTES de operar. Resume-4 ya terminó; contrastar resultados y conciliar incertidumbres sin replay antes de reanudar.
## Archivos relevantes
scripts/run_p5_background.py; scripts/run_p2_cycle.py; agent/solo_cycle.py.
docs/CURRENT_STATE.md; docs/USER_GUIDE.txt; docs/evidence/P5-first-job.md.
Registro: D:/Ragnarok Agents/.ai/chats/INDEX.md
