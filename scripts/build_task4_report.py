"""Tạo báo cáo Nhiệm vụ 4 (Phần 5 — cấp 3, 4) dạng .docx và bảng 20 căn dạng .xlsx từ kết quả đã chạy."""
import json
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / "outputs" / "task4" / "tables"
F = ROOT / "outputs" / "task4" / "figures"
S = json.loads((T / "task4_summary.json").read_text(encoding="utf-8"))
met = pd.read_csv(T / "model_metrics_mape_report.csv")
seg = pd.read_csv(T / "mape_by_price_segment.csv")
thr = pd.read_csv(T / "sensitivity_threshold.csv")
stab = pd.read_csv(T / "sensitivity_top20_stability.csv")
wif = pd.read_csv(T / "sensitivity_whatif.csv")
perm = pd.read_csv(T / "permutation_importance.csv")
top = pd.read_csv(T / "top20_undervalued_king.csv", dtype={"id": str, "zipcode": str})
raw = pd.read_csv(T / "top20_raw_largest_negative_residual_king.csv", dtype={"id": str})
chk = pd.read_csv(T / "candidates_need_verification_king.csv", dtype={"id": str})

def m(market, model, col="MAPE_%"):
    return float(met[(met["Thi_truong"] == market) & (met["Mo_hinh"] == model)][col].iloc[0])

K, KT = "King County", "King County (chia theo thời gian)"
XG, LR, RF = "XGBoost (tuned)", "Linear Regression (baseline)", "Random Forest"
NAIVE = "Mốc thô: đơn giá zipcode × diện tích"

# ---------------- Excel 20 căn ----------------
vi = top.rename(columns={
    "Hang": "Hạng", "id": "Mã tài sản (id)", "date": "Ngày giao dịch", "zipcode": "Zipcode",
    "price": "Giá giao dịch (USD)", "predicted_price": "Giá trị mô hình (USD)",
    "upside_usd": "Chênh lệch (USD)", "discount_pct": "Mức giảm theo XGBoost (%)",
    "discount_conservative_pct": "Mức giảm thận trọng (%)", "residual": "Residual (USD)",
    "models_agree_undervalued": "Số mô hình đồng ý (/3)", "sqft_living": "Diện tích ở (sqft)",
    "bedrooms": "Phòng ngủ", "bathrooms": "Phòng tắm", "grade": "Grade", "condition": "Condition",
    "view": "View", "waterfront": "Mặt nước", "house_age": "Tuổi nhà", "distance_to_center_km":
    "Cách trung tâm (km)", "lat": "Vĩ độ", "long": "Kinh độ", "cumulative_cost_usd": "Vốn lũy kế (USD)"})
with pd.ExcelWriter(ROOT / "outputs" / "task4" / "Top20_can_dinh_gia_thap.xlsx") as xw:
    vi.to_excel(xw, sheet_name="20 căn khuyến nghị", index=False)
    raw.to_excel(xw, sheet_name="20 căn thô (residual âm nhất)", index=False)
    chk.to_excel(xw, sheet_name="Giảm >50% - cần xác minh", index=False)
    met.round(3).to_excel(xw, sheet_name="Báo cáo MAPE", index=False)
    thr.round(2).to_excel(xw, sheet_name="Độ nhạy ngưỡng", index=False)
    for ws in xw.book.worksheets:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = max(10, min(40, max(len(str(c.value or "")) for c in col) + 2))
        ws.freeze_panes = "A2"

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

fmt = lambda v: f"{v:,.0f}".replace(",", ".")
pct = lambda v: f"{v:.1f}".replace(".", ",") + "%"

title = doc.add_heading("PHẦN 5 (tiếp) — A: PHÂN TÍCH CẤP 3 (DỰ BÁO) VÀ CẤP 4 (ĐỀ XUẤT)", 0)
for r in title.runs:
    r.font.size = Pt(18); r.font.name = "Times New Roman"
