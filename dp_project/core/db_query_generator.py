import os
from dotenv import load_dotenv
import json
from sqlalchemy import create_engine, text, exc as sqlalchemy_exc
import google.generativeai as genai
import time # For delays in testing
from typing import Dict, Any, List, Optional # For type hinting

# --- 0. Tải biến môi trường và Cấu hình (Giữ nguyên) ---
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DB_HOST = os.getenv("DB_HOST")
# ... (các biến môi trường DB khác và kiểm tra của chúng giữ nguyên) ...
# DB_PORT = os.getenv("DB_PORT")
DB_PORT = 5432
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

if not GOOGLE_API_KEY:
    print("STOP: GOOGLE_API_KEY not set in .env file.")
    exit()
if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
    print("STOP: Database environment variables not fully set in .env file.")
    exit()

genai.configure(api_key=GOOGLE_API_KEY)
llm_sql_generator = None
try:
    llm_sql_generator = genai.GenerativeModel(
        model_name="gemini-3-flash-preview",
        generation_config={"temperature": 0.0}
    )
    print("--- DB Query Generator: Gemini model for SQL generation initialized. ---")
except Exception as e:
    print(f"--- DB Query Generator: Error initializing Gemini model: {e} ---")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
try:
    db_engine = create_engine(DATABASE_URL)
    print("--- DB Query Generator: PostgreSQL engine created. ---")
except Exception as e:
    print(f"--- DB Query Generator: Error creating PostgreSQL engine: {e} ---")
    db_engine = None

# --- Mô tả Schema Database cho LLM (Cập nhật phần Important Notes) ---
# --- Mô tả Schema Database cho LLM (Cập nhật phần Important Notes) ---
DB_SCHEMA_DESCRIPTION = """
You have access to a PostgreSQL database with the following tables and columns:

Table: companies
Description: Stores information about publicly traded companies.
Columns:
  id (SERIAL PRIMARY KEY): Unique identifier for the company.
  ticker (VARCHAR(10) UNIQUE NOT NULL): Stock ticker symbol (e.g., 'AAPL', 'MSFT').
  company_name (VARCHAR(255)): Full name of the company.
  sector (VARCHAR(100)): The sector the company operates in.
  industry (VARCHAR(100)): The specific industry of the company.
  exchange (VARCHAR(50)): The stock exchange where the company's stock is traded.
  country (VARCHAR(100)): The country where the company is based.
  summary (TEXT): A brief summary of the company's business.
  website (VARCHAR(255)): The company's official website URL.

Table: daily_stock_prices
Description: Stores daily Open, High, Low, Close (OHLC) price data and volume for stocks.
Columns:
  id (SERIAL PRIMARY KEY): Unique identifier for the price record.
  company_id (INTEGER NOT NULL, FOREIGN KEY to companies.id): Links to the company in the 'companies' table.
  price_date (DATE NOT NULL): The date of the stock price data.
  open_price (NUMERIC(19, 4)): The opening price for the day.
  high_price (NUMERIC(19, 4)): The highest price during the day.
  low_price (NUMERIC(19, 4)): The lowest price during the day.
  close_price (NUMERIC(19, 4)): The closing price for the day.
  volume (BIGINT): The number of shares traded during the day.

Relationships:
- daily_stock_prices.company_id references companies.id.

Important Notes for SQL Generation:
- **Crucial for Metrics**: When the user asks for a specific financial metric (e.g., 'stock price', 'sector', 'volume', 'company summary') or implies a comparison, your SELECT clause MUST include the actual column(s) for those metrics from the 'daily_stock_prices' or 'companies' tables, along with a company identifier (like `c.ticker` or `c.company_name`).
- **Querying Company Attributes**: For questions about company-specific attributes like 'sector', 'industry', 'company_name', 'summary', 'website', 'exchange', or 'country', query the `companies` table. Ensure you select the requested attribute and `c.ticker`.
- **Date Handling for Periods**: If a period like "during YYYY" (e.g., "during 2024") is given, infer the start date as 'YYYY-01-02' and the end date as 'YYYY-12-31' for queries on `daily_stock_prices`.
- **Price Change (Absolute or Percentage) for ONE specific ticker**: Fetch `close_price` for the ticker at both start and end dates. Select `c.ticker`, `dsp.price_date`, `dsp.close_price`. Calculation is done later.
- **Data for Comparisons Across ALL Companies over a period**: For "largest/smallest" or "highest/lowest" price changes (absolute or percentage) across all companies over a period, your SQL should fetch `close_price` for ALL companies on the inferred start_date AND end_date of that period. Select `c.ticker`, `dsp.price_date`, `dsp.close_price`. Use `WHERE dsp.price_date IN (start_date, end_date)`. Calculation and ranking are done later.
- **Highest/Lowest Metric on a Specific Date (Across ALL Companies)**: Query all companies for the metric on that date, then `ORDER BY metric_column DESC/ASC LIMIT 1`. Select `c.ticker` and the metric.
- **Latest Data**: For "latest price" for specific ticker(s), use `ORDER BY price_date DESC LIMIT 1` per ticker, selecting `close_price` and `price_date`.
- **P/E Ratio**: Retrieve the latest 'close_price'. Calculation is done later.
- **Output 'NO_QUERY_POSSIBLE'**: If a query cannot be formed from the schema for the given request.
- **Tickers**: Use `ticker` symbol(s) in `WHERE` clauses. For multiple tickers, use `WHERE c.ticker IN (...)`. Always select `c.ticker`.
- **Preferred Price**: Use `close_price` for "price" or "closing price".
- **Average price/average close price**: ALWAYS select c.ticker and dsp.close_price. Example: select c.ticker, dsp.close_price FROM companies c JOIN daily_stock_prices dsp ON c.id = dsp.company_id WHERE c.ticker = 'MSFT' AND dsp.price_date BETWEEN '2025-03-01' AND '2025-03-31'
"""

