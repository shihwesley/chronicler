# AI Agent Contribution & Behavior Guidelines

This document defines the "Rules of Engagement" for any autonomous or semi-autonomous AI agent operating within this enterprise codebase.

## 1. Pre-Implementation Protocol

Before writing any code, an agent MUST:

1. **Read the Chronicler Hub:** Read the `.tech.md` for the target component.
2. **Consult Mnemon:** Check the 3D Graph for "Blast Radius" warnings.
3. **Read Invariants:** Explicitly verify that the proposed change does not violate `.invariants.md`.

## 2. Coding Standards

* **Format:** All code must strictly follow the enterprise style guide (linked here).
* **Side-Effects:** Any new side-effect (API call, DB write) must be documented as an `edge` in the Chronicler YAML.
* **Observability:** Every logic fork must have appropriate tracing and logging that matches the `X-Trace-ID` standard.

## 3. Documentation "Tithe" (The Harvest)

Agents are responsible for their own documentation maintenance. A Code PR is considered "Incomplete" by Chronicler unless:

1. **YAML is Updated:** New dependencies/contracts are added to the YAML frontmatter.
2. **Audit Log Entry:** A technical summary of the fix/feature is added to the "Operational Memory."
3. **QA-Blueprint Update:** If logic changes, the blueprint for testing must be updated.

## 4. Safety Guardrails

* **No Stealth Work:** Agents may not modify files outside their assigned scope (Blast Radius).
* **Explicit Rollbacks:** Every major change must include a "Technical Mitigation" strategy in the doc.
* **Hallucination Check:** If an agent finds a discrepancy between the Code and the Chronicler Doc, it MUST flag it immediately using `[FLAG:OUTDATED]` rather than making assumptions.

## 5. Conflict Resolution

If multiple agents (or a human and an agent) clash on a technical ledger, the **ADR (Architecture Decision Record)** is the tie-breaker.
