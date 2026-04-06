#!/usr/bin/env python3
"""
ModelProvider abstraction for flexible model inference.

Supports multiple backends:
- OpenRouter (remote, via OPENROUTER_API_KEY)
- Local endpoint (via LOCAL_MODEL_ENDPOINT env var, Ollama-compatible)

Allows swapping between local and remote without code changes, only config.
"""

import json
import logging
import os
from typing import Optional, Any, Dict
from openai import OpenAI

logger = logging.getLogger(__name__)


class ModelProvider:
    """Abstraction over model inference backends (OpenRouter, local, etc.)."""

    def __init__(
        self,
        model_name: str = "google/gemini-3-flash-preview",
        provider: str = "auto",
    ):
        """Initialize ModelProvider.

        Args:
            model_name: Model identifier (e.g., "google/gemini-3-flash-preview" for OpenRouter)
            provider: Provider to use ("auto", "openrouter", "local")
                - "auto": try LOCAL_MODEL_ENDPOINT first, then OpenRouter
                - "openrouter": force OpenRouter
                - "local": force local endpoint
        """
        self.model_name = model_name
        self.provider = provider
        self.client = None
        self.endpoint_type = None  # "openrouter" or "local"

        self._init_client()

    def _init_client(self):
        """Initialize the underlying OpenAI-compatible client."""
        local_endpoint = os.getenv("LOCAL_MODEL_ENDPOINT", "").strip()
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()

        # Determine which backend to use
        use_local = False
        use_openrouter = False

        if self.provider == "local":
            if not local_endpoint:
                raise ValueError("LOCAL_MODEL_ENDPOINT env var not set, cannot use local provider")
            use_local = True
        elif self.provider == "openrouter":
            if not openrouter_key:
                raise ValueError("OPENROUTER_API_KEY env var not set, cannot use openrouter provider")
            use_openrouter = True
        elif self.provider == "auto":
            # Try local first, then OpenRouter
            if local_endpoint:
                use_local = True
            elif openrouter_key:
                use_openrouter = True
            else:
                raise ValueError(
                    "No LOCAL_MODEL_ENDPOINT or OPENROUTER_API_KEY set. "
                    "Please set one to enable model inference."
                )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        # Initialize client
        if use_local:
            self.client = OpenAI(
                api_key="dummy",  # Local endpoints typically don't need auth
                base_url=local_endpoint.rstrip("/") + "/v1",
            )
            self.endpoint_type = "local"
            logger.info(f"Using local model endpoint: {local_endpoint}")
        else:
            self.client = OpenAI(
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
            )
            self.endpoint_type = "openrouter"
            logger.info(f"Using OpenRouter with model: {self.model_name}")

    def score_text(self, text: str, prompt: str) -> float:
        """Score text via a model completion, extracting a numeric score.

        Args:
            text: The text to evaluate
            prompt: The prompt to send to the model (should ask for a number 0.0-1.0)

        Returns:
            A float between 0.0 and 1.0

        Raises:
            Exception if the model returns unparseable output
        """
        full_prompt = f"{prompt}\n\nText to evaluate:\n{text}"

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.0,
                max_tokens=10,
            )

            content = response.choices[0].message.content.strip()
            # Extract first float from response (e.g., "0.85" or "Score: 0.85")
            score = float(content.split()[-1].rstrip(".,:;"))
            return max(0.0, min(1.0, score))  # Clamp to [0.0, 1.0]
        except Exception as exc:
            logger.error(f"Error scoring text with {self.endpoint_type}: {exc}")
            raise

    def extract_json(self, prompt: str, text: str) -> Dict[str, Any]:
        """Extract structured JSON from text via model inference.

        Args:
            prompt: System prompt or instruction
            text: Text to process

        Returns:
            Parsed JSON dict

        Raises:
            Exception if parsing fails
        """
        full_prompt = f"{prompt}\n\nText:\n{text}\n\nRespond with only valid JSON."

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.0,
                max_tokens=2000,
            )

            content = response.choices[0].message.content.strip()
            # Try to extract JSON from response
            if content.startswith("{"):
                return json.loads(content)
            # If wrapped in markdown code blocks, extract it
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            if "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            # Fallback: assume the whole thing is JSON
            return json.loads(content)
        except Exception as exc:
            logger.error(f"Error extracting JSON with {self.endpoint_type}: {exc}")
            raise

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        """Generate text completion.

        Args:
            prompt: User message
            system: Optional system prompt

        Returns:
            Model's text response
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.error(f"Error generating completion with {self.endpoint_type}: {exc}")
            raise
