# infra/live/storage

R2 buckets, lifecycle rules, bucket locks, the `cdn` custom domain and its Cache Rules. Everything here carries `prevent_destroy`.

Placeholder: only the OpenTofu version is pinned here. The stack is written in P1 task 6.
`mise run tofu:plan` plans it read-only; applies run from CI, never from a session.
