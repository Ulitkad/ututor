#!/bin/sh
# Run from the repository root: sh deploy/init.sh
set -eu
umask 077
mkdir -p data
if [ ! -e .admin_credentials ]; then
    touch .admin_credentials
fi
chmod 600 .admin_credentials
if [ ! -e .env ]; then
    cat > .env <<EOF
JWT_SECRET=$(openssl rand -hex 32)
APP_PORT=8080
COOKIE_SECURE=false
LOCAL_UID=$(id -u)
LOCAL_GID=$(id -g)
EOF
    printf '%s\n' 'Created .env with a random JWT secret.'
fi
printf '%s\n' 'Ready. Run: docker compose up --build -d'
