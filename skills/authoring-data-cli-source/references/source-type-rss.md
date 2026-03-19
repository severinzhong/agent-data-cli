# RSS Source Guidance

Use this file when the target behaves like a feed or route-indexed feed network.

## Good fit

RSS is a good fit when:

- a channel can be mapped to a feed URL
- entries already have stable title, link, and publish time
- update is naturally feed fetch plus normalization

## Research questions

- How is channel identity represented?
- Is there a route index or discovery API?
- Are publish times stable and parseable?
- Is pagination available, or is the feed window fixed?
- Are there concrete feeds and template feeds?

## Capability mapping

- `channel search`: only if remote feed discovery is real
- `content search`: often unsupported unless the site offers remote search
- `content update`: usually the main capability
- `content interact`: usually unsupported

## Common mistakes

- treating a route template as a concrete channel without parameters
- using feed order as identity instead of deriving a stable `content_key`
- silently ignoring malformed publish time data
