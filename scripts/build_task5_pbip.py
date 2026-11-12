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

    refs = "\n".join(f"ref table {t[1]}" for t in TABLES)
    query_order = ", ".join(json.dumps(t[1], ensure_ascii=False) for t in TABLES)
    write(MODEL_DIR / "definition" / "model.tmdl",
          "model Model\n\tculture: en-US\n"
          "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
          "\tdiscourageImplicitMeasures\n\tsourceQueryCulture: en-US\n\n"
          f"\tannotation PBI_QueryOrder = [{query_order}]\n\n"
          "\tannotation __PBI_TimeIntelligenceEnabled = 0\n\n"
          f"{refs}\nref table {KPI_TABLE}\nref table Nguong\n\nref cultureInfo en-US\n")


# ---------------------------------------------------------------- report
def col(entity, prop, native=None):
    return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}},
                                 "Property": prop}},
            "queryRef": f"{entity}.{prop}", "nativeQueryRef": native or prop}


def meas(entity, prop, native=None):
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}},
                                  "Property": prop}},
            "queryRef": f"{entity}.{prop}", "nativeQueryRef": native or prop}


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
                   "visualContainerObjects": {"title": [{"properties": {
                       "text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
                       "show": {"expr": {"Literal": {"Value": "true"}}}}}]},
                   "objects": objects},
    }


def add(page_dir, v):
    write(page_dir / "visuals" / v["name"] / "visual.json",
          json.dumps(v, ensure_ascii=False, indent=2))


PAGES = [
    ("tong_quan", "1. Tổng quan King County"),
    ("what_if", "2. What-if ngưỡng undervalued"),
    ("top20", "3. 20 căn đề xuất"),
    ("ames", "4. So sánh Ames"),
    ("mo_hinh", "5. Mô hình và độ nhạy"),
]


def build_report():
    write(REPORT_DIR / ".platform", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": PROJECT},
        "config": {"version": "2.0", "logicalId": uid()}}, indent=2))
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
        "themeCollection": {"baseTheme": {
            "name": "CY24SU06", "reportVersionAtImport": "5.55",
            "type": "SharedResources"}},
        "settings": {"useStylableVisualContainerHeader": True}}, indent=2))
    write(REPORT_DIR / "definition" / "pages" / "pages.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [p[0] for p in PAGES], "activePageName": PAGES[0][0]}, indent=2))
    for name, display in PAGES:
        write(REPORT_DIR / "definition" / "pages" / name / "page.json", json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.4.0/schema.json",
            "name": name, "displayName": display, "displayOption": "FitToPage",
            "height": 720, "width": 1280}, ensure_ascii=False, indent=2))
    return REPORT_DIR / "definition" / "pages"


def card(name, x, y, w, h, entity, measure, title):
    v = visual(name, "card", x, y, w, h, {"Values": [meas(entity, measure)]}, title)
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
    add(p, card("k_cand", 964, 16, 300, 100, KPI_TABLE, "Candidates Text", "Ứng viên @ ngưỡng 20%"))
    add(p, visual("c_band", "clusteredColumnChart", 16, 132, 624, 260,
                  {"Category": [col("KingSales", "price_band")],
                   "Y": [meas(KPI_TABLE, "King Transactions")]},
                  "Số giao dịch theo khúc giá"))
    add(p, visual("b_zip", "barChart", 648, 132, 616, 260,
                  {"Category": [col("KingSales", "zip_top")],
                   "Y": [meas(KPI_TABLE, "King Transactions")]},
                  "Top 12 ZIP theo số giao dịch"))
    add(p, visual("t_zip", "tableEx", 16, 408, 1248, 296,
                  {"Values": [col("KingSales", "zip_top"),
                              meas(KPI_TABLE, "King Transactions"),
                              meas(KPI_TABLE, "King Median Price"),
                              meas(KPI_TABLE, "Candidate Share")]},
                  "ZIP: quy mô và tỷ lệ ứng viên"))

    # ---- Trang 2
    p = pages / "what_if"
    slicer = visual("s_nguong", "slicer", 16, 16, 300, 150,
                    {"Values": [col("Nguong", "Value")]},
                    "Ngưỡng undervalued (5%–50%)")
    slicer["visual"]["objects"] = {
        "data": [{"properties": {
            "mode": {"expr": {"Literal": {"Value": "'Between'"}}},
            "start": {"expr": {"Literal": {"Value": "0.20D"}}},
            "end": {"expr": {"Literal": {"Value": "0.50D"}}},
        }}],
        "general": [{"properties": {"filter": {"filter": {
            "Version": 2,
            "From": [{"Name": "n", "Entity": "Nguong", "Type": 0}],
            "Where": [{"Condition": {"Between": {
                "Expression": {"Column": {
                    "Expression": {"SourceRef": {"Source": "n"}},
                    "Property": "Value"}},
                "LowerBound": {"Literal": {"Value": "0.20D"}},
                "UpperBound": {"Literal": {"Value": "0.50D"}},
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
                  {"Category": [col("KingSales", "zip_top")],
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

    # ---- Trang 3
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

    # ---- Trang 4
    p = pages / "ames"
    add(p, card("a_n", 16, 16, 300, 100, KPI_TABLE, "AmesProperties Text", "Số tài sản Ames"))
    add(p, card("a_med", 332, 16, 300, 100, KPI_TABLE, "AmesMedian Text", "Giá trung vị Ames (USD)"))
    add(p, card("a_mape", 648, 16, 300, 100, KPI_TABLE, "Ames OOF MAPE", "MAPE out-of-fold Ames"))
    add(p, card("a_cand", 964, 16, 300, 100, KPI_TABLE, "AmesCandidates Text", "Ames ứng viên @ ngưỡng"))
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

    # ---- Trang 5
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


def main():
    write(OUT / f"{PROJECT}.pbip", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{PROJECT}.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2))
    write_model()
    build_pages()
    print("Đã sinh PBIP:", OUT / f"{PROJECT}.pbip")


if __name__ == "__main__":
    main()
