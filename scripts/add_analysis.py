import argparse
from collections import defaultdict
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import DataBarRule
from openpyxl.chart import BarChart, Reference

ap=argparse.ArgumentParser(description='为达人直播工作簿生成“产出分析”sheet')
ap.add_argument('--workbook',required=True)
ap.add_argument('--out',required=True)
ap.add_argument('--sheet',default='产出分析')
args=ap.parse_args()
SRC=args.workbook
OUT=args.out
SHEET=args.sheet

wb=load_workbook(SRC,data_only=True)
if SHEET in wb.sheetnames:
    del wb[SHEET]
ws=wb.create_sheet(SHEET)
ws.sheet_properties.tabColor='2F5597'
ws.sheet_view.showGridLines=False

# ---------- 读取聚合 ----------
dr=wb['达人']; pt=wb['点位']; pd=wb['单品']
creator=defaultdict(lambda:{'name':'','org':'','gmv':0.0,'buyers':0,'orders':0,'items':0,'dates':set()})
daily=defaultdict(lambda:{'gmv':0.0,'buyers':0,'orders':0,'items':0,'authors':set(),'contents':set(),'skus':set()})
month=defaultdict(lambda:{'gmv':0.0,'buyers':0,'orders':0,'items':0,'authors':set(),'dates':set()})
product=defaultdict(lambda:{'name':'','gmv':0.0,'buyers':0,'orders':0,'items':0,'authors':set(),'dates':set()})
author_contents=defaultdict(set); author_skus=defaultdict(set)

def f(v): return float(v or 0)
for r in range(2,dr.max_row+1):
    date=str(dr.cell(r,2).value)[:10]
    author=str(dr.cell(r,3).value)
    if not date or date=='None' or not author or author=='None': continue
    name=dr.cell(r,4).value or ''
    org=dr.cell(r,1).value or '未知'
    g=f(dr.cell(r,12).value); b=f(dr.cell(r,13).value); o=f(dr.cell(r,14).value); it=f(dr.cell(r,15).value)
    c=creator[author]
    if not c['name']: c['name']=name
    if not c['org']: c['org']=org
    c['gmv']+=g; c['buyers']+=b; c['orders']+=o; c['items']+=it; c['dates'].add(date)
    d=daily[date]
    d['gmv']+=g; d['buyers']+=b; d['orders']+=o; d['items']+=it; d['authors'].add(author)
    m=month[date[:7]]
    m['gmv']+=g; m['buyers']+=b; m['orders']+=o; m['items']+=it; m['authors'].add(author); m['dates'].add(date)

for r in range(2,pt.max_row+1):
    date=str(pt.cell(r,4).value)[:10]; author=str(pt.cell(r,1).value); cid=str(pt.cell(r,5).value)
    if not date or date=='None': continue
    if cid and cid!='None': daily[date]['contents'].add(cid); author_contents[author].add(cid)

for r in range(2,pd.max_row+1):
    date=str(pd.cell(r,5).value)[:10]; author=str(pd.cell(r,1).value); sku=str(pd.cell(r,6).value)
    if not date or date=='None' or not sku or sku=='None': continue
    name=pd.cell(r,7).value or ''
    g=f(pd.cell(r,12).value); b=f(pd.cell(r,13).value); o=f(pd.cell(r,14).value); it=f(pd.cell(r,15).value)
    p=product[sku]
    if not p['name']: p['name']=name
    p['gmv']+=g; p['buyers']+=b; p['orders']+=o; p['items']+=it; p['authors'].add(author); p['dates'].add(date)
    daily[date]['skus'].add(sku); author_skus[author].add(sku)

total_gmv=sum(c['gmv'] for c in creator.values())
total_buyers=sum(d['buyers'] for d in daily.values())
total_orders=sum(d['orders'] for d in daily.values())
total_items=sum(d['items'] for d in daily.values())
days=len(daily); dates=sorted(daily)
unique_contents=set().union(*[d['contents'] for d in daily.values()]) if daily else set()
unique_skus=set(product)

