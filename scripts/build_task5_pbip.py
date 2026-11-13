"""Nhiệm vụ 5: sinh Power BI project (.pbip) cho dashboard định giá BĐS.

Đọc header/kiểu từ dashboard/data/*.csv và sinh:
  dashboard/BTL_NhiemVu5.pbip
  dashboard/BTL_NhiemVu5.SemanticModel/...   (TMDL)
  dashboard/BTL_NhiemVu5.Report/...          (PBIR JSON)

Chạy: python scripts/build_task5_pbip.py
Sau đó mở file .pbip bằng Power BI Desktop và Save As .pbix.
"""
from pathlib import Path
from uuid import uuid4
import json
import shutil

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dashboard" / "data"
OUT = ROOT / "dashboard"
PROJECT = "BTL_NhiemVu5"
MODEL_DIR = OUT / f"{PROJECT}.SemanticModel"
REPORT_DIR = OUT / f"{PROJECT}.Report"
KPI_TABLE = "KPI"

# Sinh lại từ đầu để không sót file của lần chạy trước
for folder in (MODEL_DIR / "definition", REPORT_DIR / "definition"):
    if folder.exists():
        shutil.rmtree(folder)
(MODEL_DIR / "definition" / "tables").mkdir(parents=True)
(REPORT_DIR / "definition" / "pages").mkdir(parents=True)


def write_budget_plan():
    """Bảng kế hoạch mua: ứng viên ở ngưỡng 20% xếp theo mức giảm sâu nhất,
    kèm giá lũy kế để measure ngân sách chỉ cần một phép so sánh."""
    df = pd.read_csv(DATA / "fact_king.csv")
    c = df[(df.is_latest_sale == 1) & (df.zero_room_flag == 0) & (df.condition >= 3)
           & (df.residual_pct <= -0.20) & (df.discount_pct <= 50)]
    c = c.sort_values("discount_pct", ascending=False)
    plan = pd.DataFrame({
        "rank": range(1, len(c) + 1),
        "price": c.price.values,
        "cum_price": c.price.cumsum().values,
        "upside_usd": c.upside_usd.values,
    })
    plan.to_csv(DATA / "budget_plan.csv", index=False)
    return plan


def write_metric_choices():
    """Bảng rời cho hộp chọn chỉ số (bảng tính DAX bị Power BI báo lỗi nên dùng CSV)."""
    pd.DataFrame({
        "ChiSo": ["Số ứng viên", "Giá trung vị nhóm", "Chênh lệch kỳ vọng (USD)"],
        "ThuTu": [0, 1, 2],
    }).to_csv(DATA / "chon_chi_so.csv", index=False)


def uid():
    return str(uuid4())


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- bảng dữ liệu
TABLES = [
    ("fact_king.csv", "KingSales", {"source_row_id"}),
    ("fact_ames.csv", "AmesSales", set()),
    ("top20.csv", "Top20", {"Hang"}),
    ("model_metrics.csv", "ModelMetrics", set()),
    ("model_compare_long.csv", "ModelCompare", set()),
    ("segment_compare.csv", "SegmentCompare", set()),
    ("sensitivity.csv", "Sensitivity", set()),
    ("importance_top.csv", "ImportanceTop", set()),
    ("stability.csv", "Stability", set()),
    ("whatif_scenarios.csv", "WhatIfScenarios", set()),
    ("budget_plan.csv", "BudgetPlan", set()),
    ("chon_chi_so.csv", "ChonChiSo", set()),
]


def m_type(dtype):
    if pd.api.types.is_integer_dtype(dtype):
        return "Int64.Type", "int64"
    if pd.api.types.is_float_dtype(dtype):
        return "type number", "double"
    if pd.api.types.is_bool_dtype(dtype):
        return "type logical", "boolean"
    return "type text", "string"


STRING_COLS = {"id", "zipcode", "pid", "zip_top", "ms_subclass", "sale_month",
               "neighborhood", "neighborhood_top", "date"}


def table_tmdl(csv, entity, hidden):
    df = pd.read_csv(DATA / csv, nrows=200)
    cols, m_types = [], []
    for name in df.columns:
        is_date = name == "date"
        if name in STRING_COLS and not is_date:
            mtype, ttype = "type text", "string"
        elif is_date:
            mtype, ttype = "type date", "dateTime"
        else:
            mtype, ttype = m_type(df[name].dtype)
        m_types.append(f'{{"{name}", {mtype}}}')
        col = [f"\tcolumn {name}", f"\t\tdataType: {ttype}"]
        if ttype in ("int64", "double"):
            col.append("\t\tsummarizeBy: none" if name in hidden or name in {"lat", "long"}
                       else "\t\tsummarizeBy: sum")
        if name in hidden:
            col.append("\t\tisHidden")
        col.append(f"\t\tsourceColumn: {name}")
        col.append(f"\t\tlineageTag: {uid()}")
        cols.append("\n".join(col))

    typed = ",\n\t\t\t\t\t".join(m_types)
    m = (
        f'\tpartition {entity} = m\n'
        f"\t\tmode: import\n"
        f"\t\tsource =\n"
        f"\t\t\tlet\n"
        f'\t\t\t\tSource = Csv.Document(File.Contents(DataFolder & "\\{csv}"), '
        f'[Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n'
        f"\t\t\t\tPromoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n"
        f"\t\t\t\tTyped = Table.TransformColumnTypes(Promoted,\n"
        f"\t\t\t\t\t{{\n\t\t\t\t\t{typed}\n\t\t\t\t\t}}),\n"
        f"\t\t\t\tResult = Typed\n"
        f"\t\t\tin\n"
        f"\t\t\t\tResult"
    )
    return f"table {entity}\n\tlineageTag: {uid()}\n\n" + "\n".join(cols) + "\n\n" + m + "\n"


