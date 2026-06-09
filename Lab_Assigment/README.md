# Kiến trúc Hệ thống Multi-Agent (Lab Assignment)

Thư mục này chứa toàn bộ hệ thống Multi-Agent phân tán giao tiếp thông qua giao thức A2A (Agent-to-Agent). Hệ thống được thiết kế theo mô hình Microservices, trong đó mỗi Agent đóng một vai trò chuyên biệt và liên kết với nhau qua Service Registry.

## 🏗️ Cấu trúc các thành phần (Components)

Hệ thống bao gồm các thành phần cốt lõi sau:

### 1. 📇 Service Registry (`day08_registry`)
- **Vai trò**: Đóng vai trò là "Danh bạ" (Service Discovery) của hệ thống.
- **Hoạt động**: Khi khởi động, các agents sẽ gửi một request `/register` tới Registry để khai báo tên, địa chỉ endpoint và các task (nhiệm vụ) mà nó có thể giải quyết (ví dụ: `legal_consultation`, `legal_kb_query`). Khi một agent cần gọi agent khác, nó sẽ gọi `/discover/{task}` để xin địa chỉ IP/Endpoint của agent đảm nhận task đó.

### 2. 🖥️ Web UI (`day08_ui`)
- **Vai trò**: Giao diện người dùng (Front-end) xây dựng bằng FastAPI.
- **Hoạt động**: Tiếp nhận câu hỏi của người dùng. Hệ thống sẽ khởi tạo một `session_id` (để lưu phiên làm việc) và `trace_id` (để theo dõi log các bước). Sau đó, UI sẽ đóng gói câu hỏi này thành dạng A2A message và gửi cho **Customer Agent**.

### 3. 🤵 Customer Agent (`day08_customer_agent`)
- **Vai trò**: Tiếp tân (Front-door agent).
- **Hoạt động**: Nhận request trực tiếp từ UI/Client. Agent này sẽ truy vấn Registry để tìm người xử lý nghiệp vụ chính (`legal_consultation`), sau đó uỷ quyền (delegate) toàn bộ câu hỏi sang cho **Orchestrator Agent**.

### 4. 🧠 Orchestrator Agent (`day08_orchestrator_agent`)
- **Vai trò**: Trái tim của hệ thống điều phối, xây dựng bằng **LangGraph**.
- **Hoạt động theo đồ thị (Graph)**:
  1. **`load_memory`**: Tải lịch sử hội thoại dựa trên `context_id` (session của user).
  2. **`analyze_routing`**: Phân tích câu hỏi (bằng từ khóa) để xác định xem user đang hỏi về luật (Legal) hay tin tức (News), hoặc cả hai.
  3. **Delegation**: Dựa vào kết quả phân tích, nó hỏi Registry để tìm địa chỉ của các chuyên gia tương ứng (`call_legal_rag` và/hoặc `call_news_rag`). Sau đó gọi song song tới các RAG Agents này thông qua hàm `delegate`.
  4. **`aggregate`**: Chờ nhận kết quả từ các chuyên gia, sử dụng LLM để tổng hợp (synthesize) câu trả lời cuối cùng sao cho mượt mà, lưu vào memory và trả ngược lại cho Customer Agent.

### 5. 📚 Specialist RAG Agents (`day08_legal_rag_agent` & `day08_news_rag_agent`)
- **Vai trò**: Các chuyên gia trả lời câu hỏi dựa trên kho tri thức riêng (Knowledge Base).
- **Hoạt động**: Tiếp nhận câu hỏi từ Orchestrator. Agent sẽ chạy quy trình RAG (Retrieval-Augmented Generation) để tìm kiếm các văn bản pháp luật hoặc tin tức phù hợp, sau đó sinh ra câu trả lời chi tiết kèm theo các nguồn tham chiếu (sources/evidence). Kết quả được đóng gói trả về cho Orchestrator.

### 6. 🔍 Traceability (`common/trace_store.py`)
- **Vai trò**: Hệ thống ghi log tập trung.
- **Hoạt động**: Trong suốt chu trình từ UI -> Customer -> Orchestrator -> RAG Agents, mỗi khi một hành động được thực thi, hàm `append_trace` sẽ được gọi để lưu lại log. Nhờ cơ chế này, trên UI người dùng có thể nhìn thấy từng bước hệ thống đang chạy (Ví dụ: "Đang gọi Registry...", "Đang phân tích định tuyến...", "Chuyên gia Luật đang xử lý...").

---

## 🚀 Luồng hoạt động tổng thể (Workflow)

1. **User** nhập câu hỏi: *"Khung hình phạt cho tội buôn bán ma túy là gì?"* vào **UI**.
2. **UI** sinh ra `trace_id = 123` và chuyển cho **Customer Agent**.
3. **Customer Agent** hỏi Registry -> Tìm được **Orchestrator Agent** -> Delegate câu hỏi.
4. **Orchestrator Agent** phân tích câu hỏi -> Nhận diện từ khóa "hình phạt", "ma túy" -> Xác định nhánh cần đi là `needs_legal = True`.
5. **Orchestrator Agent** hỏi Registry -> Tìm được **Legal RAG Agent** -> Delegate câu hỏi.
6. **Legal RAG Agent** tìm trong database các bộ luật liên quan, tạo ra câu trả lời chi tiết và trả lại cho Orchestrator.
7. **Orchestrator Agent** nhận kết quả, gọi node `aggregate` để đúc kết lại nội dung và lưu lịch sử.
8. Kết quả cuối cùng được trả ngược theo đường cũ: `Orchestrator -> Customer Agent -> UI -> User`.

Toàn bộ quá trình giao tiếp này sử dụng `a2a_client.py` theo chuẩn **Agent-to-Agent Protocol**.

## 🛠 Cách vận hành (Khởi động)

Bạn có thể chạy toàn bộ các agents này đồng loạt bằng script có sẵn:
- Trên Windows (PowerShell): `.\start_all.ps1`
- Trền Linux/Mac: `./start_all.sh`

Script sẽ khởi động các process riêng biệt cho từng agent ở các port khác nhau (từ `11000` đến `11013`) và chạy cả phần UI để bạn tương tác. Để dừng hệ thống, hãy chạy `.\stop_all.ps1`.
