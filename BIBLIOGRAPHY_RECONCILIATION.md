# Bibliography Reconciliation

`writing-bibliography` reconciles current inline/trace citations with canonical Paper Registry IDs, `03_library/references.bib`, evidence-linked source identities and exact document hashes/versions. Citation keys remain the existing stable paper IDs; no identity renaming or provider-driven overwrite occurs.

Checks include unknown citations, missing/unused entries, duplicate keys, duplicate DOI/title entries, DOI/title/author/year mismatches, incomplete cited metadata, registry conflicts/ambiguous identity, unsupported sources and document identity/version errors. A secondary-source warning requires the separate semantic attribution audit; metadata cannot determine whether prose launders a secondary citation.

Outputs: `10_audit/BIBLIOGRAPHY_AUDIT.md` contains structured historical reports; `09_writing/references.bib` is a cited-only export. Original library BibTeX and provider records are not silently rewritten. Unused entries are warnings, not deletions. Resolve metadata conflicts through reviewed upstream identity correction, then reconcile again.

The conservative parser accepts brace-delimited entries, nested TeX groups, braced/quoted values and numeric values. String macros/preambles and unsupported syntax produce explicit errors rather than guessed expansion. It is not a complete BibTeX/LaTeX engine. Additional styles, CSL formatting, RIS writing output and DOCX export are deferred; existing upstream bibliography functions remain unchanged.

No network or DOI resolution is performed by this command. Canonical metadata is checked against saved records, not independently re-verified with a live publisher. Correct metadata does not establish Claim–Evidence entailment.
