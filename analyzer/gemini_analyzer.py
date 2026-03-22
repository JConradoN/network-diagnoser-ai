"""Gemini API integration for advanced diagnosis with Token Optimization."""

from __future__ import annotations
import json
import re
import logging
import time
from typing import Any
from google import genai

class GeminiAnalyzerError(Exception):
    """Raised when Gemini analysis cannot be completed."""

class GeminiAnalyzer:
    """Build prompts and request diagnosis from Gemini API with payload compression."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", timeout: int = 60) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        print(f"🤖 IA Ativa: {self.model}")
        self.client = genai.Client(api_key=api_key)
        try:
            self.client.models.get(model=self.model)
            print(f"✅ Conexão com modelo {self.model} verificada.")
        except Exception as e:
            print(f"⚠️ Erro ao validar modelo: {e}")

    def _compact_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        """Remove redundâncias para evitar erro 429 de limite de tokens."""
        compact = {
            "dispositivos": [],
            "saude_hardware": data.get("mikrotik_health", {}),
            "alertas_detectados": data.get("findings", []),
            "interface": data.get("interface")
        }

        # Filtramos apenas o essencial de cada dispositivo detectado
        for dev in data.get("devices", []):
            if dev.get("status") != "Invisível (DHCP Record)":
                compact["dispositivos"].append({
                    "ip": dev.get("ip"),
                    "nome": dev.get("hostname"),
                    "vendor": dev.get("vendor")
                })
        
        # Simplifica a topologia
        compact["topologia"] = [
            {"origem": e.get("from"), "destino": e.get("to")}
            for e in data.get("topology", {}).get("edges", [])
        ]
        
        return compact

    def _build_prompt(self, network_payload: dict[str, Any]) -> str:
        # Compactamos os dados antes de criar o prompt
        essential_data = self._compact_payload(network_payload)
        pretty_payload = json.dumps(essential_data, ensure_ascii=False)
        
        print(f"DEBUG: Payload compactado de {len(json.dumps(network_payload))} para {len(pretty_payload)} caracteres.")

        return (
            "Como engenheiro de redes, analise os dados abaixo e retorne APENAS um JSON estruturado:\n"
            "{\n"
            "  \"diagnostico_detalhado\": \"string\",\n"
            "  \"problemas_identificados\": [],\n"
            "  \"acoes_recomendadas\": [],\n"
            "  \"status_geral\": \"CRÍTICO/ATENÇÃO/ESTÁVEL\"\n"
            "}\n\n"
            f"Dados: {pretty_payload}"
        )

    def _parse_json(self, text: str) -> dict:
        try:
            clean_text = re.sub(r"```json\s?|\s?```", "", text).strip()
            match = re.search(r"\{.*\}", clean_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            print(f"❌ Erro ao parsear JSON da IA: {e}")
        return {"raw_response": text}

    def analyze(self, network_payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise GeminiAnalyzerError("GEMINI_API_KEY nao configurada.")

        prompt = self._build_prompt(network_payload)
        start_time = time.time()
        
        print(f"🧠 [STAGE 10] Iniciando chamada API Gemini ({self.model})...")
        
        try:
            response = self.client.models.generate_content(
                model=self.model, 
                contents=prompt
            )
            
            elapsed = time.time() - start_time
            print(f"🕒 Gemini respondeu em {elapsed:.2f}s")
            
            if not response or not response.text:
                print("❌ Gemini retornou uma resposta vazia!")
                return {"parsed": {"error": "Resposta vazia da IA"}}

            parsed = self._parse_json(response.text)
            return {"parsed": parsed}

        except Exception as e:
            logging.error(f"Erro Crítico Gemini: {e}", exc_info=True)
            raise GeminiAnalyzerError(f"Falha na API: {e}")