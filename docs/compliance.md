# Compliance Mapping

Sentinel Stack maps every layer of the pipeline to specific regulatory controls. Each audit log entry carries a `regulation_mappings` field that records which controls were satisfied by that request.

---

## Control ID Format

Control IDs follow this convention:

| Regulation | Format | Example |
|---|---|---|
| EU AI Act | `Article <N>` | `Article 14` |
| NIST AI RMF | `<FUNCTION>-<CATEGORY>.<SUBCATEGORY>` | `MANAGE-1.3` |
| HIPAA | `<Section>(<Subsection>)` | `164.308(a)(3)` |
| Colorado SB205 | `Section <N>-<N>-<N>(<L>)` | `Section 6-1-1702(c)` |

---

## Layer-to-Control Mapping

### Layer 1 — Ingestion

| Regulation | Control | Description |
|---|---|---|
| EU AI Act | Article 12 | Technical documentation and recordkeeping |
| NIST AI RMF | GOVERN-1.1 | Policies, processes, and procedures are in place |
| HIPAA | 164.312(b) | Audit controls — hardware, software, and procedural mechanisms |

**What this means in practice:** Every request that enters Sentinel generates an audit record. Layer 1 is the point at which that record begins — the request is tagged with a unique ID, the source is identified, and token estimates are generated. Together these satisfy basic documentation and audit trail requirements.

---

### Layer 2 — Routing

| Regulation | Control | Description |
|---|---|---|
| EU AI Act | Article 9 | Risk management system |
| NIST AI RMF | GOVERN-1.2 | Accountability structures are in place |
| NIST AI RMF | GOVERN-1.4 | Organizational teams are committed to policies |
| Colorado SB205 | Section 6-1-1702(b) | Governance program for high-risk AI systems |

**What this means in practice:** Layer 2 enforces which models an agent may use and whether budget thresholds have been exceeded. This constitutes a technical risk management control: agents are bounded by explicit organizational policies, and those bounds are enforced on every request.

---

### Layer 3 — Pre-call Enforcement

| Regulation | Control | Description |
|---|---|---|
| EU AI Act | Article 14 | Human oversight of high-risk AI systems |
| NIST AI RMF | MANAGE-1.3 | Responses to identified AI risks |
| HIPAA | 164.308(a)(3) | Workforce authorization and supervision |
| Colorado SB205 | Section 6-1-1702(c) | Ability to correct, update, or shut down AI systems |

**What this means in practice:** Layer 3 is the primary enforcement point. The kill switch is a direct implementation of Art. 14 human oversight requirements — it allows an operator (or the anomaly engine) to stop an agent before execution. Purpose binding and forbidden endpoint controls enforce workforce authorization policies. All checks run before the model is called.

---

### Layer 4 — Reasoning

| Regulation | Control | Description |
|---|---|---|
| EU AI Act | Article 13 | Transparency and provision of information to deployers |
| NIST AI RMF | MAP-1.1 | Context is established for AI risk assessment |

**What this means in practice:** Layer 4 records which model was used, what provider, how many tokens were consumed, and the final cost. This information appears in the audit log and satisfies transparency requirements — operators can see exactly what model executed any request.

---

### Layer 5 — Grounding

| Regulation | Control | Description |
|---|---|---|
| EU AI Act | Article 15 | Accuracy, robustness, and cybersecurity |
| NIST AI RMF | MEASURE-2.5 | Likelihood and magnitude of each AI risk are evaluated |
| Colorado SB205 | Section 6-1-1702(a) | Assessment of algorithmic discrimination risks |

**What this means in practice:** Layer 5 verifies that model responses are grounded in provided sources. Ungrounded responses indicate potential hallucination, which is both an accuracy risk (Art. 15) and a discrimination risk (SB205) if the hallucinated content concerns consequential decisions. Low-confidence responses are blocked and queued for human review.

---

### Layer 6 — Anomaly Detection

| Regulation | Control | Description |
|---|---|---|
| EU AI Act | Article 9 | Risk management system (ongoing monitoring) |
| NIST AI RMF | MEASURE-2.2 | Scientific methods are used to characterize AI risks |
| NIST AI RMF | MANAGE-2.2 | Mechanisms are in place to respond to AI risks |

**What this means in practice:** Layer 6 implements the ongoing monitoring component of a risk management system. The Welford online algorithm tracks behavioral baselines; z-score-based drift detection is a scientific measurement approach. Graduated automatic containment is the response mechanism. Together these satisfy the monitoring and response requirements of Art. 9, MEASURE-2.2, and MANAGE-2.2.

---

### Layer 7 — Compliance Output

| Regulation | Control | Description |
|---|---|---|
| EU AI Act | Article 11 | Technical documentation requirements |
| EU AI Act | Article 12 | Recordkeeping obligations |
| NIST AI RMF | GOVERN-6.1 | Policies address AI risks associated with third-party entities |
| HIPAA | 164.312(b) | Audit controls |

**What this means in practice:** Layer 7 writes the immutable audit record. The append-only PostgreSQL constraint (REVOKE UPDATE, DELETE) ensures that these records cannot be altered after the fact, satisfying the integrity requirements of Art. 11/12 and HIPAA 164.312(b). The GOVERN-6.1 control is satisfied by the audit record capturing which third-party provider and model was used.

---

### Kill Switch Events

Kill switch state transitions generate their own audit entries with additional control mappings:

| Regulation | Control |
|---|---|
| EU AI Act | Article 14 |
| NIST AI RMF | MANAGE-1.3 |
| NIST AI RMF | MANAGE-2.4 |

---

### Human Review Events (Layer 5 escalations)

When Layer 5 queues a response for human review:

| Regulation | Control |
|---|---|
| EU AI Act | Article 14 |
| NIST AI RMF | GOVERN-5.1 |

---

## Evidence Package Generation

The compliance package generator (`POST /api/compliance/generate`) queries the audit log for a time range and produces an evidence index: for each control ID, it lists the audit entry IDs that demonstrate the control was exercised.

### Gap Analysis

A control is considered covered if:
- At least one audit log entry exists in the time range
- The entry's `regulation_mappings` includes the control ID
- The entry's `status` is not `"error"`

A gap is reported when zero qualifying entries exist for a required control. The gap description names the layer responsible for that control and describes what would need to be active to produce evidence.

**Example gap:**
```json
{
  "control_id": "NIST MEASURE-2.5",
  "regulation": "nist_ai_rmf",
  "description": "No MEASURE-2.5 evidence in range. This control is satisfied by grounding (Layer 5) events. Ensure Layer 5 is active and processing requests."
}
```

---

## Supported Regulations

| Regulation | Identifier in API | Articles / Sections |
|---|---|---|
| EU Artificial Intelligence Act | `eu_ai_act` | Articles 9, 11, 12, 13, 14, 15 |
| NIST AI Risk Management Framework | `nist_ai_rmf` | GOVERN-1.1/1.2/1.4/5.1/6.1, MAP-1.1, MEASURE-2.2/2.5, MANAGE-1.3/2.2/2.4 |
| Health Insurance Portability and Accountability Act | `hipaa` | 164.308(a)(3), 164.312(b) |
| Colorado AI Act (SB205) | `colorado_sb205` | Sections 6-1-1702(a)(b)(c) |
