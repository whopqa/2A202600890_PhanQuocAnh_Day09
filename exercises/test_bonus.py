"""Lightweight checks for the exercise bonus requirements.

Run:
    python exercises/test_bonus.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import exercises.exercise_2_tools as exercise_2
import exercises.exercise_4_multiagent as exercise_4


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    def invoke(self, messages):
        prompt = messages[-1].content
        if "thiệt hại tài chính" in prompt or "direct damages" in prompt:
            return FakeResponse("Financial exposure: direct damages, remediation cost, legal fees.")
        if "GDPR" in prompt or "bảo vệ dữ liệu" in prompt:
            return FakeResponse("Privacy exposure: GDPR notice duties and data subject rights.")
        if "thuế" in prompt or "IRS" in prompt:
            return FakeResponse("Tax exposure: back taxes, interest, and penalties.")
        if "Tổng hợp" in prompt:
            return FakeResponse("Final report combines law, tax, privacy, and financial analysis.")
        return FakeResponse("General legal analysis.")


class FakeHttpResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "results": [
                {
                    "caseName": "Hadley v. Baxendale",
                    "court": "Court of Exchequer",
                    "dateFiled": "1854-02-23",
                    "absolute_url": "/opinion/1/hadley-v-baxendale/",
                }
            ]
        }


def test_exercise_2_bonus() -> None:
    labor_entries = [entry for entry in exercise_2.LEGAL_KNOWLEDGE if entry["id"] == "labor_law"]
    assert labor_entries, "Missing labor_law knowledge entry"

    assert exercise_2.check_statute_of_limitations.invoke({"case_type": "contract"}).startswith("4 năm")

    original_get = exercise_2.httpx.get
    exercise_2.httpx.get = lambda *args, **kwargs: FakeHttpResponse()
    try:
        api_result = exercise_2.lookup_public_legal_resource.invoke({"topic": "contract breach"})
        assert "Hadley v. Baxendale" in api_result, "Custom public API tool must return text"
    finally:
        exercise_2.httpx.get = original_get


async def test_exercise_4_bonus() -> None:
    original_get_llm = exercise_4.get_llm
    exercise_4.get_llm = lambda: FakeLLM()
    try:
        routing = exercise_4.route_to_agents({
            "question": "data breach tax damages thiệt hại tài chính",
            "conversation_context": "",
            "law_analysis": "",
            "tax_analysis": "",
            "compliance_analysis": "",
            "privacy_analysis": "",
            "financial_analysis": "",
            "final_response": "",
        })
        destinations = {send.node for send in routing}
        assert "tax_agent" in destinations, "Tax routing missing"
        assert "privacy_agent" in destinations, "Privacy routing missing"
        assert "financial_agent" in destinations, "Financial routing missing"

        graph = exercise_4.build_graph()
        result = await graph.ainvoke({
            "question": "data breach tax damages thiệt hại tài chính",
            "conversation_context": "",
            "law_analysis": "",
            "tax_analysis": "",
            "compliance_analysis": "",
            "privacy_analysis": "",
            "financial_analysis": "",
            "final_response": "",
        })
        assert result["financial_analysis"], "Financial agent did not produce analysis"
        assert result["privacy_analysis"], "Privacy agent did not produce analysis"
        assert result["tax_analysis"], "Tax agent did not produce analysis"
        assert result["final_response"], "Aggregator did not produce final response"
        assert exercise_4.CONVERSATION_MEMORY, "Conversation memory was not updated"
    finally:
        exercise_4.get_llm = original_get_llm


async def main() -> None:
    test_exercise_2_bonus()
    await test_exercise_4_bonus()
    print("All bonus checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
