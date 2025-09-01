#!/bin/bash
# wait-for-mysql.sh

set -e

host="${MYSQL_HOST:-localhost}"
port="${MYSQL_PORT:-3306}"
user="${MYSQL_USER:-root}"
password="${MYSQL_PASSWORD:-root_password}"
database="${MYSQL_DATABASE:-vendor_categorization}"
cmd="$@"

echo "Waiting for MySQL to be available at $host:$port..."

# Simple TCP connection check using netcat
apt-get update && apt-get install -y netcat-traditional

# Wait for MySQL to be ready
max_attempts=60
attempt=0
while [ $attempt -lt $max_attempts ]; do
  if nc -z "$host" "$port"; then
    echo "MySQL port is open, waiting a few more seconds for full initialization..."
    sleep 5
    break
  fi
  >&2 echo "MySQL is unavailable - sleeping (attempt $((attempt+1))/$max_attempts)"
  sleep 2
  attempt=$((attempt+1))
done

if [ $attempt -eq $max_attempts ]; then
  >&2 echo "Error: Could not connect to MySQL after $max_attempts attempts"
  exit 1
fi

>&2 echo "MySQL is up - executing command"
exec $cmd
