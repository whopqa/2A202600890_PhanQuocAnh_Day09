"""Bài Tập 4: Thêm Privacy Agent vào Multi-Agent System

Hoàn thành các TODO để thêm privacy agent và conditional routing.
"""

import asyncio
import os
import sys
import time
from typing import Annotated, TypedDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from common.llm import get_llm


class FallbackResponse:
    """Small response object used when the live LLM provider is unavailable."""

    def __init__(self, content: str):
        self.content = content


def _last_wins(left: str | None, right: str | None) -> str:
    """Reducer: giá trị mới ghi đè giá trị cũ."""
    return right if right is not None else (left or "")


CONVERSATION_MEMORY: list[dict[str, str]] = []
MAX_MEMORY_ITEMS = 5


def _memory_context() -> str:
    """Return compact conversation memory for the next run."""
    if not CONVERSATION_MEMORY:
        return "Chưa có lịch sử hội thoại."
    recent = CONVERSATION_MEMORY[-MAX_MEMORY_ITEMS:]
    return "\n".join(
        f"- Q: {item['question']}\n  A: {item['answer'][:300]}"
        for item in recent
    )


def _remember(question: str, answer: str) -> None:
    """Store the latest conversation turn in memory."""
    CONVERSATION_MEMORY.append({"question": question, "answer": answer})
    del CONVERSATION_MEMORY[:-MAX_MEMORY_ITEMS]


def invoke_llm_with_retry(llm, messages: list[HumanMessage], agent_name: str, max_attempts: int = 3):
    """Call an LLM with retry so one transient provider error does not fail the graph."""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return llm.invoke(messages)
        except Exception as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            wait_seconds = 0.5 * (2 ** (attempt - 1))
            print(f"[{agent_name}] Lỗi tạm thời, thử lại lần {attempt + 1}/{max_attempts}...")
            time.sleep(wait_seconds)

    return FallbackResponse(
        f"{agent_name} fallback: không gọi được LLM sau {max_attempts} lần "
        f"({type(last_error).__name__}). Vui lòng kiểm tra API key/credits; "
        "graph vẫn tiếp tục để minh họa error handling và multi-agent flow."
    )


class State(TypedDict):
    question: str
    conversation_context: Annotated[str, _last_wins]
    law_analysis: Annotated[str, _last_wins]
    tax_analysis: Annotated[str, _last_wins]
    compliance_analysis: Annotated[str, _last_wins]
    privacy_analysis: Annotated[str, _last_wins]
    financial_analysis: Annotated[str, _last_wins]
    final_response: str


def load_memory(state: State) -> dict:
    """Load recent conversation memory into graph state."""
    return {"conversation_context": _memory_context()}


def law_agent(state: State) -> dict:
    """Agent phân tích pháp lý tổng quát."""
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia pháp lý. Phân tích câu hỏi sau:

{state['question']}

Lịch sử hội thoại gần đây:
{state.get('conversation_context', 'Chưa có lịch sử hội thoại.')}

Tập trung vào: hợp đồng, trách nhiệm dân sự, quyền và nghĩa vụ pháp lý."""
    
    response = invoke_llm_with_retry(llm, [HumanMessage(content=prompt)], "law_agent")
    return {"law_analysis": response.content}


def check_routing(state: State) -> dict:
    """Marker node before conditional routing."""
    return {}


def route_to_agents(state: State) -> list[Send]:
    """Quyết định gọi agents nào dựa trên nội dung câu hỏi."""
    question_lower = state["question"].lower()
    tasks = []
    
    if any(kw in question_lower for kw in ["tax", "irs", "thuế"]):
        tasks.append(Send("tax_agent", state))
    
    if any(kw in question_lower for kw in ["compliance", "sec", "regulation"]):
        tasks.append(Send("compliance_agent", state))
    
    if any(kw in question_lower for kw in ["data", "privacy", "gdpr", "dữ liệu"]):
        tasks.append(Send("privacy_agent", state))

    if any(kw in question_lower for kw in ["financial", "finance", "loss", "damage", "damages", "revenue", "thiệt hại", "tài chính"]):
        tasks.append(Send("financial_agent", state))
    
    return tasks if tasks else [Send("aggregate_results", state)]


def tax_agent(state: State) -> dict:
    """Agent chuyên về thuế."""
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia thuế. Phân tích khía cạnh thuế trong câu hỏi:

Câu hỏi: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Tập trung: IRS, tax evasion, penalties, FBAR, FATCA."""
    
    response = invoke_llm_with_retry(llm, [HumanMessage(content=prompt)], "tax_agent")
    return {"tax_analysis": response.content}


def compliance_agent(state: State) -> dict:
    """Agent chuyên về compliance."""
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia compliance. Phân tích khía cạnh tuân thủ:

