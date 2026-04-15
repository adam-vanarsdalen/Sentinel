# References (Primary Sources)

These references ground SentinelLaw’s pilot design choices and documentation.

## OWASP (GenAI / LLM Security)
- OWASP Top 10 for Large Language Model Applications (LLM Top 10) — threat categories and mitigations for LLM apps (project home / latest).  
  URL: https://genai.owasp.org/llm-top-10/
- OWASP LLM01:2025 Prompt Injection — prompt injection risk description + mitigations within the OWASP LLM Top 10 taxonomy.  
  URL: https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- OWASP Top 10 for LLM Applications 2025 — latest curated list and downloadable resource.  
  URL: https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/
- OWASP Foundation project page — background and category list (LLM Top 10 v1.1).  
  URL: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- OWASP Cheat Sheet Series — “LLM Prompt Injection Prevention” (practical mitigations and validation patterns).  
  URL: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html
- OWASP Community — “Prompt Injection” overview (general attack pattern description).  
  URL: https://owasp.org/www-community/attacks/PromptInjection

## NIST (Risk Governance + Log Management)
- NIST AI RMF 1.0 publication page (NIST AI 100-1) — authoritative AI risk governance framework + download links.  
  URL: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10
- NIST AI RMF 1.0 PDF (NIST AI 100-1) — stable artifact hosted on `nvlpubs.nist.gov`.  
  URL: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf
- NIST AI RMF 1.0 PDF download (publication artifact) — stable PDF for governance references and citations.  
  URL: https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=936225
- NIST SP 800-92 (Guide to Computer Security Log Management) — log generation, collection, retention, and analysis practices.  
  URL: https://csrc.nist.gov/pubs/sp/800/92/final
- NIST SP 800-92 DOI landing page — stable identifier for citations.  
  URL: https://doi.org/10.6028/NIST.SP.800-92
- NIST SP 800-92 Rev. 1 (2nd Public Draft) — updated log management guidance (draft) for modern environments.  
  URL: https://csrc.nist.gov/pubs/sp/800/92/r1/2pd

## Legal Ethics, Confidentiality, and Responsible AI Use
- ABA Model Rules of Professional Conduct — Rule 1.1 (Competence).  
  URL: https://www.americanbar.org/groups/professional_responsibility/publications/model_rules_of_professional_conduct/rule_1_1_competence/
- ABA Model Rules of Professional Conduct — Rule 1.1 (Competence) Comment (includes Comment [8] on “benefits and risks associated with relevant technology”).  
  URL: https://www.americanbar.org/groups/professional_responsibility/publications/model_rules_of_professional_conduct/rule_1_1_competence/comment_on_rule_1_1/
- ABA Model Rules of Professional Conduct — Rule 1.6 (Confidentiality of Information).  
  URL: https://www.americanbar.org/groups/professional_responsibility/publications/model_rules_of_professional_conduct/rule_1_6_confidentiality_of_information/
- ABA Model Rules of Professional Conduct — Rule 1.6 Comment (includes factors for “reasonable efforts” to prevent unauthorized access/disclosure).  
  URL: https://www.americanbar.org/groups/professional_responsibility/publications/model_rules_of_professional_conduct/rule_1_6_confidentiality_of_information/comment_on_rule_1_6/
- ABA Formal Opinion 512 (2024) — “Generative Artificial Intelligence Tools” (duties of competence, confidentiality, supervision, communication).  
  URL: https://www.americanbar.org/content/dam/aba/administrative/professional_responsibility/formal-opinion-512.pdf
- The State Bar of California — Practical Guidance for the Use of Generative Artificial Intelligence in the Practice of Law (2024).  
  URL: https://www.calbar.ca.gov/Portals/0/documents/ethics/Practical-Guidance-for-the-Use-of-Generative-AI-in-the-Practice-of-Law.pdf
- New Jersey State Bar Association — “Guidelines for Using Artificial Intelligence Tools” (2024).  
  URL: https://njsba.com/wp-content/uploads/2024/04/Guidelines_for_Using_Artificial_Intelligence_Tools.pdf
- New York City Bar Association — “The Ethical Use of Artificial Intelligence in the Practice of Law” (2024) (survey and synthesis of bar guidance).  
  URL: https://www.nycbar.org/reports/the-ethical-use-of-artificial-intelligence-in-the-practice-of-law/

## Legal “Matter” Concepts (Law Firm Terminology)
- Clio Help Center — Matter Numbering Scheme (updated Apr 22, 2025): describes “matter numbers” as firm-configurable identifiers that can incorporate client name, description, year, etc.  
  URL: https://help.clio.com/hc/en-us/articles/9286019831707-Matter-Numbering-Scheme
- LexisNexis CounselLink Support — “Adding a Law Firm Matter ID” (support article): describes a law-firm matter ID as a unique identifier assigned by time/billing software and required for certain workflows.  
  URL: https://supportcenter.lexisnexis.com/app/answers/answer_view/a_id/1087377/~/adding-a-law-firm-matter-id-to-a-matter-on-counsellink

## Multi-tenant Isolation & Least Privilege (Platform Admin)
- OWASP Cloud Tenant Isolation — practical guidance focused on preventing cross-tenant vulnerabilities in SaaS/PaaS systems.  
  URL: https://owasp.org/www-project-cloud-tenant-isolation/
- AWS Whitepaper (PDF): SaaS Tenant Isolation Strategies — overview of isolation models (silo/pool/bridge) and tradeoffs.  
  URL: https://d1.awsstatic.com/whitepapers/saas-tenant-isolation-strategies.pdf
- Microsoft Azure Architecture Center: Multitenant compute approaches — discusses isolation choices and warns about data leakage in shared state (e.g., caches).  
  URL: https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/approaches/compute
- NIST Glossary: Least Privilege — definition and principle of granting only minimum necessary access.  
  URL: https://csrc.nist.gov/glossary/term/least_privilege

## HL7 FHIR (Legacy / Optional Audit Export Mapping)
- HL7 FHIR AuditEvent resource (build) — canonical, up-to-date AuditEvent definition and field descriptions.  
  URL: https://build.fhir.org/auditevent.html
- HL7 FHIR R4 AuditEvent resource — R4 snapshot for compatibility references.  
  URL: https://www.hl7.org/fhir/R4/auditevent.html

## Enterprise Dashboard / Admin UX Patterns
- Atlassian Design System — navigation patterns and guidelines for enterprise admin applications.  
  URL: https://atlassian.design/components/navigation/
- Material Design — data table component guidance (sorting, filtering, density, selection).  
  URL: https://m3.material.io/components/data-tables/overview
- Nielsen Norman Group — dashboard design guidance and common usability considerations for presenting metrics.  
  URL: https://www.nngroup.com/articles/dashboard-design/

## Log / Audit Viewer UX Patterns
- Elastic Kibana — Discover app for log exploration (search, filters, time range, saved views).  
  URL: https://www.elastic.co/guide/en/kibana/current/discover.html
- Google Cloud Logs Explorer — log filtering, queries, and export/download workflows (industry reference UI).  
  URL: https://cloud.google.com/logging/docs/view/logs-explorer-interface

## Auth / Session UX & Security Patterns
- OWASP Session Management Cheat Sheet — guidance for cookie attributes (`HttpOnly`, `Secure`, `SameSite`) and session handling.  
  URL: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- Atlassian Design System — message patterns for user-facing errors, warnings, and confirmations (incl. authentication messages).  
  URL: https://atlassian.design/patterns/messages/
