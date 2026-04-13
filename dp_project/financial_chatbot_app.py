# financial_chatbot_app.py
import gradio as gr
import json
from agent.langgraph_orchestrator import create_answer_to_gradio

# --- Hàm Backend (Gradio Interface Function) ---
def process_user_query(user_message: str, chat_history: list) -> str:

    display_output = create_answer_to_gradio(user_message)

    # print(f"--- Gradio App: Nhận được từ người dùng ---")
    # print(f"Câu hỏi: '{user_message}'")

    # if not active_llm_instance:
    #     return "Lỗi: LLM (Native SDK) chưa được khởi tạo ở backend. Vui lòng kiểm tra API Key và console của llm_handler."

    # # Gọi hàm analyze_query_native_sdk từ llm_handler
    # # Hàm này hiện tại chỉ nhận user_message
    # analysis_result_dict = analyze_query_native_sdk(user_message)
    
    # # print(f"--- Gradio App: Kết quả phân tích (Native SDK) từ backend LLM ---")
    
    # display_output = f"Kết quả phân tích (Native SDK):\n```json\n{json.dumps(analysis_result_dict, indent=2, ensure_ascii=False)}\n```"
    
    return display_output


# --- Hàm chính để khởi chạy giao diện Gradio---
def main():
    print("--- Khởi chạy Giao diện Chatbot Tài chính Gradio (LLM Native SDK) ---")

    iface = gr.ChatInterface(
        fn=process_user_query,
        title="Hệ thống Thông tin Tài chính Thông minh (Agentic Financial Information System)",
        description="Chào mừng bạn! Hãy nhập câu hỏi và hệ thống sẽ trả lời.",
        chatbot=gr.Chatbot(
            height=600,
            show_label=False,
            bubble_full_width=False,
            show_copy_button=True,
        ),
        textbox=gr.Textbox(
            placeholder="Nhập câu hỏi của bạn ở đây...",
            container=False,
            scale=7
        ),
        examples=[ # Cập nhật ví dụ sang tiếng Anh
            ["What is Apple's stock price today?"],
            ["Show me Apple's Q1 2025 report."],
            ["Thank you very much!"],
            ["What is the capital of France?"],
            ["Tell me about Microsoft general business"]
        ],
    )

    iface.launch()
    print("--- Giao diện Gradio đã đóng ---")

if __name__ == "__main__":
    main()