P("Chủ đề 14 — Mô hình định giá bất động sản tự động. Người thực hiện: Thành viên 4. "
  "Mã nguồn: notebooks/04_Modeling.ipynb (đã chạy, có đầu ra) và scripts/task4_modeling.py. "
  "Dữ liệu đầu vào: bộ dữ liệu sạch của Nhiệm vụ 2.")

H("5.3. Phân tích cấp 3 — Dự báo giá (Predictive)", 1)
H("5.3.1. Thiết kế mô hình", 2)
P(f"Bài toán: dự báo giá giao dịch (USD) của một căn nhà từ đặc điểm vật lý, vị trí và thời điểm bán, rồi so "
  f"giá thực với giá mô hình để tìm căn bị định giá thấp. Thị trường chính là King County (21.612 giao dịch, "
  f"21.435 tài sản) vì có tọa độ và zipcode; Ames (2.930 căn) dùng để kiểm chứng ở thị trường thứ hai, không gộp chung.")
B("20 biến số (diện tích, phòng, grade, condition, view, mặt nước, tuổi nhà, vĩ độ/kinh độ, khoảng cách tới "
  "trung tâm, diện tích nhà lân cận, …) và zipcode. Tạo thêm: is_renovated, years_since_update (số năm từ lần "
  "xây/cải tạo gần nhất), month_index (xu hướng thị trường theo tháng).", "Biến đầu vào: ")
B("price_per_sqft và price_iqr_outlier chứa giá mục tiêu nên bị loại khỏi X (có assert kiểm tra trong code); "
  "id, source_row_id chỉ dùng truy vết.", "Chống rò rỉ: ")
B(f"80/20 theo id tài sản (GroupShuffleSplit, seed 42): train {fmt(S['test_split']['train_rows'])}, test "
  f"{fmt(S['test_split']['test_rows'])} giao dịch; 177 giao dịch bán lại không thể nằm ở cả hai phía. "
  "Mọi bước tiền xử lý nằm trong Pipeline và chỉ học trên train.", "Chia dữ liệu: ")
B("mọi mô hình học log(price) do giá lệch phải mạnh, sau đó đổi ngược về USD; MAPE/RMSE tính trên giá thật.",
  "Biến mục tiêu: ")
B("(0) Mốc thô = trung vị đơn giá/sqft của zipcode × diện tích — cách định giá thủ công của môi giới; "
  "(1) Baseline Linear Regression (log diện tích, chuẩn hóa, one-hot zipcode); (2) Random Forest 300 cây; "
  "(3) XGBoost tinh chỉnh bằng RandomizedSearch 20 tổ hợp × 3-fold theo id trên train.", "Các mô hình: ")
p = S["xgb_best_params"]
P(f"Tham số XGBoost tốt nhất: max_depth={p['max_depth']}, learning_rate={p['learning_rate']}, "
  f"n_estimators={p['n_estimators']}, subsample={p['subsample']}, colsample_bytree={p['colsample_bytree']}, "
  f"min_child_weight={p['min_child_weight']}, reg_lambda={p['reg_lambda']}.")

H("5.3.2. Báo cáo sai số (MAPE, RMSE)", 2)
tb = met[met["Thi_truong"] == K][["Mo_hinh", "MAPE_%", "MdAPE_%", "RMSE", "R2", "Ty_le_sai_<=10%"]].copy()
tb.columns = ["Mô hình", "MAPE (%)", "MdAPE (%)", "RMSE (USD)", "R²", "% căn sai ≤10%"]
tb["RMSE (USD)"] = tb["RMSE (USD)"].map(fmt)
TABLE(tb.round(2), "Bảng 5.3.1. Sai số trên tập test King County (4.321 giao dịch chưa từng thấy khi huấn luyện)")
IMG("king_model_comparison_mape", "Hình 5.3.1. MAPE theo mô hình — XGBoost thấp nhất", 14)
P(f"XGBoost là mô hình tốt nhất: MAPE {pct(m(K, XG))}, nghĩa là trung bình giá dự báo lệch khoảng "
  f"{pct(m(K, XG))} so với giá thực; một nửa số căn lệch dưới {pct(m(K, XG, 'MdAPE_%'))}. So với baseline "
  f"Linear Regression ({pct(m(K, LR))}), XGBoost giảm {pct(m(K, LR) - m(K, XG))} điểm MAPE và giảm RMSE từ "
  f"{fmt(m(K, LR, 'RMSE'))} xuống {fmt(m(K, XG, 'RMSE'))} USD. So với cách định giá thủ công theo đơn giá "
  f"zipcode ({pct(m(K, NAIVE))}), mô hình giảm sai số khoảng {(1 - m(K, XG) / m(K, NAIVE)) * 100:.0f}%. "
  f"RMSE lớn hơn nhiều so với MAE vì một số căn đắt (trên 2 triệu USD) có sai số tuyệt đối lớn; với mục tiêu "
  f"so sánh tương đối giữa các căn, MAPE là thước đo chính.")
