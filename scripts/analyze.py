"""EDA và chẩn đoán tái lập cho nhiệm vụ 3; chạy từ bất kỳ thư mục nào."""
from pathlib import Path
import json, sys, warnings
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
TABLES, FIGURES = ROOT/'outputs/tables', ROOT/'outputs/figures'
for folder in (TABLES, FIGURES):
    folder.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'figure.dpi':120,
                     'savefig.dpi':180,'axes.spines.top':False,'axes.spines.right':False})
COLORS = {'low':'#D55E00','rest':'#0072B2'}
LABELS = {'price':'Giá bán (USD)','sqft_living':'Diện tích ở (sqft)',
          'house_age':'Tuổi nhà (năm)','sqft_lot':'Diện tích đất (sqft)',
          'lot_area':'Diện tích đất (sqft)','grade':'Hạng chất lượng',
          'overall_qual':'Chất lượng tổng thể','bathrooms':'Số phòng tắm',
          'bedrooms':'Số phòng ngủ','bedroom_abvgr':'Phòng ngủ trên mặt đất',
          'distance_to_center_km':'Khoảng cách đến mốc trung tâm (km)',
          'bathrooms_total':'Phòng tắm trên mặt đất (quy đổi)'}

def holm(pvalues):
    """Holm step-down, kiểm soát family-wise error; giữ NaN khi không kiểm định được."""
    p = np.asarray(pvalues, dtype=float)
    result = np.full(len(p), np.nan)
    valid = np.flatnonzero(np.isfinite(p)); order = valid[np.argsort(p[valid])]
    result[order] = np.minimum(1, np.maximum.accumulate((len(order)-np.arange(len(order)))*p[order]))
    return result

def truth(s):
    if s.dtype == bool: return s.fillna(False)
    return s.astype(str).str.lower().isin(['true','1','1.0'])

def independent_sample(df, dataset):
    """Đơn vị suy luận King là tài sản: giữ giao dịch sớm nhất, không chọn theo giá."""
    if dataset == 'king_county':
        return df.sort_values(['date','source_row_id']).drop_duplicates('id',keep='first').copy()
    # De Cock giữ giao dịch mới nhất mỗi PID trước khi công bố dữ liệu Ames.
    assert not df['pid'].duplicated().any(), 'Ames PID lặp: cần xác định đơn vị độc lập'
    return df.copy()

def welch_row(df, field):
    low = pd.to_numeric(df.loc[df.undervalued_global,field],errors='coerce').dropna().to_numpy()
    rest = pd.to_numeric(df.loc[~df.undervalued_global,field],errors='coerce').dropna().to_numpy()
    n1,n0=len(low),len(rest)
    if min(n1,n0)<3: return None
    m1,m0=low.mean(),rest.mean(); v1,v0=low.var(ddof=1),rest.var(ddof=1)
    se=np.sqrt(v1/n1+v0/n0)
    if se == 0: return None
    dfree=(v1/n1+v0/n0)**2/((v1/n1)**2/(n1-1)+(v0/n0)**2/(n0-1))
    t,p=stats.ttest_ind(low,rest,equal_var=False)
    diff=m1-m0; critical=stats.t.ppf(.975,dfree)
    pooled=np.sqrt(((n1-1)*v1+(n0-1)*v0)/(n1+n0-2))
    correction=1-3/(4*(n1+n0)-9)
    return dict(variable=field,n_low=n1,n_rest=n0,mean_low=m1,mean_rest=m0,
                difference_low_minus_rest=diff,ci95_low=diff-critical*se,
                ci95_high=diff+critical*se,t=float(t),df=dfree,p_raw=float(p),
                hedges_g=correction*diff/pooled if pooled>0 else np.nan)

def savefig(name):
    plt.savefig(FIGURES/f'{name}.png',bbox_inches='tight')
    plt.savefig(FIGURES/f'{name}.svg',bbox_inches='tight')
    plt.close()

