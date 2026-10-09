# Product scope and next steps

The MVP implements four tools: define a contract, show its native-comment history,
observe post-delivery evidence, and check what attention is needed. The implemented
rules are in [the protocol](record-protocol.md), with boundaries summarized in
[MVP constraints](mvp-constraints.md).

Repository work ends with an open, tested PR and actual human review, not an
assistant-triggered merge or live deployment. Keep ordinary review/remediation on
the existing native task and feature lane.

A separately approved low-risk real-project pilot can establish whether outcome
bookkeeping is useful: declare a contract, let native Kanban deliver, then assess
the result with real evidence. Passing tests alone does not establish usefulness.

Do not expand into dashboards, scheduling, fleet crawlers or automatic remediation
without evidence from that pilot. Packaging and development tooling support the
plugin; they are not independent products.
