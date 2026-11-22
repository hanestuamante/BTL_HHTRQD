"""Tạo báo cáo Nhiệm vụ 4 (Phần 5 — cấp 3, 4) dạng .docx và bảng ứng viên dạng .xlsx từ kết quả đã chạy.

Phiên bản 2: cập nhật theo feedback 21/11/2026 — chọn mô hình bằng CV (F04), backtest thời gian độc lập (F02),
nested CV (F03), Ames điền thiếu trong Pipeline (F01), what-if giữ quan hệ diện tích (F06) và diễn giải đúng mức
bằng chứng (F05, F07, F08). Mọi số đọc từ outputs/task4/tables/*.
"""
import json
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / "outputs" / "task4" / "tables"
F = ROOT / "outputs" / "task4" / "figures"
S = json.loads((T / "task4_summary.json").read_text(encoding="utf-8"))
TB = json.loads((T / "temporal_backtest.json").read_text(encoding="utf-8"))
met = pd.read_csv(T / "model_metrics_mape_report.csv")
seg = pd.read_csv(T / "mape_by_price_segment.csv")
thr = pd.read_csv(T / "sensitivity_threshold.csv")
stab = pd.read_csv(T / "sensitivity_top20_stability.csv")
freq = pd.read_csv(T / "top20_membership_frequency.csv", dtype={"id": str})
wif = pd.read_csv(T / "sensitivity_whatif.csv")
perm = pd.read_csv(T / "permutation_importance.csv")
cvt = pd.read_csv(T / "model_selection_cv_train.csv")
nested = pd.read_csv(T / "nested_cv_folds.csv")
ames_fix = pd.read_csv(T / "ames_imputation_fix_comparison.csv")
rules = pd.read_csv(T / "selection_rules.csv")
top = pd.read_csv(T / "top20_candidates_below_prediction_king.csv", dtype={"id": str, "zipcode": str})
raw = pd.read_csv(T / "top20_raw_largest_negative_residual_king.csv", dtype={"id": str})
chk = pd.read_csv(T / "candidates_need_verification_king.csv", dtype={"id": str})

K, KT, KN = "King County", "King County (backtest thời gian)", "King County (nested CV 5×3, OOF)"
XG, LR, RF = "XGBoost (tuned)", "Linear Regression (baseline)", "Random Forest"
NAIVE = "Mốc thô: đơn giá zipcode × diện tích"
BEST = S["best_model"]
LOCKED = TB["locked_model"]["model"]


def m(market, model, col="MAPE_%"):
    return float(met[(met["Thi_truong"] == market) & (met["Mo_hinh"] == model)][col].iloc[0])


fmt = lambda v: f"{v:,.0f}".replace(",", ".")
pct = lambda v: f"{v:.1f}".replace(".", ",") + "%"
pct2 = lambda v: f"{v:.2f}".replace(".", ",") + "%"
vdate = lambda s: "/".join(reversed(s.split("-")))

# ---------------- Excel ứng viên ----------------
VI = {"Hang": "Hạng", "id": "Mã tài sản (id)", "date": "Ngày giao dịch", "zipcode": "Zipcode",
      "price": "Giá giao dịch lịch sử (USD)", "predicted_price": "Giá dự báo (USD)",
      "gap_to_prediction_usd": "Chênh lệch so với giá dự báo (USD)",
      "below_prediction_pct": "Thấp hơn dự báo — mô hình chính (%)",
      "below_prediction_conservative_pct": "Thấp hơn dự báo — thận trọng, 3 mô hình (%)", "residual": "Residual (USD)",
      "models_agree_below_20pct": "Số mô hình cùng thấy thấp hơn ≥20% (/3)", "sqft_living": "Diện tích ở (sqft)",
      "bedrooms": "Phòng ngủ", "bathrooms": "Phòng tắm", "grade": "Grade", "condition": "Condition", "view": "View",
      "waterfront": "Mặt nước", "house_age": "Tuổi nhà", "distance_to_center_km": "Cách trung tâm (km)",
      "lat": "Vĩ độ", "long": "Kinh độ", "cumulative_price_usd": "Tổng giá lịch sử lũy kế (USD)"}