IMG("king_actual_vs_predicted", "Hình 5.3.2. Giá thực tế và giá dự báo trên tập test (thang log)")

s_lr = seg[seg["Mo_hinh"] == LR].set_index("Phan_khuc")["MAPE_%"]
s_xg = seg[seg["Mo_hinh"] == XG].set_index("Phan_khuc")
P("MAPE theo phân khúc giá (chia tập test thành 5 nhóm bằng nhau): XGBoost tốt hơn baseline ở cả 5 nhóm. "
  f"Sai số cao nhất ở nhóm rẻ nhất (dưới ~300 nghìn USD: {pct(s_xg.loc['Q1 rẻ nhất', 'MAPE_%'])}) và nhóm đắt nhất "
  f"({pct(s_xg.loc['Q5 đắt nhất', 'MAPE_%'])}); thấp nhất ở nhóm giữa ({pct(s_xg.loc['Q3', 'MAPE_%'])}). "
  "Hệ quả: căn giá rẻ dễ bị mô hình đánh giá là \"định giá thấp\" chỉ vì sai số lớn — cần thận trọng khi đọc danh sách ứng viên.")
B(f"Chia theo thời gian (học giao dịch trước 01/02/2015, dự báo giao dịch sau đó của các căn chưa thấy): "
  f"XGBoost MAPE {pct(m(KT, XG))}, baseline {pct(m(KT, LR))}. Sai số tăng khoảng 1 điểm % khi dự báo tương lai "
  "nhưng thứ hạng mô hình không đổi.", "Kiểm tra tính tổng quát: ")
B(f"Ames: XGBoost MAPE {pct(m('Ames', 'XGBoost'))}, Linear Regression {pct(m('Ames', LR))}, Random Forest "
  f"{pct(m('Ames', RF))}, mốc thô {pct(m('Ames', 'Mốc thô: đơn giá neighborhood × diện tích'))}. Ames đồng nhất hơn "
  "nên sai số thấp hơn King County; XGBoost vẫn tốt nhất nhưng chênh lệch với hồi quy tuyến tính nhỏ.", "Thị trường thứ hai: ")

H("5.3.3. Phân tích độ nhạy của mô hình", 2)
IMG("king_sensitivity", "Hình 5.3.3. Trái: tầm quan trọng của biến (permutation). Phải: what-if — % thay đổi giá dự báo", 16.5)
top3 = perm.head(4)
P("Permutation importance (xáo trộn ngẫu nhiên một biến trên tập test và đo MAPE tăng thêm): vị trí chi phối mô hình — "
  f"xáo trộn vĩ độ làm MAPE tăng {top3.iloc[0]['MAPE_tang_diem_%']:.1f} điểm, khoảng cách tới trung tâm "
  f"{perm.set_index('Bien').loc['distance_to_center_km', 'MAPE_tang_diem_%']:.1f} điểm; tiếp theo là diện tích ở "
  f"({perm.set_index('Bien').loc['sqft_living', 'MAPE_tang_diem_%']:.1f}) và grade "
  f"({perm.set_index('Bien').loc['grade', 'MAPE_tang_diem_%']:.1f}). Điều này khớp với kết quả EDA của Nhiệm vụ 3 "
  "(giá phân hóa mạnh theo zipcode).")
