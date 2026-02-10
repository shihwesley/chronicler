"""Section drafters: LLM-powered generators for individual .tech.md sections."""

from __future__ import annotations

from chronicler_core.drafter.models import PromptContext
from chronicler_core.drafter.prompts import PromptTemplate
from chronicler_core.llm.base import LLMProvider

_ARCHITECTURAL_INTENT_SYSTEM = """\
You are Chronicler, an enterprise technical documentation generator. \
Your task is to write ONLY the "Architectural Intent" section for a .tech.md file.

## Output Format

Write a concise Markdown section with exactly these parts:
1. **What this component does** (1-2 sentences)
2. **Why it exists** (business context if inferable from the repo data; write "unknown" if not)
3. **Key responsibilities** (bullet list, 3-7 items)

## Writing Rules

1. **Strictly technical** — no marketing language, no fluff
2. **Concise** — prefer short declarative sentences
3. **Unknown values** — write "unknown" rather than guessing
4. Do NOT include YAML frontmatter, Mermaid diagrams, or any other sections
5. Do NOT wrap the output in a heading — just the content

## Examples

### Good
Handles user authentication via JWT tokens and session management.

Exists to centralize auth logic across the platform's microservices, \
replacing per-service token validation.

**Key responsibilities:**
- Issue and validate JWT access/refresh tokens
- Manage user sessions (create, refresh, revoke)
- Integrate with corporate SSO via SAML 2.0
- Rate-limit login attempts per IP

### Bad
"This cutting-edge microservice revolutionizes the way we think about authentication..."

### Bad
"This service is responsible for handling all aspects of the user authentication \
flow including but not limited to..."

### Bad (guessing)
"Built by the Platform team to support the Q3 2024 migration initiative."\
"""


async def draft_architectural_intent(
    context: PromptContext,
    llm: LLMProvider,
) -> str:
    """Draft the Architectural Intent section via one-shot LLM call.

    Uses PromptTemplate to build the user prompt (with truncation) from the
    repo context, paired with a focused system prompt that targets only the
    Architectural Intent section.

    Returns the raw LLM output string (Markdown prose, no heading wrapper).
    """
    template = PromptTemplate()
    _, user_prompt = template.render(context)

    response = await llm.generate(
        system=_ARCHITECTURAL_INTENT_SYSTEM,
        user=user_prompt,
    )
    return response.content
