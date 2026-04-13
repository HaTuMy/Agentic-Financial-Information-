import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD").strip()

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

def create_tables():
    create_companies_table_sql = """
    CREATE TABLE IF NOT EXISTS companies (
        id SERIAL PRIMARY KEY,
        ticker VARCHAR(10) UNIQUE NOT NULL,
        company_name VARCHAR(255),
        sector VARCHAR(100),
        industry VARCHAR(100),
        exchange VARCHAR(50),        
        country VARCHAR(100),        
        summary TEXT,                
        website VARCHAR(255)
    );
    """
    create_daily_prices_table_sql = """
    CREATE TABLE IF NOT EXISTS daily_stock_prices (
        id SERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL,
        price_date DATE NOT NULL,
        open_price NUMERIC(19, 4),
        high_price NUMERIC(19, 4),
        low_price NUMERIC(19, 4),
        close_price NUMERIC(19, 4),
        volume BIGINT,
        FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE,
        CONSTRAINT uq_company_date UNIQUE (company_id, price_date)
    );
    """
    try:
        with engine.connect() as connection:
            connection.execute(text(create_companies_table_sql))
            connection.execute(text(create_daily_prices_table_sql))
            connection.commit()
        print("✅ Success: Tables created.")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")

def ingest_from_local_csv():
    try:
        # Đường dẫn file CSV (My kiểm tra lại vị trí file so với folder này nhé)
        info_df = pd.read_csv('../../djia_companies_20260411.csv')
        prices_df = pd.read_csv('../../djia_prices_20260411.csv')
        
        with engine.connect() as conn:
            for _, row in info_df.iterrows():
                insert_comp = text("""
                    INSERT INTO companies (ticker, company_name, sector, industry, country, website)
                    VALUES (:ticker, :name, :sector, :industry, :country, :website)
                    ON CONFLICT (ticker) DO NOTHING;
                """)
                conn.execute(insert_comp, {
                    "ticker": row['symbol'],
                    "name": row['name'],
                    "sector": row['sector'],
                    "industry": row['industry'],
                    "country": row['country'],
                    "website": row['website']
                })
            conn.commit()
        print("✅ Success: Companies data ingested.")

        prices_df['Date'] = pd.to_datetime(prices_df['Date'], utc=True, errors='coerce')
        prices_df = prices_df.dropna(subset=['Date'])  
        prices_df['Date'] = prices_df['Date'].dt.date

        with engine.connect() as conn:
            mapping = conn.execute(text("SELECT ticker, id FROM companies")).fetchall()
            ticker_to_id = {r[0]: r[1] for r in mapping}

            for _, row in prices_df.iterrows():
                ticker = row['Ticker']
                if ticker in ticker_to_id:
                    insert_price = text("""
                        INSERT INTO daily_stock_prices (company_id, price_date, open_price, high_price, low_price, close_price, volume)
                        VALUES (:c_id, :p_date, :open, :high, :low, :close, :vol)
                        ON CONFLICT (company_id, price_date) DO NOTHING;
                    """)
                    conn.execute(insert_price, {
                        "c_id": ticker_to_id[ticker],
                        "p_date": row['Date'],
                        "open": row['Open'],
                        "high": row['High'],
                        "low": row['Low'],
                        "close": row['Close'],
                        "vol": row['Volume']
                    })
            conn.commit()
        print("✅ Success: Stock prices data ingested.")

    except Exception as e:
        print(f"Ingestion Error: {e}")

if __name__ == "__main__":
    create_tables()
    ingest_from_local_csv()