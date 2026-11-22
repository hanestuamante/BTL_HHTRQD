"""Nhiệm vụ 5: sinh hình minh họa, văn bản Phần 6 (docs/phan_6_ket_qua.txt) và file Word Phần 6 (Kết quả).

Phiên bản 2 (23/11/2026): mọi số trong văn bản được tính từ dashboard/data và outputs/task4 (không gõ tay),
diễn đạt thống nhất với feedback F05/F07/F08: "ứng viên có giá giao dịch thấp hơn dự báo, cần xác minh",
"chênh lệch so với giá dự báo" (không phải lợi nhuận/ROI).
"""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dashboard" / "data"
FIG = ROOT / "outputs" / "task5" / "figures"
REPORT = ROOT / "reports"
TXT = ROOT / "docs" / "phan_6_ket_qua.txt"
for p in (FIG, REPORT):
    p.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE, GRAY, INK, MUTED = "#2a78d6", "#eb6834", "#a3a29c", "#0b0b0b", "#52514e"
plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "savefig.facecolor": "#fcfcfb",
    "axes.edgecolor": "#d6d5cf", "axes.labelcolor": MUTED, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.titlecolor": INK, "axes.titlesize": 11,
    "axes.titleweight": "bold", "axes.labelsize": 9, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#ecebe7",
    "grid.linewidth": 0.8, "font.family": "DejaVu Sans", "font.size": 9,
    "figure.dpi": 120,
})


def savefig(fig, name):
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight", dpi=180)
    plt.close(fig)
    print("  ", name)


# ---------------------------------------------------------------- hình
sens = pd.read_csv(DATA / "sensitivity.csv")
fig, ax = plt.subplots(figsize=(7.2, 3.3))
ax.bar(sens.threshold_pct, sens.candidates, color=BLUE, width=2.6, alpha=.9)
ax.set_xlabel("Ngưỡng giá giao dịch thấp hơn dự báo (%)")
ax.set_ylabel("Số căn ứng viên")
ax2 = ax.twinx()
ax2.plot(sens.threshold_pct, sens.share_pct, color=ORANGE, marker="o", lw=1.6)
ax2.set_ylabel("Tỷ lệ trên pool (%)", color=ORANGE)
ax2.tick_params(axis="y", colors=ORANGE)
ax2.grid(False)
row = sens[sens.threshold_pct == 20].iloc[0]
ax.annotate(f"20%: {row.candidates:,.0f} căn\n({row.share_pct:.2f}%)",
            xy=(20, row.candidates), xytext=(24, row.candidates * 0.75),
            fontsize=9, color=INK,
            arrowprops=dict(arrowstyle="->", color=MUTED, lw=.8))
ax.set_title("Số ứng viên theo ngưỡng — điểm chọn 20%", loc="left")
savefig(fig, "whatif_curve")

top = pd.read_csv(DATA / "top20.csv")
fig, ax = plt.subplots(figsize=(7.4, 4.2))
t = top.sort_values("upside_usd")
colors = [ORANGE if d >= 50 else BLUE for d in t.discount_pct]
bars = ax.barh([f"#{int(h):02d} · {z}" for h, z in zip(t.Hang, t.zipcode)], t.upside_usd / 1000,
               color=colors, height=.65)
for b, v in zip(bars, t.upside_usd / 1000):
    ax.text(v + 4, b.get_y() + b.get_height() / 2, f"{v:,.0f}", va="center", fontsize=7.5)
ax.set_xlabel("Chênh lệch so với giá dự báo (nghìn USD) — không phải lợi nhuận")
ax.set_title(f"20 ứng viên cần xác minh — tổng giá lịch sử {top.price.sum():,.0f} USD", loc="left")
ax.grid(axis="y", visible=False)
savefig(fig, "top20_upside")

