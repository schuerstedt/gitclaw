#!/usr/bin/env python3
"""
Azure LLM query script with OpenRouter fallback.

Usage:
    python llm.py --model <model> --prompt <prompt>
                  [--system <system_prompt>]
                  [--max-tokens <n>]
                  [--temperature <f>]
                  [--json]        # output raw JSON response
                  [--no-fallback] # disable OpenRouter fallback

Environment:
    AZURE_ENDPOINT   - Azure AI base URL
    AZURE_APIKEY     - Azure AI key
    OPENROUTER_API_KEY - OpenRouter key (for fallback)

Available models (Azure):
    model-router              (Azure AI model router — picks best model automatically)
    Kimi-K2.5
    grok-4-1-fast-non-reasoning
    grok-4-1-fast-reasoning
"""

import argparse
import json
import os
import sys
import time

try:
    from openai import OpenAI, AzureOpenAI, RateLimitError, APIStatusError
except ImportError:
    print("ERROR: openai package not installed. Run: pip install openai", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Model routing tables
# ---------------------------------------------------------------------------

# Azure deployments that use AzureOpenAI client (require api-version header)
AZURE_NATIVE_MODELS = {"model-router"}

# Azure deployments that use plain OpenAI client (OpenAI-compatible endpoint)
AZURE_OPENAI_COMPAT_MODELS = {
    "Kimi-K2.5",
    "grok-4-1-fast-non-reasoning",
    "grok-4-1-fast-reasoning",
}

# OpenRouter model IDs for fallback
OPENROUTER_FALLBACK = {
    "model-router": "anthropic/claude-3.5-sonnet",
    "Kimi-K2.5": "moonshotai/kimi-k2",
    "grok-4-1-fast-non-reasoning": "x-ai/grok-4",
    "grok-4-1-fast-reasoning": "x-ai/grok-4",
}

AZURE_API_VERSION = "2024-12-01-preview"
MAX_RETRIES = 3
BASE_BACKOFF = 5  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_messages(prompt: str, system: str | None) -> list[dict]:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs


def call_with_retry(fn, max_retries: int = MAX_RETRIES):
    """Call fn(), retrying on RateLimitError with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return fn()
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            wait = BASE_BACKOFF * (2 ** attempt)
            print(f"[azure] Rate limited. Waiting {wait}s (attempt {attempt + 1}/{max_retries})…", file=sys.stderr)
            time.sleep(wait)
        except APIStatusError as e:
            if e.status_code == 429:
                if attempt == max_retries - 1:
                    raise
                wait = BASE_BACKOFF * (2 ** attempt)
                print(f"[azure] 429 status. Waiting {wait}s (attempt {attempt + 1}/{max_retries})…", file=sys.stderr)
                time.sleep(wait)
            else:
                raise


# ---------------------------------------------------------------------------
# Azure calls
# ---------------------------------------------------------------------------

def call_azure_native(endpoint: str, api_key: str, model: str, messages: list,
                       max_tokens: int, temperature: float):
    """Call via AzureOpenAI client (model-router, etc.)."""
    client = AzureOpenAI(
        api_version=AZURE_API_VERSION,
        azure_endpoint=endpoint,
        api_key=api_key,
    )
    return call_with_retry(lambda: client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    ))


def call_azure_compat(endpoint: str, api_key: str, model: str, messages: list,
                       max_tokens: int, temperature: float):
    """Call via plain OpenAI client (OpenAI-compatible Azure endpoint)."""
    client = OpenAI(
        base_url=endpoint,
        api_key=api_key,
    )
    return call_with_retry(lambda: client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    ))


# ---------------------------------------------------------------------------
# OpenRouter fallback
# ---------------------------------------------------------------------------

def call_openrouter(api_key: str, model: str, messages: list,
                    max_tokens: int, temperature: float):
    """Call OpenRouter (fallback when Azure is rate-limited)."""
    or_model = OPENROUTER_FALLBACK.get(model, model)
    print(f"[openrouter] Falling back to {or_model}…", file=sys.stderr)
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={"HTTP-Referer": "https://github.com/schuerstedt/copilotclaw"},
    )
    return client.chat.completions.create(
        model=or_model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Query Azure LLM with OpenRouter fallback")
    parser.add_argument("--model", default="model-router", help="Model deployment name")
    parser.add_argument("--prompt", required=True, help="User prompt")
    parser.add_argument("--system", default=None, help="System prompt")
    parser.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Print raw JSON response object")
    parser.add_argument("--no-fallback", action="store_true", dest="no_fallback",
                        help="Disable OpenRouter fallback")
    args = parser.parse_args()

    azure_endpoint = os.environ.get("AZURE_ENDPOINT", "").rstrip("/")
    azure_key = os.environ.get("AZURE_APIKEY", "")
    or_key = os.environ.get("OPENROUTER_API_KEY", "")

    if not azure_endpoint or not azure_key:
        print("ERROR: AZURE_ENDPOINT and AZURE_APIKEY must be set.", file=sys.stderr)
        sys.exit(1)

    messages = build_messages(args.prompt, args.system)
    response = None
    used_provider = "azure"

    try:
        if args.model in AZURE_NATIVE_MODELS:
            response = call_azure_native(azure_endpoint, azure_key, args.model,
                                          messages, args.max_tokens, args.temperature)
        else:
            response = call_azure_compat(azure_endpoint, azure_key, args.model,
                                          messages, args.max_tokens, args.temperature)

    except (RateLimitError, APIStatusError) as e:
        if args.no_fallback or not or_key:
            print(f"ERROR: Azure rate limited and no fallback available. {e}", file=sys.stderr)
            sys.exit(1)
        print(f"[azure] Exhausted retries ({e}). Switching to OpenRouter…", file=sys.stderr)
        used_provider = "openrouter"
        try:
            response = call_openrouter(or_key, args.model, messages,
                                        args.max_tokens, args.temperature)
        except Exception as e2:
            print(f"ERROR: OpenRouter also failed: {e2}", file=sys.stderr)
            sys.exit(1)

    if response is None:
        print("ERROR: No response received.", file=sys.stderr)
        sys.exit(1)

    if args.output_json:
        print(response.model_dump_json(indent=2))
    else:
        content = response.choices[0].message.content
        if used_provider == "openrouter":
            print(f"[via openrouter:{OPENROUTER_FALLBACK.get(args.model, args.model)}]")
        elif hasattr(response, "model") and response.model:
            print(f"[model: {response.model}]")
        print(content)


if __name__ == "__main__":
    main()
