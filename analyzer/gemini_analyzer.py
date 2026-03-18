"""Gemini API integration for advanced diagnosis."""

from __future__ import annotations

import json
import re
from typing import Any

import requests


class GeminiAnalyzerError(Exception):
    """Raised when Gemini analysis cannot be completed."""


class GeminiAnalyzer:
    """Build prompts and request diagnosis from Gemini API."""

    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", timeout: int = 60) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def build_prompt(self, network_payload: dict[str, Any]) -> str:
        """Generate standardized diagnosis prompt."""
        pretty_payload = json.dumps(network_payload, ensure_ascii=False, indent=2)
        # Extrai temperatura do payload SNMP
        temp = None
        try:
            temp = network_payload.get('mikrotik_health', {}).get('temperature')
        except Exception:
            temp = None
        temp_msg = ""
        if temp is not None:
            try:
                temp_val = float(temp)
                if temp_val < 45:
                    temp_msg = ("\nSe a temperatura do MikroTik estiver abaixo de 45°C, elogie a eficiência térmica da instalação, "
                                "mencionando que mesmo no clima de Macapá o hardware está estável.")
                elif temp_val > 55:
                    temp_msg = ("\nSe a temperatura do MikroTik estiver acima de 55°C, gere um alerta de saúde física, recomendando inspeção e ventilação.")
            except Exception:
                pass
        return (
            "Voce e um especialista em redes domesticas e corporativas.\n\n"
            "Aqui estao os dados coletados da rede:\n\n"
            f"{pretty_payload}\n\n"
            f"{temp_msg}\n"
            "Com base nisso, gere:\n"
            "1. Diagnostico detalhado\n"
            "2. Lista de problemas encontrados\n"
            "3. Causas provaveis\n"
            "4. Sugestoes de correcao\n"
            "5. Topologia ideal recomendada\n"
            "6. Lista de acoes passo a passo\n"
            "7. Riscos se nada for corrigido\n\n"
            "Responda em formato JSON estruturado."
        )

    def analyze(self, network_payload: dict[str, Any]) -> dict[str, Any]:
        """Call Gemini API and return normalized structured output."""
        if not self.api_key:
            raise GeminiAnalyzerError("GEMINI_API_KEY nao configurada.")

        prompt = self.build_prompt(network_payload)
        url = f"{self.API_BASE}/{self.model}:generateContent?key={self.api_key}"
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }

        try:
            response = requests.post(url, json=body, timeout=self.timeout)
            response.raise_for_status()
        except requests.Timeout:
            raise GeminiAnalyzerError("Timeout ao chamar Gemini API. Tente novamente ou reduza o tamanho dos dados.")
        except requests.RequestException as exc:
            raise GeminiAnalyzerError(f"Falha ao chamar Gemini API: {exc}") from exc

        data = response.json()
        text = self._extract_text(data)
        parsed, parse_error = self._parse_json_text(text)

        return {
            "model": self.model,
            "raw": data,
            "text": text,
            "parsed": parsed,
            "valid_json": parse_error is None,
            "parse_error": parse_error,
        }

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        """Extract generated plain text from Gemini response payload."""
        candidates = payload.get("candidates", [])
        if not candidates:
            return ""

        parts = candidates[0].get("content", {}).get("parts", [])
        chunks = [part.get("text", "") for part in parts if isinstance(part, dict)]
        return "\n".join(item for item in chunks if item)

    @staticmethod
    def _parse_json_text(text: str) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
        """Parse JSON output and gracefully fallback when model returns extra text."""
        cleaned = (text or "").strip()
        if not cleaned:
            return None, "Resposta vazia da Gemini API"

        try:
            return json.loads(cleaned), None
        except json.JSONDecodeError:
            pass

        fence_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", cleaned, flags=re.DOTALL)
        if fence_match:
            block = fence_match.group(1)
            try:
                return json.loads(block), None
            except json.JSONDecodeError:
                pass

        first_obj = cleaned.find("{")
        last_obj = cleaned.rfind("}")
        if first_obj != -1 and last_obj != -1 and last_obj > first_obj:
            candidate = cleaned[first_obj : last_obj + 1]
            try:
                return json.loads(candidate), None
            except json.JSONDecodeError as exc:
                return None, f"JSON invalido na resposta da Gemini: {exc}"

        first_arr = cleaned.find("[")
        last_arr = cleaned.rfind("]")
        if first_arr != -1 and last_arr != -1 and last_arr > first_arr:
            candidate = cleaned[first_arr : last_arr + 1]
            try:
                return json.loads(candidate), None
            except json.JSONDecodeError as exc:
                return None, f"JSON invalido na resposta da Gemini: {exc}"

        return None, "Nao foi possivel extrair JSON da resposta da Gemini"
