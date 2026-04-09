#!/bin/bash
set -e

# --- Step 1: Create TUN device if missing ---
if [ ! -d /dev/net ]; then
    mkdir -p /dev/net
fi
if [ ! -c /dev/net/tun ]; then
    mknod /dev/net/tun c 10 200
    chmod 600 /dev/net/tun
fi

# --- Step 2: Start WireGuard ---
wg-quick up wg0
echo "WireGuard tunnel active"

# --- Step 3: Fix SSH key permissions ---
if [ -d "${home_dir}/.ssh-mount" ]; then
    cp -r "${home_dir}/.ssh-mount" "${home_dir}/.ssh"
    chmod 700 "${home_dir}/.ssh"
    chmod 600 "${home_dir}/.ssh/"* 2>/dev/null || true
    chown -R ${run_as_user}:${run_as_user} "${home_dir}/.ssh"
fi

# --- Step 4: Source environment variables from .env ---
if [ -f /app/.env ]; then
    set -a
    . /app/.env
    set +a
fi

# --- Step 5: Launch agent as non-root ---
exec gosu ${run_as_user} "$$@"
