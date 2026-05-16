#!/usr/bin/env python3
"""
AskYourPDF v4.0 — Translation Engine
Handles detecting languages and translating between 10 languages
"""
import os
import requests
import time
from typing import Optional, Dict, List
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")
TRANSLATION_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
MAX_RETRIES = 2
RETRY_DELAY = 1

SUPPORTED_LANGUAGES = {
    "en": {"name": "English", "native_name": "English", "flag": "🇬🇧", "prompt_name": "English"},
    "fr": {"name": "French", "native_name": "Français", "flag": "🇫🇷", "prompt_name": "French"},
    "es": {"name": "Spanish", "native_name": "Español", "flag": "🇪🇸", "prompt_name": "Spanish"},
    "de": {"name": "German", "native_name": "Deutsch", "flag": "🇩🇪", "prompt_name": "German"},
    "it": {"name": "Italian", "native_name": "Italiano", "flag": "🇮🇹", "prompt_name": "Italian"},
    "pt": {"name": "Portuguese", "native_name": "Português", "flag": "🇵🇹", "prompt_name": "Portuguese"},
    "nl": {"name": "Dutch", "native_name": "Nederlands", "flag": "🇳🇱", "prompt_name": "Dutch"},
    "ja": {"name": "Japanese", "native_name": "日本語", "flag": "🇯🇵", "prompt_name": "Japanese"},
    "zh": {"name": "Chinese", "native_name": "中文", "flag": "🇨🇳", "prompt_name": "Chinese"},
    "ar": {"name": "Arabic", "native_name": "العربية", "flag": "🇸🇦", "prompt_name": "Arabic"},
}

@dataclass
class TranslationResult:
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    confidence: float = 1.0


def _call_ollama(prompt, max_tokens=100, temperature=0, timeout=30):
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": TRANSLATION_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
                timeout=timeout,
            )
            if response.status_code == 200:
                return response.json().get("response", "").strip()
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except (requests.ConnectionError, requests.Timeout):
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"Translation error: {e}")
            return None
    return None


def detect_language(text: str) -> str:
    if not text or len(text.strip()) < 5:
        return "en"
    
    sample = text[:300].strip()
    prompt = f"Identify the language. Respond with ONLY the two-letter code (en, fr, es, de, it, pt, nl, ja, zh, ar).\n\nText: {sample}\n\nCode:"
    
    result = _call_ollama(prompt, max_tokens=5, temperature=0, timeout=10)
    
    if result:
        cleaned = ''.join(c for c in result.lower() if c.isalpha())[:2]
        if cleaned in SUPPORTED_LANGUAGES:
            return cleaned
    return "en"


def translate_text(text: str, target_language: str, source_language: Optional[str] = None) -> TranslationResult:
    if not text or not text.strip():
        return TranslationResult(text or "", text or "", source_language or "en", target_language)
    
    if target_language not in SUPPORTED_LANGUAGES:
        return TranslationResult(text, f"[Unsupported language: {target_language}]", source_language or "en", target_language, 0.0)
    
    if source_language is None:
        source_language = detect_language(text)
    
    if source_language == target_language:
        return TranslationResult(text, text, source_language, target_language, 1.0)
    
    source_info = SUPPORTED_LANGUAGES.get(source_language, SUPPORTED_LANGUAGES["en"])
    target_info = SUPPORTED_LANGUAGES[target_language]
    
    prompt = f"""Translate from {source_info['prompt_name']} to {target_info['prompt_name']}. Return ONLY the translated text.

{source_info['prompt_name']}: {text}

{target_info['prompt_name']}:"""
    
    translated = _call_ollama(prompt, max_tokens=max(len(text) * 2, 100), temperature=0.1, timeout=60)
    
    if translated:
        cleaned = translated.strip().strip('"').strip("'")
        return TranslationResult(text, cleaned, source_language, target_language, 1.0)
    
    return TranslationResult(text, f"[Translation failed] {text}", source_language, target_language, 0.0)


def get_supported_languages() -> List[Dict]:
    return [
        {"code": code, "name": info["name"], "native_name": info["native_name"], "flag": info["flag"]}
        for code, info in SUPPORTED_LANGUAGES.items()
    ]


def get_language_name(code: str) -> str:
    return SUPPORTED_LANGUAGES.get(code, {}).get("name", "Unknown")


def get_language_flag(code: str) -> str:
    return SUPPORTED_LANGUAGES.get(code, {}).get("flag", "🌐")