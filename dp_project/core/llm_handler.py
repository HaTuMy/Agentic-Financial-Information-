# llm_handler.py (Cập nhật để trích xuất nhiều thực thể hơn)
import os
from dotenv import load_dotenv
import google.generativeai as genai 
import json
import re 

# Load environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
gemini_model = None 

if GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        
        generation_config_json = genai.types.GenerationConfig(
            temperature=0.0, # Để output nhất quán và có cấu trúc
            response_mime_type="application/json" # Yêu cầu Gemini trả về JSON
        )

        gemini_model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview", # Sử dụng model mạnh nhất bạn có
            generation_config=generation_config_json
        )
        print("--- LLM Handler: Google GenAI Model (gemini-3-flash-preview) initialized for structured JSON output. ---")
    except Exception as e:
        print(f"--- LLM Handler: Error initializing Google GenAI Model: {e} ---")
        import traceback
        traceback.print_exc()
else:
    print("--- LLM Handler: Error! GOOGLE_API_KEY not found. LLM not initialized. ---")

# Hàm này vẫn có thể hữu ích sau này, không cần thay đổi
def _format_chat_history_for_google_ai(gradio_history: list) -> list:
    messages = []
    if gradio_history:
        for user_turn, bot_turn in gradio_history:
            if user_turn:
                messages.append({"role": "user", "parts": [user_turn]})
            if bot_turn:
                messages.append({"role": "model", "parts": [bot_turn]})
    return messages