note = pd.DataFrame({"Ghi chú": [
    "Ứng viên = giao dịch lịch sử 2014–2015 có giá thấp hơn giá mô hình dự báo, CẦN XÁC MINH; chưa chứng minh bị định giá thấp.",
    "Chênh lệch so với giá dự báo không phải lợi nhuận; chưa tính chi phí giao dịch, cải tạo, thuế, và không xác nhận hiện có thể mua ở giá đó.",
    "Ba mô hình dùng cùng dữ liệu nên đồng thuận không phải ba bằng chứng độc lập.",
    "Quy tắc chọn R1–R7 (sheet 'Quy tắc chọn') là lựa chọn của nhóm, chưa được hiệu chỉnh bằng kết quả thẩm định.",
    f"Mô hình chính: {BEST} (chọn bằng CV trên train). MAPE test {pct(m(K, BEST))}; nested CV {pct(S['king_nested_cv']['MAPE_%'])}.",
]})
with pd.ExcelWriter(ROOT / "outputs" / "task4" / "Top20_ung_vien_can_xac_minh.xlsx", engine="openpyxl") as xw:
    note.to_excel(xw, sheet_name="Đọc trước", index=False)
    top.rename(columns=VI).to_excel(xw, sheet_name="20 ứng viên cần xác minh", index=False)
    raw.rename(columns=VI).to_excel(xw, sheet_name="20 căn residual âm nhất (thô)", index=False)
    chk.rename(columns=VI).to_excel(xw, sheet_name="Thấp hơn >50% - xác minh", index=False)
    rules.to_excel(xw, sheet_name="Quy tắc chọn", index=False)
    freq.to_excel(xw, sheet_name="Tần suất xuất hiện", index=False)
    met.round(3).to_excel(xw, sheet_name="Báo cáo MAPE", index=False)
    thr.round(2).to_excel(xw, sheet_name="Độ nhạy ngưỡng", index=False)
    for ws in xw.book.worksheets:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = max(10, min(60, max(len(str(c.value or "")) for c in col) + 2))
        ws.freeze_panes = "A2"
old = ROOT / "outputs" / "task4" / "Top20_can_dinh_gia_thap.xlsx"
if old.exists():
    old.unlink()           # tên cũ ngụ ý "bị định giá thấp" (F05)

# ---------------- Word ----------------
doc = Document()
st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(13)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
for s in doc.sections:
    s.left_margin = s.right_margin = Cm(2.5); s.top_margin = s.bottom_margin = Cm(2)


def H(text, lvl):
    h = doc.add_heading(text, lvl)
    for r in h.runs:
        r.font.name = "Times New Roman"; r.font.color.rgb = RGBColor(0x1f, 0x3a, 0x5f)


def P(text, bold_prefix=None):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(6)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if bold_prefix:
        p.add_run(bold_prefix).bold = True
    p.add_run(text); return p


def B(text, bold_prefix=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        p.add_run(bold_prefix).bold = True
    p.add_run(text)


def IMG(name, caption, w=16):
    doc.add_picture(str(F / f"{name}.png"), width=Cm(w))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    c = doc.add_paragraph(caption); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.runs[0].italic = True; c.runs[0].font.size = Pt(11)


def TABLE(df, caption, fs=10):
    c = doc.add_paragraph(caption); c.runs[0].bold = True; c.runs[0].font.size = Pt(11)
    t = doc.add_table(rows=1, cols=len(df.columns)); t.style = "Light Grid Accent 1"
    for i, col in enumerate(df.columns):
        t.rows[0].cells[i].text = str(col)
    for _, row in df.iterrows():
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)
    for r in t.rows:
        for cell in r.cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(fs)
    doc.add_paragraph()


title = doc.add_heading("PHẦN 5 (tiếp) — A: PHÂN TÍCH CẤP 3 (DỰ BÁO) VÀ CẤP 4 (ĐỀ XUẤT)", 0)
for r in title.runs:
    r.font.size = Pt(18); r.font.name = "Times New Roman"
