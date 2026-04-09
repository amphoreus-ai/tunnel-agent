services:
  tunnel:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ${project_name}
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
    volumes:
      - ${workspace_path}:/workspace
      - ${env_file}:/app/.env:ro
      ${ssh_mount}
      ${claude_mount}
      ${extra_mounts}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    working_dir: /workspace
    stdin_open: true
    tty: true
    ${gpu_config}
