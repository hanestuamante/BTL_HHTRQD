# Phản hồi feedback đánh giá ngày 21/11/2026

Đối chiếu từng mục của file *Feedback_danh_gia_project_BTL_HHTRQD.docx* với thay đổi trong repo (23/11/2026).
Số liệu "trước" lấy từ commit `01b6b0c` (NV4 bản 1); số liệu "sau" lấy từ `outputs/task4/tables/task4_summary.json`
của lần chạy đầy đủ (notebook `notebooks/04_Modeling.ipynb`).

| Mã | Vấn đề | Đã làm | Bằng chứng / nghiệm thu |
|----|--------|--------|--------------------------|
| F01 | Ames điền thiếu trước khi chia tập | Ô điền học từ dữ liệu được trả về NaN theo `metadata/imputation_audit.csv`; `GroupMedianImputer` nằm trong Pipeline, fit trên train; điền cấu trúc cố định được giữ | `bds_valuation/ames.py`; `tests/test_splits_and_ames.py` (đổi test không đổi trung vị train; trung vị học = trung vị train); `outputs/task4/tables/ames_imputation_fix_comparison.csv` ghi MAPE cũ/mới |
| F02 | Tuning chưa độc lập với kiểm tra thời gian | Tương lai (từ 01/02/2015, tài sản chưa thấy) tách trước; tinh chỉnh + chọn mô hình chỉ trên quá khứ với validation 3 tháng cuối; khóa cấu hình rồi chấm tương lai một lần | `evaluation.temporal_split/run_temporal_backtest`; `temporal_backtest.json` (mốc, số mẫu, tham số, metrics); `test_temporal_split_future_isolated` |
| F03 | OOF chưa độc lập ở cấp siêu tham số | Thêm nested CV 5×3 (tinh chỉnh + chọn mô hình trong từng outer fold); OOF 4 seed giữ cho sàng lọc và ghi rõ giới hạn trong notebook/báo cáo; chọn mô hình bằng CV trên train, test chỉ chấm cuối | `nested_cv_oof`; `nested_cv_folds.csv`; `model_selection_cv_train.csv`; Bảng 5.9.1, 5.9.3 |
| F04 | Nhánh chọn model sai khi LR thắng | Một `MODEL_REGISTRY` dùng chung cho đánh giá, OOF, final fit; bundle kiểm tra tên ↔ kiểu estimator ↔ metrics | `bds_valuation/models.py`; `tests/test_models_registry.py` (3 trường hợp thắng, bundle lệch bị từ chối) |
| F05 | Residual âm chưa chứng minh định giá thấp | Đổi định nghĩa thống nhất: "ứng viên có giá giao dịch thấp hơn dự báo, cần xác minh"; bỏ "chênh lệch kỳ vọng", "cận trên"; cột `upside_usd` → `gap_to_prediction_usd`; Excel có sheet "Đọc trước"; dashboard có ghi chú | Notebook, báo cáo NV4, báo cáo tổng hợp, Excel `Top20_ung_vien_can_xac_minh.xlsx`, dashboard, slide; `test_top20_follows_rules` kiểm không còn `upside_usd` |
| F06 | What-if diện tích phá quan hệ dữ liệu | Hai kịch bản rõ ràng (trên mặt đất / tổng diện tích), tính lại `sqft_living`; mọi kịch bản kiểm `sqft_living = sqft_above + sqft_basement`; thêm cột tỷ lệ ngoài miền huấn luyện | `bds_valuation/whatif.py`; `tests/test_whatif_and_selection.py` (nhà có và không có hầm, lỗi cũ bị bắt) |
| F07 | Khuyến nghị cải tạo vượt bằng chứng | Bỏ khuyến nghị "cải tạo là đòn bẩy +8–10%"; what-if mô tả là phản ứng của mô hình, chỉ dùng đặt giả thuyết khảo sát | Báo cáo 5.9.4, 5.10.4; slide 9 |
| F08 | Quy tắc top 20 chưa hiệu chỉnh | Công bố quy tắc R1–R7 kèm lý do và mục tiêu; lưu tần suất xuất hiện từng tài sản qua 8 biến thể; không gọi là danh sách tối ưu | `selection_rules.csv`, `top20_membership_frequency.csv`, Bảng 5.10.1, 5.10.4 |
| F09 | Chưa có test tự động | Bộ `pytest` (thư mục `tests/`), gồm hồi quy cho F01, F02, F04, F06, top 20, đường dẫn, API dự báo, tính nhất quán artifact | `python -m pytest` |
| F10 | Dependency phân tán | Một `requirements.txt` cho toàn project; `requirements_task4.txt` chỉ trỏ về file này; đã cài trong venv sạch và chạy lại NV2–3 cho kết quả trùng byte | `requirements.txt` (ghi phiên bản dùng lưu `model.pkl`) |
| F11 | Đường dẫn phụ thuộc thư mục chạy | Script dùng `__file__`, notebook dùng cwd, đi ngược lên tìm thư mục gốc; hoặc `BDS_PROJECT_ROOT`; lỗi rõ khi không tìm thấy | `bds_valuation/paths.py`; `tests/test_paths.py`; đã chạy script từ `/tmp` và notebook với cwd `notebooks/` |
| F12 | Chưa đóng gói luồng dự báo | Package `bds_valuation` (import không huấn luyện); `predict_prices` tạo biến + kiểm schema; CLI `python -m bds_valuation.predict` | `tests/test_features_and_predict.py`, `test_import_does_not_train_and_cli_runs_from_outside` |
| F13 | README chưa bao quát | `README.md` mới: mục tiêu, trạng thái 6 nhiệm vụ, cấu trúc, cài đặt, thứ tự chạy, sản phẩm, giới hạn; `README.txt` bỏ | `README.md` |
| NV5–6 | Phạm vi | NV5 Power BI đã có từ 14–19/11 (PR #2 merge vào nhánh `nhiem-vu-4`, chưa vào `main` nên người đánh giá không thấy) — nay gộp vào main, sinh lại dữ liệu + `.pbip` theo NV4 mới, đổi nhãn theo F05 (bỏ "ROI", "chênh lệch kỳ vọng", "undervalued"), danh sách ngân sách dùng cùng quy tắc R1–R7, sửa measure MAPE OOF (trước tính trung bình \|residual_pct\|). Thêm bản web HTML. NV6: báo cáo 7 phần, slide, kịch bản video. Nhóm tự làm: Refresh/lưu `.pbix` + xuất PDF/ảnh, quay video, thư mục Drive | `README.md`, `dashboard/README.md`, `docs/huong_dan_nhiem_vu_5.txt` |
| Notebook | Build không execute ghi đè output | `build_task4_notebook.py` mặc định execute bằng nbclient và dừng nếu có error output | `notebooks/04_Modeling.ipynb` |

## Kết quả trước / sau

| Chỉ số | Trước (bản 1, 10/11) | Sau (bản 2, 23/11) | Ghi chú |
|--------|----------------------|--------------------|---------|
| Mô hình chọn | XGBoost, chọn theo MAPE **trên test** | XGBoost, chọn theo **CV trên train** (LR 13,12% · RF 12,34% · XGB 11,27%) | Cùng kết quả, nay quy trình đúng |
| MAPE test King County (XGBoost) | 11,20% | 11,25% | Cùng tham số tinh chỉnh; chênh lệch nhỏ do thứ tự fit |
| Backtest thời gian | 12,46% (tham số chọn trên dữ liệu có cả tương lai) | 12,43% (tinh chỉnh + chọn chỉ trên quá khứ; 15.610 GD quá khứ, 5.880 GD tương lai) | Kết quả độc lập |
| Nested CV 5×3 | — | 11,08% (cả 5 fold đều chọn XGBoost) | Ước lượng nghiêm ngặt mới |
| OOF sàng lọc (TB 4 seed) | 10,94% | 10,94% | Giữ, ghi rõ giới hạn F03 |
| Ames XGBoost / LR / RF | 7,49% / 7,96% / 8,22% (điền trước khi chia) | 7,54% / 7,96% / 8,16% (điền trong Pipeline) | Thay đổi ≤ 0,08 điểm % |
| Ứng viên đạt R4–R6 | 795 | 795 | |
| Tổng giá lịch sử / dự báo 20 căn | 4.534.822 / 8.521.716 USD | 4.669.822 / 8.786.216 USD | Không phải lợi nhuận |
| Độ ổn định top 20 qua 4 seed | 15–18/20 | 16–18/20; 4 căn có mặt ở cả 8 biến thể; nested CV giữ 18/20 | Thêm bảng tần suất |
| What-if diện tích +10% | +3,6% (tăng sqft_living và sqft_above, giữ basement → sai quan hệ ở 8.486 GD có hầm) | Trên mặt đất +10%: +3,3%; tổng diện tích +10%: +3,6% | Giữ `sqft_living = above + basement` |
| Test tự động | 0 | 37 test qua | `python -m pytest` |

Giới hạn còn lại (không bắt buộc theo feedback): chưa có khoảng dự báo; quy tắc chọn chưa hiệu chỉnh bằng kết quả
thẩm định thực tế; file `.pbix` và video phải do nhóm thực hiện.