P("Chủ đề 14 — Mô hình định giá bất động sản tự động. Người thực hiện: Thành viên 4. Phiên bản 2 (23/11/2026), "
  "đã sửa theo feedback đánh giá ngày 21/11/2026. Mã nguồn: package bds_valuation/, scripts/task4_modeling.py, "
  "notebook notebooks/04_Modeling.ipynb (đã chạy, có đầu ra). Dữ liệu đầu vào: bộ dữ liệu sạch của Nhiệm vụ 2.")

H("5.9. Phân tích cấp 3 — Dự báo giá (Predictive)", 1)
H("5.9.1. Thiết kế mô hình và quy trình đánh giá", 2)
P("Bài toán: dự báo giá giao dịch (USD) của một căn nhà từ đặc điểm vật lý, vị trí và thời điểm bán, rồi so giá giao "
  "dịch với giá dự báo để lập danh sách căn cần thẩm định. Thị trường chính là King County (21.612 giao dịch, 21.435 tài "
  "sản) vì có tọa độ và zipcode; Ames (2.930 căn) dùng để kiểm chứng ở thị trường thứ hai, không gộp chung.")
B("20 biến số (diện tích, phòng, grade, condition, view, mặt nước, tuổi nhà, vĩ độ/kinh độ, khoảng cách tới trung tâm, "
  "diện tích nhà lân cận, …) và zipcode. Biến thêm: is_renovated, years_since_update, month_index. Mọi biến được tạo bởi "
  "một hàm duy nhất (bds_valuation.features.engineer_king_features) dùng chung cho huấn luyện và dự báo, có kiểm tra schema.",
  "Biến đầu vào: ")
B("price_per_sqft và price_iqr_outlier chứa giá mục tiêu nên bị loại khỏi X (có assert trong code).", "Chống rò rỉ: ")
B(f"80/20 theo id tài sản (GroupShuffleSplit, seed 42): train {fmt(S['test_split']['train_rows'])}, test "
  f"{fmt(S['test_split']['test_rows'])} giao dịch. Tập test là tập đánh giá cuối: không tham gia tinh chỉnh, không "
  "tham gia chọn mô hình.", "Chia dữ liệu: ")
B("mọi mô hình học log(price), đổi ngược về USD; MAPE/RMSE tính trên giá thật.", "Biến mục tiêu: ")
B("(0) Mốc thô = trung vị đơn giá/sqft của zipcode × diện tích (cách định giá thủ công); (1) Baseline Linear Regression; "
  "(2) Random Forest 300 cây; (3) XGBoost tinh chỉnh bằng RandomizedSearch 20 tổ hợp × GroupKFold 3 theo id trên train. "
  "Ba mô hình lấy từ một bảng ánh xạ tên → hàm khởi tạo dùng chung cho đánh giá, OOF và mô hình lưu (sửa lỗi F04).",
  "Các mô hình: ")
p = S["xgb_best_params"]
P(f"Tham số XGBoost tốt nhất (trên train): max_depth={p['max_depth']}, learning_rate={p['learning_rate']}, "
  f"n_estimators={p['n_estimators']}, subsample={p['subsample']}, colsample_bytree={p['colsample_bytree']}, "
  f"min_child_weight={p['min_child_weight']}, reg_lambda={p['reg_lambda']}.")
cv = cvt.copy(); cv["CV_MAPE_train_%"] = cv["CV_MAPE_train_%"].map(pct2); cv["Duoc_chon"] = cv["Duoc_chon"].map({True: "✔", False: ""})
cv.columns = ["Mô hình", "MAPE CV trên train", "Được chọn"]
TABLE(cv, "Bảng 5.9.1. Chọn mô hình bằng CV 3 fold theo id trên train (trước khi xem tập test)")
P(f"Mô hình được chọn: {BEST}. Điểm CV của XGBoost hơi lạc quan vì cùng các fold đã dùng để tinh chỉnh; vì vậy mục 5.9.3 "
  "báo thêm nested CV, nơi cả bước tinh chỉnh và chọn mô hình được làm lại bên trong từng fold.")

