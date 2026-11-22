# BTL HHTRQD — Chủ đề 14: Mô hình định giá bất động sản tự động

Học phần Hệ hỗ trợ ra quyết định. Câu hỏi quyết định: *với ràng buộc xét 20 căn, Giám đốc đầu tư nên đưa
20 căn nào vào danh sách thẩm định ưu tiên, và danh sách đó đáng tin đến mức nào?*

Dữ liệu: giao dịch nhà ở King County, WA (05/2014–05/2015) là thị trường chính; Ames, Iowa (2006–2010) để kiểm chứng.
Mọi số liệu trong báo cáo, slide và dashboard được sinh từ mã nguồn trong repo; AI chỉ hỗ trợ viết mã và diễn đạt
(xem `docs/nv1/nhat_ky_dung_ai.md`).

## Đọc nhanh

| Muốn xem | Mở |
|----------|----|
| Báo cáo tổng hợp 7 phần | `reports/Bao_cao_tong_hop_Chu_de_14.docx` (và `.pdf`) |
| Dashboard Power BI (NV5) | `dashboard/BTL_NhiemVu5.pbip` / `.pbix` / `.pdf` — xem `dashboard/README.md` |
| Dashboard bản web (không cần Power BI) | `dashboard/Dashboard_Chu_de_14.html` |
| Slide thuyết trình + kịch bản video | `slides/Chu_de_14_thuyet_trinh.pptx`, `docs/nv6/kich_ban_video.md` |
| 20 ứng viên cần xác minh, báo cáo MAPE | `outputs/task4/Top20_ung_vien_can_xac_minh.xlsx` |
| Notebook đã chạy | `notebooks/02_03_ETL_EDA.ipynb`, `notebooks/04_Modeling.ipynb` |

## Trạng thái theo bảng phân công

