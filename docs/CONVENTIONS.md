# Chronicler Conventions

## Document Naming

```
<ComponentID>.<SubCategory>.tech.md
```

Examples: `auth-service.api.tech.md`, `db-connector.util.tech.md`

## Storage Location

- `.chronicler/` directory at project root, OR
- Adjacent to source file for granular logic

## Hub-and-Spoke Model

- **Hub** (`.tech.md`): Metadata, Architectural Intent, Connectivity. Max ~1,500 words.
- **Spokes** (`.satellite.md`): Overflow sections (Operational Memory >50 entries, etc.)
- Satellite types: `.qa.tech.md`, `.audit.tech.md`, `.invariants.md`, `.logic_map.md`

## YAML Frontmatter Schema

Required fields for all `.tech.md` files:

```yaml
component_id: "string"
version: "semver"
owner_team: "team-id"
layer: "infrastructure|logic|api"
security_level: "low|medium|high|critical"
governance:
  verification_status: "ai_draft|human_verified|verified_in_ci"
  visibility: "internal|confidential|secret"
```

Key optional fields: `infrastructure`, `edges`, `contracts`, `slo_target`, `satellite_docs`

## Inter-Service Linking

URI pattern: `agent://<service-name>/<file-path>.tech.md`

## Implementation Phases

| Phase | Deliverable |
|-------|-------------|
| 1 | Orchestrator MVP (VCS Crawler, Harvester, AI Drafter, PR Engine) |
| 2 | Continuous Harvesting & Drift Detection |
| 3 | Mnemon Data Foundation (GraphQL Indexer) |
| 4 | Mnemon 3D Visualization |
| 5 | Enterprise Governance & Security (RBAC, Cost Engine, Audit) |