Câu hỏi: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Tập trung: SEC, SOX, FCPA, AML, regulatory violations."""
    
    response = invoke_llm_with_retry(llm, [HumanMessage(content=prompt)], "compliance_agent")
    return {"compliance_analysis": response.content}


def privacy_agent(state: State) -> dict:
    """Agent chuyên về bảo vệ dữ liệu cá nhân và GDPR."""
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia về GDPR và luật bảo vệ dữ liệu cá nhân.

Câu hỏi: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Tập trung: GDPR, data protection, privacy rights, data breach, nghĩa vụ thông báo
và biện pháp giảm thiểu rủi ro pháp lý."""
    
    response = invoke_llm_with_retry(llm, [HumanMessage(content=prompt)], "privacy_agent")
    return {"privacy_analysis": response.content}


def financial_agent(state: State) -> dict:
    """Agent chuyên phân tích thiệt hại tài chính và exposure."""
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia phân tích thiệt hại tài chính trong tranh chấp doanh nghiệp.

Câu hỏi: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Hãy ước lượng các nhóm thiệt hại có thể phát sinh: direct damages, consequential
damages, remediation cost, legal cost, regulatory fine exposure và business impact.
Không bịa số cụ thể nếu đề bài không cung cấp dữ liệu."""

    response = invoke_llm_with_retry(llm, [HumanMessage(content=prompt)], "financial_agent")
    return {"financial_analysis": response.content}


def aggregate_results(state: State) -> dict:
    """Tổng hợp kết quả từ tất cả agents."""
    llm = get_llm()
    
    sections = []
    if state.get("law_analysis"):
        sections.append(f"📋 PHÂN TÍCH PHÁP LÝ:\n{state['law_analysis']}")
    if state.get("tax_analysis"):
        sections.append(f"💰 PHÂN TÍCH THUẾ:\n{state['tax_analysis']}")
    if state.get("compliance_analysis"):
        sections.append(f"✅ PHÂN TÍCH TUÂN THỦ:\n{state['compliance_analysis']}")
    if state.get("privacy_analysis"):
        sections.append(f"🔒 PHÂN TÍCH BẢO VỆ DỮ LIỆU:\n{state['privacy_analysis']}")
    if state.get("financial_analysis"):
        sections.append(f"📈 PHÂN TÍCH TÀI CHÍNH:\n{state['financial_analysis']}")
    
    combined = "\n\n".join(sections)
    
    prompt = f"""Tổng hợp các phân tích sau thành một báo cáo pháp lý hoàn chỉnh:

{combined}

Câu hỏi gốc: {state['question']}

Hãy tạo một báo cáo ngắn gọn, có cấu trúc rõ ràng."""
    
    response = invoke_llm_with_retry(llm, [HumanMessage(content=prompt)], "aggregate_results")
    _remember(state["question"], response.content)
    return {"final_response": response.content}


def build_graph() -> StateGraph:
    """Xây dựng multi-agent graph."""
    graph = StateGraph(State)
    
    # Add nodes
    graph.add_node("load_memory", load_memory)
    graph.add_node("law_agent", law_agent)
    graph.add_node("check_routing", check_routing)
    graph.add_node("tax_agent", tax_agent)
    graph.add_node("compliance_agent", compliance_agent)
    graph.add_node("privacy_agent", privacy_agent)
    graph.add_node("financial_agent", financial_agent)
    graph.add_node("aggregate_results", aggregate_results)
    
    # Define edges
    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "law_agent")
    graph.add_edge("law_agent", "check_routing")
    graph.add_conditional_edges("check_routing", route_to_agents)
    graph.add_edge("tax_agent", "aggregate_results")
    graph.add_edge("compliance_agent", "aggregate_results")
    graph.add_edge("privacy_agent", "aggregate_results")
    graph.add_edge("financial_agent", "aggregate_results")
    graph.add_edge("aggregate_results", END)
    
    return graph.compile()


async def main():
    load_dotenv()
    
    # Test với câu hỏi có liên quan đến privacy
    question = "Nếu công ty bị rò rỉ dữ liệu khách hàng, hậu quả pháp lý, thuế và thiệt hại tài chính là gì?"
    
    print("=" * 70)
    print("MULTI-AGENT SYSTEM với Privacy Agent")
    print("=" * 70)
    print(f"\nCâu hỏi: {question}\n")
    print("Đang xử lý qua các agents...\n")
    
    graph = build_graph()
    
    result = await graph.ainvoke({
        "question": question,
        "conversation_context": "",
        "law_analysis": "",
        "tax_analysis": "",
        "compliance_analysis": "",
        "privacy_analysis": "",
        "financial_analysis": "",
        "final_response": "",
    })
    
    print("\n" + "=" * 70)
    print("KẾT QUẢ CUỐI CÙNG")
    print("=" * 70)
    print(result["final_response"])
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