H("5.9.2. Báo cáo sai số trên tập test (MAPE, RMSE)", 2)
tb = met[met["Thi_truong"] == K][["Mo_hinh", "MAPE_%", "MdAPE_%", "RMSE", "R2", "Ty_le_sai_<=10%"]].copy()
tb.columns = ["Mô hình", "MAPE (%)", "MdAPE (%)", "RMSE (USD)", "R²", "% căn sai ≤10%"]
tb["RMSE (USD)"] = tb["RMSE (USD)"].map(fmt)
TABLE(tb.round(2), f"Bảng 5.9.2. Sai số trên tập test King County ({fmt(S['test_split']['test_rows'])} giao dịch của các tài sản không có trong train)")
IMG("king_model_comparison_mape", "Hình 5.9.1. MAPE theo mô hình trên tập test (xanh = mô hình chọn bằng CV)", 14)
P(f"{BEST}: MAPE {pct(m(K, BEST))}, MdAPE {pct(m(K, BEST, 'MdAPE_%'))}, RMSE {fmt(m(K, BEST, 'RMSE'))} USD, "
  f"R² {m(K, BEST, 'R2'):.3f}. So với baseline Linear Regression ({pct(m(K, LR))}) MAPE giảm "
  f"{pct(m(K, LR) - m(K, BEST))} điểm; so với mốc thô theo đơn giá zipcode ({pct(m(K, NAIVE))}) sai số tương đối giảm "
  f"khoảng {(1 - m(K, BEST) / m(K, NAIVE)) * 100:.0f}%. RMSE lớn hơn nhiều so với MAE vì một số căn đắt có sai số tuyệt đối "
  "lớn; với mục tiêu so sánh tương đối giữa các căn, MAPE là thước đo chính.")
IMG("king_actual_vs_predicted", "Hình 5.9.2. Giá thực tế và giá dự báo trên tập test (thang log)")
s_b = seg[seg["Mo_hinh"] == BEST].set_index("Phan_khuc")
P("MAPE theo phân khúc giá (5 nhóm bằng nhau của tập test): sai số cao nhất ở nhóm rẻ nhất "
  f"({pct(s_b.loc['Q1 rẻ nhất', 'MAPE_%'])}) và nhóm đắt nhất ({pct(s_b.loc['Q5 đắt nhất', 'MAPE_%'])}), thấp nhất ở nhóm giữa "
  f"({pct(s_b.loc['Q3', 'MAPE_%'])}). Hệ quả: căn giá rẻ dễ có residual âm lớn chỉ vì sai số mô hình lớn — cần thận trọng khi "
  "đọc danh sách ứng viên.")

H("5.9.3. Kiểm tra độ tin cậy của ước lượng sai số", 2)
P(f"Backtest thời gian độc lập (sửa F02). Tập tương lai được tách trước: giao dịch từ {vdate(TB['cutoff'])} của tài sản chưa "
  f"xuất hiện trong quá khứ ({fmt(TB['future_rows'])} giao dịch, {vdate(TB['future_date_range'][0])}–{vdate(TB['future_date_range'][1])}). "
  f"Chỉ quá khứ ({fmt(TB['past_rows'])} giao dịch) được dùng để tinh chỉnh và chọn mô hình: fit trên giao dịch trước "
  f"{vdate(TB['validation_start'])} ({fmt(TB['inner_train_rows'])}), validation là 3 tháng cuối quá khứ "
  f"({fmt(TB['inner_validation_rows'])}). Cấu hình được khóa ({LOCKED}), fit lại trên toàn bộ quá khứ rồi chấm tương lai "
  f"đúng một lần: MAPE {pct(m(KT, LOCKED))}, baseline Linear Regression {pct(m(KT, LR))}. Không hàng nào của tập tương lai "
  "tham gia tiền xử lý, tinh chỉnh hay chọn mô hình (có test tự động kiểm tra).")
P(f"Nested CV (F03). Outer GroupKFold 5 theo id trên toàn bộ giao dịch; trong mỗi outer-train, XGBoost được tinh chỉnh "
  f"(10 tổ hợp × GroupKFold 3) và mô hình được chọn giữa LR/RF/XGBoost, rồi mới dự báo outer-test. MAPE nested CV = "
  f"{pct(S['king_nested_cv']['MAPE_%'])} (R² {S['king_nested_cv']['R2']:.3f}); mô hình được chọn ở các fold: "
  f"{', '.join(nested['chosen_model'])}. Đây là ước lượng hiệu năng nghiêm ngặt nhất của toàn bộ quy trình.")
