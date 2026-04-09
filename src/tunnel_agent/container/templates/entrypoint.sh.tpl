#!/bin/bash
set -e

# --- Step 1: Create TUN device if missing ---
mkdir -p /dev/net
[ -c /dev/net/tun ] || mknod /dev/net/tun c 10 200

# --- Step 2: Set up WireGuard manually (bypass wg-quick and its deps) ---
# Parse address and DNS from config
WG_ADDR=$$(grep -i '^Address' /etc/wireguard/wg0.conf | head -1 | sed 's/.*=\s*//' | cut -d',' -f1 | xargs)
WG_DNS=$$(grep -i '^DNS' /etc/wireguard/wg0.conf | head -1 | sed 's/.*=\s*//' | xargs)
WG_ENDPOINT=$$(grep -i '^Endpoint' /etc/wireguard/wg0.conf | head -1 | sed 's/.*=\s*//' | cut -d':' -f1 | xargs)

# Create stripped config (remove Interface-level keys that wg doesn't understand)
grep -iv '^\(Address\|DNS\|MTU\|SaveConfig\|PostUp\|PostDown\|Table\)' /etc/wireguard/wg0.conf > /tmp/wg0-stripped.conf

# Create interface and apply config
ip link add wg0 type wireguard
wg setconf wg0 /tmp/wg0-stripped.conf
ip address add "$$WG_ADDR" dev wg0
ip link set mtu 1420 up dev wg0

# Route all traffic through WireGuard, except traffic to the VPN endpoint itself
if [ -n "$$WG_ENDPOINT" ]; then
    ORIG_GW=$$(ip route show default | awk '{print $$3}')
    ORIG_DEV=$$(ip route show default | awk '{print $$5}')
    # Keep route to VPN server via original gateway
    ip route add "$$WG_ENDPOINT/32" via "$$ORIG_GW" dev "$$ORIG_DEV" 2>/dev/null || true
fi
# Default route through WireGuard
ip route replace default dev wg0

# Set DNS
if [ -n "$$WG_DNS" ]; then
    : > /etc/resolv.conf
    for dns in $$(echo "$$WG_DNS" | tr ',' ' '); do
        echo "nameserver $$dns" >> /etc/resolv.conf
    done
else
    echo "nameserver 1.1.1.1" > /etc/resolv.conf
fi

echo "WireGuard tunnel active ($$WG_ADDR → $$WG_ENDPOINT)"

# --- Step 3: Fix Claude config ownership + persistence ---
if [ -d "${home_dir}/.claude" ]; then
    chown -R ${run_as_user}:${run_as_user} "${home_dir}/.claude"
    # Symlink .claude.json into mounted dir so it persists across restarts
    if [ ! -e "${home_dir}/.claude.json" ] && [ -f "${home_dir}/.claude/.claude.json" ]; then
        ln -sf "${home_dir}/.claude/.claude.json" "${home_dir}/.claude.json"
    elif [ ! -e "${home_dir}/.claude.json" ]; then
        touch "${home_dir}/.claude/.claude.json"
        ln -sf "${home_dir}/.claude/.claude.json" "${home_dir}/.claude.json"
    fi
    chown ${run_as_user}:${run_as_user} "${home_dir}/.claude.json" 2>/dev/null || true
    # Restore from backup if available
    if [ ! -s "${home_dir}/.claude.json" ] && [ -d "${home_dir}/.claude/backups" ]; then
        BACKUP=$$(ls -t "${home_dir}/.claude/backups/.claude.json.backup."* 2>/dev/null | head -1)
        if [ -n "$$BACKUP" ]; then
            cp "$$BACKUP" "${home_dir}/.claude/.claude.json"
        fi
    fi
fi

# --- Step 4: Match container user UID to workspace owner ---
WORKSPACE_UID=$$(stat -c '%u' /workspace)
if [ "$$WORKSPACE_UID" != "0" ] && [ "$$WORKSPACE_UID" != "$$(id -u ${run_as_user})" ]; then
    usermod -u "$$WORKSPACE_UID" ${run_as_user} 2>/dev/null || true
    chown -R "$$WORKSPACE_UID" "${home_dir}" 2>/dev/null || true
fi
mkdir -p /workspace/.tmp
chown ${run_as_user}:${run_as_user} /workspace/.tmp

# --- Step 5: Fix SSH key permissions ---

if [ -d "${home_dir}/.ssh-mount" ]; then
    cp -r "${home_dir}/.ssh-mount" "${home_dir}/.ssh"
    chmod 700 "${home_dir}/.ssh"
    chmod 600 "${home_dir}/.ssh/"* 2>/dev/null || true
    chown -R ${run_as_user}:${run_as_user} "${home_dir}/.ssh"
fi

# --- Step 6: Source environment variables from .env ---
if [ -f /app/.env ]; then
    set -a
    . /app/.env
    set +a
fi

# --- Step 7: Launch agent as non-root ---
if [ $$# -eq 0 ]; then
    exec gosu ${run_as_user} sleep infinity
else
    exec gosu ${run_as_user} "$$@"
fi
