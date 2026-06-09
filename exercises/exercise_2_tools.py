"""Bài Tập 2: Thêm Tools và Knowledge Base

Hoàn thành các TODO để thêm tool và knowledge base entry mới.
"""

import asyncio
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from common.llm import get_llm


class FallbackResponse:
    """Small response object used when the live LLM provider is unavailable."""

    def __init__(self, content: str, tool_calls: list[dict] | None = None):
        self.content = content
        self.tool_calls = tool_calls or []


# Knowledge base
LEGAL_KNOWLEDGE = [
    {
        "id": "ucc_breach",
        "keywords": ["breach", "contract", "remedies", "damages", "ucc"],
        "text": (
            "Under the Uniform Commercial Code (UCC) Article 2, remedies for breach of contract "
            "include: (1) expectation damages; (2) consequential damages; (3) specific performance; "
            "(4) cover damages. Statute of limitations is typically 4 years (UCC § 2-725)."
        ),
    },
    {
        "id": "labor_law",
        "keywords": ["lao động", "sa thải", "hợp đồng lao động", "labor", "termination"],
        "text": (
            "Theo Bộ luật Lao động Việt Nam 2019, người sử dụng lao động có thể "
            "đơn phương chấm dứt hợp đồng trong các trường hợp: (1) người lao động "
            "thường xuyên không hoàn thành công việc; (2) bị ốm đau, tai nạn đã điều trị "
            "12 tháng chưa khỏi; (3) thiên tai, hỏa hoạn; (4) người lao động đủ tuổi nghỉ hưu."
        ),
    },
]


@tool
def search_legal_knowledge(query: str) -> str:
    """Tìm kiếm trong knowledge base pháp lý."""
    query_lower = query.lower()
    for entry in LEGAL_KNOWLEDGE:
        if any(kw in query_lower for kw in entry["keywords"]):
            return f"[{entry['id']}] {entry['text']}"
    return "Không tìm thấy thông tin liên quan."


@tool
def check_statute_of_limitations(case_type: str) -> str:
    """Kiểm tra thời hiệu khởi kiện theo loại vụ án.

    Args:
        case_type: Loại vụ án (contract, tort, property)
    """
    limits = {
        "contract": "4 năm (UCC § 2-725)",
        "tort": "2-3 năm tùy bang",
        "property": "5 năm",
    }
    return limits.get(case_type.lower(), "Không xác định")


@tool
def lookup_public_legal_resource(topic: str) -> str:
    """Tra cứu nguồn pháp lý công khai từ CourtListener API.

    Args:
        topic: Chủ đề pháp lý cần tìm, ví dụ contract breach hoặc tax evasion.
    """
    try:
        response = httpx.get(
            "https://www.courtlistener.com/api/rest/v4/search/",
            params={"q": topic, "type": "o"},
            timeout=8.0,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return f"Không tìm thấy nguồn công khai phù hợp cho chủ đề: {topic}"

        first = results[0]
        case_name = first.get("caseName") or first.get("case_name") or "Không rõ tên vụ án"
        court = first.get("court") or "Không rõ tòa"
        date_filed = first.get("dateFiled") or first.get("date_filed") or "Không rõ ngày"
        absolute_url = first.get("absolute_url") or ""
        url = f"https://www.courtlistener.com{absolute_url}" if absolute_url else "Không có URL"
        return f"{case_name} | {court} | {date_filed} | {url}"
    except Exception as exc:
        return (
            "Không thể gọi CourtListener API lúc này. "
            f"Dùng fallback nội bộ cho '{topic}'. Lỗi: {type(exc).__name__}"
        )


async def invoke_tool_with_retry(tool_fn: Any, args: dict, max_attempts: int = 3) -> str:
    """Execute a tool with simple exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await tool_fn.ainvoke(args)
        except Exception as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
    return f"Tool failed after {max_attempts} attempts: {last_error}"


async def invoke_llm_with_fallback(llm_with_tools, messages: list, question: str) -> FallbackResponse:
    """Call the bound LLM, or fall back to deterministic tool usage if provider fails."""
    try:
        return await llm_with_tools.ainvoke(messages)
    except Exception as exc:
        question_lower = question.lower()
        fallback_calls: list[dict] = []
        if any(keyword in question_lower for keyword in ["thời hiệu", "contract", "hợp đồng", "vi phạm"]):
            fallback_calls.append({
                "name": "check_statute_of_limitations",
                "args": {"case_type": "contract"},
                "id": "fallback-statute",
            })

        if any(keyword in question_lower for keyword in ["án lệ", "case law", "court", "vụ án"]):
            fallback_calls.append({
                "name": "lookup_public_legal_resource",
                "args": {"topic": question},
                "id": "fallback-public-resource",
            })

        return FallbackResponse(
            content=(
                f"LLM fallback activated because provider call failed: {type(exc).__name__}. "
                "The exercise will continue using deterministic tool routing."
            ),
            tool_calls=fallback_calls,
        )


async def main():
    load_dotenv()
    llm = get_llm()
    
    tools = [
        search_legal_knowledge,
        check_statute_of_limitations,
        lookup_public_legal_resource,
    ]
    llm_with_tools = llm.bind_tools(tools)
    tool_map = {tool_fn.name: tool_fn for tool_fn in tools}
    
    question = "Thời hiệu khởi kiện vụ vi phạm hợp đồng là bao lâu?"
    
    messages = [
        SystemMessage(content="Bạn là chuyên gia pháp lý. Sử dụng tools để tra cứu thông tin."),
        HumanMessage(content=question),
    ]
    
    print(f"Câu hỏi: {question}\n")
    
    # First LLM call - decide which tools to use
    response = await invoke_llm_with_fallback(llm_with_tools, messages, question)
    messages.append(response)
    
    # Execute tools if requested
    if response.tool_calls:
        for tool_call in response.tool_calls:
            print(f"🔧 Gọi tool: {tool_call['name']}")
            tool_fn = tool_map.get(tool_call["name"])
            tool_result = None
            if tool_fn is not None:
                tool_result = await invoke_tool_with_retry(tool_fn, tool_call["args"])
            
            if tool_result:
                messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))
        
        # Second LLM call - synthesize final answer
        try:
            final_response = await llm_with_tools.ainvoke(messages)
            final_text = final_response.content
        except Exception:
            final_text = (
                "Theo fallback tool execution, thời hiệu khởi kiện vụ vi phạm hợp đồng là "
                f"{check_statute_of_limitations.invoke({'case_type': 'contract'})}."
            )
        print(f"\n✅ Kết quả:\n{final_text}")
    else:
        print(f"\n✅ Kết quả:\n{response.content}")


if __name__ == "__main__":
    asyncio.run(main())
