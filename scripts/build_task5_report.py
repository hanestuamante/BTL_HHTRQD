"""Nhiệm vụ 5: sinh hình minh họa và file Word phần 6 (Kết quả)."""
from pathlib import Path
import re

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
ax.set_xlabel("Ngưỡng undervalued (%)")
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
ax.set_xlabel("Chênh lệch kỳ vọng (nghìn USD)")
ax.set_title(f"20 căn đề xuất — vốn {top.price.sum():,.0f} USD, "
             f"chênh lệch {top.upside_usd.sum():,.0f} USD", loc="left")
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

# ---------------------------------------------------------------- Word
text = TXT.read_text(encoding="utf-8")
chunks = re.split(r"\n(?=6\.\d+\. )", text)
sections = []
for chunk in chunks:
    lines = [l.strip() for l in chunk.strip().split("\n") if l.strip()]
    if not lines:
        continue
    head, body = lines[0], lines[1:]
    sections.append((head, body))

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
        add_table(df, "Bảng 6.1. Kết quả tham số What-if theo ngưỡng")
        add_picture("whatif_curve.png", "Hình 6.2. Số ứng viên và tỷ lệ theo ngưỡng.")
        add_picture("dashboard_page2.png", "Hình 6.3. Trang What-if với hộp chọn ngưỡng 5%–50%.")
        add_picture("dashboard_page3.png",
                    "Hình 6.4. Trang Ngân sách: what-if thứ hai, ngân sách 2.000.000 USD mua được "
                    "8 căn (dùng 90,5% ngân sách, ROI kỳ vọng 97,2%).")
    elif head.startswith("6.4"):
        add_picture("top20_upside.png", "Hình 6.5. Chênh lệch kỳ vọng của 20 căn đề xuất.")
    elif head.startswith("6.5"):
        add_picture("model_compare.png", "Hình 6.6. So sánh MAPE King County và Ames; sai số theo khúc giá.")
    elif head.startswith("6.6"):
        add_picture("importance.png", "Hình 6.7. Các biến quan trọng nhất của mô hình.")

doc.core_properties.title = "Phần 6 - Kết quả dashboard định giá bất động sản"
out = REPORT / "Bao_cao_Nhiem_vu_5.docx"
doc.save(out)
print("Đã tạo:", out)
