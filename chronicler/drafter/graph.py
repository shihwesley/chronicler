"""Connectivity graph generator for .tech.md files.

Generates Mermaid `graph LR` diagrams from repo metadata and key files.
Uses basic parsing (import analysis, package.json deps) rather than LLM inference.
"""

from __future__ import annotations

import json
import re

from chronicler.vcs.models import FileNode, RepoMetadata

# Infrastructure patterns matched against Dockerfile content (case-insensitive)
_INFRA_PATTERNS: list[tuple[str, str, str, str]] = [
    # (regex_pattern, node_id, label, relationship)
    (r"postgres(?:ql)?", "postgres", "PostgreSQL", "reads/writes"),
    (r"redis", "redis", "Redis", "uses"),
    (r"mongo(?:db)?", "mongo", "MongoDB", "reads/writes"),
    (r"mysql|mariadb", "mysql", "MySQL", "reads/writes"),
    (r"rabbitmq|amqp", "rabbitmq", "RabbitMQ", "uses"),
    (r"kafka", "kafka", "Kafka", "uses"),
    (r"elasticsearch|elastic", "elasticsearch", "Elasticsearch", "reads/writes"),
]

# Max dependency nodes to include in the graph
_MAX_DEPS = 10


def _sanitize_node_id(name: str) -> str:
    """Convert a name to a valid Mermaid node ID (alphanumeric + hyphens)."""
    sanitized = re.sub(r"[^a-zA-Z0-9-]", "-", name)
    sanitized = re.sub(r"-+", "-", sanitized).strip("-")
    return sanitized.lower() or "component"


def _parse_python_deps(key_files: dict[str, str]) -> list[str]:
    """Extract Python dependency names from requirements.txt or pyproject.toml."""
    deps: list[str] = []

    # Try requirements.txt first
    for path in ("requirements.txt", "requirements/base.txt", "requirements/prod.txt"):
        content = key_files.get(path)
        if content:
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                # Strip version specifiers: package>=1.0 -> package
                pkg = re.split(r"[>=<!~;\[\s]", line)[0].strip()
                if pkg:
                    deps.append(pkg)
            break

    # Fallback to pyproject.toml
    if not deps:
        content = key_files.get("pyproject.toml")
        if content:
            # Match lines inside dependencies = [...] or [project.dependencies]
            in_deps = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped == "[project.dependencies]" or re.match(
                    r"^dependencies\s*=\s*\[", stripped
                ):
                    in_deps = True
                    # Handle inline: dependencies = ["pkg1", "pkg2"]
                    inline = re.findall(r'"([^"]+)"', stripped)
                    for dep_str in inline:
                        pkg = re.split(r"[>=<!~;\[\s]", dep_str)[0].strip()
                        if pkg:
                            deps.append(pkg)
                    continue
                if in_deps:
                    if stripped.startswith("]") or (
                        stripped.startswith("[") and not stripped.startswith('"')
                    ):
                        in_deps = False
                        continue
                    matches = re.findall(r'"([^"]+)"', stripped)
                    for dep_str in matches:
                        pkg = re.split(r"[>=<!~;\[\s]", dep_str)[0].strip()
                        if pkg:
                            deps.append(pkg)

    return deps


def _parse_node_deps(key_files: dict[str, str]) -> list[str]:
    """Extract Node.js production dependency names from package.json."""
    content = key_files.get("package.json")
    if not content:
        return []
    try:
        pkg = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []
    dependencies = pkg.get("dependencies", {})
    if isinstance(dependencies, dict):
        return list(dependencies.keys())
    return []


def _detect_infrastructure(
    key_files: dict[str, str], tree: list[FileNode]
) -> list[tuple[str, str, str]]:
    """Detect infrastructure services from Dockerfile and docker-compose.yml.

    Returns list of (node_id, label, relationship).
    """
    found: list[tuple[str, str, str]] = []
    seen_ids: set[str] = set()

    # Check Dockerfile
    dockerfile_content = key_files.get("Dockerfile", "")
    if dockerfile_content:
        lower = dockerfile_content.lower()
        for pattern, node_id, label, rel in _INFRA_PATTERNS:
            if node_id not in seen_ids and re.search(pattern, lower):
                found.append((node_id, label, rel))
                seen_ids.add(node_id)

    # Check docker-compose.yml for service names
    compose = key_files.get("docker-compose.yml") or key_files.get(
        "docker-compose.yaml"
    )
    if compose:
        # Simple YAML parsing: look for top-level service names under `services:`
        in_services = False
        for line in compose.splitlines():
            stripped = line.strip()
            if stripped == "services:":
                in_services = True
                continue
            if in_services:
                # Top-level keys under services are indented exactly one level
                if line and not line[0].isspace():
                    break  # Left the services block
                # Service name: indented, ends with colon, not deeply nested
                match = re.match(r"^  (\w[\w-]*):", line)
                if match:
                    svc = match.group(1).lower()
                    for pattern, node_id, label, rel in _INFRA_PATTERNS:
                        if node_id not in seen_ids and re.search(pattern, svc):
                            found.append((node_id, label, rel))
                            seen_ids.add(node_id)

    return found


def _humanize_label(name: str) -> str:
    """Convert a package name into a readable label."""
    return name.replace("-", " ").replace("_", " ").title()


def generate_connectivity_graph(
    metadata: RepoMetadata,
    key_files: dict[str, str],
    tree: list[FileNode],
) -> str:
    """Generate Mermaid connectivity graph from repo analysis.

    Returns valid Mermaid graph LR syntax string.
    """
    component_id = _sanitize_node_id(metadata.name)
    component_label = metadata.name

    lines: list[str] = ["graph LR"]
    lines.append(f"    {component_id}[{component_label}]")

    # Collect library dependencies
    deps: list[str] = []
    lang_keys = set(metadata.languages.keys())

    if "Python" in lang_keys:
        deps = _parse_python_deps(key_files)
    if not deps and lang_keys & {"JavaScript", "TypeScript"}:
        deps = _parse_node_deps(key_files)

    # Limit to top N deps (first N — listed order is typically importance order)
    for dep in deps[:_MAX_DEPS]:
        dep_id = _sanitize_node_id(dep)
        dep_label = _humanize_label(dep)
        lines.append(
            f"    {component_id} -->|depends_on| {dep_id}[{dep_label}]"
        )

    # Infrastructure nodes
    infra = _detect_infrastructure(key_files, tree)
    for node_id, label, rel in infra:
        lines.append(f"    {component_id} -->|{rel}| {node_id}[({label})]")

    return "\n".join(lines) + "\n"
