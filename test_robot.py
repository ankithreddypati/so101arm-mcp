# test_robot_chat.py
import os, json
from dotenv import load_dotenv

from groq import Groq


# Import functions you defined in server.py
from server import move_pose, presenting_talk, listening, thinking, talk

load_dotenv()

MODEL = os.getenv("MODEL")

# ---- client ----
client = Groq(api_key=os.getenv("GROQ_API_KEY"))



# ---- tool schema for Chat Completions ----
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "move_to_pose",
            "description": "Move robot to a saved pose by name (instant or smooth).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "pose name in saved_positions.json"},
                    "duration": {"type": "number", "default": 1.5},
                    "fps": {"type": "number", "default": 30},
                    "settle": {"type": "number", "default": 0.0},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "presenting_talk",
            "description": "Smoothly go to 'presenting' then flap gripper for N seconds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number"},
                    "settle": {"type": "number", "default": 1.0},
                    "dwell": {"type": "number", "default": 0.25},
                },
                "required": ["seconds"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listening",
            "description": "Smoothly go to 'presenting' then nod for N seconds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number"},
                    "settle": {"type": "number", "default": 1.0},
                    "dwell": {"type": "number", "default": 0.3},
                    "delta": {"type": "number", "default": 15.0},
                },
                "required": ["seconds"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "thinking",
            "description": "Roll wrist back and forth to simulate thinking for N seconds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number"},
                    "dwell": {"type": "number", "default": 0.6},
                    "roll_hi": {"type": "number", "default": 25.8},
                    "roll_lo": {"type": "number", "default": -30.4},
                },
                "required": ["seconds"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "talking",
            "description": "Flap gripper for N seconds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number"},
                    "dwell": {"type": "number", "default": 0.25},
                },
                "required": ["seconds"],
                "additionalProperties": False,
            },
        },
    },
]

# Map tool calls to your local Python functions (return JSON strings)
FUNCTIONS = {
    "move_to_pose": lambda name, duration=1.5, fps=30, settle=0.0: json.dumps(
        {"ok": bool(move_pose(name, duration, fps, settle)), "pose": name}
    ),
    "presenting_talk": lambda seconds, settle=1.0, dwell=0.25: json.dumps(
        {"ok": bool(presenting_talk(seconds, settle, dwell)), "seconds": seconds}
    ),
    "listening": lambda seconds, settle=1.0, dwell=0.3, delta=15.0: json.dumps(
        {"ok": bool(listening(seconds, settle, dwell, delta)), "seconds": seconds}
    ),
    "thinking": lambda seconds, dwell=0.6, roll_hi=25.8, roll_lo=-30.4: json.dumps(
        {"ok": bool(thinking(seconds, dwell, roll_hi, roll_lo)), "seconds": seconds}
    ),
    "talking": lambda seconds, dwell=0.25: json.dumps(
        {"ok": bool(talk(seconds, dwell)), "seconds": seconds}
    ),
}

def run(prompt: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system",
             "content": "You control a physical robot arm through tools. Always use a tool to perform actions."},
            {"role": "user", "content": prompt},
        ],
        tools=TOOLS,
        tool_choice="required",   
        temperature=0.0,
        max_completion_tokens=512,
    )

    msg = resp.choices[0].message
    tool_calls = msg.tool_calls or []
    if not tool_calls:
        return "(no tool call?)"

    messages = [
        {"role": "system",
         "content": "You control a physical robot arm through tools. Always use a tool to perform actions."},
        {"role": "user", "content": prompt},
        msg, 
    ]

    for call in tool_calls:
        fn = call.function.name
        args = json.loads(call.function.arguments or "{}")
        print(f"🔧 {fn}({args})")
        runner = FUNCTIONS.get(fn)
        if not runner:
            out = json.dumps({"ok": False, "error": f"unknown tool {fn}"})
        else:
            out = runner(**args)

        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "name": fn,
            "content": out,
        })

    final = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.0,
        max_completion_tokens=256,
    )
    return final.choices[0].message.content or "(done)"

if __name__ == "__main__":
    print(run("Move to the 'presenting' pose, then talk for 4 seconds."))
    print(run("Listen for 3 seconds."))
    print(run("Think for 5 seconds."))
    print(run("Finally, move to the 'rest' pose."))