def draw_figures(df,key,title,fields,geo):
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    sns.histplot(df.price/1000,bins=55,color=COLORS['rest'],ax=axes[0])
    axes[0].axvline(.8*df.price.median()/1000,color=COLORS['low'],ls='--',label='Ngưỡng 80% trung vị')
    axes[0].set(xlabel='Giá bán (nghìn USD)',ylabel='Số giao dịch',title='Thang giá gốc')
    axes[0].legend(fontsize=9)
    sns.histplot(np.log10(df.price),bins=45,color=COLORS['rest'],ax=axes[1])
    axes[1].set(xlabel='log10 giá bán (USD)',ylabel='Số giao dịch',title='Thang logarit')
    fig.suptitle(f'{title} | Phân phối giá bán',fontweight='bold'); fig.tight_layout()
    savefig(f'{key}_price_distribution')
    medians=df.groupby(geo).price.median().sort_values()
    order=list(medians.index); chunks=np.array_split(np.array(order,dtype=object),2 if len(order)>40 else 1)
    fig,axes=plt.subplots(1,len(chunks),figsize=(14 if len(chunks)>1 else 10,11),squeeze=False)
    for ax,chunk in zip(axes.flat,chunks):
        sns.boxplot(data=df,x='price',y=geo,order=list(chunk),color='#9BC9E0',showfliers=False,ax=ax)
        ax.set_xscale('log'); ax.set(xlabel='Giá bán USD (thang log)',ylabel='Mã ZIP' if geo=='zipcode' else 'Khu dân cư')
        counts=df[geo].value_counts()
        ax.set_yticks(range(len(chunk)),[f'{x} (n={counts[x]:,})' for x in chunk],fontsize=9)
        ax.grid(axis='x',alpha=.2)
    if len(chunks)>1:
        limits=(min(ax.get_xlim()[0] for ax in axes.flat),max(ax.get_xlim()[1] for ax in axes.flat))
        for ax in axes.flat:
            ax.set_xticks([100000,300000,1000000,3000000],['100k','300k','1M','3M'])
            ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
            ax.set_xlim(limits)
    else:
        limits=axes.flat[0].get_xlim()
        axes.flat[0].set_xticks([20000,50000,100000,200000,500000],['20k','50k','100k','200k','500k'])
        axes.flat[0].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        axes.flat[0].set_xlim(limits)
    fig.suptitle(f'{title} | Giá theo {"zipcode" if geo=="zipcode" else "neighborhood"}\nSắp theo trung vị; ẩn điểm ngoại lệ trên biểu đồ, vẫn giữ trong thống kê',fontweight='bold',fontsize=13)
    fig.tight_layout(rect=[0,0,1,.95]); savefig(f'{key}_geographic_boxplot')
    selected=['price']+fields
    corr=df[selected].corr(method='spearman')
    fig,ax=plt.subplots(figsize=(10,8))
    sns.heatmap(corr,annot=True,fmt='.2f',cmap='RdBu_r',vmin=-1,vmax=1,center=0,
                xticklabels=[LABELS.get(x,x) for x in selected],yticklabels=[LABELS.get(x,x) for x in selected],ax=ax)
    ax.set_title(f'{title} | Tương quan hạng Spearman',pad=15,fontweight='bold')
    ax.tick_params(axis='x',labelrotation=65); fig.tight_layout(); savefig(f'{key}_spearman_heatmap')
    view=['sqft_living','house_age','grade' if key=='king_county' else 'overall_qual',
          'distance_to_center_km' if key=='king_county' else 'bathrooms_total']
    fig,axes=plt.subplots(1,4,figsize=(14,4.3))
    for ax,field in zip(axes,view):
        groups=[df.loc[df.undervalued_global,field].dropna(),df.loc[~df.undervalued_global,field].dropna()]
        bp=ax.boxplot(groups,patch_artist=True,showfliers=False,widths=.55)
        for box,c in zip(bp['boxes'],COLORS.values()): box.set_facecolor(c); box.set_alpha(.65)
        ax.set_xticks([1,2],['Nhóm giá thấp','Còn lại'],rotation=20,fontsize=9)
        ax.set_title(LABELS[field],fontsize=11); ax.grid(axis='y',alpha=.15)
    fig.suptitle(f'{title} | Đặc điểm hai nhóm theo ngưỡng 80% trung vị giá',fontweight='bold')
    fig.tight_layout(); savefig(f'{key}_group_comparison')
    fig,axes=plt.subplots(1,3,figsize=(13,4.2))
    xfields=['sqft_living','house_age','distance_to_center_km' if key=='king_county' else 'overall_qual']
    for ax,field in zip(axes,xfields):
        hb=ax.hexbin(df[field],np.log10(df.price),gridsize=35,mincnt=1,cmap='Blues',bins='log')
        ax.set(xlabel=LABELS[field],ylabel='log10 giá bán (USD)')
    fig.suptitle(f'{title} | Giá và các thuộc tính',fontweight='bold')
    fig.tight_layout(); savefig(f'{key}_price_relationships')


