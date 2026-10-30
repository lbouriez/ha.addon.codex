ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.13-alpine3.21
FROM ${BUILD_FROM}

LABEL maintainer="Laurent (@lbouriez)"
LABEL org.opencontainers.image.title="Codex App for Home Assistant"
LABEL org.opencontainers.image.description="OpenAI Codex App for the Home Assistant sidebar with terminal access, model controls, and optional MCP integration"
LABEL org.opencontainers.image.source="https://github.com/lbouriez/ha.addon.codex"
LABEL org.opencontainers.image.licenses="MIT"

ENV \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TERM=xterm-256color \
    NODE_OPTIONS=--max-old-space-size=512

RUN apk add --no-cache \
    acl \
    bash \
    bubblewrap \
    ca-certificates \
    coreutils \
    curl \
    findutils \
    gawk \
    git \
    github-cli \
    grep \
    jq \
    nano \
    ncurses \
    ncurses-terminfo-base \
    nginx \
    nodejs \
    npm \
    openssh-client \
    openssl \
    p7zip \
    procps \
    ripgrep \
    sed \
    sudo \
    su-exec \
    tmux \
    vim \
    libstdc++ \
    && update-ca-certificates

ARG BUILD_ARCH
RUN case "${BUILD_ARCH}" in \
        amd64) TTYD_ARCH="x86_64"; TTYD_SHA256="8a217c968aba172e0dbf3f34447218dc015bc4d5e59bf51db2f2cd12b7be4f55" ;; \
        aarch64) TTYD_ARCH="aarch64"; TTYD_SHA256="b38acadd89d1d396a0f5649aa52c539edbad07f4bc7348b27b4f4b7219dd4165" ;; \
        *) echo "Unsupported arch: ${BUILD_ARCH}" && exit 1 ;; \
    esac && \
    curl -fsSL "https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.${TTYD_ARCH}" -o /usr/bin/ttyd && \
    echo "${TTYD_SHA256}  /usr/bin/ttyd" | sha256sum -c - && \
    chmod +x /usr/bin/ttyd

ARG CODEX_VERSION=0.164.0
RUN NPM_CONFIG_CACHE=/tmp/npm-cache npm install -g "@openai/codex@${CODEX_VERSION}" \
    && codex --version \
    && rm -rf /tmp/npm-cache

RUN pip3 install --no-cache-dir --break-system-packages "mcp==1.30.0" "aiohttp>=3.13,<4"

RUN case "${BUILD_ARCH}" in \
        amd64) HA_ARCH="amd64" ;; \
        aarch64) HA_ARCH="aarch64" ;; \
        *) HA_ARCH="amd64" ;; \
    esac && \
    curl -fsSL "https://github.com/home-assistant/cli/releases/latest/download/ha_${HA_ARCH}" -o /usr/local/bin/ha && \
    chmod +x /usr/local/bin/ha

RUN adduser -D -H -u 22000 -G root codex && \
    mkdir -p \
    /data/codex-home \
    /data/codex-managed \
    /homeassistant \
    /root/.local/bin

COPY rootfs/ /

# Extend the verified ttyd client once at build time; no CDN or runtime patching.
COPY terminal/ /tmp/codex-terminal/
RUN python3 /tmp/codex-terminal/build.py /usr/bin/ttyd /usr/share/codex/terminal.html \
    && rm -rf /tmp/codex-terminal

RUN chmod +x \
    /usr/local/bin/ha-mcp \
    /usr/local/bin/codex-ha-helper \
    /usr/local/bin/ha-api \
    /usr/local/bin/codex-merge-config \
    /usr/local/bin/codex-shell \
    /usr/local/bin/codex-select-cli \
    /usr/local/bin/codex-session \
    /usr/local/bin/codex-start \
    /usr/local/bin/codex-web \
    && chmod 440 /etc/sudoers.d/codex-ha

RUN cat > /etc/tmux.conf << 'EOF'
set -g history-limit 5000
set -ga terminal-overrides ',xterm*:smcup@:rmcup@'
set -g mouse off
set -g xterm-keys on
set -s set-clipboard on
set -g allow-passthrough on
EOF

RUN ln -sf /etc/tmux.conf /root/.tmux.conf

RUN cat > /etc/codex.bashrc << 'EOF'
export TERM=xterm-256color
export LANG=C.UTF-8
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
PS1='\[\033[1;36m\]codex\[\033[0m\]:\[\033[1;34m\]\w\[\033[0m\]\$ '

alias ll='ls -la'
alias ha-config='cd /homeassistant'
alias ha-logs='ha-api supervisor GET /core/logs'
EOF

RUN echo 'source /etc/codex.bashrc' > /root/.profile

ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /homeassistant

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -sf http://localhost:7681/ >/dev/null || exit 1

ENTRYPOINT []
CMD ["/usr/local/bin/codex-start"]
