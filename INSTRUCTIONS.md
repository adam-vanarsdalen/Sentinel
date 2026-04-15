# SentinelLaw AI Governance Dashboard — End User Instructions

## Introduction — Understand what SentinelLaw is and what you can do here

### What is SentinelLaw?
SentinelLaw is a governance dashboard for AI tools used in legal environments. It helps your firm use AI more safely by tracking usage, spotting risks, and keeping an audit trail.

### Why you would use this guide
Use this guide when you need to review AI usage, investigate a concern, export records for an audit, or update rules that control how AI requests are handled.

### What you can accomplish by following these instructions
You can:
- Sign in and choose the right firm.
- View activity and risk metrics on the dashboard.
- Search and export the AI activity log (audit trail).
- Create and revoke API keys (if you are allowed).
- Configure firm-owned provider credentials and defaults (if you are allowed).
- Configure governance alerts and send test notifications (if you are allowed).
- Review, test, and publish Firm AI Rules.
- Run Safety & Consistency Tests and compare results over time.
- Manage basic settings and users (if you are allowed).

[Screenshot: Home / Dashboard] Show the left navigation, top bar, and key metric cards.

---

## Getting Started — Log in and access the right firm

### Why this matters
Logging in confirms who you are. Choosing the correct firm ensures you only see the data for the right organization.

### Prerequisites
- Receive your SentinelLaw web link from your organization.
- Receive your SentinelLaw email and password from your administrator.
- Use a modern browser (Chrome, Edge, or Firefox recommended).

### Log in to SentinelLaw
[Screenshot: Login page] Show the “Email” field, “Password” field, and “Sign in” button.

1) Open the SentinelLaw login page in your browser.
2) Enter your email address in the field labeled “Email.”
3) Enter your password in the field labeled “Password.”
4) Click the button labeled “Sign in.”
5) Confirm you see the “Dashboard” page load.

### Reset your password (if needed)
SentinelLaw password reset is typically handled by your administrator in pilot deployments.

1) Contact your SentinelLaw administrator or help desk.
2) Request a password reset for your SentinelLaw email address.
3) Sign in using the temporary password you receive.
4) Ask your administrator how to set a new permanent password (if your deployment supports it).

### Switch firms (if applicable)
Some users (for example, platform administrators) can view multiple firms. Most users have only one firm.

[Screenshot: Firm selector] Show the top bar with a “Select firm” button or firm name.

1) Click the button in the top bar labeled “Select firm.”
2) Click the firm name you want to view.
3) Confirm the firm name appears in the top bar.
4) Refresh the page if the data does not change right away.

### Common mistakes and troubleshooting (Getting Started)
- If you see “Select a firm…” on pages, switch firms in the top bar.
- If your login fails, double-check spelling and try again.
- If you see “Signing you out…” or “Failed to load session,” your session may have expired. Return to the login page and sign in again. (In local pilots, also make sure you use the same hostname each time, e.g. always `localhost`, not sometimes `127.0.0.1`.)
- If you are redirected to the **403 Forbidden** page, your role does not allow that page or action for the current firm.
- If you land on the **404 Not Found** page, the page address is wrong or the page no longer exists.
- If you still cannot log in, contact your SentinelLaw administrator.

---

## Using the Dashboard — See AI activity and risk at a glance

### Why this matters
The dashboard provides a quick view of activity trends, potential risk signals, and estimated cost. This helps you spot changes and prioritize reviews.

### Prerequisites
- Sign in successfully.
- Select a firm (if you have a firm selector).

### View system metrics
[Screenshot: Dashboard metrics] Show the metric cards and charts.

1) Click “Dashboard” in the left navigation.
2) Review the metric cards at the top of the page.
3) Review the charts and breakdowns below the cards.

### Interpret the key metrics (plain language)
- **Total Requests**: How many AI requests were made in the selected time range.
- **Policy Blocks**: How many requests were blocked by your rules.
- **Confidentiality Exposure Flagged**: How many requests were flagged for possible sensitive client data (PII or other confidential content).
- **Avg Exposure Score**: The average underlying exposure score across events (higher means more likely to contain sensitive content).
- **Est. Cost**: An estimate of AI usage cost for the selected time range.
- **Top API Keys**: Which apps or systems sent the most requests.
- **Risk Flags**: Signals that may indicate risky behavior (for example, prompt injection attempts).
- **Severity**: A simple “low / medium / high” risk level used to help you prioritize review.

