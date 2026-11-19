# Dashboard định giá bất động sản — Nhiệm vụ 5

Dashboard Power BI cho bài toán định giá bất động sản tự động (Chủ đề 14). Toàn bộ số liệu lấy từ
dự báo out-of-fold của mô hình Nhiệm vụ 4 (mỗi giao dịch được định giá bởi mô hình chưa từng thấy
căn đó), gồm 6 trang và 2 tham số What-if.

## Nội dung thư mục

| Tệp / thư mục | Mô tả |
|---|---|
| `BTL_NhiemVu5.pbip` | Project nguồn, mở trực tiếp bằng Power BI Desktop (≥ 2.159) |
| `BTL_NhiemVu5.pbix` | Bản đóng gói đã lưu, dữ liệu nhúng sẵn — dùng để gửi/nộp |
| `BTL_NhiemVu5.pdf` | Bản PDF 6 trang của dashboard (cho người không cài Power BI) |
| `BTL_NhiemVu5.SemanticModel/` | Model dạng TMDL: 15 bảng, các measure DAX, parameter `DataFolder` |
| `BTL_NhiemVu5.Report/` | Báo cáo dạng PBIR: 6 trang, visual, bookmark, theme `ThemeNhiemVu5.json` |
| `data/` | CSV nguồn cho model (sinh từ `scripts/prepare_dashboard_data.py`) |

## Mở dashboard

1. Mở `BTL_NhiemVu5.pbip` bằng Power BI Desktop bản 2.159 trở lên.
2. Model đã có cache dữ liệu; nếu trang trống thì vào **Home → Refresh** một lần.
3. Muốn có bản một tệp: **File → Save as** → chọn `.pbix`.

## 6 trang

| Trang | Nội dung chính |
|---|---|
| 1. Tổng quan King County | 21.612 giao dịch, giá trung vị 450.000 USD, MAPE out-of-fold 10,7%, 1.193 ứng viên tại ngưỡng 20%; phân bố theo khúc giá, theo ZIP và bảng ZIP – tỷ lệ ứng viên |
| 2. What-if ngưỡng undervalued | Hộp chọn ngưỡng 5%–50% (mặc định 20%); card số ứng viên, tỷ lệ, tổng chênh lệch, giá trung vị nhóm; biểu đồ theo ZIP/khúc giá; bảng tổng hợp theo ZIP |
| 3. Ngân sách và kế hoạch mua | Hộp chọn ngân sách 0,5–10 triệu USD (mặc định 2.000.000); số căn mua được, vốn, chênh lệch, % ngân sách đã dùng, ROI; biểu đồ theo ZIP đổi chỉ số bằng hộp chọn; 2 hộp giải thích cách tính |
| 4. 20 căn đề xuất | Vốn 4.534.822 USD, chênh lệch kỳ vọng 3.986.894 USD, mức giảm trung vị 46,1%, cả 3 mô hình đồng ý 20/20; bảng chi tiết và chênh lệch theo ZIP |
| 5. Kiểm chứng bằng Ames | MAPE King vs Ames theo mô hình, giá trung vị theo khu dân cư, số tài sản theo khúc giá, MAPE theo khúc giá King |
| 6. Mô hình và độ nhạy | 12 biến quan trọng nhất (permutation importance), what-if từng biến, số ứng viên theo ngưỡng, độ ổn định của danh sách 20 căn |

Dải 6 nút điều hướng có ở cuối **mọi trang** (trang đang mở được tô đậm). Trong Power BI Desktop
ở chế độ chỉnh sửa phải **Ctrl+click** nút, hoặc chuyển **View → Reading view**.

## Hai tham số What-if

Cả hai dùng cùng một cơ chế: một bảng tính chỉ chứa dải giá trị (không sửa dữ liệu gốc), một hộp
chọn để chọn đúng **một** giá trị, các measure DAX đọc giá trị đang chọn rồi tính lại số liệu.