def analyze_query_native_sdk(user_query: str) -> dict:
    if not gemini_model:
        return {
            "error": "Google GenAI Model not initialized properly.",
            "original_query": user_query,
            "query_type": "unknown",
            "company_name": None, # Sẽ là list hoặc None
            "ticker": None,       # Sẽ là list hoặc None
            "report_period": None,
            "financial_metrics": None # Sẽ là list hoặc None
        }

    # System prompt được cập nhật để yêu cầu JSON với nhiều trường hơn,
    # và company_name, ticker là LISTS.
    system_prompt_for_expanded_json = """You are a highly capable financial query analyzer.
    Your ONLY task is to analyze the user's CURRENT query and respond with a single, valid JSON object.
    This JSON object MUST contain the following keys: "original_query", "query_type", "company_name", "ticker", "report_period", and "financial_metrics".

    Field Definitions and Requirements:
    1.  "original_query": (String, Required) MUST be an EXACT, UNMODIFIED copy of the user's CURRENT query.
    2.  "query_type": (String, Required) MUST be one of: "number", "report", "general_query", "general_greeting", "unknown".
        -   "number": For questions about specific stock prices, financial ratios (P/E, EPS), market capitalization, trading volume, or other specific financial figures. This includes comparisons between companies.
        -   "report": For questions asking for information from company financial reports (e.g., 10-K, 10-Q), typically for a specific company (or companies) and a report period.
        -   "general_query": For general questions about a company (or companies), its products, general news, or financial concepts not requiring specific figures or detailed report extraction.
        -   "general_greeting": For simple greetings, thank you notes, or non-informational conversational phrases.
        -   "unknown": If the query is ambiguous, not financially related (unless a general greeting), or doesn't fit other categories.
    3.  "company_name": (List of Strings or null) A list of full official company names if identifiable (e.g., ["Apple Inc.", "Microsoft Corporation"]). If only one company is found, return a list with one element (e.g., ["Apple Inc."]). Infer if possible from ticker(s) or context. Set to null if no companies are applicable/found.
    4.  "ticker": (List of Strings or null) A list of stock ticker symbols (e.g., ["AAPL", "MSFT"]). If only one ticker is found, return a list with one element (e.g., ["AAPL"]). Infer if possible from company name(s) or context. Set to null if no tickers are applicable/found.
    5.  "report_period": (String or null) The specific report period mentioned (e.g., "Q1 2025", "2023 fiscal year", "last quarter"). Standardize to 'Q[1-4]YYYY' or 'YYYY Annual' if possible. Set to null if not applicable/found.
    6.  "financial_metrics": (List of Strings or null) A list of specific financial metrics or data points requested (e.g., ["revenue", "net income", "EPS", "stock price", "moving average", "exponential moving average", "P/E ratio", "MACD", "RSI", "Bollinger"]). Set to null if no specific metrics are explicitly or implicitly requested.

    Example 1 (Single Company):
    User's CURRENT query: "What is the P/E ratio of MSFT and its current stock price?"
    Your JSON response:
    {
    "original_query": "What is the P/E ratio of MSFT and its current stock price?",
    "query_type": "number",
    "company_name": ["Microsoft Corporation"],
    "ticker": ["MSFT"],
    "report_period": null,
    "financial_metrics": ["P/E ratio", "current stock price"]
    }

    Example 2 (Multiple Companies):
    User's CURRENT query: "On January 15, 2025, which company had a higher closing price, Apple or Microsoft?"
    Your JSON response:
    {
    "original_query": "On January 15, 2025, which company had a higher closing price, Apple or Microsoft?",
    "query_type": "number",
    "company_name": ["Apple Inc.", "Microsoft Corporation"],
    "ticker": ["AAPL", "MSFT"],
    "report_period": "January 15, 2025", 
    "financial_metrics": ["closing price"]
    }

    Example 3 (Report for one company):
    User's CURRENT query: "Show me Google's Q2 2024 report."
    Your JSON response:
    {
    "original_query": "Show me Google's Q2 2024 report.",
    "query_type": "report",
    "company_name": ["Google LLC"], 
    "ticker": ["GOOGL"], 
    "report_period": "Q2 2024",
    "financial_metrics": null
    }

    Example 4 (Greeting):
    User's CURRENT query: "Thanks"
    Your JSON response:
    {
    "original_query": "Thanks",
    "query_type": "general_greeting",
    "company_name": null,
    "ticker": null,
    "report_period": null,
    "financial_metrics": null
    }

    Focus ONLY on the CURRENT user query. Your entire response MUST be ONLY the JSON object.
    The user's CURRENT query is: """

    full_prompt = f"{system_prompt_for_expanded_json}\n\"{user_query}\""

    default_error_response = {
        "original_query": user_query,
        "query_type": "unknown",
        "company_name": None, # Default to None
        "ticker": None,       # Default to None
        "report_period": None,
        "financial_metrics": None, # Default to None
        "error": "Failed to get a valid structured response from LLM using native SDK."
    }

    try:
        print(f"  LLM Handler (Native SDK): Sending prompt to Gemini for query: '{user_query}'")
        # print(f"Full prompt being sent:\n{full_prompt}") # Debug

        response = gemini_model.generate_content(full_prompt)
        
        llm_output_string = ""
        try:
            if response.parts:
                llm_output_string = "".join(part.text for part in response.parts if hasattr(part, 'text'))
            elif hasattr(response, 'text') and response.text:
                llm_output_string = response.text
            else:
                print(f"  LLM Handler (Native SDK): Unexpected response structure: {response.prompt_feedback if hasattr(response, 'prompt_feedback') else response}")
                default_error_response["error"] = "Unexpected response structure from LLM."
                return default_error_response
        except Exception as e_text:
            print(f"  LLM Handler (Native SDK): Error extracting text from LLM response: {e_text}")
            default_error_response["error"] = f"Error extracting text from LLM response: {e_text}"
            return default_error_response
        
        print(f"  LLM Handler (Native SDK): Raw string output from LLM: '{llm_output_string}'")
        
        try:
            analysis_dict = json.loads(llm_output_string)
            
            # Đảm bảo các trường có giá trị mặc định là None hoặc list rỗng nếu LLM không trả về
            analysis_dict.setdefault("company_name", None) # Sẽ là list hoặc None
            analysis_dict.setdefault("ticker", None)       # Sẽ là list hoặc None
            analysis_dict.setdefault("report_period", None)
            analysis_dict.setdefault("financial_metrics", None) # Sẽ là list hoặc None

            # Nếu financial_metrics là None từ LLM, chuyển thành list rỗng để nhất quán
            if analysis_dict.get("financial_metrics") is None:
                 analysis_dict["financial_metrics"] = []
            # Tương tự cho company_name và ticker nếu bạn muốn default là list rỗng thay vì None khi không tìm thấy
            # Tuy nhiên, prompt yêu cầu "Set to null if no companies are applicable/found"
            # nên giữ None là phù hợp nếu LLM tuân thủ.

            if analysis_dict.get("original_query") != user_query:
                print(f"  LLM Handler (Native SDK): WARNING - LLM's original_query ('{analysis_dict.get('original_query')}') differs. Overriding.")
                analysis_dict["original_query"] = user_query
            
            valid_query_types = ["number", "report", "general_query", "general_greeting", "unknown"]
            if analysis_dict.get("query_type") not in valid_query_types:
                print(f"  LLM Handler (Native SDK): WARNING - LLM's query_type ('{analysis_dict.get('query_type')}') is invalid. Setting to 'unknown'.")
                analysis_dict["query_type"] = "unknown"

            print(f"  LLM Handler (Native SDK): Parsed analysis: {json.dumps(analysis_dict, indent=2, ensure_ascii=False)}")
            return analysis_dict

        except json.JSONDecodeError as json_e:
            print(f"  LLM Handler (Native SDK): Failed to decode JSON: {json_e}. Output: '{llm_output_string}'")
            default_error_response["error"] = f"Failed to decode JSON from LLM: {json_e}. Raw: {llm_output_string}"
            return default_error_response
        except Exception as parse_e:
            print(f"  LLM Handler (Native SDK): Error processing parsed JSON: {parse_e}")
            default_error_response["error"] = f"Error processing parsed JSON: {parse_e}"
            return default_error_response

    except Exception as e:
        print(f"  LLM Handler (Native SDK): Error during LLM content generation: {e}")
        import traceback
        traceback.print_exc()
        default_error_response["error"] = f"Error during LLM content generation: {str(e)}"
        return default_error_response
    
# Test block (giữ nguyên các câu hỏi test)
if __name__ == "__main__":
    if gemini_model: 
        print("\n--- Testing llm_handler.py (Native SDK - Expanded JSON Output - English) ---")
        
        queries_to_test_en = [
            "What is Apple's stock price today?",
            "Show me Apple's Q1 2025 report.",
            "MSFT P/E ratio?",
            "What is Apple's business situation in the Q1-2025 and Q2-2025 reports?",
            "What are Microsoft's revenue and profit in the 2023 annual report?",
            "Thank you very much!",
            "What is the capital of France?",
            "Tell me about Microsoft general business"
        ]

        for test_query in queries_to_test_en:
            print(f"\nAnalyzing English query: \"{test_query}\"")
            analysis = analyze_query_native_sdk(test_query) 
            print(f"Analysis result:")
            print(json.dumps(analysis, indent=2, ensure_ascii=False))
    else:
        print("Google GenAI Model (gemini_model) for direct JSON output was not initialized. Test cannot run.")