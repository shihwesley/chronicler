# Technical Specification: Chronicler System

## 1. Document Architecture

Technical documents MUST follow a deterministic naming pattern to allow for agentic "Zero-Shot" identification:

* **Pattern:** `<ComponentID>.<SubCategory>.tech.md`
  * Example: `auth-service.api.tech.md` (for service-level)
  * Example: `db-connector.util.tech.md` (for file-level logic)
* **Storage:** Stored within a `.chronicler/` directory at the project root or adjacent to the source file for granular logic.

## 2. Metadata Schema (YAML Frontmatter)

Each document MUST start with a YAML block:

```yaml
---
component_id: "string"
version: "semver"
owner_team: "team-id"
layer: "infrastructure|logic|api"
infrastructure:
  provider: "aws|gcp|azure|on-prem"
  region: "string"
  hosting: "kubernetes|lambda|ec2|appserver"
  database:
    type: "postgres|mongodb|redis|etc"
    instance_id: "string"
edges:
  - target: "uri://component-id"
    relationship: "CONSUMES|PRODUCES|DEPENDS_ON|TRIGGERS"
    transport: "grpc|http|kafka|amqp"
visual_cluster: "string" # For 3D Graph Grouping
vcs_context:
  provider: "github|azure|gitlab|bitbucket"
  org: "string"
  project: "string"
contracts:
  inbound: ["uri://contract-id"]
  outbound: ["uri://contract-id"]
security_level: "low|medium|high|critical"
governance:
  business_impact: "P0|P1|P2|P3" # System criticality
  cost_center: "string"          # Cloud budget ID
  pii_handled: boolean           # Privacy compliance
  lifecycle_status: "active|deprecated|eol"
  verification_status: "ai_draft|human_verified|verified_in_ci"
  visibility: "internal|confidential|secret"
last_harvest: "datetime"
slo_target: "0.999" # 99.9% availability requirement
monitoring_link: "uri" # Deep link to Datadog/NewRelic dashboard
satellite_docs: # Links to deep-dive files to prevent main-doc bloat
  audit_log: "string"
  qa_blueprint: "string"
  infra_manifest: "string"
  invariants: "string"   # Critical architectural rules
  logic_map: "string"     # Data flow and side-effects
---
```

## 3. Section Specifications

### 3.1 Architectural Intent

* Definition of the core algorithm or service responsibility.
* State machine definitions (if applicable).
* Memory and performance constraints.

### 3.2 Connectivity Graph

* Uses **Mermaid.js** for visualization.
* Must define side-effects (e.g., Cache invalidation, Database writes).
* Links to external documentation via standardized `docs://` OR Git-relative paths.

### 3.3 Operational Memory (The "Audit Log")

* Format: Data-indexed list of failures.
* Schema: `[DATE] | [FAILURE_TYPE] | [MITIGATION_STEP] | [LINK_TO_PR]`
* Objective: Provide context to future AI agents on what NOT to do.

### 3.4 Deployment & Infrastructure Mapping

* **Logical vs. Physical:** Maps the application components to their physical cloud resources.
* **Resource Links:** Links to Terraform, Pulumi, or K8s manifests defining the infrastructure.
* **Scaling Policies:** Documentation of auto-scaling triggers and instance limits.

### 3.5 QA Blueprints

* **Definition:** Structured instructions that allow an AI Agent to generate test code.
* **Format:**

    ```markdown
    #### QA-BLUEPRINT-v1
    - Setup: `docker-compose up -d redis`
    - Entry Point: `App.init()`
    - Mock Boundary: `ServiceB.client`
    - Assertion: `Response.status == 200`
    ```

### 3.6 Discovery & GraphQL Interface (The "Knowledge Graph")

* **Centralized Indexer:** A service that crawls all enterprise repositories to parse `.tech.md` files.
* **GraphQL Queryable:** Both humans and AI agents interact with the graph via GraphQL.
  * Example Query: `findSystems { affectedBy(failedNode: "database-a") { tech_doc_url } }`
