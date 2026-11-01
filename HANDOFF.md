# Relevo — Ragnarok Agents
Actualizado: 2026-11-01 por Codex. Rama `codex/single-agent-plan`.

## P5.5: negativa del NPC observada
- NPC gratuito de seis primeras clases cargado sin errores de parser observados; Nilo Job1 recibió la negativa real. Clase, EXP, puntos, Zeny e inventario conservados. Ver docs/evidence/P5-first-job.md.
- OpenKore informó nombre vacío para el NPC. El validador `first_job` exige nombre; un elegible podría quedar rechazado antes de hablar. No se ha observado cambio real.
- Nilo detenido, prontera (153,192), base2/job1; tutorial paso9 completo y ciclo1/1 completo, sin inflight. Servidores y Ollama activos; map-server PID 20924.
- Pendiente: resolver identificación segura del NPC y validar el cambio legítimo; entrenamiento acotado a Job10 aún no implementado. No iniciar otro hito sin aprobación.