def run_analysis():
    frames={}; summary={}; descriptives=[]; groups=[]; welch=[]; directional=[]; sensitivity=[]; geo_tables=[]
    for key,title in [('king_county','King County'),('ames','Ames')]:
        path=ROOT/f'data/processed/{key}_clean.csv'
        df=pd.read_csv(path,dtype={'id':'string','pid':'string','zipcode':'string'})
        assert df.price.gt(0).all() and df.sqft_living.gt(0).all()
        df['undervalued_global']=df.price.lt(.8*df.price.median())
        geo='zipcode' if key=='king_county' else 'neighborhood'
        localmedian=df.groupby(geo).price.transform('median')
        df['undervalued_local']=df.price.lt(.8*localmedian)
        df['local_reference_median']=localmedian
        if key=='ames':
            df['bathrooms_total']=df.full_bath+.5*df.half_bath
        fields=['sqft_living','house_age','sqft_lot','grade','bathrooms','bedrooms','distance_to_center_km'] if key=='king_county' else ['sqft_living','house_age','lot_area','overall_qual','bathrooms_total','bedroom_abvgr']
        sample=independent_sample(df,key)
        desc=df[['price','price_per_sqft']+fields].describe(percentiles=[.01,.25,.5,.75,.99]).T.reset_index(names='variable')
        desc.insert(0,'dataset',key); descriptives.append(desc)
        for field in ['price','price_per_sqft']+fields:
            for low,label in [(True,'low_price'),(False,'rest')]:
                values=df.loc[df.undervalued_global.eq(low),field].dropna()
                groups.append(dict(dataset=key,group=label,variable=field,n=len(values),mean=values.mean(),median=values.median(),sd=values.std()))
        wr=[welch_row(sample,field) for field in fields]; wr=[r for r in wr if r]
        adj=holm([r['p_raw'] for r in wr])
        for r,padj in zip(wr,adj):
            r.update(dataset=key,p_holm=padj,significant_holm=bool(padj<.05),sample='one_sale_per_property',
                     group_threshold=.8*df.price.median()); welch.append(r)
        expected={'sqft_living':'positive','house_age':'negative','grade' if key=='king_county' else 'overall_qual':'positive'}
        if key=='king_county': expected['distance_to_center_km']='negative'
        dr=[]
        for field,direction in expected.items():
            valid=sample[[field,'price']].dropna()
            # Alternative đã khai báo theo giả thuyết trước khi tính kết quả.
            alternative='greater' if direction=='positive' else 'less'
            test=stats.spearmanr(valid[field],valid.price,alternative=alternative)
            dr.append(dict(dataset=key,variable=field,expected_direction=direction,n=len(valid),rho=float(test.statistic),p_one_sided=float(test.pvalue),sample='one_sale_per_property'))
        for r,padj in zip(dr,holm([r['p_one_sided'] for r in dr])):
            same=(r['rho']>0) == (r['expected_direction']=='positive')
            r.update(p_holm=padj,conclusion='supported' if same and padj<.05 else ('opposite_observed' if not same else 'inconclusive'))
            directional.append(r)
        for discount in [.1,.2,.3]:
            g=df.price.lt((1-discount)*df.price.median()); loc=df.price.lt((1-discount)*localmedian)
            sensitivity.append(dict(dataset=key,analysis='threshold',discount=discount,reference='global',n=len(df),n_low=int(g.sum()),share_low=float(g.mean()),overlap_with_global20=int((g & df.undervalued_global).sum())))
            sensitivity.append(dict(dataset=key,analysis='threshold',discount=discount,reference=geo,n=len(df),n_low=int(loc.sum()),share_low=float(loc.mean()),overlap_with_global20=int((loc & df.undervalued_global).sum())))
        subsets={'all_transactions':df,'one_sale_per_property':sample,
                 'exclude_price_or_area_iqr':sample.loc[~(truth(sample.price_iqr_outlier)|truth(sample.area_iqr_outlier))],
                 'exclude_true_imputation':sample.loc[~truth(sample.has_true_imputation)]}
        if key=='ames':
            subsets['exclude_ames_over_4000_sqft']=sample.loc[sample.sqft_living.le(4000)]
        for name,sub in subsets.items():
            sr=[welch_row(sub,f) for f in fields]; sr=[r for r in sr if r]
            for r,padj in zip(sr,holm([r['p_raw'] for r in sr])):
                sensitivity.append(dict(dataset=key,analysis='welch_robustness',reference=name,n=len(sub),variable=r['variable'],difference_low_minus_rest=r['difference_low_minus_rest'],p_raw=r['p_raw'],p_holm=padj,n_low=r['n_low'],n_rest=r['n_rest'],hedges_g=r['hedges_g']))
        geo_tab=df.groupby(geo).agg(n=('price','size'),median_price=('price','median'),mean_price=('price','mean'),n_low_global=('undervalued_global','sum'),n_low_local=('undervalued_local','sum')).reset_index()
        geo_tab.insert(0,'dataset',key); geo_tab.rename(columns={geo:'geography'},inplace=True); geo_tables.append(geo_tab)
        df[['source_row_id','price','local_reference_median','undervalued_global','undervalued_local']].to_csv(TABLES/f'{key}_group_labels.csv',index=False)
        summary[key]=dict(name=title,n=len(df),n_independent=len(sample),median_price=float(df.price.median()),mean_price=float(df.price.mean()),min_price=float(df.price.min()),max_price=float(df.price.max()),price_skew=float(df.price.skew()),threshold_global20=float(.8*df.price.median()),n_low=int(df.undervalued_global.sum()),share_low=float(df.undervalued_global.mean()),n_low_local=int(df.undervalued_local.sum()),share_low_local=float(df.undervalued_local.mean()),n_overlap_global_local=int((df.undervalued_global & df.undervalued_local).sum()),n_geographies=int(df[geo].nunique()),sale_year_min=int(pd.to_datetime(df.date).dt.year.min()) if key=='king_county' else int(df.yr_sold.min()),sale_year_max=int(pd.to_datetime(df.date).dt.year.max()) if key=='king_county' else int(df.yr_sold.max()),n_resales_removed_inference=int(len(df)-len(sample)),fields=fields)
        draw_figures(df,key,title,fields,geo)
        frames[key]=df
    pd.concat(descriptives).to_csv(TABLES/'summary_statistics.csv',index=False)
    pd.DataFrame(groups).to_csv(TABLES/'group_summary.csv',index=False)
    pd.DataFrame(welch).to_csv(TABLES/'welch_tests.csv',index=False)
    pd.DataFrame(directional).to_csv(TABLES/'directional_tests.csv',index=False)
    pd.DataFrame(sensitivity).to_csv(TABLES/'sensitivity.csv',index=False)
    pd.concat(geo_tables).to_csv(TABLES/'geographic_summary.csv',index=False)
    result={'definition':'price < 0.8 * median(price) trong từng bộ dữ liệu sạch; strict <',
            'interpretation':'Nhãn low-price proxy, không chứng minh nhà bị định giá thấp so với giá trị thị trường.',
            'inference':'King County dùng giao dịch sớm nhất mỗi id; Ames mỗi PID một quan sát. Ngưỡng nhóm giữ theo toàn bộ dữ liệu sạch.',
            'alpha':.05,'multiple_testing':'Holm điều chỉnh riêng từng dataset và từng họ Welch hoặc Spearman; CI95% Welch riêng từng biến, không đồng thời.',
            'datasets':summary,'welch':welch,'directional':directional}
    (TABLES/'analysis_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    lines=['NHIỆM VỤ 3  PHÂN TÍCH MÔ TẢ VÀ CHẨN ĐOÁN','',result['definition'],result['interpretation'],result['inference'],result['multiple_testing'],'']
    for key,s in summary.items():
        lines += [f"{s['name']}: n={s['n']:,}; suy luận n={s['n_independent']:,}; trung vị {s['median_price']:,.0f} USD; ngưỡng {s['threshold_global20']:,.0f} USD; nhóm thấp {s['n_low']:,} ({s['share_low']:.2%}); nhóm thấp theo địa phương {s['n_low_local']:,} ({s['share_low_local']:.2%})."]
        for r in welch:
            if r['dataset']==key:
                lines.append(f"Welch {r['variable']}: mean thấp={r['mean_low']:.3f}; còn lại={r['mean_rest']:.3f}; chênh lệch={r['difference_low_minus_rest']:.3f}; CI95% [{r['ci95_low']:.3f},{r['ci95_high']:.3f}]; p Holm={r['p_holm']:.4g}; Hedges g={r['hedges_g']:.3f}.")
        for r in directional:
            if r['dataset']==key: lines.append(f"Spearman {r['variable']} kỳ vọng {r['expected_direction']}: rho={r['rho']:.4f}; p Holm một phía={r['p_holm']:.4g}; kết luận={r['conclusion']}.")
    lines += ['', 'Giới hạn: t-test coi chất lượng thứ bậc như số để so trung bình; cần đọc kèm tương quan hạng. Dữ liệu quan sát lịch sử, chưa điều chỉnh đầy đủ vị trí/thời gian/chất lượng nên không diễn dịch nhân quả. Phụ thuộc không gian có thể còn lại dù bỏ bán lặp. P-value có thể rất nhỏ do cỡ mẫu lớn, phải đọc CI và effect size. Ames nguyên bản không có tọa độ hoặc zipcode; không tính khoảng cách và dùng neighborhood thay thế phân nhóm địa lý. Các giao dịch giá cao hợp lệ được giữ; loại điểm IQR chỉ là sensitivity. Median nhóm tính toàn mẫu phục vụ EDA; khi mô hình hóa phải fit ngưỡng/imputation trên train để tránh leakage. Không dùng price_per_sqft hoặc nhãn undervalued làm predictor giá.']
    (ROOT/'docs/eda_interpretation.txt').write_text('\n'.join(lines),encoding='utf8')
    assert len(welch)==13 and len(directional)==7
    assert all(0<=r['p_holm']<=1 for r in welch+directional)
    assert all(r['ci95_low']<=r['difference_low_minus_rest']<=r['ci95_high'] for r in welch)
    assert np.allclose(holm([.01,.04,.03]),[.03,.06,.06])
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return result

if __name__=='__main__': run_analysis()
