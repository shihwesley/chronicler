# Enterprise Data Dictionary (EDD): [Domain/Cluster Name]

This document ensures that all humans and AI agents use identical terminology when documenting or modifying code within the `[Cluster Name]` domain.

## 1. Domain Entities

| Entity Name | Canonical Definition | Primary Keys / IDs | Owner Team |
| :--- | :--- | :--- | :--- |
| `UserAccount` | The authenticated identity for a billing customer. | `user_id` (UUID) | Identity Team |
| `Transaction` | A single record of financial exchange. | `tx_id` (CUID) | Billing Team |

## 2. Common Attributes & Types

| Attribute Name | Data Type | Constraint / Regex | Global Meaning |
| :--- | :--- | :--- | :--- |
| `status` | Enum | `[PENDING, ACTIVE, CLOSED]` | The business lifecycle state of the entity. |
| `created_at` | ISO-8601 | `YYYY-MM-DDTHH:MM:SSZ` | Universal UTC timestamp of record creation. |

## 3. Reserved Keywords

List of terms that have specialized meaning within this enterprise:

* **"Hard-Fail":** A failure that triggers an immediate rollback and incident alert.
* **"Soft-Fail":** A transient error that should be retried 3 times before escalation.

## 4. Relationship Semantics

Definitions of what specific Chronicler "Edges" mean in this domain:

* `CONSUMES`: This application triggers logic based on an event from X.
* `OWNS`: This application is the *exclusive* writer for data entity Y.

## 5. Governance

* **Update Frequency:** Quarterly review by Domain Architects.
* **AI Duty:** If an AI agent introduces a new technical term, it MUST be proposed via an ADR and added here.
