# Development container for GlobaLens 3.0. The toolchain itself is pinned in mise.toml; this
# image only provides what mise and the Claude Code hooks need to run.
FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# python3: the hooks in .claude/hooks run on the system Python.
# gnupg: lets mise verify the signature on Node.js releases.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git gnupg python3 \
    && rm -rf /var/lib/apt/lists/*

USER vscode

# mise, pinned. It installs every tool in mise.toml under the user's home directory.
ARG MISE_VERSION=v2026.11.4
RUN curl -fsSL https://mise.run | MISE_VERSION="${MISE_VERSION}" sh
ENV PATH="/home/vscode/.local/share/mise/shims:/home/vscode/.local/bin:${PATH}"
