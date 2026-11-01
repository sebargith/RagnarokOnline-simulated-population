# Relevo — Ragnarok Agents
Actualizado: 2026-11-01 por Codex. Rama `codex/single-agent-plan`.

## P5.5 — entrenamiento preparado
- Nombre del Job Changer se solicita al servidor para el actor exacto; timeout, sustitución o nombre incorrecto rechazan. Aún no validado en vivo para un elegible.
- Meta persistente hacia primera clase con modo explícito sin inferencia; conserva checkpoint e historial y requiere build/campo/destino guardados. Verificar resumen de la muestra antes de operar.
- Último estado anterior al lanzamiento: Nilo detenido en prontera (153,192), base2/job1, tutorial completo y ciclo1/1 completo sin inflight. Servidores y Ollama activos.
- La muestra usa proceso local limitado, sin monitor ni llamadas a modelos. El principal revisa resultados y propone siguiente alcance; no iniciar otro hito.

- Muestra anterior agotó tiempo: Nilo base3/job2, 11 kills, cero inferencias. c_52 navegación llegó, resultado consultado y conciliado sin replay; entrenamiento sigue activo sin inflight. Se prepara continuación de hasta una hora con cliente existente.
