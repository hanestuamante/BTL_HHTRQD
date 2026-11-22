"""Nhiệm vụ 6: ghép báo cáo tổng hợp 7 phần (Word) từ các phần đã có + phần mới, số liệu đọc từ file kết quả.

    python scripts/build_full_report.py          # tạo reports/Bao_cao_tong_hop_Chu_de_14.docx
    python scripts/build_full_report.py --pdf    # thêm bản PDF (cần Microsoft Word trên macOS hoặc LibreOffice)

Cấu trúc: Phần 1–3 (Nhiệm vụ 1) · Phần 4, 5.1–5.8 (Nhiệm vụ 2–3, lấy từ reports/Bao_cao_Nhiem_vu_2_3.docx)
· Phần 5.9–5.10 (Nhiệm vụ 4, reports/Bao_cao_Nhiem_vu_4.docx) · Phần 6 (Nhiệm vụ 5) · Phần 7 (Nhiệm vụ 6)
· Minh bạch sử dụng AI · Tài liệu tham khảo · Phụ lục.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docxcompose.composer import Composer

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports"
T4 = ROOT / "outputs" / "task4" / "tables"
T3 = ROOT / "outputs" / "tables"
SHOTS = ROOT / "dashboard" / "screenshots"
OUT = REP / "Bao_cao_tong_hop_Chu_de_14.docx"

S4 = json.loads((T4 / "task4_summary.json").read_text(encoding="utf-8"))
TB = json.loads((T4 / "temporal_backtest.json").read_text(encoding="utf-8"))
A3 = json.loads((T3 / "analysis_summary.json").read_text(encoding="utf-8"))
ETL = json.loads((ROOT / "metadata" / "etl_summary.json").read_text(encoding="utf-8"))
MET = pd.read_csv(T4 / "model_metrics_mape_report.csv")
THR = pd.read_csv(T4 / "sensitivity_threshold.csv").set_index("Nguong_%")
STAB = pd.read_csv(T4 / "sensitivity_top20_stability.csv")
QS = pd.read_csv(ROOT / "docs" / "nv1" / "bang_cau_hoi_S.csv")

fmt = lambda v: f"{v:,.0f}".replace(",", ".")
pct = lambda v: f"{v:.1f}".replace(".", ",") + "%"
BEST = S4["best_model"]
LOCKED = TB["locked_model"]["model"]


def mm(market, model, col="MAPE_%"):
    return float(MET[(MET["Thi_truong"] == market) & (MET["Mo_hinh"] == model)][col].iloc[0])


MAPE_TEST = mm("King County", BEST)
MAPE_LR = mm("King County", "Linear Regression (baseline)")
MAPE_NAIVE = mm("King County", "Mốc thô: đơn giá zipcode × diện tích")
MAPE_TIME = mm("King County (backtest thời gian)", LOCKED)
MAPE_NESTED = S4["king_nested_cv"]["MAPE_%"]
RATE20 = THR.loc[20, "Ty_le_ung_vien_%"]
N20 = int(THR.loc[20, "So_can_ung_vien"])
seed_rows = STAB[STAB["Bien_the"].str.startswith("1 seed") & STAB["Bien_the"].str.contains("thận trọng")]
STAB_MIN, STAB_MAX = int(seed_rows["Trung_voi_ds_chinh"].min()), int(seed_rows["Trung_voi_ds_chinh"].max())

# KPI do nhóm đặt ở Phần 3 (giả định quản trị, không phải số liệu thực tế)
KPI_MAPE_MAX = 12.0
KPI_RATE_RANGE = (2.0, 10.0)
KPI_STAB_MIN = 15


# ---------------------------------------------------------------- tiện ích định dạng
def setup(doc):
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin, sec.bottom_margin, sec.left_margin, sec.right_margin = Cm(2), Cm(2), Cm(2.5), Cm(2)
    for name in ["Normal", "Title", "Heading 1", "Heading 2", "Heading 3", "Caption"]:
        s = doc.styles[name]
        s.font.name = "Times New Roman"
        s._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Times New Roman")
    doc.styles["Normal"].font.size = Pt(12)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.2
    doc.styles["Normal"].paragraph_format.space_after = Pt(6)
    for h, size in [("Heading 1", 16), ("Heading 2", 13.5), ("Heading 3", 12)]:
        doc.styles[h].font.size = Pt(size)
        doc.styles[h].font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        doc.styles[h].paragraph_format.keep_with_next = True
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run("Chủ đề 14 — Mô hình định giá bất động sản tự động  |  Trang ")
    fld = OxmlElement("w:fldSimple"); fld.set(qn("w:instr"), "PAGE"); footer._p.append(fld)
    for r in footer.runs:
        r.font.size = Pt(9)


class W:
    def __init__(self, doc):
        self.d = doc

    def h(self, text, level=1):
        return self.d.add_heading(text, level=level)

    def p(self, text, bold_prefix=None, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
        para = self.d.add_paragraph(); para.alignment = align
        if bold_prefix:
            para.add_run(bold_prefix).bold = True
        r = para.add_run(text); r.italic = italic
        return para

    def b(self, text, bold_prefix=None):
        para = self.d.add_paragraph(style="List Bullet")
        if bold_prefix:
            para.add_run(bold_prefix).bold = True
        para.add_run(text)

    def table(self, headers, rows, widths=None, fs=10, caption=None):
        if caption:
            c = self.d.add_paragraph(); r = c.add_run(caption); r.bold = True; r.font.size = Pt(10.5)
        t = self.d.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for c, x in zip(t.rows[0].cells, headers):
            c.text = str(x)
        for row in rows:
            for c, x in zip(t.add_row().cells, row):
                c.text = str(x)
        for i, row in enumerate(t.rows):
            for j, c in enumerate(row.cells):
                if widths:
                    c.width = Cm(widths[j])
                if i == 0:
                    sh = OxmlElement("w:shd"); sh.set(qn("w:fill"), "1F3A5F"); c._tc.get_or_add_tcPr().append(sh)
                for para in c.paragraphs:
                    para.paragraph_format.space_after = Pt(2)
                    for r in para.runs:
                        r.font.size = Pt(fs)
                        if i == 0:
                            r.bold = True; r.font.color.rgb = RGBColor(255, 255, 255)
            if i == 0:
                row._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
        self.d.add_paragraph()
        return t

    def img(self, path, caption, width=16):
        if not Path(path).exists():
            self.p(f"[Thiếu hình: {Path(path).relative_to(ROOT)} — chạy scripts/build_dashboard.py --screens]", italic=True)
            return
        self.d.add_picture(str(path), width=Cm(width))
        self.d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        c = self.d.add_paragraph(caption, style="Caption"); c.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def page_break(self):
        self.d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ---------------------------------------------------------------- phần mở đầu + Phần 1–3
def front_and_parts_1_3():
    doc = Document(); setup(doc); w = W(doc)
    for line, size, bold in [("ĐẠI HỌC — HỌC PHẦN HỆ HỖ TRỢ RA QUYẾT ĐỊNH (261HHTQD)", 13, True),
                             ("BÁO CÁO BÀI TẬP LỚN", 22, True),
                             ("CHỦ ĐỀ 14: MÔ HÌNH ĐỊNH GIÁ BẤT ĐỘNG SẢN TỰ ĐỘNG", 16, True),
                             ("Nhóm: 261HHTQD_Nhom__ (điền số nhóm)", 12, False),
                             (f"Phiên bản tổng hợp ngày {date.today():%d/%m/%Y}", 12, False)]:
        para = doc.add_paragraph(); para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_before = Pt(18 if size > 14 else 6)
        r = para.add_run(line); r.bold = bold; r.font.size = Pt(size)
    w.table(["TV", "Nhiệm vụ", "Sản phẩm trong repo", "Họ tên"], [
        ["1", "Đặt câu hỏi, KPI, ràng buộc — Phần 1, 2, 3", "docs/nv1/bang_cau_hoi_S.csv, docs/nv1/nhat_ky_dung_ai.md", ""],
        ["2", "Dữ liệu, ETL 4 bước, từ điển — Phần 4", "data/processed/, dictionaries/, docs/nhat_ky_etl_4_buoc.txt", ""],
        ["3", "EDA, chẩn đoán — Phần 5 cấp 1, 2", "notebooks/02_03_ETL_EDA.ipynb, outputs/figures/", ""],
        ["4", "Mô hình, MAPE, 20 ứng viên — Phần 5 cấp 3, 4", "models/model.pkl, notebooks/04_Modeling.ipynb, outputs/task4/", ""],
        ["5", "Dashboard What-if — Phần 6", "dashboard/ (HTML tương tác + gói Power BI)", ""],
        ["6", "Phần 7, tổng hợp báo cáo, slide, video", "reports/, slides/, docs/nv6/", ""],
    ], widths=[1, 6, 7, 3], fs=9.5, caption="Phân công và sản phẩm bàn giao (cột Họ tên do nhóm điền)")
    w.p("Nguyên tắc số liệu: mọi con số trong báo cáo được sinh ra từ mã nguồn chạy trên dữ liệu gốc và đọc lại từ các file "
        "kết quả trong repo; không có số liệu thực tế nào do AI tạo ra. Phần minh bạch sử dụng AI nằm sau Phần 7.", italic=True)
    w.page_break()

    w.h("Phần 1. Vấn đề kinh doanh (Lớp 1)")
    w.p("Bối cảnh: một quỹ đầu tư nhà ở muốn tìm những căn có giá giao dịch thấp hơn mức mà đặc điểm của căn gợi ý, để đưa "
        "vào danh sách thẩm định trước khi quyết định mua. Cách làm thủ công phổ biến là nhân đơn giá trung vị của khu vực "
        "với diện tích. Cách này nhanh nhưng bỏ qua chất lượng xây dựng, tình trạng, tầm nhìn, tuổi nhà và vị trí chi tiết, "
        "nên sai số lớn và khó giải thích vì sao một căn được xem là rẻ.")
    w.p(f"Bằng chứng từ dữ liệu: trên tập test King County, mốc 'đơn giá zipcode × diện tích' có MAPE {pct(MAPE_NAIVE)} "
        f"(outputs/task4/tables/model_metrics_mape_report.csv). Với sai số đó, một căn lệch 20% so với mốc có thể chỉ là sai "
        "số của chính phương pháp định giá.")
    w.p("Vấn đề kinh doanh: xây dựng một quy trình định giá tự động, nhất quán và kiểm chứng được, để (1) ước lượng giá "
        "cho từng căn với sai số thấp hơn cách làm thủ công và (2) lập danh sách ứng viên có giá giao dịch thấp hơn dự báo, "
        "giới hạn ở số căn mà bộ phận thẩm định xử lý được.")
    w.p("Phạm vi: dữ liệu giao dịch lịch sử King County (Washington, 05/2014–05/2015) là thị trường chính; Ames (Iowa, "
        "2006–2010) để kiểm chứng ở thị trường thứ hai. Đây là dữ liệu lịch sử; kết quả dùng để minh họa và đánh giá quy trình, "
        "không xác nhận cơ hội mua ở thời điểm hiện tại.")
    w.b("Giám đốc đầu tư — người ra quyết định chọn căn đưa vào thẩm định.", "Người ra quyết định: ")
    w.b("bộ phận thẩm định (xác minh thực địa, pháp lý), hội đồng đầu tư.", "Người liên quan: ")
    w.b("chọn 20 căn ưu tiên thẩm định; không phải quyết định mua ngay.", "Quyết định cần hỗ trợ: ")

    w.h("Phần 2. Câu hỏi quyết định và chuỗi 4 lớp câu hỏi (bước S)")
    w.p("Câu hỏi quyết định: Với ràng buộc xét 20 căn, Giám đốc đầu tư nên đưa 20 căn nào vào danh sách thẩm định ưu tiên, "
        "và danh sách đó đáng tin đến mức nào?", bold_prefix="")
    w.p("Chuỗi 4 lớp câu hỏi đi từ vấn đề kinh doanh tới câu hỏi quyết định; mỗi lớp gắn với một cấp phân tích và nơi trả lời "
        "trong báo cáo:")
    for lbl, text in [("Lớp 1 — Vấn đề kinh doanh: ", "Có thể thay định giá thủ công bằng quy trình tự động, nhất quán và kiểm chứng được không?"),
                      ("Lớp 2 — Hiểu dữ liệu (mô tả, chẩn đoán): ", "Giá phân bố thế nào theo khu vực; nhóm giá thấp khác nhóm còn lại ở đặc điểm nào; chiều quan hệ có đúng giả thuyết?"),
                      ("Lớp 3 — Dự báo: ", "Mô hình dự báo giá với sai số bao nhiêu, có tốt hơn mốc thủ công và giữ được khi dự báo giao dịch tương lai không?"),
                      ("Lớp 4 — Quyết định: ", "Chọn 20 căn nào để thẩm định, và danh sách nhạy thế nào với ngưỡng, mô hình, cách xếp hạng?")]:
        w.b(text, lbl)
    w.table(["Lớp", "Câu hỏi", "Người dùng câu trả lời", "Cấp phân tích", "Dữ liệu & phương pháp", "Sản phẩm trả lời"],
            QS.values.tolist(), widths=[2.2, 4.6, 2.3, 2, 3.4, 2.5], fs=8,
            caption="Bảng 2.1. Bảng câu hỏi S (6 cột) — docs/nv1/bang_cau_hoi_S.csv")

    w.h("Phần 3. KPI và ràng buộc")
    w.p("KPI và ngưỡng mục tiêu dưới đây là giả định quản trị do nhóm đặt trước khi đọc kết quả cuối; chúng không phải số liệu "
        "thực tế. Kết quả đo được đối chiếu ở Phần 6.")
    w.table(["KPI", "Định nghĩa", "Ngưỡng mục tiêu (giả định)", "Lý do"], [
        ["KPI1 — MAPE", "Trung bình |giá dự báo − giá thực| / giá thực trên giao dịch mô hình chưa thấy (tập test theo id; kiểm tra thêm bằng backtest thời gian và nested CV)",
         f"≤ {KPI_MAPE_MAX:.0f}% và thấp hơn baseline Linear Regression, thấp hơn mốc thủ công",
         "Ngưỡng ứng viên −20% chỉ có nghĩa khi sai số điển hình của mô hình nhỏ hơn đáng kể so với 20%"],
        ["KPI2 — Tỷ lệ ứng viên", "Số căn có giá giao dịch thấp hơn dự báo ≥ 20% / số căn trong pool (giao dịch gần nhất, sau R1–R3)",
         f"Trong khoảng {KPI_RATE_RANGE[0]:.0f}–{KPI_RATE_RANGE[1]:.0f}%", "Quá cao: ngưỡng không phân biệt; quá thấp: không đủ lựa chọn sau khi lọc"],
        ["KPI3 — Độ ổn định top 20", "Số căn của danh sách chính còn lại khi đổi seed chia fold (cùng quy tắc)",
         f"≥ {KPI_STAB_MIN}/20 ở mọi seed", "Danh sách quá nhạy với cách chia dữ liệu thì không nên dùng để ra quyết định"],
    ], widths=[2.6, 6.2, 3.4, 4.8], fs=9, caption="Bảng 3.1. KPI")
    w.table(["Ràng buộc", "Nội dung"], [
        ["Số căn", "Giám đốc đầu tư xét đúng 20 căn (ngân sách thẩm định)."],
        ["Không trùng tài sản", "Mỗi tài sản xuất hiện tối đa một lần (giao dịch gần nhất)."],
        ["Chống rò rỉ", "Không dùng biến chứa giá (price_per_sqft, cờ ngoại lệ theo giá) làm đầu vào; chia train/test theo id tài sản."],
        ["Diễn giải", "Residual âm là tín hiệu cần xác minh, không phải bằng chứng bị định giá thấp; chênh lệch so với dự báo không phải lợi nhuận."],
        ["Số liệu", "Không dùng AI để tạo số liệu thực tế; mọi số đọc từ file kết quả."],
    ], widths=[3.5, 13.5], fs=9.5, caption="Bảng 3.2. Ràng buộc")
    w.page_break()
    return doc


# ---------------------------------------------------------------- Phần 6, 7, AI, tài liệu tham khảo
def parts_6_7():
    doc = Document(); setup(doc); w = W(doc)
    w.h("Phần 6. Kết quả và Dashboard ra quyết định").paragraph_format.page_break_before = True
    w.p("Dashboard được xây cho Giám đốc đầu tư, có tham số What-if là thanh trượt ngưỡng 'giá giao dịch thấp hơn dự báo ít "
        "nhất x%' (5–50%). Khi kéo thanh trượt, số căn ứng viên, tỷ lệ ứng viên, giá trung vị, bản đồ, phân phối residual và "
        "danh sách thẩm định ưu tiên cập nhật ngay. Có hai chế độ: 'R4–R6 (khuyến nghị)' áp đủ quy tắc chọn, 'Chỉ ngưỡng' chỉ lọc "
        "theo residual của mô hình chính; bộ lọc zipcode để xem từng khu vực.")
    w.b("dashboard/Dashboard_Chu_de_14.html — bản tương tác chạy trên mọi trình duyệt, không cần cài đặt; số liệu nhúng từ "
        "outputs/task4/tables và được script đối chiếu với sensitivity_threshold.csv.", "Bản tương tác: ")
    w.b("dashboard/powerbi/ — bảng dữ liệu, bảng tham số, công thức DAX và hướng dẫn dựng file .pbix (What-if parameter). "
        "File .pbix/.twbx phải được dựng trong Power BI Desktop/Tableau; xem dashboard/powerbi/HUONG_DAN_POWER_BI.md.",
        "Gói Power BI/Tableau: ")
    w.img(SHOTS / "dashboard_nguong_20.png", "Hình 6.1. Dashboard ở ngưỡng 20% (chế độ R4–R6)", 16)
    w.img(SHOTS / "dashboard_nguong_10.png", "Hình 6.2. Ngưỡng 10%: số ứng viên tăng mạnh; top 20 (xếp từ căn thấp hơn dự báo nhiều nhất) không đổi", 16)

    w.h("6.1. Đối chiếu KPI", 2)
    k1 = MAPE_TEST <= KPI_MAPE_MAX and MAPE_TEST < MAPE_LR < MAPE_NAIVE
    k2 = KPI_RATE_RANGE[0] <= RATE20 <= KPI_RATE_RANGE[1]
    k3 = STAB_MIN >= KPI_STAB_MIN
    w.table(["KPI", "Mục tiêu", "Kết quả đo", "Đạt?"], [
        ["KPI1 — MAPE", f"≤ {KPI_MAPE_MAX:.0f}%, thấp hơn baseline và mốc thủ công",
         f"Test {pct(MAPE_TEST)} ({BEST}); baseline {pct(MAPE_LR)}; mốc thủ công {pct(MAPE_NAIVE)}; backtest thời gian "
         f"{pct(MAPE_TIME)}; nested CV {pct(MAPE_NESTED)}", "Đạt" if k1 else "Chưa đạt"],
        ["KPI2 — Tỷ lệ ứng viên", f"{KPI_RATE_RANGE[0]:.0f}–{KPI_RATE_RANGE[1]:.0f}%",
         f"{pct(RATE20)} ({fmt(N20)} căn / {fmt(S4['candidate_pool_size'])}); sau R4–R6 còn {fmt(S4['recommended_pool_size'])}",
         "Đạt" if k2 else "Chưa đạt"],
        ["KPI3 — Độ ổn định", f"≥ {KPI_STAB_MIN}/20 ở mọi seed", f"{STAB_MIN}–{STAB_MAX}/20 qua 4 seed; "
         f"{S4['top20_core_all_seed_variants']} căn có mặt ở cả {S4['seed_variants_counted']} biến thể seed × cách xếp",
         "Đạt" if k3 else "Chưa đạt"],
    ], widths=[3, 3.8, 8.2, 2], fs=9, caption="Bảng 6.1. KPI: mục tiêu và kết quả (nguồn: outputs/task4/tables)")
    if not k1 and MAPE_TEST > KPI_MAPE_MAX:
        w.p(f"KPI1 chưa đạt ngưỡng {KPI_MAPE_MAX:.0f}% do nhóm đặt; vẫn tốt hơn baseline và mốc thủ công. Cần thận trọng hơn ở "
            "phân khúc giá thấp nơi sai số lớn nhất.")
    if MAPE_TIME > KPI_MAPE_MAX:
        w.p(f"Khi dự báo giao dịch tương lai (backtest thời gian), MAPE là {pct(MAPE_TIME)}, cao hơn trên tập test ngẫu nhiên; "
            "đây là mức sai số nên dùng khi áp dụng cho giao dịch mới.")

    w.h("6.2. Câu trả lời cho câu hỏi quyết định", 2)
    w.p(f"Quy trình đề xuất 20 ứng viên có giá giao dịch thấp hơn dự báo, cần xác minh (Bảng 5.10.2 và file "
        f"outputs/task4/Top20_ung_vien_can_xac_minh.xlsx). Tổng giá giao dịch lịch sử của 20 căn là "
        f"{fmt(S4['top20_total_historical_price_usd'])} USD, tổng giá dự báo {fmt(S4['top20_total_predicted_usd'])} USD. "
        "Chênh lệch giữa hai tổng chỉ mô tả khoảng cách so với mô hình trên giao dịch 2014–2015, không phải lợi nhuận có thể đạt được.")
    for t in ["Đưa 20 căn vào thẩm định theo thứ tự mức thấp hơn dự báo thận trọng; ưu tiên căn có tần suất xuất hiện cao qua các biến thể.",
              "Xác minh điều kiện giao dịch và dữ liệu trước khi định giá lại theo thị trường hiện tại.",
              "Dùng thanh trượt What-if để thấy đánh đổi: ngưỡng thấp cho nhiều lựa chọn nhưng lẫn sai số mô hình; ngưỡng cao "
              "cho ít căn hơn, tập trung vào nhà giá thấp — phân khúc mô hình kém chính xác nhất."]:
        w.b(t)

    w.h("Phần 7. Hướng phát triển")
    for lbl, t in [
        ("Dữ liệu hiện tại và nhiều nguồn hơn: ", "cập nhật giao dịch mới; bổ sung điều kiện bán (bán tháo, người thân, thừa kế), "
         "lịch sử cải tạo, ảnh và mô tả nhà, trường học, tội phạm, giao thông để giảm residual do thiếu đặc điểm."),
        ("Khoảng dự báo: ", "thêm quantile regression hoặc conformal prediction để mỗi căn có khoảng giá; chỉ gọi là ứng viên khi "
         "giá giao dịch nằm dưới cận dưới của khoảng, thay vì so với một ước lượng điểm."),
        ("Hiệu chỉnh quy tắc chọn: ", "lưu kết quả thẩm định thực tế của từng ứng viên (đúng/sai) để hiệu chỉnh ngưỡng −20%, trần "
         "−50% và tiêu chí lọc; đo precision của danh sách thay vì chỉ độ ổn định."),
        ("Tối ưu danh mục có ràng buộc: ", "khi có chi phí giao dịch, chi phí cải tạo, ngân sách vốn và mục tiêu lợi nhuận rõ, "
         "chuyển từ xếp hạng sang bài toán tối ưu (knapsack/MILP) chọn 20 căn."),
        ("Tác động cải tạo: ", "đánh giá nhân quả (so sánh trước/sau cải tạo, difference-in-differences) thay vì suy từ what-if của mô hình."),
        ("Vận hành: ", "giám sát MAPE trên giao dịch mới theo tháng, huấn luyện lại định kỳ, kiểm thử tự động trên CI, đóng gói "
         "API dự báo (bds_valuation.predict) thành dịch vụ; dashboard Power BI kết nối trực tiếp tới bảng kết quả."),
        ("Mở rộng thị trường: ", "áp dụng cùng quy trình cho dữ liệu nhà ở Việt Nam khi có nguồn giao dịch đáng tin cậy, chú ý khác biệt pháp lý và cách đo diện tích."),
    ]:
        w.b(t, lbl)

    w.h("Minh bạch sử dụng AI")
    w.p("Nhóm dùng trợ lý AI để hỗ trợ viết mã, cấu trúc nội dung và diễn đạt; mọi số liệu được tạo bởi mã nguồn chạy trên dữ liệu "
        "gốc. Nhật ký chi tiết theo bước (gồm prompt bước S) ở docs/nv1/nhat_ky_dung_ai.md. Các điểm kiểm soát:")
    for t in ["Số liệu trong văn bản được chèn tự động từ file kết quả bởi scripts/build_*_report.py, không gõ tay.",
              "Bộ kiểm thử tự động (tests/) kiểm tra chia tập theo tài sản, điền thiếu học trên train, ánh xạ mô hình, ràng buộc "
              "what-if, quy tắc chọn và API dự báo.",
              "Feedback độc lập ngày 21/11/2026 (13 mục F01–F13) đã được xử lý; các câu diễn đạt vượt bằng chứng do AI viết ở bản trước "
              "('bị định giá thấp', 'chênh lệch kỳ vọng', 'cận trên', 'cải tạo là đòn bẩy') đã được sửa.",
              "AI không quay video và không dựng file .pbix thay nhóm; các phần này do thành viên thực hiện."]:
        w.b(t)

    w.h("Tài liệu tham khảo")
    for t in ["[1] harlfoxem. House Sales in King County, USA. Kaggle. https://www.kaggle.com/datasets/harlfoxem/housesalesprediction",
              "[2] De Cock, D. (2011). Ames, Iowa: Alternative to the Boston Housing Data as an End of Semester Regression Project. "
              "Journal of Statistics Education, 19(3). https://jse.amstat.org/v19n3/decock.pdf",
              "[3] Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. KDD '16.",
              "[4] Pedregosa, F. et al. (2011). Scikit-learn: Machine Learning in Python. JMLR 12.",
              "[5] Breiman, L. (2001). Random Forests. Machine Learning 45(1)."]:
        w.p(t, align=WD_ALIGN_PARAGRAPH.LEFT)

    w.h("Phụ lục — Danh mục bàn giao", 1)
    w.table(["Hạng mục", "Đường dẫn"], [
        ["Báo cáo tổng hợp (Word, PDF)", "reports/Bao_cao_tong_hop_Chu_de_14.docx / .pdf"],
        ["Dữ liệu sạch, từ điển, ETL", "data/processed/, dictionaries/data_dictionary.csv, docs/nhat_ky_etl_4_buoc.txt"],
        ["Notebook", "notebooks/02_03_ETL_EDA.ipynb, notebooks/04_Modeling.ipynb"],
        ["Mô hình", "models/model.pkl (dự báo qua bds_valuation.predict)"],
        ["Ứng viên, MAPE", "outputs/task4/Top20_ung_vien_can_xac_minh.xlsx, outputs/task4/tables/model_metrics_mape_report.csv"],
        ["Dashboard", "dashboard/Dashboard_Chu_de_14.html, dashboard/powerbi/"],
        ["Slide, kịch bản video", "slides/Chu_de_14_thuyet_trinh.pptx, docs/nv6/kich_ban_video.md"],
        ["Kiểm thử", "tests/ (python -m pytest)"],
    ], widths=[5, 12], fs=9.5)
    return doc


# ---------------------------------------------------------------- ghép
def trimmed(path, start_text, stop_text=None):
    """Bản sao docx chỉ giữ từ heading bắt đầu bằng start_text tới trước heading stop_text."""
    d = Document(str(path))
    body = d.element.body
    children = [c for c in body.iterchildren() if c.tag != qn("w:sectPr")]
    keep, state = [], "before"
    for c in children:
        text = "".join(t.text or "" for t in c.iter(qn("w:t"))) if c.tag == qn("w:p") else ""
        is_heading = c.tag == qn("w:p") and c.find(qn("w:pPr")) is not None and any(
            (s.get(qn("w:val")) or "").startswith(("Heading", "Title")) for s in c.iter(qn("w:pStyle")))
        if state == "before" and is_heading and text.strip().startswith(start_text):
            state = "in"
        elif state == "in" and stop_text and is_heading and text.strip().startswith(stop_text):
            state = "after"
        if state != "in":
            body.remove(c)
    assert len(body) > 5, f"Không tìm thấy '{start_text}' trong {path.name}"
    for para in d.paragraphs:                   # câu phạm vi cũ của NV2–3: chỉ tới phần đã làm trong báo cáo tổng hợp
        if para.text.rstrip().endswith("vì các sản phẩm đó thuộc nhiệm vụ 4."):
            para.add_run(" Các kết quả này nằm ở Phần 5.9–5.10.")
    return d


def to_pdf(docx: Path) -> Path | None:
    pdf = docx.with_suffix(".pdf")
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(docx.parent), str(docx)], check=True)
        return pdf
    if sys.platform == "darwin" and Path("/Applications/Microsoft Word.app").exists():
        script = f'''
        tell application "Microsoft Word"
            open POSIX file "{docx}"
            set d to active document
            update (fields of d)
            save as d file name (POSIX file "{pdf}" as string) file format format PDF
            close d saving no
        end tell'''
        subprocess.run(["osascript", "-e", script], check=True, timeout=300)
        return pdf
    print("Không có LibreOffice/Word — bỏ qua PDF; mở file .docx và Save as PDF.")
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args(argv)
    master = front_and_parts_1_3()
    comp = Composer(master)
    comp.append(trimmed(REP / "Bao_cao_Nhiem_vu_2_3.docx", "4 Dữ liệu", "Phụ lục nội dung slide"))
    nv4 = trimmed(REP / "Bao_cao_Nhiem_vu_4.docx", "5.9.", "Phụ lục — Sản phẩm bàn giao")
    nv4.paragraphs[0].paragraph_format.page_break_before = True
    comp.append(nv4)
    comp.append(parts_6_7())
    master.core_properties.title = "Chủ đề 14 — Mô hình định giá bất động sản tự động"
    master.core_properties.subject = "Báo cáo tổng hợp 7 phần"
    comp.save(str(OUT))
    print("Wrote", OUT)
    if a.pdf:
        pdf = to_pdf(OUT)
        if pdf:
            print("Wrote", pdf)


if __name__ == "__main__":
    main()
