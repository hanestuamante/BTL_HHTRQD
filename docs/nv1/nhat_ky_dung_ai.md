# Nhật ký sử dụng AI — Chủ đề 14

Mục đích: minh bạch việc dùng AI theo yêu cầu đề bài. Nguyên tắc nhóm áp dụng: **không dùng AI để tạo "Fact"**.
Mọi con số trong báo cáo, slide, dashboard được sinh ra từ mã nguồn chạy trên dữ liệu gốc
(`data/raw`) và đọc lại từ file kết quả (`outputs/**`, `metadata/**`); AI chỉ hỗ trợ viết mã, cấu trúc nội dung
và diễn đạt. Người phụ trách từng phần chịu trách nhiệm duyệt lại.

## 1. Bước S — prompt dùng để xây dựng câu hỏi (Nhiệm vụ 1)

| # | Ngày | Công cụ | Prompt (nguyên văn hoặc rút gọn) | AI trả lại | Nhóm dùng thế nào / kiểm tra |
|---|------|---------|----------------------------------|-----------|------------------------------|
| S1 | 23/11/2026 | Claude (Claude Code, mô hình Opus) | "Dò bảng BTL HTRQD — đó là yêu cầu chung, xem repo này hoàn thành tới mức nào — hoàn thành nốt những phần còn lại, đồng thời tôi cũng được 1 file feedback, thống nhất tất cả để hoàn thiện rồi merge main" (kèm bảng phân công PDF và file feedback) | Đối chiếu repo với 6 nhiệm vụ; xác định Nhiệm vụ 1, 5, 6 còn thiếu | Dùng làm danh sách việc; nhóm xác nhận phạm vi |
| S2 | 23/11/2026 | Claude | Yêu cầu nội bộ khi soạn Nhiệm vụ 1: "Từ vai trò Giám đốc đầu tư phải chọn 20 căn, viết chuỗi 4 lớp câu hỏi đi từ vấn đề kinh doanh tới câu hỏi quyết định, mỗi lớp gắn cấp phân tích, dữ liệu, phương pháp và nơi trả lời trong báo cáo; KPI gồm MAPE và tỷ lệ ứng viên; ràng buộc 20 căn" | Bản nháp `bang_cau_hoi_S.csv` (6 cột) và Phần 1–3 | Câu hỏi không chứa số liệu; KPI là **ngưỡng do nhóm đặt**, kết quả đo nằm ở Phần 6 và lấy từ file kết quả |
| S3 | 23/11/2026 | Claude | "Đặt KPI kiểm chứng được và không mượn số từ bên ngoài dữ liệu" | Đề xuất KPI1 (MAPE), KPI2 (tỷ lệ ứng viên), KPI3 (độ ổn định top 20) | Ngưỡng mục tiêu là giả định quản trị, được ghi rõ là giả định |
| — | (nhóm bổ sung) | | Các prompt nhóm đã dùng trước ngày 23/11 cho bước S, nếu có | | Thành viên 1 điền |

## 2. Các bước khác

| Bước | Ngày | Công cụ | Việc AI làm | Kiểm tra của con người / bằng chứng |
|------|------|---------|-------------|-------------------------------------|
| O (Nhiệm vụ 2) | 02/11/2026 | Trợ lý AI lập trình | Hỗ trợ viết `scripts/prepare_data.py`, từ điển dữ liệu | Checksum nguồn trong `metadata/sources.json`; `docs/kiem_tra_doc_lap.txt` |
| A cấp 1–2 (Nhiệm vụ 3) | 02/11/2026 | Trợ lý AI lập trình | Hỗ trợ viết `scripts/analyze.py`, biểu đồ, báo cáo NV2–3 | Kiểm định tính lại độc lập (`docs/kiem_tra_doc_lap.txt`) |
| A cấp 3–4 (Nhiệm vụ 4) | 10/11/2026 | Trợ lý AI lập trình | Hỗ trợ viết `scripts/task4_modeling.py` | Notebook đã chạy; feedback độc lập 21/11/2026 |
| Sửa theo feedback F01–F13 | 23/11/2026 | Claude (Claude Code) | Tách package `bds_valuation`, sửa leakage Ames, backtest thời gian, nested CV, registry mô hình, what-if, diễn giải, test tự động, README | `pytest` (thư mục `tests/`), chạy lại toàn bộ NV4, số liệu mới đọc từ `outputs/task4/tables/*` |
| Nhiệm vụ 5 | 23/11/2026 | Claude | Chuẩn bị dữ liệu dashboard, bản HTML tương tác có thanh trượt What-if, hướng dẫn và công thức DAX cho Power BI | Số trên dashboard đối chiếu với `sensitivity_threshold.csv` (có test đối chiếu) |
| Nhiệm vụ 6 | 23/11/2026 | Claude | Soạn Phần 6, Phần 7, ghép báo cáo 7 phần, tạo slide, kịch bản video | Nhóm duyệt nội dung, quay video thật (AI không quay video thay nhóm) |

## 3. Giới hạn đã ghi nhận
- AI có thể diễn đạt quá mức chắc chắn. Feedback 21/11 đã chỉ ra (F05, F07, F08); các câu "bị định giá thấp",
  "chênh lệch kỳ vọng", "cận trên", "cải tạo là đòn bẩy" đã được sửa thành mô tả đúng mức bằng chứng.
- Liên kết "Prompt" và "Chủ đề" trên Drive của đề bài không được đọc trong phiên 23/11; nội dung bám theo bảng
  phân công (PDF) và file feedback. Nếu mẫu bảng S của giảng viên có tên cột khác, giữ nội dung và đổi tên cột.
