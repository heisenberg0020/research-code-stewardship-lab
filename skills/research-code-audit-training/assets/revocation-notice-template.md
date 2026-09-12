# Blind Challenge Revocation Notice

Replace every double-braced prompt. Publish this notice when a release must be
quarantined, withdrawn, or superseded. Describe the affected boundary without
revealing evaluator-only answers, probes, mappings, or repair spans.

This notice records declared human decisions. Names and roles written here are
not authenticated identities, signatures, or proof of authority. Local staging
is a packaging convenience, not access control; enforce withdrawal through the
actual delivery system, filesystem permissions, and downstream coordination.

## Release identity

- Release ID: {{stable-release-id}}
- Case ID and version: {{case-id and case-version}}
- Manifest digest: {{blind-source-manifest SHA-256}}
- Previous status: {{active or superseded}}
- New status (`quarantined`, `withdrawn`, or `superseded`): {{status}}
- Effective time: {{YYYY-MM-DDTHH:MM:SSZ}}
- Replacement release ID: {{release-id or None}}

## Declared decision

- Initiating human and role: {{declared name and role}}
- Decision owner and role: {{declared name and role}}
- Trigger: {{provenance, license, design, leakage, integrity, or other bounded trigger}}
- Evidence references: {{manifest fields, logs, review IDs, hashes, or incident records}}
- Decision rationale: {{facts, uncertainty, and why continued distribution is unsafe}}
- Authentication boundary: declaration only; identity and authority not authenticated

## Affected scope

- Affected package roles (`challenge`, `evaluator`, `maintainer`): {{roles}}
- Affected files or digest set: {{relative paths and SHA-256 digests}}
- First known affected release: {{release ID and version}}
- Last known unaffected release: {{release ID and version or Unknown}}
- Known recipients or delivery channels: {{bounded list or Unknown with owner}}
- Claims, scores, or decisions requiring review: {{bounded impact or Unknown}}

## Immediate containment

- Delivery disabled or paused: {{system, owner, time, and evidence}}
- Existing copies quarantined or access revoked: {{action and evidence}}
- Maintainer and evaluator materials preserved: {{read-only evidence location and digest}}
- Downstream recipients notified: {{notification IDs and timestamps}}
- Actions deliberately not taken: {{for example, do not delete incident evidence}}

Revocation is not erasure. Previously distributed copies may remain available,
and this notice does not prove that access was prevented before or after the
effective time.

## Reissue and follow-up conditions

- Required provenance or license resolution: {{evidence and approval gate}}
- Required design or anti-leakage correction: {{bounded correction and validation}}
- Required package-integrity and reproducibility checks: {{commands and evidence}}
- New case version or release ID rule: {{versioning requirement}}
- Human approvals required before reissue: provenance, license, design, leakage, release-preparation
- Residual risk and revisit trigger: {{risk, owner, and trigger}}

## Human review record

| Gate | Status | Declared approver and role | Time | Evidence reference |
| --- | --- | --- | --- | --- |
| provenance | {{status}} | {{name and role}} | {{timestamp}} | {{reference}} |
| license | {{status}} | {{name and role}} | {{timestamp}} | {{reference}} |
| design | {{status}} | {{name and role}} | {{timestamp}} | {{reference}} |
| leakage | {{status}} | {{name and role}} | {{timestamp}} | {{reference}} |
| release-preparation | {{status}} | {{name and role}} | {{timestamp}} | {{reference}} |

Final note: these rows are human declarations for auditability. They are not
cryptographic signatures, identity verification, scientific certification, or
legal advice.
