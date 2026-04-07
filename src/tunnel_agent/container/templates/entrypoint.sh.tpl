#!/bin/bash
set -e

# --- Step 1: Start redsocks ---
redsocks -c /etc/redsocks.conf
sleep 0.5

# --- Step 2: Resolve proxy domains to IPs ---
PROXY_DOMAINS="${proxy_domains}"
PROXY_IPS_MANUAL="${proxy_ips_manual}"

RESOLVED_IPS=""
if [ -n "$$PROXY_IPS_MANUAL" ]; then
    RESOLVED_IPS="$$PROXY_IPS_MANUAL"
else
    for domain in $$PROXY_DOMAINS; do
        ips=$$(dig +short "$$domain" 2>/dev/null | grep -E '^[0-9]+\.' || true)
        if [ -z "$$ips" ]; then
            echo "Warning: could not resolve $$domain"
        fi
        RESOLVED_IPS="$$RESOLVED_IPS $$ips"
    done
fi

# --- Step 3: iptables NAT rules ---
for ip in $$RESOLVED_IPS; do
    iptables -t nat -A OUTPUT -d "$$ip" -p tcp -j REDIRECT --to-port 12345
done

# --- Step 4: Fix SSH key permissions ---
if [ -d "${home_dir}/.ssh-mount" ]; then
    cp -r "${home_dir}/.ssh-mount" "${home_dir}/.ssh"
    chmod 700 "${home_dir}/.ssh"
    chmod 600 "${home_dir}/.ssh/"* 2>/dev/null || true
    chown -R ${run_as_user}:${run_as_user} "${home_dir}/.ssh"
fi

# --- Step 5: Source environment variables from .env ---
if [ -f /app/.env ]; then
    set -a
    . /app/.env
    set +a
fi

# --- Step 6: Launch agent as non-root ---
exec gosu ${run_as_user} "$$@"
