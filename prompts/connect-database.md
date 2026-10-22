# Assess database access — copyable prompt

This checks endpoint-specific capability and authorized access, not a blanket “connected” flag.

```text
Research Question/project: [details]
Sources I require/exclude: [optional; otherwise recommend appropriate options]
Intended operation: [metadata search / DOI lookup / citation tracking]
Access I already have: [none / free key configured privately / institutional]
Permission to consult official access documentation: [yes / ask first]
Probe/search scope and total HTTP budget: [propose for confirmation / exact limits]
Account registration or email use: not authorized unless I separately agree

First inspect installed adapters and local configuration without exposing keys.
Separate no-key endpoints, optional free setup, mandatory keys and institutional
entitlement. Do not treat configuration or a quota check as proof of search access.
OpenAlex first-page anonymous search is distinct from keyed quota inspection
and cursor pagination. Record endpoint-specific status and actual time.

Use available, key_missing, key_invalid, insufficient_entitlement,
quota_exhausted, rate_limited, temporarily_unavailable, not_implemented,
or not_verified when no live verification has occurred.
A missing optional key must not block independently authorized public sources.

Prepare one source/query/access budget for confirmation. Include verification
requests and metadata subrequests, then execute ordinary authorized calls
without repeated prompts. After I configure a key, perform the included
verification; activation pending is not usable authentication.
Never switch providers/credential modes, purchase quota or broaden scope
beyond this plan without consent.

Assess OpenAlex's official Agent-assisted registration only if useful.
Never invent or infer my email, register automatically, or click activation
on my behalf. Do not expose credentials in logs, reports, commands or Git.

For Scopus/Web of Science/PsycINFO, distinguish missing adapter from missing
institutional entitlement. Record coverage gaps and leave requests unexecuted
when unsupported. Continue other authorized sources. Keep all existing
research Gates; no library import, fake results or automatic scientific approval.
```
