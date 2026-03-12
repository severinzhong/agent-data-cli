# Result Reporting

When reporting back after execution, keep it short but concrete.

## Minimum structure

Always cover:

- what command flow was run
- what result was obtained
- what important constraint or failure was encountered
- what next action is now possible

## Good patterns

- "Ran `content search` against `bbc` for `openai`; found 5 remote items and did not write to local storage."
- "Subscribed `ashare:sh600519`, synced 20 records, then queried local content."
- "Did not run `content interact` because the request did not provide explicit refs."

## Avoid

- dumping raw commands with no interpretation
- saying "done" without reporting the result
- hiding that a command only searched remotely or only queried locally
- implying persistence when only discovery was performed
