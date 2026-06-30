#!/bin/zsh
set -eu

LOCAL_PROXY_HOST="127.0.0.1"
LOCAL_PROXY_PORT="3128"
REMOTE_BIND_HOST="127.0.0.1"
REMOTE_TUNNEL_PORT="3129"
REMOTE_HOST="5.42.110.57"
REMOTE_USER="paylakurusyan"
SSH_KEY="$HOME/.ssh/elixirshop_tunnel_ed25519"

for _ in {1..60}; do
  if /usr/bin/nc -z "$LOCAL_PROXY_HOST" "$LOCAL_PROXY_PORT" >/dev/null 2>&1; then
    break
  fi
  /bin/sleep 2
done

exec /usr/bin/ssh \
  -i "$SSH_KEY" \
  -o BatchMode=yes \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=accept-new \
  -N \
  -R "$REMOTE_BIND_HOST:$REMOTE_TUNNEL_PORT:$LOCAL_PROXY_HOST:$LOCAL_PROXY_PORT" \
  "$REMOTE_USER@$REMOTE_HOST"
