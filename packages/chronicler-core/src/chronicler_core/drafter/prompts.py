"""Prompt templates for .tech.md generation."""

from __future__ import annotations

from chronicler_core.drafter.models import PromptContext, TruncationConfig

SYSTEM_PROMPT = """\
You are Chronicler, an enterprise technical documentation generator. Your task is to create a `.tech.md` file that serves as a "Living Technical Ledger" for the given codebase.

## Output Format

Generate a complete Markdown document with:
1. **YAML Frontmatter** (required fields below)
2. **Architectural Intent** section
3. **Connectivity Graph** section (Mermaid diagram)

## YAML Schema (REQUIRED)

```yaml
---
component_id: "<repo-name>"
version: "0.1.0"
owner_team: "unknown"
layer: "infrastructure|logic|api"
security_level: "low|medium|high|critical"
governance:
  business_impact: null
  verification_status: "ai_draft"
  visibility: "internal"
edges: []
---
```

## Writing Rules

1. **Strictly technical** - No marketing language, no fluff
2. **Infer layer from structure:**
   - `api/`, `routes/`, `controllers/` -> layer: api
   - `services/`, `core/`, `lib/` -> layer: logic
   - `infra/`, `terraform/`, `deploy/` -> layer: infrastructure
3. **Connectivity Graph:** Show dependencies as Mermaid `graph LR`
4. **Unknown values:** Use "unknown" rather than guessing
5. **Max length:** ~1000 words for hub document

## Section Templates

### Architectural Intent
- What this component does (1-2 sentences)
- Why it exists (business context if inferable)
- Key responsibilities (bullet list)

### Connectivity Graph
```mermaid
graph LR
    ComponentName --> Dependency1
    ComponentName --> Dependency2
    ExternalService -->|consumes| ComponentName
```

## AVOID These Patterns

### Bad: Marketing language
- "This cutting-edge microservice revolutionizes authentication..."
+ "Handles user authentication via JWT tokens."

### Bad: Guessing unknown values
- owner_team: "platform-team"
+ owner_team: "unknown"

### Bad: Verbose descriptions
- "This service is responsible for handling all aspects of user authentication..."
+ "Handles user auth: login, logout, password reset, session management."

### Bad: Empty/placeholder Mermaid
- graph LR A --> B
+ graph LR auth-service --> postgres[(PostgreSQL)]

### Bad: Wrong verification_status
- verification_status: "human_verified"
+ verification_status: "ai_draft"\
"""

USER_PROMPT_TEMPLATE = """\
Generate a .tech.md document for the following repository:

## Repository Info
- **Name:** {repo_name}
- **Default Branch:** {default_branch}\
"""

_OPTIONAL_SECTIONS: list[tuple[str, str, str]] = [
    ("description", "- **Description:** {value}", ""),
    ("languages", "- **Languages:** {value}", ""),
    ("topics", "- **Topics:** {value}", ""),
    ("file_tree", "\n## File Tree\n```\n{value}\n```", ""),
    ("readme_content", "\n## README\n{value}", ""),
    ("package_json", "\n## Dependencies (package.json)\n```json\n{value}\n```", ""),
    ("dockerfile", "\n## Dockerfile\n```dockerfile\n{value}\n```", ""),
    ("dependencies_list", "\n## Dependencies\n{value}", ""),
    ("converted_docs_summary", "\n## Existing Documentation\n{value}", ""),
]


class PromptTemplate:
    """Renders system/user prompts from a PromptContext with truncation."""

    def __init__(self, truncation: TruncationConfig | None = None) -> None:
        self.truncation = truncation or TruncationConfig()

    def render(self, context: PromptContext) -> tuple[str, str]:
        """Render system and user prompts from context.

        Returns (system_prompt, user_prompt) tuple. Truncation is applied
        during render — the context object is not mutated.
        """
        truncated = self._apply_truncation(context)
        user_prompt = self._build_user_prompt(truncated)
        return SYSTEM_PROMPT, user_prompt

    def _apply_truncation(self, context: PromptContext) -> PromptContext:
        """Return a copy of context with fields truncated per config."""
        cfg = self.truncation
        updates: dict[str, str | None] = {}

        if context.readme_content and len(context.readme_content) > cfg.max_readme_chars:
            updates["readme_content"] = context.readme_content[: cfg.max_readme_chars] + "\n... (truncated)"

        if context.dockerfile and len(context.dockerfile) > cfg.max_dockerfile_chars:
            updates["dockerfile"] = context.dockerfile[: cfg.max_dockerfile_chars] + "\n... (truncated)"

        if context.description and len(context.description) > cfg.max_description_chars:
            updates["description"] = context.description[: cfg.max_description_chars] + "..."

        if context.file_tree:
            lines = context.file_tree.splitlines()
            if len(lines) > cfg.max_file_tree_files:
                updates["file_tree"] = (
                    "\n".join(lines[: cfg.max_file_tree_files])
                    + f"\n... ({len(lines) - cfg.max_file_tree_files} more files)"
                )

        if updates:
            return context.model_copy(update=updates)
        return context

    @staticmethod
    def _build_user_prompt(context: PromptContext) -> str:
        """Assemble user prompt, omitting empty optional sections."""
        parts = [
            USER_PROMPT_TEMPLATE.format(
                repo_name=context.repo_name,
                default_branch=context.default_branch,
            )
        ]

        for field_name, template, _default in _OPTIONAL_SECTIONS:
            value = getattr(context, field_name, None)
            if value:
                parts.append(template.format(value=value))

        return "\n".join(parts)