creators_sorted=sorted(creator.items(),key=lambda kv:kv[1]['gmv'],reverse=True)
products_sorted=sorted(product.items(),key=lambda kv:kv[1]['gmv'],reverse=True)
top10_creator=sum(v['gmv'] for _,v in creators_sorted[:10])/total_gmv if total_gmv else 0
top10_product=sum(v['gmv'] for _,v in products_sorted[:10])/total_gmv if total_gmv else 0
top_creator=creators_sorted[0] if creators_sorted else ('',{'gmv':0,'name':'','org':''})
top_day=max(daily.items(),key=lambda kv:kv[1]['gmv']) if daily else ('',{'gmv':0})
top_product=products_sorted[0] if products_sorted else ('',{'gmv':0,'name':''})

# ---------- 样式 ----------
NAVY='1F4E78'; BLUE='2F5597'; LIGHT='D9E2F3'; BAND='F4F7FB'; WHITE='FFFFFF'
thin=Side(style='thin',color='BFBFBF')
BORDER=Border(left=thin,right=thin,top=thin,bottom=thin)
def title(row,text,ncols=14):
    ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=ncols)
    c=ws.cell(row,1,text); c.fill=PatternFill('solid',fgColor=NAVY); c.font=Font(name='微软雅黑',size=16,bold=True,color=WHITE)
    c.alignment=Alignment(horizontal='left',vertical='center'); ws.row_dimensions[row].height=32
def section(row,text,ncols=14):
    ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=ncols)
    c=ws.cell(row,1,text); c.fill=PatternFill('solid',fgColor=LIGHT); c.font=Font(name='微软雅黑',size=12,bold=True,color=NAVY)
    c.alignment=Alignment(horizontal='left',vertical='center'); ws.row_dimensions[row].height=24
def header(row,heads):
    for j,h in enumerate(heads,1):
        c=ws.cell(row,j,h); c.fill=PatternFill('solid',fgColor=BLUE); c.font=Font(name='微软雅黑',size=9,bold=True,color=WHITE)
        c.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True); c.border=BORDER
    ws.row_dimensions[row].height=30
def put(row,vals,fmts=None,band=False,wrap=False):
    for j,v in enumerate(vals,1):
        c=ws.cell(row,j,v); c.border=BORDER; c.font=Font(name='微软雅黑',size=9)
        c.alignment=Alignment(horizontal='left' if isinstance(v,str) else 'right',vertical='center',wrap_text=wrap)
        if fmts and j<=len(fmts) and fmts[j-1]: c.number_format=fmts[j-1]
        if band: c.fill=PatternFill('solid',fgColor=BAND)

# ---------- 标题 ----------
title(1,f'京东商智达人直播产出分析  {dates[0]} ～ {dates[-1]}')
ws.merge_cells('A2:N2')
ws['A2']='口径：仅统计“当日引导成交人数 > 0”的记录；金额为当日引导成交金额；“成交人次”为按日累加，非去重人数；点位金额因同一订单被多条内容重复归因，不参与总额校验。'
ws['A2'].font=Font(name='微软雅黑',size=9,color='595959'); ws['A2'].alignment=Alignment(wrap_text=True,vertical='center'); ws.row_dimensions[2].height=38

