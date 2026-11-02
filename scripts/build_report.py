"""Tạo phần báo cáo 4 và 5 từ các bảng kết quả thực tế đã chạy."""
from pathlib import Path
import json
import pandas as pd
from docx import Document
from docx.shared import Inches, Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports'
REPORT.mkdir(exist_ok=True)

def fmt(x, digits=0):
    return f'{x:,.{digits}f}'

def pv(x):
    return '<0,001' if x < .001 else f'{x:.3f}'.replace('.', ',')

LABEL = {'sqft_living':'Diện tích ở', 'house_age':'Tuổi nhà',
         'sqft_lot':'Diện tích đất','lot_area':'Diện tích đất',
         'grade':'Hạng chất lượng','overall_qual':'Chất lượng tổng thể',
         'bathrooms':'Phòng tắm','bathrooms_total':'Phòng tắm trên mặt đất',
         'bedrooms':'Phòng ngủ','bedroom_abvgr':'Phòng ngủ trên mặt đất',
         'distance_to_center_km':'Khoảng cách trung tâm'}
UNITS = {'sqft_living':'sqft','house_age':'năm','sqft_lot':'sqft','lot_area':'sqft',
         'grade':'điểm','overall_qual':'điểm','bathrooms':'phòng','bathrooms_total':'phòng',
         'bedrooms':'phòng','bedroom_abvgr':'phòng','distance_to_center_km':'km'}

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.top_margin, sec.bottom_margin = Cm(1.8), Cm(1.7)
sec.left_margin, sec.right_margin = Cm(2), Cm(2)
for style_name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3','Caption']:
    s = doc.styles[style_name]
    s.font.name = 'Arial'
    s.font.color.rgb = RGBColor(0,0,0)
    s._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Arial')
    for border in s._element.xpath('./w:pPr/w:pBdr'):
        border.getparent().remove(border)
doc.styles['Normal'].font.size = Pt(10.5)
doc.styles['Normal'].paragraph_format.line_spacing = 1.15
doc.styles['Normal'].paragraph_format.space_after = Pt(6)
doc.styles['Title'].font.size = Pt(24)
doc.styles['Heading 1'].font.size = Pt(17)
doc.styles['Heading 2'].font.size = Pt(13)
doc.styles['Caption'].font.size = Pt(9)
doc.styles['Title'].paragraph_format.space_after = Pt(12)
for h in ['Heading 1','Heading 2','Heading 3']:
    doc.styles[h].paragraph_format.keep_with_next = True
footer = sec.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
footer.add_run('Nhiệm vụ 2 và 3  |  ')
fld = OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); footer._p.append(fld)
for r in footer.runs: r.font.size=Pt(8)

def p(text, bold=False):
    para=doc.add_paragraph()
    r=para.add_run(text); r.bold=bold
    return para

def h(text, level=2):
    return doc.add_heading(text, level=level)

def page(title):
    doc.add_page_break(); h(title,1)

def table(headers, rows, widths=None, fontsize=9):
    t=doc.add_table(rows=1, cols=len(headers))
    t.alignment=WD_TABLE_ALIGNMENT.CENTER
    t.autofit=False
    if widths:
        for col,width in zip(t.columns,widths): col.width=Cm(width)
    for c,text in zip(t.rows[0].cells,headers): c.text=str(text)
    for row in rows:
        for c,text in zip(t.add_row().cells,row): c.text=str(text)
    for i,row in enumerate(t.rows):
        for j,c in enumerate(row.cells):
            if widths: c.width=Cm(widths[j])
            c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tcpr=c._tc.get_or_add_tcPr()
            sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'243746' if i==0 else ('F0F4F7' if i%2==0 else 'FFFFFF'));tcpr.append(sh)
            borders=OxmlElement('w:tcBorders')
            for side in ['top','left','bottom','right']:
                b=OxmlElement('w:'+side);b.set(qn('w:val'),'single');b.set(qn('w:sz'),'4');b.set(qn('w:color'),'D9D9D9');borders.append(b)
            tcpr.append(borders)
            for para in c.paragraphs:
                para.paragraph_format.space_after=Pt(4)
                para.paragraph_format.space_before=Pt(4)
                para.paragraph_format.line_spacing=1.06
                for r in para.runs:
                    r.font.size=Pt(fontsize)
                    if i==0: r.bold=True;r.font.color.rgb=RGBColor(255,255,255)
        if i==0:
            repeat=OxmlElement('w:tblHeader'); row._tr.get_or_add_trPr().append(repeat)
        cant=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(cant)
    doc.add_paragraph().paragraph_format.space_after=Pt(1)
    return t

def figure(name, caption, width=6.5):
    path=ROOT/'outputs/figures'/name
    para=doc.add_paragraph();para.paragraph_format.keep_with_next=True
    para.alignment=WD_ALIGN_PARAGRAPH.CENTER
    run=para.add_run();run.add_picture(str(path),width=Inches(width))
    for inline in run._r.xpath('.//wp:docPr'):
        inline.set('descr',caption)
    doc.add_paragraph(caption,style='Caption')

def equation(text):
    # Native Word math giữ công thức tìm kiếm và sửa được trong Word.
    para=doc.add_paragraph();para.alignment=WD_ALIGN_PARAGRAPH.CENTER
    math=OxmlElement('m:oMath');r=OxmlElement('m:r');t=OxmlElement('m:t');t.text=text;r.append(t);math.append(r);para._p.append(math)