nt = nested[["outer_fold", "train_rows", "test_rows", "chosen_model", "outer_test_MAPE_%"]].copy()
nt["outer_test_MAPE_%"] = nt["outer_test_MAPE_%"].map(pct2)
nt.columns = ["Fold", "Train", "Test", "Mô hình chọn trong fold", "MAPE outer-test"]
TABLE(nt, "Bảng 5.9.3. Nested CV theo từng outer fold")
af = ames_fix.copy()
for c in ["MAPE_cu_dien_truoc_khi_chia_%", "MAPE_moi_dien_trong_pipeline_%"]:
    af[c] = af[c].map(pct2)
af["Chenh_lech_diem_%"] = af["Chenh_lech_diem_%"].map(lambda v: f"{v:+.3f}".replace(".", ","))
af = af[["Mo_hinh", "MAPE_cu_dien_truoc_khi_chia_%", "MAPE_moi_dien_trong_pipeline_%", "Chenh_lech_diem_%"]]
af.columns = ["Mô hình", "MAPE cũ (điền trước khi chia)", "MAPE mới (điền trong Pipeline)", "Chênh lệch (điểm %)"]
P(f"Ames — thị trường thứ hai (sửa F01). CSV sạch của Nhiệm vụ 2 phục vụ EDA nên đã điền trung vị theo neighborhood trên "
  "toàn bộ dữ liệu. Khi mô hình hóa, các ô điền học từ dữ liệu (lot_frontage, mas_vnr_area, garage_yr_blt, …) được trả lại "
  "NaN theo metadata/imputation_audit.csv và điền lại bằng GroupMedianImputer chỉ học trên train; điền cấu trúc cố định "
  "(NA = không có tiện ích) được giữ. Kết quả mới: XGBoost MAPE "
  f"{pct(m('Ames', 'XGBoost'))}, Linear Regression {pct(m('Ames', LR))}, Random Forest {pct(m('Ames', RF))}, mốc thô "
  f"{pct(m('Ames', 'Mốc thô: đơn giá neighborhood × diện tích'))}.")
TABLE(af, "Bảng 5.9.4. Ames: thay đổi MAPE sau khi đưa điền thiếu vào Pipeline")

H("5.9.4. Phân tích độ nhạy của mô hình", 2)
IMG("king_sensitivity", "Hình 5.9.3. Trái: tầm quan trọng của biến (permutation). Phải: what-if — % thay đổi giá dự báo", 16.5)
pi = perm.set_index("Bien")["MAPE_tang_diem_%"]
P(f"Permutation importance trên tập test: {perm.iloc[0]['Bien']} ({perm.iloc[0]['MAPE_tang_diem_%']:.1f} điểm MAPE), "
  f"{perm.iloc[1]['Bien']} ({perm.iloc[1]['MAPE_tang_diem_%']:.1f}), {perm.iloc[2]['Bien']} ({perm.iloc[2]['MAPE_tang_diem_%']:.1f}), "
  f"{perm.iloc[3]['Bien']} ({perm.iloc[3]['MAPE_tang_diem_%']:.1f}). Vị trí và diện tích/chất lượng chi phối mô hình, khớp "
  "với kết quả EDA của Nhiệm vụ 3.")
w = wif.set_index("Kich_ban")
wv = w["Trung_vi_thay_doi_%"]
P("What-if (sửa F06): thay một đặc điểm trên tập test, giữ nguyên biến khác, lấy trung vị % thay đổi giá dự báo. Kịch bản "
  "diện tích nay giữ đúng sqft_living = sqft_above + sqft_basement: tăng diện tích trên mặt đất 10% (hầm giữ nguyên) "
  f"{wv['Diện tích trên mặt đất +10% (hầm giữ nguyên)']:+.1f}%, tăng tổng diện tích 10% (cả hầm) "
  f"{wv['Tổng diện tích ở +10% (trên mặt đất và hầm cùng tỷ lệ)']:+.1f}%; grade +1 {wv['Grade (chất lượng xây) +1']:+.1f}%; "
  f"view +1 {wv['View +1 bậc']:+.1f}%; condition +1 {wv['Condition (tình trạng) +1']:+.1f}%; đặt về trạng thái vừa cải tạo "
  f"{wv['Đặt về trạng thái vừa cải tạo (years_since_update = 0)']:+.1f}%; thêm phòng ngủ cùng diện tích "
  f"{wv['Thêm 1 phòng ngủ (cùng diện tích)']:+.1f}%. Kịch bản 'thời điểm bán +6 tháng' có "
  f"{pct(w.loc['Thời điểm bán +6 tháng', 'Ty_le_ngoai_mien_huan_luyen_%'])} dòng nằm ngoài khoảng thời gian huấn luyện, "
  "nên mô hình cây không ngoại suy được xu hướng — không dùng để dự báo giá tương lai.")
