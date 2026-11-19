# infra/live/web

The Workers Static Assets deployment that serves the site, its preview version per pull request and the static-asset headers file.

Placeholder: only the OpenTofu version is pinned here. The stack is written in P1 tasks 12 and 16.
`mise run tofu:plan` plans it read-only; applies run from CI, never from a session.
