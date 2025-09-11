# server.py
import os, time, json, socket, atexit, threading
from pathlib import Path
from dotenv import load_dotenv
from lerobot.robots.so101_follower import SO101Follower, SO101FollowerConfig
from mcp.server.fastmcp import FastMCP

# ---- env & constants ----
load_dotenv()
POSE_FILE = Path("saved_positions.json")
_PERSIST = True  # True = keep one robot connection alive for the whole process

# ---- utilities ----
def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def _cfg():
    port = os.getenv("ROBOT_PORT")
    rid  = os.getenv("ROBOT_ID")
    if not port or not rid:
        raise RuntimeError(".env missing ROBOT_PORT or ROBOT_ID")
    return SO101FollowerConfig(port=port, id=rid)

def _load_poses() -> dict:
    if not POSE_FILE.exists():
        return {}
    with POSE_FILE.open("r") as f:
        return json.load(f)

def _valid_keys(robot: SO101Follower) -> set:
    obs = robot.get_observation()
    return {k for k in obs.keys() if k.endswith(".pos")}

def _ease_in_out_quad(t: float) -> float:
    return 2*t*t if t < 0.5 else 1 - ((-2*t + 2)**2)/2

# ---- persistent robot session (thread-safe) ----
_ROBOT = None
_LOCK = threading.Lock()

def _get_robot() -> SO101Follower:
    """Return a connected robot. If _PERSIST=True, reuse one connection."""
    global _ROBOT
    if not _PERSIST:
        r = SO101Follower(_cfg())
        r.connect(calibrate=False)
        return r
    with _LOCK:
        if _ROBOT is None:
            _ROBOT = SO101Follower(_cfg())
            _ROBOT.connect(calibrate=False)
        return _ROBOT

def _release_robot(r: SO101Follower):
    """Release robot if not using persistent mode."""
    global _ROBOT
    if _PERSIST:
        return  # keep alive
    try:
        r.disconnect()
    except Exception:
        pass

def _cleanup_robot():
    """Always disconnect on process exit for safety."""
    global _ROBOT
    with _LOCK:
        if _ROBOT is not None:
            try:
                _ROBOT.disconnect()
            except Exception:
                pass
            _ROBOT = None

atexit.register(_cleanup_robot)

# ---------- single mover (instant or smooth) ----------
def move(target: dict, duration: float = 1.5, fps: int = 30, settle: float = 0.0) -> bool:
    """
    Move to target pose.
      - duration <= 0 => instant send
      - duration  > 0 => smooth interpolation with easing
    """
    r = _get_robot()
    try:
        keys = _valid_keys(r)
        target = {k: v for k, v in target.items() if k in keys}
        if not target:
            print("⚠️ nothing to move (no valid keys)")
            return False

        if duration <= 0:
            r.send_action(target)
            if settle > 0: time.sleep(settle)
            return True

        # smooth interpolation
        obs = r.get_observation()
        start = {k: obs[k] for k in obs if k.endswith(".pos")}
        joint_keys = sorted(set(start.keys()) & set(target.keys()))
        if not joint_keys:
            print("⚠️ no overlapping joints to move")
            return False

        steps = max(1, int(duration * fps))
        dt = duration / steps
        for i in range(1, steps + 1):
            t = i / steps
            et = _ease_in_out_quad(t)
            frame = {k: start[k] + (target[k] - start[k]) * et for k in joint_keys}
            r.send_action(frame)
            time.sleep(dt)
        if settle > 0: time.sleep(settle)
        return True
    finally:
        _release_robot(r)

def move_pose(name: str, duration: float = 1.5, fps: int = 30, settle: float = 0.0) -> bool:
    poses = _load_poses()
    pose = poses.get(name, {})
    if not pose:
        print(f"⚠️ missing pose: {name}")
        return False
    return move(pose, duration=duration, fps=fps, settle=settle)

# ---------- simple actions (seconds come from caller) ----------
def talk(seconds: float, dwell: float = 0.25) -> bool:
    """Flap gripper for `seconds`."""
    if seconds <= 0 or dwell <= 0:
        return True
    r = _get_robot()
    try:
        keys = _valid_keys(r)
        if "gripper.pos" not in keys:
            print("⚠️ no gripper.pos key")
            return False
        cycles = max(1, int(seconds / (2.0 * dwell)))
        open_pose  = {"gripper.pos": 12.7}
        close_pose = {"gripper.pos": 0.0}
        for _ in range(cycles):
            r.send_action(open_pose);  time.sleep(dwell)
            r.send_action(close_pose); time.sleep(dwell)
        return True
    finally:
        _release_robot(r)