# ---------- 一、总览 ----------
row=4; section(row,'一、总览')
row+=1; header(row,['指标','数值','口径说明']); ws.merge_cells(start_row=row,start_column=3,end_row=row,end_column=5)
row+=1
kpis=[
 ('总产出金额',round(total_gmv,2),'#,##0.00',f'{dates[0]} 至 {dates[-1]}，共 {days} 个有数据日'),
 ('成交人次',int(total_buyers),'#,##0','按日累加，非去重人数'),
 ('成交单量',int(total_orders),'#,##0','当日引导成交单量合计'),
 ('成交件数',int(total_items),'#,##0','当日引导商品成交件数合计'),
 ('达人数',len(creator),'#,##0','出现产出的去重达人 ID 数'),
 ('内容数',len(unique_contents),'#,##0','点位表中出现的去重内容 ID 数'),
 ('SKU 数',len(unique_skus),'#,##0','单品表中出现的去重 SKU 数'),
 ('有数据天数',days,'0','该区间内商智返回产出的天数'),
 ('日均产出',round(total_gmv/days,2) if days else 0,'#,##0.00','总产出 / 有数据天数'),
 ('客单价',round(total_gmv/total_buyers,2) if total_buyers else 0,'#,##0.00','总产出 / 成交人次（近似）'),
 ('Top10 达人集中度',round(top10_creator,4),'0.00%','前 10 名达人产出占总额比例'),
 ('Top10 商品集中度',round(top10_product,4),'0.00%','前 10 名 SKU 产出占总额比例'),
]
for label,val,fmt,note in kpis:
    ws.cell(row,1,label).fill=PatternFill('solid',fgColor='DDEBF7')
    ws.cell(row,1).font=Font(name='微软雅黑',size=9,bold=True); ws.cell(row,1).border=BORDER
    c=ws.cell(row,2,val); c.number_format=fmt; c.font=Font(name='微软雅黑',size=10,bold=True); c.border=BORDER
    c.alignment=Alignment(horizontal='right',vertical='center')
    ws.merge_cells(start_row=row,start_column=3,end_row=row,end_column=5)
    n=ws.cell(row,3,'  '+note); n.font=Font(name='微软雅黑',size=9,color='595959'); n.alignment=Alignment(vertical='center',wrap_text=True)
    for cc in range(3,6): ws.cell(row,cc).border=BORDER
    row+=1

# 关键洞察
row+=1; section(row,'关键洞察')
row+=1
insights=[
 ('产出最高达人', f"{top_creator[1]['name']}（{top_creator[1]['org']}）  ￥{top_creator[1]['gmv']:,.2f}  占比 {top_creator[1]['gmv']/total_gmv:.2%}"),
 ('产出最高单日', f"{top_day[0]}  ￥{top_day[1]['gmv']:,.2f}  当天 {len(top_day[1]['authors'])} 个达人"),
 ('产出最高商品', f"{top_product[1]['name'][:60]}  ￥{top_product[1]['gmv']:,.2f}  占比 {top_product[1]['gmv']/total_gmv:.2%}"),
]
for label,text in insights:
    ws.cell(row,1,label).fill=PatternFill('solid',fgColor='FFF2CC')
    ws.cell(row,1).font=Font(name='微软雅黑',size=9,bold=True); ws.cell(row,1).border=BORDER
    ws.merge_cells(start_row=row,start_column=2,end_row=row,end_column=8)
    c=ws.cell(row,2,text); c.font=Font(name='微软雅黑',size=9); c.alignment=Alignment(vertical='center',wrap_text=True)
    for cc in range(2,9): ws.cell(row,cc).border=BORDER
    row+=1

# ---------- 二、月度 ----------
row+=1; section(row,'二、月度产出')
row+=1; header(row,['月份','产出金额','成交人次','成交单量','成交件数','活跃达人数','有数据天数','日均产出'])
row+=1; month_start=row
for m in sorted(month):
    d=month[m]
    put(row,[f'{int(m[5:])}月',round(d['gmv'],2),int(d['buyers']),int(d['orders']),int(d['items']),len(d['authors']),len(d['dates']),round(d['gmv']/len(d['dates']),2)],
        [None,'#,##0.00','#,##0','#,##0','#,##0','#,##0','0','#,##0.00'],band=((row-month_start)%2==1))
    row+=1
put(row,['合计',round(total_gmv,2),int(total_buyers),int(total_orders),int(total_items),len(creator),days,round(total_gmv/days,2)],
    [None,'#,##0.00','#,##0','#,##0','#,##0','#,##0','0','#,##0.00'])
