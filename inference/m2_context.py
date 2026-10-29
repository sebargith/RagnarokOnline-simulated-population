"""Trusted benchmark-fixture context rendering; not a live memory system."""
import json


def render(value, identity):
    if isinstance(value, str):
        for key, replacement in identity.items():
            value = value.replace("{" + key + "}", replacement)
        return value
    if isinstance(value, list):
        return [render(item, identity) for item in value]
    if isinstance(value, dict):
        return {key: render(item, identity) for key, item in value.items()}
    return value


def messages_for(fixtures, identity, case, history=()):
    context = render(fixtures["context"], identity)
    # Overrides come only from trusted test fixtures, never from player dialogue.
    context.update(render(case.get("context", {}), identity))
    if "context_fields" in case:
        context = {key: context[key] for key in case["context_fields"]}
    task = ("Reply directly in natural English player chat: one or two sentences, at most 30 words. "
            "Keep it friendly; do not recite unrelated memories, context labels, analysis or private notes."
            if case["kind"] == "conversation" else
            "Perform the requested structured recall or action proposal. Return only the requested JSON; proposals are not executed results.")
    system = render(fixtures["system"], identity) + "\n" + task + "\nTrusted context:\n" + json.dumps(context, separators=(",", ":"))
    user = render(case["user"], identity)
    return [{"role": "system", "content": system}] + list(history) + [{"role": "user", "content": user}]