w = wif.set_index("Kich_ban")["Trung_vi_thay_doi_%"]
P("What-if (thay một đặc điểm trên toàn bộ tập test, giữ nguyên các biến khác, lấy trung vị % thay đổi giá dự báo): "
  f"cải tạo mới {w.iloc[0]:+.1f}%, tăng grade 1 bậc {w['Grade (chất lượng xây) +1']:+.1f}%, tăng view 1 bậc "
  f"{w['View +1 bậc']:+.1f}%, condition +1 {w['Condition (tình trạng) +1']:+.1f}%, diện tích ở +10% "
  f"{w['Diện tích ở +10%']:+.1f}%, thời điểm bán muộn 6 tháng {w['Thời điểm bán +6 tháng']:+.1f}%, tuổi nhà +10 năm "
  f"{w['Tuổi nhà +10 năm']:+.1f}%. Thêm phòng ngủ khi giữ nguyên diện tích gần như không tăng giá "
  f"({w['Thêm 1 phòng ngủ (cùng diện tích)']:+.1f}%) — chia nhỏ phòng không tạo giá trị. Các chiều tác động đều "
  "hợp lý về kinh tế, cho thấy mô hình không học các quan hệ phi lý. Gợi ý đầu tư: cải tạo và nâng chất lượng "
  "hoàn thiện là đòn bẩy giá trị lớn nhất sau khi mua.")

H("5.4. Phân tích cấp 4 — Đề xuất (Prescriptive): danh sách 20 căn", 1)
H("5.4.1. Phương pháp xác định căn bị định giá thấp", 2)
P("Residual = giá giao dịch − giá mô hình; residual % = giá giao dịch / giá mô hình − 1. Residual âm nghĩa là căn "
  "được bán rẻ hơn giá trị mà đặc điểm của nó gợi ý. Để residual khách quan, mỗi giao dịch được định giá bởi mô hình "
  "chưa từng thấy tài sản đó (dự báo out-of-fold, 5-fold theo id). Nếu dùng mô hình đã học cả căn đó, residual "
  "sẽ bị thu nhỏ giả tạo. Giá mô hình chính là trung bình XGBoost qua 4 cách chia fold khác nhau, "
  f"đạt MAPE out-of-fold {pct(S['oof_mape_pct'])} trên toàn bộ dữ liệu.")
P(f"Với ngưỡng 20% theo KPI của nhóm, {pct(S['undervalued_rate_pct_all_transactions'])} giao dịch có giá thấp hơn "
  "giá mô hình từ 20% trở lên (tỷ lệ ứng viên).")
IMG("king_residuals_and_candidates_map", "Hình 5.4.1. Phân phối residual out-of-fold và vị trí 20 căn khuyến nghị")
P("Quy tắc chọn 20 căn (danh sách khuyến nghị):", None)
for t in ["Mỗi tài sản chỉ xét giao dịch gần nhất (không chọn trùng căn).",
          "Loại căn có 0 phòng ngủ/tắm (nghi lỗi dữ liệu) và căn condition ≤ 2 (giá thấp do hư hỏng là có lý do).",
          "Cả 3 mô hình (XGBoost, Random Forest, Linear Regression) cùng cho residual ≤ −20%.",
          "Mức giảm không quá 50%; loại nhà tuổi 0 (đang xây/vừa xây, giá có thể là giá đất hoặc đặt cọc).",
          "Xếp theo mức giảm thận trọng = mức giảm nhỏ nhất trong 3 mô hình, lấy 20 căn đầu."]:
    B(t)
