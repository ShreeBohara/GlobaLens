# infra/live/bootstrap

The R2 bucket that holds OpenTofu state, with client-side state encryption. Applied once by the owner from their own machine: the only production change that does not go through CI.

Placeholder: only the OpenTofu version is pinned here. The stack is written in P1 task 6.
`mise run tofu:plan` plans it read-only; applies run from CI, never from a session.