mc = pd.read_csv(DATA / "model_compare.csv")
mc = mc.set_index("model").loc[["Linear Regression", "Random Forest", "XGBoost"]]
fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.4), gridspec_kw={"width_ratios": [1, 1.15]})
x = range(len(mc))
w = 0.36
axes[0].bar([i - w / 2 for i in x], mc.mape_king, width=w, color=BLUE, label="King County")
axes[0].bar([i + w / 2 for i in x], mc.mape_ames, width=w, color=ORANGE, label="Ames")
axes[0].set_xticks(list(x), mc.index, fontsize=8)
axes[0].set_ylabel("MAPE (%)")
axes[0].legend(frameon=False, fontsize=8)
axes[0].set_title("Sai số theo mô hình", loc="left")
seg = pd.read_csv(DATA / "segment_compare.csv")
axes[1].plot(seg.segment, seg.mape_lr, marker="o", color=GRAY, label="Linear Regression")
axes[1].plot(seg.segment, seg.mape_xgb, marker="o", color=BLUE, label="XGBoost")
axes[1].set_ylabel("MAPE (%)")
axes[1].set_title("King County: sai số theo khúc giá", loc="left")
axes[1].legend(frameon=False, fontsize=8)
axes[1].tick_params(axis="x", labelsize=8)
savefig(fig, "model_compare")

imp = pd.read_csv(DATA / "importance_top.csv").head(10).iloc[::-1]
fig, ax = plt.subplots(figsize=(6.4, 3.4))
ax.barh(imp.feature, imp.mape_increase_pp, color=BLUE, height=.62)
ax.set_xlabel("MAPE tăng thêm khi xáo trộn biến (điểm %)")
ax.set_title("10 biến quan trọng nhất theo permutation importance", loc="left")
ax.grid(axis="y", visible=False)
savefig(fig, "importance")

# ---------------------------------------------------------------- văn bản Phần 6 (sinh từ dữ liệu)
T4 = ROOT / "outputs" / "task4" / "tables"
S4 = json.loads((T4 / "task4_summary.json").read_text(encoding="utf-8"))
TB = json.loads((T4 / "temporal_backtest.json").read_text(encoding="utf-8"))
A3 = json.loads((ROOT / "outputs" / "tables" / "analysis_summary.json").read_text(encoding="utf-8"))["datasets"]["king_county"]
D5 = json.loads((ROOT / "outputs" / "task5" / "tables" / "dashboard_data_summary.json").read_text(encoding="utf-8"))
king = pd.read_csv(DATA / "fact_king.csv", dtype={"id": "string", "zipcode": "string"})
met = pd.read_csv(DATA / "model_metrics.csv")
perm = pd.read_csv(DATA / "importance.csv")
wif = pd.read_csv(DATA / "whatif_scenarios.csv").set_index("scenario")["median_change_pct"]
stab = pd.read_csv(DATA / "stability.csv")
plan = pd.read_csv(DATA / "budget_plan.csv")

vn = lambda v, d=0: f"{v:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")
pc = lambda v, d=1: vn(v, d) + "%"


def mval(market, model, col="mape"):
    return float(met[(met.market == market) & (met.model == model)][col].iloc[0])


pool = king[(king.is_latest_sale == 1) & (king.zero_room_flag == 0) & (king.condition >= 3)]
c20 = pool[pool.residual_pct <= -0.20]
r = sens.set_index("threshold_pct")
band_counts = c20.price_band.value_counts()
zip20 = c20.zipcode.value_counts()
zip_tx = king.zipcode.value_counts()
top_zip_top20 = top.zipcode.astype(str).value_counts()
over50 = int((pool.residual_pct < -0.50).sum())


def budget(b):
    t = plan[plan.cum_price <= b]
    return len(t), t.price.sum(), t.upside_usd.sum()


B = {b: budget(b) for b in (1_000_000, 2_000_000, 5_000_000, 10_000_000)}
XG, LR, RF = "XGBoost (tuned)", "Linear Regression (baseline)", "Random Forest"
LOCKED = TB["locked_model"]["model"]
seed_rows = stab[stab.variant.str.startswith("1 seed") & stab.variant.str.contains("thận trọng")].overlap_20
usd_row = int(stab[stab.variant.str.contains("USD")].overlap_20.iloc[0])
raw_row = int(stab[stab.variant.str.contains("thô")].overlap_20.iloc[0])
top4 = perm.head(4)