# --- 1. Hàm tạo câu lệnh SQL từ LLM (Cập nhật Prompt) ---
def generate_sql_query_from_analysis(analyzed_query: Dict[str, Any]) -> Optional[str]:
    if not llm_sql_generator:
        print("  SQL Gen: LLM for SQL generation not initialized.")
        return None

    original_question = analyzed_query.get("original_query", "")
    query_type = analyzed_query.get("query_type", "unknown")
    tickers: Optional[List[str]] = analyzed_query.get("ticker") 
    metrics: Optional[List[str]] = analyzed_query.get("financial_metrics", [])
    report_period = analyzed_query.get("report_period") 
    
    metrics_str = ", ".join(metrics) if metrics else "Not specified"
    tickers_str = ", ".join(tickers) if tickers and len(tickers) > 0 else "Not specified (may imply all companies for comparisons)"
    
    prompt_parts = [
        DB_SCHEMA_DESCRIPTION,
        f"\nUser's original question: {original_question}",
        "\nAnalysis of the user's question (input to you):",
        f"  Query Type: {query_type}",
        f"  Ticker(s): {tickers_str}",
        f"  Financial Metrics/Info Requested: {metrics_str}",
        f"  Report Period/Specific Date(s): {report_period if report_period else 'N/A'}",
        "\nBased on the user's question, the analysis, and the database schema provided, generate a single, syntactically correct PostgreSQL SELECT query to retrieve the relevant data.",
        "Your SELECT clause MUST include the actual data columns for the 'Financial Metrics/Info Requested' AND company identifiers (like c.ticker). For example, if 'stock price' is requested, SELECT 'dsp.close_price'. If 'sector' is requested, SELECT 'c.sector'.",
        "If comparing companies or if multiple tickers are given, SELECT the company identifier (e.g., c.ticker) AND the metric being compared for ALL relevant companies.",
        "If the question asks for a change (absolute or percentage) for specific tickers over a period, retrieve the start and end prices for those tickers.",
        "If the question asks for a comparison across ALL companies over a period (e.g., 'largest increase during 2024') AND no specific tickers are mentioned in the analysis, your SQL query should fetch the `close_price` for ALL companies on the inferred start_date and end_date of that period (e.g., for 'during 2024', use '2024-01-02' and '2024-12-31'). The query should look like: SELECT c.ticker, dsp.close_price, dsp.price_date FROM companies c JOIN daily_stock_prices dsp ON c.id = dsp.company_id WHERE dsp.price_date IN ('YYYY-MM-DD_start', 'YYYY-MM-DD_end');. The final calculation and ranking will be done in a later step.",
        "If the question asks for an average price (or average closing price), the query should retrieve close_price attribute of the ticker from daily_stock_prices from YYYY-MM-02 to the end of the month (YYYY-MM-30 or YYYY-MM-31). Example: SELECT dsp.close_price FROM companies c JOIN daily_stock_prices dsp ON c.id=dsp.company_id WHERE c.ticker='MSFT' AND dsp.price_date BETWEEN '2025-03-02' AND '2025-03-31'"
        "ONLY output the SQL query. If a query cannot be formed, output 'NO_QUERY_POSSIBLE'."
    ]

    if query_type == "number":
        prompt_parts.append("For 'number' type queries, if a specific metric like 'P/E ratio' is asked, query for related data like the latest 'close_price' for the given ticker(s). If a direct stock price is asked (e.g., 'today', 'latest'), query for the latest 'close_price' and 'price_date'.")
    elif query_type == "general_query":
        prompt_parts.append("For 'general_query' type, generate a SQL query ONLY IF the 'Financial Metrics/Info Requested' or the 'User's original question' clearly asks for attributes available in the 'companies' table (e.g., 'sector', 'industry', 'summary', 'website', 'company_name', 'exchange', 'country') for the given ticker(s). If the query is too broad or asks for information not in the 'companies' table columns, output 'NO_QUERY_POSSIBLE'.")
    
    # Updated and new examples
    prompt_parts.append("Example for 'number' - latest price: SELECT c.ticker, dsp.close_price, dsp.price_date FROM daily_stock_prices dsp JOIN companies c ON dsp.company_id = c.id WHERE c.ticker = 'MSFT' ORDER BY dsp.price_date DESC LIMIT 1;")
    prompt_parts.append("Example for 'general_query' - company sector (analysis: ticker ['AAPL']): SELECT c.ticker, c.sector FROM companies c WHERE c.ticker = 'AAPL';")
    prompt_parts.append("Example for 'general_query' - company summary (analysis: ticker ['MSFT']): SELECT c.ticker, c.summary FROM companies c WHERE c.ticker = 'MSFT';")
    prompt_parts.append("Example for 'general_query' - company website (analysis: ticker ['GOOG']): SELECT c.ticker, c.website FROM companies c WHERE c.ticker = 'GOOG';")
    prompt_parts.append("Example for 'number' comparison - specific date (analysis: tickers ['AAPL', 'MSFT'], metrics ['closing price'], report_period '2024-10-01'): SELECT c.ticker, dsp.close_price, dsp.price_date FROM daily_stock_prices dsp JOIN companies c ON dsp.company_id = c.id WHERE c.ticker IN ('AAPL', 'MSFT') AND dsp.price_date = '2024-10-01';")
    prompt_parts.append("Example for 'number' - highest price on a specific date (analysis: tickers null, metrics ['highest closing price'], report_period 'July 1, 2024'): SELECT c.ticker, c.company_name, dsp.close_price FROM daily_stock_prices dsp JOIN companies c ON dsp.company_id = c.id WHERE dsp.price_date = '2024-07-01' ORDER BY dsp.close_price DESC LIMIT 1;")
    prompt_parts.append("Example for 'number' - data for price change comparison across ALL companies (analysis: tickers null, metrics ['largest absolute increase', 'closing price'], report_period 'during 2024'): SELECT c.ticker, dsp.close_price, dsp.price_date FROM companies c JOIN daily_stock_prices dsp ON c.id = dsp.company_id WHERE dsp.price_date IN ('2024-01-02', '2024-12-31');") # LLM should infer start/end dates for 'during 2024'


    full_prompt = "\n".join(prompt_parts)

    print(f"  SQL Gen: Sending prompt to LLM for SQL generation (query: '{original_question}')")
    # print(f"  DEBUG SQL Gen Prompt:\n{full_prompt}\n") 
    
    try:
        response = llm_sql_generator.generate_content(full_prompt)
        sql_query = response.text.strip() if hasattr(response, 'text') and response.text else ""
        
        if sql_query.startswith("```sql"): sql_query = sql_query[6:]
        if sql_query.endswith("```"): sql_query = sql_query[:-3]
        sql_query = sql_query.strip().rstrip(';')

        print(f"  SQL Gen: LLM generated SQL: {sql_query}")

        if "NO_QUERY_POSSIBLE" in sql_query.upper() or not sql_query:
            print("  SQL Gen: LLM indicated no query is possible or returned empty.")
            return None
        
        if not sql_query.upper().startswith("SELECT"):
            print(f"  SQL Gen: WARNING - Generated query is not a SELECT statement: {sql_query}")
            return None
        return sql_query
    except Exception as e:
        print(f"  SQL Gen: Error during SQL generation by LLM: {e}")
        return None

