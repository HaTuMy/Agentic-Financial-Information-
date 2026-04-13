# langgraph_orchestrator.py
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
import json

# Import các hàm xử lý từ các module còn lại
from core.llm_handler import analyze_query_native_sdk
from core.db_query_generator import get_data_from_postgres_for_query
from core.response_synthesizer import generate_final_response

# --- 1. Định nghĩa State của Graph ---
class AgentState(TypedDict):
    original_user_query: str
    chat_history: List[List[str]]
    analyzed_query: Optional[Dict[str, Any]]
    db_query_results: Optional[Dict[str, Any]]
    final_answer: Optional[str]
    error_message: Optional[str]


# --- 2. Định nghĩa các Node Functions ---
def entry_node(state: AgentState) -> Dict[str, Any]:
    print("--- LangGraph: Entry Node ---")
    return {}

def analyze_query_node(state: AgentState) -> Dict[str, Any]:
    print("--- LangGraph: Analyzing Query Node ---")
    user_query = state["original_user_query"]
    analysis = analyze_query_native_sdk(user_query)
    if analysis.get("error"):
        return {"error_message": f"Query analysis failed: {analysis.get('error')}"}
    return {"analyzed_query": analysis}

def db_query_node(state: AgentState) -> Dict[str, Any]:
    print("--- LangGraph: Database Query Node ---")
    analyzed_query = state.get("analyzed_query")
    if not analyzed_query:
        return {"error_message": "Cannot query DB: Analyzed query is missing."}
    db_results = get_data_from_postgres_for_query(analyzed_query)
    return {"db_query_results": db_results}

def synthesize_response_node(state: AgentState) -> Dict[str, Any]:
    print("--- LangGraph: Synthesize Response Node ---")
    user_query = state["original_user_query"]
    chat_history = state["chat_history"]

    context_data = {
        "analyzed_query_details": state.get("analyzed_query"),
        "database_info": state.get("db_query_results"),
    }

    if state.get("error_message"):
        context_data["previous_errors"] = state["error_message"]
        print(f"  Synthesizer received error: {state['error_message']}")

    response_output = generate_final_response(user_query, context_data, chat_history)
    return {"final_answer": response_output}


# --- 3. Conditional Routing ---
def router_after_analysis(state: AgentState) -> str:
    print("--- LangGraph: Router After Analysis ---")
    
    # Nếu có lỗi ngay từ bước phân tích, đi thẳng đến node tổng hợp để báo lỗi cho user
    if state.get("error_message"):
        print("  Routing to synthesize due to error in analysis.")
        return "synthesize_direct"

    analyzed_query = state.get("analyzed_query")
    query_type = analyzed_query.get("query_type") if analyzed_query else "unknown"
    print(f"  Query type for routing: {query_type}")

    # Chỉ đi vào nhánh DB nếu là câu hỏi cần số liệu hoặc truy vấn thông thường
    if query_type in ["number", "general_query"]:
        return "db_path"
    else:  # Các loại khác như chào hỏi, không rõ, báo cáo...
        return "synthesize_direct"


# --- 4. Xây dựng Graph ---
def create_agent_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    # Thêm các Node
    workflow.add_node("entry", entry_node)
    workflow.add_node("analyze_query", analyze_query_node)
    workflow.add_node("query_database", db_query_node)
    workflow.add_node("synthesize_response", synthesize_response_node)

    # Thiết lập luồng đi
    workflow.set_entry_point("entry")
    workflow.add_edge("entry", "analyze_query")

    # Luồng điều kiện sau khi phân tích
    workflow.add_conditional_edges(
        "analyze_query",
        router_after_analysis,
        {
            "db_path": "query_database",
            "synthesize_direct": "synthesize_response"
        }
    )

    # Sau khi truy vấn DB xong thì tổng hợp kết quả
    workflow.add_edge("query_database", "synthesize_response")
    
    # Kết thúc tại node tổng hợp
    workflow.add_edge("synthesize_response", END)

    app = workflow.compile()
    print("--- LangGraph: Agent graph compiled successfully! ---")
    return app


def create_answer_to_gradio(text: str):
    # Khởi tạo graph mỗi lần nhận câu hỏi từ Gradio
    app = create_agent_graph()

    initial_state = AgentState(
        original_user_query=text,
        chat_history=[],
        analyzed_query=None,
        db_query_results=None,
        final_answer=None,
        error_message=None
    )

    # Chạy luồng
    final_state_output = app.invoke(initial_state)
    return final_state_output["final_answer"]


if __name__ == '__main__':
    # Test thử một câu trong terminal
    result = create_answer_to_gradio("What is Apple's stock price today?")
    print(f"\nFINAL RESULT:\n{result}")