def nod(seconds: float, dwell: float = 0.3, delta: float = 15.0) -> bool:
    """Nod for `seconds` using wrist_flex.pos ± delta."""
    if seconds <= 0 or dwell <= 0:
        return True
    r = _get_robot()
    try:
        keys = _valid_keys(r)
        if "wrist_flex.pos" not in keys:
            print("⚠️ no wrist_flex.pos key")
            return False
        base = r.get_observation().get("wrist_flex.pos", 0.0)
        up   = {"wrist_flex.pos": base + delta}
        down = {"wrist_flex.pos": base - delta}
        cycles = max(1, int(seconds / (2.0 * dwell)))
        for _ in range(cycles):
            r.send_action(down); time.sleep(dwell)
            r.send_action(up);   time.sleep(dwell)
        return True
    finally:
        _release_robot(r)

def presenting_talk(seconds: float, settle: float = 1.0, dwell: float = 0.25) -> bool:
    """Smoothly go to 'presenting' (settle sec), then talk for `seconds`."""
    poses = _load_poses()
    presenting = poses.get("presenting", {})
    if not presenting:
        print("⚠️ no presenting pose")
        return False
    if not move(presenting, duration=settle, fps=30, settle=0.0):
        return False
    return talk(seconds=seconds, dwell=dwell)

def listening(seconds: float, settle: float = 1.0, dwell: float = 0.3, delta: float = 15.0) -> bool:
    """Smoothly go to 'presenting' (settle sec), then nod for `seconds`."""
    poses = _load_poses()
    presenting = poses.get("presenting", {})
    if not presenting:
        print("⚠️ no presenting pose")
        return False
    if not move(presenting, duration=settle, fps=30, settle=0.0):
        return False
    return nod(seconds=seconds, dwell=dwell, delta=delta)

def thinking(seconds: float, dwell: float = 0.6, roll_hi: float = 25.8, roll_lo: float = -30.4) -> bool:
    """Roll wrist between hi/lo for `seconds`."""
    if seconds <= 0 or dwell <= 0:
        return True
    r = _get_robot()
    try:
        keys = _valid_keys(r)
        if "wrist_roll.pos" not in keys:
            print("⚠️ no wrist_roll.pos key")
            return False
        cycles = max(1, int(seconds / (2.0 * dwell)))
        hi_pose = {"wrist_roll.pos": float(roll_hi)}
        lo_pose = {"wrist_roll.pos": float(roll_lo)}
        for _ in range(cycles):
            r.send_action(lo_pose); time.sleep(dwell)
            r.send_action(hi_pose); time.sleep(dwell)
        return True
    finally:
        _release_robot(r)

# ---------- MCP server ----------
mcp = FastMCP("so101arm")

@mcp.tool()
def move_pose_tool(name: str, duration: float = 1.5, fps: int = 30, settle: float = 0.0) -> dict:
    """Move to a saved pose by name. duration<=0 => instant; >0 => smooth."""
    ok = move_pose(name=name, duration=duration, fps=fps, settle=settle)
    return {"ok": bool(ok), "pose": name, "duration": duration}

@mcp.tool()
def talking_tool(seconds: float, dwell: float = 0.25) -> dict:
    """Flap gripper for `seconds` (provided by upstream process)."""
    ok = talk(seconds=seconds, dwell=dwell)
    return {"ok": bool(ok), "seconds": seconds, "dwell": dwell}

@mcp.tool()
def listening_tool(seconds: float, settle: float = 1.0, dwell: float = 0.3, delta: float = 15.0) -> dict:
    """Smoothly enter 'presenting' (settle), then nod for `seconds`."""
    ok = listening(seconds=seconds, settle=settle, dwell=dwell, delta=delta)
    return {"ok": bool(ok), "seconds": seconds, "settle": settle}

@mcp.tool()
def presenting_talk_tool(seconds: float, settle: float = 1.0, dwell: float = 0.25) -> dict:
    """Smoothly enter 'presenting' (settle), then talk for `seconds`."""
    ok = presenting_talk(seconds=seconds, settle=settle, dwell=dwell)
    return {"ok": bool(ok), "seconds": seconds, "settle": settle}

@mcp.tool()
def thinking_tool(seconds: float, dwell: float = 0.6, roll_hi: float = 25.8, roll_lo: float = -30.4) -> dict:
    """Roll wrist hi/lo to simulate thinking for `seconds`."""
    ok = thinking(seconds=seconds, dwell=dwell, roll_hi=roll_hi, roll_lo=roll_lo)
    return {"ok": bool(ok), "seconds": seconds}

if __name__ == "__main__":
    # Single extra line for your convenience; MCP prints its own banner.
    print(f" Network URL (LAN): http://{get_local_ip()}:8000")
    mcp.run("sse")