P(f"Vì sao không lấy thẳng 20 căn có residual âm nhất? Danh sách thô đó (lưu trong file Excel, sheet 2) gồm toàn các căn "
  f"giảm {raw['discount_pct'].min():.0f}–{raw['discount_pct'].max():.0f}%, mức lệch gấp 5–10 lần sai số điển hình của mô hình. "
  f"Ví dụ căn hạng 1 rộng {fmt(raw.iloc[0]['sqft_living'])} sqft, grade {raw.iloc[0]['grade']}, tuổi nhà 0, bán "
  f"{fmt(raw.iloc[0]['price'])} USD so với giá mô hình {fmt(raw.iloc[0]['predicted_price'])} USD. Những giao dịch "
  "như vậy thường là bán cho người thân, thừa kế, bán tháo, bán khi nhà chưa xây xong, hoặc lỗi nhập liệu; nhà đầu "
  f"tư không thể mua lại với giá đó. {S['needs_verification_count']} căn giảm trên 50% được chuyển sang danh sách "
  "\"cần xác minh\" (sheet 3) thay vì bị bỏ đi.")

H("5.4.2. Danh sách 20 căn ứng viên", 2)
t20 = top[["Hang", "id", "zipcode", "price", "predicted_price", "discount_conservative_pct", "sqft_living",
           "bedrooms", "grade", "house_age"]].copy()
t20["price"] = t20["price"].map(fmt); t20["predicted_price"] = t20["predicted_price"].map(fmt)
t20.columns = ["#", "Mã id", "Zip", "Giá bán", "Giá mô hình", "Giảm thận trọng %", "Sqft", "PN", "Grade", "Tuổi"]
TABLE(t20, "Bảng 5.4.1. 20 căn bị định giá thấp (USD) — bản đầy đủ: outputs/task4/Top20_can_dinh_gia_thap.xlsx", fs=9)
P(f"Tổng vốn mua 20 căn: {fmt(S['top20_total_price_usd'])} USD; tổng giá trị theo mô hình "
  f"{fmt(S['top20_total_predicted_usd'])} USD; chênh lệch kỳ vọng {fmt(S['top20_total_predicted_usd'] - S['top20_total_price_usd'])} USD. "
  "Cột \"Vốn lũy kế\" trong file Excel giúp Giám đốc đầu tư cắt danh sách theo ngân sách thực tế. Đa số ứng viên là nhà "
  f"giá thấp ({top['price'].min()/1000:.0f}–{top['price'].max()/1000:.0f} nghìn USD), tuổi cao, ở phía nam và bắc Seattle — đúng phân khúc mà MAPE của mô hình cao nhất, "
  "nên chênh lệch kỳ vọng là cận trên, không phải lợi nhuận chắc chắn.")

H("5.4.3. Độ nhạy của danh sách ứng viên", 2)
th = thr[["Nguong_%", "So_can_ung_vien", "Ty_le_ung_vien_%", "Ca_3_mo_hinh_dong_y", "Gia_trung_vi_USD"]].copy()
th.columns = ["Ngưỡng giảm (%)", "Số căn", "Tỷ lệ (%)", "Cả 3 mô hình đồng ý", "Giá trung vị (USD)"]
th["Giá trung vị (USD)"] = th["Giá trung vị (USD)"].map(fmt)
TABLE(th.round(2), "Bảng 5.4.2. Số căn ứng viên theo ngưỡng (giao dịch gần nhất của mỗi căn, đã lọc cơ bản)")
P("Số ứng viên giảm nhanh khi siết ngưỡng: 10% cho khoảng 3,7 nghìn căn, 20% còn khoảng 1,2 nghìn, 30% còn khoảng 400. "
  "Ở mọi ngưỡng từ 5% đến 40% vẫn có đủ 20 căn, nên ràng buộc 20 căn luôn khả thi; ngưỡng càng cao thì giá trung vị "
  "của ứng viên càng thấp, xác nhận rằng các mức giảm lớn tập trung ở nhà rẻ. Bảng này là dữ liệu cho thanh trượt "
  "What-if trên Dashboard (Nhiệm vụ 5).")
