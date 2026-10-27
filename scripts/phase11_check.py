"""Time the deployed stream. Prints status and timings, never secrets."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

URL = sys.argv[1] if len(sys.argv) > 1 else "https://multi-agent-rag-749179608015.us-west1.run.app"
QUESTIONS = [
    ("cold", "What does PEP 8 say about imports?"),
    ("warm", "How many PEPs in the table have status Final?"),
]


def health() -> dict:
    started = time.perf_counter()
    with urllib.request.urlopen(URL + "/health", timeout=120) as response:
        body = response.read().decode("utf-8")
    elapsed = round((time.perf_counter() - started) * 1000, 1)
    payload = json.loads(body)
    print(f"health {response.status} {elapsed} ms {json.dumps(payload)}")
    if not payload.get("ok") or not payload.get("chroma_count"):
        raise SystemExit("health is not green")
    if not payload.get("providers_configured"):
        raise SystemExit("providers are not configured")
    blob = json.dumps(payload).lower()
    for marker in ("sk-", "aiza", "tvly-"):
        if marker in blob:
            raise SystemExit("health returned a secret")
    return payload


def first_token(label: str, question: str) -> None:
    payload = json.dumps({"query": question, "history": []}).encode("utf-8")
    request = urllib.request.Request(
        URL + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    started = time.perf_counter()
    ttft = None
    kinds = []
    answer = []
    route = None
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            if response.status != 200:
                raise SystemExit(f"{label} status {response.status}")
            buffer = ""
            while True:
                chunk = response.read(256)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n\n" in buffer:
                    frame, buffer = buffer.split("\n\n", 1)
                    if frame.startswith(":"):
                        continue
                    event = "message"
                    data = ""
                    for line in frame.splitlines():
                        if line.startswith("event:"):
                            event = line.split(":", 1)[1].strip()
                        elif line.startswith("data:"):
                            data += line.split(":", 1)[1].strip()
                    kinds.append(event)
                    if event == "token" and ttft is None:
                        ttft = round((time.perf_counter() - started) * 1000, 1)
                    if event == "token" and data:
                        try:
                            answer.append(json.loads(data).get("text") or "")
                        except json.JSONDecodeError:
                            pass
                    if event == "route" and route is None and data:
                        route = json.loads(data)
                    if event == "done":
                        break
                if kinds and kinds[-1] == "done":
                    break
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{label} HTTP {exc.code} {exc.read()[:200]!r}") from exc
    elapsed = round((time.perf_counter() - started) * 1000, 1)
    text = "".join(answer).strip()
    print(f"{label} ttft_ms={ttft} wall_ms={elapsed} events={kinds[:8]}")
    print(f"{label} route={route}")
    print(f"{label} answer={text[:400]}")
    if ttft is None or not text:
        raise SystemExit(f"{label} did not stream an answer")
    if not route or not route.get("provider") or not route.get("reason"):
        raise SystemExit(f"{label} route did not name a provider and a reason")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("url", URL)
    for label, question in QUESTIONS:
        first_token(label, question)
    health()


if __name__ == "__main__":
    main()
