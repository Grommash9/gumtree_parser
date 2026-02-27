"""
Azure OpenAI client for LLM calls.
Handles rate limiting, retries, and response parsing.
"""

import json
import requests
from typing import Optional, List, Dict, Any

from common.config import (
    AZURE_API_KEY,
    AZURE_ENDPOINT,
    AZURE_DEPLOYMENT,
    AZURE_API_VERSION,
    MAX_RETRIES,
    RETRY_DELAY,
)
from llm_classifier.rate_limiter import rate_limiter


def check_azure_connection() -> bool:
    """Check if Azure OpenAI is configured and working."""
    if not AZURE_API_KEY:
        print("ERROR: AZURE_API_KEY environment variable not set")
        return False
    if not AZURE_ENDPOINT:
        print("ERROR: AZURE_ENDPOINT environment variable not set")
        return False

    try:
        url = f"{AZURE_ENDPOINT}/openai/deployments/{AZURE_DEPLOYMENT}/chat/completions?api-version={AZURE_API_VERSION}"
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "api-key": AZURE_API_KEY
            },
            json={
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 5
            },
            timeout=15
        )
        if response.status_code == 200:
            print(f"Azure OpenAI connected, deployment: {AZURE_DEPLOYMENT}")
            return True
        else:
            print(f"Azure OpenAI error: {response.status_code} - {response.text[:100]}")
            return False
    except Exception as e:
        print(f"Azure connection error: {e}")
        return False


def call_llm(
    prompt: str,
    system_message: str = "You are a helpful assistant. Return only valid JSON.",
    is_json_response: bool = True,
    post_id: str = "",
    stage: str = "",
    max_tokens: int = 4000
) -> Optional[str]:
    """
    Call Azure OpenAI LLM and return response text.
    Implements rate limiting with exponential backoff on 429 errors.

    Args:
        prompt: User prompt to send
        system_message: System message for the model
        is_json_response: Whether to expect JSON response
        post_id: Post ID for logging
        stage: Stage name for logging
        max_tokens: Maximum tokens in response

    Returns:
        Response content string or None on failure
    """
    import time

    # Estimate tokens for rate limiting (prompt + expected completion)
    estimated_tokens = (len(prompt) + len(system_message)) // 4 + 1000

    log_prefix = f"[{post_id}:{stage}]" if post_id else "[LLM]"

    for attempt in range(MAX_RETRIES):
        try:
            # Wait if we're approaching TPM limit
            wait_time = rate_limiter.wait_if_needed(estimated_tokens)
            if wait_time > 0:
                print(f"{log_prefix} Rate limit wait: {wait_time:.1f}s", flush=True)

            url = f"{AZURE_ENDPOINT}/openai/deployments/{AZURE_DEPLOYMENT}/chat/completions?api-version={AZURE_API_VERSION}"
            response = requests.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "api-key": AZURE_API_KEY
                },
                json={
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0,
                    "max_tokens": max_tokens
                },
                timeout=120
            )

            if response.status_code == 200:
                result = response.json()
                try:
                    message = result['choices'][0]['message']
                    content = message.get('content')
                    if content is None:
                        refusal = message.get('refusal')
                        if refusal:
                            print(f"{log_prefix} Model refused: {refusal}", flush=True)
                            return f"REFUSED: {refusal}"
                        return ""
                except (KeyError, IndexError) as e:
                    print(f"{log_prefix} Unexpected response format: {e}", flush=True)
                    return ""

                # Record actual token usage
                usage = result.get('usage', {})
                actual_tokens = usage.get('total_tokens')
                rate_limiter.record_usage(prompt, content or "", actual_tokens)
                return content

            elif response.status_code == 429:
                print(f"{log_prefix} Rate limited (429)", flush=True)
                retry_after = _parse_retry_after(response.headers)

                if retry_after is None:
                    retry_after = min(RETRY_DELAY * (2 ** attempt), 60)

                rate_limiter.set_retry_after(retry_after)
                time.sleep(retry_after)
                continue

            else:
                print(f"{log_prefix} API error: {response.status_code} - {response.text[:200]}", flush=True)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))

        except requests.exceptions.RequestException as e:
            print(f"{log_prefix} Request exception: {e}", flush=True)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue

    print(f"{log_prefix} FAILED after {MAX_RETRIES} attempts", flush=True)
    return None


def _parse_retry_after(headers: dict) -> Optional[float]:
    """Parse retry-after time from response headers."""
    retry_after = None

    # Check Retry-After header
    if 'Retry-After' in headers:
        try:
            retry_after = float(headers['Retry-After'])
        except ValueError:
            pass

    # Check x-ratelimit-reset-tokens header (Azure specific)
    if 'x-ratelimit-reset-tokens' in headers:
        try:
            reset_str = headers['x-ratelimit-reset-tokens']
            if 'm' in reset_str:
                parts = reset_str.replace('s', '').split('m')
                retry_after = int(parts[0]) * 60 + int(parts[1] or 0)
            else:
                retry_after = int(reset_str.replace('s', ''))
        except ValueError:
            pass

    return retry_after


def parse_json_response(response_text: str) -> Optional[dict]:
    """Extract and parse JSON object from LLM response."""
    if not response_text:
        return None

    # Find JSON object
    json_start = response_text.find('{')
    json_end = response_text.rfind('}') + 1

    if json_start >= 0 and json_end > json_start:
        try:
            json_str = response_text[json_start:json_end]
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    return None


def parse_json_array_response(response_text: str) -> Optional[List[Dict[str, Any]]]:
    """Extract and parse JSON array from LLM response."""
    if not response_text:
        return None

    # First try to find array
    array_start = response_text.find('[')
    array_end = response_text.rfind(']') + 1

    if array_start >= 0 and array_end > array_start:
        try:
            json_str = response_text[array_start:array_end]
            result = json.loads(json_str)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # Try to find object with array inside
    obj = parse_json_response(response_text)
    if obj:
        # Look for any array value in the object
        for value in obj.values():
            if isinstance(value, list):
                return value

    return None