sb = stab.copy(); sb.columns = ["Biến thể", "Số căn trùng với danh sách chính", "Tỷ lệ (%)"]
TABLE(sb, "Bảng 5.4.3. Độ ổn định của danh sách 20 căn khi thay đổi cách tính")
P("Khi chỉ dùng một lần chia fold của XGBoost, danh sách giữ được 75–90% số căn; vì vậy lấy trung bình nhiều lần chia "
  "và xếp theo mức giảm thận trọng là cần thiết. Nếu xếp theo residual của riêng XGBoost, danh sách chỉ giữ khoảng "
  "một nửa. Xếp theo residual USD cho một danh sách gần như khác hẳn (thiên về nhà đắt), nên nhóm chọn residual %. "
  "Khoảng 15–17/20 căn là nhóm lõi ổn định; các căn cuối danh sách nên được thẩm định kỹ hơn.")

H("5.4.4. Khuyến nghị cho Giám đốc đầu tư", 2)
for t in [
    "Dùng danh sách 20 căn làm danh sách thẩm định ưu tiên, không phải danh sách mua ngay: mô hình chỉ thấy các đặc "
    "điểm có trong dữ liệu, không thấy nội thất hư hỏng, pháp lý, hay điều kiện bán.",
    "Thẩm định thực địa và kiểm tra lịch sử giao dịch của từng căn trước, ưu tiên các căn có mức giảm thận trọng cao và "
    "grade ≥ 7.",
    "Phân bổ ngân sách theo cột vốn lũy kế; nếu ngân sách nhỏ hơn tổng vốn, giữ thứ tự theo mức giảm thận trọng.",
    "Sau khi mua, cải tạo và nâng chất lượng hoàn thiện là đòn bẩy giá trị lớn nhất theo phân tích what-if "
    "(+8% đến +10% giá trị dự báo).",
    "Theo dõi KPI: MAPE của mô hình trên giao dịch mới (mục tiêu dưới 12–13%) và tỷ lệ ứng viên; huấn luyện lại mô hình "
    "định kỳ vì giá tăng theo thời gian (+2,9% sau 6 tháng theo mô hình).",
]:
    B(t)

H("5.4.5. Hạn chế", 2)
for t in [
    "Dữ liệu 2014–2015, không có thông tin điều kiện giao dịch (bán tháo, người thân) ở King County nên một phần residual "
    "âm là giao dịch không theo thị trường mà mô hình không phân biệt được.",
    "MAPE ở phân khúc rẻ khoảng 16%, cao hơn ngưỡng 20% không nhiều; nên dùng mức giảm thận trọng và sự đồng thuận của 3 mô hình.",
    "Mô hình là tương quan, không nhân quả: kết quả what-if mô tả cách mô hình phản ứng, không đảm bảo thị trường trả đúng mức đó.",
]:
    B(t)

H("Phụ lục — Sản phẩm bàn giao Nhiệm vụ 4", 2)
for t in ["models/model.pkl — mô hình XGBoost (đã huấn luyện trên toàn bộ dữ liệu King County) kèm danh sách biến và metadata.",
          "notebooks/04_Modeling.ipynb — notebook đã chạy; scripts/task4_modeling.py — cùng nội dung dạng script.",
          "outputs/task4/Top20_can_dinh_gia_thap.xlsx — 20 căn khuyến nghị, danh sách thô, danh sách cần xác minh, báo cáo MAPE.",
          "outputs/task4/tables/model_metrics_mape_report.csv — báo cáo MAPE/RMSE/MAE/R² đầy đủ.",
          "outputs/task4/tables/king_oof_predictions.csv — giá mô hình và residual cho 21.612 giao dịch (dữ liệu cho Dashboard).",
          "outputs/task4/figures/ — 4 biểu đồ, mỗi biểu đồ có bản PNG và SVG."]:
    B(t)

out = ROOT / "reports" / "Bao_cao_Nhiem_vu_4.docx"
out.parent.mkdir(exist_ok=True)
doc.save(out)
print("Wrote", out)
