# response_synthesizer.py
import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
from typing import Dict, Any, List, Generator

# --- 0. Tải biến môi trường và Cấu hình LLM ---
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
llm_synthesizer_model = None

if GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        # Sử dụng model mạnh mẽ cho việc tổng hợp và tạo câu trả lời cuối cùng
        # gemini-1.5-pro-latest là lựa chọn tốt cho khả năng hiểu ngữ cảnh phức tạp và sinh văn bản chất lượng.
        # Hoặc bạn có thể dùng gemini-1.5-flash-latest nếu muốn nhanh hơn và chi phí thấp hơn.
        llm_synthesizer_model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview", 
            # generation_config={"temperature": 0.6} # Nhiệt độ vừa phải cho câu trả lời tự nhiên
        )
        print("--- Response Synthesizer: Gemini model for final response generation initialized. ---")
    except Exception as e:
        print(f"--- Response Synthesizer: Error initializing Gemini model: {e} ---")
else:
    print("--- Response Synthesizer: Error! GOOGLE_API_KEY not found. LLM not initialized. ---")

def _format_chat_history_for_synthesis(chat_history: List[List[str]]) -> List[Dict[str, Any]]:
    """
    Chuyển đổi lịch sử chat của Gradio sang định dạng của google-generativeai SDK cho chat.
    """
    messages = []
    if chat_history:
        for user_turn, bot_turn in chat_history:
            if user_turn:
                messages.append({"role": "user", "parts": [{"text": user_turn}]})
            if bot_turn: # Đảm bảo bot_turn không rỗng
                messages.append({"role": "model", "parts": [{"text": bot_turn}]})
    return messages

def generate_final_response(
    original_user_query: str,
    context_data: Dict[str, Any],
    chat_history_gradio: List[List[str]]
) -> str: # MODIFIED: Returns a single string, not a Generator
    """
    Uses LLM to synthesize information from context_data and chat history
    to generate a final, complete response for the original_user_query.
    Returns the full response as a string.
    """
    if not llm_synthesizer_model:
        return "Sorry, I cannot process your request at this moment due to an issue with the language model."

    context_data_json_string = json.dumps(context_data, indent=2, ensure_ascii=False, default=str)

    prompt_instructions = f"""You are a knowledgeable and helpful financial assistant.
    Your goal is to provide a clear, concise, and accurate answer to the user's original query.
    You will be provided with the user's original query and a JSON object string under "Available Context Data". This JSON object contains all information gathered from previous processing steps, including:
    - 'analyzed_query_details': The initial analysis of the user's query.
    - 'database_info': Results from database queries, if any (check its 'status' and 'data' fields).
    - 'calculated_financial_data': Calculated financial indicators, if any (check 'performed_calculations' and 'errors').
    - 'pdf_document_context': Relevant snippets or summaries from PDF documents, if any.

    Carefully parse and use the information within the 'Available Context Data' JSON to formulate your response.
    Address the user's original query directly.
    Do not make up information if it's not present in the context. If the context doesn't fully answer the query, state that clearly.
    If the context data indicates errors or missing information from previous steps (e.g., in 'database_info.status' or 'calculated_financial_data.errors'), acknowledge them gracefully in your response.
    Maintain a professional and helpful tone. Answer in the same language as the user's original query.

    User's Original Query: "{original_user_query}"

    Available Context Data (JSON object string):
    ```json
    {context_data_json_string}
    ```

    Based on the user's original query and ALL the 'Available Context Data' JSON provided above, please formulate your comprehensive response:
    """
    
    formatted_history = _format_chat_history_for_synthesis(chat_history_gradio)
    
    messages_for_generation = []
    messages_for_generation.extend(formatted_history)
    messages_for_generation.append({
        "role": "user",
        "parts": [prompt_instructions]
    })
    
    print(f"  Response Synthesizer: Sending request to LLM for final answer generation (non-streaming).")

    try:
        # Call generate_content without stream=True to get the full response
        response = llm_synthesizer_model.generate_content(
            messages_for_generation
            # generation_config can be set here if not set at model initialization
        )
        
        full_response_text = ""
        if response.parts:
            full_response_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
        elif hasattr(response, 'text') and response.text:
            full_response_text = response.text
        else:
            print(f"  Response Synthesizer: LLM response structure not as expected or empty. Feedback: {response.prompt_feedback if hasattr(response, 'prompt_feedback') else 'N/A'}")
            full_response_text = "I'm sorry, I couldn't formulate a response based on the provided information."

        print(f"  Response Synthesizer: Non-streaming finished. Full response (start): \"{full_response_text[:200]}...\"")
        return full_response_text.strip()

    except Exception as e:
        print(f"  Response Synthesizer: Error during final response generation by LLM: {e}")
        import traceback
        traceback.print_exc()
        return "Sorry, an error occurred while I was trying to generate a response for you."