| TV | Nhiệm vụ | Sản phẩm | Trạng thái |
|----|----------|----------|-----------|
| 1 | Câu hỏi, KPI, ràng buộc (Phần 1–3) | `docs/nv1/bang_cau_hoi_S.csv` (6 cột), `docs/nv1/nhat_ky_dung_ai.md`, Phần 1–3 trong báo cáo tổng hợp | Có trong repo |
| 2 | Dữ liệu, ETL 4 bước, từ điển (Phần 4) | `data/processed/`, `dictionaries/data_dictionary.csv`, `docs/nhat_ky_etl_4_buoc.txt`, `reports/Bao_cao_Nhiem_vu_2_3.*` | Có trong repo |
| 3 | EDA và chẩn đoán (Phần 5 cấp 1–2) | `notebooks/02_03_ETL_EDA.ipynb`, `outputs/figures/`, `outputs/tables/` | Có trong repo |
| 4 | Mô hình, MAPE, 20 ứng viên, độ nhạy (Phần 5 cấp 3–4) | `models/model.pkl`, `notebooks/04_Modeling.ipynb`, `outputs/task4/`, `reports/Bao_cao_Nhiem_vu_4.docx` | Có trong repo, đã sửa theo feedback 21/11 |
| 5 | Dashboard có tham số What-if (Phần 6) | Power BI 6 trang, 2 What-if (`dashboard/BTL_NhiemVu5.*`, `scripts/prepare_dashboard_data.py`, `scripts/build_task5_pbip.py`), `reports/Bao_cao_Nhiem_vu_5.docx`; bản web `dashboard/Dashboard_Chu_de_14.html` | Có trong repo (TV5, PR #2 vào nhánh `nhiem-vu-4`, nay gộp vào main). Dữ liệu + `.pbip` đã sinh lại theo NV4 mới; **`.pbix`, PDF và ảnh 6 trang cần Refresh/xuất lại trong Power BI Desktop** (`docs/huong_dan_nhiem_vu_5.txt`) |
| 6 | Phần 7, tổng hợp báo cáo, slide, video | `reports/Bao_cao_tong_hop_Chu_de_14.*`, `slides/`, `docs/nv6/` | Báo cáo + slide + kịch bản có trong repo. **Video mp4 (mọi thành viên xuất hiện) do nhóm quay**; thư mục Drive `261HHTQD_NhomXX` do nhóm tổng hợp |

## Cấu trúc

```
bds_valuation/        package dùng chung: tạo biến + kiểm tra schema, registry mô hình, đánh giá
                      (chia theo tài sản, backtest thời gian, nested CV), Ames imputer, what-if, quy tắc chọn, API dự báo
scripts/              prepare_data.py (NV2) · analyze.py, build_notebook.py, build_report.py (NV3)
                      task4_modeling.py, build_task4_notebook.py, build_task4_report.py (NV4)
                      prepare_dashboard_data.py, build_task5_pbip.py, validate_pbip.py, build_task5_report.py (NV5 Power BI)
                      build_dashboard.py (NV5 bản web) · build_full_report.py, build_slides.py, build_manifest.py (NV6)
tests/                pytest: chia tập, imputer Ames, registry mô hình, what-if, quy tắc chọn, đường dẫn, API dự báo
data/raw, data/processed, dictionaries/, metadata/   dữ liệu gốc, dữ liệu sạch, từ điển, nguồn + checksum + audit
outputs/              bảng và hình NV3 (outputs/tables, figures) và NV4 (outputs/task4)
models/model.pkl      mô hình King County đã chọn bằng CV, fit lại trên toàn bộ dữ liệu
notebooks/ reports/ dashboard/ slides/ docs/
```

## Cài đặt (một môi trường cho toàn project)

Python 3.12. Từ thư mục gốc repo:

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

`requirements_task4.txt` chỉ còn trỏ về `requirements.txt`. Phải dùng đúng phiên bản scikit-learn 1.9.1 và
xgboost 3.2.0 để đọc `models/model.pkl`. Trên Windows nên đặt `PYTHONUTF8=1`.

## Tái lập theo thứ tự

```bash
python scripts/prepare_data.py            # NV2: ETL (dùng raw đã lưu, kiểm SHA256)
python scripts/analyze.py                 # NV3: EDA, kiểm định, biểu đồ
python scripts/build_notebook.py          # NV3: notebook 02_03 đã thực thi
python scripts/build_report.py            # NV3: báo cáo Word NV2–3
python scripts/build_task4_notebook.py    # NV4: chạy toàn bộ mô hình trong notebook 04 (~30 phút), ghi outputs/task4 + model.pkl
python scripts/build_task4_report.py      # NV4: báo cáo Word + Excel ứng viên
python scripts/prepare_dashboard_data.py  # NV5: dữ liệu Power BI (dashboard/data)
python scripts/build_task5_pbip.py        # NV5: project Power BI .pbip (rồi Refresh + lưu .pbix trong Power BI Desktop)
python scripts/build_task5_report.py      # NV5: Phần 6 (Word + docs/phan_6_ket_qua.txt)
python scripts/build_dashboard.py --screens   # NV5: bản web HTML + ảnh chụp (cần Chrome)
python scripts/build_full_report.py --pdf     # NV6: báo cáo 7 phần (PDF cần Word trên macOS hoặc LibreOffice)
python scripts/build_slides.py            # NV6: slide
python -m pytest                          # kiểm thử
```

`python scripts/task4_modeling.py` chạy cùng nội dung với notebook 04 dưới dạng script. Đặt `BDS_FAST=1` để chạy nhanh
kiểm tra luồng (ít vòng tinh chỉnh, khoảng 10 phút) — **không dùng kết quả chế độ nhanh để nộp**.
Các script tìm thư mục gốc project tự động; khi chạy từ một thư mục bất kỳ có thể đặt `BDS_PROJECT_ROOT=<đường dẫn repo>`.

## Dự báo căn mới bằng model.pkl

```python
import pandas as pd
from bds_valuation.predict import load_bundle, predict_prices

df = pd.read_csv("data/raw/kc_house_data.csv", dtype={"id": "string", "zipcode": "string"}).head(10)
out = predict_prices(df, load_bundle())     # tạo biến + kiểm tra schema giống lúc huấn luyện
```

hoặc `python -m bds_valuation.predict input.csv output.csv`. Thiếu trường, sai kiểu hoặc sai miền (ví dụ
`sqft_living ≠ sqft_above + sqft_basement`) sẽ báo lỗi rõ. Dự báo ngoài 05/2014–05/2015 được đánh dấu là ngoài
khoảng huấn luyện.

## Cách đánh giá mô hình (tóm tắt)

- Chia 80/20 **theo id tài sản**; tập test chỉ chấm một lần, không tham gia chọn gì.
- Tinh chỉnh XGBoost và **chọn mô hình bằng CV trên train**; LR, RF, XGBoost lấy từ một registry dùng chung cho
  đánh giá, OOF và mô hình lưu.
- **Backtest thời gian độc lập**: tách giao dịch từ 01/02/2015 trước, tinh chỉnh và chọn mô hình chỉ trên quá khứ.
- **Nested CV 5×3**: ước lượng nghiêm ngặt của cả quy trình tinh chỉnh + chọn mô hình.
- Ames: điền thiếu học từ dữ liệu được làm trong Pipeline, fit trên train.

Kết quả cụ thể: `outputs/task4/tables/task4_summary.json`, `model_metrics_mape_report.csv`.

## Giới hạn cần giữ khi trình bày

1. Ứng viên = giá giao dịch lịch sử **thấp hơn giá dự báo, cần xác minh** — chưa chứng minh bị định giá thấp; chênh
   lệch so với giá dự báo **không phải lợi nhuận**.
2. What-if là phản ứng của mô hình khi thay đầu vào, **không phải tác động nhân quả** của cải tạo.
3. Ngưỡng −20%, trần −50% và các lọc là quy tắc của nhóm, chưa hiệu chỉnh bằng kết quả thẩm định thực tế.
4. Nhóm "giá < 80% trung vị" ở NV3 là nhóm giá thấp, khác với ứng viên dựa trên residual ở NV4.
5. Dữ liệu 2014–2015 (King) và 2006–2010 (Ames), USD, hai thị trường không gộp.

## Lịch sử thay đổi

- 02/11/2026 — NV2, NV3.
- 10/11/2026 — NV4 bản 1.
- 14–19/11/2026 — NV5 Power BI (TV5).
- 23/11/2026 — Sửa NV4 theo feedback 21/11 (F01–F13), thêm package `bds_valuation`, test, môi trường chung;
  gộp NV5 Power BI của TV5 (nhánh `nhiem-vu-4`) và cập nhật theo NV4 mới; thêm NV1, bản web dashboard, NV6 (báo cáo
  7 phần, slide, kịch bản video). Chi tiết đối chiếu từng
  mục feedback: `docs/phan_hoi_feedback_21_11.md`.
