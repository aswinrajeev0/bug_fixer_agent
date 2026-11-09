import json
import re
import time
from typing import List, Optional
from google import genai
from google.genai import types
from pydantic import ValidationError
from healcode.agent.models import HealingProposal
from healcode.agent.prompts import SYSTEM_PROMPT
from rich.console import Console

console = Console()

FALLBACK_MODELS: List[str] = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
]

class GeminiAgent:
    """Interface to Google Gemini for diagnosing and generating code patches."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.6-flash"):
        self.api_key = api_key.strip().strip('"').strip("'") if api_key else None
        self.model = model
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def generate_healing_proposal(self, prompt: str) -> HealingProposal:
        """Invokes Gemini to analyze the bug and propose a structured fix with resilient model fallbacks."""
        if not self.client:
            raise ValueError(
                "Gemini client is not initialized. Ensure GEMINI_API_KEY is configured."
            )

        # Build candidate models starting with user's chosen model
        models_to_try = [self.model]
        for m in FALLBACK_MODELS:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error = None
        for candidate_model in models_to_try:
            try:
                config = types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,  # Low temperature for deterministic, surgical code fixes
                    response_mime_type="application/json",
                    response_schema=HealingProposal,
                )
                response = self.client.models.generate_content(
                    model=candidate_model,
                    contents=prompt,
                    config=config,
                )
                raw_text = response.text or ""
                return self._parse_json_response(raw_text)

            except Exception as e:
                err_msg = str(e)
                last_error = e
                # Check for transient capacity, not found, or model deprecation errors
                is_transient = any(
                    code in err_msg
                    for code in ["503", "404", "429", "UNAVAILABLE", "NOT_FOUND", "RESOURCE_EXHAUSTED", "high demand"]
                )
                if is_transient and candidate_model != models_to_try[-1]:
                    console.print(
                        f"[yellow]⚠ Model '{candidate_model}' unavailable ({err_msg[:60]}...). Failing over to next model...[/yellow]"
                    )
                    time.sleep(1.0)
                    continue

                # If schema validation error occurred in API, try unstructured text fallback
                if "response_schema" in err_msg.lower() or "schema" in err_msg.lower():
                    try:
                        return self._generate_with_text_fallback(candidate_model, prompt)
                    except Exception as fallback_err:
                        last_error = fallback_err
                        continue

        raise RuntimeError(f"All Gemini model candidates failed. Last error: {last_error}")

    def _generate_with_text_fallback(self, model: str, prompt: str) -> HealingProposal:
        """Fallback in case model requires unstructured json prompt."""
        fallback_prompt = prompt + "\n\nPlease respond strictly with a valid JSON object matching the requested schema."
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
            response_mime_type="application/json",
        )
        response = self.client.models.generate_content(
            model=model,
            contents=fallback_prompt,
            config=config,
        )
        return self._parse_json_response(response.text or "")

    def _parse_json_response(self, text: str) -> HealingProposal:
        text = text.strip()
        # Strip ```json ... ``` code fence if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n", "", text)
            text = re.sub(r"\n```$", "", text)
            text = text.strip()

        try:
            data = json.loads(text)
            return HealingProposal.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as err:
            raise ValueError(
                f"Failed to parse Gemini healing proposal into schema: {err}\nRaw text was:\n{text[:500]}"
            )
