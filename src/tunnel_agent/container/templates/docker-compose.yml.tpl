services:
  tunnel:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ${project_name}
    cap_add:
      - NET_ADMIN
    sysctls:
      - net.ipv4.conf.all.src_valid_mark=1
    devices:
      - /dev/net/tun:/dev/net/tun
    volumes:
      - ${workspace_path}:/workspace
      - ${env_file}:/app/.env:ro
      ${ssh_mount}
      ${claude_mount}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    working_dir: /workspace
    stdin_open: true
    tty: true
