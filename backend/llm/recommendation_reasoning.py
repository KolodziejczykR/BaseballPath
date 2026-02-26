"""
LLM-based reasoning layer for school recommendations.

Grounding rules:
- Use only provided fields and playing time stats.
- Do not invent facts about schools or players.
"""

import asyncio
import json
import os
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from backend.utils.recommendation_types import LLMReasoning, RelaxSuggestion, SchoolRecommendation

load_dotenv()


def _extract_json(content: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Fallback: try to extract the first JSON object
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        return json.loads(content[start : end + 1])
    except json.JSONDecodeError:
        return None


class RecommendationReasoningGenerator:
    def __init__(
        self,
        client: Optional[OpenAI] = None,
        llm_timeout_s: float = 30.0,
        max_concurrent_batches: int = 2,
    ):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = client or OpenAI(api_key=api_key)
        self.llm_timeout_s = llm_timeout_s
        self.max_concurrent_batches = max_concurrent_batches

    async def generate_school_reasoning_async(
        self,
        schools: List[SchoolRecommendation],
        player_info: Dict[str, Any],
        ml_summary: Dict[str, Any],
        preferences: Dict[str, Any],
        batch_size: int = 5,
    ) -> Dict[str, LLMReasoning]:
        results: Dict[str, LLMReasoning] = {}
        if not schools:
            return results

        semaphore = asyncio.Semaphore(self.max_concurrent_batches)
        tasks = []
        for i in range(0, len(schools), batch_size):
            batch = schools[i : i + batch_size]
            tasks.append(
                self._generate_school_reasoning_batch_async(
                    batch, player_info, ml_summary, preferences, semaphore
                )
            )

        for batch_result in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(batch_result, dict):
                results.update(batch_result)
        return results

    def generate_school_reasoning(
        self,
        schools: List[SchoolRecommendation],
        player_info: Dict[str, Any],
        ml_summary: Dict[str, Any],
        preferences: Dict[str, Any],
        batch_size: int = 5,
    ) -> Dict[str, LLMReasoning]:
        results: Dict[str, LLMReasoning] = {}
        for i in range(0, len(schools), batch_size):
            batch = schools[i : i + batch_size]
            batch_results = self._generate_school_reasoning_batch(
                batch, player_info, ml_summary, preferences
            )
            results.update(batch_results)
        return results

    def _generate_school_reasoning_batch(
        self,
        schools: List[SchoolRecommendation],
        player_info: Dict[str, Any],
        ml_summary: Dict[str, Any],
        preferences: Dict[str, Any],
    ) -> Dict[str, LLMReasoning]:
        prompt = self._build_school_reasoning_prompt(
            schools, player_info, ml_summary, preferences
        )

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise, grounded sports recruiting assistant. "
                        "Only use the provided fields. Do not add facts."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content.strip()
        data = _extract_json(content)
        if not data:
            return {}

        results: Dict[str, LLMReasoning] = {}
        for item in data.get("schools", []):
            name = item.get("school_name")
            if not name:
                continue
            results[name] = LLMReasoning(
                summary=item.get("summary"),
                fit_qualities=item.get("fit_qualities", []) or [],
                cautions=item.get("cautions", []) or [],
            )
        return results

    async def _generate_school_reasoning_batch_async(
        self,
        schools: List[SchoolRecommendation],
        player_info: Dict[str, Any],
        ml_summary: Dict[str, Any],
        preferences: Dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, LLMReasoning]:
        async with semaphore:
            prompt = self._build_school_reasoning_prompt(
                schools, player_info, ml_summary, preferences
            )
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.chat.completions.create,
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are a concise, grounded sports recruiting assistant. "
                                    "Only use the provided fields. Do not add facts."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                    ),
                    timeout=self.llm_timeout_s,
                )
            except Exception:
                return {}

            content = response.choices[0].message.content.strip()
            data = _extract_json(content)
            if not data:
                return {}

            results: Dict[str, LLMReasoning] = {}
            for item in data.get("schools", []):
                name = item.get("school_name")
                if not name:
                    continue
                results[name] = LLMReasoning(
                    summary=item.get("summary"),
                    fit_qualities=item.get("fit_qualities", []) or [],
                    cautions=item.get("cautions", []) or [],
                )
            return results

    def _build_school_reasoning_prompt(
        self,
        schools: List[SchoolRecommendation],
        player_info: Dict[str, Any],
        ml_summary: Dict[str, Any],
        preferences: Dict[str, Any],
    ) -> str:
        schools_payload = [asdict(s) for s in schools]

        return (
            "Create grounded, school-specific fit reasoning using ONLY the provided data. "
            "Do not add new facts about schools or players. "
            "If a field is missing, omit it. "
            "Each school must mention playing_time if available. "
            "Return strict JSON with the following schema:\n"
            "{\n"
            '  "schools": [\n'
            "    {\n"
            '      "school_name": "string",\n'
            '      "summary": "1-2 sentences",\n'
            '      "fit_qualities": ["3-5 short bullets"],\n'
            '      "cautions": ["0-2 short bullets"]\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "PLAYER_INFO:\n"
            f"{json.dumps(player_info, ensure_ascii=True)}\n\n"
            "ML_SUMMARY:\n"
            f"{json.dumps(ml_summary, ensure_ascii=True)}\n\n"
            "PREFERENCES:\n"
            f"{json.dumps(preferences, ensure_ascii=True)}\n\n"
            "SCHOOLS:\n"
            f"{json.dumps(schools_payload, ensure_ascii=True)}\n"
        )

    def generate_player_summary(
        self,
        schools: List[SchoolRecommendation],
        player_info: Dict[str, Any],
        ml_summary: Dict[str, Any],
        preferences: Dict[str, Any],
    ) -> Optional[str]:
        prompt = self._build_player_summary_prompt(
            schools, player_info, ml_summary, preferences
        )

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise, grounded sports recruiting assistant. "
                        "Only use the provided fields. Do not add facts."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content.strip()
        data = _extract_json(content)
        if not data:
            return None
        return data.get("player_summary")

    async def generate_player_summary_async(
        self,
        schools: List[SchoolRecommendation],
        player_info: Dict[str, Any],
        ml_summary: Dict[str, Any],
        preferences: Dict[str, Any],
    ) -> Optional[str]:
        prompt = self._build_player_summary_prompt(
            schools, player_info, ml_summary, preferences
        )
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.chat.completions.create,
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a concise, grounded sports recruiting assistant. "
                                "Only use the provided fields. Do not add facts."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                ),
                timeout=self.llm_timeout_s,
            )
        except Exception:
            return None

        content = response.choices[0].message.content.strip()
        data = _extract_json(content)
        if not data:
            return None
        return data.get("player_summary")

    def _build_player_summary_prompt(
        self,
        schools: List[SchoolRecommendation],
        player_info: Dict[str, Any],
        ml_summary: Dict[str, Any],
        preferences: Dict[str, Any],
    ) -> str:
        schools_payload = []
        for school in schools:
            payload = asdict(school)
            payload.pop("llm_reasoning", None)
            schools_payload.append(payload)
        return (
            "Create a single paragraph that highlights the player's top stats "
            "(only from provided fields) AND summarizes the overall school results. "
            "Focus more on the school results than the player bio. "
            "Keep the tone positive and avoid emphasizing poor playing time fits. "
            "Do not add new facts. Do not mention playing time. "
            "Return strict JSON with:\n"
            '{ "player_summary": "string" }\n\n'
            "PLAYER_INFO:\n"
            f"{json.dumps(player_info, ensure_ascii=True)}\n\n"
            "ML_SUMMARY:\n"
            f"{json.dumps(ml_summary, ensure_ascii=True)}\n\n"
            "PREFERENCES:\n"
            f"{json.dumps(preferences, ensure_ascii=True)}\n\n"
            "SCHOOLS:\n"
            f"{json.dumps(schools_payload, ensure_ascii=True)}\n"
        )

    def generate_relax_suggestions(
        self,
        must_haves: Dict[str, Any],
        total_matches: int,
        min_threshold: int = 5,
    ) -> List[RelaxSuggestion]:
        if total_matches >= min_threshold or not must_haves:
            return []

        prompt = self._build_relax_suggestions_prompt(must_haves, total_matches)
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a cautious assistant. Only suggest relaxing must-have preferences. "
                        "Do not mention budget unless it is already a must-have, and place it last."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content.strip()
        data = _extract_json(content)
        if not data:
            return []

        suggestions = [
            RelaxSuggestion(
                preference=item.get("preference", ""),
                suggestion=item.get("suggestion", ""),
                reason=item.get("reason", ""),
            )
            for item in data.get("suggestions", [])
            if item.get("preference") and item.get("suggestion")
        ]

        # Enforce budget-last if present
        budget_pref = "max_budget"
        budget_items = [s for s in suggestions if s.preference == budget_pref]
        non_budget_items = [s for s in suggestions if s.preference != budget_pref]
        return non_budget_items + budget_items

    async def generate_relax_suggestions_async(
        self,
        must_haves: Dict[str, Any],
        total_matches: int,
        min_threshold: int = 5,
    ) -> List[RelaxSuggestion]:
        if total_matches >= min_threshold or not must_haves:
            return []

        prompt = self._build_relax_suggestions_prompt(must_haves, total_matches)
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.chat.completions.create,
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a cautious assistant. Only suggest relaxing must-have preferences. "
                                "Do not mention budget unless it is already a must-have, and place it last."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                ),
                timeout=self.llm_timeout_s,
            )
        except Exception:
            return []

        content = response.choices[0].message.content.strip()
        data = _extract_json(content)
        if not data:
            return []

        suggestions = [
            RelaxSuggestion(
                preference=item.get("preference", ""),
                suggestion=item.get("suggestion", ""),
                reason=item.get("reason", ""),
            )
            for item in data.get("suggestions", [])
            if item.get("preference") and item.get("suggestion")
        ]

        budget_pref = "max_budget"
        budget_items = [s for s in suggestions if s.preference == budget_pref]
        non_budget_items = [s for s in suggestions if s.preference != budget_pref]
        return non_budget_items + budget_items

    def _build_relax_suggestions_prompt(
        self, must_haves: Dict[str, Any], total_matches: int
    ) -> str:
        return (
            "We have too few matches. Suggest 1-3 optional relaxations. "
            "Only use must-have preferences listed. "
            "Do not mention budget unless it is present, and make it the last suggestion.\n"
            "Return strict JSON with:\n"
            '{ "suggestions": [ { "preference": "string", "suggestion": "string", "reason": "string" } ] }\n\n'
            f"TOTAL_MATCHES: {total_matches}\n\n"
            "MUST_HAVES:\n"
            f"{json.dumps(must_haves, ensure_ascii=True)}\n"
        )
