import json
import time
import uuid

# try to import orjson and ujson
try:
    import orjson
except ImportError:
    orjson = None
    print("orjson not installed")
try:
    import ujson
except ImportError:
    ujson = None
    print("ujson not installed")

# generate a bunch of dummy tool calls
tool_calls_raw = [
    {
        "id": str(uuid.uuid4()),
        "type": "function",
        "function": {
            "name": "search",
            "arguments": json.dumps({"query": f"dummy search query {i}", "num_results": 10, "offset": i})
        }
    }
    for i in range(10)
]

tool_calls_str = json.dumps(tool_calls_raw)

N = 100000

# Benchmark json.loads
start = time.perf_counter()
for _ in range(N):
    json.loads(tool_calls_str)
end = time.perf_counter()
print(f"json.loads: {end - start:.4f}s")

# Benchmark orjson.loads
if orjson:
    start = time.perf_counter()
    for _ in range(N):
        orjson.loads(tool_calls_str)
    end = time.perf_counter()
    print(f"orjson.loads: {end - start:.4f}s")

# Benchmark ujson.loads
if ujson:
    start = time.perf_counter()
    for _ in range(N):
        ujson.loads(tool_calls_str)
    end = time.perf_counter()
    print(f"ujson.loads: {end - start:.4f}s")
