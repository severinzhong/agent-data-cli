# API Source Guidance

Use this file for HTTP or JSON API backed sources.

## Research questions

- Is the API public, authenticated, or session-based?
- Is there a stable identifier for channels?
- Is remote search separate from update?
- What field should become `external_id`?
- What field should become `published_at`?
- How does pagination work?
- Is incremental fetch based on time, cursor, page, or none?

## Capability mapping

- `channel search`: valid when the API supports remote channel discovery
- `content search`: valid when the API supports remote content discovery
- `content update`: valid when subscribed channels can be fetched incrementally
- `content interact`: valid only when side-effect endpoints are available and reliable

## Config design

Declare config through manifest only.

Typical API config:

- base URL
- token or cookie
- proxy URL
- mode when there are multiple acquisition paths

## Common mistakes

- confusing search results with update records
- using a display title as unique id
- burying auth logic in ad hoc environment reads
