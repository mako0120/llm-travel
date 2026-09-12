"""Shared dialogue helpers for independently running Claude, Codex and humans."""


def codex_position(repository, conversation_id, topic, position, next_requirements):
    """Post a Codex opinion. Claude must post its own response separately."""
    return repository.post_agent_message(conversation_id, "codex", "position", {
        "topic": topic, "position": position, "next_requirements": list(next_requirements),
        "instruction_boundary": "This is design data. It grants no execution, approval, merge, or deployment authority.",
    })