# ---------------------------------------------------------------- measures
MEASURES = {
    "King Transactions": ("COUNTROWS('KingSales')", "#,0"),
    "King Properties": ("DISTINCTCOUNT('KingSales'[id])", "#,0"),
    "King Median Price": ("MEDIAN('KingSales'[price])", "#,0"),
    "King OOF MAPE": ("AVERAGEX('KingSales', ABS('KingSales'[residual_pct]))", "0.0%"),
    "Selected Threshold": (
        "IF(ISFILTERED('Nguong'[Value]), MIN('Nguong'[Value]), 0.20)", "0%"),
    "Candidate Base": (
        "CALCULATE(COUNTROWS('KingSales'), 'KingSales'[is_latest_sale] = 1, "
        "'KingSales'[zero_room_flag] = 0, 'KingSales'[condition] >= 3)", "#,0"),
    "Candidates": (
        "VAR t = -[Selected Threshold]\n"
        "RETURN CALCULATE([Candidate Base], 'KingSales'[residual_pct] <= t)", "#,0"),
    "Candidate Share": ("DIVIDE([Candidates], [Candidate Base])", "0.00%"),
    "Candidate Upside": (
        "VAR t = -[Selected Threshold]\n"
        "RETURN CALCULATE(SUM('KingSales'[upside_usd]), 'KingSales'[is_latest_sale] = 1, "
        "'KingSales'[zero_room_flag] = 0, 'KingSales'[condition] >= 3, "
        "'KingSales'[residual_pct] <= t)", "#,0"),
    "Candidate Median Price": (
        "VAR t = -[Selected Threshold]\n"
        "RETURN CALCULATE(MEDIAN('KingSales'[price]), 'KingSales'[is_latest_sale] = 1, "
        "'KingSales'[zero_room_flag] = 0, 'KingSales'[condition] >= 3, "
        "'KingSales'[residual_pct] <= t)", "#,0"),
    "Candidate All3": (
        "VAR t = -[Selected Threshold]\n"
        "RETURN CALCULATE(COUNTROWS('KingSales'), 'KingSales'[is_latest_sale] = 1, "
        "'KingSales'[zero_room_flag] = 0, 'KingSales'[condition] >= 3, "
        "'KingSales'[models_agree_undervalued] = 3, "
        "'KingSales'[residual_pct] <= t)", "#,0"),
    "Top20 Count": ("COUNTROWS('Top20')", "#,0"),
    "Top20 Capital": ("SUM('Top20'[price])", "#,0"),
    "Top20 Upside": ("SUM('Top20'[upside_usd])", "#,0"),
    "Top20 Median Discount": ("MEDIAN('Top20'[discount_pct])", "0.0"),
    "Top20 All3": ("COUNTROWS(FILTER('Top20', 'Top20'[models_agree_undervalued] = 3))", "#,0"),
    "Importance Increase": ("SUM('ImportanceTop'[mape_increase_pp])", "0.00"),
    "Scenario Change": ("SUM('WhatIfScenarios'[median_change_pct])", "0.00"),
    "Sensitivity Candidates": ("SUM('Sensitivity'[candidates])", "#,0"),
    "Model MAPE": ("SUM('ModelCompare'[mape])", "0.0"),
    "KingTx Text": ('FORMAT([King Transactions], "#,##0")', None),
    "KingMedian Text": ('FORMAT([King Median Price], "#,##0")', None),
    "Candidates Text": ('FORMAT([Candidates], "#,##0")', None),
    "CandidateUpside Text": ('FORMAT([Candidate Upside], "#,##0")', None),
    "CandidateMedian Text": ('FORMAT([Candidate Median Price], "#,##0")', None),
    "Top20Capital Text": ('FORMAT([Top20 Capital], "#,##0")', None),
    "Top20Upside Text": ('FORMAT([Top20 Upside], "#,##0")', None),
    "Top20All3 Text": ('FORMAT([Top20 All3], "#,##0")', None),
    "AmesProperties Text": ('FORMAT([Ames Properties], "#,##0")', None),
    "AmesMedian Text": ('FORMAT([Ames Median Price], "#,##0")', None),
    "AmesCandidates Text": ('FORMAT([Ames Candidates], "#,##0")', None),
    "Ames Properties": ("COUNTROWS('AmesSales')", "#,0"),
    "Ames Median Price": ("MEDIAN('AmesSales'[price])", "#,0"),
    "Ames OOF MAPE": ("AVERAGEX('AmesSales', ABS('AmesSales'[residual_pct]))", "0.0%"),
    "Ames Candidates": (
        "VAR t = -[Selected Threshold]\n"
        "RETURN CALCULATE(COUNTROWS('AmesSales'), 'AmesSales'[residual_pct] <= t)", "#,0"),
    "Ames Candidate Share": ("DIVIDE([Ames Candidates], [Ames Properties])", "0.00%"),
    "MAPE King XGB": (
        "CALCULATE(MAX('ModelMetrics'[mape]), 'ModelMetrics'[market] = \"King County\", "
        "'ModelMetrics'[model] = \"XGBoost (tuned)\")", "0.0"),
    "MAPE Ames XGB": (
        "CALCULATE(MAX('ModelMetrics'[mape]), 'ModelMetrics'[market] = \"Ames\", "
        "'ModelMetrics'[model] = \"XGBoost\")", "0.0"),
    "R2 King XGB": (
        "CALCULATE(MAX('ModelMetrics'[r2]), 'ModelMetrics'[market] = \"King County\", "
        "'ModelMetrics'[model] = \"XGBoost (tuned)\")", "0.000"),
    "R2 Ames XGB": (
        "CALCULATE(MAX('ModelMetrics'[r2]), 'ModelMetrics'[market] = \"Ames\", "
        "'ModelMetrics'[model] = \"XGBoost\")", "0.000"),
    "MAPE King Time XGB": (
        "CALCULATE(MAX('ModelMetrics'[mape]), "
        "'ModelMetrics'[market] = \"King County (chia theo thời gian)\", "
        "'ModelMetrics'[model] = \"XGBoost (tuned)\")", "0.0"),
    "Vĩ độ": ("AVERAGE('KingSales'[lat])", "0.0000"),
    "Kinh độ": ("AVERAGE('KingSales'[long])", "0.0000"),
    "Selected Budget": (
        "IF(ISFILTERED('NganSach'[Value]), MAX('NganSach'[Value]), 2000000)", "#,0"),
    "Budget Bought": (
        "VAR b = [Selected Budget]\n"
        "RETURN CALCULATE(COUNTROWS('BudgetPlan'), 'BudgetPlan'[cum_price] <= b)", "#,0"),
    "Budget Capital": (
        "VAR b = [Selected Budget]\n"
        "RETURN CALCULATE(SUM('BudgetPlan'[price]), 'BudgetPlan'[cum_price] <= b)", "#,0"),
    "Budget Upside": (
        "VAR b = [Selected Budget]\n"
        "RETURN CALCULATE(SUM('BudgetPlan'[upside_usd]), 'BudgetPlan'[cum_price] <= b)", "#,0"),
    "Chỉ số đang chọn": (
        "SWITCH(SELECTEDVALUE('ChonChiSo'[ChiSo]),\n"
        "    \"Giá trung vị nhóm\", [Candidate Median Price],\n"
        "    \"Chênh lệch kỳ vọng (USD)\", [Candidate Upside],\n"
        "    [Candidates])", "#,0"),
    "Budget Used": ("DIVIDE([Budget Capital], [Selected Budget])", "0.0%"),
    "Budget ROI": ("DIVIDE([Budget Upside], [Budget Capital])", "0.0%"),
    "SelectedBudget Text": ('FORMAT([Selected Budget], "#,##0")', None),
    "BudgetBought Text": ('FORMAT([Budget Bought], "#,##0")', None),
    "BudgetCapital Text": ('FORMAT([Budget Capital], "#,##0")', None),
    "BudgetUpside Text": ('FORMAT([Budget Upside], "#,##0")', None),
}