* **3D Visualization Metadata:** The `visual_cluster` and `relationship` tags are used to position nodes in a 3D space for intuitive navigation.

### 3.7 Business Impact & Governance (Executive View)

* **SLO/SLA Tracking:** Links the "Technical Intent" of the code to its "Operational Reality." If the code is documented to handle 10k requests/sec but the dashboard shows failure at 5k, the document is flagged as "Inaccurate."
* **Incident Runbook:** A "Strictly Technical" list of steps to take if this component fails (Primary escalation human + AI failover).
* **Tech Debt Score:** A weighted metric (0-100) calculated by Chronicler:
* **Drift Factor:** Time since last harvest vs. code change frequency.
* **Complexity Factor:** Number of cross-application "Edges."
* **Reliability Factor:** Frequency of entries in the "Operational Memory" (Audit Log).

### 3.8 Document Composition (Hub-and-Spoke Model)

To prevent bloat in enterprise-scale applications:

* **The Hub (`.tech.md`):** Contains Metadata, Architectural Intent, and Connectivity. Max suggested length: 1,500 words.
* **The Spokes (`.satellite.md`):** If a section (e.g., *Operational Memory*) exceeds 50 entries or 1,000 words, it MUST be moved to a satellite file linked in the YAML.
* **Lazy Discovery:** AI agents recognize "Satellite Links" and only fetch the specific file relevant to their task (e.g., a "QA Agent" only fetches the `.qa.tech.md` spoke).

### 3.9 Trust & Accuracy Feedback Loop

* **Correction Trigger:** If an engineer or AI agent discovers an inaccuracy, they can header a block with `[FLAG:OUTDATED]`—this triggers a priority re-harvest.
* **CI Validation:** Automated scripts that check if the documented gRPC/API contracts match the actual code implementation (using Reflection/OpenAPI export).

### 3.10 Visualization (Mnemon Platform)

* **Engine:** Mnemon consumes the GraphQL output from the Chronicler Indexer to render a persistent 3D graph.
* **Navigation:** Nodes are positioned using `visual_cluster` metadata and connected via `edges` defined in the CSS-like relationship schema.

## 4. Chronicler Workflow (Lifecycle)

### 4.1 Implementation: The "Orchestrator" Model

To scale across an enterprise with pre-existing legacy code, Chronicler operates as a centralized **Service**, not just a local tool.

1. **Discovery (The Crawl):** The Orchestrator connects to enterprise VCS APIs (GitHub/Azure). It identifies all repositories and their primary languages/frameworks.
2. **Bootstrapping (The AI Surge):**
    * **Metadata Harvesting:** Automatically extracts info from `package.json`, `Dockerfiles`, and `TF` files to populate YAML.
    * **Contextual Generation:** LLM generates a baseline `.tech.md` for major services based on folder structure and existing READMEs.
3. **Local Injection:** Once the baseline is generated, the Orchestrator opens a "Documentation Initialized" PR in the target repository, introducing the `.chronicler/` folder.
4. **Continuous Maintenance:**
    * **CI/CD Hook:** Injects a validation step into the repo's pipeline.
    * **PR Harvesting:** On every merge, the agent scans the diff to update the *Operational Memory* and *Tech Debt Score*.

5. **Creation:** Triggered on repository initialization.
6. **Harvesting:** Triggered on PR Merge. Agent scans diffs and comments for design decisions or error fixes.
7. **Validation:** CI/CD step where Chronicler checks if `.tech.md` is updated when source code changes (Technical Drift detection).
8. **Retrieval:** AI Agents use the `read_tech_doc` tool during planning phases.

## 5. Inter-Application Linking

* References to other services MUST follow a deterministic URI: `agent://<service-name>/<file-path>.tech.md`.
* This allows a "Global Knowledge Graph" to be built by scanning all repositories in the enterprise.

## 6. Security & Privacy

* Documents shall not contain PII or secrets.
* `security_level` tag determines if the AI Agent can share context with external models (e.g., public LLMs).
