# Code Review Phase 6 — Fix Log

Reviewed: 23 files, 2,262 lines added
Fixed: 18 issues across 10 files (P0: 3, P1: 6, P2: 6, P3: 3)

All 328 tests passing post-fix, 0 regressions.

---

## P0 — Critical

### 1. Cypher injection in GraphQL resolvers

**Files:** `graphql_server.py`, `neo4j_graph.py`, `graph.py` (protocol)

All Query methods interpolated user input via f-strings (`f"MATCH (n:Component {{id: '{id}'}})""`). An attacker could inject arbitrary Cypher through the GraphQL API.

**Fix:** Added `parameters` kwarg to `GraphPlugin.query()` protocol and `Neo4jGraph.query()`. Rewrote all 4 GraphQL resolvers to use `$param` syntax with parameter dicts. The Neo4j driver handles escaping.

### 2. RBAC bypass for unknown actions

**File:** `rbac.py:68`

`_ACTION_LEVELS.get(permission.action, 0)` returned 0 for unregistered actions, so any role (even viewer at level 1) passed the check. A plugin-added action not in the dict was open to everyone.

**Fix:** Changed default to `None`. Unknown actions now return `False` (deny by default).

### 3. Unbounded DLQ drain in SQS

**File:** `sqs.py:128-147`

`dead_letters()` looped `while True` pulling all messages into memory. A DLQ with 100k messages would OOM.

**Fix:** Added `max_results` parameter (default 1000) with batch-size clamping.

---

## P1 — High

### 4. Bare `except Exception` in PR Engine

**File:** `engine.py:63-69, 131-137`

Both `create_doc_pr()` and `batch_prs()` caught all exceptions when checking file existence, silently falling back to `create_file()`. This swallowed auth failures, rate limits, and network errors.

**Fix:** Narrowed to `UnknownObjectException` (PyGithub's 404). Other exceptions now propagate.

### 5. ServiceBus `str(msg)` for payload deserialization

**File:** `servicebus.py:49`

`json.loads(str(msg))` assumed `__str__` returns the message body. Azure SDK's `str(ServiceBusReceivedMessage)` returns a debug representation.

**Fix:** Changed to `json.loads(str(msg.body))`.

### 6. Nack reason discarded in all queue implementations

**Files:** `sqs.py:115`, `pubsub.py:90`, `servicebus.py:82`

All three `nack(job_id, reason)` implementations ignored the reason parameter entirely. Error context was lost.

**Fix:** Added `logger.warning("nack job=%s reason=%s", job_id, reason)` to all three.

### 7. No logging anywhere in chronicler-enterprise

The entire enterprise package had zero `logging.getLogger()` calls. Core modules all set up loggers; enterprise silently swallowed failures.

**Fix:** Added `logger = logging.getLogger(__name__)` to all 6 enterprise modules: `sqs.py`, `pubsub.py`, `servicebus.py`, `rbac.py`, `neo4j_graph.py`, `graphql_server.py`, `engine.py`.

### 8. `neighbors()` depth f-string injection

**File:** `neo4j_graph.py:60`

The `depth` parameter was interpolated into Cypher without validation. A very large value could cause graph traversal explosion (DoS).

**Fix:** Added `isinstance(depth, int)` check and clamped to max 10.

### 9. N+1 query in `blast_radius`

**File:** `graphql_server.py:87-103`

Called `neighbors()` once per depth level in a loop, generating `depth` separate Neo4j round-trips.

**Fix:** Replaced with single Cypher query using `min(length(path))` to return all affected nodes with their hop distance in one call.

---

## P2 — Medium

### 10. Plugin loader returns class, not instance

**File:** `loader.py:96-112`

`load_queue()` etc. were typed as returning `QueuePlugin` (instance) but actually returned the class object from `ep.load()`. Callers trying `queue.enqueue(job)` would get `TypeError: missing 'self'`.

**Fix:** Changed return types to `type[QueuePlugin]`, `type[GraphPlugin]`, etc.

### 11. Duplicated Job serialization across 3 queue implementations

**Files:** `sqs.py`, `pubsub.py`, `servicebus.py`

All three repeated the same 6-field `job_to_attrs` / `attrs_to_job` logic (~40 lines duplicated).

**Fix:** Extracted to `cloud_queue/_serialization.py` with shared `job_to_attrs()` and `attrs_to_job()`. Each queue adapter now handles only its transport-specific wrapping (SQS `DataType`/`StringValue`, PubSub flat attrs, ServiceBus `application_properties`).

### 12. `SQSQueue.MAX_ATTEMPTS = 3` is dead code

**File:** `sqs.py:22`

Declared but never referenced anywhere.

**Fix:** Removed.

### 13. `ChroniclerRBAC._load_config()` raises `NotImplementedError`

**File:** `rbac.py:43-48, 126-127`

Constructor accepted `config_path`, then crashed at runtime.

**Fix:** Removed the `config_path` parameter and the `_load_config` method.

### 14. No resource cleanup on ServiceBus/PubSub

**Files:** `servicebus.py`, `pubsub.py`

These held long-lived client connections but had no `close()` method. `Neo4jGraph` already had one.

**Fix:** Added `close()` to both `ServiceBusQueue` (closes sender, receiver, client) and `PubSubQueue` (closes publisher transport and subscriber).

### 15. `_SCOPE_LEVELS` defined but unused

**File:** `rbac.py:30-33`

Identical to `_SCOPE_ACCESS` and never referenced.

**Fix:** Removed.

---

## P3 — Low

### 16. `revoke()` creates empty dict entries

**File:** `rbac.py:90-91`

Revoking from a non-existent user created `{user_id: []}`. Minor memory leak over time.

**Fix:** Early return when user not in `_permissions`.

### 17. Hardcoded `host="0.0.0.0"` in GraphQLServer

**File:** `graphql_server.py:109`

Bound to all interfaces by default.

**Fix:** Changed default to `"127.0.0.1"` (local-only).

### 18. Dependencies lack upper bounds

**File:** `pyproject.toml:10-13`

`pydantic>=2.0.0` without ceiling. A major version bump could break things.

**Fix:** Changed to `pydantic>=2.0.0,<3.0.0`.

---

## Test updates

Three tests required updates to match the new behavior:

- `test_query_passthrough`: Updated assertion to expect `parameters={}` kwarg
- `_FakeGraph.query`: Added optional `parameters` param for protocol compliance
- `test_dequeue_returns_job` (ServiceBus): Changed `raw_msg.__str__` mock to `raw_msg.body`

## Files modified

| File | Issues fixed |
|---|---|
| `neo4j_graph.py` | #1, #7, #8 |
| `graphql_server.py` | #1, #7, #9, #17 |
| `graph.py` (protocol) | #1 |
| `rbac.py` | #2, #7, #13, #15, #16 |
| `sqs.py` | #3, #6, #7, #11, #12 |
| `pubsub.py` | #6, #7, #11, #14 |
| `servicebus.py` | #5, #6, #7, #11, #14 |
| `engine.py` | #4, #7 |
| `loader.py` | #10 |
| `pyproject.toml` | #18 |
| `_serialization.py` (new) | #11 |