### Change time ranges and filters
[Screenshot: Dashboard range selector] Show the “Last 24 hours / Last 7 days / Last 30 days” dropdown.

1) Click the time range selector near the top of the dashboard.
2) Select “Last 24 hours,” “Last 7 days,” or “Last 30 days.”
3) Wait for the dashboard to refresh.

### Common mistakes and troubleshooting (Dashboard)
- If the numbers look blank or show “—”, wait a few seconds and reload the page.
- If the page tells you to select a firm, switch firms in the top bar.
- If you expect activity but see none, confirm the correct firm is selected.

---

## AI Activity Log (Audit Trail) — Find events, review details, and export records

### Why this matters
Audit logs are the core record of what happened. Use them to investigate incidents, support compliance reviews, and answer “who did what and when.”

### Prerequisites
- Sign in successfully.
- Select a firm (if you have a firm selector).

### Open the AI activity log page
[Screenshot: Navigation] Highlight “AI Activity Log (Audit Trail)” in the left navigation.

1) Click “AI Activity Log (Audit Trail)” in the left navigation.
2) Confirm you see the “Filters” panel and the “Events” table.

### Filter logs (date, app, severity)
[Screenshot: Logs filters] Show Start/End date, Action, Outcome, Severity, API Key, and Flag fields.

1) Set a start time in the field labeled “Start.”
2) Set an end time in the field labeled “End.”
3) Select an action in the dropdown labeled “Action” (optional).
4) Select an app in the dropdown labeled “API Key” (optional).
5) Select a severity level in the dropdown labeled “Severity” (optional).
6) Type a keyword in the field labeled “Flag contains” (optional).
7) Optionally filter by “User” to see events performed by a specific dashboard user (admin actions).

### Save a filter view (optional)
[Screenshot: Views menu] Show the “Views” button and “Save current…” option.

1) Click the button labeled “Views.”
2) Click the option labeled “Save current…”
3) Enter a name for your view.
4) Click the button labeled “Save.”

### View expanded log details
[Screenshot: Event details modal] Show the event summary, risk signals, hashes, and redacted snippets.

1) Click a row in the “Events” table.
2) Review the “Summary” section for action and outcome.
3) Review the “Risk Signals” section for flags and confidential data score.
4) Review the “Redaction & Hashes” section to see what was stored.
5) Click the button labeled “Copy request_id” if you need to reference the event in a ticket.

### Export logs and client audit reports
[Screenshot: Export buttons] Show “Generate Client Audit Report,” “Export CSV,” “Export JSON,” and “Export PDF.”

1) Apply the filters you want to export.
2) For a client-ready flow, click **Generate Client Audit Report**.
3) Choose:
   - a date range,
   - an optional Matter ID,
   - an optional Practice Group,
   - the format (`HTML report`, `PDF report`, `CSV`, or `JSON`),
   - whether to include the executive summary sections.
4) Click **Generate**.
5) Use **HTML report** or **PDF report** when you need a professional review packet with summary context.
6) Use **CSV** or **JSON** when you need the raw export for spreadsheets, analysis, or downstream tooling.
7) Confirm the downloaded file matches your selected scope.

### Common scenarios
**Scenario: “I don’t see new logs.”**
1) Confirm the correct firm is selected in the top bar.
2) Clear filters by clicking the button labeled “Clear.”
3) Expand the time range by setting an earlier “Start” time.
4) Refresh the page.

### Common mistakes and troubleshooting (AI Activity Log)
- If exports look empty, broaden the time range and try again.
- If you cannot find an event, remove filters one by one and retry.
- If you see “No events match…”, confirm the selected firm and time range.
- If a client audit report is too broad, add a Matter ID or Practice Group before regenerating it.
- If you need a client-ready packet, choose **HTML report** or **PDF report** rather than the raw CSV/JSON export.

---

## Creating and Managing API Keys — Allow an app to send requests through SentinelLaw

### Why this matters
API keys let an application connect to SentinelLaw. Treat them like passwords for a system. Anyone with the key can send requests.

### Prerequisites
- Have a role that allows API key management (ask your administrator if you are unsure).
- Know the name of the app or system that will use the key.

### Create a new API key
[Screenshot: API Keys page] Show the “Create key” button and the keys table.

1) Click “API Keys” in the left navigation.
2) Click the button labeled “Create key.”
3) Type a key name in the field labeled “Name” (for example, “radiology-app”).
4) Click the button labeled “Create.”
5) Confirm you see the secret value labeled “Secret (copy now).”

