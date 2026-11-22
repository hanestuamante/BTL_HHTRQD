# Dựng Dashboard Power BI (Nhiệm vụ 5)

Bản tương tác chạy ngay: `dashboard/Dashboard_Chu_de_14.html` (mở bằng trình duyệt). Đề bài yêu cầu file
Power BI/Tableau. File `.pbix` chỉ dựng được trong Power BI Desktop (Windows). Thư mục này có sẵn dữ liệu,
bảng tham số và công thức DAX, nên dựng mất khoảng 30–45 phút. Lưu file thành `dashboard/Dashboard_Chu_de_14.pbix`.

Mọi file trong thư mục được sinh lại bằng `python scripts/build_dashboard.py` sau khi chạy mô hình.

## 1. Dữ liệu

| File | Nội dung | Dòng |
|------|----------|------|
| `fact_ung_vien_king.csv` | Pool ứng viên: giao dịch gần nhất của mỗi tài sản sau R1–R3; giá giao dịch, giá dự báo OOF, residual của 3 mô hình, đặc điểm, lat/long | ~21 nghìn |
| `param_nguong.csv` | Giá trị 5..50 cho tham số What-if (nếu không dùng New parameter) | 46 |
| `sensitivity_threshold.csv` | Bảng đối chiếu: số căn theo ngưỡng (dùng để kiểm tra measure) | 10 |
| `model_metrics.csv` | MAPE/RMSE/R² theo mô hình và cách đánh giá | ~14 |
| `top20_candidates.csv` | 20 ứng viên chính thức ở ngưỡng 20% | 20 |
| `DAX_measures.dax` | Các measure cần tạo | |

Get Data → Text/CSV → chọn từng file. Ở Power Query, đặt kiểu `id`, `zipcode` = **Text** (giữ số 0 đầu),
`date` = Date, các cột residual = Decimal.

## 2. Tham số What-if (bắt buộc theo đề)

Modeling → New parameter → Numeric range:
- Name: `Nguong_pct`, Minimum 5, Maximum 50, Increment 1, Default 20, tick **Add slicer to this page**.
- Power BI tạo bảng `Nguong_pct` và measure `[Nguong_pct Value]`. Trong `DAX_measures.dax`, thay
  `[Nguong Value]` bằng `[Nguong_pct Value]` (hoặc tạo measure `Nguong Value = [Nguong_pct Value]`).

## 3. Measure

Mở `DAX_measures.dax`, tạo lần lượt: `So can ung vien`, `Ty le ung vien %`, `So can dat R4-R6`,
`Gia trung vi ung vien`, `La ung vien (theo nguong)`, `La ung vien R4-R6`, `Hang than trong`, `Tong gia lich su top N`.

## 4. Bố cục gợi ý (1 trang, 16:9)

1. Hàng KPI (Card): MAPE test, MAPE backtest thời gian, MAPE nested CV (lọc `model_metrics`), `So can ung vien`,
   `Ty le ung vien %`, `Gia trung vi ung vien`.
2. Slicer `Nguong_pct` (dạng thanh trượt) + slicer `zipcode`.
3. Map/Scatter: Latitude = `lat`, Longitude = `long`; Legend hoặc màu theo `La ung vien R4-R6`.
4. Line chart từ `sensitivity_threshold.csv`: trục X `Nguong_%`, trục Y `So_can_ung_vien`; thêm đường hằng 20 (ràng buộc).
5. Table: id, zipcode, date, price, predicted_price, below_prediction_pct, below_prediction_conservative_pct, grade,
   house_age; filter visual `La ung vien R4-R6 = 1`, Top N 20 theo `residual_pct_conservative` tăng dần.
6. Text box ghi chú bắt buộc: *"Ứng viên = giá giao dịch lịch sử thấp hơn giá dự báo, cần xác minh; chênh lệch không phải
   lợi nhuận."*

## 5. Kiểm tra trước khi nộp

- Kéo thanh trượt về 20: `So can ung vien` phải bằng cột `So_can_ung_vien` dòng 20 của `sensitivity_threshold.csv`;
  `So can dat R4-R6` bằng `recommended_pool_size` trong `outputs/task4/tables/task4_summary.json`.
- Bảng Top 20 ở ngưỡng 20 phải trùng `top20_candidates.csv`.
- Chụp ảnh dashboard ở 2–3 ngưỡng đưa vào Phần 6 (đã có ảnh của bản HTML trong `dashboard/screenshots/`).

## Tableau (thay thế)

Tạo Parameter `Nguong_pct` (Integer, Range 5–50, step 1, current 20) → Show Parameter. Calculated field
`La ung vien = [residual_pct] <= -[Nguong_pct]/100`; `R4-R6 = [La ung vien] AND [residual_pct] >= -0.5 AND
[residual_pct_model2] <= -[Nguong_pct]/100 AND [residual_pct_model3] <= -[Nguong_pct]/100 AND [house_age] > 0`.
Lưu thành `dashboard/Dashboard_Chu_de_14.twbx`.
