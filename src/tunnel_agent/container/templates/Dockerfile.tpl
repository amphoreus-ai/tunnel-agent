FROM debian:bookworm-slim

RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null; true

RUN apt-get update && apt-get install -y --no-install-recommends \
    wireguard-tools \
    iproute2 \
    gosu \
    openssh-client \
    git \
    curl \
    ca-certificates \
    ${system_packages} \
    && rm -rf /var/lib/apt/lists/*

RUN ${cli_install_cmd}

RUN groupadd -r ${run_as_user} \
    && useradd -r -g ${run_as_user} -m -d ${home_dir} -s /bin/bash ${run_as_user} \
    && mkdir -p /workspace \
    && chown ${run_as_user}:${run_as_user} /workspace

${env_vars}

COPY entrypoint.sh /entrypoint.sh
COPY wg0.conf /etc/wireguard/wg0.conf

RUN chmod +x /entrypoint.sh && chmod 600 /etc/wireguard/wg0.conf

WORKDIR /workspace
ENTRYPOINT ["/entrypoint.sh"]