### Copy and store the key safely
[Screenshot: Secret shown once] Show the secret block and “Copy” button.

1) Click the button labeled “Copy.”
2) Save the key in your organization’s approved secure storage (for example, a password manager or vault).
3) Share the key only with the system owner who needs it.
4) Record who received the key and why (your organization may require this).

### Revoke a key
[Screenshot: Revoke button] Show the “Revoke” button in the Actions column.

1) Find the key you want to disable in the keys list.
2) Click the button labeled “Revoke.”
3) Confirm the key shows as “revoked.”

### Safety notes about API keys
- Do not paste API keys into chat tools, email threads, or documents.
- Do not store API keys in shared spreadsheets.
- Do revoke keys when an app is retired or access is no longer needed.

### Common mistakes and troubleshooting (API Keys)
- If you close the window before copying the key, you may not be able to see it again. Create a new key instead.
- If an app stops working, confirm the key was not revoked and the app is using the current key.

---

## Provider Settings — Configure firm-owned LLM providers for this firm

### Why this matters
Provider Settings lets your firm use its own OpenAI, Anthropic, or Azure OpenAI credentials instead of relying on a shared deployment-wide provider configuration.

### Prerequisites
- Have a role that allows provider management (`tenant_admin` or equivalent).
- Know which provider your firm will use.
- Have the provider credential and any required non-secret settings ready.

### Open the Provider Settings page
1) Click **Provider Settings** in the left navigation.
2) Confirm you see three provider cards:
   - **OpenAI**
   - **Anthropic**
   - **Azure OpenAI**
3) Confirm each card shows whether the provider is configured, enabled, and the default provider.

### Add or update a provider configuration
1) Find the provider card you want to use.
2) Enter a clear connection name.
3) Turn on **Enable this provider for firm traffic** if the firm should be allowed to use it.
4) Enter the approved models or deployments, one per line.
5) Enter the provider-specific details:
   - OpenAI: API key, optional custom base URL, optional default model.
   - Anthropic: API key, optional custom base URL, optional default model.
   - Azure OpenAI: endpoint, API version, default deployment, and either API key or managed-identity settings.
6) Click **Save** to store the configuration.
7) Click **Save and Test** if you want SentinelLaw to save the settings and immediately verify the connection.

### Set the default provider
1) Save at least one enabled provider connection.
2) If your firm uses more than one enabled provider, click **Set as Default** on the provider card you want SentinelLaw to use by default.
3) Read the warning message carefully before confirming the change.

### Understand what the approval controls do
- Enabled provider configs are the firm’s approved providers.
- The approved-models list is enforced on the server for each provider.
- If a request names a provider your firm did not approve, SentinelLaw blocks it.
- If a request names a model your firm did not approve for that provider, SentinelLaw blocks it.
- If multiple providers are approved and there is no default provider, requests that omit `provider` are blocked.
- If a request omits `model` and there is no default model or deployment for the chosen provider, the request is blocked.

### Edit or rotate provider credentials
1) Find the provider card you want to update.
2) Change any non-secret settings you need.
3) If you need to rotate the credential, paste a new API key into the password field.
4) Leave the secret field blank if you want to keep the existing stored secret.
5) Click **Save** or **Save and Test**.

### Test a provider connection
1) Find the provider card you want to verify.
2) Click **Test Connection**.
3) Wait for the success or failure message.
4) If the test fails, review the model/deployment allowlist and provider-specific settings.

### Important notes about secrets
- SentinelLaw does not show stored provider secrets after you save them.
- The page only shows whether a secret is configured.
- If you lose the original secret, obtain a fresh one from your provider and update the configuration.

### Common mistakes and troubleshooting (Provider Settings)
- Only the **Firm Administrator** role can manage Provider Settings. Other roles will be redirected to **403 Forbidden**.
- If requests are blocked for “provider not allowed,” confirm the correct firm is selected and the provider is enabled.
- If requests are blocked for “model not allowed,” add the model or deployment to the allowlist.
- If requests are blocked because no default provider is configured, set one directly on the provider card.
- If requests are blocked because no default model or deployment is configured, set one directly on the provider card.
- If Azure OpenAI tests fail, confirm the endpoint, API version, and deployment name exactly match Azure.
- If a connection test says the provider is temporarily unavailable, wait and try again before changing credentials.