# --- 2. Hàm thực thi câu lệnh SQL (Giữ nguyên) ---
def execute_sql_query(sql_query: str) -> list[dict] | None:
    print(DB_PORT)
    # ... (Nội dung hàm này giữ nguyên như trước - tôi sẽ rút gọn ở đây để tiết kiệm token) ...
    if not db_engine: print("  DB Exec: Database engine not initialized."); return None
    if not sql_query: print("  DB Exec: No SQL query provided."); return None
    print(f"  DB Exec: Executing SQL query: {sql_query}")
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text(sql_query))
            rows = result.mappings().all() 
            print('rows: ', rows)
            print(f"  DB Exec: Query executed successfully, {len(rows)} row(s) returned.")
            return [dict(row) for row in rows]
    except sqlalchemy_exc.SQLAlchemyError as e:
        print(f"  DB Exec: Error executing SQL query: {e}")
        return None
    except Exception as e_gen:
        print(f"  DB Exec: A general error occurred during SQL execution: {e_gen}")
        return None

# --- Hàm chính của file này (Giữ nguyên logic quyết định, nhưng prompt cho LLM đã thay đổi) ---
def get_data_from_postgres_for_query(analyzed_query_input: Dict[str, Any]) -> Dict[str, Any]:
    # ... (Nội dung hàm này giữ nguyên như trước, nó sẽ gọi generate_sql_query_from_analysis đã được cập nhật) ...
    print(f"\n--- DB Query Generator: Processing analyzed query ---")
    print(f"Input analysis: {json.dumps(analyzed_query_input, indent=2, ensure_ascii=False)}")
    query_type = analyzed_query_input.get("query_type")
    tickers: Optional[List[str]] = analyzed_query_input.get("ticker")
    proceed_with_sql = False
    reason_for_skipping = ""
    # Logic quyết định proceed_with_sql giờ đây linh hoạt hơn.
    # Nếu query_type là number, và có metrics, ngay cả khi không có ticker (cho trường hợp highest/lowest)
    if query_type == "number":
        if analyzed_query_input.get("financial_metrics"): # Cần có metrics để biết so sánh cái gì
            proceed_with_sql = True
            print(f"  Query type is 'number'. Will attempt SQL generation.")
        else:
            reason_for_skipping = "Query type is 'number' but no financial_metrics specified for comparison/retrieval."
    elif query_type == "general_query":
        if tickers and len(tickers) > 0:
            proceed_with_sql = True
            print(f"  Query type is 'general_query' with ticker(s) and metrics. Will attempt SQL generation.")
        else:
            reason_for_skipping = "Query type 'general_query' requires specific tickers and metrics for company attribute lookup."
    elif query_type == "report": # Có thể vẫn query bảng companies nếu có ticker và metrics phù hợp
         if tickers and len(tickers) > 0 and analyzed_query_input.get("financial_metrics"):
            proceed_with_sql = True
            print(f"  Query type is 'report' with ticker(s) and metrics. Will attempt SQL for general company info.")
         else:
            reason_for_skipping = "Query type 'report' for SQL needs specific tickers and metrics for company attribute lookup."
    else:
        reason_for_skipping = f"Query type '{query_type}' is not targeted for direct SQL database query at this stage."
    
    if not proceed_with_sql:
        print(f"  {reason_for_skipping} Skipping SQL generation.")
        return {"status": "skipped_sql_generation", "reason": reason_for_skipping, "data": None, "sql_query": None}
    
    sql_query = generate_sql_query_from_analysis(analyzed_query_input)
    if not sql_query:
        print("  Failed to generate SQL query.")
        return {"status": "sql_generation_failed", "data": None, "sql_query": None}
    
    query_result = execute_sql_query(sql_query)
    status_msg = "sql_execution_failed"
    if query_result is None: 
        print(f"  SQL query execution failed or an error occurred.")
    elif not query_result: 
        status_msg = "sql_execution_success_no_data"
        print(f"  SQL query executed successfully but returned no data.")
    else: 
        status_msg = "success"
    return {"status": status_msg, "data": query_result if isinstance(query_result, list) else None, "sql_query": sql_query}


