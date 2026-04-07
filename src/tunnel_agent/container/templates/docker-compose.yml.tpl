services:
  tunnel:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ${project_name}
    cap_add:
      - NET_ADMIN
    volumes:
      - ${workspace_path}:/workspace
      - ${env_file}:/app/.env:ro
      ${ssh_mount}
      ${claude_mount}
    environment:
      - PROXY_HOST=${proxy_host}
      - PROXY_PORT=${proxy_port}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    working_dir: /workspace
    stdin_open: true
    tty: true