thr_lines = []
for t in (5, 10, 15, 20, 25, 30):
    line = (f"Ngưỡng {t}%: {vn(r.loc[t, 'candidates'])} căn ({pc(r.loc[t, 'share_pct'], 2)} pool), "
            f"cả 3 mô hình cùng thấy {vn(r.loc[t, 'all3'])} căn")
    if t == 20:
        line += f", giá trung vị {vn(r.loc[t, 'median_price'])} USD"
    thr_lines.append(line + ".")

SECTIONS = [
    ("6.1. Mục tiêu và phạm vi", [
        "Phần 6 trình bày kết quả của dashboard Power BI cho bài toán định giá bất động sản tự động (Chủ đề 14). Dashboard "
        "kế thừa dữ liệu sạch của Nhiệm vụ 2, kết quả EDA của Nhiệm vụ 3 và mô hình của Nhiệm vụ 4. Số liệu King County lấy "
        "từ dự báo out-of-fold (OOF): mỗi giao dịch được dự báo bởi mô hình chưa fit trên tài sản đó. Lưu ý (feedback F03): "
        "bộ siêu tham số đã chọn trước trên tập train, nên OOF dùng để sàng lọc; ước lượng sai số nghiêm ngặt là nested CV "
        f"(MAPE {pc(S4['king_nested_cv']['MAPE_%'], 2)}).",
        "Dashboard gồm 6 trang: (1) Tổng quan King County, (2) What-if ngưỡng thấp hơn dự báo, (3) Ngân sách thẩm định, "
        "(4) 20 ứng viên cần xác minh, (5) Kiểm chứng bằng Ames, (6) Mô hình và độ nhạy. Trang 2 có hộp chọn ngưỡng 5%–50%, "
        "trang 3 có hộp chọn ngân sách 0,5–10 triệu USD; cả hai là tham số What-if nên đổi một giá trị là số liệu liên quan "
        "cập nhật ngay.",
        "6 trang dùng chung một mô hình dữ liệu và cùng định nghĩa ứng viên. Dashboard có dải 6 nút điều hướng ở cuối mỗi "
        "trang, hai bookmark \"Chế độ nhà đầu tư\" và \"Chế độ học thuật\", hộp chọn chỉ số ở trang Ngân sách, tooltip, "
        "alt text và thứ tự tab cho trình đọc màn hình.",
    ]),
    ("6.2. Kết quả trang Tổng quan King County", [
        f"Bộ dữ liệu sạch có {vn(A3['n'])} giao dịch của {vn(A3['n_independent'])} tài sản trong giai đoạn 05/2014–05/2015, "
        f"thuộc {A3['n_geographies']} mã ZIP. Giá giao dịch trung vị {vn(A3['median_price'])} USD, trung bình "
        f"{vn(A3['mean_price'])} USD; phân phối lệch phải mạnh (skewness {vn(A3['price_skew'], 2)}). Sau khi lọc đúng phạm vi "
        f"của Nhiệm vụ 4 (giao dịch gần nhất của mỗi tài sản, loại zero_room_flag, condition ≥ 3) còn {vn(len(pool))} tài sản.",
        "Các ZIP có nhiều giao dịch nhất: " + ", ".join(zip_tx.head(6).index) + ". Các ZIP đóng góp nhiều ứng viên nhất ở "
        "ngưỡng 20%: " + ", ".join(f"{z} ({n})" for z, n in zip20.head(6).items()) + ".",
    ]),
    ("6.3. Hai tham số What-if và kết quả theo ngưỡng", [
        "Hai tham số What-if xây theo cùng một cách: một bảng chỉ chứa dải giá trị (không sửa dữ liệu gốc), một hộp chọn để "
        "chọn đúng một giá trị, và các measure DAX đọc giá trị đang chọn rồi tính lại số liệu — không phải huấn luyện lại mô "
        "hình.",
        "Tham số thứ nhất — ngưỡng: bảng Nguong = 5%–50%, bước 1%, mặc định 20%. Một tài sản là ứng viên khi residual_pct = "
        "giá giao dịch / giá dự báo − 1 ≤ −ngưỡng, tức giá giao dịch lịch sử thấp hơn giá dự báo ít nhất bằng ngưỡng. Đây là "
        "tín hiệu cần xác minh, chưa chứng minh căn bị định giá thấp (có thể do mô hình dự báo cao, thiếu đặc điểm, giao dịch "
        "đặc biệt hoặc lỗi dữ liệu).",
        "Tham số thứ hai — ngân sách thẩm định: 0,5–10 triệu USD, bước 250.000, mặc định 2.000.000 USD. Danh sách dùng đúng quy "
        "tắc R1–R7 của 20 ứng viên (thấp hơn dự báo 20–50%, cả 3 mô hình cùng thấy, loại nhà tuổi 0), xếp theo mức thấp hơn dự "
        "báo thận trọng rồi cộng dồn giá giao dịch đến khi hết ngân sách; 20 dòng đầu trùng 20 ứng viên chính thức.",
        "Kết quả theo ngưỡng (mặc định 20%):", *thr_lines,
        f"Ở ngưỡng 20%, {vn(band_counts.get('<250k', 0))} căn ({pc(100 * band_counts.get('<250k', 0) / len(c20))}) dưới "
        f"250.000 USD và {vn(band_counts.get('250-400k', 0))} căn ({pc(100 * band_counts.get('250-400k', 0) / len(c20))}) trong "
        "khoảng 250.000–400.000 USD: ứng viên tập trung ở phân khúc giá thấp — cũng là phân khúc mô hình có MAPE cao nhất, "
        "nên một phần chênh lệch có thể chỉ là sai số mô hình.",
        f"Có {over50} tài sản thấp hơn dự báo trên 50%. Đây là đuôi bất thường (thường là giao dịch không theo thị trường "
        "hoặc lỗi dữ liệu), được tách sang danh sách xác minh dữ liệu thay vì đưa vào danh sách thẩm định.",
        f"Ngân sách 2.000.000 USD gồm {B[2_000_000][0]} căn, tổng giá lịch sử {vn(B[2_000_000][1])} USD, chênh lệch so với giá "
        f"dự báo {vn(B[2_000_000][2])} USD. 1.000.000 USD → {B[1_000_000][0]} căn; 5.000.000 USD → {B[5_000_000][0]} căn; "
        f"10.000.000 USD → {B[10_000_000][0]} căn. Chênh lệch so với giá dự báo không phải lợi nhuận: đây là giao dịch "
        "2014–2015, chưa có chi phí giao dịch, cải tạo, thuế và chưa xác nhận hiện có thể mua ở giá đó. Tham số ngân sách vì "
        "vậy dùng để quyết định bao nhiêu căn đưa đi thẩm định, không dùng để ước tính lợi nhuận (feedback F05, F08).",
    ]),
    ("6.4. Kết quả danh sách 20 ứng viên cần xác minh", [
        "Danh sách giữ đúng ràng buộc của Giám đốc đầu tư: mỗi tài sản một lần, loại căn thiếu phòng/condition thấp, loại "
        "giao dịch thấp hơn dự báo quá 50%, yêu cầu cả ba mô hình cùng cho residual ≤ −20%, xếp theo mức thấp hơn dự báo thận "
        "trọng. Ba mô hình dùng cùng dữ liệu nên đồng thuận giảm rủi ro một mô hình nhưng không phải ba bằng chứng độc lập.",
        f"Tổng giá giao dịch lịch sử của 20 căn {vn(top.price.sum())} USD; tổng giá dự báo {vn(top.predicted_price.sum())} USD; "
        f"chênh lệch so với giá dự báo {vn(top.upside_usd.sum())} USD (không phải lợi nhuận). Mức thấp hơn dự báo trung vị "
        f"{pc(top.discount_pct.median())}; {int((top.models_agree_undervalued == 3).sum())}/20 căn được cả ba mô hình cùng thấy. "
        f"20 căn nằm ở {top.zipcode.nunique()} mã ZIP, nhiều nhất " + ", ".join(
            f"{z} ({n})" for z, n in top_zip_top20.head(4).items()) + f"; trung vị diện tích {vn(top.sqft_living.median())} sqft, "
        f"grade {vn(top.grade.median())}, cách điểm đại diện trung tâm Seattle {vn(top.distance_to_center_km.median(), 1)} km.",
    ]),
    ("6.5. Kết quả kiểm chứng bằng Ames", [
        f"Ames là thị trường kiểm chứng, không dùng để chọn 20 căn. Trên {vn(D5['ames_rows'])} tài sản (2006–2010), XGBoost đạt "
        f"MAPE {pc(mval('Ames', 'XGBoost'), 2)} và R² {vn(mval('Ames', 'XGBoost', 'r2'), 3)} trên tập test (điền thiếu học trên "
        f"train — feedback F01), so với King County MAPE {pc(mval('King County', XG), 2)}, R² {vn(mval('King County', XG, 'r2'), 3)}. "
        f"OOF trên toàn bộ Ames có MAPE {pc(D5['ames_oof_mape_pct'], 2)}; cùng ngưỡng 20% có {D5['ames_undervalued_20pct']} tài sản "
        "là ứng viên. Chênh lệch chủ yếu do Ames đồng nhất hơn và ít giao dịch cực đoan, không phải do mô hình tốt hơn về bản chất.",
    ]),
    ("6.6. Chất lượng mô hình và độ nhạy", [
        f"Trên tập test King County (mô hình chọn bằng CV trên train, test chỉ chấm cuối), XGBoost đạt MAPE "
        f"{pc(mval('King County', XG), 2)}, RMSE {vn(mval('King County', XG, 'rmse'))} USD, R² {vn(mval('King County', XG, 'r2'), 3)}; "
        f"Linear Regression {pc(mval('King County', LR), 2)}, Random Forest {pc(mval('King County', RF), 2)}; mốc thô đơn giá "
        f"ZIP × diện tích {pc(mval('King County', 'Mốc thô: đơn giá zipcode × diện tích'), 2)}. Backtest thời gian độc lập "
        f"(tương lai từ {TB['cutoff'][8:]}/{TB['cutoff'][5:7]}/{TB['cutoff'][:4]} tách trước, tinh chỉnh chỉ trên quá khứ): "
        f"{LOCKED} MAPE {pc(mval('King County (backtest thời gian)', LOCKED), 2)} — mức sai số nên dùng cho giao dịch mới.",
        f"Permutation importance: {top4.feature.iloc[0]} quan trọng nhất (MAPE tăng {vn(top4.mape_increase_pp.iloc[0], 2)} điểm % "
        f"khi xáo trộn), sau đó {top4.feature.iloc[1]} ({vn(top4.mape_increase_pp.iloc[1], 2)}), {top4.feature.iloc[2]} "
        f"({vn(top4.mape_increase_pp.iloc[2], 2)}) và {top4.feature.iloc[3]} ({vn(top4.mape_increase_pp.iloc[3], 2)}). What-if "
        "một biến (phản ứng của mô hình, không phải tác động nhân quả của cải tạo — F07): đặt về trạng thái vừa cải tạo "
        f"{pc(wif['Đặt về trạng thái vừa cải tạo (years_since_update = 0)'], 2)}, grade +1 {pc(wif['Grade (chất lượng xây) +1'], 2)}, "
        f"view +1 {pc(wif['View +1 bậc'], 2)}, condition +1 {pc(wif['Condition (tình trạng) +1'], 2)}, diện tích trên mặt đất +10% "
        f"{pc(wif['Diện tích trên mặt đất +10% (hầm giữ nguyên)'], 2)} (giữ sqft_living = trên mặt đất + hầm — F06); tuổi nhà +10 năm "
        f"{pc(wif['Tuổi nhà +10 năm'], 2)}.",
        f"Độ ổn định của danh sách 20 căn: đổi seed chia fold giữ {seed_rows.min()}–{seed_rows.max()}/20 căn; "
        f"{S4['top20_core_all_seed_variants']} căn có mặt ở cả {S4['seed_variants_counted']} biến thể seed × cách xếp hạng; xếp "
        f"theo chênh lệch USD chỉ giữ {usd_row}/20; danh sách thô không lọc bất thường trùng {raw_row}/20. Danh sách phụ thuộc "
        "mục tiêu xếp hạng; bảng tần suất xuất hiện là cơ sở để nói về nhóm lõi.",
    ]),
    ("6.7. Khuyến nghị và giới hạn", [
        f"Đề xuất giữ ngưỡng 20% làm mặc định: còn {vn(r.loc[20, 'candidates'])} ứng viên ({pc(r.loc[20, 'share_pct'], 2)}), đủ "
        f"để lọc ra 20 căn sau các quy tắc R4–R6 ({vn(S4['recommended_pool_size'])} căn đạt). Ngưỡng 10% quá rộng "
        f"({vn(r.loc[10, 'candidates'])} căn), ngưỡng 30% còn {vn(r.loc[30, 'candidates'])} căn. Ngưỡng là quy tắc nhóm đặt, "
        "chưa hiệu chỉnh bằng kết quả thẩm định thực tế.",
        "Giới hạn cần giữ khi trình bày: (1) ứng viên dựa trên residual mô hình, cần xác minh, không chứng minh nhà bị định giá "
        "thấp; (2) chênh lệch so với giá dự báo không phải lợi nhuận; (3) quan hệ là tương quan, what-if không phải nhân quả; "
        "(4) Ames chỉ để kiểm chứng; (5) dữ liệu lịch sử 2014–2015 và 2006–2010; (6) khi dự báo giao dịch mới dùng luồng "
        "bds_valuation.predict (tạo biến + kiểm tra schema) và tham chiếu sai số backtest thời gian.",
    ]),
    ("6.8. Kết luận", [
        "Dashboard trả lời câu hỏi quyết định của Giám đốc đầu tư ở mức sàng lọc: 20 ứng viên có giá giao dịch thấp hơn dự báo "
        f"(tổng giá lịch sử {vn(top.price.sum())} USD), tập trung ở các ZIP " + ", ".join(top_zip_top20.head(3).index) + ", được "
        "đưa vào thẩm định theo thứ tự. Tham số What-if giúp điều chỉnh ngưỡng và ngân sách thẩm định theo khẩu vị rủi ro mà "
        "không cần chạy lại mô hình.",
    ]),
]
TXT.write_text("PHẦN 6. KẾT QUẢ\n\n" + "\n\n".join(h + "\n" + "\n\n".join(b) for h, b in SECTIONS) + "\n",
               encoding="utf-8")
