#!/usr/bin/env bash
set -euo pipefail
systemctl is-enabled youbun-collector.timer
systemctl is-active youbun-collector.timer
systemctl list-timers youbun-collector.timer --no-pager
journalctl -u youbun-collector.service -n 20 --no-pager
