#!/bin/sh
# Renders the NGINX config, makes sure a TLS certificate exists, then runs the given command
# (nginx by default; `nginx -t` to validate the configuration).
set -eu

: "${GATEWAY_HTTPS_PORT:=8443}"
export GATEWAY_HTTPS_PORT

# Substitute ONLY this variable, so NGINX's own $host, $request_uri, ... are left alone
envsubst '${GATEWAY_HTTPS_PORT}' < /etc/qav/nginx.conf.template > /etc/nginx/nginx.conf

CERT_DIR=/etc/nginx/certs
mkdir -p "$CERT_DIR"
if [ ! -s "$CERT_DIR/tls.crt" ] || [ ! -s "$CERT_DIR/tls.key" ]; then
  echo "qav-gateway: generating a self-signed certificate for localhost"
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,DNS:gateway,DNS:host.docker.internal" \
    -keyout "$CERT_DIR/tls.key" -out "$CERT_DIR/tls.crt" 2>/dev/null
fi

exec "$@"