for c in range(1,9): ws.cell(row,c).font=Font(name='微软雅黑',size=9,bold=True)
row+=1

# ---------- 三、达人 ----------
row+=1; section(row,'三、达人产出（按产出金额降序）')
row+=1; header(row,['排名','达人ID','达人名称','机构','产出金额','金额占比','成交人次','成交单量','成交件数','活跃天数','内容数','SKU数','客单价','日均产出'])
row+=1; creator_start=row
for i,(aid,c) in enumerate(creators_sorted,1):
    put(row,[i,aid,c['name'],c['org'],round(c['gmv'],2),round(c['gmv']/total_gmv,4) if total_gmv else 0,
             int(c['buyers']),int(c['orders']),int(c['items']),len(c['dates']),len(author_contents[aid]),len(author_skus[aid]),
             round(c['gmv']/c['buyers'],2) if c['buyers'] else 0,round(c['gmv']/len(c['dates']),2) if c['dates'] else 0],
        [None,None,None,None,'#,##0.00','0.00%','#,##0','#,##0','#,##0','0','0','0','#,##0.00','#,##0.00'],band=(i%2==0))
    row+=1
creator_end=row-1
put(row,['','','合计','',round(total_gmv,2),1,int(total_buyers),int(total_orders),int(total_items),'—','—','—',round(total_gmv/total_buyers,2) if total_buyers else 0,round(total_gmv/days,2)],
    [None,None,None,None,'#,##0.00','0.00%','#,##0','#,##0','#,##0',None,None,None,'#,##0.00','#,##0.00'])
for c in range(1,15): ws.cell(row,c).font=Font(name='微软雅黑',size=9,bold=True)
row+=1

# ---------- 四、时间线 ----------
row+=1; section(row,'四、时间线产出（按日）')
row+=1; header(row,['日期','月份','产出金额','环比','7日移动平均','成交人次','成交单量','成交件数','达人数','内容数','SKU数','客单价'])
row+=1; timeline_start=row
prev=None
for i,dt in enumerate(dates):
    d=daily[dt]
    mom=None if prev in (None,0) else (d['gmv']-prev)/prev
    window=[daily[x]['gmv'] for x in dates[max(0,i-6):i+1]]
    ma=sum(window)/len(window)
    put(row,[dt,dt[:7],round(d['gmv'],2),mom,round(ma,2),int(d['buyers']),int(d['orders']),int(d['items']),len(d['authors']),len(d['contents']),len(d['skus']),round(d['gmv']/d['buyers'],2) if d['buyers'] else 0],
        [None,None,'#,##0.00','0.00%','#,##0.00','#,##0','#,##0','#,##0','0','0','0','#,##0.00'],band=(i%2==1))
    prev=d['gmv']; row+=1
timeline_end=row-1
put(row,['合计','',round(total_gmv,2),None,None,int(total_buyers),int(total_orders),int(total_items),len(creator),len(unique_contents),len(unique_skus),round(total_gmv/total_buyers,2) if total_buyers else 0],
    [None,None,'#,##0.00',None,None,'#,##0','#,##0','#,##0','#,##0','#,##0','#,##0','#,##0.00'])
for c in range(1,13): ws.cell(row,c).font=Font(name='微软雅黑',size=9,bold=True)
row+=1

# ---------- 五、商品 ----------
row+=1; section(row,'五、商品产出（全部 SKU，按产出金额降序）')
row+=1; header(row,['排名','SKU ID','商品名称','产出金额','金额占比','成交人次','成交单量','成交件数','关联达人数','活跃天数','客单价','日均产出'])
row+=1; product_start=row
for i,(sku,p) in enumerate(products_sorted,1):
    put(row,[i,sku,p['name'],round(p['gmv'],2),round(p['gmv']/total_gmv,4) if total_gmv else 0,
             int(p['buyers']),int(p['orders']),int(p['items']),len(p['authors']),len(p['dates']),
             round(p['gmv']/p['buyers'],2) if p['buyers'] else 0,round(p['gmv']/len(p['dates']),2) if p['dates'] else 0],
        [None,None,None,'#,##0.00','0.00%','#,##0','#,##0','#,##0','0','0','#,##0.00','#,##0.00'],band=(i%2==0),wrap=True)
    ws.row_dimensions[row].height=30
    row+=1
