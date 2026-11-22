"""Nhiệm vụ 6: tạo slide thuyết trình (.pptx, mở/nhập được vào PowerPoint, Canva, Google Slides).

    python scripts/build_slides.py   # -> slides/Chu_de_14_thuyet_trinh.pptx

Số liệu đọc từ outputs/ và metadata/; biểu đồ số dùng chart gốc của PowerPoint (sửa được), hình phân tích lấy từ
outputs/*/figures. Mỗi slide có ghi chú lời dẫn và người trình bày (TV1–TV6) cho video ~10 phút.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_TICK_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
T3, F3 = ROOT / "outputs" / "tables", ROOT / "outputs" / "figures"
T4, F4 = ROOT / "outputs" / "task4" / "tables", ROOT / "outputs" / "task4" / "figures"
SHOT = ROOT / "dashboard" / "screenshots" / "dashboard_nguong_20.png"
OUT = ROOT / "slides" / "Chu_de_14_thuyet_trinh.pptx"

NAVY, INK, MUTED, LIGHT, WHITE = "16324F", "1B1F24", "5B6470", "EEF2F6", "FFFFFF"
ORANGE, TEAL = "E4572E", "2A9D8F"
FONT_H, FONT_B = "Cambria", "Calibri"

S4 = json.loads((T4 / "task4_summary.json").read_text(encoding="utf-8"))
TB = json.loads((T4 / "temporal_backtest.json").read_text(encoding="utf-8"))
A3 = json.loads((T3 / "analysis_summary.json").read_text(encoding="utf-8"))["datasets"]
MET = pd.read_csv(T4 / "model_metrics_mape_report.csv")
THR = pd.read_csv(T4 / "sensitivity_threshold.csv").set_index("Nguong_%")
WIF = pd.read_csv(T4 / "sensitivity_whatif.csv")
TOP = pd.read_csv(T4 / "top20_candidates_below_prediction_king.csv", dtype={"id": str, "zipcode": str})
STAB = pd.read_csv(T4 / "sensitivity_top20_stability.csv")
DICT_N = len(pd.read_csv(ROOT / "dictionaries" / "data_dictionary.csv"))
BEST, LOCKED = S4["best_model"], TB["locked_model"]["model"]

vn = lambda v, d=0: f"{v:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")
pct = lambda v: vn(v, 1) + "%"


def mm(market, model):
    return float(MET[(MET["Thi_truong"] == market) & (MET["Mo_hinh"] == model)]["MAPE_%"].iloc[0])


def rgb(h):
    return RGBColor.from_string(h)


prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
W, H = prs.slide_width, prs.slide_height


def bg(slide, color):
    f = slide.background.fill; f.solid(); f.fore_color.rgb = rgb(color)


def text(slide, x, y, w, h, runs, size=16, color=INK, font=FONT_B, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, name=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    paras = runs if isinstance(runs, list) else [runs]
    for i, ptxt in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(6)
        r = p.add_run(); r.text = ptxt
        r.font.size = Pt(size); r.font.color.rgb = rgb(color); r.font.name = font; r.font.bold = bold
    return tb


def bullets(slide, x, y, w, h, items, size=16, color=INK):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(10)
        pPr = p._p.get_or_add_pPr()
        pPr.set("marL", str(Emu(Inches(0.28)))); pPr.set("indent", str(-Emu(Inches(0.28))))
        bu = pPr.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}buChar", {"char": "•"})
        pPr.append(bu)
        if isinstance(it, tuple):
            r = p.add_run(); r.text = it[0]; r.font.bold = True
            r.font.size = Pt(size); r.font.color.rgb = rgb(color); r.font.name = FONT_B
            it = it[1]
        r = p.add_run(); r.text = it
        r.font.size = Pt(size); r.font.color.rgb = rgb(color); r.font.name = FONT_B
    return tb


def title(slide, t, sub=None, dark=False):
    text(slide, 0.6, 0.45, 12.1, 0.8, t, size=30, bold=True, font=FONT_H, color=WHITE if dark else NAVY, name="Title")
    if sub:
        text(slide, 0.6, 1.25, 12.1, 0.5, sub, size=16, color=("C9D6E3" if dark else MUTED))


def card(slide, x, y, w, h, fill=LIGHT):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = 0.08
    s.fill.solid(); s.fill.fore_color.rgb = rgb(fill); s.line.fill.background(); s.shadow.inherit = False
    return s


def stat(slide, x, y, w, value, label, color=NAVY, fill=LIGHT, h=1.6):
    card(slide, x, y, w, h, fill)
    text(slide, x + 0.25, y + 0.2, w - 0.5, 0.8, value, size=34, bold=True, color=color, font=FONT_H)
    text(slide, x + 0.25, y + 0.98, w - 0.5, h - 1.05, label, size=13, color=MUTED)


def badge(slide, x, y, n, color=ORANGE):
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(0.55), Inches(0.55))
    s.fill.solid(); s.fill.fore_color.rgb = rgb(color); s.line.fill.background()
    tf = s.text_frame; tf.margin_left = tf.margin_right = 0
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = str(n); r.font.size = Pt(16); r.font.bold = True; r.font.color.rgb = rgb(WHITE)


def picture(slide, path, x, y, w=None, h=None, alt=""):
    if not Path(path).exists():
        text(slide, x, y, w or 4, 0.5, f"[Thiếu hình {Path(path).name}]", size=12, color=MUTED)
        return None
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    pic._element.nvPicPr.cNvPr.set("descr", alt)
    return pic


def presenter(slide, who):
    text(slide, 10.3, 7.0, 2.6, 0.3, who, size=10, color=MUTED, align=PP_ALIGN.RIGHT)


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


def bar_chart(slide, x, y, w, h, cats, vals, highlight=None, number_format='0.0"%"', title_txt=None, colors=None):
    cd = CategoryChartData(); cd.categories = cats; cd.add_series("MAPE", vals)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart; ch.has_legend = False
    ch.font.size = Pt(12); ch.font.name = FONT_B; ch.font.color.rgb = rgb(INK)
    if title_txt:
        ch.has_title = True; ch.chart_title.text_frame.text = title_txt
        ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(13)
    else:
        ch.has_title = False
    plot = ch.plots[0]; plot.gap_width = 60; plot.has_data_labels = True
    dl = plot.data_labels; dl.number_format = number_format; dl.number_format_is_linked = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END; dl.font.size = Pt(12)
    va = ch.value_axis; va.has_major_gridlines = False; va.visible = False
    ca = ch.category_axis; ca.reverse_order = True; ca.format.line.color.rgb = rgb("C8CED6")
    ca.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    plot.series[0].invert_if_negative = False
    ca.tick_labels.font.size = Pt(12)
    for i, pt in enumerate(plot.series[0].points):
        pt.format.fill.solid()
        c = (colors[i] if colors else (ORANGE if highlight is not None and i == highlight else "9AA5B1"))
        pt.format.fill.fore_color.rgb = rgb(c)
    # PowerPoint mặc định đảo màu thanh âm thành trắng ở từng điểm dữ liệu; tắt rõ ở mỗi <c:dPt>.
    from pptx.oxml.ns import qn as _qn
    for dpt in plot.series[0]._element.findall(_qn("c:dPt")):
        if dpt.find(_qn("c:invertIfNegative")) is None:
            inv = dpt.makeelement(_qn("c:invertIfNegative"), {"val": "0"})
            dpt.find(_qn("c:idx")).addnext(inv)
    return ch


# 1 ----------------------------------------------------------------- tiêu đề
s = prs.slides.add_slide(BLANK); bg(s, NAVY)
text(s, 0.8, 2.0, 11.5, 0.5, "HỆ HỖ TRỢ RA QUYẾT ĐỊNH · CHỦ ĐỀ 14", size=16, color="9FB7CF", bold=True)
text(s, 0.8, 2.6, 11.5, 1.8, "Mô hình định giá bất động sản tự động", size=44, color=WHITE, bold=True, font=FONT_H)
text(s, 0.8, 4.6, 11.5, 0.9, "Từ dữ liệu giao dịch King County đến danh sách 20 căn ưu tiên thẩm định cho Giám đốc đầu tư",
     size=20, color="C9D6E3")
text(s, 0.8, 6.3, 11.5, 0.5, "Nhóm 261HHTQD_Nhom__ · TV1–TV6", size=14, color="9FB7CF")
notes(s, "TV6 mở đầu (20 giây): giới thiệu nhóm, chủ đề, và câu hỏi quyết định sẽ trả lời ở cuối bài.")

# 2 ----------------------------------------------------------------- vấn đề & câu hỏi
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Câu hỏi quyết định: 20 căn nào nên thẩm định trước?")
naive = mm("King County", "Mốc thô: đơn giá zipcode × diện tích")
stat(s, 0.6, 1.95, 4.0, pct(naive), "MAPE của cách định giá thủ công 'đơn giá zipcode × diện tích' trên tập test", color=ORANGE, h=1.9)
text(s, 0.6, 4.1, 4.0, 2.6, ["Sai số thủ công gần bằng chính ngưỡng 20% dùng để gọi một căn là 'rẻ' — cần quy trình định giá "
                             "tự động, nhất quán, kiểm chứng được."], size=15, color=INK)
layers = [("Lớp 1 · Vấn đề kinh doanh", "Thay định giá thủ công bằng quy trình tự động?"),
          ("Lớp 2 · Mô tả & chẩn đoán", "Giá phân bố ra sao; nhóm giá thấp khác gì?"),
          ("Lớp 3 · Dự báo", "Dự báo giá với sai số bao nhiêu, có giữ được với giao dịch tương lai?"),
          ("Lớp 4 · Quyết định", "Chọn 20 căn nào, danh sách nhạy thế nào?")]
for i, (h_, d_) in enumerate(layers):
    y = 1.95 + i * 1.22
    badge(s, 5.2, y + 0.15, i + 1, ORANGE if i == 3 else NAVY)
    text(s, 6.0, y + 0.05, 6.8, 0.45, h_, size=18, bold=True, color=NAVY)
    text(s, 6.0, y + 0.52, 6.8, 0.5, d_, size=15, color=MUTED)
presenter(s, "TV1")
notes(s, "TV1 (60–75 giây): vấn đề kinh doanh, câu hỏi quyết định, chuỗi 4 lớp câu hỏi. Bảng câu hỏi S 6 cột ở Phần 2 báo cáo.")

# 3 ----------------------------------------------------------------- KPI
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "KPI và ràng buộc", "Ngưỡng do nhóm đặt trước khi xem kết quả — giả định quản trị, không phải số liệu")
for i, (k, d_, tgt) in enumerate([("KPI1 · MAPE", "Sai số % trung bình trên giao dịch mô hình chưa thấy", "≤ 12%, thấp hơn baseline và mốc thủ công"),
                                   ("KPI2 · Tỷ lệ ứng viên", "Căn có giá giao dịch thấp hơn dự báo ≥ 20%", "2–10% số căn trong pool"),
                                   ("KPI3 · Độ ổn định", "Số căn top 20 giữ được khi đổi seed chia fold", "≥ 15/20 ở mọi seed")]):
    x = 0.6 + i * 4.1
    card(s, x, 2.0, 3.8, 3.0)
    text(s, x + 0.3, 2.25, 3.2, 0.5, k, size=20, bold=True, color=NAVY, font=FONT_H)
    text(s, x + 0.3, 2.9, 3.2, 1.0, d_, size=15, color=INK)
    text(s, x + 0.3, 4.05, 3.2, 0.8, "Mục tiêu: " + tgt, size=14, color=ORANGE, bold=True)
bullets(s, 0.6, 5.4, 12.1, 1.6, [("Ràng buộc: ", "đúng 20 căn, không trùng tài sản, không dùng biến chứa giá làm đầu vào."),
                                 ("Diễn giải: ", "residual âm = tín hiệu cần xác minh, không phải bằng chứng bị định giá thấp.")], size=15)
presenter(s, "TV1")
notes(s, "TV1 (40 giây): ba KPI và vì sao chọn; nhấn mạnh ngưỡng là giả định, kết quả đối chiếu ở slide KPI cuối.")

# 4 ----------------------------------------------------------------- dữ liệu
k, a = A3["king_county"], A3["ames"]
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Dữ liệu: hai thị trường, phân tích riêng", "King County 2014–2015 là thị trường chính; Ames 2006–2010 để kiểm chứng")
stat(s, 0.6, 1.95, 2.9, vn(k["n"]), "giao dịch King County sạch")
stat(s, 3.7, 1.95, 2.9, vn(k["n_independent"]), "tài sản King County (bán lại được tách)")
stat(s, 6.8, 1.95, 2.9, vn(a["n"]), "căn Ames")
stat(s, 9.9, 1.95, 2.85, vn(DICT_N), "trường trong từ điển dữ liệu")
for i, (h_, d_) in enumerate([("Extract", "Tải nguồn công khai, lưu SHA256"), ("Transform", "Missing, ngoại lệ, cách ly có lý do"),
                              ("Tạo biến", "price_per_sqft, house_age, Haversine"), ("Load & kiểm tra", "CSV đúng kiểu, assert, audit")]):
    x = 0.6 + i * 3.1
    badge(s, x, 4.15, i + 1, TEAL)
    text(s, x + 0.7, 4.15, 2.3, 0.45, h_, size=17, bold=True, color=NAVY)
    text(s, x + 0.7, 4.62, 2.3, 0.9, d_, size=14, color=MUTED)
text(s, 0.6, 5.9, 12.1, 0.9, "Ames gốc không có tọa độ: không tự gán khoảng cách. Khi mô hình hóa, điền thiếu học từ dữ liệu "
     "được làm lại bên trong Pipeline trên train (sửa theo feedback F01).", size=14, color=INK)
presenter(s, "TV2")
notes(s, "TV2 (60 giây): nguồn, ETL 4 bước, biến mới. Nhắc: CSV sạch phục vụ EDA; mô hình fit lại tiền xử lý trên train.")

# 5 ----------------------------------------------------------------- EDA
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Giá lệch phải và phân hóa mạnh theo zipcode")
picture(s, F3 / "king_county_geographic_boxplot.png", 0.6, 1.5, w=7.9, alt="Boxplot giá theo zipcode King County")
stat(s, 8.9, 1.5, 3.85, vn(k["median_price"]) + " $", "giá trung vị King County", h=1.5)
stat(s, 8.9, 3.2, 3.85, vn(k["price_skew"], 2), "độ lệch (skewness) của giá → dùng trung vị, mô hình học log(giá)", h=1.7)
text(s, 8.9, 5.15, 3.85, 1.6, f"{k['n_geographies']} zipcode King và {a['n_geographies']} neighborhood Ames; vị trí là yếu tố "
     "phân hóa giá rõ nhất.", size=14)
presenter(s, "TV3")
notes(s, "TV3 (45 giây): đọc boxplot — hộp Q1–Q3, trung vị; giá chênh nhiều lần giữa các zipcode.")

# 6 ----------------------------------------------------------------- chẩn đoán
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Nhóm giá thấp: nhà nhỏ hơn, chất lượng thấp hơn", "Nhóm giá < 80% trung vị — giá thấp không đồng nghĩa bị định giá thấp")
picture(s, F3 / "king_county_group_comparison.png", 0.6, 1.9, w=7.6, alt="So sánh nhóm giá thấp và nhóm còn lại")
stat(s, 8.6, 1.9, 4.15, pct(100 * k["share_low"]), f"giao dịch King County thuộc nhóm giá thấp ({vn(k['n_low'])} giao dịch)", h=1.7)
stat(s, 8.6, 3.8, 4.15, pct(100 * a["share_low"]), f"căn Ames thuộc nhóm giá thấp ({vn(a['n_low'])} căn)", h=1.7)
text(s, 8.6, 5.75, 4.15, 1.2, "Welch t-test có CI95%, Hedges g, hiệu chỉnh Holm; Spearman một phía kiểm chiều quan hệ đặt trước.", size=13, color=MUTED)
presenter(s, "TV3")
notes(s, "TV3 (60 giây): chênh lệch diện tích và chất lượng giữa hai nhóm (bảng welch_tests.csv); tương quan không phải nhân quả.")

# 7 ----------------------------------------------------------------- quy trình mô hình
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Quy trình mô hình: chọn trước, chấm sau", "Mỗi bước đánh giá dùng dữ liệu mà mô hình chưa thấy")
steps = [("Chia theo tài sản", "80/20 theo id; một căn bán nhiều lần chỉ nằm một phía"),
         ("Tinh chỉnh + chọn bằng CV trên train", f"LR, RF, XGBoost từ cùng một registry → chọn {BEST}"),
         ("Chấm tập test một lần", "Tập test không tham gia chọn gì"),
         ("Backtest thời gian", f"Tương lai từ {TB['cutoff'][8:10]}/{TB['cutoff'][5:7]}/{TB['cutoff'][:4]} tách trước; tinh chỉnh chỉ trên quá khứ"),
         ("Nested CV 5×3", "Tinh chỉnh và chọn mô hình lặp lại trong từng fold")]
for i, (h_, d_) in enumerate(steps):
    y = 1.95 + i * 1.0
    badge(s, 0.6, y, i + 1, NAVY)
    text(s, 1.4, y - 0.02, 5.2, 0.45, h_, size=17, bold=True, color=NAVY)
    text(s, 1.4, y + 0.42, 5.4, 0.5, d_, size=13, color=MUTED)
card(s, 7.3, 1.95, 5.45, 4.85)
bullets(s, 7.6, 2.2, 4.9, 4.4, [("Mục tiêu: ", "log(giá), đổi ngược về USD để tính MAPE/RMSE."),
                                ("Chống rò rỉ: ", "loại price_per_sqft và cờ ngoại lệ theo giá khỏi đầu vào."),
                                ("Đã sửa theo feedback: ", "nhánh chọn mô hình (F04), tuning độc lập thời gian (F02), nested CV (F03)."),
                                ("Kiểm thử: ", "pytest cho chia tập, registry, what-if, quy tắc chọn, API dự báo.")], size=14)
presenter(s, "TV4")
notes(s, "TV4 (60 giây): giải thích vì sao chia theo tài sản và vì sao có ba cách đánh giá; nested CV là ước lượng nghiêm ngặt nhất.")

# 8 ----------------------------------------------------------------- MAPE
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
mt = mm("King County", BEST)
title(s, f"{BEST}: MAPE {pct(mt)} so với {pct(naive)} thủ công")
cats = ["Mốc thủ công", "Linear Regression", "Random Forest", "XGBoost"]
vals = [naive, mm("King County", "Linear Regression (baseline)"), mm("King County", "Random Forest"), mm("King County", "XGBoost (tuned)")]
order = {"Linear Regression (baseline)": 1, "Random Forest": 2, "XGBoost (tuned)": 3}
bar_chart(s, 0.6, 1.6, 7.3, 4.9, cats, [round(v, 2) for v in vals], highlight=order[BEST], title_txt="MAPE trên tập test King County (%)")
stat(s, 8.4, 1.6, 4.35, pct(S4["king_nested_cv"]["MAPE_%"]), "MAPE nested CV — ước lượng nghiêm ngặt cả quy trình", h=1.55)
stat(s, 8.4, 3.3, 4.35, pct(mm("King County (backtest thời gian)", LOCKED)), f"MAPE backtest thời gian ({LOCKED}) — dùng cho giao dịch mới", color=ORANGE, h=1.55)
stat(s, 8.4, 5.0, 4.35, pct(mm("Ames", "XGBoost")), "MAPE Ames (XGBoost), điền thiếu học trên train", h=1.5)
presenter(s, "TV4")
notes(s, "TV4 (60 giây): so sánh mô hình; sai số tăng khi dự báo tương lai; RMSE lớn do nhà đắt; MAPE là thước đo chính.")

# 9 ----------------------------------------------------------------- what-if
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Độ nhạy: chất lượng và diện tích chi phối", "Phản ứng của mô hình khi thay đầu vào — không phải tác động nhân quả của cải tạo")
w9 = WIF.sort_values("Trung_vi_thay_doi_%", ascending=False)
short = {"Diện tích trên mặt đất +10% (hầm giữ nguyên)": "Diện tích trên mặt đất +10%",
         "Tổng diện tích ở +10% (trên mặt đất và hầm cùng tỷ lệ)": "Tổng diện tích +10%",
         "Đặt về trạng thái vừa cải tạo (years_since_update = 0)": "Như vừa cải tạo",
         "Grade (chất lượng xây) +1": "Grade +1", "Condition (tình trạng) +1": "Condition +1",
         "Thêm 1 phòng tắm (cùng diện tích)": "Thêm 1 phòng tắm", "Thêm 1 phòng ngủ (cùng diện tích)": "Thêm 1 phòng ngủ"}
cats = [short.get(c, c) for c in w9["Kich_ban"]]
vals = [round(v, 2) for v in w9["Trung_vi_thay_doi_%"]]
bar_chart(s, 0.6, 1.8, 7.6, 5.2, cats, vals, number_format='+0.0"%";-0.0"%"',
          colors=[TEAL if v >= 0 else ORANGE for v in vals], title_txt="Trung vị % thay đổi giá dự báo")
card(s, 8.6, 1.8, 4.15, 5.2)
bullets(s, 8.85, 2.05, 3.7, 4.8, [("Giữ quan hệ diện tích: ", "sqft_living = trên mặt đất + hầm (sửa F06)."),
                                  ("Ngoài miền dữ liệu: ", "'+6 tháng' vượt khoảng thời gian huấn luyện → không dùng dự báo tương lai."),
                                  ("Dùng để: ", "đặt giả thuyết khảo sát, chưa có chi phí và bằng chứng nhân quả (F07).")], size=14)
presenter(s, "TV4")
notes(s, "TV4 (45 giây): đọc 2–3 kịch bản; nhấn mạnh không suy ra lợi nhuận cải tạo.")

# 10 ---------------------------------------------------------------- 20 ứng viên
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "20 ứng viên giá thấp hơn dự báo, cần xác minh")
picture(s, F4 / "king_residuals_and_candidates_map.png", 0.6, 1.5, w=6.6, alt="Phân phối residual và bản đồ 20 ứng viên")
rows = TOP.head(10)
tbl = s.shapes.add_table(len(rows) + 1, 5, Inches(7.5), Inches(1.45), Inches(5.25), Inches(4.3)).table
for j, hdr in enumerate(["#", "Zip", "Giá GD ($)", "Dự báo ($)", "Thấp hơn*"]):
    tbl.cell(0, j).text = hdr
for i, r in enumerate(rows.itertuples(), start=1):
    for j, v in enumerate([r.Hang, r.zipcode, vn(r.price), vn(r.predicted_price), pct(r.below_prediction_conservative_pct)]):
        tbl.cell(i, j).text = str(v)
for i in range(len(rows) + 1):
    for j in range(5):
        c = tbl.cell(i, j); c.margin_top = c.margin_bottom = Inches(0.03)
        for p in c.text_frame.paragraphs:
            for run in p.runs:
                run.font.size = Pt(12); run.font.name = FONT_B
                run.font.bold = i == 0; run.font.color.rgb = rgb(WHITE if i == 0 else INK)
        c.fill.solid(); c.fill.fore_color.rgb = rgb(NAVY if i == 0 else (LIGHT if i % 2 else WHITE))
text(s, 7.5, 5.85, 5.25, 0.4, "10/20 căn đầu · *mức thấp hơn thận trọng (ít âm nhất trong 3 mô hình)", size=11, color=MUTED)
text(s, 0.6, 6.25, 12.1, 0.9, f"Tổng giá giao dịch lịch sử {vn(S4['top20_total_historical_price_usd'])} $; tổng giá dự báo "
     f"{vn(S4['top20_total_predicted_usd'])} $. Chênh lệch không phải lợi nhuận — giao dịch 2014–2015, chưa xác minh điều kiện bán.",
     size=14, color=INK)
presenter(s, "TV4")
notes(s, "TV4 (60 giây): quy tắc R1–R7; vì sao loại căn thấp hơn >50%; danh sách là để thẩm định, không phải để mua ngay (F05).")

# 11 ---------------------------------------------------------------- độ ổn định
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Danh sách nhạy với cách xếp hạng", "Cần đọc kèm độ ổn định và tần suất xuất hiện")
seed = STAB[STAB["Bien_the"].str.startswith("1 seed") & STAB["Bien_the"].str.contains("thận trọng")]["Trung_voi_ds_chinh"]
usd = int(STAB[STAB["Bien_the"].str.contains("USD")]["Trung_voi_ds_chinh"].iloc[0])
stat(s, 0.6, 1.8, 3.9, f"{seed.min()}–{seed.max()}/20", "căn giữ lại khi đổi seed chia fold (cùng quy tắc)", h=1.8)
stat(s, 4.75, 1.8, 3.9, f"{S4['top20_core_all_seed_variants']}", f"căn xuất hiện ở cả {S4['seed_variants_counted']} biến thể seed × cách xếp", h=1.8)
stat(s, 8.9, 1.8, 3.85, f"{usd}/20", "căn trùng nếu xếp theo chênh lệch USD thay vì %", color=ORANGE, h=1.8)
bullets(s, 0.6, 4.0, 12.1, 3.0, [("Mục tiêu xếp hạng: ", "ưu tiên chênh lệch tương đối và đồng thuận 3 mô hình — không phải tối ưu lợi nhuận."),
                                 ("Ba mô hình cùng dữ liệu: ", "đồng thuận giảm rủi ro một mô hình, nhưng không phải ba bằng chứng độc lập."),
                                 ("Bảng tần suất xuất hiện: ", "cơ sở để nói về 'nhóm lõi' (sheet 'Tần suất xuất hiện' trong Excel)."),
                                 ("Ngưỡng −20%, trần −50%: ", "quy tắc nhóm đặt, chưa hiệu chỉnh bằng kết quả thẩm định thực tế (F08).")], size=15)
presenter(s, "TV4")
notes(s, "TV4 (45 giây): đọc ba con số; kết luận: ưu tiên căn có tần suất cao.")

# 12 ---------------------------------------------------------------- dashboard
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Dashboard: kéo ngưỡng What-if, thấy ngay đánh đổi", "Power BI 6 trang (TV5) · ảnh: bản web cùng dữ liệu")
pic = picture(s, SHOT, 0.6, 1.8, h=5.2, alt="Ảnh chụp dashboard ở ngưỡng 20%")
xr = 0.6 + (pic.width / 914400 if pic else 6) + 0.4
r20, r10, r30 = THR.loc[20], THR.loc[10], THR.loc[30]
bullets(s, xr, 1.9, 12.73 - xr, 5.1, [("Tham số What-if: ", "ngưỡng thấp hơn dự báo 5–50%."),
                                      ("Ngưỡng 10%: ", f"{vn(r10['So_can_ung_vien'])} căn"), ("Ngưỡng 20%: ", f"{vn(r20['So_can_ung_vien'])} căn ({pct(r20['Ty_le_ung_vien_%'])})"),
                                      ("Ngưỡng 30%: ", f"{vn(r30['So_can_ung_vien'])} căn"),
                                      ("What-if 2: ", "ngân sách thẩm định 0,5–10 triệu USD (cùng quy tắc R1–R7)."),
                                      ("Power BI: ", "6 trang, điều hướng, bookmark nhà đầu tư / học thuật."),
                                      ("Bản web: ", "một file HTML cho người không có Power BI.")], size=14)
presenter(s, "TV5")
notes(s, "TV5 (75 giây): demo kéo thanh trượt 20% → 10% → 30%, đổi chế độ R4–R6/Chỉ ngưỡng, lọc zipcode.")

# 13 ---------------------------------------------------------------- KPI kết quả
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Kết quả so với KPI")
rate = r20["Ty_le_ung_vien_%"]
res = [("KPI1 · MAPE", f"Test {pct(mt)} · Nested {pct(S4['king_nested_cv']['MAPE_%'])} · Thời gian {pct(mm('King County (backtest thời gian)', LOCKED))}",
        mt <= 12 and mt < mm("King County", "Linear Regression (baseline)") < naive),
       ("KPI2 · Tỷ lệ ứng viên", f"{pct(rate)} ở ngưỡng 20%", 2 <= rate <= 10),
       ("KPI3 · Độ ổn định", f"{seed.min()}–{seed.max()}/20 qua 4 seed", seed.min() >= 15)]
for i, (k_, v_, ok) in enumerate(res):
    x = 0.6 + i * 4.1
    card(s, x, 1.8, 3.8, 3.2, fill=("E6F4F1" if ok else "FDEBE6"))
    text(s, x + 0.3, 2.05, 3.2, 0.5, k_, size=19, bold=True, color=NAVY, font=FONT_H)
    text(s, x + 0.3, 2.7, 3.2, 1.4, v_, size=15, color=INK)
    text(s, x + 0.3, 4.2, 3.2, 0.6, "Đạt" if ok else "Chưa đạt", size=22, bold=True, color=(TEAL if ok else ORANGE))
bullets(s, 0.6, 5.35, 12.1, 1.8, [("Khuyến nghị: ", "đưa 20 căn vào thẩm định theo thứ tự; xác minh điều kiện bán và dữ liệu trước khi định giá lại."),
                                  ("Áp dụng cho giao dịch mới: ", "dùng mức sai số của backtest thời gian, huấn luyện lại định kỳ.")], size=15)
presenter(s, "TV5")
notes(s, "TV5 (45 giây): đối chiếu từng KPI với mục tiêu ở slide 3; nêu điểm chưa đạt nếu có.")

# 14 ---------------------------------------------------------------- hướng phát triển
s = prs.slides.add_slide(BLANK); bg(s, WHITE)
title(s, "Hướng phát triển")
items = [("Khoảng dự báo", "Quantile / conformal: chỉ gọi ứng viên khi giá dưới cận dưới"),
         ("Hiệu chỉnh quy tắc", "Lưu kết quả thẩm định để đo precision và chỉnh ngưỡng"),
         ("Tối ưu danh mục", "Thêm chi phí, ngân sách → bài toán tối ưu chọn 20 căn"),
         ("Dữ liệu giàu hơn", "Điều kiện bán, cải tạo, trường học, giao thông, ảnh nhà"),
         ("Nhân quả cải tạo", "So sánh trước/sau cải tạo thay vì suy từ what-if"),
         ("Vận hành", "Giám sát MAPE hằng tháng, CI chạy test, API dự báo")]
for i, (h_, d_) in enumerate(items):
    col, row = i % 3, i // 3
    x, y = 0.6 + col * 4.1, 1.8 + row * 2.6
    card(s, x, y, 3.8, 2.3)
    badge(s, x + 0.3, y + 0.3, i + 1, TEAL)
    text(s, x + 1.05, y + 0.32, 2.6, 0.5, h_, size=18, bold=True, color=NAVY)
    text(s, x + 0.3, y + 1.05, 3.25, 1.1, d_, size=14, color=INK)
presenter(s, "TV6")
notes(s, "TV6 (45 giây): chọn 2–3 hướng quan trọng nhất (khoảng dự báo, hiệu chỉnh quy tắc).")

# 15 ---------------------------------------------------------------- kết
s = prs.slides.add_slide(BLANK); bg(s, NAVY)
text(s, 0.8, 1.6, 11.7, 1.2, "Kết luận", size=40, bold=True, color=WHITE, font=FONT_H)
bullets(s, 0.8, 2.8, 11.7, 2.8, [f"Quy trình tự động giảm sai số so với định giá thủ công ({pct(naive)} → {pct(mt)}).",
                                 "20 ứng viên là danh sách thẩm định ưu tiên, không phải danh sách mua.",
                                 "Mọi số liệu sinh từ mã nguồn; AI chỉ hỗ trợ viết mã và diễn đạt — nhật ký trong repo."], size=20, color=WHITE)
text(s, 0.8, 6.2, 11.7, 0.5, "Repo GitHub: github.com/hanestuamante/BTL_HHTRQD", size=14, color="9FB7CF")
notes(s, "TV6 (30 giây): tóm tắt, cảm ơn. Tổng thời lượng mục tiêu ~10 phút.")

OUT.parent.mkdir(exist_ok=True)
prs.core_properties.title = "Chủ đề 14 — Mô hình định giá bất động sản tự động"
prs.save(OUT)
print("Wrote", OUT, len(prs.slides), "slides")