def measures_tmdl():
    lines = [f"table {KPI_TABLE}\n\tlineageTag: {uid()}\n"]
    for name, (dax, fmt) in MEASURES.items():
        body = "\t\t\t" + dax.replace("\n", "\n\t\t\t")
        fmt_line = f"\t\tformatString: {fmt}\n" if fmt else ""
        lines.append(
            f"\tmeasure '{name}' =\n{body}\n"
            f"{fmt_line}\t\tlineageTag: {uid()}\n")
    lines.append(
        "\tcolumn Placeholder\n\t\tdataType: string\n\t\tisHidden\n"
        f"\t\tsourceColumn: Placeholder\n\t\tlineageTag: {uid()}\n")
    lines.append(
        f"\tpartition {KPI_TABLE} = m\n\t\tmode: import\n\t\tsource =\n"
        "\t\t\tlet\n"
        "\t\t\t\tSource = #table(type table [Placeholder = text], {{\"\"}})\n"
        "\t\t\tin\n\t\t\t\tSource\n")
    return "\n".join(lines)


def write_model():
    write(MODEL_DIR / "definition.pbism",
          json.dumps({"version": "4.0", "settings": {}}, indent=2))
    write(MODEL_DIR / ".platform", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": f"{PROJECT}.SemanticModel"},
        "config": {"version": "2.0", "logicalId": uid()}}, indent=2))
    write(MODEL_DIR / "definition" / "database.tmdl",
          "database\n\tcompatibilityLevel: 1567\n")

    write(MODEL_DIR / "definition" / "expressions.tmdl",
          "/// Thư mục chứa CSV của dashboard. Đổi đường dẫn tại đây nếu chuyển máy.\n"
          f'expression DataFolder = "{DATA}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
          f"\tlineageTag: {uid()}\n\n\tannotation PBI_ResultType = Text\n")

    for csv, entity, hidden in TABLES:
        write(MODEL_DIR / "definition" / "tables" / f"{entity}.tmdl",
              table_tmdl(csv, entity, hidden))
    write(MODEL_DIR / "definition" / "tables" / f"{KPI_TABLE}.tmdl", measures_tmdl())

    write(MODEL_DIR / "definition" / "tables" / "Nguong.tmdl",
          f"table Nguong\n\tlineageTag: {uid()}\n\n"
          "\tcolumn Value\n\t\tdataType: double\n\t\tformatString: 0%\n"
          "\t\tsummarizeBy: none\n\t\tisNameInferred\n\t\tsourceColumn: [Value]\n"
          f"\t\tlineageTag: {uid()}\n\n"
          "\tpartition Nguong = calculated\n\t\tmode: import\n"
          "\t\tsource = GENERATESERIES(0.05, 0.50, 0.01)\n")

    # Tham số ngân sách (what-if thứ 2).
    write(MODEL_DIR / "definition" / "tables" / "NganSach.tmdl",
          f"table NganSach\n\tlineageTag: {uid()}\n\n"
          "\tcolumn Value\n\t\tdataType: double\n\t\tformatString: #,0\n"
          "\t\tsummarizeBy: none\n\t\tisNameInferred\n\t\tsourceColumn: [Value]\n"
          f"\t\tlineageTag: {uid()}\n\n"
          "\tpartition NganSach = calculated\n\t\tmode: import\n"
          "\t\tsource = GENERATESERIES(500000, 10000000, 250000)\n")

    # Bảng chọn chỉ số cho biểu đồ: nhập từ CSV như các bảng khác (bảng tính DAX
    # và field parameter NAMEOF đều bị Power BI báo lỗi trong project này).

    refs = "\n".join(f"ref table {t[1]}" for t in TABLES)
    query_order = ", ".join(json.dumps(t[1], ensure_ascii=False) for t in TABLES)
    write(MODEL_DIR / "definition" / "model.tmdl",
          "model Model\n\tculture: en-US\n"
          "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
          "\tdiscourageImplicitMeasures\n\tsourceQueryCulture: en-US\n\n"
          f"\tannotation PBI_QueryOrder = [{query_order}]\n\n"
          "\tannotation __PBI_TimeIntelligenceEnabled = 0\n\n"
          f"{refs}\nref table {KPI_TABLE}\nref table Nguong\nref table NganSach\n"
          "ref table ChonChiSo\n\nref cultureInfo en-US\n")


# ---------------------------------------------------------------- report
DISPLAY = {
    "King Transactions": "Số giao dịch",
    "King Median Price": "Giá trung vị",
    "King OOF MAPE": "MAPE OOF",
    "Candidates": "Ứng viên",
    "Candidate Share": "Tỷ lệ ứng viên",
    "Candidate Upside": "Chênh lệch (USD)",
    "Candidate Median Price": "Giá trung vị",
    "Candidate All3": "Đồng thuận 3 mô hình",
    "Top20 Capital": "Vốn (USD)",
    "Top20 Upside": "Chênh lệch (USD)",
    "Top20 Median Discount": "Giảm (%)",
    "Top20 All3": "Đồng thuận",
    "Ames Properties": "Số tài sản",
    "Ames Median Price": "Giá trung vị",
    "Ames OOF MAPE": "MAPE OOF",
    "Ames Candidates": "Ứng viên",
    "Selected Threshold": "Ngưỡng",
    "zip_top": "Mã ZIP",
    "price_band": "Khúc giá",
    "zipcode": "ZIP",
    "price": "Giá bán",
    "predicted_price": "Giá mô hình",
    "upside_usd": "Chênh lệch",
    "discount_pct": "Giảm (%)",
    "sqft_living": "Diện tích (sqft)",
    "grade": "Hạng chất lượng",
    "condition": "Tình trạng",
    "distance_to_center_km": "Cách trung tâm (km)",
    "Hang": "Hạng",
    "id": "ID",
    "segment": "Khúc giá",
    "mape_lr": "MAPE Linear",
    "mape_xgb": "MAPE XGBoost",
    "variant": "Kịch bản",
    "overlap_20": "Trùng 20 căn",
    "share_pct": "Tỷ lệ (%)",
    "feature": "Biến",
    "scenario": "Kịch bản",
    "threshold_pct": "Ngưỡng (%)",
    "candidates": "Số ứng viên",
    "mape_increase_pp": "MAPE tăng (điểm %)",
    "median_change_pct": "Thay đổi (%)",
    "discount_flag": "Nhóm định giá",
    "Vĩ độ": "Vĩ độ",
    "Kinh độ": "Kinh độ",
    "waterfront": "Giáp nước",
    "view": "Hướng nhìn",
    "is_renovated": "Đã cải tạo",
    "bedrooms": "Phòng ngủ",
    "house_age": "Tuổi nhà",
    "undervalued_20pct": "Cờ định giá thấp",
    "models_agree_undervalued": "Số mô hình đồng ý",
    "Selected Budget": "Ngân sách",
    "Budget Bought": "Căn mua được",
    "Budget Capital": "Vốn sử dụng",
    "Budget Upside": "Chênh lệch kỳ vọng",
    "Budget Used": "% ngân sách đã dùng",
    "Budget ROI": "ROI kỳ vọng",
    "ChiSo": "Chỉ số",
}


