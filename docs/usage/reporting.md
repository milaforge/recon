# Reporting and exit-code contract

Recon prints redacted findings. Terminal output begins with classification totals and
each detail includes the detector, bounded classification, confidence, reason,
location, and suggested action. Candidate credential values are represented only by
a deterministic fingerprint and length.

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

`REFERENCE`, `FALSE_POSITIVE`, and `UNKNOWN` remain visible but do not trigger the
default policy exit. Consumers should use the versioned JSON fields rather than
parsing terminal text.