sections = SECTIONS
doc = Document()
st = doc.styles["Normal"]
st.font.name = "Times New Roman"
st.font.size = Pt(12)
for section in doc.sections:
    section.left_margin = section.right_margin = Cm(2.3)
    section.top_margin = section.bottom_margin = Cm(2.0)

title = doc.add_heading("PHẦN 6. KẾT QUẢ", 0)
for r in title.runs:
    r.font.name = "Times New Roman"
    r.font.color.rgb = RGBColor(0x0b, 0x0b, 0x0b)


def add_para(t):
    p = doc.add_paragraph(t)
    p.paragraph_format.space_after = Pt(6)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def add_picture(name, caption):
    doc.add_picture(str(FIG / name), width=Cm(15.5))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    c = doc.add_paragraph(caption)
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.runs[0].italic = True
    c.runs[0].font.size = Pt(10)


def add_table(df, caption):
    c = doc.add_paragraph(caption)
    c.runs[0].bold = True
    c.runs[0].font.size = Pt(10.5)
    table = doc.add_table(rows=1, cols=len(df.columns))
    table.style = "Light Grid Accent 1"
    for i, col in enumerate(df.columns):
        table.rows[0].cells[i].text = str(col)
    for _, row in df.iterrows():
        cells = table.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)
    for r in table.rows:
        for cell in r.cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(9.5)
    doc.add_paragraph()