### Read SentinelLaw error messages safely
- SentinelLaw now shows a safe end-user message first and keeps the more specific detail for administrators.
- If you report a problem, capture the **request ID** shown by your administrator tools or exported logs.
- The most common categories are:
  - Authentication required
  - Forbidden
  - Firm scope error
  - Blocked by Firm AI Rules
  - Provider unavailable / timed out

---

## Firm AI Rules — Set rules that block or flag risky AI use

### Why this matters
A rule set is a set of rules you define. Firm AI Rules can block certain requests, limit usage, and flag risky content for review.

### Prerequisites
- Have a role that allows policy editing (ask your administrator if you are unsure).
- Agree internally on what you want to block or flag (for example, prompt injection attempts).

### Open the policies editor
[Screenshot: Firm AI Rules page] Show the JSON editor, “Publish” button, and “Test Rules (Dry Run)” section.

1) Click “Firm AI Rules” in the left navigation.
2) Review the rule text in the “Firm AI Rules (JSON)” panel.
3) Review the **Version History** panel on the right before making changes.

### Edit policy settings (simple guidance)
Rules are written as structured text. SentinelLaw checks it before saving. If you must change it, make small changes and test them.

1) Read the current policy first before editing anything.
2) Change one setting at a time.
3) Watch for any “Invalid JSON” message after you edit.
4) Add a short change note when you publish so legal/compliance reviewers can understand why the rule set changed.

### Understand the prompt-injection controls
- **Injection protection** blocks explicit prompt-injection phrases using the rule patterns in the current policy.
- **Prompt-injection heuristic response** controls what SentinelLaw does when it detects suspicious instructions hidden in contracts, comments, annexes, metadata blocks, or multiline text:
  - `Flag only`: log and surface the signal without blocking.
  - `Block on High only`: block only stronger multi-signal prompt-injection cases.
  - `Block on Medium+`: block medium and high heuristic prompt-injection cases.
- Dry-run results can show detector names and redacted normalized examples so administrators can understand why a prompt was flagged without exposing the full prompt.

### Test a policy against example text
[Screenshot: Dry run panel] Show “Sample prompt,” “Sample response,” and “Run dry-run.”

1) Enter an example request in the field labeled “Sample prompt.”
2) Enter an example response in the field labeled “Sample response.”
3) Click the button labeled “Run dry-run.”

### Review version history
1) In the **Version History** section, select a version entry.
2) Check:
   - when it was created,
   - who published it,
   - the change note or summary,
   - whether it is the active version.
3) Use this before approving changes or answering “who changed what?”

### Compare versions safely
1) Select a version in **Version History**.
2) Open the **Compare Versions** panel.
3) Choose one of the compare modes:
   - **Current vs selected** to compare the active rule set against an older version.
   - **Template vs selected** when the selected version came from a built-in template.
4) Review the highlighted JSON differences before publishing or rolling back.

### Roll back to an earlier Firm AI Rules version
1) Select the historical version you want to restore.
2) Click **Rollback to this version**.
3) Read the confirmation message carefully.
4) Confirm the rollback.
5) SentinelLaw creates a brand-new active version from that historical version. It does not overwrite or delete the old record.

### Important notes about version history
- SentinelLaw keeps Firm AI Rules history tenant-scoped.
- Old versions are immutable records.
- Rollback creates a new active version and preserves the original version you selected.
- Policy templates and published firm policies are tracked separately so reviewers can compare a customized version back to its template baseline.

### Save / publish changes
[Screenshot: Publish confirm dialog] Show the confirmation dialog.

1) Click the button labeled “Publish.”
2) Confirm the change when you see the confirmation dialog.
3) Confirm you see a message that the policy was published.

### Common mistakes and troubleshooting (Firm AI Rules)
- If you see an error about invalid policy text, undo your last change and try again.
- If you are not allowed to edit, ask a firm administrator to publish changes.
- If behavior does not change, wait a minute and try a new test request (policies apply to new requests).

---

## Safety & Consistency Tests — Run the test suite and compare results over time

### Why this matters
Safety & Consistency Tests help you check whether models and configurations behave as expected. This is useful before and after rule changes or provider changes.

### Prerequisites
- Have a role that allows running evaluations (ask your administrator if you are unsure).
- Understand the goal of the run (for example, “verify we block prompt injection attempts”).

### Run the test suite
[Screenshot: Tests run dialog] Show “Run suite,” provider/model choices, and the Run button.