P("Giới hạn diễn giải (F07): các con số trên là phản ứng của mô hình khi thay đầu vào, không phải tác động nhân quả của việc "
  "cải tạo hay nâng cấp ngoài thực tế. Chưa có chi phí, khả năng thực hiện hay lợi nhuận ròng, nên chúng chỉ dùng để đặt "
  "giả thuyết khảo sát (ví dụ: kiểm tra chi phí nâng grade ở các căn ứng viên), không dùng để khẳng định hiệu quả cải tạo.")

H("5.10. Phân tích cấp 4 — Đề xuất (Prescriptive): danh sách 20 ứng viên cần xác minh", 1)
H("5.10.1. Phương pháp", 2)
P("Residual = giá giao dịch − giá dự báo; residual % = giá giao dịch / giá dự báo − 1. Residual âm nghĩa là giá giao dịch "
  "lịch sử thấp hơn mức mô hình dự báo cho đặc điểm của căn. Điều này chưa chứng minh căn bị định giá thấp: chênh lệch có thể "
  "do mô hình dự báo cao, thiếu đặc điểm quan trọng (nội thất, pháp lý), giao dịch đặc biệt, lỗi dữ liệu, hoặc cơ hội thật. "
  "Vì vậy danh sách được gọi là ứng viên có giá giao dịch thấp hơn dự báo, cần xác minh (sửa F05).")
P(f"Giá dự báo dùng cho sàng lọc là dự báo out-of-fold (GroupKFold 5 theo id), trung bình {BEST} qua 4 seed chia fold; MAPE "
  f"OOF {pct(S['oof_screening_mape_pct'])}. Giới hạn (F03): bộ siêu tham số đã chọn trước trên train, nên 'mô hình chưa thấy "
  "tài sản' chỉ đúng ở bước fit; ước lượng hiệu năng nghiêm ngặt là nested CV ở mục 5.9.3. Với ngưỡng −20%, "
  f"{pct(S['below_prediction_rate_pct_all_transactions'])} giao dịch có giá thấp hơn dự báo từ 20% trở lên.")
IMG("king_residuals_and_candidates_map", "Hình 5.10.1. Phân phối residual out-of-fold và vị trí 20 ứng viên")
rt = rules.copy(); rt.columns = ["Mã", "Quy tắc", "Lý do"]
TABLE(rt, "Bảng 5.10.1. Quy tắc chọn ứng viên (quy tắc của nhóm, chưa hiệu chỉnh bằng thẩm định thực tế)", fs=9)
P("Mục tiêu của quy tắc là ưu tiên chênh lệch tương đối so với giá dự báo, ổn định qua ba mô hình, và loại trường hợp nhiều "
  "khả năng là giao dịch đặc biệt hoặc lỗi dữ liệu. Quy tắc không tối ưu lợi nhuận hay phân bổ vốn (F08). Ba mô hình dùng cùng "
  f"dữ liệu nên đồng thuận không phải ba bằng chứng độc lập. Danh sách thô (20 căn residual âm nhất, không lọc R4–R6) gồm các "
  f"căn thấp hơn dự báo {raw['below_prediction_pct'].min():.0f}–{raw['below_prediction_pct'].max():.0f}%, mức lệch gấp nhiều lần "
  f"sai số điển hình; {S['needs_verification_count']} căn thấp hơn trên 50% được chuyển sang danh sách xác minh dữ liệu "
  "(Excel, sheet 4) thay vì bị bỏ đi.")

