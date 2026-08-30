# Reporting and exit-code contract

Recon reports actionable `SECRET` and review-required `UNKNOWN` findings by default.
`REFERENCE` and `FALSE_POSITIVE` candidates remain available with
`--include-non-actionable`. Terminal output begins with classification totals and each
detail includes the detector, bounded classification, confidence, reason, location,
and suggested action.

Candidate credential values are redacted to a deterministic fingerprint and length
unless `--show-raw-evidence` is explicitly set. Raw evidence can contain live
credentials and must be handled as sensitive output.

JSON output is a single object with `schema_version: "1.0"`, a `summary`, and a
`findings` array. Additive fields may be introduced within version 1; removing or
renaming fields requires a schema-version change. Progress messages go to stderr so
stdout remains parseable JSON.

| Exit code | Meaning |
| --- | --- |
| `0` | Scan completed and no `SECRET` finding triggered policy. |
| `1` | Invocation, regular expression, ref, repository, or other operational error. |
| `2` | Scan completed and at least one finding was classified `SECRET`. |
| `3` | Scan was stopped because complete history could not be guaranteed. |

`REFERENCE`, `FALSE_POSITIVE`, and `UNKNOWN` do not trigger the default policy exit.
Consumers should use the versioned JSON fields rather than parsing terminal text.