product_end=row-1
put(row,['','','合计',round(total_gmv,2),1,int(total_buyers),int(total_orders),int(total_items),len(creator),'—',round(total_gmv/total_buyers,2) if total_buyers else 0,round(total_gmv/days,2)],
    [None,None,None,'#,##0.00','0.00%','#,##0','#,##0','#,##0','#,##0',None,'#,##0.00','#,##0.00'],wrap=True)
for c in range(1,13): ws.cell(row,c).font=Font(name='微软雅黑',size=9,bold=True)
row+=2
ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=12)
ws.cell(row,1,'说明：达人产出/商品产出按日累加；商品可跨达人销售，因此“关联达人数”可能大于 1；点位金额因内容重复归因，仅作单条内容参考。').font=Font(name='微软雅黑',size=8,color='808080')
ws.cell(row,1).alignment=Alignment(wrap_text=True,vertical='center')

# ---------- 列宽/冻结 ----------
widths={'A':12,'B':14,'C':50,'D':16,'E':16,'F':11,'G':11,'H':11,'I':11,'J':10,'K':10,'L':12,'M':14,'N':14}
for k,v in widths.items(): ws.column_dimensions[k].width=v
ws.freeze_panes='A3'

# ---------- 数据条 ----------
for rng in [f'E{creator_start}:E{creator_end}',f'C{timeline_start}:C{timeline_end}',f'D{product_start}:D{product_end}']:
    ws.conditional_formatting.add(rng,DataBarRule(start_type='num',start_value=0,end_type='max',color='5B9BD5',showValue=True))

# ---------- 图表 ----------
# 月度趋势
month_chart=BarChart(); month_chart.type='col'; month_chart.title='2026年月度产出趋势'; month_chart.y_axis.title='产出金额'; month_chart.x_axis.title='月份'
month_chart.height=8; month_chart.width=16; month_chart.style=12
month_end=month_start+len(month)-1
data=Reference(ws,min_col=2,min_row=month_start-1,max_row=month_end)
cats=Reference(ws,min_col=1,min_row=month_start,max_row=month_end)
month_chart.add_data(data,titles_from_data=True); month_chart.set_categories(cats)
ws.add_chart(month_chart,'P4')

# 达人 Top10
bar=BarChart(); bar.type='bar'; bar.title='达人产出 Top10'; bar.y_axis.title='产出金额'; bar.x_axis.title='达人'
bar.height=8; bar.width=16; bar.style=12
data=Reference(ws,min_col=5,min_row=creator_start-1,max_row=creator_start+9)
cats=Reference(ws,min_col=3,min_row=creator_start,max_row=creator_start+9)
bar.add_data(data,titles_from_data=True); bar.set_categories(cats)
ws.add_chart(bar,'P27')

# 商品 Top10
bar2=BarChart(); bar2.type='bar'; bar2.title='商品产出 Top10（按 SKU）'; bar2.y_axis.title='产出金额'; bar2.x_axis.title='SKU'
bar2.height=8; bar2.width=16; bar2.style=12
data=Reference(ws,min_col=4,min_row=product_start-1,max_row=product_start+9)
cats=Reference(ws,min_col=2,min_row=product_start,max_row=product_start+9)
bar2.add_data(data,titles_from_data=True); bar2.set_categories(cats)
ws.add_chart(bar2,'P50')

wb.active=wb.sheetnames.index(SHEET)
wb.save(OUT)
print('WROTE',OUT)
print('rows',dr.max_row-1,pt.max_row-1,pd.max_row-1,'creators',len(creator),'products',len(product),'days',days)
