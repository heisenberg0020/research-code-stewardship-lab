# Blind Challenge Access Log

Use this append-oriented log for one release. Replace every double-braced prompt
and add one row per material access, delivery, denial, copy, validation, or
withdrawal action. Never paste hidden answers, tokens, credentials, personal
data, probe logic, or other restricted contents into the log; record stable
references and digests instead.

This is a declared activity record, not an authentication system or tamper-proof
audit trail. A written name or role does not verify identity or authority. Local
staging and the allowlists below organize review surfaces; they do not enforce
access control. Apply separate filesystem ACLs, isolated hosts, or controlled
delivery mechanisms where blind isolation matters.

## Release binding

- Release ID: {{stable-release-id}}
- Case ID and version: {{case-id and case-version}}
- Manifest path and SHA-256: {{path and digest}}
- Log owner: {{declared human name and role}}
- Log opened at: {{YYYY-MM-DDTHH:MM:SSZ}}
- External access-control mechanism: {{ACL, isolated host, delivery service, or None with risk owner}}

## Declared role allowlists

Anything not explicitly listed is denied by policy. These rows document intended
scope only; verify enforcement independently.

| Role | Allowed read paths | Allowed write paths | Allowed commands or actions | Explicitly denied paths |
| --- | --- | --- | --- | --- |
| challenge | `challenge/**`, `blind-source-manifest.json`, `REVOCATION_NOTICE.md` | `{{external-challenge-workspace}}/**` | `{{public-check-command}}` | `evaluator/**`, `maintainer/**`, `ACCESS_LOG.md` |
| evaluator | `challenge/**`, `evaluator/**`, manifest, revocation notice, access log | `{{external-evaluator-workspace}}/**`, `ACCESS_LOG.md` | `{{evaluator-verification-command}}` | `maintainer/**` |
| maintainer | challenge, evaluator, maintainer, manifest, revocation notice, access log | the same explicitly listed release paths | `{{package-validation-and-release-commands}}` | {{None or explicit external denylist}} |

## Access events

Use UTC timestamps and stable event IDs. `Result` is one of `allowed`, `denied`,
`failed`, or `revoked`. Record the policy decision and the observed result
separately when they differ.

| Event ID | UTC timestamp | Declared actor | Role | Action | Relative path or release channel | Purpose | Policy basis | Result | Evidence reference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| {{ACCESS-0001}} | {{YYYY-MM-DDTHH:MM:SSZ}} | {{name or service label}} | {{challenge, evaluator, or maintainer}} | {{read, write, execute, copy, deliver, deny, validate, quarantine, or revoke}} | {{relative path or channel; no secret URL}} | {{bounded purpose}} | {{manifest allowlist item, approval gate, or exception ID}} | {{allowed, denied, failed, or revoked}} | {{log, receipt, hash, or ticket reference}} |

## Exceptions and incidents

For every access outside the declared allowlist, create an incident entry even if
the attempt failed.

| Incident ID | Related event IDs | Observed boundary crossing | Immediate containment | Evidence preserved | Human owner | Status |
| --- | --- | --- | --- | --- | --- | --- |
| {{INCIDENT-0001}} | {{event IDs}} | {{attempted or completed access and affected role boundary}} | {{deny, pause, quarantine, revoke, or notify}} | {{stable references and hashes}} | {{declared name and role}} | {{open, contained, resolved, or withdrawn}} |

## Integrity checkpoints

| Checkpoint ID | Covered event range | Previous checkpoint digest | Current log SHA-256 | Created at | Declared reviewer | Review result |
| --- | --- | --- | --- | --- | --- | --- |
| {{CHECKPOINT-0001}} | {{ACCESS-0001..ACCESS-00NN}} | {{digest or GENESIS}} | {{64-lowercase-hex-digest}} | {{YYYY-MM-DDTHH:MM:SSZ}} | {{name and role}} | {{accepted, discrepancy, or cannot-assess}} |

Checkpoint hashes can reveal later edits but do not authenticate the person who
created them and do not make this log append-only or tamper-proof.

## Closure or withdrawal

- Final release status: {{active, quarantined, withdrawn, or superseded}}
- Closed at: {{YYYY-MM-DDTHH:MM:SSZ or open}}
- Revocation notice reference: {{path and digest or None}}
- Unresolved access uncertainty: {{unknowns, owner, and next check}}
- Declared human review: {{name, role, decision, timestamp, and evidence}}
- Claims not made: identity authentication, enforced access control, absence of prior exposure, scientific correctness, or certification