| Tham số | Bảng | Dải giá trị | Mặc định | Measure đọc giá trị |
|---|---|---|---|---|
| Ngưỡng undervalued | `Nguong` | 5%–50%, bước 1% | 20% | `Ngưỡng (%)` → chia 100 |
| Ngân sách mua | `NganSach` | 500.000–10.000.000 USD, bước 250.000 | 2.000.000 USD | `Selected Budget` |

Quy tắc tính:

- Ứng viên: `residual_pct = giá bán / giá mô hình − 1 ≤ −ngưỡng`, trên phạm vi Nhiệm vụ 4
  (`is_latest_sale = 1`, `zero_room_flag = 0`, `condition ≥ 3` → 21.229 giao dịch).
- Ngân sách là **tổng vốn**, không phải giá một căn: ứng viên ở ngưỡng 20% được xếp theo mức giảm
  sâu nhất, mua lần lượt đến khi hết ngân sách, chỉ xét giao dịch giảm ≤ 50%.
- Mốc đối chiếu: ngưỡng 20% → **1.193 căn (5,62%)**, 839 căn cả 3 mô hình đồng ý, giá trung vị
  285.000 USD. Ngân sách 2.000.000 USD → **8 căn**, vốn 1.809.500 USD, chênh lệch 1.758.645 USD,
  dùng 90,5% ngân sách, ROI 97,2%.

## Mô hình dữ liệu

- 15 bảng import từ CSV trong `data/`, đường dẫn lấy từ parameter `DataFolder`.
- Bảng chính: `KingSales` (21.612 dòng), `AmesSales` (2.930), `Top20` (20), `BudgetPlan` (1.157
  ứng viên xếp theo mức giảm), `ModelMetrics`, `ModelCompare`, `Sensitivity`, `Stability`,
  `ImportanceTop`, `WhatIfScenarios`, `ChonChiSo`.
- Bảng tính: `Nguong`, `NganSach` (2 tham số What-if), `KPI` (chứa toàn bộ measure).
- Measure tiêu biểu: `Số ứng viên`, `Tỷ lệ ứng viên`, `Chênh lệch ứng viên (USD)`,
  `Giá trung vị ứng viên`, `Đồng thuận 3 mô hình`, `Budget Bought`, `Budget Capital`,
  `Budget Upside`, `Budget Used`, `Budget ROI`.

## Tính năng tương tác

- **Page navigator**: 6 nút ở mọi trang (PBIR tự sinh từ danh sách trang).
- **Bookmark**: "Chế độ nhà đầu tư" mở trang 3, "Chế độ học thuật" mở trang 6 (menu View → Bookmarks).
- **Hộp chọn chỉ số** ở trang 3: đổi biểu đồ theo ZIP giữa số ứng viên / tỷ lệ / giá trung vị.
- Tooltip trên từng điểm dữ liệu; mọi visual có alt text và thứ tự tab đọc được.

## Tái lập

```bash
python scripts/prepare_dashboard_data.py   # sinh dashboard/data + dự báo OOF Ames
python scripts/build_task5_pbip.py         # sinh lại project PBIP
python scripts/validate_pbip.py            # kiểm JSON schema + tham chiếu field
```

Sau khi sửa model/CSV phải mở lại Power BI Desktop (đóng hẳn rồi mở lại) để nạp lại dữ liệu.

## Ghi chú

- `DataFolder` là đường dẫn tuyệt đối; chuyển máy thì sửa ở **Transform data → Manage parameters**
  rồi Refresh (bản `.pbix` không cần vì dữ liệu đã nhúng).
- "Định giá thấp" chỉ là proxy theo sai số mô hình (~11%), không chứng minh chủ nhà định giá sai;
  dữ liệu là giao dịch lịch sử 2014–2015 và 2006–2010, không phải giá hiện tại.
- 36 giao dịch giảm trên 50% bị tách sang danh sách cần xác minh thủ công, không vào top 20.