H("5.10.2. Danh sách 20 ứng viên", 2)
t20 = top[["Hang", "id", "date", "zipcode", "price", "predicted_price", "below_prediction_conservative_pct", "sqft_living",
           "grade", "house_age"]].copy()
t20["price"] = t20["price"].map(fmt); t20["predicted_price"] = t20["predicted_price"].map(fmt)
for c in ["sqft_living", "grade", "house_age"]:
    t20[c] = t20[c].astype(int)
t20["below_prediction_conservative_pct"] = t20["below_prediction_conservative_pct"].map(lambda v: f"{v:.1f}".replace(".", ","))
t20.columns = ["#", "Mã id", "Ngày GD", "Zip", "Giá GD lịch sử", "Giá dự báo", "Thấp hơn (thận trọng) %", "Sqft", "Grade", "Tuổi"]
TABLE(t20, "Bảng 5.10.2. 20 ứng viên có giá giao dịch thấp hơn dự báo, cần xác minh (USD) — bản đầy đủ: "
      "outputs/task4/Top20_ung_vien_can_xac_minh.xlsx", fs=8.5)
P(f"Tổng giá giao dịch lịch sử của 20 căn: {fmt(S['top20_total_historical_price_usd'])} USD; tổng giá dự báo: "
  f"{fmt(S['top20_total_predicted_usd'])} USD. Chênh lệch so với giá dự báo ({fmt(S['top20_gap_to_prediction_usd'])} USD) mô tả "
  "khoảng cách giữa giá lịch sử và giá mô hình, không phải lợi nhuận có thể đạt được: đây là giao dịch 2014–2015, chưa có chi "
  "phí giao dịch, cải tạo, thuế, và không xác nhận hiện có thể mua ở giá đó. Đa số ứng viên là nhà giá thấp "
  f"({top['price'].min()/1000:.0f}–{top['price'].max()/1000:.0f} nghìn USD) — đúng phân khúc mà MAPE của mô hình cao nhất.")

H("5.10.3. Độ nhạy của danh sách ứng viên", 2)
th = thr[["Nguong_%", "So_can_ung_vien", "Ty_le_ung_vien_%", "Ca_3_mo_hinh_dong_y", "Gia_trung_vi_USD"]].copy()
th.columns = ["Ngưỡng thấp hơn dự báo (%)", "Số căn", "Tỷ lệ (%)", "Cả 3 mô hình cùng thấy", "Giá trung vị (USD)"]
th["Giá trung vị (USD)"] = th["Giá trung vị (USD)"].map(fmt)
TABLE(th.round(2), "Bảng 5.10.3. Số căn theo ngưỡng (giao dịch gần nhất của mỗi căn, sau R1–R3) — dữ liệu cho thanh trượt What-if")
r20 = thr.set_index("Nguong_%")
P(f"Ngưỡng 10% cho {fmt(r20.loc[10, 'So_can_ung_vien'])} căn, 20% cho {fmt(r20.loc[20, 'So_can_ung_vien'])}, 30% cho "
  f"{fmt(r20.loc[30, 'So_can_ung_vien'])}. Ở mọi ngưỡng trong bảng vẫn có đủ 20 căn nên ràng buộc 20 căn khả thi; ngưỡng càng cao "
  "thì giá trung vị của ứng viên càng thấp, xác nhận rằng mức chênh lệch lớn tập trung ở nhà rẻ.")
sb = stab.copy(); sb.columns = ["Biến thể", "Số căn trùng với danh sách chính", "Tỷ lệ (%)"]
TABLE(sb, "Bảng 5.10.4. Độ ổn định của danh sách 20 căn khi thay đổi seed, mô hình xếp hạng hoặc thước đo", fs=9)
nseed = S["seed_variants_counted"]
main_freq = freq[freq["Trong_danh_sach_chinh"] == 1]["So_lan_xuat_hien"]
P(f"Tần suất xuất hiện (F08): qua {nseed} biến thể (4 seed × 2 cách xếp hạng), {len(freq)} tài sản khác nhau từng vào top 20; "
  f"{S['top20_core_all_seed_variants']} căn xuất hiện ở mọi biến thể; trong danh sách chính, "
  f"{int((main_freq >= nseed / 2).sum())}/20 căn xuất hiện ở ít nhất một nửa số biến thể. Số căn trùng ở từng biến thể chưa "
  "chứng minh có một nhóm lõi cố định; bảng tần suất (outputs/task4/tables/top20_membership_frequency.csv, sheet 'Tần suất "
  "xuất hiện') mới là cơ sở để nói về nhóm lõi. Xếp theo chênh lệch USD cho danh sách gần như khác hẳn (thiên về nhà đắt), "
  "cho thấy danh sách phụ thuộc mục tiêu xếp hạng.")

