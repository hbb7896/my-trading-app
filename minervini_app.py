import streamlit as st
import pandas as pd
import numpy as np
import FinanceDataReader as fdr
import altair as alt
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import random, re, hashlib
import google.generativeai as genai

# ============================================================
# 1. PAGE / CONNECTION
# ============================================================
st.set_page_config(page_title="Trading Master Dashboard", page_icon="💎", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

REQUIRED_COLUMNS = ["Trade_ID","Entry_Date","Exit_Date","Holding_Days","Ticker","Buy_Amount","Sell_Amount","P_L_Amount","ROI_Percent","Mistake_Tags","Emotion","Discipline","Memo"]
MISTAKE_OPTIONS = ["추격매수","손절 지연","조기청산","과도한 포지션","계획 없는 진입","재진입 남발","복수매매/뇌동매매","진입 기준 미충족","기타"]
NORMAL_TAG_WORDS = {"","정상","정상매매","정상 매매","정상거래","정상 거래","없음","해당없음","해당 없음","none","normal","nan","<na>"}

# ============================================================
# 2. COMMON HELPERS
# ============================================================
def create_legacy_trade_id(row,index):
    date_value=row.get("Exit_Date",row.get("Date",""))
    values=[str(index),str(date_value),str(row.get("Ticker","")),str(row.get("Buy_Amount","")),str(row.get("Sell_Amount","")),str(row.get("P_L_Amount","")),str(row.get("ROI_Percent","")),str(row.get("Memo",""))]
    return f"LEGACY_{hashlib.sha1('|'.join(values).encode('utf-8')).hexdigest()[:12]}"

def create_new_trade_id():
    return f"TRD_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{random.randint(1000,9999)}"

def clean_number(series):
    s=series.astype("string").fillna("").str.replace(",","",regex=False).str.replace("%","",regex=False).str.replace("원","",regex=False).str.strip()
    return pd.to_numeric(s,errors="coerce").fillna(0.0).astype("float64")

def is_blank_series(series):
    return series.isna() | series.astype("string").fillna("").str.strip().str.lower().isin(["","nan","nat","none","<na>"])

def split_tags(value):
    if pd.isna(value): return []
    raw=str(value).strip()
    if not raw: return []
    tags=[x.strip() for x in re.split(r"[,|;/]",raw) if x.strip()]
    return [x for x in tags if x.lower() not in NORMAL_TAG_WORDS]

def has_mistake(row):
    return len(split_tags(row.get("Mistake_Tags","")))>0

def format_days(value):
    return "-" if value is None or pd.isna(value) else f"{float(value):.1f}일"

def calculate_trade_result(buy_amount,sell_amount):
    buy=float(buy_amount or 0); sell=float(sell_amount or 0)
    pnl=sell-buy
    roi=(pnl/buy*100) if buy>0 else 0.0
    return pnl,roi

# ============================================================
# 3. DATA LAYER
# ============================================================
def normalize_trade_dataframe(raw_df):
    if raw_df is None or raw_df.empty: return pd.DataFrame(columns=REQUIRED_COLUMNS)
    x=raw_df.copy()

    if "Exit_Date" not in x.columns:
        x["Exit_Date"]=x["Date"].copy() if "Date" in x.columns else pd.Series([None]*len(x),index=x.index,dtype="object")
    elif "Date" in x.columns:
        missing=is_blank_series(x["Exit_Date"])
        x["Exit_Date"]=x["Exit_Date"].astype("object")
        x.loc[missing,"Exit_Date"]=x.loc[missing,"Date"].astype("object")

    if "Entry_Date" not in x.columns: x["Entry_Date"]=pd.Series([None]*len(x),index=x.index,dtype="object")
    if "Holding_Days" not in x.columns: x["Holding_Days"]=pd.Series([np.nan]*len(x),index=x.index,dtype="float64")
    if "Trade_ID" not in x.columns: x["Trade_ID"]=pd.Series([""]*len(x),index=x.index,dtype="object")

    defaults={"Ticker":"","Buy_Amount":0.0,"Sell_Amount":0.0,"P_L_Amount":0.0,"ROI_Percent":0.0,"Mistake_Tags":"","Emotion":"","Discipline":"","Memo":""}
    for col,val in defaults.items():
        if col not in x.columns: x[col]=val

    x["Entry_Date"]=pd.to_datetime(x["Entry_Date"],errors="coerce")
    x["Exit_Date"]=pd.to_datetime(x["Exit_Date"],errors="coerce")
    x=x[x["Exit_Date"].notna()].copy()
    if x.empty: return pd.DataFrame(columns=REQUIRED_COLUMNS)

    for col in ["Buy_Amount","Sell_Amount","P_L_Amount","ROI_Percent"]: x[col]=clean_number(x[col])
    for col in ["Ticker","Mistake_Tags","Emotion","Discipline","Memo"]: x[col]=x[col].astype("string").fillna("").replace({"nan":"","None":"","<NA>":""}).astype(str)

    holding=pd.Series(np.nan,index=x.index,dtype="float64")
    valid=x["Entry_Date"].notna() & x["Exit_Date"].notna() & (x["Entry_Date"]<=x["Exit_Date"])
    if valid.any(): holding.loc[valid]=(x.loc[valid,"Exit_Date"].dt.normalize()-x.loc[valid,"Entry_Date"].dt.normalize()).dt.days.astype(float)
    x["Holding_Days"]=holding

    recovery=(x["Buy_Amount"]==0)&(x["ROI_Percent"]!=0)
    if recovery.any():
        x.loc[recovery,"Buy_Amount"]=(x.loc[recovery,"P_L_Amount"]/(x.loc[recovery,"ROI_Percent"]/100)).abs()
        x.loc[recovery,"Sell_Amount"]=x.loc[recovery,"Buy_Amount"]+x.loc[recovery,"P_L_Amount"]

    sell_recovery=(x["Sell_Amount"]==0)&(x["Buy_Amount"]>0)&((x["P_L_Amount"]!=0)|(x["ROI_Percent"]!=0))
    if sell_recovery.any(): x.loc[sell_recovery,"Sell_Amount"]=x.loc[sell_recovery,"Buy_Amount"]+x.loc[sell_recovery,"P_L_Amount"]

    for pos,idx in enumerate(x.index):
        tid=x.at[idx,"Trade_ID"]
        if pd.isna(tid) or str(tid).strip().lower() in ["","nan","none","<na>"]: x.at[idx,"Trade_ID"]=create_legacy_trade_id(x.loc[idx],pos)
        else: x.at[idx,"Trade_ID"]=str(tid)

    return x[REQUIRED_COLUMNS].reset_index(drop=True)

def prepare_for_sheet(dataframe):
    x=dataframe.copy()
    for col in REQUIRED_COLUMNS:
        if col not in x.columns: x[col]=""
    for col in ["Entry_Date","Exit_Date"]:
        dates=pd.to_datetime(x[col],errors="coerce")
        x[col]=dates.dt.strftime("%Y-%m-%d").fillna("").astype(str)
    x["Holding_Days"]=pd.to_numeric(x["Holding_Days"],errors="coerce").apply(lambda v:"" if pd.isna(v) else str(int(v)))
    for col in ["Buy_Amount","Sell_Amount","P_L_Amount","ROI_Percent"]: x[col]=pd.to_numeric(x[col],errors="coerce").fillna(0.0)
    for col in ["Trade_ID","Ticker","Mistake_Tags","Emotion","Discipline","Memo"]: x[col]=x[col].astype("string").fillna("").replace({"nan":"","None":"","<NA>":""}).astype(str)
    return x[REQUIRED_COLUMNS]

def load_data():
    try: return normalize_trade_dataframe(conn.read(worksheet=0,ttl=0))
    except Exception as e:
        st.error(f"데이터 불러오기 실패: {e}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def save_trade_dataframe(dataframe):
    conn.update(worksheet=0,data=prepare_for_sheet(normalize_trade_dataframe(dataframe)))

def migrate_trade_schema():
    try:
        raw=conn.read(worksheet=0,ttl=0)
        if raw is None or raw.empty: return
        missing_columns=any(c not in raw.columns for c in REQUIRED_COLUMNS)
        legacy_date="Date" in raw.columns
        missing_ids="Trade_ID" not in raw.columns or is_blank_series(raw["Trade_ID"]).any()
        if missing_columns or legacy_date or missing_ids:
            migrated=normalize_trade_dataframe(raw)
            if not migrated.empty: conn.update(worksheet=0,data=prepare_for_sheet(migrated))
    except Exception as e: st.warning(f"데이터 구조 자동 변환을 완료하지 못했습니다: {e}")

# ============================================================
# 4. BASIC METRICS
# ============================================================
def calculate_period_metrics(data):
    empty={"count":0,"win_rate":0.0,"profit_factor":0.0,"reward_risk":0.0,"expectancy":0.0,"avg_win_pct":0.0,"avg_loss_pct":0.0,"gross_profit":0.0,"gross_loss":0.0,"net_profit":0.0,"big_winner_threshold":0.0,"big_winner_count":0,"big_winner_rate":0.0,"big_winner_contribution":0.0}
    if data is None or data.empty: return empty
    wins=data[data["P_L_Amount"]>0]; losses=data[data["P_L_Amount"]<0]; count=len(data)
    gp=wins["P_L_Amount"].sum() if not wins.empty else 0
    gl=abs(losses["P_L_Amount"].sum()) if not losses.empty else 0
    wr=len(wins)/count*100 if count else 0
    aw=wins["ROI_Percent"].mean() if not wins.empty else 0
    al=abs(losses["ROI_Percent"].mean()) if not losses.empty else 0
    pf=gp/gl if gl>0 else 0
    rr=aw/al if al>0 else 0
    expectancy=(len(wins)/count)*aw-(len(losses)/count)*al if count else 0
    threshold=al*2 if al>0 else 10
    big=wins[wins["ROI_Percent"]>=threshold]
    bp=big["P_L_Amount"].sum() if not big.empty else 0
    return {"count":count,"win_rate":wr,"profit_factor":pf,"reward_risk":rr,"expectancy":expectancy,"avg_win_pct":aw,"avg_loss_pct":al,"gross_profit":gp,"gross_loss":gl,"net_profit":data["P_L_Amount"].sum(),"big_winner_threshold":threshold,"big_winner_count":len(big),"big_winner_rate":len(big)/count*100 if count else 0,"big_winner_contribution":bp/gp*100 if gp>0 else 0}

def calculate_max_streaks(data):
    if data.empty: return 0,0
    ordered=data.sort_values(["Exit_Date","Trade_ID"]); mw=ml=cw=cl=0
    for v in ordered["P_L_Amount"]:
        if v>0: cw+=1; cl=0; mw=max(mw,cw)
        elif v<0: cl+=1; cw=0; ml=max(ml,cl)
        else: cw=cl=0
    return mw,ml

def calculate_current_streak(data):
    if data.empty: return "none",0
    vals=data.sort_values(["Exit_Date","Trade_ID"])["P_L_Amount"].tolist()
    typ="win" if vals[-1]>0 else "loss" if vals[-1]<0 else "none"
    if typ=="none": return typ,0
    n=0
    for v in reversed(vals):
        if (typ=="win" and v>0) or (typ=="loss" and v<0): n+=1
        else: break
    return typ,n

# ============================================================
# 5. LOSS CONTROL DNA 1.0
# ============================================================
def simulate_loss_cap(data,cap_pct):
    """
    실현 ROI가 -cap_pct보다 작은 거래를 단순히 -cap_pct에서
    손실이 제한됐다고 가정하는 시뮬레이션.

    실제 손절 백테스트가 아님:
    - 장중 MAE 미반영
    - 갭/슬리피지 미반영
    - 손절 후 재상승 미반영
    - 피라미딩/분할매수 미반영
    """
    if data is None or data.empty: return pd.DataFrame()

    x=data.copy()
    cap=float(abs(cap_pct))
    x["Actual_ROI"]=pd.to_numeric(x["ROI_Percent"],errors="coerce").fillna(0.0)
    x["Sim_ROI"]=x["Actual_ROI"].clip(lower=-cap)
    x["Cap_Affected"]=x["Actual_ROI"] < -cap

    x["Sim_P_L_Amount"]=x["P_L_Amount"].astype(float)

    affected=x["Cap_Affected"] & (x["Buy_Amount"]>0)
    x.loc[affected,"Sim_P_L_Amount"]=x.loc[affected,"Buy_Amount"]*(-cap/100)

    x["Difference"]=x["Sim_P_L_Amount"]-x["P_L_Amount"]
    return x

def calculate_loss_cap_metrics(data,cap_pct):
    sim=simulate_loss_cap(data,cap_pct)

    empty={"cap":float(cap_pct),"count":0,"affected_count":0,"affected_rate":0.0,"actual_pl":0.0,"sim_pl":0.0,"pl_change":0.0,"profit_factor":0.0,"avg_loss_pct":0.0,"expectancy_pct":0.0,"expectancy_amount":0.0,"max_loss_pct":0.0,"gross_profit":0.0,"gross_loss":0.0}

    if sim.empty: return empty

    profits=sim[sim["Sim_P_L_Amount"]>0]["Sim_P_L_Amount"].sum()
    losses=abs(sim[sim["Sim_P_L_Amount"]<0]["Sim_P_L_Amount"].sum())
    loss_roi=sim[sim["Sim_ROI"]<0]["Sim_ROI"]
    sim_pl=sim["Sim_P_L_Amount"].sum()
    actual_pl=sim["P_L_Amount"].sum()

    return {
        "cap":float(cap_pct),
        "count":len(sim),
        "affected_count":int(sim["Cap_Affected"].sum()),
        "affected_rate":sim["Cap_Affected"].mean()*100,
        "actual_pl":actual_pl,
        "sim_pl":sim_pl,
        "pl_change":sim_pl-actual_pl,
        "profit_factor":profits/losses if losses>0 else 0.0,
        "avg_loss_pct":abs(loss_roi.mean()) if not loss_roi.empty else 0.0,
        "expectancy_pct":sim["Sim_ROI"].mean(),
        "expectancy_amount":sim["Sim_P_L_Amount"].mean(),
        "max_loss_pct":abs(sim["Sim_ROI"].min()) if (sim["Sim_ROI"]<0).any() else 0.0,
        "gross_profit":profits,
        "gross_loss":losses
    }

def create_loss_cap_sweep(data,min_cap=3,max_cap=15):
    rows=[]
    for cap in range(int(min_cap),int(max_cap)+1):
        m=calculate_loss_cap_metrics(data,cap)
        rows.append({
            "손실 제한":cap,
            "가상 총손익":m["sim_pl"],
            "실제 대비 변화":m["pl_change"],
            "PF":m["profit_factor"],
            "평균 손실률":m["avg_loss_pct"],
            "거래당 기대수익률":m["expectancy_pct"],
            "거래당 기대손익":m["expectancy_amount"],
            "영향 거래수":m["affected_count"],
            "영향 비율":m["affected_rate"]
        })
    return pd.DataFrame(rows)

def create_loss_cap_trade_table(data,cap_pct):
    sim=simulate_loss_cap(data,cap_pct)
    if sim.empty: return pd.DataFrame()

    affected=sim[sim["Cap_Affected"]].copy()
    if affected.empty: return pd.DataFrame()

    affected["손실 제한"]=float(cap_pct)
    affected["가정 손익 개선"]=affected["Difference"]

    return affected[["Exit_Date","Ticker","Buy_Amount","Actual_ROI","Sim_ROI","P_L_Amount","Sim_P_L_Amount","가정 손익 개선"]].sort_values("가정 손익 개선",ascending=False)

# ============================================================
# 6. HOLDING PERIOD DNA
# ============================================================
def calculate_holding_period_dna(data):
    result={"valid_count":0,"coverage":0.0,"avg_all":None,"avg_wins":None,"avg_losses":None,"avg_big":None,"recent_avg_wins":None,"recent_avg_big":None}
    if data.empty: return result

    valid=data[data["Holding_Days"].notna()&(data["Holding_Days"]>=0)].copy()
    result["valid_count"]=len(valid); result["coverage"]=len(valid)/len(data)*100 if len(data) else 0
    if valid.empty: return result

    m=calculate_period_metrics(data); wins=valid[valid["P_L_Amount"]>0]; losses=valid[valid["P_L_Amount"]<0]; big=wins[wins["ROI_Percent"]>=m["big_winner_threshold"]]
    recent=data.sort_values(["Exit_Date","Trade_ID"]).tail(20); rw=recent[recent["Holding_Days"].notna()&(recent["P_L_Amount"]>0)]; rb=rw[rw["ROI_Percent"]>=m["big_winner_threshold"]]

    result.update({"avg_all":valid["Holding_Days"].mean(),"avg_wins":wins["Holding_Days"].mean() if not wins.empty else None,"avg_losses":losses["Holding_Days"].mean() if not losses.empty else None,"avg_big":big["Holding_Days"].mean() if not big.empty else None,"recent_avg_wins":rw["Holding_Days"].mean() if not rw.empty else None,"recent_avg_big":rb["Holding_Days"].mean() if not rb.empty else None})
    return result

def create_holding_bucket_table(data):
    x=data[data["Holding_Days"].notna()&(data["Holding_Days"]>=0)].copy()
    if x.empty: return pd.DataFrame()
    x["보유구간"]=pd.cut(x["Holding_Days"],bins=[-0.1,0.9,3.9,10.9,30.9,90.9,np.inf],labels=["당일","1~3일","4~10일","11~30일","31~90일","91일+"],right=True)
    rows=[]
    for name,g in x.groupby("보유구간",observed=False):
        if g.empty: continue
        m=calculate_period_metrics(g)
        rows.append({"보유구간":str(name),"거래수":len(g),"승률":m["win_rate"],"PF":m["profit_factor"],"기대값":m["expectancy"],"평균수익률":g["ROI_Percent"].mean(),"총손익":g["P_L_Amount"].sum()})
    return pd.DataFrame(rows)

# ============================================================
# 7. MISTAKE COST
# ============================================================
def calculate_mistake_cost(data):
    empty={"total_count":0,"normal_count":0,"mistake_count":0,"mistake_rate":0.0,"normal_pl":0.0,"mistake_pl":0.0,"normal_metrics":calculate_period_metrics(pd.DataFrame()),"mistake_metrics":calculate_period_metrics(pd.DataFrame()),"tag_table":pd.DataFrame(),"recent_rate":0.0,"previous_rate":0.0,"change_rate":0.0,"has_previous":False,"worst_tag":None,"most_frequent_tag":None}
    if data is None or data.empty: return empty

    x=data.copy(); x["Is_Mistake"]=x.apply(has_mistake,axis=1)
    normal=x[~x["Is_Mistake"]].copy(); mistake=x[x["Is_Mistake"]].copy(); tag_rows=[]

    for _,row in mistake.iterrows():
        for tag in split_tags(row["Mistake_Tags"]): tag_rows.append({"실수 유형":tag,"P_L_Amount":row["P_L_Amount"],"ROI_Percent":row["ROI_Percent"],"Trade_ID":row["Trade_ID"]})

    rows=[]
    if tag_rows:
        tags_df=pd.DataFrame(tag_rows)
        for tag,g in tags_df.groupby("실수 유형"):
            ids=g["Trade_ID"].astype(str).unique(); original=mistake[mistake["Trade_ID"].astype(str).isin(ids)].copy(); metrics=calculate_period_metrics(original)
            rows.append({"실수 유형":tag,"발생횟수":len(original),"승률":metrics["win_rate"],"PF":metrics["profit_factor"],"평균수익률":original["ROI_Percent"].mean(),"실제손익":original["P_L_Amount"].sum()})
        tag_table=pd.DataFrame(rows).sort_values(["실제손익","발생횟수"],ascending=[True,False]).reset_index(drop=True)
    else: tag_table=pd.DataFrame(columns=["실수 유형","발생횟수","승률","PF","평균수익률","실제손익"])

    ordered=x.sort_values(["Exit_Date","Trade_ID"]); recent=ordered.tail(min(20,len(ordered)))
    previous=ordered.iloc[-40:-20] if len(ordered)>=40 else ordered.iloc[:-20].tail(20) if len(ordered)>20 else pd.DataFrame(columns=ordered.columns)
    recent_rate=recent["Is_Mistake"].mean()*100 if not recent.empty else 0; previous_rate=previous["Is_Mistake"].mean()*100 if not previous.empty else 0; has_previous=len(previous)>=5
    worst_tag=tag_table.iloc[0].to_dict() if not tag_table.empty else None
    frequent=tag_table.sort_values(["발생횟수","실제손익"],ascending=[False,True]).iloc[0].to_dict() if not tag_table.empty else None

    return {"total_count":len(x),"normal_count":len(normal),"mistake_count":len(mistake),"mistake_rate":len(mistake)/len(x)*100 if len(x) else 0,"normal_pl":normal["P_L_Amount"].sum(),"mistake_pl":mistake["P_L_Amount"].sum(),"normal_metrics":calculate_period_metrics(normal),"mistake_metrics":calculate_period_metrics(mistake),"tag_table":tag_table,"recent_rate":recent_rate,"previous_rate":previous_rate,"change_rate":recent_rate-previous_rate if has_previous else 0,"has_previous":has_previous,"worst_tag":worst_tag,"most_frequent_tag":frequent}

def generate_mistake_insights(mc):
    if mc["mistake_count"]==0: return ["✅ 현재 기록에서는 실수 태그가 붙은 거래가 없습니다."]
    out=[]
    if mc["worst_tag"]:
        w=mc["worst_tag"]; out.append(f"💸 기록상 실제 합산 손익이 가장 낮은 실수는 **{w['실수 유형']}**입니다. {int(w['발생횟수'])}회에서 **{w['실제손익']:+,.0f}원**이 기록됐습니다.")
    if mc["most_frequent_tag"]:
        f=mc["most_frequent_tag"]; out.append(f"🔁 가장 자주 기록된 실수는 **{f['실수 유형']}**이며 총 **{int(f['발생횟수'])}회**입니다.")
    if mc["normal_count"]>=3 and mc["mistake_count"]>=3: out.append(f"📊 정상 거래 PF는 **{mc['normal_metrics']['profit_factor']:.2f}**, 실수 거래 PF는 **{mc['mistake_metrics']['profit_factor']:.2f}**입니다.")
    if mc["has_previous"] and mc["change_rate"]>=10: out.append(f"⚠️ 최근 20거래의 실수 발생률이 직전 구간보다 **{mc['change_rate']:+.1f}%p** 높아졌습니다.")
    return out[:4]

# ============================================================
# 8. TRADING DNA
# ============================================================
def calculate_trading_dna(data):
    if data.empty: return {}
    ordered=data.sort_values(["Exit_Date","Trade_ID"]).copy(); total=calculate_period_metrics(ordered); n=len(ordered); wins=ordered[ordered["P_L_Amount"]>0]; losses=ordered[ordered["P_L_Amount"]<0]

    if not wins.empty and total["gross_profit"]>0:
        top_n=max(1,int(np.ceil(len(wins)*.1))); top_profit=wins.nlargest(top_n,"P_L_Amount")["P_L_Amount"].sum(); top10=top_profit/total["gross_profit"]*100
    else: top_n,top10=0,0

    big=wins[wins["ROI_Percent"]>=total["big_winner_threshold"]].copy()
    max_win,max_loss=calculate_max_streaks(ordered); current_type,current=calculate_current_streak(ordered)
    max_loss_pct=abs(losses["ROI_Percent"].min()) if not losses.empty else 0; max_loss_amount=abs(losses["P_L_Amount"].min()) if not losses.empty else 0
    recent=ordered.tail(min(20,n)).copy(); rm=calculate_period_metrics(recent)
    previous=ordered.iloc[n-40:n-20].copy() if n>=40 else ordered.iloc[:n-20].tail(20).copy() if n>20 else pd.DataFrame(columns=ordered.columns)
    pm=calculate_period_metrics(previous); has_previous=len(previous)>=5
    keys=["win_rate","profit_factor","reward_risk","expectancy","avg_win_pct","avg_loss_pct","big_winner_rate","big_winner_contribution"]
    changes={k:rm[k]-pm[k] if has_previous else 0 for k in keys}

    if not has_previous: status,icon="데이터 축적 중","🟡"
    else:
        score=0
        score+=2 if changes["expectancy"]>.75 else -2 if changes["expectancy"]<-.75 else 0
        score+=1 if changes["profit_factor"]>.2 else -1 if changes["profit_factor"]<-.2 else 0
        score+=1 if changes["reward_risk"]>.25 else -1 if changes["reward_risk"]<-.25 else 0
        score+=1 if changes["avg_loss_pct"]<-.5 else -1 if changes["avg_loss_pct"]>.5 else 0
        score+=1 if changes["big_winner_rate"]>2 else -1 if changes["big_winner_rate"]<-2 else 0
        status,icon=("개선","🟢") if score>=2 else ("주의","🔴") if score<=-2 else ("안정","🟡")

    wr,rr=total["win_rate"],total["reward_risk"]
    if rr>=2 and wr<50: dtype,desc="🧬 Trend Follower","낮은 승률을 감수하고 큰 수익 거래로 전체 성과를 만드는 추세추종형 구조입니다."
    elif wr>=60 and rr<1.5: dtype,desc="🎯 High Accuracy Trader","높은 승률을 기반으로 수익을 누적하는 고승률형 구조입니다."
    elif rr>=1.5 and wr>=45: dtype,desc="⚖️ Balanced Trader","승률과 손익비가 비교적 균형을 이루는 구조입니다."
    elif top10>=60 or total["big_winner_contribution"]>=60: dtype,desc="🚀 Big Winner Hunter","소수의 큰 수익 거래가 전체 성과에 강한 영향을 주는 구조입니다."
    else: dtype,desc="🔬 Developing Edge","현재 기록에서는 여러 수익 패턴이 혼합되어 있습니다."

    return {"total_count":n,"win_rate":wr,"profit_factor":total["profit_factor"],"reward_risk":rr,"expectancy":total["expectancy"],"avg_win_pct":total["avg_win_pct"],"avg_loss_pct":total["avg_loss_pct"],"gross_profit":total["gross_profit"],"gross_loss":total["gross_loss"],"top10_contribution":top10,"top_n":top_n,"big_winner_threshold":total["big_winner_threshold"],"big_winner_count":len(big),"big_winner_contribution":total["big_winner_contribution"],"max_win_streak":max_win,"max_loss_streak":max_loss,"current_streak_type":current_type,"current_streak":current,"max_loss_pct":max_loss_pct,"max_loss_amount":max_loss_amount,"recent_count":len(recent),"recent_df":recent,"previous_df":previous,"recent_metrics":rm,"previous_metrics":pm,"total_metrics":total,"changes":changes,"has_previous":has_previous,"edge_status":status,"edge_icon":icon,"dna_type":dtype,"dna_description":desc,"big_winners":big}

def detect_edge_drivers(dna):
    if not dna or not dna["has_previous"]: return []
    c=dna["changes"]
    candidates=[("승률",c["win_rate"]/5,f"승률 {c['win_rate']:+.1f}%p"),("Profit Factor",c["profit_factor"]*2,f"PF {c['profit_factor']:+.2f}"),("손익비",c["reward_risk"]*1.5,f"손익비 {c['reward_risk']:+.2f}"),("평균 수익률",c["avg_win_pct"]/2,f"평균 수익률 {c['avg_win_pct']:+.2f}%p"),("평균 손실률",-c["avg_loss_pct"]/2,f"평균 손실률 {c['avg_loss_pct']:+.2f}%p"),("Big Winner 비율",c["big_winner_rate"]/4,f"Big Winner 비율 {c['big_winner_rate']:+.1f}%p")]
    return [{"name":n,"direction":"positive" if imp>0 else "negative","text":txt} for n,imp,txt in sorted(candidates,key=lambda z:abs(z[1]),reverse=True)[:3] if abs(imp)>=.15]

def generate_coach_checkpoints(dna,mc=None):
    out=[]; c=dna["changes"]; total=dna["total_metrics"]
    if dna["has_previous"] and c["avg_loss_pct"]>.75: out.append(f"🛡️ 최근 평균 손실률이 {c['avg_loss_pct']:+.2f}%p 확대됐습니다.")
    if dna["has_previous"] and c["big_winner_rate"]<-3: out.append(f"🚀 최근 Big Winner 비율이 {abs(c['big_winner_rate']):.1f}%p 감소했습니다.")
    if dna["has_previous"] and c["avg_win_pct"]<-1: out.append(f"💎 최근 평균 수익률이 {abs(c['avg_win_pct']):.2f}%p 낮아졌습니다.")
    if mc and mc["has_previous"] and mc["change_rate"]>=10: out.append(f"🧠 최근 실수 발생률이 직전 구간보다 {mc['change_rate']:+.1f}%p 증가했습니다.")
    if total["reward_risk"]>=2 and total["win_rate"]<50: out.append("🧬 장기 구조는 승률보다 손익비 의존도가 높습니다. 손실 제한과 큰 승자 보유를 관찰하세요.")
    if dna["current_streak_type"]=="loss" and dna["current_streak"]>=4: out.append(f"⚠️ 현재 {dna['current_streak']}연속 손실입니다.")
    if not out: out.append("✅ 최근 통계에서 뚜렷한 구조 훼손 신호는 발견되지 않았습니다.")
    return out[:3]

def generate_rule_based_insights(dna):
    out=[]
    if dna["big_winner_contribution"]>=60: out.append(f"🔥 큰 수익 거래가 Gross Profit의 {dna['big_winner_contribution']:.1f}%를 만들고 있습니다.")
    elif dna["big_winner_contribution"]>=35: out.append("🔥 Big Winner가 전체 수익에서 의미 있는 비중을 차지합니다.")
    else: out.append("📊 수익이 여러 거래에 상대적으로 분산되어 있습니다.")
    if dna["top10_contribution"]>=40: out.append("💎 상위 수익 거래의 기여도가 높습니다.")
    if dna["reward_risk"]>=2 and dna["win_rate"]<50: out.append("🧬 승률보다 손익비가 성과를 만드는 구조입니다.")
    if dna["avg_loss_pct"]>0 and dna["max_loss_pct"]>=dna["avg_loss_pct"]*2.5: out.append("⚠️ 최대 손실이 평균 손실보다 상당히 큽니다.")
    if dna["max_loss_streak"]>=6: out.append(f"🧠 과거 최대 연속 손실은 {dna['max_loss_streak']}회입니다.")
    return out

# ============================================================
# 9. TABLE HELPERS
# ============================================================
def create_roi_bucket_table(data):
    if data.empty: return pd.DataFrame()
    x=data.copy(); bins=[-np.inf,-10,-5,0,5,10,20,np.inf]; labels=["-10% 이하","-10 ~ -5%","-5 ~ 0%","0 ~ +5%","+5 ~ +10%","+10 ~ +20%","+20% 이상"]
    x["수익률 구간"]=pd.cut(x["ROI_Percent"],bins=bins,labels=labels,right=False)
    return x.groupby("수익률 구간",observed=False).agg(거래수=("Trade_ID","count"),총손익=("P_L_Amount","sum"),평균수익률=("ROI_Percent","mean")).reset_index()

def create_edge_comparison_table(dna):
    t,p,r,c=dna["total_metrics"],dna["previous_metrics"],dna["recent_metrics"],dna["changes"]
    names=[("승률","win_rate"),("Profit Factor","profit_factor"),("손익비","reward_risk"),("기대값","expectancy"),("평균 수익률","avg_win_pct"),("평균 손실률","avg_loss_pct"),("Big Winner 비율","big_winner_rate")]
    return pd.DataFrame([{"지표":name,"전체":t[k],"직전 20":p[k],"최근 20":r[k],"변화":c[k]} for name,k in names])

# ============================================================
# 10. AI COACH
# ============================================================
def build_ai_coach_prompt(dna,checkpoints,drivers,holding,mistake):
    t,p,r=dna["total_metrics"],dna["previous_metrics"],dna["recent_metrics"]
    driver_text="\n".join(f"- {x['text']} ({x['direction']})" for x in drivers) or "- 뚜렷한 변화 없음"
    cp="\n".join(f"- {x}" for x in checkpoints)
    avg_win_hold="데이터 없음" if holding["avg_wins"] is None else f"{holding['avg_wins']:.1f}일"
    avg_loss_hold="데이터 없음" if holding["avg_losses"] is None else f"{holding['avg_losses']:.1f}일"
    avg_big_hold="데이터 없음" if holding["avg_big"] is None else f"{holding['avg_big']:.1f}일"

    return f"""
당신은 트레이딩 저널 데이터 해석 코치입니다.
제공된 숫자만 사용하고 새로운 숫자를 만들지 마세요.
종목 추천, 미래 예측, 전략의 좋고 나쁨 판단을 하지 마세요.
상관관계를 인과관계로 표현하지 마세요.
추세추종에서는 낮은 승률 자체를 문제라고 하지 마세요.
한국어로 간결하고 실전적으로 작성하세요.

[Trading DNA]
유형 {dna['dna_type']}
전체 {dna['total_count']}건
Edge {dna['edge_status']}

[전체]
승률 {t['win_rate']:.2f}%
PF {t['profit_factor']:.2f}
손익비 {t['reward_risk']:.2f}
기대값 {t['expectancy']:.2f}%
평균수익 {t['avg_win_pct']:.2f}%
평균손실 {t['avg_loss_pct']:.2f}%

[최근]
승률 {r['win_rate']:.2f}%
PF {r['profit_factor']:.2f}
손익비 {r['reward_risk']:.2f}
기대값 {r['expectancy']:.2f}%

[Holding]
수익거래 {avg_win_hold}
손실거래 {avg_loss_hold}
Big Winner {avg_big_hold}

[Mistake]
실수 거래 {mistake['mistake_count']}건
실수 발생률 {mistake['mistake_rate']:.1f}%
실수 거래 손익 {mistake['mistake_pl']:+,.0f}원

[주요 변화]
{driver_text}

[체크포인트]
{cp}

### 🧠 AI Coach 진단
2~3문장.

### 💪 유지할 강점
1~2개.

### 🔍 최근 달라진 점
1~3개.

### 🎯 다음 10거래 체크포인트
행동 3개 이하.

마지막 문장:
"이 분석은 매수·매도 추천이 아니라 본인의 매매 행동을 점검하기 위한 트레이딩 저널 분석입니다."
"""

def run_ai_coach(api_key,dna,checkpoints,drivers,holding,mistake):
    genai.configure(api_key=api_key.strip())
    model=genai.GenerativeModel("gemini-2.5-flash")
    response=model.generate_content(build_ai_coach_prompt(dna,checkpoints,drivers,holding,mistake))
    if not response.parts: raise ValueError("AI Coach 응답이 없습니다.")
    return response.text.strip()

# ============================================================
# 11. LOAD
# ============================================================
migrate_trade_schema()
df=load_data()

st.title("💎 Trading Master Dashboard")

if df.empty: st.info("아직 거래 기록이 없습니다. 🛠️ 거래 관리 탭에서 첫 거래를 등록하세요.")

analysis_df=df.copy()
if not analysis_df.empty:
    analysis_df["Year"]=analysis_df["Exit_Date"].dt.year
    analysis_df["YearMonth"]=analysis_df["Exit_Date"].dt.strftime("%Y-%m")

tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8,tab9=st.tabs(["📊 차트","📅 월별","📆 연도별","📋 원본","⚖️ 빅터","🎯 R-배수","🔔 손익 분포","🛠️ 거래 관리","🧠 Trading DNA"])

# ============================================================
# TAB 1
# ============================================================
with tab1:
    if analysis_df.empty: st.info("거래 기록이 쌓이면 성과 차트가 표시됩니다.")
    else:
        st.subheader("🏆 전체 종합 성적표")
        m=calculate_period_metrics(analysis_df); total_pl=analysis_df["P_L_Amount"].sum(); wins=analysis_df[analysis_df["P_L_Amount"]>0]; losses=analysis_df[analysis_df["P_L_Amount"]<0]
        avg_profit=wins["P_L_Amount"].mean() if not wins.empty else 0; avg_loss=abs(losses["P_L_Amount"].mean()) if not losses.empty else 0; money_rr=avg_profit/avg_loss if avg_loss>0 else 0
        wp=m["win_rate"]/100; kelly=max(0,(wp-(1-wp)/money_rr)*100) if money_rr>0 else 0

        a,b,c,d,e=st.columns(5)
        a.metric("💰 누적 총 손익",f"{total_pl:,.0f}원"); b.metric("🎯 전체 승률",f"{m['win_rate']:.1f}%"); c.metric("🔮 기대값",f"{m['expectancy']:+.2f}%"); d.metric("💎 Profit Factor",f"{m['profit_factor']:.2f}"); e.metric("⚖️ 켈리 비중",f"{kelly:.1f}%")
        a,b,c,d=st.columns(4)
        a.metric("평균 수익금",f"{avg_profit:,.0f}원"); b.metric("평균 손실금",f"{avg_loss:,.0f}원"); c.metric("금액 손익비",f"{money_rr:.2f}"); d.metric("총 매수 대금",f"{analysis_df['Buy_Amount'].sum():,.0f}원")
        a,b,c,d=st.columns(4)
        a.metric("평균 수익률",f"+{m['avg_win_pct']:.2f}%"); b.metric("평균 손실률",f"-{m['avg_loss_pct']:.2f}%"); c.metric("기간 손익비",f"{m['reward_risk']:.2f}"); d.metric("총 거래 횟수",f"{m['count']}회")

        st.divider(); st.subheader("🚀 누적 손익")
        daily=analysis_df.groupby("Exit_Date")["P_L_Amount"].sum().reset_index().sort_values("Exit_Date"); daily["Cumulative"]=daily["P_L_Amount"].cumsum()
        st.line_chart(daily.set_index("Exit_Date")["Cumulative"])
        st.subheader("📊 월별 손익 흐름"); st.bar_chart(analysis_df.groupby("YearMonth")["P_L_Amount"].sum())

# ============================================================
# TAB 2
# ============================================================
with tab2:
    st.subheader("📅 월별 상세 성적표")
    if analysis_df.empty: st.info("거래 기록이 없습니다.")
    else:
        rows=[]
        for ym,g in analysis_df.groupby("YearMonth"):
            x=calculate_period_metrics(g); w=g[g["P_L_Amount"]>0]; l=g[g["P_L_Amount"]<0]
            rows.append({"기간":ym,"총 손익":g["P_L_Amount"].sum(),"평균수익":w["P_L_Amount"].mean() if not w.empty else 0,"평균손실":l["P_L_Amount"].mean() if not l.empty else 0,"거래횟수":len(g),"승률":x["win_rate"],"손익비":x["reward_risk"],"PF":x["profit_factor"],"기대수익":x["expectancy"],"매수총액":g["Buy_Amount"].sum()})
        table=pd.DataFrame(rows).sort_values("기간",ascending=False)
        st.dataframe(table.style.format({"총 손익":"{:+,.0f}원","평균수익":"{:,.0f}원","평균손실":"{:,.0f}원","승률":"{:.1f}%","손익비":"{:.2f}","PF":"{:.2f}","기대수익":"{:+.2f}%","매수총액":"{:,.0f}원"}),use_container_width=True)

# ============================================================
# TAB 3
# ============================================================
with tab3:
    st.subheader("📆 연도별 종합 성적표")
    if analysis_df.empty: st.info("거래 기록이 없습니다.")
    else:
        rows=[]
        for year,g in analysis_df.groupby("Year"):
            x=calculate_period_metrics(g); w=g[g["P_L_Amount"]>0]; l=g[g["P_L_Amount"]<0]
            rows.append({"연도":int(year),"총 손익":g["P_L_Amount"].sum(),"평균수익":w["P_L_Amount"].mean() if not w.empty else 0,"평균손실":l["P_L_Amount"].mean() if not l.empty else 0,"거래횟수":len(g),"승률":x["win_rate"],"손익비":x["reward_risk"],"PF":x["profit_factor"],"기대수익":x["expectancy"],"매수총액":g["Buy_Amount"].sum()})
        table=pd.DataFrame(rows).sort_values("연도",ascending=False)
        st.dataframe(table.style.format({"총 손익":"{:+,.0f}원","평균수익":"{:,.0f}원","평균손실":"{:,.0f}원","승률":"{:.1f}%","손익비":"{:.2f}","PF":"{:.2f}","기대수익":"{:+.2f}%","매수총액":"{:,.0f}원"}),use_container_width=True)

# ============================================================
# TAB 4
# ============================================================
with tab4:
    st.subheader("📋 전체 거래 기록")
    if analysis_df.empty: st.info("거래 기록이 없습니다.")
    else:
        table=analysis_df.sort_values(["Exit_Date","Trade_ID"],ascending=[False,False]).copy()
        table["거래구분"]=table.apply(lambda r:"⚠️ 실수" if has_mistake(r) else "✅ 정상",axis=1)
        cols=["Entry_Date","Exit_Date","Holding_Days","Ticker","Buy_Amount","Sell_Amount","P_L_Amount","ROI_Percent","거래구분","Mistake_Tags","Memo"]
        st.dataframe(table[cols].style.format({"Holding_Days":lambda x:"-" if pd.isna(x) else f"{x:.0f}일","Buy_Amount":"{:,.0f}원","Sell_Amount":"{:,.0f}원","P_L_Amount":"{:+,.0f}원","ROI_Percent":"{:+.2f}%"}),use_container_width=True)

# ============================================================
# TAB 5
# ============================================================
with tab5:
    st.subheader("⚖️ Victor Sperandeo Reward-to-Risk Analysis")
    st.markdown("**목표 기준: 평균 수익 / 평균 손실 = 3 : 1**")
    if analysis_df.empty: st.info("거래 기록이 없습니다.")
    else:
        period=st.radio("📅 분석 기간",["전체","최근 1개월","최근 3개월","최근 6개월","최근 1년"],horizontal=True,key="vic_period")
        vdf=analysis_df.copy(); days={"최근 1개월":30,"최근 3개월":90,"최근 6개월":180,"최근 1년":365}
        if period in days: vdf=vdf[vdf["Exit_Date"]>=pd.Timestamp.today().normalize()-timedelta(days=days[period])]
        if not vdf.empty:
            vm=calculate_period_metrics(vdf)
            a,b,c=st.columns(3); a.metric("기간 손익비",f"{vm['reward_risk']:.2f} : 1"); b.metric("기간 기대값",f"{vm['expectancy']:+.2f}%"); c.metric("목표 기준","3.0 : 1")
            target=vm["avg_loss_pct"]*3 if vm["avg_loss_pct"]>0 else 10
            chart=vdf.copy(); chart["Color_Hex"]=np.select([chart["ROI_Percent"]>=target,chart["ROI_Percent"]>0],["#00CC00","#F1C40F"],default="#FF4B4B")
            scatter=alt.Chart(chart).mark_circle(size=100).encode(x="Exit_Date:T",y="ROI_Percent:Q",color=alt.Color("Color_Hex:N",scale=None,legend=None),tooltip=["Ticker","Entry_Date","Exit_Date","Holding_Days","ROI_Percent","P_L_Amount"]).interactive()
            rule=alt.Chart(pd.DataFrame({"Target":[target]})).mark_rule(strokeDash=[3,3]).encode(y="Target:Q")
            st.altair_chart(scatter+rule,use_container_width=True)

# ============================================================
# TAB 6
# ============================================================
with tab6:
    st.subheader("🎯 R-배수 분석"); st.caption("1R = 선택 기간의 평균 손실금")
    if analysis_df.empty: st.info("거래 기록이 없습니다.")
    else:
        period=st.radio("📅 분석 기간",["전체","최근 1개월","최근 3개월","최근 6개월","최근 1년"],horizontal=True,key="r_period")
        rdf=analysis_df.copy(); days={"최근 1개월":30,"최근 3개월":90,"최근 6개월":180,"최근 1년":365}
        if period in days: rdf=rdf[rdf["Exit_Date"]>=pd.Timestamp.today().normalize()-timedelta(days=days[period])]
        if not rdf.empty:
            losses=rdf[rdf["P_L_Amount"]<0]; one_r=abs(losses["P_L_Amount"].mean()) if not losses.empty else 1
            if pd.isna(one_r) or one_r<=0: one_r=1
            rdf=rdf.copy(); rdf["R_Value"]=rdf["P_L_Amount"]/one_r
            a,b,c=st.columns(3); a.metric("나의 1R",f"{one_r:,.0f}원"); b.metric("평균 R-배수",f"{rdf['R_Value'].mean():.2f}R"); c.metric("최고 R-배수",f"{rdf['R_Value'].max():.2f}R")
            rdf=rdf.sort_values("Exit_Date"); rdf["Cumulative_R"]=rdf["R_Value"].cumsum(); rdf["Trade_Num"]=range(1,len(rdf)+1)
            st.line_chart(rdf.set_index("Trade_Num")["Cumulative_R"])

# ============================================================
# TAB 7
# ============================================================
with tab7:
    st.subheader("🔔 손익 분포")
    if analysis_df.empty: st.info("거래 기록이 없습니다.")
    else:
        histogram=alt.Chart(analysis_df).mark_bar().encode(x=alt.X("ROI_Percent:Q",bin=alt.Bin(step=2.5)),y="count():Q",color=alt.condition(alt.datum.ROI_Percent>0,alt.value("#00AA00"),alt.value("#FF4444"))).properties(height=400)
        st.altair_chart(histogram,use_container_width=True)
        skew=analysis_df["ROI_Percent"].skew(); st.info(f"📊 Skewness: {0 if pd.isna(skew) else skew:.2f}")

# ============================================================
# TAB 8 - TRADE MANAGEMENT
# ============================================================
with tab8:
    st.subheader("🛠️ 거래 관리")
    st.caption("신규 거래 등록부터 기존 거래 수정·삭제까지 한곳에서 관리합니다.")
    mode=st.radio("작업 선택",["➕ 신규 거래","✏️ 수정 · 삭제"],horizontal=True,key="trade_manage_mode")

    if mode=="➕ 신규 거래":
        st.markdown("### ➕ 신규 거래 등록")
        if "new_trade_form_version" not in st.session_state: st.session_state["new_trade_form_version"]=0
        fv=st.session_state["new_trade_form_version"]

        with st.form(f"new_trade_{fv}",clear_on_submit=False):
            c1,c2=st.columns(2); entry_date=c1.date_input("매수 진입일",datetime.today().date()); exit_date=c2.date_input("매도 청산일",datetime.today().date())
            ticker=st.text_input("종목명").strip()
            c1,c2=st.columns(2); buy_amt=c1.number_input("총 매수 금액 (원)",min_value=0,value=0,step=100000); sell_amt=c2.number_input("총 매도 금액 (원)",min_value=0,value=0,step=100000)
            holding=(exit_date-entry_date).days; pnl,roi=calculate_trade_result(buy_amt,sell_amt)

            st.markdown("#### 📊 자동 계산")
            c1,c2,c3=st.columns(3); c1.metric("⏱️ 보유기간",f"{holding}일" if holding>=0 else "날짜 확인"); c2.metric("💰 손익",f"{pnl:+,.0f}원"); c3.metric("📈 수익률",f"{roi:+.2f}%")

            st.markdown("#### 🧠 매매 복기")
            mistake_tags=st.multiselect("실수 태그",MISTAKE_OPTIONS,help="정상 거래라면 아무것도 선택하지 마세요.")
            memo=st.text_area("메모",placeholder="진입 근거, 청산 이유, 잘한 점이나 아쉬운 점 등을 기록하세요.")
            if mistake_tags: st.warning("⚠️ 이 거래는 실수 거래로 자동 분류됩니다.")
            else: st.info("✅ 실수 태그가 없으므로 정상 거래로 분류됩니다.")

            save=st.form_submit_button("💾 거래 저장",use_container_width=True,type="primary")
            if save:
                if exit_date<entry_date: st.error("청산일은 진입일보다 빠를 수 없습니다.")
                elif not ticker: st.error("종목명을 입력해주세요.")
                elif buy_amt<=0: st.error("매수금액을 입력해주세요.")
                else:
                    try:
                        new=pd.DataFrame([{"Trade_ID":create_new_trade_id(),"Entry_Date":pd.Timestamp(entry_date),"Exit_Date":pd.Timestamp(exit_date),"Holding_Days":holding,"Ticker":ticker,"Buy_Amount":float(buy_amt),"Sell_Amount":float(sell_amt),"P_L_Amount":float(pnl),"ROI_Percent":float(roi),"Mistake_Tags":" | ".join(mistake_tags),"Emotion":"","Discipline":"","Memo":memo}])
                        raw=conn.read(worksheet=0,ttl=0); live=normalize_trade_dataframe(raw) if raw is not None and not raw.empty else pd.DataFrame(columns=REQUIRED_COLUMNS)
                        save_trade_dataframe(pd.concat([live,new],ignore_index=True))
                        st.session_state["new_trade_form_version"]+=1
                        st.success(f"✅ {ticker} 거래 저장 완료! 손익 {pnl:+,.0f}원 / 수익률 {roi:+.2f}%"); st.rerun()
                    except Exception as e: st.error(f"🚨 거래 저장 실패: {e}")

    else:
        st.markdown("### ✏️ 기존 거래 수정 · 삭제")
        if analysis_df.empty: st.info("수정할 거래가 없습니다.")
        else:
            manage=analysis_df.sort_values(["Exit_Date","Trade_ID"],ascending=[False,False]).copy()
            manage["Display_Name"]=manage["Exit_Date"].dt.strftime("%Y-%m-%d")+" | "+manage["Ticker"].astype(str)+" | "+manage["ROI_Percent"].map(lambda x:f"{x:+.2f}%")+" | "+manage["P_L_Amount"].map(lambda x:f"{x:+,.0f}원")
            display=dict(zip(manage["Trade_ID"].astype(str),manage["Display_Name"]))
            tid=st.selectbox("📋 수정/삭제할 거래 선택",options=list(display.keys()),format_func=lambda x:display.get(x,x))
            rows=manage[manage["Trade_ID"].astype(str)==str(tid)]

            if not rows.empty:
                s=rows.iloc[0]; mistake_state=has_mistake(s)
                a,b,c,d=st.columns(4); a.metric("종목",s["Ticker"]); b.metric("청산일",s["Exit_Date"].strftime("%Y-%m-%d")); c.metric("보유일수","-" if pd.isna(s["Holding_Days"]) else f"{s['Holding_Days']:.0f}일"); d.metric("거래 구분","⚠️ 실수" if mistake_state else "✅ 정상")
                a,b,c=st.columns(3); a.metric("매수금액",f"{s['Buy_Amount']:,.0f}원"); b.metric("매도금액",f"{s['Sell_Amount']:,.0f}원"); c.metric("손익",f"{s['P_L_Amount']:+,.0f}원")

                st.divider(); st.markdown("### ✏️ 거래 수정")
                current_tags=split_tags(s["Mistake_Tags"]); known_tags=[t for t in current_tags if t in MISTAKE_OPTIONS]; custom_tags=[t for t in current_tags if t not in MISTAKE_OPTIONS]; has_entry_original=pd.notna(s["Entry_Date"])

                with st.form(f"edit_{tid}"):
                    use_entry=st.checkbox("진입일 정보 입력",value=has_entry_original)
                    e_entry=None
                    if use_entry:
                        default_entry=s["Entry_Date"].date() if has_entry_original else s["Exit_Date"].date()
                        e_entry=st.date_input("매수 진입일",value=default_entry)
                    else: st.caption("진입일 미입력 상태로 유지됩니다.")

                    e_exit=st.date_input("매도 청산일",value=s["Exit_Date"].date()); e_ticker=st.text_input("종목명",value=str(s["Ticker"]))
                    c1,c2=st.columns(2); e_buy=c1.number_input("총 매수 금액 (원)",min_value=0,value=max(0,int(round(s["Buy_Amount"]))),step=100000); e_sell=c2.number_input("총 매도 금액 (원)",min_value=0,value=max(0,int(round(s["Sell_Amount"]))),step=100000)
                    preview_pl,preview_roi=calculate_trade_result(e_buy,e_sell); preview_holding=(e_exit-e_entry).days if use_entry and e_entry is not None else None
                    c1,c2,c3=st.columns(3); c1.metric("⏱️ 보유기간","-" if preview_holding is None else f"{preview_holding}일"); c2.metric("💰 손익",f"{preview_pl:+,.0f}원"); c3.metric("📈 수익률",f"{preview_roi:+.2f}%")

                    e_tags=st.multiselect("실수 태그",MISTAKE_OPTIONS,default=known_tags)
                    if custom_tags:
                        st.caption("기존 사용자 정의 태그: "+", ".join(custom_tags)); keep_custom=st.checkbox("기존 사용자 정의 태그 유지",value=True)
                    else: keep_custom=False
                    e_memo=st.text_area("메모",value=str(s["Memo"]))
                    update_clicked=st.form_submit_button("💾 수정 내용 저장",use_container_width=True,type="primary")

                    if update_clicked:
                        if use_entry and e_entry is not None and e_exit<e_entry: st.error("청산일은 진입일보다 빠를 수 없습니다.")
                        elif not e_ticker.strip(): st.error("종목명을 입력해주세요.")
                        elif e_buy<=0: st.error("매수금액을 입력해주세요.")
                        else:
                            try:
                                live=normalize_trade_dataframe(conn.read(worksheet=0,ttl=0)); mask=live["Trade_ID"].astype(str)==str(tid)
                                if not mask.any(): st.error("거래를 찾을 수 없습니다.")
                                else:
                                    i=live[mask].index[0]; pl,roi=calculate_trade_result(e_buy,e_sell); final_tags=e_tags+(custom_tags if keep_custom else [])
                                    live.at[i,"Entry_Date"]=pd.Timestamp(e_entry) if use_entry and e_entry is not None else pd.NaT
                                    live.at[i,"Exit_Date"]=pd.Timestamp(e_exit); live.at[i,"Holding_Days"]=(e_exit-e_entry).days if use_entry and e_entry is not None else np.nan
                                    live.at[i,"Ticker"]=e_ticker.strip(); live.at[i,"Buy_Amount"]=float(e_buy); live.at[i,"Sell_Amount"]=float(e_sell); live.at[i,"P_L_Amount"]=float(pl); live.at[i,"ROI_Percent"]=float(roi)
                                    live.at[i,"Mistake_Tags"]=" | ".join(final_tags); live.at[i,"Discipline"]=""; live.at[i,"Memo"]=e_memo
                                    save_trade_dataframe(live); st.success(f"✅ 거래 수정 완료! 손익 {pl:+,.0f}원 / 수익률 {roi:+.2f}%"); st.rerun()
                            except Exception as e: st.error(f"수정 실패: {e}")

                st.divider(); st.markdown("### 🗑️ 거래 삭제")
                confirm=st.checkbox("이 거래를 정말 삭제하겠습니다.",key=f"delete_confirm_{tid}")
                if st.button("🗑️ 거래 영구 삭제",disabled=not confirm,use_container_width=True):
                    try:
                        live=normalize_trade_dataframe(conn.read(worksheet=0,ttl=0)); live=live[live["Trade_ID"].astype(str)!=str(tid)].copy()
                        conn.update(worksheet=0,data=prepare_for_sheet(live)); st.success("🗑️ 거래 삭제 완료!"); st.rerun()
                    except Exception as e: st.error(f"삭제 실패: {e}")

# ============================================================
# TAB 9 - TRADING DNA
# ============================================================
with tab9:
    st.subheader("🧠 My Trading DNA")

    if analysis_df.empty: st.info("거래 기록이 쌓이면 Trading DNA가 생성됩니다.")
    else:
        dna=calculate_trading_dna(analysis_df); holding=calculate_holding_period_dna(analysis_df); mc=calculate_mistake_cost(analysis_df)

        st.markdown(f"## {dna['dna_type']}"); st.info(dna["dna_description"]); st.caption(f"{dna['total_count']:,}건의 거래 기록 기반")

        st.markdown("### 🧬 핵심 DNA")
        a,b,c,d=st.columns(4); a.metric("🎯 승률",f"{dna['win_rate']:.1f}%"); b.metric("⚖️ 평균 손익비",f"{dna['reward_risk']:.2f}"); c.metric("💎 Profit Factor",f"{dna['profit_factor']:.2f}"); d.metric("🔮 거래당 기대값",f"{dna['expectancy']:+.2f}%")

        st.divider(); st.markdown("### 🚀 Big Winner DNA")
        a,b,c,d=st.columns(4); a.metric("🔥 Big Winner 기여도",f"{dna['big_winner_contribution']:.1f}%"); b.metric("🚀 Big Winner 수",f"{dna['big_winner_count']}건"); c.metric("💎 상위 10% 수익 기여",f"{dna['top10_contribution']:.1f}%"); d.metric("🎯 Big Winner 기준",f"+{dna['big_winner_threshold']:.2f}%")

        if not dna["big_winners"].empty:
            bt=dna["big_winners"].sort_values("P_L_Amount",ascending=False)[["Entry_Date","Exit_Date","Holding_Days","Ticker","ROI_Percent","P_L_Amount"]]
            st.dataframe(bt.style.format({"Holding_Days":lambda x:"-" if pd.isna(x) else f"{x:.0f}일","ROI_Percent":"{:+.2f}%","P_L_Amount":"{:+,.0f}원"}),use_container_width=True)

        st.divider(); st.markdown("### ⏱️ Holding Period DNA")
        a,b,c,d=st.columns(4); a.metric("보유기간 데이터",f"{holding['valid_count']}/{len(analysis_df)}건",f"{holding['coverage']:.1f}%"); b.metric("수익거래 평균 보유",format_days(holding["avg_wins"])); c.metric("손실거래 평균 보유",format_days(holding["avg_losses"])); d.metric("Big Winner 평균 보유",format_days(holding["avg_big"]))

        if holding["valid_count"]>0:
            hb=create_holding_bucket_table(analysis_df)
            if not hb.empty: st.dataframe(hb.style.format({"거래수":"{:.0f}건","승률":"{:.1f}%","PF":"{:.2f}","기대값":"{:+.2f}%","평균수익률":"{:+.2f}%","총손익":"{:+,.0f}원"}),use_container_width=True,hide_index=True)

        # ====================================================
        # LOSS CONTROL DNA 1.0
        # ====================================================
        st.divider()
        st.markdown("## 🛡️ Loss Control DNA 1.0")
        st.caption("내 과거 거래에서 손실 제한을 다르게 가정했을 때 성과 지표가 어떻게 달라졌을지 비교합니다.")

        selected_cap=st.slider("가정 손실 제한",min_value=3,max_value=15,value=8,step=1,format="-%d%%",key="loss_control_cap")
        cap_metrics=calculate_loss_cap_metrics(analysis_df,selected_cap)
        actual_metrics=calculate_period_metrics(analysis_df)

        st.markdown(f"### 🔬 실제 기록 vs -{selected_cap}% 손실 제한 가정")

        a,b,c,d=st.columns(4)
        a.metric("실제 총손익",f"{cap_metrics['actual_pl']:+,.0f}원")
        b.metric("가정 총손익",f"{cap_metrics['sim_pl']:+,.0f}원",f"{cap_metrics['pl_change']:+,.0f}원")
        c.metric("실제 PF",f"{actual_metrics['profit_factor']:.2f}")
        d.metric("가정 PF",f"{cap_metrics['profit_factor']:.2f}",f"{cap_metrics['profit_factor']-actual_metrics['profit_factor']:+.2f}")

        a,b,c,d=st.columns(4)
        a.metric("실제 평균 손실률",f"-{actual_metrics['avg_loss_pct']:.2f}%")
        b.metric("가정 평균 손실률",f"-{cap_metrics['avg_loss_pct']:.2f}%")
        c.metric("영향 받은 거래",f"{cap_metrics['affected_count']}건",f"{cap_metrics['affected_rate']:.1f}%")
        d.metric("가정 거래당 기대손익",f"{cap_metrics['expectancy_amount']:+,.0f}원")

        if selected_cap==8:
            st.info("📌 현재 선택한 **-8%는 제이슨의 기본 손실 관리 기준을 참고하기 위한 기준선**입니다. 이 화면은 -8%가 정답이라고 판정하지 않습니다.")

        affected_table=create_loss_cap_trade_table(analysis_df,selected_cap)

        if affected_table.empty:
            st.success(f"현재 기록에는 실현 수익률이 -{selected_cap}%보다 큰 손실로 끝난 거래가 없습니다.")
        else:
            st.markdown(f"#### 🔎 -{selected_cap}%보다 크게 손실 난 거래")
            st.dataframe(affected_table.style.format({"Buy_Amount":"{:,.0f}원","Actual_ROI":"{:+.2f}%","Sim_ROI":"{:+.2f}%","P_L_Amount":"{:+,.0f}원","Sim_P_L_Amount":"{:+,.0f}원","가정 손익 개선":"{:+,.0f}원"}),use_container_width=True,hide_index=True)

        st.markdown("### 📊 손실 제한별 비교")
        sweep=create_loss_cap_sweep(analysis_df,3,15)

        sweep_chart=sweep.copy()
        sweep_chart["손실 제한 표시"]=-sweep_chart["손실 제한"]

        profit_chart=alt.Chart(sweep_chart).mark_line(point=True).encode(
            x=alt.X("손실 제한 표시:Q",title="가정 손실 제한 (%)"),
            y=alt.Y("가상 총손익:Q",title="가상 총손익 (원)"),
            tooltip=[
                alt.Tooltip("손실 제한 표시:Q",title="손실 제한",format=".0f"),
                alt.Tooltip("가상 총손익:Q",format=",.0f"),
                alt.Tooltip("실제 대비 변화:Q",format="+,.0f"),
                alt.Tooltip("영향 거래수:Q")
            ]
        ).properties(height=330)

        st.altair_chart(profit_chart,use_container_width=True)

        pf_chart=alt.Chart(sweep_chart).mark_line(point=True).encode(
            x=alt.X("손실 제한 표시:Q",title="가정 손실 제한 (%)"),
            y=alt.Y("PF:Q",title="Profit Factor"),
            tooltip=[
                alt.Tooltip("손실 제한 표시:Q",title="손실 제한",format=".0f"),
                alt.Tooltip("PF:Q",format=".2f"),
                alt.Tooltip("평균 손실률:Q",format=".2f"),
                alt.Tooltip("영향 거래수:Q")
            ]
        ).properties(height=300)

        st.altair_chart(pf_chart,use_container_width=True)

        display_sweep=sweep.copy()
        display_sweep["손실 제한"]=display_sweep["손실 제한"].map(lambda x:f"-{int(x)}%")

        st.dataframe(display_sweep.style.format({
            "가상 총손익":"{:+,.0f}원",
            "실제 대비 변화":"{:+,.0f}원",
            "PF":"{:.2f}",
            "평균 손실률":"{:.2f}%",
            "거래당 기대수익률":"{:+.2f}%",
            "거래당 기대손익":"{:+,.0f}원",
            "영향 거래수":"{:.0f}건",
            "영향 비율":"{:.1f}%"
        }),use_container_width=True,hide_index=True)

        with st.expander("⚠️ Loss Control DNA 해석할 때 꼭 알아둘 점"):
            st.markdown("""
이 분석은 **실제 손절 백테스트가 아니라 과거 최종 실현수익률을 이용한 단순 손실 제한 시뮬레이션**입니다.

예를 들어 실제로 **-12%**에서 청산한 거래를 -8% 제한으로 선택하면, 이 도구는 단순히 **-8%에서 손실이 끝났다고 가정**합니다.

하지만 실제 시장에서는 다음을 알 수 없습니다.

- 거래 중 -8%까지 내려갔다가 +20%로 끝난 거래
- 갭하락 때문에 -8% 주문이 -11%에서 체결됐을 가능성
- 손절 후 재진입했을 가능성
- 시험매매 → 추가매수 → 피라미딩 과정에서 실제 위험금액이 달라진 경우
- 손절로 확보한 자금을 다른 거래에 투입했을 경우

따라서 이 숫자는 **“몇 % 손절이 정답인가?”를 결정하는 도구가 아니라, 내 손실 분포가 어느 구간에 집중되어 있는지 탐색하는 도구**로 사용합니다.

향후 **MAE / MFE 데이터**가 쌓이면 실제 추세추종 전략에 훨씬 가까운 손절 분석으로 발전시킬 수 있습니다.
""")

        # MISTAKE COST
        st.divider(); st.markdown("### 💸 Mistake Cost 2.0")
        a,b,c,d=st.columns(4); a.metric("✅ 정상 거래",f"{mc['normal_count']}건"); b.metric("⚠️ 실수 거래",f"{mc['mistake_count']}건",f"{mc['mistake_rate']:.1f}%"); c.metric("💰 정상 거래 손익",f"{mc['normal_pl']:+,.0f}원"); d.metric("💸 실수 거래 손익",f"{mc['mistake_pl']:+,.0f}원")
        a,b,c,d=st.columns(4); a.metric("정상 거래 승률",f"{mc['normal_metrics']['win_rate']:.1f}%"); b.metric("실수 거래 승률",f"{mc['mistake_metrics']['win_rate']:.1f}%"); c.metric("정상 거래 PF",f"{mc['normal_metrics']['profit_factor']:.2f}"); d.metric("실수 거래 PF",f"{mc['mistake_metrics']['profit_factor']:.2f}")

        if mc["mistake_count"]>0:
            st.markdown("#### 🧾 실수 유형별 실제 성과")
            st.dataframe(mc["tag_table"].style.format({"발생횟수":"{:.0f}회","승률":"{:.1f}%","PF":"{:.2f}","평균수익률":"{:+.2f}%","실제손익":"{:+,.0f}원"}),use_container_width=True,hide_index=True)

        st.markdown("#### 🧠 Mistake Coach")
        for x in generate_mistake_insights(mc): st.markdown(f"- {x}")

        # RISK
        st.divider(); st.markdown("### 🛡️ Risk DNA")
        a,b,c,d=st.columns(4); a.metric("평균 손실률",f"-{dna['avg_loss_pct']:.2f}%"); b.metric("최대 손실률",f"-{dna['max_loss_pct']:.2f}%"); c.metric("최대 연속 손실",f"{dna['max_loss_streak']}회"); d.metric("최대 연속 수익",f"{dna['max_win_streak']}회")

        # EDGE
        st.divider(); st.markdown("### 📡 Edge Change Detection")
        st.markdown(f"## {dna['edge_icon']} 현재 Edge 상태: **{dna['edge_status']}**")
        recent=dna["recent_metrics"]
        a,b,c,d=st.columns(4); a.metric("최근 20 승률",f"{recent['win_rate']:.1f}%",f"{dna['changes']['win_rate']:+.1f}%p" if dna["has_previous"] else None); b.metric("최근 20 PF",f"{recent['profit_factor']:.2f}",f"{dna['changes']['profit_factor']:+.2f}" if dna["has_previous"] else None); c.metric("최근 20 손익비",f"{recent['reward_risk']:.2f}",f"{dna['changes']['reward_risk']:+.2f}" if dna["has_previous"] else None); d.metric("최근 20 기대값",f"{recent['expectancy']:+.2f}%",f"{dna['changes']['expectancy']:+.2f}%p" if dna["has_previous"] else None)

        if dna["has_previous"]: st.dataframe(create_edge_comparison_table(dna).style.format({"전체":"{:.2f}","직전 20":"{:.2f}","최근 20":"{:.2f}","변화":"{:+.2f}"}),use_container_width=True,hide_index=True)
        else: st.info("직전 구간과 비교하려면 거래 기록이 조금 더 필요합니다.")

        st.markdown("### 🔍 Edge 변화 원인")
        drivers=detect_edge_drivers(dna)
        if drivers:
            for x in drivers:
                if x["direction"]=="positive": st.success("📈 "+x["text"])
                else: st.warning("📉 "+x["text"])
        else: st.info("현재 구간에서는 뚜렷한 Edge 변화 원인이 감지되지 않았습니다.")

        # ROI
        st.divider(); st.markdown("### 📊 어디에서 돈을 벌고 잃는가?")
        buckets=create_roi_bucket_table(analysis_df)
        if not buckets.empty:
            st.dataframe(buckets.style.format({"거래수":"{:,.0f}건","총손익":"{:+,.0f}원","평균수익률":"{:+.2f}%"}),use_container_width=True,hide_index=True)

        # COACH
        st.divider(); st.markdown("### 🧠 Trading Coach Insights")
        for x in generate_rule_based_insights(dna): st.markdown(f"- {x}")

        st.markdown("### 🎯 다음 거래 체크포인트")
        checkpoints=generate_coach_checkpoints(dna,mc)
        for i,x in enumerate(checkpoints,1): st.markdown(f"**{i}.** {x}")

        # AI
        st.divider(); st.markdown("### 🤖 AI Trading Coach")
        with st.expander("🔑 AI Coach 설정",expanded=False):
            api_key=st.text_input("Gemini API Key",type="password",key="dna_ai_api_key")

        if not api_key: st.info("AI Coach를 사용할 경우 Gemini API Key를 입력하세요.")
        else:
            if st.button("🧠 내 Trading DNA AI 분석",use_container_width=True,type="primary"):
                with st.spinner("AI Coach가 Trading DNA를 분석 중입니다..."):
                    try: st.session_state["ai_coach_report"]=run_ai_coach(api_key,dna,checkpoints,drivers,holding,mc)
                    except Exception as e: st.error(f"🚨 AI Coach 분석 실패: {e}")

            if st.session_state.get("ai_coach_report"):
                st.success("✅ AI Coach 분석 완료")
                st.markdown(st.session_state["ai_coach_report"])

        st.caption("⚠️ Trading Coach는 투자 추천이 아니라 본인의 매매 기록과 행동을 복기하기 위한 분석 도구입니다.")
