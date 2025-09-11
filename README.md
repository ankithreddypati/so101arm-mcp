# so101arm-mcp

MCP server for controlling SO101 robotic arm and perform simple actions via Model Context Protocol and ToolUse.

## Setup

1. Install dependencies:
```bash
uv pip install -r requirements.txt
```

2. Connect robot and find port:
```bash
uv run -m lerobot.find_port
```

3. Add port to `.envsample` file and rename to `.env`

4. Calibrate robot (skip if already calibrated):
```bash
uv run -m lerobot.calibrate \
    --robot.type=so101_follower \
    --robot.port=/dev/tty.usbmodem5A7A0592641 \
    --robot.id=mythos_arm
```

## Usage

Start MCP server:
```bash
uv run server.py
```

Test robot:
```bash
uv run test_robot.py
```

Add your LLM API key and model name to `.env` file before testing.

## References

[MCP Specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)

[ToolUse](https://console.groq.com/docs/tool-use)