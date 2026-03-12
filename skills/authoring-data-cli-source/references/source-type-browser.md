# Browser Source Guidance

Use this file when stable acquisition requires a browser, cookie-backed session, or rendered HTML.

## Use browser only when needed

Prefer:

1. RSS
2. public API
3. direct HTTP fetch and parse
4. browser automation only if the earlier paths are not sufficient

## Research questions

- Is rendered HTML required, or can HTTP fetch do the job?
- Is authentication mandatory?
- Does the site depend on anti-bot timing or browser state?
- Is the data available in inline JSON or network calls after page load?
- Can the browser path be restricted to discovery only, while update uses HTTP?

## Design notes

- keep browser-specific logic local to the source
- declare required config clearly
- keep mode selection explicit when both HTTP and browser paths exist
- avoid hidden fallback from API mode to browser mode

## Common mistakes

- defaulting to browser too early
- mixing scraping logic and normalization logic in one large function
- making source behavior depend on undeclared browser state