H("5.10.4. Khuyến nghị cho Giám đốc đầu tư", 2)
for t in [
    "Dùng 20 căn làm danh sách thẩm định ưu tiên, không phải danh sách mua: mô hình chỉ thấy đặc điểm có trong dữ liệu, không "
    "thấy nội thất hư hỏng, pháp lý, hay điều kiện bán; giao dịch là lịch sử 2014–2015.",
    "Bước xác minh cho từng căn: kiểm tra lịch sử giao dịch và điều kiện bán (bán cho người thân, thừa kế, bán tháo), thẩm định "
    "thực địa, rồi mới định giá lại theo thị trường hiện tại.",
    "Ưu tiên căn xuất hiện ở nhiều biến thể (bảng tần suất) và có mức thấp hơn dự báo thận trọng lớn; căn ở cuối danh sách hoặc "
    "chỉ xuất hiện ở một biến thể nên được xem là ít chắc chắn hơn.",
    "Không dùng kết quả what-if để quyết định cải tạo: đó là phản ứng của mô hình, chưa có chi phí và bằng chứng nhân quả. Nếu "
    "muốn đánh giá cải tạo, cần dữ liệu chi phí và so sánh giao dịch trước/sau cải tạo.",
    f"Theo dõi KPI: MAPE trên giao dịch mới (tham chiếu backtest thời gian {pct(m(KT, LOCKED))}) và tỷ lệ ứng viên; huấn luyện lại "
    "định kỳ vì mô hình không ngoại suy được xu hướng giá theo thời gian.",
]:
    B(t)

H("5.10.5. Hạn chế", 2)
for t in [
    "Dữ liệu 2014–2015; King County không có thông tin điều kiện giao dịch nên một phần residual âm là giao dịch không theo thị "
    "trường mà mô hình không phân biệt được.",
    f"MAPE ở phân khúc rẻ ({pct(s_b.loc['Q1 rẻ nhất', 'MAPE_%'])}) không xa ngưỡng 20%; ngưỡng −20%, trần −50% và lọc tuổi nhà "
    "là quy tắc nhóm đặt, chưa hiệu chỉnh bằng kết quả thẩm định.",
    "Giá dự báo là ước lượng điểm, chưa có khoảng dự báo; không có cận trên/cận dưới thống kê cho chênh lệch.",
    "Mô hình là tương quan, không nhân quả.",
]:
    B(t)

H("Phụ lục — Sản phẩm bàn giao Nhiệm vụ 4", 2)
for t in [f"models/model.pkl — {BEST} (chọn bằng CV trên train) fit lại trên toàn bộ King County; dự báo qua "
          "bds_valuation.predict.predict_prices (tạo biến + kiểm tra schema).",
          "notebooks/04_Modeling.ipynb — notebook đã chạy; scripts/task4_modeling.py — cùng nội dung dạng script.",
          "outputs/task4/Top20_ung_vien_can_xac_minh.xlsx — 20 ứng viên, danh sách thô, danh sách xác minh dữ liệu, quy tắc, tần suất, MAPE.",
          "outputs/task4/tables/ — model_metrics_mape_report.csv, temporal_backtest.json, nested_cv_folds.csv, "
          "ames_imputation_fix_comparison.csv, king_oof_predictions.csv (dữ liệu Dashboard), các bảng độ nhạy.",
          "outputs/task4/figures/ — 4 biểu đồ, mỗi biểu đồ có PNG và SVG.",
          "tests/ — bộ kiểm thử tự động (pytest)."]:
    B(t)

out = ROOT / "reports" / "Bao_cao_Nhiem_vu_4.docx"
out.parent.mkdir(exist_ok=True)
doc.save(out)
print("Wrote", out)