def mr(text):
    r=OxmlElement('m:r');t=OxmlElement('m:t');t.text=text;r.append(t);return r

def mf(num,den):
    f=OxmlElement('m:f')
    for tag,content in [('m:num',num),('m:den',den)]:
        x=OxmlElement(tag);x.append(mr(content));f.append(x)
    return f

def ms(base,power):
    s=OxmlElement('m:sSup')
    for tag,content in [('m:e',base),('m:sup',power)]:
        x=OxmlElement(tag);x.append(mr(content));s.append(x)
    return s

def native_math(nodes):
    para=doc.add_paragraph();para.alignment=WD_ALIGN_PARAGRAPH.CENTER
    math=OxmlElement('m:oMath')
    for node in nodes: math.append(node)
    para._p.append(math)

def build():
    etl=json.loads((ROOT/'metadata/etl_summary.json').read_text())
    result=json.loads((ROOT/'outputs/tables/analysis_summary.json').read_text())
    summary=result['datasets']; k=summary['king_county']; a=summary['ames']
    sources=json.loads((ROOT/'metadata/sources.json').read_text())
    tests=pd.read_csv(ROOT/'outputs/tables/welch_tests.csv')
    directions=pd.read_csv(ROOT/'outputs/tables/directional_tests.csv')
    sens=pd.read_csv(ROOT/'outputs/tables/sensitivity.csv')
    dictionary=pd.read_csv(ROOT/'dictionaries/data_dictionary.csv')
    doc.core_properties.title='Dữ liệu và phân tích mô tả chẩn đoán giá bất động sản'
    doc.core_properties.subject='Chủ đề 14  Nhiệm vụ 2 và 3  Phần 4 và phần 5 cấp 1 cấp 2'
    doc.core_properties.author='Nhiệm vụ 2 và 3'
    doc.add_paragraph('Dữ liệu và phân tích giá bất động sản',style='Title')
    doc.add_paragraph('Chủ đề 14  Mô hình định giá bất động sản tự động',style='Subtitle')
    p('Nhiệm vụ 2 và 3  |  Phần 4 và phần 5 cấp 1 cấp 2  |  Ngày 02 tháng 11 năm 2026',True)
    p(f'Báo cáo chuẩn bị hai bộ dữ liệu lịch sử và phân tích sự khác biệt giữa nhóm giá thấp và các giao dịch còn lại. Sau làm sạch, King County có {fmt(k["n"])} giao dịch và Ames có {fmt(a["n"])} căn. Kết quả hỗ trợ lựa chọn biến và thiết kế bước dự báo, chưa xác định danh sách đầu tư 20 căn.')
    h('Kết quả chính')
    p(f'Theo đúng ngưỡng giá bán thấp hơn 20% trung vị toàn từng bộ dữ liệu, King County có {fmt(k["n_low"])} giao dịch ({k["share_low"]:.2%}) dưới {fmt(k["threshold_global20"])} USD; Ames có {fmt(a["n_low"])} căn ({a["share_low"]:.2%}) dưới {fmt(a["threshold_global20"])} USD. Nhãn này phản ánh giá thấp tuyệt đối, không chứng minh bất động sản bị định giá thấp so với giá trị thị trường.')
    p('Các bảng kiểm định bên dưới đo chênh lệch diện tích, chất lượng, tuổi nhà và vị trí. Phân tích tách hai thị trường vì khác giai đoạn, mặt bằng giá và định nghĩa diện tích. Mọi số liệu được tính từ dữ liệu lưu trong gói bàn giao.')
    table(['Phạm vi','King County','Ames'],[
        ['Dữ liệu gốc',f'{etl["king_county"]["raw_rows"]:,} dòng × 21 cột','2,930 dòng × 82 cột'],
        ['Sau làm sạch',f'{k["n"]:,} giao dịch',f'{a["n"]:,} căn'],
        ['Giai đoạn','02/05/2014 đến 27/05/2015','2006 đến 2010'],
        ['Địa lý','70 zipcode; có lat và long',f'{a["n_geographies"]} neighborhood; thiếu tọa độ'],
        ['Đơn vị suy luận',f'{k["n_independent"]:,} tài sản',f'{a["n_independent"]:,} PID duy nhất']
    ],[4.3,6.2,6.2])
    h('Cách sử dụng phần bàn giao')
    p('Phần 4 trình bày nguồn, ETL, biến mới và từ điển dữ liệu. Phần 5 bao gồm phân tích mô tả và chẩn đoán. Notebook có mã và đầu ra đã chạy; CSV kiểm định chứa đầy đủ cỡ mẫu, bậc tự do, khoảng tin cậy và kích thước hiệu ứng. Phụ lục cuối báo cáo có nội dung slide để ghép vào Canva và phần minh bạch sử dụng AI.')

    page('4 Dữ liệu')
    h('4 1 Nguồn và đơn vị quan sát')
    p('King County dùng bản CSV công khai của bộ House Sales in King County do harlfoxem công bố trên Kaggle [1]. Tệp thực tế được tải từ mirror GitHub [2], giữ các ID, ngày bán và 21 trường gốc. Không gọi mirror là cổng dữ liệu chính thức của King County. Ames lấy trực tiếp tệp 2.930 quan sát và 82 trường kèm bài báo De Cock năm 2011 [3, 4]. Từ điển gốc [5] hướng dẫn ý nghĩa danh mục và NA.')
    p('Giá là USD danh nghĩa tại thời điểm bán; không điều chỉnh lạm phát hoặc quy đổi sang thị trường Việt Nam. Đơn vị King là giao dịch: cùng ID có thể bán nhiều lần. Đơn vị Ames là tài sản theo PID trong bản công bố. Giữ dữ liệu riêng cho từng nguồn, không nối dọc để phân tích giá chung.')
    h('4 2 Nhật ký ETL bốn bước')
    table(['Bước','Thao tác và bằng chứng'],[
        ['1 Extract','Tải raw; kiểm kích thước 21.613 × 21 và 2.930 × 82; lưu nguồn, thời điểm tải, byte và SHA256 trong sources.json.'],
        ['2 Transform kiểu và thiếu','Chuẩn hóa ngày, mã chuỗi và tên biến Ames; phân biệt NA cấu trúc với thiếu thông tin; lưu từng ô thay đổi trong imputation_audit.csv.'],
        ['3 Transform ngoại lệ và biến mới','Cách ly lỗi nghi ngờ, gắn cờ IQR, lưu tuổi gốc; tính tuổi tại năm bán, USD/sqft và Haversine khi có tọa độ.'],
        ['4 Load và kiểm tra','Xuất hai clean CSV, quarantine, dictionary và audit; assert giá/diện tích dương, ID, số dòng, tuổi và khoảng cách; chạy EDA từ đầu ra đã kiểm.']
    ],[3,13.7])
    p('Chi tiết từng bước và số lượng xử lý nằm trong docs/nhat_ky_etl_4_buoc.txt. Chạy lại mặc định dùng raw đã lưu và kiểm checksum; chỉ tùy chọn --refresh mới tải lại. Nhờ vậy đầu ra không âm thầm thay đổi khi mirror cập nhật.')
    h('Dấu vết nguồn')
    for key in ['king_county','ames','ames_documentation']:
        s=sources[key]
        p(f'{s["file"]}: SHA256 {s["sha256"][:24]}…; {s["bytes"]:,} byte. Hash đầy đủ và ngày tải có trong metadata/sources.json.')

    page('4 3 Xử lý dữ liệu thiếu và ngoại lệ')
    p('King County không thiếu giá trị ở các trường gốc. Với Ames, chuỗi NA được đọc là thiếu nhưng chuỗi None ở Mas Vnr Type là giá trị hợp lệ biểu thị không có lớp ốp; giữ nguyên 1.752 giá trị này. Tổng số ô thiếu gốc là 13.997. Một năm gara 2207 ngoài miền hợp lý được coi là thiếu thực và điền bằng trung vị neighborhood, thay vì tự đoán thành năm 2007.')
    table(['Tình huống Ames','Quy tắc'],[
        ['NA là không có tiện ích','Dựa theo từ điển gốc cho Alley, Pool QC, Fence, Misc Feature, Fireplace Qu và các trường liên quan. Giữ nhãn No_feature.'],
        ['Gara hoặc tầng hầm','Đối chiếu diện tích và sức chứa trước khi điền No_garage hoặc No_basement và số lượng 0. Không xem mọi NA là không tồn tại.'],
        ['Thiếu thực danh mục','Điền Unknown để tránh áp đặt loại vật liệu hoặc mức chất lượng không có bằng chứng.'],
        ['Thiếu thực số','Điền trung vị neighborhood, dự phòng trung vị toàn bộ; không dùng giá bán để điền. Mỗi thay đổi có cờ và audit.']
    ],[5.1,11.6])
    p(f'Có {fmt(etl["ames"]["imputation_or_structural_fill_cells"])} lượt thay ô, gồm NA cấu trúc và một năm gara sai. has_any_imputation ghi mọi lần thay; has_true_imputation chỉ ghi ước lượng/Unknown do thiếu thực. Tách hai cờ này để kiểm tra độ nhạy không loại toàn bộ Ames chỉ vì căn nhà không có hồ bơi hoặc ngõ.')
    h('Quy tắc ngoại lệ')
    p('Ngưỡng 1,5 IQR chỉ gắn cờ: nhỏ hơn Q1 trừ 1,5 IQR hoặc lớn hơn Q3 cộng 1,5 IQR. Các giao dịch đắt và nhà lớn vẫn nằm trong mẫu chính. Riêng King cách ly dòng có 33 phòng ngủ theo quy tắc bedrooms lớn hơn 20; đây là lỗi nghi ngờ, chưa xác minh với hồ sơ gốc. Hai tệp quarantine giữ dòng và lý do để truy vết.')
    table(['Kiểm tra','King County','Ames'],[
        ['Dòng cách ly','1','0'],['Trùng toàn dòng','0','0'],
        ['Gắn cờ giá 1,5 IQR',fmt(etl['king_county']['price_iqr_outliers']),fmt(etl['ames']['price_iqr_outliers'])],
        ['Gắn cờ diện tích 1,5 IQR',fmt(etl['king_county']['area_iqr_outliers']),fmt(etl['ames']['area_iqr_outliers'])],
        ['Tuổi âm được giữ dấu vết','12','1'],['Ames trên 4.000 sqft','Không áp dụng','5 căn giữ trong mẫu chính']
    ],[7,4.8,4.9])
    p('De Cock lưu ý các căn Ames trên 4.000 sqft gồm giao dịch có điều kiện đặc biệt và nhà rất lớn hợp lệ [3]. Phân tích bổ sung loại nhóm này để đánh giá độ ổn định; không kết luận tất cả là dữ liệu sai.')

    page('4 4 Biến mới và từ điển dữ liệu')
    native_math([mr('price_per_sqft = '),mf('price','sqft_living')])
    p('Đơn vị USD/sqft. King sqft_living gồm diện tích sinh hoạt bên trong kể cả basement; Ames dùng Gr Liv Area trên mặt đất. Vì mẫu số khác nghĩa, đơn giá không được dùng để kết luận thị trường nào rẻ hơn.')
    equation('raw_house_age = sale_year − year_built')
    equation('house_age = max(raw_house_age, 0)')
    p('Tuổi tính tại thời điểm giao dịch, không dùng năm hiện tại. King có 12 dòng và Ames có 1 dòng năm xây sau năm bán; giữ raw_house_age và cờ age_capped_zero, dùng 0 làm giá trị vận hành. Đây là giả định cần kiểm tra nếu sử dụng cho dự báo.')
    native_math([mr('a = '),ms('sin','2'),mr('('),mf('φ − φ₀','2'),mr(') + cos(φ)cos(φ₀)'),ms('sin','2'),mr('('),mf('λ − λ₀','2'),mr(')')])
    para=doc.add_paragraph();para.alignment=WD_ALIGN_PARAGRAPH.CENTER
    math=OxmlElement('m:oMath');math.append(mr('d = 2R arcsin('))
    rad=OxmlElement('m:rad');pr=OxmlElement('m:radPr');hide=OxmlElement('m:degHide');hide.set(qn('m:val'),'1');pr.append(hide);rad.append(pr)
    rad.append(OxmlElement('m:deg'));e=OxmlElement('m:e');e.append(mr('a'));rad.append(e);math.append(rad);math.append(mr(')'));para._p.append(math)
    p('d là distance_to_center_km. Tất cả góc chuyển từ độ sang radian; R bằng 6.371,0088 km. Điểm tham chiếu Seattle được nhóm quy ước là lat 47,6062 và long −122,3321. Đây là khoảng cách đường chim bay đến một mốc phân tích, không phải khoảng cách lái xe hoặc định nghĩa chính thức của trung tâm thương mại.')
    p('Ames không có lat, long hoặc zipcode trong 82 trường gốc. distance_to_center_km được để NA có chủ đích, distance_available bằng 0; không gán khoảng cách 0 và không suy ra tọa độ từ tên neighborhood.')
    table(['Trường bàn giao','Vai trò và cách đọc'],[
        ['price và sale_price','Biến đích; sale_price là trường gốc Ames, price là alias.'],
        ['sqft_living','Biến diện tích thống nhất tên; nghĩa đo lường vẫn khác giữa hai nguồn.'],
        ['price_per_sqft','Chỉ phục vụ mô tả; chứa giá đích nên cấm dùng để dự báo chính price.'],
        ['source_row_id và id hoặc pid','Khóa truy vết; không xem ID là biến số liên tục.'],
        ['price_iqr_outlier','Cờ dùng giá thực tế; chỉ dùng audit và sensitivity.'],
        ['has_true_imputation','Cờ hàng có thiếu thực được xử lý; phân biệt với vắng tiện ích.']
    ],[6,10.7])

    page('4 5 Dữ liệu bàn giao cho các nhiệm vụ sau')
    p(f'Từ điển dictionaries/data_dictionary.csv bao phủ {len(dictionary):,} trường của hai tệp sạch, gồm tên raw, tên sạch, kiểu dữ liệu, đơn vị, mô tả tiếng Việt, vai trò, rò rỉ mục tiêu, quy tắc thiếu, số thiếu sau xử lý và nguồn đối chiếu. Ames giữ đủ 82 trường gốc dưới tên snake_case; các alias chỉ giúp dùng chung mã, không tạo thông tin mới.')
    table(['Tệp','Mục đích'],[
        ['data/processed/king_county_clean.csv',f'{etl["king_county"]["clean_rows"]:,} giao dịch × {etl["king_county"]["clean_columns"]} cột.'],
        ['data/processed/ames_clean.csv',f'{etl["ames"]["clean_rows"]:,} căn × {etl["ames"]["clean_columns"]} cột; tọa độ không có sẵn.'],
        ['metadata/missingness_before_after.csv','Đối chiếu tỷ lệ thiếu từng trường trước và sau ETL.'],
        ['metadata/imputation_audit.csv','Từng ô đổi với giá trị trước, sau và quy tắc.'],
        ['metadata/outlier_audit.csv','Các dòng cần xem xét; cờ không đồng nghĩa lỗi.'],
        ['outputs/tables/*_group_labels.csv','Nhãn nhóm EDA theo source_row_id; không coi là nhãn đầu tư thực.']
    ],[9,7.7])
    h('Quy tắc khi chuyển sang dự báo')
    p('Các tệp sạch phục vụ EDA trên toàn mẫu. Nhiệm vụ 4 cần chia train và test trước, rồi fit lại trung vị điền thiếu, ngưỡng ngoại lệ, mã hóa và mọi biến phụ thuộc phân phối chỉ trên train. Dùng raw và mã ETL để xây pipeline đúng thời điểm, thay vì giả định CSV đã điền toàn mẫu là đầu vào đánh giá hoàn toàn độc lập.')
    p('Loại price_per_sqft, sale_price alias của price, price_iqr_outlier và mọi nhãn hoặc ngưỡng dùng giá đích khỏi X. Không đưa đồng thời các alias trùng nghĩa vào mô hình tuyến tính. Ngày bán và các trường chỉ biết sau giao dịch cần được rà soát theo thời điểm quyết định thực tế.')
    p(f'King có {fmt(etl["king_county"]["repeat_transaction_rows_beyond_first"])} giao dịch vượt lần đầu của cùng tài sản. Dùng chia nhóm theo ID hoặc chia theo thời gian khi đánh giá, để một căn nhà không xuất hiện ở cả train và test. Báo cáo này chưa huấn luyện mô hình, chưa báo MAPE hoặc RMSE và chưa lựa chọn 20 căn, vì các sản phẩm đó thuộc nhiệm vụ 4.')
    h('Kiểm tra đã chạy')
    p('ETL kiểm số dòng và cột raw, hash, giá và diện tích dương, tuổi không âm sau xử lý, công thức đơn giá, tính duy nhất PID Ames, giao dịch lặp King và khoảng cách hợp lệ. Phân tích kiểm nhãn ngưỡng, p-value sau điều chỉnh nằm trong 0 đến 1, khoảng tin cậy chứa ước lượng chênh lệch, cùng tự kiểm Holm và Welch. Notebook đã thực thi và lưu đầu ra để đối chiếu trực tiếp.')

    page('5 Phân tích cấp 1 và cấp 2')
    h('5 1 Phân phối giá bán')
    figure('king_county_price_distribution.png','Hình 1  Giá King County theo thang gốc và log10; đường ngắt là 80% trung vị.')
    figure('ames_price_distribution.png','Hình 2  Giá Ames theo thang gốc và log10; mọi giao dịch sạch được giữ.')
    p(f'King có trung vị {fmt(k["median_price"])} USD và trung bình {fmt(k["mean_price"])} USD; Ames lần lượt là {fmt(a["median_price"])} và {fmt(a["mean_price"])} USD. Trung bình cao hơn trung vị phù hợp với đuôi phải của phân phối. Độ lệch mẫu tương ứng là {k["price_skew"]:.2f} và {a["price_skew"]:.2f}. Thang log làm phần giá phổ biến dễ quan sát hơn nhưng không thay thế giá gốc trong định nghĩa nhóm hoặc kiểm định thuộc tính.')
    p(f'Khoảng giá sạch là {fmt(k["min_price"])} đến {fmt(k["max_price"])} USD ở King và {fmt(a["min_price"])} đến {fmt(a["max_price"])} USD ở Ames. Các mức giá cực trị cần đọc cùng diện tích, vị trí và điều kiện giao dịch; riêng một mức giá thấp chưa chứng minh cơ hội đầu tư.')

    page('5 2 Phân bố giá theo zipcode')
    figure('king_county_geographic_boxplot.png','Hình 3  Toàn bộ zipcode King County được sắp theo trung vị, n là số giao dịch; trục giá logarit.',width=6.6)
    p('Hộp thể hiện Q1 đến Q3, đường giữa là trung vị và râu theo quy tắc 1,5 IQR. Điểm nằm ngoài râu được ẩn để tăng khả năng đọc; chúng vẫn có mặt trong dữ liệu và thống kê. Hai cụm cột chỉ là cách dàn trang, không phải phân khúc do thuật toán tìm ra.')
    p('Sự khác nhau giữa các zipcode cho thấy ngưỡng trung vị toàn thị trường có thể gom nhiều nhà ở khu giá thấp. Không dùng boxplot để tách tác động vị trí khỏi quy mô hoặc chất lượng. Bản SVG trong outputs/figures cho phép phóng to từng nhãn; geographic_summary.csv cung cấp n, trung vị và số nhà thuộc từng nhóm.')

    page('5 3 Phân bố giá theo neighborhood tại Ames')
    figure('ames_geographic_boxplot.png','Hình 4  Ames được nhóm theo neighborhood vì raw không có zipcode; quy ước hộp và râu như Hình 3.',width=5.55)
    p('Neighborhood là khu dân cư, không phải zipcode và cũng không thay thế tọa độ chính xác. Báo cáo chỉ so sánh giá theo đơn vị địa lý có sẵn. Khác biệt giữa các khu là lý do kiểm tra thêm ngưỡng địa phương ở mục độ nhạy.')

    page('5 4 Định nghĩa nhóm và đặc điểm mô tả')
    equation('undervalued_global = 1 khi price < 0,8 × median(price)')
    p('Trung vị tính riêng trên toàn bộ mỗi bộ dữ liệu sạch; dấu nhỏ hơn là nghiêm ngặt nên giao dịch đúng ngưỡng không thuộc nhóm thấp. Tên undervalued được giữ để khớp đề bài; trong diễn giải, báo cáo gọi là nhóm giá thấp. Không dùng dự báo hoặc residual để tạo nhãn trong nhiệm vụ này.')
    table(['Chỉ tiêu','King County','Ames'],[
        ['Ngưỡng chính',f'{k["threshold_global20"]:,.0f} USD',f'{a["threshold_global20"]:,.0f} USD'],
        ['Nhóm giá thấp',f'{k["n_low"]:,} ({k["share_low"]:.2%})',f'{a["n_low"]:,} ({a["share_low"]:.2%})'],
        ['Nhóm còn lại',fmt(k['n']-k['n_low']),fmt(a['n']-a['n_low'])]
    ],[6.5,5.1,5.1])
    figure('king_county_group_comparison.png','Hình 5  Đặc điểm các nhóm King County; biểu đồ mô tả toàn bộ giao dịch sạch.')
    figure('ames_group_comparison.png','Hình 6  Đặc điểm các nhóm Ames; phòng tắm chỉ tính trên mặt đất theo full_bath cộng nửa half_bath.')
    p('Biểu đồ giúp nhận diện nhóm giá thấp có khác quy mô và chất lượng hay không. Bảng kiểm định ở trang sau dùng một giao dịch trên mỗi tài sản, nên trung bình và cỡ mẫu ở đó có thể khác bảng mô tả toàn giao dịch.')

    page('5 5 Kiểm định chênh lệch hai nhóm')
    p('Đặt H0 là trung bình thuộc tính giữa hai nhóm bằng nhau; H1 là khác nhau. Dùng Welch hai phía, equal_var=False, mức ý nghĩa 5%, không giả định phương sai hai nhóm bằng nhau [6]. King giữ giao dịch sớm nhất theo ID, lựa chọn không dựa vào giá; nhãn vẫn theo ngưỡng toàn mẫu sạch. Ames có một PID cho mỗi quan sát.')
    p('Chênh lệch dưới đây là trung bình nhóm giá thấp trừ nhóm còn lại. CI95% là khoảng riêng từng biến, chưa điều chỉnh đồng thời. p được điều chỉnh Holm trong từng bộ dữ liệu cho họ kiểm định Welch; Hedges g chuẩn hóa chênh lệch để đọc cùng ý nghĩa thực tế. Ký hiệu p nhỏ hơn 0,001 bao gồm cả trường hợp máy tính làm tròn về 0.')
    for key in ['king_county','ames']:
        sub=tests[tests.dataset.eq(key)]
        h(summary[key]['name'])
        p(f'Mẫu suy luận có {summary[key]["n_independent"]:,} tài sản. Cỡ mẫu từng nhóm, t và bậc tự do từng biến có trong welch_tests.csv.')
        rows=[]
        for _,r in sub.iterrows():
            rows.append([LABEL[r.variable]+' ('+UNITS[r.variable]+')',fmt(r.mean_low,2),fmt(r.mean_rest,2),f'{r.difference_low_minus_rest:,.2f}\n[{r.ci95_low:,.2f}; {r.ci95_high:,.2f}]',f'{r.hedges_g:.2f}',pv(r.p_holm)])
        table(['Thuộc tính','Nhóm thấp','Còn lại','Chênh lệch và CI95%','g','p Holm'],rows,[4.1,2.1,2.1,4.8,1.2,2.4],fontsize=8.1)
    p('Phòng ngủ và chất lượng là biến đếm hoặc thứ bậc; Welch ở đây chỉ so trung bình theo yêu cầu đề bài. Không kiểm định chênh lệch giá vì nhóm đã được định nghĩa bằng giá; không kiểm định đơn giá như bằng chứng độc lập vì đơn giá chứa chính giá đích.')

    page('5 6 Diễn giải chẩn đoán')
    kr=tests[tests.dataset.eq('king_county')].set_index('variable')
    ar=tests[tests.dataset.eq('ames')].set_index('variable')
    ka=kr.loc['sqft_living']; aa=ar.loc['sqft_living']
    p(f'Ở King County, nhóm giá thấp có diện tích ở trung bình {ka.mean_low:,.0f} sqft so với {ka.mean_rest:,.0f} sqft của nhóm còn lại; chênh lệch {ka.difference_low_minus_rest:,.0f} sqft, CI95% [{ka.ci95_low:,.0f}; {ka.ci95_high:,.0f}]. Hạng chất lượng thấp hơn {abs(kr.loc["grade","difference_low_minus_rest"]):.2f} điểm và xa mốc Seattle hơn {kr.loc["distance_to_center_km","difference_low_minus_rest"]:.2f} km. Tuổi nhà cao hơn {kr.loc["house_age","difference_low_minus_rest"]:.2f} năm nhưng g chỉ {kr.loc["house_age","hedges_g"]:.3f}, một khác biệt nhỏ dù p rất thấp.')
    figure('king_county_price_relationships.png','Hình 7  Giá King County và diện tích, tuổi, khoảng cách; màu biểu thị mật độ quan sát.')
    p(f'Ở Ames, diện tích nhóm thấp nhỏ hơn {abs(aa.difference_low_minus_rest):,.0f} sqft, CI95% [{aa.ci95_low:,.0f}; {aa.ci95_high:,.0f}], chất lượng thấp hơn {abs(ar.loc["overall_qual","difference_low_minus_rest"]):.2f} điểm và tuổi cao hơn {ar.loc["house_age","difference_low_minus_rest"]:.2f} năm. Chênh lệch tuổi có g bằng {ar.loc["house_age","hedges_g"]:.3f}, lớn hơn nhiều so với King trong thang chuẩn hóa của từng mẫu.')
    figure('ames_price_relationships.png','Hình 8  Giá Ames và diện tích, tuổi, chất lượng; đây là các liên hệ đơn biến.')
    p('Các mẫu hình phù hợp với việc nhóm giá thấp tập trung vào những căn nhỏ hơn hoặc chất lượng thấp hơn, và ở King còn xa mốc trung tâm hơn. EDA chưa phân biệt được mức giá thấp do đặc điểm tài sản với một khoản chiết khấu so với giá trị hợp lý. Cần mô hình điều chỉnh nhiều thuộc tính để tiến thêm ở nhiệm vụ 4.')

    page('5 7 Giả thuyết chiều hướng quan hệ')
    p('Trước khi tính, đặt kỳ vọng giá tăng theo diện tích và chất lượng, giảm theo tuổi nhà và khoảng cách đến mốc Seattle. Kiểm định tương quan hạng Spearman một phía theo chiều đã đặt, dùng mẫu một giao dịch mỗi tài sản; Holm điều chỉnh riêng họ Spearman trong từng bộ dữ liệu [7]. Không đổi chiều kiểm định sau khi xem dấu hệ số.')
    rows=[]
    for _,r in directions.iterrows():
        expected='Dương' if r.expected_direction=='positive' else 'Âm'
        conclusion={'supported':'Ủng hộ chiều đặt trước','inconclusive':'Chưa đủ bằng chứng','opposite_observed':'Dấu quan sát ngược kỳ vọng'}[r.conclusion]
        rows.append([summary[r.dataset]['name']+'\n'+LABEL[r.variable],expected,f'{r.rho:.3f}',pv(r.p_holm),conclusion])
    table(['Bộ dữ liệu và biến','Kỳ vọng','rho','p Holm','Kết luận'],rows,[5.2,1.7,1.5,2.3,6],fontsize=8.8)
    for key in ['king_county','ames']:
        sub=directions[directions.dataset.eq(key)]
        area=sub[sub.variable.eq('sqft_living')].iloc[0]
        quality=sub[sub.variable.eq('grade' if key=='king_county' else 'overall_qual')].iloc[0]
        age=sub[sub.variable.eq('house_age')].iloc[0]
        p(f'{summary[key]["name"]}: rho của diện tích là {area.rho:.3f}, chất lượng {quality.rho:.3f} và tuổi nhà {age.rho:.3f}. Các hệ số là liên hệ đơn biến; chúng chưa kiểm soát vị trí, thời điểm hay tương tác giữa tuổi và chất lượng. Tuổi âm đã được gắn cờ và chặn ở 0 như phần ETL.')
    p('Các mức ý nghĩa thống kê dựa trên giả định độc lập của tài sản. Bỏ giao dịch bán lặp làm giảm một nguồn phụ thuộc nhưng không loại hoàn toàn sự phụ thuộc không gian trong cùng khu. Vì vậy, p-value cần đọc cùng kích thước hiệu ứng và phân bố thuộc tính; không diễn giải là quan hệ nhân quả.')

    page('5 8 Độ nhạy và hàm ý chẩn đoán')
    threshold=sens[sens.analysis.eq('threshold')]
    rows=[]
    for _,r in threshold.iterrows():
        rows.append([summary[r.dataset]['name'],f'{r.discount:.0%}', 'Toàn thị trường' if r.reference=='global' else r.reference,fmt(r.n_low),f'{r.share_low:.2%}'])
    table(['Bộ dữ liệu','Thấp hơn trung vị','Mốc trung vị','Số nhóm thấp','Tỷ lệ'],rows,[3,3.1,4.6,3,3],fontsize=8.8)
    p(f'Ở ngưỡng 20%, thay trung vị chung bằng trung vị zipcode làm King đổi từ {k["n_low"]:,} sang {k["n_low_local"]:,} giao dịch; chỉ {k["n_overlap_global_local"]:,} giao dịch đồng thời thuộc cả hai nhóm. Ames đổi từ {a["n_low"]:,} sang {a["n_low_local"]:,}, giao nhau {a["n_overlap_global_local"]:,} căn. Ngưỡng địa phương giảm một phần khác biệt mặt bằng khu vực nhưng vẫn chưa điều chỉnh diện tích, chất lượng và điều kiện bán.')
    robustness=sens[sens.analysis.eq('welch_robustness')]
    p('sensitivity.csv còn tính lại Welch khi dùng tất cả giao dịch, một giao dịch mỗi tài sản, bỏ điểm giá hoặc diện tích ngoài 1,5 IQR, và loại hàng có thiếu thực được điền. Ames có thêm kịch bản bỏ căn trên 4.000 sqft. Các kịch bản giữ ngưỡng nhóm chính cố định để tách ảnh hưởng của việc đổi mẫu khỏi ảnh hưởng đổi ngưỡng.')
    main=tests.set_index(['dataset','variable'])
    changed=[]
    for _,r in robustness.iterrows():
        base=main.loc[(r.dataset,r.variable)]
        if (r.p_holm<.05)!=(base.p_holm<.05) or (r.difference_low_minus_rest>0)!=(base.difference_low_minus_rest>0):
            changed.append((r.dataset,r.reference,r.variable))
    if changed:
        p('Có kết luận nhạy với kịch bản loại mẫu: '+ '; '.join(f'{summary[d]["name"]}, {ref}, {LABEL[v]}' for d,ref,v in changed)+'. Cần đọc các dòng này trước khi khẳng định kết quả ổn định.')
    else:
        p('Trong các kịch bản Welch đã tính, không ghi nhận đổi dấu chênh lệch hoặc đổi quyết định ở mức p Holm 5% so với mẫu chính. Điều này chỉ đánh giá độ ổn định với các quy tắc đã thử, không loại trừ các yếu tố gây nhiễu chưa đo được.')
    p('Hàm ý cho nhiệm vụ 4: dùng diện tích, chất lượng, tuổi và địa lý như ứng viên giải thích, đồng thời kiểm tra điều kiện bán Ames và chia mẫu đúng thời gian hoặc ID. Chỉ khi mô hình có đánh giá ngoài mẫu và định nghĩa residual rõ ràng mới có cơ sở sàng lọc ứng viên theo giá so với dự báo; nhóm thấp tuyệt đối của nhiệm vụ 3 không tự động trở thành danh sách mua.')

    page('Phụ lục nội dung slide và thuyết trình')
    p('Nội dung dưới đây có thể ghép vào Canva của nhóm. Mỗi slide trình bày khoảng 25 đến 40 giây, tổng phần hai nhiệm vụ khoảng 3 đến 4 phút, tùy thời lượng chung của video.')
    slides=[
        ('1 Dữ liệu được chọn',f'King County: {k["n"]:,} giao dịch sạch, 2014 đến 2015. Ames: {a["n"]:,} căn, 2006 đến 2010. Hai thị trường phân tích riêng. Dùng bảng tổng quan đầu báo cáo.','Giới thiệu đơn vị quan sát và lý do giữ hai nguồn riêng; nhấn mạnh đây là dữ liệu lịch sử.'),
        ('2 Làm sạch và tạo biến','ETL bốn bước; cách ly một dòng 33 phòng ngủ; giữ ngoại lệ hợp lệ; phân biệt thiếu thực và vắng tiện ích. Biến mới: đơn giá, tuổi tại năm bán và Haversine cho King.','Ames không có lat/long hoặc zipcode nên không bịa tọa độ; năm xây sau năm bán được giữ cờ.'),
        ('3 Phân phối và địa lý','Dùng Hình 1 đến 4; giá lệch phải, khác biệt giữa các khu. Nêu trung vị thay vì chỉ dùng trung bình.','Giải thích hộp Q1 đến Q3, trung vị và việc ẩn điểm ngoại lệ chỉ để đọc hình.'),
        ('4 Nhóm giá thấp',f'Định nghĩa price nhỏ hơn 0,8 trung vị. King {k["n_low"]:,} ({k["share_low"]:.2%}); Ames {a["n_low"]:,} ({a["share_low"]:.2%}). Dùng Hình 5 và 6.','Nói rõ giá thấp không đồng nghĩa bị định giá thấp. Nhóm có thể gồm nhiều căn nhỏ hoặc ở khu giá thấp.'),
        ('5 Kiểm định và giả thuyết','Welch hai phía, CI95%, Hedges g và Holm. Spearman một phía kiểm chiều diện tích, chất lượng, tuổi và khoảng cách.','Trình bày một chênh lệch diện tích cùng CI và một hệ số tương quan từ bảng; không đọc hết p-value hoặc gọi tương quan là nguyên nhân.'),
        ('6 Độ nhạy và bàn giao','So ngưỡng 10%, 20%, 30% và mốc toàn thị trường với địa phương. Bàn giao CSV, dictionary, ETL, notebook, bảng và biểu đồ.','Chuyển sang thành viên làm mô hình; nhắc chống rò rỉ price_per_sqft và chia theo tài sản hoặc thời gian.')
    ]
    for title,content,speech in slides:
        h(title);p(content);p('Lời dẫn: '+speech)

    page('Phụ lục minh bạch sử dụng AI và tài liệu tham khảo')
    h('Minh bạch sử dụng AI')
    p('AI hỗ trợ xây dựng và chạy mã ETL, EDA, kiểm định, kiểm tra chéo kết quả và soạn thảo báo cáo. Dữ liệu nguồn được tải nguyên bản; số dòng, trung vị, tỷ lệ, p-value, khoảng tin cậy và biểu đồ được tính bằng Python từ các tệp lưu trong gói. Không dùng dữ liệu tổng hợp do AI sinh để thay dữ liệu thực tế. Tọa độ mốc Seattle và các quy tắc xử lý là giả định phân tích được công bố, không trình bày như quan sát thu thập được.')
    p('Nhật ký thao tác có thể kiểm chứng qua source hash, audit từng ô, các script, notebook có execution count và outputs, cùng môi trường thư viện được ghim phiên bản. Các diễn giải chỉ giới hạn trong hai mẫu lịch sử và các quy tắc đã ghi. Nội dung không gán tên người thực hiện, xác nhận của giảng viên hoặc kết quả mô hình chưa chạy.')
    h('Tài liệu tham khảo')
    refs=[
        '[1] harlfoxem. House Sales in King County, USA. Kaggle. https://www.kaggle.com/datasets/harlfoxem/housesalesprediction',
        '[2] jmatth11. Bản sao kc_house_data.csv. https://github.com/jmatth11/King-County-House-Data-Set/blob/master/kc_house_data.csv',
        '[3] De Cock, D. (2011). Ames, Iowa: Alternative to the Boston Housing Data as an End of Semester Regression Project. Journal of Statistics Education, 19(3). https://jse.amstat.org/v19n3/decock.pdf',
        '[4] De Cock, D. Tệp dữ liệu gốc AmesHousing.txt. https://jse.amstat.org/v19n3/decock/AmesHousing.txt',
        '[5] De Cock, D. DataDocumentation.txt. https://jse.amstat.org/v19n3/decock/DataDocumentation.txt',
        '[6] SciPy. scipy.stats.ttest_ind. https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html',
        '[7] SciPy. scipy.stats.spearmanr. https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html'
    ]
    for text in refs:p(text)
    p('Nguồn dữ liệu tải và tài liệu phương pháp đối chiếu ngày 02/11/2026. Metadata lưu thời điểm và checksum của chính tệp được phân tích. Các bảng chi tiết và toàn bộ biểu đồ PNG/SVG có trong gói bàn giao.')
    out=REPORT/'Bao_cao_Nhiem_vu_2_3.docx'
    doc.save(out)
    print(out)

if __name__=='__main__': build()
