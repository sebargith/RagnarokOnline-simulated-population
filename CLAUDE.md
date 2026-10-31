# Continuidad del proyecto

Sigue las reglas de [AGENTS.md](AGENTS.md). Para "toma el control" o
"prepara el relevo", aplica `C:/Users/azusu/AI_PROTOCOL.md`.

El punto de entrada local es `D:/Ragnarok Agents/HANDOFF.md`. El código actual
continúa en el checkout existente `D:/Ragnarok Agents/m4-continuous`, rama
`codex/single-agent-plan`; no crear otro checkout para este relevo. Dentro de él,
leer [HANDOFF](HANDOFF.md), [estado](docs/CURRENT_STATE.md) y
[plan aprobado](docs/NATIVE_AGENT_PLAN.md). No implementar en la raíz antigua.

Los servicios, puertos, GPU y bases son compartidos. Verificar quién los usa
antes de una prueba; no reinicializar datos ni reiniciar al jugador por rutina.
