"""One-shot Phase 0 check. Prints model replies and the embedding size, never secrets."""

import json
import os
import sys
import urllib.request

from dotenv import load_dotenv
from google import genai
from openai import OpenAI

load_dotenv()


def require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"MISSING {name}")
        sys.exit(1)
    return value


def main() -> None:
    openai_model = require("OPENAI_MODEL")
    gemini_model = require("GEMINI_MODEL")
    embedding_model = require("OPENAI_EMBEDDING_MODEL")
    require("OPENAI_API_KEY")
    require("GOOGLE_API_KEY")
    require("TAVILY_API_KEY")

    openai_client = OpenAI()
    openai_response = openai_client.responses.create(
        model=openai_model,
        input="Reply with the single word pong.",
        reasoning={"effort": "low"},
        max_output_tokens=256,
    )
    openai_text = (openai_response.output_text or "").strip().replace("\n", " ")
    print(f"OPENAI {openai_model}: {openai_text[:120]}")

    gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    gemini_response = gemini_client.models.generate_content(
        model=gemini_model,
        contents="Reply with the single word pong.",
    )
    gemini_text = (gemini_response.text or "").strip().replace("\n", " ")
    print(f"GEMINI {gemini_model}: {gemini_text[:120]}")

    embedding = openai_client.embeddings.create(
        model=embedding_model,
        input="PEP 8 import layout",
    )
    vector = embedding.data[0].embedding
    print(f"EMBEDDING {embedding_model}: dims={len(vector)}")

    tavily_body = json.dumps(
        {
            "api_key": os.environ["TAVILY_API_KEY"],
            "query": "Python PEP 8",
            "max_results": 1,
            "search_depth": "basic",
        }
    ).encode()
    tavily_request = urllib.request.Request(
        "https://api.tavily.com/search",
        data=tavily_body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(tavily_request, timeout=30) as tavily_response:
        tavily_payload = json.load(tavily_response)
    result_count = len(tavily_payload.get("results") or [])
    print(f"TAVILY search: results={result_count}")

    import chromadb
    import fastapi
    import langchain
    import langchain_mcp_adapters
    import langgraph
    import mcp
    import ragas
    from importlib.metadata import version

    print(
        "IMPORTS ok "
        f"fastapi={version('fastapi')} "
        f"langchain={version('langchain')} "
        f"langgraph={version('langgraph')} "
        f"chromadb={version('chromadb')} "
        f"ragas={version('ragas')} "
        f"mcp={version('mcp')} "
        f"mcp_adapters={langchain_mcp_adapters.__name__} "
        f"modules={fastapi.__name__},{langgraph.__name__},{mcp.__name__},{chromadb.__name__},{ragas.__name__},{langchain.__name__}"
    )


if __name__ == "__main__":
    main()
