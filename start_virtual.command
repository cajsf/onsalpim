#!/bin/bash
# 보드 없이 가상 세대(101·102·104·105호)로 개발할 때 (Mac). 시연에는 start_real.command
# 가상 세대는 공용 서버에 h101·h102·h104·h105 를 실물 보드와 같은 구조로 만든다
exec "$(dirname "$0")/start_real.command" virtual
