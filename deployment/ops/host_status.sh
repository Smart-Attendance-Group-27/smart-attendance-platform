#!/usr/bin/env bash
set -euo pipefail

printf 'UTC: '; date -u +%Y-%m-%dT%H:%M:%SZ
printf '\nMemory:\n'; free -h
printf '\nDisk:\n'; df -h /
printf '\nContainers:\n'; docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
printf '\nUsage:\n'; docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'
