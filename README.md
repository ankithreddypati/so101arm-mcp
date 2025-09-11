# SO101 Arm MCP Server

![SO101 Arm Demo](assets/output2.gif)

A Model Context Protocol (MCP) server for controlling SO101 robotic arms through natural language commands. This project enables seamless interaction with robotic hardware using AI-powered tool calling and the MCP specification.

## 🛠️ Setup

### Prerequisites
- Python 3.8+
- SO101 robotic arm
- USB connection to robot

### Installation

1. **Create and activate virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Find robot port:**
```bash
python3 -m lerobot.find_port
```

4. **Configure environment:**
   - Copy `.envsample` to `.env`
   - Add your robot port and ID to the `.env` file

5. **Calibrate robot (first time only):**
```bash
uv run -m lerobot.calibrate \
    --robot.type=so101_follower \
    --robot.port=/dev/tty.usbmodem5A7A0592641 \
    --robot.id=mythos_arm
```

## 🎮 Usage

### Starting the MCP Server

```bash
python3 server.py
```

The server will start on `http://127.0.0.1:8000/sse` and provide MCP-compatible endpoints.

### LM Studio Integration

Add to your `mcp.json`:
```json
{
  "mcpServers": {
    "so101arm": {
      "url": "http://127.0.0.1:8000/sse",
      "headers": {}
    }
  }
}
```

Enable the MCP integration in LM Studio and start chatting with your robot!

### Direct Testing

Test the robot with Groq's tool calling:
```bash
python3 test_robot.py
```

Make sure to add your `GROQ_API_KEY` and `MODEL` to the `.env` file.

##  Available Commands

The MCP server provides several tools for robot control as this was just a demo for a hackathon to act like puppet:

- **`move_to_pose`**: Move to saved positions with smooth interpolation
- **`presenting_talk`**: Gesture while "speaking" (nodding motion)
- **`listening`**: Attentive pose for listening
- **`thinking`**: Contemplative pose with slight movements
- **`talk`**: Conversational gestures
- **`save_pose`**: Save current robot position for later use
- **`get_robot_state`**: Get current robot status and position


## Configuration

### Environment Variables

Create a `.env` file with:
```env
ROBOT_PORT=/dev/tty.usbmodem5A7A0592641
ROBOT_ID=mythos_arm
GROQ_API_KEY=your_groq_api_key
MODEL=llama-3.1-70b-versatile
```

### Saved Positions

Robot poses are automatically saved to `saved_positions.json`. You can:
- Save poses using the `save_pose` tool
- Move to saved poses using the `move_to_pose` tool
- Manually edit the JSON file for custom positions


##  References

- [MCP Specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- [Groq Tool Use Documentation](https://console.groq.com/docs/tool-use)
- [LeRobot Documentation](https://huggingface.co/docs/lerobot/)
