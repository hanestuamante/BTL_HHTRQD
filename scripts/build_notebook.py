"""Dựng và chạy notebook bàn giao bằng đúng kernel của dự án."""
from pathlib import Path
import json, os, sys
import nbformat as nbf
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

ROOT=Path(__file__).resolve().parents[1]
nb=nbf.v4.new_notebook()
c=[]
def md(s): c.append(nbf.v4.new_markdown_cell(s))
def code(s): c.append(nbf.v4.new_code_cell(s))
md('''# Nhiệm vụ 2 và 3 Chuẩn bị dữ liệu và phân tích bất động sản

Notebook tái lập cho chủ đề 14, nhóm 4. Dùng **King County** và **Ames** nguyên bản; báo cáo mô tả lịch sử giao dịch, làm sạch theo quy tắc minh bạch, so sánh hai nhóm giá và kiểm tra giả thuyết quan hệ.

**Cách chạy:** từ thư mục dự án, cài `requirements.txt`, chạy `python scripts/prepare_data.py`, rồi Run All notebook. Chạy từ thư mục `notebooks` cũng được. ETL sử dụng bản raw đã lưu và chỉ tải lại khi raw chưa tồn tại. Tất cả số liệu dưới đây được tính bằng mã, không gán thủ công.

Không xây mô hình dự báo hoặc chọn 20 ứng viên đầu tư trong nhiệm vụ này. `undervalued` trong EDA chỉ là **nhãn nhóm giá thấp theo trung vị**, chưa phải bằng chứng bị định giá thấp so với thị trường.''')
code('''from pathlib import Path
import json, subprocess, sys
import pandas as pd
from IPython.display import display, Image, Code, Markdown
ROOT = Path.cwd() if (Path.cwd()/"scripts").exists() else Path.cwd().parent
assert (ROOT/"scripts/prepare_data.py").exists(), "Mở notebook từ thư mục dự án hoặc notebooks"
print("Thư mục dự án:", ROOT)
''')
md('''## Nhiệm vụ 2 ETL bốn bước

1. **Extract:** tải dữ liệu và tài liệu mô tả; lưu raw, URL, SHA-256 và thời điểm tải.
2. **Transform:** chuẩn hóa schema, kiểu dữ liệu và giao dịch; giữ giao dịch bán lặp của King County, loại trùng hoàn toàn; sửa hoặc cách ly giá trị không hợp lệ có dấu vết.
3. **Transform và tạo biến:** xử lý thiếu theo ngữ nghĩa, tạo `price_per_sqft = price / sqft_living`, `house_age = sale_year - year_built` với cờ các tuổi âm cần xử lý; Haversine dùng bán kính Trái Đất 6.371,0088 km và mốc Seattle do nhóm chọn. Biến từ giá là biến mô tả, không được dùng làm đầu vào dự báo giá.
4. **Load và kiểm tra:** lưu hai CSV sạch, từ điển dữ liệu, audit; assert số dòng, miền giá trị và công thức.

Phạm vi diện tích khác nhau: King County tính diện tích trong nhà có tầng hầm, Ames dùng diện tích ở trên mặt đất. Vì vậy không so trực tiếp price_per_sqft giữa hai thị trường.

Ames nguyên bản không có `lat`, `long`, `zipcode`. Khoảng cách của Ames được giữ thiếu có lý do, không nội suy tọa độ; dùng `neighborhood` để phân nhóm địa lý. Điểm ngoài khoảng 1,5 IQR được gắn cờ; các giá trị cực đoan hợp lệ vẫn được giữ. Mã ETL đầy đủ được hiển thị dưới đây để kiểm tra quy tắc chi tiết.''')
code('''etl_source = (ROOT/"scripts/prepare_data.py").read_text(encoding="utf8")
display(Code(etl_source, language="python"))
etl_process = subprocess.run([sys.executable, str(ROOT/"scripts/prepare_data.py")], check=True, capture_output=True, text=True)
print(etl_process.stdout)
''')
code('''etl_summary = json.loads((ROOT/"metadata/etl_summary.json").read_text(encoding="utf8"))
print(json.dumps(etl_summary, ensure_ascii=False, indent=2))
for filename in ["missingness_before_after.csv", "outlier_audit.csv", "imputation_audit.csv"]:
    print("\\n", filename)
    display(pd.read_csv(ROOT/"metadata"/filename).head(20))
print("Từ điển dữ liệu đầy đủ:")
display(pd.read_csv(ROOT/"dictionaries/data_dictionary.csv"))
''')
md('''## Nhiệm vụ 3 Thiết kế EDA và kiểm định

- Phân tích mô tả dùng **tất cả giao dịch sạch**. Giá và phân phối log được xem riêng cho mỗi thị trường; không gộp hai thành phố hoặc quy đổi thời gian theo giả định.
- Nhãn chính: `price < 0.8 × median(price)` trong từng bộ dữ liệu sạch, dấu `<` nghiêm ngặt. Kiểm tra độ nhạy với ngưỡng 10%, 20%, 30% và trung vị địa phương (`zipcode` hoặc `neighborhood`).
- Suy luận King County dùng **giao dịch sớm nhất mỗi tài sản** sau làm sạch để giảm phụ thuộc từ bán lặp. Ngưỡng nhãn vẫn giữ theo toàn mẫu sạch. Ames mỗi PID một quan sát. Dữ liệu còn có thể phụ thuộc không gian.
- **Welch t-test hai phía:** H0: trung bình thuộc tính hai nhóm bằng nhau. H1: khác nhau. Báo chênh lệch `nhóm thấp − còn lại`, CI95%, t, bậc tự do Welch, p thô, p Holm và Hedges g. Không kiểm định giá hoặc price_per_sqft vì cách lập nhóm đã dùng giá.
- **Giả thuyết chiều Spearman:** giá tăng theo diện tích và chất lượng; giảm theo tuổi và khoảng cách. Kiểm định một phía theo chiều kỳ vọng đã nêu; điều chỉnh Holm riêng mỗi họ kiểm định và mỗi dataset. Hệ số ngược chiều được báo trung thực. Biến thứ bậc chất lượng cần đọc cùng tương quan hạng.
- CI95% cho từng chênh lệch, không phải khoảng đồng thời đã hiệu chỉnh. `p < .05` không tự nói mức độ ảnh hưởng lớn, nên cần đọc effect size. Mọi quan hệ ở đây là quan sát, chưa mang nghĩa nhân quả.

Mã thực hiện đầy đủ nằm trong các cell tiếp theo và đồng nhất với `scripts/analyze.py`.''')
source=(ROOT/'scripts/analyze.py').read_text(encoding='utf8')
source=source.replace("ROOT = Path(__file__).resolve().parents[1]", "ROOT = Path.cwd() if (Path.cwd()/'scripts').exists() else Path.cwd().parent")
source=source.replace("if __name__=='__main__': run_analysis()",'')
code(source)
code('''results = run_analysis()
display(pd.DataFrame(results["datasets"]).T)
''')
md('''## Phân phối giá và khác biệt địa lý

Biểu đồ hộp dùng thang log để đọc được toàn bộ dải giá. Không hiển thị điểm ngoại lệ trên boxplot nhằm giảm chồng lấp, nhưng các điểm vẫn có trong thống kê và kiểm định chính. King County hiển thị tất cả zipcode; Ames hiển thị tất cả neighborhood, kèm số quan sát từng nhóm.''')
code('''display(pd.read_csv(TABLES/"summary_statistics.csv"))
display(pd.read_csv(TABLES/"geographic_summary.csv"))
for key in ["king_county", "ames"]:
    for suffix in ["price_distribution", "geographic_boxplot"]:
        display(Image(filename=str(FIGURES/f"{key}_{suffix}.png")))
''')
md('''## So sánh nhóm bằng Welch t-test

Bảng kiểm định dưới đây dùng mẫu một giao dịch mỗi tài sản. Các trung bình trong bảng mô tả `group_summary.csv` dùng toàn giao dịch, vì vậy không thay thế trực tiếp cho trung bình suy luận. `p_holm` điều chỉnh đồng thời các thuộc tính trong từng bộ dữ liệu. Giá trị p bằng 0 trong CSV có nghĩa phép tính dấu phẩy động nhỏ hơn khả năng biểu diễn, không phải xác suất đúng bằng 0.''')
code('''welch_results = pd.read_csv(TABLES/"welch_tests.csv")
display(welch_results)
for key in ["king_county", "ames"]:
    display(Image(filename=str(FIGURES/f"{key}_group_comparison.png")))
''')
md('''## Kiểm tra chiều quan hệ

Spearman dùng cặp quan sát không thiếu của từng biến. Hệ số rho phản ánh chiều và mức liên hệ đơn biến; vị trí, thời gian và chất lượng có thể gây nhiễu. Không dùng tương quan để kết luận một thuộc tính làm giá tăng hoặc giảm.''')
code('''display(pd.read_csv(TABLES/"directional_tests.csv"))
for key in ["king_county", "ames"]:
    for suffix in ["spearman_heatmap", "price_relationships"]:
        display(Image(filename=str(FIGURES/f"{key}_{suffix}.png")))
''')
md('''## Kiểm tra độ nhạy và giới hạn

So sánh tỷ lệ nhãn theo trung vị toàn thị trường và trung vị địa phương để đánh giá ảnh hưởng vị trí. Welch được chạy lại trên toàn giao dịch, một giao dịch mỗi tài sản, sau bỏ các cờ IQR và sau bỏ quan sát có missing thực được nội suy (không loại NA cấu trúc). Riêng Ames thêm kịch bản bỏ diện tích ở trên 4.000 sqft theo cảnh báo của De Cock; đây là kiểm tra độ nhạy, không khẳng định mọi căn lớn đều sai.

Dữ liệu 2006–2010 của Ames và 2014–2015 của King County không phải thị trường hiện tại. Các kiểm định không thay thế mô hình giá có điều chỉnh đặc điểm; nhãn EDA không được dùng trực tiếp để quyết định mua nhà. Khi chuyển sang nhiệm vụ 4, cần tách train/test theo thời gian hoặc tài sản, fit imputer/ngưỡng trên train và loại biến phát sinh từ giá khỏi predictors.''')
code('''sensitivity_results = pd.read_csv(TABLES/"sensitivity.csv")
display(sensitivity_results.loc[sensitivity_results.analysis.eq("threshold")])
display(sensitivity_results.loc[sensitivity_results.analysis.eq("welch_robustness")])
print((ROOT/"docs/eda_interpretation.txt").read_text(encoding="utf8"))
''')
md('''## Nguồn và minh bạch sử dụng AI

Nguồn dữ liệu, bản raw và checksum: `metadata/sources.json` (hoặc manifest nguồn trong thư mục `metadata`). King County có nguồn gốc bộ House Sales in King County của Harlfoxem trên Kaggle. Ames do Dean De Cock công bố, dựa trên Ames Assessor's Office; xem [bài báo gốc](https://jse.amstat.org/v19n3/decock.pdf) và [từ điển gốc](https://jse.amstat.org/v19n3/decock/DataDocumentation.txt).

AI hỗ trợ soạn mã ETL, EDA, kiểm định, diễn giải và cấu trúc báo cáo. Dữ liệu không do AI tạo. Toàn bộ số liệu, bảng và biểu đồ do mã chạy trên CSV đã lưu; audit và raw cho phép kiểm tra lại. Các ngưỡng và mốc trung tâm là lựa chọn phân tích của nhóm và được công khai. Notebook có assertions kiểm tra miền giá trị, CI và hiệu chỉnh Holm.''')
nb.cells=c
nb.metadata={'kernelspec':{'name':'project-python','display_name':'Python bất động sản','language':'python'},'language_info':{'name':'python','version':'3.12'}}
path=ROOT/'notebooks/02_03_ETL_EDA.ipynb'; path.parent.mkdir(exist_ok=True)
nbf.write(nb,path)
kdir=ROOT/'.jupyter/kernels/project-python'; kdir.mkdir(parents=True,exist_ok=True)
python=sys.executable
(kdir/'kernel.json').write_text(json.dumps({'argv':[python,'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'Python bất động sản','language':'python','env':({'PYTHONPATH':str(ROOT/'.deps'),'MPLCONFIGDIR':str(ROOT/'.mplconfig')} if (ROOT/'.deps').exists() else {})}))
ksm=KernelSpecManager(kernel_dirs=[str(ROOT/'.jupyter/kernels')])
km=KernelManager(kernel_name='project-python',kernel_spec_manager=ksm)
client=NotebookClient(nb,timeout=900,km=km,resources={'metadata':{'path':str(ROOT)}},allow_errors=False)
client.execute()
# Rút gọn đường dẫn máy chạy trước khi lưu notebook để chia sẻ công khai.
for cell in nb.cells:
    for output in cell.get('outputs', []):
        if isinstance(output.get('text'), str):
            output['text'] = output['text'].replace(str(ROOT), '<thu_muc_du_an>')
nb.metadata.kernelspec = {"name":"python3","display_name":"Python 3","language":"python"}
nbf.write(nb,path)
assert not any(o.output_type=='error' for cell in nb.cells if cell.cell_type=='code' for o in cell.get('outputs',[]))
print('Đã chạy và lưu:',path)
