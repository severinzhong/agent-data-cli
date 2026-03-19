# Interact Source Guidance

Use this file when the source needs explicit remote side effects such as like, comment, vote, or other per-item actions.

## Preconditions

Only add `content.interact` when the source can support all of:

- explicit executable refs
- stable verb semantics
- clear side-effect boundaries
- auditable execution results

## Design rules

- verbs are private to the source
- `content interact` must always require explicit `--source`
- only explicit refs are accepted
- the source must parse and validate its own `content_ref`
- interact must not implicitly update local records
- `content_ref` is for executable remote targets; it is not a replacement for `content_key`

## Research questions

- What actions are actually possible?
- What auth or session state is required?
- Can refs be executed later, or are they one-time tokens?
- What error shapes does the remote action return?
- Is batching safe, or should refs be handled independently?

## Common mistakes

- adding interact before ref format is stable
- trying to standardize verbs across sources
- allowing implicit target expansion from query results
