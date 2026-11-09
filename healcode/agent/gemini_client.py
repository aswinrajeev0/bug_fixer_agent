import json
import re
from typing import Optional
from google import genai
from google.genai import types
from pydantic import ValidationError
from healcode.agent.models import HealingProposal
from healcode.agent.prompts import SYSTEM_PROMPT

class GeminiAgent:
    """Interface to Google Gemini for diagnosing and generating code patches."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self.client = genai.Client(api_key=api_key) if api_key else None

    def generate_healing_proposal(self, prompt: str) -> HealingProposal:
        """Invokes Gemini to analyze the bug and propose a structured fix."""
        if not self.client:
            raise ValueError(
                "Gemini client is not initialized. Ensure GEMINI_API_KEY is configured."
            )

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,  # Low temperature for deterministic, surgical code fixes
            response_mime_type="application/json",
            response_schema=HealingProposal,
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            raw_text = response.text or ""
            return self._parse_json_response(raw_text)
        except Exception as e:
            # Try fallback without response_schema if schema validation error occurred in API
            if "response_schema" in str(e).lower() or "schema" in str(e).lower():
                return self._generate_with_text_fallback(prompt)
            raise e

    def _generate_with_text_fallback(self, prompt: str) -> HealingProposal:
        """Fallback in case model requires unstructured json prompt."""
        fallback_prompt = prompt + "\n\nPlease respond strictly with a valid JSON object matching the requested schema."
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
            response_mime_type="application/json",
        )
        response = self.client.models.generate_content(
            model=self.model,
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