# --- Khối Test ---
if __name__ == "__main__":
    if not llm_synthesizer_model:
        print("LLM for response synthesis not initialized. Cannot run tests.")
    else:
        print("\n--- Testing Response Synthesizer ---")

        sample_original_query = "What is MSFT P/E ratio and its 14-day RSI?"
        sample_context_data = {
            "analyzed_query_details": {
                "original_query": "What is MSFT P/E ratio and its 14-day RSI?",
                "query_type": "number",
                "ticker": "MSFT",
                "financial_metrics": ["P/E ratio", "RSI_14"]
            },
            "database_info": {
                "status": "success",
                "sql_executed": "SELECT price_date, adj_close_price, open_price, high_price, low_price, volume FROM daily_stock_prices dp JOIN companies c ON dp.company_id = c.id WHERE c.ticker = 'MSFT' ORDER BY price_date DESC LIMIT 20;",
                "retrieved_data": [ # Dữ liệu giả lập, chỉ lấy 1 dòng
                    {"price_date": "2025-05-19", "adj_close_price": 430.25, "open_price": 428.0, "high_price": 431.50, "low_price": 427.0, "volume": 15000000}
                ]
            },
            "calculated_financial_data": {
                "ticker": "MSFT",
                "performed_calculations": {
                    "P/E Ratio": {"value": 35.27, "price_used": 430.25, "eps_used": 12.20, "source": "yfinance (trailing/forward)"},
                    "RSI_14": {"value": 68.5}
                },
                "data_fetch_summary": {"latest_adj_close_price": 430.25, "price_data_points": 252},
                "errors": []
            }
        }
        sample_chat_history = [
            ["Hello", "Hi there! How can I help you today?"],
            ["I want to know about Microsoft stock.", "Sure, what specific information are you looking for about Microsoft (MSFT)?"]
        ]

        print(f"\nSimulating final response generation for: '{sample_original_query}'")
        print("Context Data:")
        print(json.dumps(sample_context_data, indent=2, ensure_ascii=False, default=str))
        print("\nStreaming final answer from LLM:")
        
        full_final_response = ""
        for chunk in generate_final_response(sample_original_query, sample_context_data, sample_chat_history):
            print(chunk, end="", flush=True)
            full_final_response += chunk
        
        print("\n--- End of final streamed response ---")
        # print(f"Full final response collected: {full_final_response}")

        # Test trường hợp có lỗi
        print("\n--- Test case with error in context ---")
        error_context = {
             "analyzed_query_details": {
                "original_query": "What is XYZ stock price?",
                "query_type": "number",
                "ticker": "XYZ",
                "financial_metrics": ["stock price"]
            },
            "database_info": {"status": "sql_execution_failed_or_no_data", "data": None, "sql_query": "SELECT ..."},
            "calculated_financial_data": { "ticker": "XYZ", "errors": ["Could not fetch historical data for XYZ."]}
        }
        for chunk in generate_final_response("What is XYZ stock price?", error_context, []):
            print(chunk, end="", flush=True)
        print("\n--- End of error test case ---")