# Ảnh trang dashboard chụp từ Power BI Desktop. dashboard/pbix_data_sha256.txt ghi SHA256 của fact_king.csv mà file .pbix
# đang chứa; khác với dữ liệu hiện tại nghĩa là .pbix/ảnh chưa được refresh. Sau khi Refresh + lưu .pbix + chụp lại ảnh,
# chạy: python scripts/build_task5_report.py --pbix-refreshed
import hashlib
import sys
MARK = ROOT / "dashboard" / "pbix_data_sha256.txt"
CUR = hashlib.sha256((DATA / "fact_king.csv").read_bytes()).hexdigest()
if "--pbix-refreshed" in sys.argv:
    MARK.write_text(CUR + "\n")
PBI_STALE = not MARK.exists() or MARK.read_text().strip() != CUR
WHATIF_COLS = {"Ngưỡng": "Ngưỡng (%)", "Số căn": "Số căn", "Tỷ lệ": "Tỷ lệ (%)",
               "Đồng thuận": "Cả 3 mô hình", "Giá trung vị": "Giá trung vị (USD)"}

for head, body in sections:
    doc.add_heading(head, 1)
    for para in body:
        add_para(para)
    if head.startswith("6.2"):
        add_picture("dashboard_page1.png", "Hình 6.1. Trang Tổng quan King County trên dashboard.")
    elif head.startswith("6.3"):
        df = sens[sens.threshold_pct.isin([5, 10, 15, 20, 25, 30])].copy()
        df = pd.DataFrame({
            "Ngưỡng (%)": df.threshold_pct.astype(int),
            "Số căn": df.candidates.map(lambda v: f"{v:,.0f}"),
            "Tỷ lệ (%)": df.share_pct.map(lambda v: f"{v:.2f}"),
            "Cả 3 mô hình": df.all3.map(lambda v: f"{v:,.0f}"),
            "Giá trung vị (USD)": df.median_price.map(lambda v: f"{v:,.0f}"),
        })
        add_table(df, "Bảng 6.1. Kết quả tham số What-if theo ngưỡng (giao dịch gần nhất của mỗi tài sản, sau R1–R3)")
        add_picture("whatif_curve.png", "Hình 6.2. Số ứng viên và tỷ lệ theo ngưỡng.")
        add_picture("dashboard_page2.png", "Hình 6.3. Trang What-if với hộp chọn ngưỡng 5%–50%.")
        add_picture("dashboard_page3.png", "Hình 6.4. Trang Ngân sách thẩm định: what-if thứ hai (ngân sách).")
        if PBI_STALE:
            add_para("Ghi chú: Hình 6.1, 6.3, 6.4 là ảnh chụp file .pbix trước khi chạy lại Nhiệm vụ 4 ngày 23/11/2026; số "
                     "trên ảnh lệch nhẹ so với văn bản và ảnh còn nhãn cũ (ROI, undervalued) đã được đổi trong .pbip. Số chính thức là số "
                     "trong văn bản và Bảng 6.1. Mở "
                     "dashboard/BTL_NhiemVu5.pbip → Refresh → lưu .pbix và xuất lại ảnh để cập nhật.")
    elif head.startswith("6.4"):
        add_picture("top20_upside.png", "Hình 6.5. Chênh lệch so với giá dự báo của 20 ứng viên (không phải lợi nhuận).")
    elif head.startswith("6.5"):
        add_picture("model_compare.png", "Hình 6.6. So sánh MAPE King County và Ames; sai số theo khúc giá.")
    elif head.startswith("6.6"):
        add_picture("importance.png", "Hình 6.7. Các biến quan trọng nhất của mô hình.")

doc.core_properties.title = "Phần 6 - Kết quả dashboard định giá bất động sản"
out = REPORT / "Bao_cao_Nhiem_vu_5.docx"
doc.save(out)
print("Đã tạo:", out)