1) Click “Safety & Consistency Tests” in the left navigation.
2) Click the button labeled “Run suite.”
3) Select a provider in the dropdown labeled “Provider.”
4) Select a model in the dropdown labeled “Model.”
5) Click the button labeled “Run.”
6) Wait for the run status to change to “finished.”

### Read results and compare runs
[Screenshot: Run details] Show pass/fail counts and a “Previous” reference.

1) Click a row in the “Runs” table to open run details.
2) Review the pass and fail counts at the top.
3) Review the pass rate and the change vs the previous run (if shown).
4) Click a test case ID to view its details.

### Understand “pass” and “fail” (plain language)
- **Pass** means the test behaved as expected under your current policy and settings.
- **Fail** means the test did not behave as expected. This may indicate a policy gap, a configuration issue, or a provider/model behavior change.

### Respond when many tests fail
1) Pause any policy changes in progress.
2) Review the failed cases to see common patterns.
3) Run the suite again to confirm the result is consistent.
4) Contact your SentinelLaw administrator if failures persist.

### Common mistakes and troubleshooting (Safety & Consistency Tests)
- If runs never finish, reload the page and check again.
- If results look unexpected, confirm you selected the intended provider and model.

---

## Alerts — Notify your team about important governance events

### Why this matters
Alerts let your firm receive governance notifications without watching the dashboard continuously.

### Prerequisites
- Have the **Firm Administrator** role.
- Have at least one email address or webhook destination ready.

### Open and configure Alerts
[Screenshot: Alerts page] Show the delivery settings, trigger checkboxes, and recent alert history.

1) Click **Alerts** in the left navigation.
2) Enter one or more recipient email addresses, one per line.
3) Optionally add a webhook URL if your firm wants alerts sent to Slack, Teams, or another internal system.
4) Choose the webhook format if you use a webhook.
5) Set the severity threshold.
6) Set the confidentiality threshold and throttle window.
7) Choose which trigger events should create alerts.
8) Click **Save Alerts**.

### Understand the available alert triggers
- **High confidentiality exposure**: alerts when a request crosses the firm’s confidentiality threshold.
- **Prompt injection detected**: alerts when SentinelLaw finds likely instruction-hijacking patterns.
- **Requests blocked by Firm AI Rules**: alerts when policy, approval controls, or confidentiality rules block a request.
- **Repeated provider failures**: alerts when the same provider fails multiple times inside the configured window.

### Send a test alert
1) Save your alert settings first.
2) Click **Send Test Alert**.
3) Confirm you see a success or delivery-warning message.
4) Review **Recent Alert History** to confirm the delivery attempt was recorded.

### Important notes about stored destinations
- SentinelLaw shows your saved email list back to you.
- SentinelLaw does **not** reveal a stored webhook URL after save.
- The page only shows whether a webhook is configured and, when possible, a safe destination hint.

### Common mistakes and troubleshooting (Alerts)
- If **Send Test Alert** fails immediately, configure at least one email recipient or webhook first.
- If email delivery fails, ask your SentinelLaw administrator to confirm SMTP settings are configured.
- If alerts feel too noisy, raise the severity threshold or lengthen the throttle window.
- If alerts are not arriving, review **Recent Alert History** for sent/failed attempts.

---

## Settings and User Management — Control storage choices and manage access (if permitted)

### Why this matters
Settings control what is stored in the audit trail. User management controls who can view and change governance controls.

### Prerequisites
- Have a role that allows settings and user management (ask your administrator if you are unsure).

### Open and update settings
[Screenshot: Settings page] Show “Content Storage” and the link to the Alerts page.

1) Click “Settings” in the left navigation.
2) Review the “Content Storage” section.
3) Select a storage mode in the dropdown labeled “Storage mode.”
4) Click the button labeled “Save.”
5) Use the **Alerts** page for notification recipients, webhook delivery, trigger events, and recent alert history.

### Understand the storage options (plain language)
- **OFF (hash only)**: Stores a fingerprint of the text. It does not store the text itself.
- **Store redacted snippet**: Stores a short snippet with sensitive patterns masked.
- **Store full content**: Stores the text. This can increase risk because it may include sensitive information.

### Add a user (if permitted)
[Screenshot: Users page] Show “Create user,” email field, role dropdown, and temporary password display.

