base {
    log_debug = off;
    log_info = on;
    daemon = yes;
    redirector = iptables;
}

redsocks {
    local_ip = 127.0.0.1;
    local_port = 12345;
    ip = ${proxy_host};
    port = ${proxy_port};
    type = socks5;
}
