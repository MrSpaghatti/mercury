import time
import uuid
import json
from pathlib import Path
from hermes_state import SessionDB

db = SessionDB(Path("test_bench.db"))
session_id = "test_session_" + str(uuid.uuid4())

db.create_session(session_id=session_id, source="benchmark")

tool_calls_raw = [
    {
        "id": str(uuid.uuid4()),
        "type": "function",
        "function": {
            "name": "search",
            "arguments": json.dumps({"query": f"dummy search query {i}", "num_results": 10, "offset": i})
        }
    }
    for i in range(5)
]

# Insert more messages to have a better benchmark baseline
for _ in range(50000):
    db.append_message(
        session_id=session_id,
        role="assistant",
        content="Here are the search results you requested.",
        tool_calls=tool_calls_raw
    )

print("Starting benchmark for get_messages...")
start = time.perf_counter()
messages = db.get_messages(session_id)
end = time.perf_counter()

print(f"get_messages baseline (50000 messages with tool_calls): {end - start:.4f}s")

print("Starting benchmark for get_messages_as_conversation...")
start = time.perf_counter()
messages_conv = db.get_messages_as_conversation(session_id)
end = time.perf_counter()

print(f"get_messages_as_conversation baseline (50000 messages with tool_calls): {end - start:.4f}s")

db.close()
import os
os.remove("test_bench.db")
