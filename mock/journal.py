import json
import os
import urllib.request

MOCK_URL = os.environ.get("MOCK_URL", "http://host.docker.internal:1080")
SHOWN_FIELDS = ("final_amount", "monthly_remaining_eur", "eligible", "error")

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def recorded_requests() -> list[dict]:
    req = urllib.request.Request(
        f"{MOCK_URL}/mockserver/retrieve?type=REQUESTS",
        data=b'{"path": ".*/chat/completions"}', method="PUT",
        headers={"Content-Type": "application/json"})
    with _opener.open(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def describe(number: int, request: dict) -> str:
    body = request["body"]
    body = body.get("json", body) if isinstance(body, dict) else json.loads(body)
    last = body["messages"][-1]
    if last["role"] == "tool":
        result = json.loads(last["content"])
        shown = {k: result[k] for k in SHOWN_FIELDS if k in result}
        return (f"#{number}  tool result back to the model   "
                f"{last['tool_call_id']}  {json.dumps(shown)}")
    return (f"#{number}  question to the model            "
            f"tools={len(body.get('tools', []))}  {str(last['content'])[:64]!r}")


def main() -> None:
    requests = recorded_requests()
    print(f"{len(requests)} requests reached the mock instead of the model")
    for number, request in enumerate(requests, 1):
        print(describe(number, request))


if __name__ == "__main__":
    main()
