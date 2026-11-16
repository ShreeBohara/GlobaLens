# infra/live/node-paid

The paid node (OVH VPS-1, configuration S): the order under `prevent_destroy`, deny-all-inbound, and the first-boot bootstrap.

Placeholder: only the OpenTofu version is pinned here. The stack is written in P1 task 7.
`mise run tofu:plan` plans it read-only; applies run from CI, never from a session.