def col(entity, prop, native=None):
    return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}},
                                 "Property": prop}},
            "queryRef": f"{entity}.{prop}",
            "nativeQueryRef": native or DISPLAY.get(prop, prop)}


def meas(entity, prop, native=None):
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}},
                                  "Property": prop}},
            "queryRef": f"{entity}.{prop}",
            "nativeQueryRef": native or DISPLAY.get(prop, prop)}


def container(title=None):
    c = {
        "background": [{"properties": {
            "show": {"expr": {"Literal": {"Value": "true"}}},
            "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#FFFFFF'"}}}}},
            "transparency": {"expr": {"Literal": {"Value": "0D"}}},
        }}],
        "border": [{"properties": {
            "show": {"expr": {"Literal": {"Value": "true"}}},
            "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#DCE6F0'"}}}}},
            "radius": {"expr": {"Literal": {"Value": "8D"}}},
        }}],
        "padding": [{"properties": {
            "top": {"expr": {"Literal": {"Value": "8D"}}},
            "bottom": {"expr": {"Literal": {"Value": "8D"}}},
            "left": {"expr": {"Literal": {"Value": "10D"}}},
            "right": {"expr": {"Literal": {"Value": "10D"}}},
        }}],
        "visualHeader": [{"properties": {
            "show": {"expr": {"Literal": {"Value": "false"}}},
        }}],
    }
    if title:
        c["title"] = [{"properties": {
            "text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
            "show": {"expr": {"Literal": {"Value": "true"}}},
            "fontSize": {"expr": {"Literal": {"Value": "11D"}}},
            "bold": {"expr": {"Literal": {"Value": "true"}}},
            "fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#12324F'"}}}}},
        }}]
    return c


def visual(name, kind, x, y, w, h, roles, title, extra_objects=None):
    query_state = {role: {"projections": projs} for role, projs in roles.items()}
    objects = extra_objects or {}
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": 1, "width": w, "height": h, "tabOrder": 1},
        "visual": {"visualType": kind,
                   "query": {"queryState": query_state,
                             "sortDefinition": {"sort": [], "isDefaultSort": True}},
                   "drillFilterOtherVisuals": True,
                   "visualContainerObjects": container(title),
                   "objects": objects},
    }


def textbox(name, x, y, w, h, paragraphs):
    """paragraphs: list of (text, size_pt, bold, color)."""
    runs = []
    for text, size, bold, color in paragraphs:
        style = {"fontSize": f"{size}pt", "color": color}
        if bold:
            style["fontWeight"] = "bold"
        runs.append({"textRuns": [{"value": text, "textStyle": style}]})
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": 1, "width": w, "height": h, "tabOrder": 1},
        "visual": {"visualType": "textbox",
                   "objects": {"general": [{"properties": {"paragraphs": runs}}]},
                   "drillFilterOtherVisuals": True,
                   "visualContainerObjects": container()},
    }


def add(page_dir, v):
    write(page_dir / "visuals" / v["name"] / "visual.json",
          json.dumps(v, ensure_ascii=False, indent=2))


def page_nav(name, x=16, y=664, w=1248, h=48):
    """Dải điều hướng: tự liệt kê mọi trang của báo cáo."""
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": 1, "width": w, "height": h, "tabOrder": 1},
        "visual": {"visualType": "pageNavigator",
                   "visualContainerObjects": container(),
                   "objects": {}},
    }


PAGES = [
    ("tong_quan", "1. Tổng quan King County"),
    ("what_if", "2. What-if ngưỡng undervalued"),
    ("ngan_sach", "3. Ngân sách và kế hoạch mua"),
    ("top20", "4. 20 căn đề xuất"),
    ("ames", "5. So sánh Ames"),
    ("mo_hinh", "6. Mô hình và độ nhạy"),
    ("ban_do", "7. Bản đồ ứng viên"),
    ("yeu_to", "8. Yếu tố ảnh hưởng"),
    ("phuong_phap", "9. Phương pháp và định nghĩa"),
]


def build_report():
    write(REPORT_DIR / ".platform", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": PROJECT},
        "config": {"version": "2.0", "logicalId": uid()}}, indent=2))
    theme = {
        "name": "NhiemVu5",
        "dataColors": ["#1F6FB2", "#E4572E", "#2A9D8F", "#E9C46A", "#7B61A8", "#6C757D",
                       "#457B9D", "#F4A261"],
        "foreground": "#1B2A3A",
        "foregroundNeutralSecondary": "#5A6B7B",
        "background": "#FFFFFF",
        "backgroundLight": "#F4F7FB",
        "tableAccent": "#1F6FB2",
        "good": "#2A9D8F", "neutral": "#E9C46A", "bad": "#E4572E",
        "textClasses": {
            "callout": {"fontSize": 34, "fontFace": "Segoe UI Semibold", "color": "#12324F"},
            "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": "#12324F"},
            "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": "#12324F"},
            "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": "#4A5A6A"},
        },
        "visualStyles": {
            "card": {"*": {
                "labels": [{"fontSize": 28, "bold": True,
                            "color": {"solid": {"color": "#12324F"}}}],
                "categoryLabels": [{"fontSize": 10,
                                    "color": {"solid": {"color": "#5A6B7B"}}}]}},
            "barChart": {"*": {
                "labels": [{"show": True, "fontSize": 8}],
                "categoryAxis": [{"fontSize": 8}],
                "valueAxis": [{"fontSize": 8}]}},
            "clusteredColumnChart": {"*": {
                "labels": [{"show": True, "fontSize": 8}],
                "categoryAxis": [{"fontSize": 8}],
                "valueAxis": [{"fontSize": 8}]}},
            "tableEx": {"*": {
                "columnHeaders": [{"fontSize": 9, "bold": True,
                                   "fontColor": {"solid": {"color": "#FFFFFF"}},
                                   "backColor": {"solid": {"color": "#1F6FB2"}}}],
                "values": [{"fontSize": 9}]}},
            "slicer": {"*": {"items": [{"fontSize": 9}], "header": [{"fontSize": 9}]}},
        },
    }
    write(REPORT_DIR / "StaticResources" / "RegisteredResources" / "ThemeNhiemVu5.json",
          json.dumps(theme, ensure_ascii=False, indent=2))
    write(REPORT_DIR / "definition.pbir", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{PROJECT}.SemanticModel"}}}, indent=2))
    write(REPORT_DIR / "definition" / "version.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"}, indent=2))
    write(REPORT_DIR / "definition" / "report.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.3.0/schema.json",
        "layoutOptimization": "None",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU06", "reportVersionAtImport": "5.55",
                          "type": "SharedResources"},
            "customTheme": {"name": "ThemeNhiemVu5.json", "reportVersionAtImport": "5.64",
                            "type": "RegisteredResources"}},
        "resourcePackages": [{
            "name": "RegisteredResources", "type": "RegisteredResources",
            "items": [{"name": "ThemeNhiemVu5.json", "path": "ThemeNhiemVu5.json",
                       "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True}}, indent=2))
    write(REPORT_DIR / "definition" / "pages" / "pages.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [p[0] for p in PAGES], "activePageName": PAGES[0][0]}, indent=2))
    for name, display in PAGES:
        write(REPORT_DIR / "definition" / "pages" / name / "page.json", json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.4.0/schema.json",
            "name": name, "displayName": display, "displayOption": "FitToPage",
            "height": 720, "width": 1280,
            "objects": {"background": [{"properties": {
                "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#F4F7FB'"}}}}}}}]}},
            ensure_ascii=False, indent=2))
    return REPORT_DIR / "definition" / "pages"


