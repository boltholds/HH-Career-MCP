FROM debian:bookworm-slim

ARG TARGETARCH
ARG TUNNEL_CLIENT_VERSION=0.0.10
ARG TUNNEL_CLIENT_SHA256_AMD64=b9e0388a343f2d7adeff3992f411a0bd3d916a64bc56534aac5fd15ac1b20cd5
ARG TUNNEL_CLIENT_SHA256_ARM64=b842a9b2352eebd80514cf01a1fbb1c0d400a7d24a4015e85a7ea5f1aeaa5b30

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && case "$TARGETARCH" in \
         amd64) checksum="$TUNNEL_CLIENT_SHA256_AMD64" ;; \
         arm64) checksum="$TUNNEL_CLIENT_SHA256_ARM64" ;; \
         *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && archive="tunnel-client-v${TUNNEL_CLIENT_VERSION}-linux-${TARGETARCH}.zip" \
    && curl --fail --location --retry 3 \
       "https://github.com/openai/tunnel-client/releases/download/v${TUNNEL_CLIENT_VERSION}/${archive}" \
       --output "/tmp/${archive}" \
    && echo "${checksum}  /tmp/${archive}" | sha256sum --check - \
    && unzip "/tmp/${archive}" -d /tmp/tunnel-client \
    && find /tmp/tunnel-client -type f -name tunnel-client \
       -exec install -m 0755 {} /usr/local/bin/tunnel-client \; \
    && test -x /usr/local/bin/tunnel-client \
    && rm -rf /tmp/tunnel-client "/tmp/${archive}" /var/lib/apt/lists/*

COPY docker/tunnel/entrypoint.sh /usr/local/bin/tunnel-entrypoint

RUN sed -i 's/\r$//' /usr/local/bin/tunnel-entrypoint \
    && chmod 0755 /usr/local/bin/tunnel-entrypoint \
    && useradd --create-home --uid 10002 tunnel \
    && mkdir -p /data/tunnel-client \
    && chown -R tunnel:tunnel /data/tunnel-client

USER tunnel
EXPOSE 8080
ENTRYPOINT ["tunnel-entrypoint"]