1) Click “Users & Roles” in the left navigation.
2) Click the button labeled “Create user.”
3) Enter the user’s email address.
4) Select a role from the “Role” dropdown.
5) Click the button labeled “Create.”
6) Copy the temporary password shown and deliver it through your organization’s approved method.

### Review a user’s activity (quick audit)
[Screenshot: User Activity modal] Show clicking a user row and the “User Activity” dialog.

1) Click “Users & Roles” in the left navigation.
2) Click a user row (active or inactive).
3) Review the “User Activity” list.
4) Click “View in AI Activity Log” to open the full log filtered to that user.

### Change a user’s role (if permitted)
[Screenshot: Role dropdown in table] Show the role selector in the user row.

1) Find the user in the list.
2) Select the new role from the dropdown in the “Actions” column.
3) Confirm you see a message that the role was updated.

### Delete a user (remove access) (if permitted)
[Screenshot: Delete button] Show “Delete” in the user row.

1) Find the user in the list.
2) Click the button labeled “Delete.”
3) Confirm the prompt to remove access.
4) Confirm the user is removed from the list (use “Show inactive” to view deactivated users).

Note: In pilots, deleting a user is implemented as deactivation so audit trails remain intact.

### Safety reminders
- Grant the minimum access needed for someone to do their job.
- Avoid enabling full content storage unless you have a clear need and an approved retention plan.
- Treat exports as sensitive if they include redacted snippets or other identifiers.

### Common mistakes and troubleshooting (Settings and Users)
- If you cannot see the Settings or Users pages, your role may not allow it.
- If you enable full content storage by accident, switch back to OFF and click “Save,” then contact your administrator.

---

## Common Troubleshooting — Resolve the most common issues quickly

### Login issues
1) Re-enter your email carefully and try again.
2) Re-enter your password carefully and try again.
3) Contact your administrator to reset your password if needed.

### Unable to see logs
1) Select the correct firm in the top bar.
2) Expand the time range using “Start” and “End.”
3) Clear filters using the button labeled “Clear.”
4) Refresh the page.

### Export fails
1) Try a smaller time range first.
2) Remove some filters and retry.
3) Refresh the page and try again.
4) Contact your administrator if the error continues.

### Contact support guidance
When you contact support, include:
- What you were trying to do.
- The page name (for example, “AI Activity Log (Audit Trail)”).
- The time and date the issue happened.
- The request_id (if you have it) from the event details screen.

---

## Super Admin — Manage Firms (Tenants)

This section applies only to platform administrators (role `super_admin`).

### Create a new firm
1) Click **Firms** in the left navigation.
2) Click **Create firm**.
3) Enter the firm name.
4) Optionally set a slug (URL-safe identifier). If you leave it blank, SentinelLaw generates one.
5) Click **Create** and confirm you land on the firm detail page.

### Switch into a firm context
Switching context lets you view the dashboard, activity log, API keys, and rules for a specific firm.

1) Open the firm detail page.
2) Click **Switch to this firm**.
3) Confirm you see a banner: **Viewing as: <Firm Name>**.

### Return to platform context
1) Click **Return to Platform** in the banner at the top of the page.

### Suspend a firm (disable switching)
1) Open the firm detail page.
2) Go to **Settings**.
3) Change **Status** to `suspended`.
4) Click **Save** and confirm.

Note: Suspending a firm is reversible and avoids breaking database integrity.

## Glossary — Understand common terms in everyday language

- **Tenant**: Your firm’s (or organization’s) space in SentinelLaw. It separates your data from other organizations.
- **Dashboard**: A summary screen that shows key numbers and trends.
- **Audit log**: A record of what happened and when. It is used for review and compliance.
- **Event**: A single record in the audit log (for example, one AI request or one policy block).
- **API key**: A secret code that lets an application connect to SentinelLaw. Treat it like a password.
- **Policy**: A set of rules you set so the system blocks or flags unwanted input or output.
- **Confidential data**: Sensitive client data (for example, PII, case details, or privileged work product) that should not be disclosed or stored broadly.
- **Confidential data score**: A number that estimates how likely text contains confidential or sensitive client data.
- **Risk flag**: A signal that something may be risky (for example, a prompt injection attempt).
- **Severity**: A “low / medium / high” label that helps prioritize what to review first.
- **Export (CSV/JSON)**: A downloaded file of records. CSV is spreadsheet-friendly. JSON is structured for tools.
- **Evaluation**: A set of test cases run to check behavior and safety signals over time.