def card(name, x, y, w, h, entity, measure, title):
    v = visual(name, "card", x, y, w, h, {"Values": [meas(entity, measure)]}, title)
    v["visual"]["objects"]["categoryLabels"] = [{"properties": {
        "show": {"expr": {"Literal": {"Value": "false"}}}}}]
    v["visual"]["objects"]["labels"] = [{"properties": {
        "labelDisplayUnits": {"expr": {"Literal": {"Value": "0D"}}}}}]
    return v


def build_pages():
    pages = build_report()

    # ---- Trang 1
    p = pages / "tong_quan"
    add(p, card("k_tx", 16, 16, 300, 100, KPI_TABLE, "KingTx Text", "Tổng giao dịch"))
    add(p, card("k_med", 332, 16, 300, 100, KPI_TABLE, "KingMedian Text", "Giá trung vị (USD)"))
    add(p, card("k_mape", 648, 16, 300, 100, KPI_TABLE, "King OOF MAPE", "MAPE out-of-fold"))
    add(p, card("k_cand", 964, 16, 300, 100, KPI_TABLE, "Candidates Text", "Ứng viên tại ngưỡng 20%"))
    add(p, visual("c_band", "clusteredColumnChart", 16, 132, 624, 260,
                  {"Category": [col("KingSales", "price_band")],
                   "Y": [meas(KPI_TABLE, "King Transactions")]},
                  "Số giao dịch theo khúc giá"))
    bz = visual("b_zip", "barChart", 648, 132, 616, 260,
                {"Category": [col("KingSales", "zipcode")],
                 "Y": [meas(KPI_TABLE, "King Transactions")]},
                "Top 12 ZIP theo số giao dịch")
    bz["visual"]["objects"]["labels"] = [{"properties": {
        "show": {"expr": {"Literal": {"Value": "false"}}}}}]
    add(p, bz)
    add(p, visual("t_zip", "tableEx", 16, 408, 1248, 248,
                  {"Values": [col("KingSales", "zip_top"),
                              meas(KPI_TABLE, "King Transactions"),
                              meas(KPI_TABLE, "King Median Price"),
                              meas(KPI_TABLE, "Candidate Share")]},
                  "ZIP: quy mô và tỷ lệ ứng viên"))
    add(p, page_nav("nav_trang"))

    # ---- Trang 2
    p = pages / "what_if"
    slicer = visual("s_nguong", "slicer", 16, 16, 300, 150,
                    {"Values": [col("Nguong", "Value")]},
                    "Ngưỡng undervalued (kéo đầu trái, 5%–50%)")
    slicer["visual"]["objects"] = {
        "data": [{"properties": {
            "mode": {"expr": {"Literal": {"Value": "'Between'"}}},
            "start": {"expr": {"Literal": {"Value": "0.20D"}}},
            "end": {"expr": {"Literal": {"Value": "0.51D"}}},
        }}],
        "general": [{"properties": {"filter": {"filter": {
            "Version": 2,
            "From": [{"Name": "n", "Entity": "Nguong", "Type": 0}],
            "Where": [{"Condition": {"Between": {
                "Expression": {"Column": {
                    "Expression": {"SourceRef": {"Source": "n"}},
                    "Property": "Value"}},
                "LowerBound": {"Literal": {"Value": "0.20D"}},
                "UpperBound": {"Literal": {"Value": "0.51D"}},
            }}}],
        }}}}],
    }
    add(p, slicer)
    add(p, card("w_thr", 16, 174, 300, 92, KPI_TABLE, "Selected Threshold", "Ngưỡng đang áp dụng"))
    add(p, card("w_cand", 332, 16, 456, 84, KPI_TABLE, "Candidates Text", "Số căn ứng viên"))
    add(p, card("w_share", 804, 16, 456, 84, KPI_TABLE, "Candidate Share", "Tỷ lệ ứng viên"))
    add(p, card("w_up", 332, 108, 456, 84, KPI_TABLE, "CandidateUpside Text", "Tổng chênh lệch (USD)"))
    add(p, card("w_med", 804, 108, 456, 84, KPI_TABLE, "CandidateMedian Text", "Giá trung vị nhóm"))
    add(p, visual("w_zip", "barChart", 16, 276, 612, 210,
                  {"Category": [col("KingSales", "zipcode")],
                   "Y": [meas(KPI_TABLE, "Candidates")]},
                  "Ứng viên theo ZIP"))
    add(p, visual("w_band", "clusteredColumnChart", 644, 276, 620, 210,
                  {"Category": [col("KingSales", "price_band")],
                   "Y": [meas(KPI_TABLE, "Candidates")]},
                  "Ứng viên theo khúc giá"))
    add(p, visual("w_tbl", "tableEx", 16, 496, 1248, 208,
                  {"Values": [col("KingSales", "zip_top"),
                              meas(KPI_TABLE, "Candidates"),
                              meas(KPI_TABLE, "Candidate Share"),
                              meas(KPI_TABLE, "Candidate Upside"),
                              meas(KPI_TABLE, "Candidate All3")]},
                  "Tổng hợp ứng viên theo ZIP"))

    # ---- Trang 3: ngân sách (what-if thứ 2)
    p = pages / "ngan_sach"
    bud = visual("s_budget", "slicer", 16, 16, 372, 150,
                 {"Values": [col("NganSach", "Value")]},
                 "Ngân sách mua (USD, kéo đầu phải)")
    bud["visual"]["objects"] = {
        "data": [{"properties": {
            "mode": {"expr": {"Literal": {"Value": "'Between'"}}},
            "start": {"expr": {"Literal": {"Value": "500000D"}}},
            "end": {"expr": {"Literal": {"Value": "2000000D"}}},
        }}],
        "general": [{"properties": {"filter": {"filter": {
            "Version": 2,
            "From": [{"Name": "b", "Entity": "NganSach", "Type": 0}],
            "Where": [{"Condition": {"Between": {
                "Expression": {"Column": {
                    "Expression": {"SourceRef": {"Source": "b"}},
                    "Property": "Value"}},
                "LowerBound": {"Literal": {"Value": "500000D"}},
                "UpperBound": {"Literal": {"Value": "2000000D"}},
            }}}],
        }}}}],
    }
    add(p, bud)

    met = visual("s_metric", "slicer", 16, 182, 372, 150,
                 {"Values": [col("ChonChiSo", "ChiSo")]},
                 "Chọn chỉ số cho biểu đồ theo ZIP")
    met["visual"]["objects"] = {
        "data": [{"properties": {
            "mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}}}],
    }
    add(p, met)

    add(p, card("b_budget", 400, 16, 280, 72, KPI_TABLE, "SelectedBudget Text", "Ngân sách đang chọn (USD)"))
    add(p, card("b_units", 692, 16, 280, 72, KPI_TABLE, "BudgetBought Text", "Số căn mua được"))
    add(p, card("b_cap", 984, 16, 280, 72, KPI_TABLE, "BudgetCapital Text", "Vốn sử dụng (USD)"))
    add(p, card("b_up", 400, 96, 280, 70, KPI_TABLE, "BudgetUpside Text", "Chênh lệch kỳ vọng (USD)"))
    add(p, card("b_used", 692, 96, 280, 70, KPI_TABLE, "Budget Used", "% ngân sách đã dùng"))
    add(p, card("b_roi", 984, 96, 280, 70, KPI_TABLE, "Budget ROI", "ROI kỳ vọng trên vốn"))

    add(p, visual("bud_zip", "barChart", 400, 178, 864, 300,
                  {"Category": [col("KingSales", "zipcode")],
                   "Y": [meas(KPI_TABLE, "Chỉ số đang chọn")]},
                  "Ứng viên theo ZIP (chỉ số do người dùng chọn)"))

    add(p, textbox("b_note", 16, 348, 372, 356, [
        ("Cách tính kế hoạch mua", 15, True, "#12324F"),
        ("Ngân sách là tổng vốn, không phải giá một căn. Ứng viên được xếp theo mức giảm "
         "sâu nhất rồi mua lần lượt đến khi hết ngân sách; chỉ xét giao dịch giảm ≤ 50% "
         "(các giao dịch giảm sâu hơn cần xác minh thủ công).", 12, False, "#1B2A3A"),
        ("Mặc định 2.000.000 USD, ngưỡng 20%: mua được 8 căn, vốn 1.809.500 USD, "
         "chênh lệch kỳ vọng 1.758.645 USD, dùng 90,5% ngân sách.", 12, False, "#1B2A3A"),
        ("Đổi ngân sách ở thanh trượt trên: số căn và vốn cập nhật ngay. ROI giảm dần khi "
         "mua nhiều vì danh sách phải lùi xuống các căn giảm ít hơn.", 12, False, "#1B2A3A"),
    ]))
    add(p, textbox("b_insight", 400, 490, 864, 214, [
        ("Ngân sách so với kết quả", 15, True, "#12324F"),
        ("1.000.000 USD → 4 căn · ROI 99,0%. 5.000.000 USD → 23 căn · ROI 92,0%. "
         "10.000.000 USD → 43 căn · ROI 84,8%.", 12, False, "#1B2A3A"),
        ("Vì giá trung vị nhóm ứng viên khoảng 285.000 USD, mỗi 1 triệu USD chỉ mua được "
         "3–5 căn: danh sách ứng viên không đủ dày để hấp thụ ngân sách lớn, nên tăng vốn "
         "nhanh hơn tăng số căn.", 12, False, "#1B2A3A"),
        ("Nút “Chọn chỉ số” đổi biểu đồ giữa số ứng viên, tỷ lệ ứng viên và giá trung vị "
         "theo từng ZIP, giúp chọn khu vực trước khi khảo sát.", 12, False, "#1B2A3A"),
    ]))

    # ---- Trang 4
    p = pages / "top20"
    add(p, card("t_cap", 16, 16, 300, 100, KPI_TABLE, "Top20Capital Text", "Tổng vốn 20 căn (USD)"))
    add(p, card("t_up", 332, 16, 300, 100, KPI_TABLE, "Top20Upside Text", "Chênh lệch kỳ vọng (USD)"))
    add(p, card("t_disc", 648, 16, 300, 100, KPI_TABLE, "Top20 Median Discount", "Mức giảm trung vị (%)"))
    add(p, card("t_all", 964, 16, 300, 100, KPI_TABLE, "Top20All3 Text", "Cả 3 mô hình đồng ý"))
    add(p, visual("t20", "tableEx", 16, 132, 1248, 384,
                  {"Values": [col("Top20", "Hang"), col("Top20", "id"),
                              col("Top20", "zipcode"), col("Top20", "price"),
                              col("Top20", "predicted_price"), col("Top20", "upside_usd"),
                              col("Top20", "discount_pct"), col("Top20", "sqft_living"),
                              col("Top20", "grade"), col("Top20", "condition"),
                              col("Top20", "distance_to_center_km")]},
                  "20 căn đề xuất (xếp theo mức giảm thận trọng)"))
    add(p, visual("t3_zip", "barChart", 16, 528, 1248, 176,
                  {"Category": [col("Top20", "zipcode")],
                   "Y": [meas(KPI_TABLE, "Top20 Upside")]},
                  "Chênh lệch kỳ vọng theo ZIP"))

    # ---- Trang 5
    p = pages / "ames"
    add(p, card("a_n", 16, 16, 300, 100, KPI_TABLE, "AmesProperties Text", "Số tài sản Ames"))
    add(p, card("a_med", 332, 16, 300, 100, KPI_TABLE, "AmesMedian Text", "Giá trung vị Ames (USD)"))
    add(p, card("a_mape", 648, 16, 300, 100, KPI_TABLE, "Ames OOF MAPE", "MAPE out-of-fold Ames"))
    add(p, card("a_cand", 964, 16, 300, 100, KPI_TABLE, "AmesCandidates Text", "Ames: ứng viên tại ngưỡng 20%"))
    add(p, visual("a_model", "clusteredColumnChart", 16, 132, 624, 260,
                  {"Category": [col("ModelCompare", "model")],
                   "Series": [col("ModelCompare", "market")],
                   "Y": [meas(KPI_TABLE, "Model MAPE")]},
                  "MAPE theo mô hình: King vs Ames (%)"))
    add(p, visual("a_nb", "barChart", 648, 132, 616, 260,
                  {"Category": [col("AmesSales", "neighborhood_top")],
                   "Y": [meas(KPI_TABLE, "Ames Median Price")]},
                  "Giá trung vị theo khu dân cư Ames"))
    add(p, visual("a_band", "clusteredColumnChart", 16, 408, 624, 296,
                  {"Category": [col("AmesSales", "price_band")],
                   "Y": [meas(KPI_TABLE, "Ames Properties")]},
                  "Số tài sản Ames theo khúc giá"))
    add(p, visual("a_seg", "tableEx", 648, 408, 616, 296,
                  {"Values": [col("SegmentCompare", "segment"),
                              col("SegmentCompare", "mape_lr"),
                              col("SegmentCompare", "mape_xgb")]},
                  "MAPE theo khúc giá King: Linear vs XGBoost"))

    # ---- Trang 6
    p = pages / "mo_hinh"
    add(p, visual("m_imp", "barChart", 16, 16, 612, 340,
                  {"Category": [col("ImportanceTop", "feature")],
                   "Y": [meas(KPI_TABLE, "Importance Increase")]},
                  "12 biến quan trọng nhất (MAPE tăng thêm, điểm %)"))
    add(p, visual("m_whatif", "barChart", 648, 16, 616, 340,
                  {"Category": [col("WhatIfScenarios", "scenario")],
                   "Y": [meas(KPI_TABLE, "Scenario Change")]},
                  "What-if: đổi một đặc điểm, giá đổi bao nhiêu %"))
    add(p, visual("m_thr", "clusteredColumnChart", 16, 372, 612, 332,
                  {"Category": [col("Sensitivity", "threshold_pct")],
                   "Y": [meas(KPI_TABLE, "Sensitivity Candidates")]},
                  "Số ứng viên theo ngưỡng (%)"))
    add(p, visual("m_stab", "tableEx", 648, 372, 616, 332,
                  {"Values": [col("Stability", "variant"),
                              col("Stability", "overlap_20"),
                              col("Stability", "share_pct")]},
                  "Độ ổn định của danh sách 20 căn"))

    # ---- Trang 7: bản đồ
    # Không dùng visual "map" vì nó phụ thuộc tùy chọn bảo mật "Use map and filled map
    # visuals" (mặc định tắt) — tọa độ thật vẫn vẽ được bằng scatter nên chạy ở mọi máy.
    p = pages / "ban_do"
    mp = visual("map_cand", "scatterChart", 16, 16, 1248, 452,
                {"X": [meas(KPI_TABLE, "Kinh độ")],
                 "Y": [meas(KPI_TABLE, "Vĩ độ")],
                 "Size": [meas(KPI_TABLE, "Candidates")],
                 "Category": [col("KingSales", "zipcode")],
                 "Tooltips": [meas(KPI_TABLE, "Candidate Median Price")]},
                "Ứng viên theo vị trí (mỗi điểm = 1 ZIP, kích thước = số ứng viên)")
    mp["visual"]["objects"] = {
        name: [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]
        for name in ("xAxis", "yAxis", "categoryAxis", "valueAxis", "legend")}
    add(p, mp)
    add(p, textbox("map_note", 16, 480, 1248, 224, [
        ("Đọc bản đồ", 15, True, "#12324F"),
        ("Mỗi bong bóng là một mã ZIP; kích thước theo số căn ứng viên ở ngưỡng đang chọn "
         "(mặc định 20%: 1.193 căn trên phạm vi 21.229 giao dịch). Di chuột lên bong bóng để xem "
         "giá trung vị của nhóm ứng viên trong ZIP đó.", 12, False, "#1B2A3A"),
        ("Kết quả 20%: 98118 dẫn đầu với 60 căn, tiếp theo 98106 (41), 98168 (34), 98103 (33), "
         "98146 (32), 98198 (32). Sáu ZIP này chiếm 19,4% tổng số ứng viên; phần còn lại rải trên "
         "64 ZIP khác, mỗi ZIP dưới 30 căn.", 12, False, "#1B2A3A"),
        ("Vì sao quan trọng: cùng một ngưỡng nhưng mật độ ứng viên lệch hẳn giữa các khu — "
         "gợi ý rằng cơ hội tập trung theo khu vực chứ không rải đều, nên khảo sát thực địa theo cụm "
         "sẽ hiệu quả hơn đi từng căn lẻ.", 12, False, "#1B2A3A"),
    ]))

    # ---- Trang 8: yếu tố ảnh hưởng
    # (Key Influencers là visual đóng gói riêng, PBIP không có resource .pbiviz nên
    #  dùng tỷ lệ ứng viên theo phân khúc — cùng nội dung, tự tính, chạy mọi máy.)
    p = pages / "yeu_to"
    add(p, visual("dtree", "decompositionTreeVisual", 16, 16, 616, 688,
                  {"Analyze": [meas(KPI_TABLE, "Candidates")],
                   "ExplainBy": [dict(col("KingSales", f), active=True) for f in
                                 ("zip_top", "price_band", "grade", "waterfront",
                                  "view", "condition", "is_renovated", "sqft_living")]},
                  "Phân rã số ứng viên theo thuộc tính"))
    add(p, visual("yt_grade", "barChart", 648, 16, 616, 330,
                  {"Category": [col("KingSales", "grade")],
                   "Y": [meas(KPI_TABLE, "Candidate Share")]},
                  "Tỷ lệ ứng viên theo hạng chất lượng (%)"))
    add(p, visual("yt_view", "barChart", 648, 358, 616, 346,
                  {"Category": [col("KingSales", "view")],
                   "Y": [meas(KPI_TABLE, "Candidate Share")]},
                  "Tỷ lệ ứng viên theo hướng nhìn (%)"))

    # ---- Trang 9: phương pháp
    p = pages / "phuong_phap"
    add(p, textbox("pp_quy_trinh", 16, 16, 616, 372, [
        ("Quy trình", 16, True, "#12324F"),
        ("1. Dữ liệu: King County house sales 2014–2015, 21.612 giao dịch; Ames 2.930 tài sản "
         "(chỉ dùng để kiểm chứng).", 12.5, False, "#1B2A3A"),
        ("2. Phạm vi ứng viên: is_latest_sale = 1, zero_room_flag = 0, condition ≥ 3 "
         "→ 21.229 giao dịch.", 12.5, False, "#1B2A3A"),
        ("3. Đặc trưng: diện tích, hạng chất lượng, tình trạng, tuổi nhà, số phòng, hướng nhìn, "
         "giáp nước, khoảng cách trung tâm, ZIP.", 12.5, False, "#1B2A3A"),
        ("4. Mô hình: Linear Regression, Random Forest, XGBoost (tuned) trên log giá; "
         "GroupKFold 5 theo id để tránh rò rỉ khi cùng một căn được bán nhiều lần.", 12.5, False, "#1B2A3A"),
        ("5. Chấm điểm: dự báo out-of-fold cho từng giao dịch — mỗi căn chỉ được dự báo bởi mô hình "
         "không thấy căn đó khi huấn luyện.", 12.5, False, "#1B2A3A"),
        ("6. Xếp hạng: residual_pct ≤ −ngưỡng là ứng viên; ưu tiên căn cả 3 mô hình đồng ý, "
         "xếp theo mức giảm thận trọng nhất.", 12.5, False, "#1B2A3A"),
    ]))
    add(p, textbox("pp_dinh_nghia", 648, 16, 616, 372, [
        ("Định nghĩa", 16, True, "#12324F"),
        ("residual_pct = (giá bán − giá mô hình) / giá mô hình. Giá trị âm nghĩa là bán dưới "
         "giá mô hình dự báo.", 12.5, False, "#1B2A3A"),
        ("Ứng viên = residual_pct ≤ −ngưỡng, tính trong phạm vi 21.229 giao dịch nêu trên.", 12.5, False, "#1B2A3A"),
        ("upside_usd = giá mô hình − giá bán: chênh lệch kỳ vọng tính bằng USD.", 12.5, False, "#1B2A3A"),
        ("discount_pct = mức giảm theo mô hình bảo thủ nhất trong 3 mô hình (%).", 12.5, False, "#1B2A3A"),
        ("Đồng thuận = cả 3 mô hình cùng gắn cờ định giá thấp tại ngưỡng đang chọn.", 12.5, False, "#1B2A3A"),
        ("Top 20 = 20 căn giảm sâu nhất theo discount_pct; 36 giao dịch giảm trên 50% bị loại "
         "sang danh sách cần xác minh thủ công.", 12.5, False, "#1B2A3A"),
        ("Ngưỡng = tham số What-if, thanh trượt 5%–50% bước 1%; mặc định 20%.", 12.5, False, "#1B2A3A"),
    ]))
    add(p, textbox("pp_kiem_chung", 16, 396, 1248, 308, [
        ("Đo lường và giới hạn", 16, True, "#12324F"),
        ("Chất lượng mô hình (tập test): XGBoost King County MAPE 11,20% · RMSE 106.477 USD · R² 0,918; "
         "out-of-fold MAPE 10,94%. Ames MAPE 7,49% · R² 0,935; out-of-fold 7,90%.", 12.5, False, "#1B2A3A"),
        ("Độ nhạy của ngưỡng: 5% → 6.248 căn (29,4%); 10% → 3.672 (17,3%); 15% → 2.132 (10,0%); "
         "20% → 1.193 (5,6%); 25% → 677 (3,2%); 30% → 411 (1,9%); 35% → 209 (1,0%); 40% → 106 (0,5%).", 12.5, False, "#1B2A3A"),
        ("Giới hạn: (1) “định giá thấp” chỉ là proxy theo sai số mô hình khoảng 11%, không chứng minh "
         "chủ nhà định giá sai; (2) dữ liệu 2014–2015, không phải giá thị trường hiện tại; "
         "(3) chưa có thông tin pháp lý, hiện trạng và quy hoạch; (4) 36 giao dịch giảm trên 50% "
         "phải xác minh thủ công trước khi dùng.", 12.5, False, "#1B2A3A"),
    ]))


KIND_LABEL = {
    "card": "Thẻ số liệu",
    "cardVisual": "Thẻ số liệu",
    "barChart": "Biểu đồ thanh",
    "clusteredColumnChart": "Biểu đồ cột",
    "columnChart": "Biểu đồ cột",
    "tableEx": "Bảng dữ liệu",
    "slicer": "Bộ lọc",
    "scatterChart": "Biểu đồ phân tán theo tọa độ",
    "decompositionTreeVisual": "Cây phân rã",
    "pageNavigator": "Điều hướng trang",
    "textbox": "Hộp văn bản",
}


def _literal(text):
    return {"expr": {"Literal": {"Value": "'" + text.replace("'", "''") + "'"}}}


def decorate_visuals(pages):
    """Alt text + thứ tự tab đọc được cho toàn bộ visual (trợ năng)."""
    for page_dir in pages.iterdir():
        items = []
        for f in page_dir.glob("visuals/*/visual.json"):
            v = json.loads(f.read_text(encoding="utf-8"))
            items.append((round(v["position"]["y"] / 40), v["position"]["x"], f, v))
        items.sort(key=lambda t: (t[0], t[1]))
        for i, (_, _, f, v) in enumerate(items):
            v["position"]["tabOrder"] = i
            vis = v["visual"]
            title = ""
            objs = vis.setdefault("visualContainerObjects", {})
            if "title" in objs:
                title = objs["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"].strip("'")
            elif vis["visualType"] == "textbox":
                title = vis["objects"]["general"][0]["properties"]["paragraphs"][0][
                    "textRuns"][0]["value"][:90]
            label = KIND_LABEL.get(vis["visualType"], "Biểu đồ")
            alt = f"{label}: {title}" if title else label
            general = objs.setdefault("general", [{"properties": {}}])
            general[0]["properties"]["altText"] = _literal(alt)
            f.write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")


BOOKMARKS = [
    ("che_do_nha_dau_tu", "Chế độ nhà đầu tư: ngân sách và danh mục", "ngan_sach"),
    ("che_do_hoc_thuat", "Chế độ học thuật: mô hình và phương pháp", "phuong_phap"),
]


def write_bookmarks():
    """2 bookmark = 2 chế độ xem, mỗi chế độ mở thẳng trang tương ứng."""
    folder = REPORT_DIR / "definition" / "bookmarks"
    folder.mkdir(parents=True, exist_ok=True)
    for name, display, page in BOOKMARKS:
        write(folder / f"{name}.bookmark.json", json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/"
                       "definition/bookmark/1.3.0/schema.json",
            "displayName": display,
            "name": name,
            "explorationState": {"version": "1.3", "activeSection": page,
                                 "sections": {page: {"visualContainers": {}}}}}, ensure_ascii=False, indent=2))
    write(folder / "bookmarks.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/"
                   "definition/bookmarksMetadata/1.0.0/schema.json",
        "items": [{"name": name} for name, _, _ in BOOKMARKS]}, indent=2))


def main():
    write(OUT / f"{PROJECT}.pbip", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{PROJECT}.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2))
    write_budget_plan()
    write_metric_choices()
    write_model()
    build_pages()
    decorate_visuals(REPORT_DIR / "definition" / "pages")
    write_bookmarks()
    print("Đã sinh PBIP:", OUT / f"{PROJECT}.pbip")


if __name__ == "__main__":
    main()
