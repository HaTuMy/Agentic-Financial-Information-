# Agentic Financial Information System using LangGraph 🚀

Hệ thống chatbot thông minh hỗ trợ truy vấn và phân tích thông tin tài chính thời gian thực, tập trung vào dữ liệu chứng khoán từ Yahoo Finance. Dự án ứng dụng kiến trúc Agentic Workflow để tối ưu hóa khả năng ra quyết định và xử lý dữ liệu phức tạp.

## 👥 Thành viên thực hiện (Nhóm - IUH)
| Họ và Tên | MSSV |
| :--- | :--- | :--- |
| **Lê Hà Tú My** | 22648801 | 
| **Phạm Văn Mạnh** | 22642071 |
| **Nguyễn Quang Mạnh** | 22645001 |

---

## 🎯 Mục tiêu dự án
* **Truy vấn Real-time:** Cung cấp thông tin chính xác về giá cổ phiếu, chỉ số tài chính và xu hướng thị trường từ Yahoo Finance.
* **Xử lý dữ liệu đa phương thức:** Khả năng xử lý linh hoạt cả dữ liệu có cấu trúc (bảng biểu, chỉ số) và không cấu trúc (tin tức, báo cáo).
* **Kiến trúc LangGraph:** Thiết kế luồng công việc (workflow) có khả năng ghi nhớ ngữ cảnh (memory), phân nhánh logic và tự động ra quyết định dựa trên ý định người dùng.
* **Tự động hóa:** Tối ưu quy trình phân tích tài chính phức tạp và trả lời các câu hỏi chuyên sâu thay vì chỉ tra cứu thông tin đơn thuần.

---

## 🛠 Công nghệ sử dụng
* **Ngôn ngữ:** Python 3.10+
* **Framework:** LangGraph, LangChain
* **LLM:** (Ví dụ: GPT-4o / Claude 3.5 Sonnet / Gemini 1.5 Pro)
* **Data Source:** Yahoo Finance API (yfinance)
* **Database/Tools:** SQLite (cho Memory), DuckDuckGo Search (cho Tin tức)

---

## 📂 Cấu trúc thư mục chính
* `dp_project/`: Chứa mã nguồn logic chính của LangGraph Agent.
* `download_djia_companies.py`: Thu thập danh sách các mã cổ phiếu trong nhóm DJIA.
* `download_djia_stock_prices.py`: Thu thập dữ liệu lịch sử giá cổ phiếu.
* `nodes/`: Định nghĩa các hàm xử lý trong đồ thị (Graph nodes).
* `state.py`: Quản lý trạng thái dữ liệu trong luồng LangGraph.

---

## 🚀 Hướng dẫn chạy dự án

Bạn cần thực hiện theo đúng thứ tự các bước sau để đảm bảo hệ thống hoạt động chính xác:

### Bước 1: Cài đặt môi trường
Mở terminal tại thư mục gốc và cài đặt các thư viện cần thiết:
```bash
pip install -r dp_project/requirements.txt
```

### Bước 2: Thiết lập API Key
Tạo file `.env` bên trong thư mục `dp_project/` (nếu chưa có) và điền các khóa API:
```env
OPENAI_API_KEY=your_openai_api_key_here
# Hoặc các API key khác nếu bạn dùng Gemini/Claude
```

### Bước 3: Thu thập dữ liệu (Quan trọng)
Trước khi khởi động Chatbot, bạn cần chạy 2 script này để tạo/cập nhật dữ liệu chứng khoán:
1. **Lấy danh sách công ty:**
   ```bash
   python download_djia_companies.py
   ```
2. **Lấy giá cổ phiếu:**
   ```bash
   python download_djia_stock_prices.py
   ```

### Bước 4: Khởi chạy Chatbot
Sau khi đã có dữ liệu CSV ở thư mục gốc, tiến hành chạy ứng dụng chính:
```bash
cd dp_project
python financial_chatbot_app.py
```
---

## 🛠 Kiến trúc hệ thống (LangGraph Workflow)
Hệ thống được thiết kế theo dạng đồ thị (Graph) giúp chatbot có khả năng phân nhánh xử lý:
1. **Node Agent:** Phân tích câu hỏi của người dùng.
2. **Node Query Generator:** Tạo câu lệnh truy vấn vào file CSV nếu hỏi về dữ liệu lịch sử.
3. **Node LLM Handler:** Xử lý ngôn ngữ tự nhiên và gọi các công cụ (tools) hỗ trợ.
4. **Node Synthesizer:** Tổng hợp dữ liệu từ các nguồn để trả lời người dùng.

---

## 📝 Ghi chú
- Đảm bảo các file `.csv` và script `download_*.py` nằm đúng vị trí thư mục gốc như cấu trúc trên GitHub.
- Dự án là một phần của môn học **Data Platform (HK8)** - Trường Đại học Công nghiệp TP.HCM.
```

---
