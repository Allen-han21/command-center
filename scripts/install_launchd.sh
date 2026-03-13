#!/bin/bash
# Command Center launchd 등록 스크립트 (10분 간격 자동 dispatch)

set -euo pipefail

PLIST_LABEL="com.dominium.command-center"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
PROJECT_DIR="$HOME/Dev/personal/command-center"
LOG_DIR="$HOME/.claude/command-center"

# uv 환경의 Python 경로 확인
if command -v uv &>/dev/null && [ -f "$PROJECT_DIR/pyproject.toml" ]; then
    PYTHON_BIN="$(cd "$PROJECT_DIR" && uv run python -c 'import sys; print(sys.executable)')"
else
    PYTHON_BIN="$(which python3)"
fi

mkdir -p "$LOG_DIR"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_BIN}</string>
        <string>-m</string>
        <string>command_center.dispatcher</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <key>StartInterval</key>
    <integer>600</integer>

    <key>RunAtLoad</key>
    <false/>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/launchd_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/launchd_stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>${PROJECT_DIR}/src</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
EOF

echo "Plist 생성: $PLIST_PATH"
echo "Python: $PYTHON_BIN"

# 기존 plist 언로드 (있으면)
launchctl unload "$PLIST_PATH" 2>/dev/null && echo "기존 plist 언로드" || true

# 새 plist 로드
launchctl load "$PLIST_PATH"

echo ""
echo "launchd 등록 완료: $PLIST_LABEL (600초 = 10분 간격)"
echo ""
echo "유용한 명령어:"
echo "  상태 확인:  launchctl list | grep command-center"
echo "  수동 실행:  launchctl start $PLIST_LABEL"
echo "  중지:       launchctl unload $PLIST_PATH"
echo "  로그 확인:  tail -f $LOG_DIR/dispatcher.log"
