# Compliance Mapper Reference

## JSONB field format (audit_log.regulation_mappings)
{
  "EU_AI_ACT": ["Article 14", "Article 12"],
  "NIST_AI_RMF": ["GOVERN-1.1", "MANAGE-2.2"],
  "COLORADO_SB205": ["Section 6-1-1702"],
  "HIPAA": ["164.312(b)"]
}

## Layer → control mapping (canonical)
Layer 1 (Ingestion):   EU Art.12, NIST GOVERN-1.1, HIPAA 164.312(b)
Layer 2 (Routing):     EU Art.9,  NIST GOVERN-1.2, NIST GOVERN-1.4, CO 6-1-1702(b)
Layer 3 (Enforcement): EU Art.14, NIST MANAGE-1.3, HIPAA 164.308(a)(3), CO 6-1-1702(c)
Layer 4 (Reasoning):   EU Art.13, NIST MAP-1.1
Layer 5 (Grounding):   EU Art.15, NIST MEASURE-2.5, CO 6-1-1702(a)
Layer 6 (Anomaly):     EU Art.9,  NIST MEASURE-2.2, NIST MANAGE-2.2
Layer 7 (Compliance):  EU Art.11, EU Art.12, NIST GOVERN-6.1, HIPAA 164.312(b)

## Gap analysis logic
A control has evidence if: at least one audit_log entry in the time range
references that control_id in regulation_mappings AND status != 'error'.
A control has a gap if: zero qualifying entries exist for that control in range.
Gap description must specify: what kind of event would satisfy it and which layer produces it.

## Control ID format rules
EU_AI_ACT:      "Article {N}" — no abbreviations
NIST_AI_RMF:    "{FUNCTION}-{category}.{subcategory}" e.g. "GOVERN-1.1"
COLORADO_SB205: "Section {statute}" e.g. "Section 6-1-1702"
HIPAA:          "{part}.{section}({paragraph})" e.g. "164.312(b)"
