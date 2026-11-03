# Relevo — Ragnarok Agents
Actualizado: 2026-11-03 por Claude (relevo a Codex tras R2)
Referencia: rama codex/single-agent-plan, commit_ref 8911f1b; este relevo en el commit siguiente.
## Objetivo actual
Comunidad de jugadores IA creíbles en rAthena pre-Renewal. P5 cumplido (novato desde nivel 1 →
Swordman). Siguiente: demostrar ≥ 4 h sin intervención y empezar R3 (comunidad de 2 personajes).
## Estado comprobado
- Único relevo: este archivo. Checkout D:/Ragnarok Agents/m4-continuous; raíz y m3/m4-field con WIP: no tocar.
- Camino principal = R1: OpenKore `--ai=auto` con config generada desde política declarativa
  (`config/r1-policy*.json` → `scripts/build_r1_profile.py`); `scripts/run_r1.py
  preflight|prepare|start|watch|stop|campaign|class-refit --character tarin|nilo --runtime ../runtime`.
  Puente solo para lo irreversible (tutorial, Job Changer, compraventa explícita, comercio).
- Nilo (cuenta 2000031, runtime/r1-nilo, puerto 8773): Swordman Base 13 / Job 3, en prt_fild00.
  Tarin (2000030, runtime/r1, puerto 8772): Swordman Base 14 / Job 4. Ambos clientes detenidos.
- En vivo R1+R2: ~3,6 h acumuladas con 0 intervenciones y 0 muertes; ~316 kills/h; tanda más larga 1,5 h.
- Ciclo antiguo P5 congelado (`scripts/freeze_p5.py`, `runtime/p5/FROZEN.json`); M1Travel, walk,
  exploración, fases de abastecimiento y recovery_tick congelados sin borrar. Detalle: R2-native-main-path.md.
- Servicios rAthena/MariaDB, Ollama y SearXNG activos al cierre. Verificar la suite completa al retomar.
## Decisiones vigentes
- rAthena pre-Renewal PACKETVER 20130807; Job Changer propio aprobado; sin premios, spawns ni @ para bots.
- Modelos: planner Groq gpt-oss-120b (respaldo Gemma 4 12B local) elige campo al subir de nivel; chat Gemma local.
- Suelo de RAM 0,5 GiB y techo de GPU 14.336 MiB para tandas largas (el usuario usa ComfyUI).
- Chat orquestador + una sesión por objetivo, un solo escritor. Documentación breve (revisión R5).
## Incompleto / problemas / validaciones pendientes
- MTBI ≥ 4 h en una sola tanda sin demostrar (long-1 cortada por un fallo del supervisor, ya
  corregido; long-2 la paró el usuario).
- No vistos en vivo: una muerte con reaparición, `r1_flee` sin alas, mapa marcado como peligroso.
- P4 (iRO Wiki Classic como fuente primaria) y R3 (comunidad) sin empezar.
- No editar vendor/openkore/tables/monsters.txt; claves en runtime/secrets/model-keys.env (no leer valores).
## Próxima acción
1) Tanda ≥ 4 h con Nilo (`run_r1.py campaign --character nilo`, `--ram-min-gib 0.5`), con preflight
y aviso al usuario. 2) Después, R3: Tarin y Nilo en el mismo campo con chat local, grupo e
intercambio; métricas sociales y normas de chat según docs/research/PROJECT_REVIEW-2026-11.md §4 y §7.
## Archivos relevantes
- docs/evidence/R1-openkore-auto.md; docs/evidence/R2-native-main-path.md; docs/research/PROJECT_REVIEW-2026-11.md.
- scripts/run_r1.py; scripts/build_r1_profile.py; config/r1-policy*.json; bridge/r1/; docs/ARCHITECTURE.md.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