# --- Khối Test (Cập nhật ví dụ) ---
if __name__ == "__main__":
    if not llm_sql_generator or not db_engine:
        print("LLM for SQL generation or DB engine not initialized. Cannot run tests.")
    else:
        print("\n--- Testing DB Query Generator (with general_query handling) ---")
        
        sample_analyzed_queries = [
            {
                "original_query": "What is Apple's stock price today?",
                "query_type": "number", "ticker": "AAPL", "financial_metrics": ["stock price"]
            },
            {
                "original_query": "MSFT P/E ratio?",
                "query_type": "number", "ticker": "MSFT", "financial_metrics": ["P/E ratio", "latest stock price"]
            },
            { # Test case cho general_query
                "original_query": "What is the sector of Apple?",
                "query_type": "general_query", "ticker": "AAPL", "financial_metrics": ["sector"]
            },
            { # Test case cho general_query
                "original_query": "Tell me a summary about MSFT.",
                "query_type": "general_query", "ticker": "MSFT", "financial_metrics": ["summary"]
            },
            { # Test case general_query không có metrics rõ ràng, LLM tự suy luận
                "original_query": "What exchange is AAPL traded on?",
                "query_type": "general_query", "ticker": "AAPL", "financial_metrics": None
            },
            { # Test case general_query không nên tạo SQL
                "original_query": "What are the latest financial news?",
                "query_type": "general_query", "ticker": None, "financial_metrics": ["news"]
            },
            { # Test case report (có thể lấy thông tin công ty)
                "original_query": "I am reading Apple's Q1 2025 report, what is their main industry?",
                "query_type": "report", "ticker": "AAPL", "company_name": "Apple Inc.", "report_period": "Q1 2025", "financial_metrics": ["industry"]
            },
            {
                "original_query": "Thank you!",
                "query_type": "general_greeting", "ticker": None, "financial_metrics": None
            }
        ]

        for i, analyzed_query in enumerate(sample_analyzed_queries):
            print(f"\n--- Test Case {i+1} ---")
            result = get_data_from_postgres_for_query(analyzed_query)
            print("\n  Result from DB Query Generator:")
            # default=str để xử lý các kiểu dữ liệu không serialize được JSON mặc định (ví dụ: date, datetime)
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str)) 
            if i < len(sample_analyzed_queries) - 1:
                 time.sleep(2) # Chờ giữa các lần gọi LLM