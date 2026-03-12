# Source Testing

Every source change needs tests beyond unit coverage.

## Required matrix

At minimum verify:

- parser behavior when command surface changes
- help output
- capability and config checks
- real CLI invocation
- persistence side effects for update
- search no-write behavior
- misuse path behavior
- interact audit behavior when applicable

## TDD sequence

1. add one failing test
2. run that focused test and confirm the failure is correct
3. implement the minimal code
4. rerun the focused test
5. rerun the relevant suite

## CLI simulation

CLI tests should simulate how a user would actually run the tool.

Cover both:

- happy path
- misuse path

Examples of misuse:

- unsupported option
- unsubscribed update target
- missing config
- invalid ref
- invalid `--source` / `--group` combinations

## Verification rule

Do not claim the source is complete until you have current command output proving the tests and CLI checks passed.
