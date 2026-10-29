# Working on this project with Codex

Use the existing **Ragnarok Agents** local project at `D:\Ragnarok Agents`. The repository files carry durable context; each chat has its own conversation. Keep implementation and debugging of the same outcome in one chat, and start a fresh chat when moving to the next milestone.

Current deployment choice: **native Windows**, using PowerShell and project-local `vendor\`, `runtime\` and `.venv\` where practical. Reuse installed system tools and existing model stores in place. WSL/Docker are outside the selected runtime. This documentation choice does not start M1 or authorize installation in a documentation-only chat.

## How to start

1. Open **Ragnarok Agents** in Codex and create **01 - Environment audit** in **Local / This computer** mode.
2. Paste the first prompt below. The repository already contains the general rules; do not paste the original long setup prompt again.
3. Review the native Windows procedure in M0 evidence. Start **02 - Server and client bridge** when ready to implement the selected layout, adding any adjustment to the prompt.
4. Continue with **03 - Local inference benchmark**, then **04 - One persistent agent**, after their prerequisites pass.

Create milestone chats as needed, not all at once. Use the main coordinator chat to evaluate evidence, track progress and GitHub publication, and decide when to start the next milestone. Keep implementation of each milestone in its focused chat.

For routine implementation, begin with your usual capable coding model at medium reasoning if available. Use higher reasoning for difficult integration or architectural debugging when it helps. Avoid changing models for every small step; judge by completed, verified work and rework. These are configuration recommendations, not settings applied by this document.

## 01 - Environment audit

```text
Work on M0 in this repository. Read AGENTS.md, docs/CURRENT_STATE.md,
and the M0 criteria in docs/ROADMAP.md; consult ARCHITECTURE as needed.

Inspect the relevant Windows/WSL environment, GPU and available VRAM,
Git state, installed dependencies, and any existing relevant assets.
Distinguish verified facts from assumptions. Do not search unrelated
personal folders. Recommend one practical local deployment layout and
a small M1 setup plan, including missing dependencies, download sizes
where known, and how to prove rAthena/client/OpenKore compatibility.
Bound research to the decisions needed for M1.

Save concise evidence in docs/evidence/M0-environment.md and update
CURRENT_STATE. Do not install dependencies or download models yet.
Review the repository setup files and create one local initial commit
containing only the reviewed setup and M0 documentation. Do not push.
If Git identity or an existing change prevents that, report the exact
issue without changing global Git settings.

Finish with the recommended setup, meaningful choices requiring my
input, and the next implementation step. Do not start M1 in this chat
unless I ask you to continue.
```

## 02 - Server and client bridge

Prerequisite: review the native Windows, project-local procedure in M0 evidence. The user has selected that layout; starting this assignment authorizes its scoped implementation. State any adjustment when pasting the prompt.

```text
Implement M1 from docs/ROADMAP.md using the native Windows setup in
docs/evidence/M0-environment.md, which I approve for this task.
Read AGENTS.md and CURRENT_STATE, verify prerequisites, and proceed
through the scoped local setup and bridge implementation.

Use PowerShell at D:\Ragnarok Agents. Prefer project-local vendor,
runtime and .venv directories, portable MariaDB/Perl, and existing
system Git/Python/Visual Studio tools. Test the space in the project
path and match native tool/DLL architectures. Keep PATH changes local
to the launching process. Preserve existing Ollama/model stores.
Use a local TCP bridge; do not switch to WSL/Docker implicitly.

Pin the tested server, client/protocol, and OpenKore revisions. Prove
Python can receive an observation and request a validated action.
Run the M1 connection, chat, gameplay, failure, and reconnect checks.
Keep installed dependencies and runtime data in documented locations;
keep credentials and generated data out of Git.

Make reversible implementation decisions without repeatedly asking
for approval. If the selected integration cannot meet the criteria,
document the failure and recommend the smallest necessary change.
Update README with commands actually verified, save concise M1
evidence, update CURRENT_STATE, and make a scoped local commit when
the checks pass. Do not push or start the social system yet.
```

## 03 - Local inference benchmark

```text
Implement M2 from docs/ROADMAP.md. Read AGENTS.md, CURRENT_STATE,
and the environment and resource findings relevant to the benchmark.
Reuse suitable installed model/runtime assets. Compare two justified
local candidates initially, including a smaller baseline. Download
only the selected candidates after checking storage and compatibility.

Build reproducible fixtures for conversation, recall, and bounded
action proposals. Measure realistic one-, three-, and five-session
profiles under the server/client resource load. Record cold/warm
conditions, context and generation settings, sample counts, latency,
queue delay, RAM/VRAM, and failures. Prepare sample conversations for
my quality review; do not substitute your own rating for that review.

Recommend one configuration and explicit operating budgets, or explain
why none qualifies. Save compact evidence in docs/evidence/M2-inference.md,
update operating commands and CURRENT_STATE, and commit validated
benchmark tooling locally. Do not push or expand the shortlist without
a concrete unresolved question. Do not mark human review complete
until I provide it.
```

## 04 - One persistent agent

Prerequisite: M1 passes and the user accepts M2's sample quality and operating budget.

```text
Implement M3 from docs/ROADMAP.md with the proven M1 bridge and the
M2 model/configuration and operating budget, which I accept for this
task. Read AGENTS.md, CURRENT_STATE, and the relevant evidence first.

Build the smallest complete persistent agent: one identity, one
gameplay routine, grounded conversation, bounded memory retrieval,
and a commitment that survives restart. Keep observations, beliefs,
dialogue, and confirmed action outcomes distinct. Validate actions
and retain per-agent information boundaries.

Implement and run checks for the M3 failure cases and the 30-minute
scenario. Prepare conversation excerpts and observable results for
my review. Record actual performance, update the relevant documents,
and make scoped local commits at validated milestones. Continue
debugging within this outcome; do not begin population expansion.
Report human review as pending until I provide it.
```

## Later work and handoffs

After M3 acceptance, start **05 - Three-agent simulation** with: "Implement M4's three-agent stage using the validated M3 system. Follow its isolation, persistence, load, and one-hour trial criteria. Prepare evidence for human review before attempting five agents."

For an independent review, use a fresh chat only when useful: "Review the current milestone diff against its acceptance criteria. Identify concrete correctness or missing-validation issues with file locations and evidence. Do not edit files." Supply the actual commit range or uncommitted scope.

If resuming unfinished work, use: "Continue M[number]. Read AGENTS.md and CURRENT_STATE, inspect the current files and relevant evidence, and complete the next unfinished acceptance criterion. Preserve existing changes and report only checks you actually run."

## Parallel work and Git

Start sequentially in Local mode. Once there is a committed baseline and independent tasks with stable interfaces, use separate worktrees for concurrent edits. Choose a starting commit that contains the required work and verify the files exist there; do not assume another chat's changes or transcript transferred. Coordinate shared services, database state, ports, and GPU benchmarks separately. Integrate deliberately and run the affected integration checks.

Do not create a dedicated chat for every file or keep separate planning, coding, and testing chats for one small feature. Keep the handoff in CURRENT_STATE compact and factual; history stays in Git and evidence files.

## Product references

Verified for this setup on 2026-10-28; UI wording may change.

- [Projects and chats](https://learn.chatgpt.com/docs/projects): local folder access and separate chat histories.
- [Codex environments](https://learn.chatgpt.com/docs/environments/modes): Local and Worktree execution on your computer.
- [Worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees): isolated checkouts for concurrent work.
- [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md): durable repository instructions.
