"""Nhiệm vụ 5 (bổ sung): bản dashboard web (HTML một file) có tham số What-if, xem được không cần Power BI.

Dashboard chính của Nhiệm vụ 5 là Power BI (dashboard/BTL_NhiemVu5.pbip/.pbix, sinh bởi
scripts/prepare_dashboard_data.py + scripts/build_task5_pbip.py). Bản HTML dùng cùng output Nhiệm vụ 4 và cùng định nghĩa.

Chạy sau scripts/task4_modeling.py:
    python scripts/build_dashboard.py            # tạo dashboard/Dashboard_Chu_de_14.html
    python scripts/build_dashboard.py --screens  # thêm ảnh chụp cho báo cáo/slide (cần Google Chrome)

Mọi số trên dashboard được tính từ outputs/task4/tables/*; script tự đối chiếu số căn theo ngưỡng với
sensitivity_threshold.csv và dừng nếu lệch.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bds_valuation import selection as S  # noqa: E402

T = ROOT / "outputs" / "task4" / "tables"
OUT = ROOT / "dashboard"


def load():
    val = pd.read_csv(T / "king_oof_predictions.csv", dtype={"id": "string", "zipcode": "string"})
    summary = json.loads((T / "task4_summary.json").read_text(encoding="utf-8"))
    met = pd.read_csv(T / "model_metrics_mape_report.csv")
    thr = pd.read_csv(T / "sensitivity_threshold.csv")
    return val, summary, met, thr


def other_cols(val):
    return [c for c in ("residual_pct_rf", "residual_pct_lr", "residual_pct_xgb") if c in val][:2]


def pool_frame(val):
    pool = S.base_pool(val).copy()
    o1, o2 = other_cols(val)
    pool["resid_o1"], pool["resid_o2"] = pool[o1], pool[o2]
    return pool


def count_at(pool, t, mode="all"):
    sel = pool[pool["residual_pct"] <= -t]
    if mode == "rec":
        sel = sel[(sel["residual_pct"] >= S.ANOMALY_CAP) & (sel[["resid_o1", "resid_o2"]] <= -t).all(axis=1)
                  & (sel["house_age"] > 0)]
    return len(sel)


def verify(pool, thr):
    for _, r in thr.iterrows():
        got = count_at(pool, r["Nguong_%"] / 100)
        assert got == r["So_can_ung_vien"], f"Ngưỡng {r['Nguong_%']}%: dashboard {got} != bảng {r['So_can_ung_vien']}"


def write_html(pool, summary, met, thr):
    o = pool
    data = {
        "id": o["id"].tolist(), "zip": o["zipcode"].tolist(), "date": o["date"].tolist(),
        "lat": o["lat"].round(4).tolist(), "lon": o["long"].round(4).tolist(),
        "price": o["price"].astype(int).tolist(), "pred": o["predicted_price"].astype(int).tolist(),
        "r": o["residual_pct"].round(4).tolist(), "r1": o["resid_o1"].round(4).tolist(),
        "r2": o["resid_o2"].round(4).tolist(), "sqft": o["sqft_living"].astype(int).tolist(),
        "bed": o["bedrooms"].astype(int).tolist(), "grade": o["grade"].astype(int).tolist(),
        "cond": o["condition"].astype(int).tolist(), "age": o["house_age"].astype(int).tolist(),
    }
    km = met[met["Thi_truong"] == "King County"].set_index("Mo_hinh")
    best = summary["best_model"]
    nested = summary["king_nested_cv"]["MAPE_%"]
    tb = summary["king_temporal_backtest"]
    locked = tb["info"]["locked_model"]["model"]
    meta = {
        "best": best, "mape_test": round(float(km.loc[best, "MAPE_%"]), 2),
        "rmse_test": round(float(km.loc[best, "RMSE"])),
        "mape_naive": round(float(km.loc["Mốc thô: đơn giá zipcode × diện tích", "MAPE_%"]), 2),
        "mape_lr": round(float(km.loc["Linear Regression (baseline)", "MAPE_%"]), 2),
        "mape_nested": round(float(nested), 2), "mape_temporal": round(float(tb[locked]["MAPE_%"]), 2),
        "temporal_model": locked, "oof_mape": summary["oof_screening_mape_pct"],
        "pool": len(pool), "cap": S.ANOMALY_CAP, "n": S.N_CANDIDATES,
        "thr_table": thr[["Nguong_%", "So_can_ung_vien"]].values.tolist(),
    }
    html = TEMPLATE.replace("/*DATA*/null", json.dumps(data, separators=(",", ":"))) \
                   .replace("/*META*/null", json.dumps(meta, ensure_ascii=False))
    OUT.mkdir(exist_ok=True)
    (OUT / "Dashboard_Chu_de_14.html").write_text(html, encoding="utf-8")


def screenshots():
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.exists():
        chrome = Path(shutil.which("google-chrome") or shutil.which("chromium") or "")
    if not chrome or not Path(chrome).exists():
        print("Không có Chrome — bỏ qua ảnh chụp.")
        return
    shots = OUT / "screenshots"
    shots.mkdir(exist_ok=True)
    page = (OUT / "Dashboard_Chu_de_14.html").resolve().as_uri()
    for name, query, size in [("dashboard_nguong_20", "?t=20&theme=light", "1440,1640"), ("dashboard_nguong_10", "?t=10&theme=light", "1440,1640"),
                              ("dashboard_nguong_30", "?t=30&mode=all&theme=light", "1440,1640")]:
        subprocess.run([str(chrome), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={size}",
                        "--force-device-scale-factor=1", "--virtual-time-budget=4000",
                        f"--screenshot={shots / (name + '.png')}", page + query],
                       check=True, capture_output=True, timeout=120)
        print("Ảnh:", shots / f"{name}.png")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--screens", action="store_true")
    a = ap.parse_args(argv)
    val, summary, met, thr = load()
    pool = pool_frame(val)
    verify(pool, thr)
    write_html(pool, summary, met, thr)
    rec20 = count_at(pool, 0.20, "rec")
    t = 0.20
    rec = pool[(pool["residual_pct"] <= -t) & (pool["residual_pct"] >= S.ANOMALY_CAP)
               & (pool[["resid_o1", "resid_o2"]] <= -t).all(axis=1) & (pool["house_age"] > 0)]
    js_top = rec.assign(k=rec[["residual_pct", "resid_o1", "resid_o2"]].max(axis=1)).sort_values(["k", "id"]).head(20)["id"]
    official = pd.read_csv(T / "top20_candidates_below_prediction_king.csv", dtype={"id": "string"})["id"]
    assert list(js_top) == list(official), "Top 20 trên dashboard khác danh sách chính thức"
    assert rec20 == summary["recommended_pool_size"], (rec20, summary["recommended_pool_size"])
    print(f"Dashboard: {len(pool):,} căn trong pool; ngưỡng 20% -> {count_at(pool, .2):,} căn; đạt R4–R6 -> {rec20:,}")
    if a.screens:
        screenshots()


TEMPLATE = r"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard Định giá BĐS</title>
<style>
:root{--bg:#f7f7f5;--card:#ffffff;--ink:#16181d;--muted:#5c5f66;--line:#e3e2dd;--blue:#2a78d6;--orange:#eb6834;--gray:#b9b8b2;--soft:#eef3fb;--warn:#fff4e5}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#121316;--card:#1b1d22;--ink:#ecedef;--muted:#a3a6ad;--line:#2c2f36;--blue:#5b9cf0;--orange:#f08a5d;--gray:#4a4c52;--soft:#1d2633;--warn:#2e2419}}
:root[data-theme="dark"]{--bg:#121316;--card:#1b1d22;--ink:#ecedef;--muted:#a3a6ad;--line:#2c2f36;--blue:#5b9cf0;--orange:#f08a5d;--gray:#4a4c52;--soft:#1d2633;--warn:#2e2419}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
.wrap{max-width:1400px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 16px}
.grid{display:grid;gap:12px}.kpis{grid-template-columns:repeat(4,1fr)}@media (max-width:860px){.kpis{grid-template-columns:repeat(2,1fr)}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi .v{font-size:24px;font-weight:700;font-variant-numeric:tabular-nums}.kpi .l{color:var(--muted);font-size:12px}
.controls{display:grid;grid-template-columns:2fr 1fr 1fr;gap:16px;align-items:end}
@media (max-width:860px){.controls{grid-template-columns:1fr}.two{grid-template-columns:1fr!important}}
label{font-size:12px;color:var(--muted);display:block;margin-bottom:6px}
input[type=range]{width:100%;accent-color:var(--orange)}.big{font-size:20px;font-weight:700;color:var(--orange)}
select{width:100%;padding:6px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.seg button{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:6px 10px;cursor:pointer}
.seg button.on{background:var(--blue);color:#fff;border-color:var(--blue)}.seg button:first-child{border-radius:6px 0 0 6px}.seg button:last-child{border-radius:0 6px 6px 0}
.two{grid-template-columns:1fr 1fr}h2{font-size:15px;margin:0 0 8px}
canvas,svg{width:100%;display:block}.note{background:var(--warn);border:1px solid var(--line);border-radius:10px;padding:12px;font-size:13px}
.tbl{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}th{color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--card)}
td:nth-child(2),td:nth-child(3),th:nth-child(2),th:nth-child(3){text-align:left}
.legend{font-size:12px;color:var(--muted)}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 4px 0 10px;vertical-align:middle}
</style>
</head>
<body>
<div class="wrap">
<h1>Định giá bất động sản tự động — King County 2014–2015</h1>
<p class="sub">Sàng lọc giao dịch có <b>giá giao dịch thấp hơn giá dự báo</b> để đưa vào danh sách thẩm định. Mỗi căn chỉ tính giao dịch gần nhất, đã loại 0 phòng và condition ≤ 2 (R1–R3).</p>

<div class="grid kpis" id="kpis"></div>

<div class="card controls" style="margin-top:12px">
  <div><label for="t">Tham số What-if — ngưỡng: giá giao dịch thấp hơn dự báo ít nhất</label>
    <div style="display:flex;gap:12px;align-items:center"><input id="t" type="range" min="5" max="50" step="1" value="20"><span class="big" id="tv">20%</span></div></div>
  <div><label>Quy tắc lọc</label><div class="seg" id="mode"><button data-m="rec" class="on">R4–R6 (khuyến nghị)</button><button data-m="all">Chỉ ngưỡng</button></div></div>
  <div><label for="z">Zipcode</label><select id="z"><option value="">Tất cả</option></select></div>
</div>

<div class="grid two" style="margin-top:12px">
  <div class="card"><h2>Số căn ứng viên theo ngưỡng</h2><svg id="curve" viewBox="0 0 560 260" role="img" aria-label="Số căn theo ngưỡng"></svg></div>
  <div class="card"><h2>Vị trí ứng viên <span class="legend"><span class="dot" style="background:var(--gray)"></span>pool <span class="dot" style="background:var(--blue)"></span>đạt ngưỡng <span class="dot" style="background:var(--orange)"></span>top <span id="nlab"></span></span></h2><canvas id="map" width="560" height="300"></canvas></div>
</div>
<div class="grid two" style="margin-top:12px">
  <div class="card"><h2>Phân phối residual % (giá giao dịch / giá dự báo − 1)</h2><svg id="hist" viewBox="0 0 560 240" role="img" aria-label="Phân phối residual"></svg></div>
  <div class="card"><h2>Sai số mô hình (MAPE, %)</h2><svg id="mape" viewBox="0 0 560 240" role="img" aria-label="MAPE theo cách đánh giá"></svg></div>
</div>
<div class="card" style="margin-top:12px"><h2 id="ttitle">Danh sách thẩm định ưu tiên</h2><div class="tbl"><table id="tbl"></table></div></div>
<div class="note" style="margin-top:12px"><b>Cách đọc:</b> residual âm nghĩa là giá giao dịch lịch sử thấp hơn giá mô hình dự báo — <b>ứng viên cần xác minh</b>, chưa chứng minh bị định giá thấp (có thể do mô hình dự báo cao, thiếu đặc điểm, giao dịch đặc biệt hoặc lỗi dữ liệu). Chênh lệch so với giá dự báo không phải lợi nhuận. Ngưỡng và quy tắc R1–R7 là lựa chọn của nhóm, chưa hiệu chỉnh bằng kết quả thẩm định thực tế. Dữ liệu 2014–2015, không xác nhận hiện có thể mua ở giá đó.</div>
</div>
<script>
const D=/*DATA*/null, M=/*META*/null;
const N=D.id.length, fmt=n=>n.toLocaleString('vi-VN'), pct=v=>(v).toFixed(1).replace('.',',')+'%';
const css=k=>getComputedStyle(document.documentElement).getPropertyValue(k).trim();
const qs=new URLSearchParams(location.search);
if(qs.get('theme'))document.documentElement.setAttribute('data-theme',qs.get('theme'));
let T=+(qs.get('t')||20), MODE=qs.get('mode')||'rec', ZIP='';
const $=id=>document.getElementById(id);
$('t').value=T;
document.querySelectorAll('#mode button').forEach(b=>{b.classList.toggle('on',b.dataset.m===MODE);b.onclick=()=>{MODE=b.dataset.m;document.querySelectorAll('#mode button').forEach(x=>x.classList.toggle('on',x===b));render()}});
[...new Set(D.zip)].sort().forEach(z=>{const o=document.createElement('option');o.value=o.textContent=z;$('z').appendChild(o)});
$('z').onchange=e=>{ZIP=e.target.value;render()};
$('t').oninput=e=>{T=+e.target.value;render()};
function passes(i,t,mode){const th=-t/100;if(D.r[i]>th)return false;if(mode==='rec'){if(D.r[i]<M.cap||D.r1[i]>th||D.r2[i]>th||D.age[i]<=0)return false}return true}
function cons(i){return Math.max(D.r[i],D.r1[i],D.r2[i])}
function count(t,mode,zip){let c=0;for(let i=0;i<N;i++){if(zip&&D.zip[i]!==zip)continue;if(passes(i,t,mode))c++}return c}
function kpi(v,l){return `<div class="card kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`}
function render(){
  $('tv').textContent=T+'%';
  const sel=[];let inZip=0;for(let i=0;i<N;i++){if(ZIP&&D.zip[i]!==ZIP)continue;inZip++;if(passes(i,T,MODE))sel.push(i)}
  const key=MODE==='rec'?cons:(i=>D.r[i]);
  sel.sort((a,b)=>key(a)-key(b)||(D.id[a]<D.id[b]?-1:1));
  const top=sel.slice(0,M.n);const prices=sel.map(i=>D.price[i]).sort((a,b)=>a-b);
  const med=prices.length?prices[Math.floor((prices.length-1)/2)]:0;
  const sumP=top.reduce((s,i)=>s+D.price[i],0), sumPred=top.reduce((s,i)=>s+D.pred[i],0);
  $('kpis').innerHTML=kpi(pct(M.mape_test),`MAPE test — ${M.best}`)+kpi(pct(M.mape_nested),'MAPE nested CV (nghiêm ngặt)')+
    kpi(pct(M.mape_temporal),`MAPE backtest thời gian — ${M.temporal_model}`)+kpi(fmt(sel.length),`Số căn ứng viên (ngưỡng ${T}%)`)+
    kpi(pct(100*sel.length/Math.max(inZip,1)),'Tỷ lệ ứng viên trong pool')+kpi(fmt(med)+' $','Giá trung vị ứng viên')+
    kpi(fmt(sumP)+' $',`Tổng giá lịch sử top ${top.length}`)+kpi(fmt(sumPred)+' $',`Tổng giá dự báo top ${top.length}`);
  $('nlab').textContent=M.n;
  drawCurve();drawMap(sel,top);drawHist();drawMape();drawTable(top);
  $('ttitle').textContent=`Danh sách thẩm định ưu tiên — ${top.length} căn đầu (${MODE==='rec'?'R4–R7, xếp theo mức thấp hơn dự báo thận trọng':'chỉ theo ngưỡng, xếp theo residual của mô hình chính'})`;
}
function drawCurve(){const s=$('curve'),W=560,H=260,L=56,B=36,R=14,Tp=12;let pts=[];for(let t=5;t<=50;t++)pts.push([t,count(t,MODE,ZIP)]);
  const ymax=Math.max(...pts.map(p=>p[1]),1),x=t=>L+(t-5)/45*(W-L-R),y=v=>H-B-(v/ymax)*(H-B-Tp);
  let g=`<line x1="${L}" y1="${H-B}" x2="${W-R}" y2="${H-B}" stroke="${css('--line')}"/>`;
  for(let k=0;k<=4;k++){const v=Math.round(ymax*k/4);g+=`<text x="${L-6}" y="${y(v)+4}" font-size="11" text-anchor="end" fill="${css('--muted')}">${fmt(v)}</text><line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="${css('--line')}" stroke-dasharray="2 3"/>`}
  for(let t=5;t<=50;t+=5)g+=`<text x="${x(t)}" y="${H-B+16}" font-size="11" text-anchor="middle" fill="${css('--muted')}">${t}%</text>`;
  g+=`<polyline fill="none" stroke="${css('--blue')}" stroke-width="2" points="${pts.map(p=>x(p[0])+','+y(p[1])).join(' ')}"/>`;
  const c=pts.find(p=>p[0]===T);g+=`<line x1="${x(T)}" x2="${x(T)}" y1="${Tp}" y2="${H-B}" stroke="${css('--orange')}"/><circle cx="${x(T)}" cy="${y(c[1])}" r="5" fill="${css('--orange')}"/><text x="${x(T)+8}" y="${y(c[1])-8}" font-size="12" fill="${css('--ink')}">${fmt(c[1])} căn</text>`;
  g+=`<line x1="${L}" x2="${W-R}" y1="${y(M.n)}" y2="${y(M.n)}" stroke="${css('--orange')}" stroke-dasharray="4 3" opacity=".6"/><text x="${W-R}" y="${y(M.n)-4}" font-size="10" text-anchor="end" fill="${css('--muted')}">ràng buộc ${M.n} căn</text>`;
  g+=`<text x="${(L+W-R)/2}" y="${H-4}" font-size="11" text-anchor="middle" fill="${css('--muted')}">Ngưỡng thấp hơn dự báo</text>`;s.innerHTML=g}
function drawMap(sel,top){const c=$('map'),dpr=window.devicePixelRatio||1,W=c.clientWidth||560,H=W*0.54;c.width=W*dpr;c.height=H*dpr;c.style.height=H+'px';const x=c.getContext('2d');x.scale(dpr,dpr);
  const lo=[-122.52,-121.31],la=[47.15,47.78],px=v=>(v-lo[0])/(lo[1]-lo[0])*W,py=v=>H-(v-la[0])/(la[1]-la[0])*H;
  x.fillStyle=css('--card');x.fillRect(0,0,W,H);x.globalAlpha=.35;x.fillStyle=css('--gray');for(let i=0;i<N;i+=1){if(ZIP&&D.zip[i]!==ZIP)continue;x.fillRect(px(D.lon[i]),py(D.lat[i]),1.6,1.6)}
  x.globalAlpha=.8;x.fillStyle=css('--blue');sel.forEach(i=>{x.beginPath();x.arc(px(D.lon[i]),py(D.lat[i]),2.2,0,7);x.fill()});
  x.globalAlpha=1;top.forEach(i=>{x.beginPath();x.arc(px(D.lon[i]),py(D.lat[i]),5.5,0,7);x.fillStyle=css('--orange');x.fill();x.strokeStyle=css('--card');x.lineWidth=1.5;x.stroke()})}
function drawHist(){const s=$('hist'),W=560,H=240,L=40,B=34,R=10,Tp=10,lo=-0.8,hi=0.8,nb=64,bins=new Array(nb).fill(0);
  for(let i=0;i<N;i++){if(ZIP&&D.zip[i]!==ZIP)continue;const v=Math.min(hi-1e-9,Math.max(lo,D.r[i]));bins[Math.floor((v-lo)/(hi-lo)*nb)]++}
  const ym=Math.max(...bins,1),bw=(W-L-R)/nb,x=v=>L+(v-lo)/(hi-lo)*(W-L-R);let g='';
  bins.forEach((b,k)=>{const v=lo+(k+.5)*(hi-lo)/nb,h=b/ym*(H-B-Tp);g+=`<rect x="${L+k*bw}" y="${H-B-h}" width="${bw-1}" height="${h}" fill="${v<=-T/100?css('--orange'):css('--blue')}" opacity=".85"/>`});
  [-0.8,-0.4,0,0.4,0.8].forEach(v=>g+=`<text x="${x(v)}" y="${H-B+16}" font-size="11" text-anchor="middle" fill="${css('--muted')}">${Math.round(v*100)}%</text>`);
  g+=`<line x1="${x(-T/100)}" x2="${x(-T/100)}" y1="${Tp}" y2="${H-B}" stroke="${css('--ink')}" stroke-dasharray="3 3"/><text x="${x(-T/100)-4}" y="${Tp+10}" font-size="11" text-anchor="end" fill="${css('--ink')}">−${T}%</text>`;s.innerHTML=g}
function drawMape(){const s=$('mape'),rows=[['Mốc thô (đơn giá zipcode × diện tích)',M.mape_naive],['Linear Regression (baseline), test',M.mape_lr],[M.best+', test',M.mape_test],['Nested CV (tinh chỉnh + chọn trong fold)',M.mape_nested],['Backtest thời gian ('+M.temporal_model+')',M.mape_temporal],['OOF sàng lọc (TB 4 seed)',M.oof_mape]];
  const W=560,L=250,R=50,bh=26,mx=Math.max(...rows.map(r=>r[1]));let g='';rows.forEach((r,k)=>{const y=10+k*(bh+10),w=(W-L-R)*r[1]/mx;
  g+=`<text x="${L-8}" y="${y+bh/2+4}" font-size="11.5" text-anchor="end" fill="${css('--ink')}">${r[0]}</text><rect x="${L}" y="${y}" width="${w}" height="${bh}" rx="3" fill="${k===2?css('--blue'):css('--gray')}"/><text x="${L+w+6}" y="${y+bh/2+4}" font-size="12" fill="${css('--ink')}">${pct(r[1])}</text>`});s.innerHTML=g}
function drawTable(top){const h=['#','Mã id','Zip','Ngày','Giá giao dịch ($)','Giá dự báo ($)','Thấp hơn dự báo','Thận trọng (3 mô hình)','Sqft','PN','Grade','Cond','Tuổi'];
  let r='<tr>'+h.map(x=>`<th>${x}</th>`).join('')+'</tr>';top.forEach((i,k)=>{r+=`<tr><td>${k+1}</td><td>${D.id[i]}</td><td>${D.zip[i]}</td><td>${D.date[i]}</td><td>${fmt(D.price[i])}</td><td>${fmt(D.pred[i])}</td><td>${pct(-100*D.r[i])}</td><td>${pct(-100*cons(i))}</td><td>${fmt(D.sqft[i])}</td><td>${D.bed[i]}</td><td>${D.grade[i]}</td><td>${D.cond[i]}</td><td>${D.age[i]}</td></tr>`});
  if(!top.length)r+='<tr><td colspan="13" style="text-align:center">Không có căn nào thỏa điều kiện</td></tr>';$('tbl').innerHTML=r}
render();window.addEventListener('resize',render);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
