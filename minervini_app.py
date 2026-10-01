import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import altair as alt
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import random, json, re, hashlib
import google.generativeai as genai
from PIL import Image

# ============================================================
# 1. PAGE / CONNECTION
# ============================================================
st.set_page_config(page_title="Trading Master Dashboard", page_icon="💎", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

REQUIRED_COLUMNS = ["Trade_ID","Entry_Date","Exit_Date","Holding_Days","Ticker","Buy_Amount","Sell_Amount","P_L_Amount","ROI_Percent","Mistake_Tags","Emotion","Discipline","Memo"]
MISTAKE_OPTIONS = ["추격매수","손절 지연","조기청산","과도한 포지션","계획 없는 진입","재진입 남발","복수매매/뇌동매매","진입 기준 미충족","기타"]
DISCIPLINE_OPTIONS = ["정상","규칙 위반"]
EMOTION_OPTIONS = ["","평온","불안","조급","흥분","복수심","확신 과다"]

# ============================================================
# 2. TRADE ID
# ============================================================
def create_legacy_trade_id(row, index):
    date_value = row.get("Exit_Date", row.get("Date",""))
    values = [str(index),str(date_value),str(row.get("Ticker","")),str(row.get("Buy_Amount","")),str(row.get("Sell_Amount","")),str(row.get("P_L_Amount","")),str(row.get("ROI_Percent","")),str(row.get("Memo",""))]
    return f"LEGACY_{hashlib.sha1('|'.join(values).encode('utf-8')).hexdigest()[:12]}"

def create_new_trade_id():
    return f"TRD_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{random.randint(1000,9999)}"

# ============================================================
# 3. CONFIG
# ============================================================
def load_status():
    try:
        x = conn.read(worksheet=1, ttl=0)
        if x.empty: return 20000000, 5000000, []
        row = x.iloc[0]; equity = int(row.get("Total_Equity",20000000)); max_pos = int(row.get("Max_Position",5000000)); h = str(row.get("History",""))
        return equity, max_pos, h.split(",") if h and h != "nan" else []
    except Exception: return 20000000, 5000000, []

def save_status(equity, max_pos, history):
    try:
        x = conn.read(worksheet=1, ttl=0); new_df = x.copy() if not x.empty else pd.DataFrame([{}])
        new_df.at[0,"Total_Equity"] = equity; new_df.at[0,"Max_Position"] = max_pos; new_df.at[0,"History"] = ",".join(map(str,history))
        conn.update(worksheet=1, data=new_df)
    except Exception as e: st.error(f"설정 저장 실패: {e}")

@st.cache_data(ttl=0)
def load_settings():
    try:
        x = conn.read(worksheet=1, ttl=0)
        if not x.empty: return x.iloc[0].to_dict()
    except Exception: pass
    return {}

saved_config = load_settings()

# ============================================================
# 4. KRX
# ============================================================
@st.cache_data(ttl=3600)
def get_krx_list():
    try:
        x = fdr.StockListing("KRX")
        return x[["Code","Name","Market"]]
    except Exception: return pd.DataFrame()

# ============================================================
# 5. SAFE DATA NORMALIZATION
# ============================================================
def is_blank_series(series):
    return series.isna() | series.astype("string").fillna("").str.strip().str.lower().isin(["","nan","nat","none","<na>"])

def clean_number(series):
    s = series.astype("string").fillna("").str.replace(",","",regex=False).str.replace("%","",regex=False).str.replace("원","",regex=False).str.strip()
    return pd.to_numeric(s, errors="coerce").fillna(0.0).astype("float64")

def normalize_trade_dataframe(raw_df):
    if raw_df is None or raw_df.empty: return pd.DataFrame(columns=REQUIRED_COLUMNS)

    x = raw_df.copy()

    # 중요: 날짜 컬럼은 float NaN 컬럼으로 만들지 않고 처음부터 object로 생성
    if "Exit_Date" not in x.columns:
        if "Date" in x.columns: x["Exit_Date"] = x["Date"].copy()
        else: x["Exit_Date"] = pd.Series([None] * len(x), index=x.index, dtype="object")
    elif "Date" in x.columns:
        missing_exit = is_blank_series(x["Exit_Date"])
        # .loc 배열 대입 대신 where 사용 -> ArrowStringArray dtype 충돌 방지
        x["Exit_Date"] = x["Exit_Date"].where(~missing_exit, x["Date"])

    if "Entry_Date" not in x.columns: x["Entry_Date"] = pd.Series([None] * len(x), index=x.index, dtype="object")
    if "Holding_Days" not in x.columns: x["Holding_Days"] = pd.Series([np.nan] * len(x), index=x.index, dtype="float64")
    if "Trade_ID" not in x.columns: x["Trade_ID"] = pd.Series([""] * len(x), index=x.index, dtype="object")

    defaults = {"Ticker":"","Buy_Amount":0.0,"Sell_Amount":0.0,"P_L_Amount":0.0,"ROI_Percent":0.0,"Mistake_Tags":"","Emotion":"","Discipline":"","Memo":""}
    for col,val in defaults.items():
        if col not in x.columns: x[col] = val

    # 날짜는 별도 Series로 변환 후 통째로 할당 -> Arrow/Pandas dtype 충돌 방지
    entry_dates = pd.to_datetime(x["Entry_Date"].astype("string").replace({"":"", "nan":"", "NaT":"", "<NA>":""}), errors="coerce")
    exit_dates = pd.to_datetime(x["Exit_Date"].astype("string").replace({"":"", "nan":"", "NaT":"", "<NA>":""}), errors="coerce")
    x = x.copy()
    x["Entry_Date"] = entry_dates
    x["Exit_Date"] = exit_dates

    # 청산일 없는 행만 제외. 진입일 없는 과거 거래는 그대로 보존.
    x = x[x["Exit_Date"].notna()].copy()
    if x.empty: return pd.DataFrame(columns=REQUIRED_COLUMNS)

    for col in ["Buy_Amount","Sell_Amount","P_L_Amount","ROI_Percent"]: x[col] = clean_number(x[col])

    for col in ["Ticker","Mistake_Tags","Emotion","Discipline","Memo"]:
        x[col] = x[col].astype("string").fillna("").replace({"nan":"","None":"","<NA>":""}).astype(str)

    # 기존 데이터에 실수 태그가 있으나 Discipline이 비어 있으면 규칙 위반으로 분류
    tag_exists = x["Mistake_Tags"].str.strip().ne("")
    discipline_blank = x["Discipline"].str.strip().eq("")
    x.loc[tag_exists & discipline_blank,"Discipline"] = "규칙 위반"

    # 보유일수는 날짜가 모두 존재하고 순서가 정상인 경우에만 계산
    holding = pd.Series(np.nan, index=x.index, dtype="float64")
    valid_dates = x["Entry_Date"].notna() & x["Exit_Date"].notna() & (x["Entry_Date"] <= x["Exit_Date"])
    if valid_dates.any():
        holding.loc[valid_dates] = (x.loc[valid_dates,"Exit_Date"].dt.normalize() - x.loc[valid_dates,"Entry_Date"].dt.normalize()).dt.days.astype(float)
    x["Holding_Days"] = holding

    # 과거 데이터 복구 로직
    recovery = (x["Buy_Amount"] == 0) & (x["ROI_Percent"] != 0)
    if recovery.any():
        x.loc[recovery,"Buy_Amount"] = (x.loc[recovery,"P_L_Amount"] / (x.loc[recovery,"ROI_Percent"] / 100)).abs()
        x.loc[recovery,"Sell_Amount"] = x.loc[recovery,"Buy_Amount"] + x.loc[recovery,"P_L_Amount"]

    # 기존 ID는 절대 변경하지 않고 없는 ID만 생성
    for pos,idx in enumerate(x.index):
        tid = x.at[idx,"Trade_ID"]
        if pd.isna(tid) or str(tid).strip().lower() in ["","nan","none","<na>"]: x.at[idx,"Trade_ID"] = create_legacy_trade_id(x.loc[idx],pos)
        else: x.at[idx,"Trade_ID"] = str(tid)

    return x[REQUIRED_COLUMNS].reset_index(drop=True)

def prepare_for_sheet(dataframe):
    x = dataframe.copy()
    for col in REQUIRED_COLUMNS:
        if col not in x.columns: x[col] = ""

    for col in ["Entry_Date","Exit_Date"]:
        dates = pd.to_datetime(x[col], errors="coerce")
        x[col] = dates.dt.strftime("%Y-%m-%d").fillna("").astype(str)

    x["Holding_Days"] = pd.to_numeric(x["Holding_Days"], errors="coerce").apply(lambda v: "" if pd.isna(v) else str(int(v)))

    for col in ["Buy_Amount","Sell_Amount","P_L_Amount","ROI_Percent"]:
        x[col] = pd.to_numeric(x[col], errors="coerce").fillna(0.0)

    for col in ["Trade_ID","Ticker","Mistake_Tags","Emotion","Discipline","Memo"]:
        x[col] = x[col].astype("string").fillna("").replace({"nan":"","None":"","<NA>":""}).astype(str)

    return x[REQUIRED_COLUMNS]

def load_data():
    try:
        raw = conn.read(worksheet=0, ttl=0)
        return normalize_trade_dataframe(raw)
    except Exception as e:
        st.error(f"데이터 불러오기 실패: {e}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def migrate_trade_schema():
    try:
        raw = conn.read(worksheet=0, ttl=0)
        if raw is None or raw.empty: return

        missing_columns = any(c not in raw.columns for c in REQUIRED_COLUMNS)
        legacy_date = "Date" in raw.columns

        if "Trade_ID" not in raw.columns: missing_ids = True
        else: missing_ids = is_blank_series(raw["Trade_ID"]).any()

        if missing_columns or legacy_date or missing_ids:
            migrated = normalize_trade_dataframe(raw)
            if not migrated.empty: conn.update(worksheet=0, data=prepare_for_sheet(migrated))
    except Exception as e:
        st.warning(f"데이터 구조 자동 변환을 완료하지 못했습니다: {e}")

# ============================================================
# 6. CORE METRICS
# ============================================================
def calculate_period_metrics(data):
    empty = {"count":0,"win_rate":0.0,"profit_factor":0.0,"reward_risk":0.0,"expectancy":0.0,"avg_win_pct":0.0,"avg_loss_pct":0.0,"gross_profit":0.0,"gross_loss":0.0,"net_profit":0.0,"big_winner_threshold":0.0,"big_winner_count":0,"big_winner_rate":0.0,"big_winner_contribution":0.0}
    if data is None or data.empty: return empty
    wins = data[data["P_L_Amount"]>0]; losses = data[data["P_L_Amount"]<0]; count = len(data)
    gp = wins["P_L_Amount"].sum() if not wins.empty else 0; gl = abs(losses["P_L_Amount"].sum()) if not losses.empty else 0
    wr = len(wins)/count*100 if count else 0; aw = wins["ROI_Percent"].mean() if not wins.empty else 0; al = abs(losses["ROI_Percent"].mean()) if not losses.empty else 0
    pf = gp/gl if gl>0 else 0; rr = aw/al if al>0 else 0; expectancy = (len(wins)/count)*aw-(len(losses)/count)*al if count else 0
    threshold = al*2 if al>0 else 10; big = wins[wins["ROI_Percent"]>=threshold]; bp = big["P_L_Amount"].sum() if not big.empty else 0
    return {"count":count,"win_rate":wr,"profit_factor":pf,"reward_risk":rr,"expectancy":expectancy,"avg_win_pct":aw,"avg_loss_pct":al,"gross_profit":gp,"gross_loss":gl,"net_profit":data["P_L_Amount"].sum(),"big_winner_threshold":threshold,"big_winner_count":len(big),"big_winner_rate":len(big)/count*100 if count else 0,"big_winner_contribution":bp/gp*100 if gp>0 else 0}

def calculate_max_streaks(data):
    if data.empty: return 0,0
    ordered = data.sort_values(["Exit_Date","Trade_ID"]); mw=ml=cw=cl=0
    for v in ordered["P_L_Amount"]:
        if v>0: cw+=1; cl=0; mw=max(mw,cw)
        elif v<0: cl+=1; cw=0; ml=max(ml,cl)
        else: cw=cl=0
    return mw,ml

def calculate_current_streak(data):
    if data.empty: return "none",0
    vals = data.sort_values(["Exit_Date","Trade_ID"])["P_L_Amount"].tolist()
    typ = "win" if vals[-1]>0 else "loss" if vals[-1]<0 else "none"
    if typ=="none": return typ,0
    n=0
    for v in reversed(vals):
        if (typ=="win" and v>0) or (typ=="loss" and v<0): n+=1
        else: break
    return typ,n

# ============================================================
# 7. HOLDING PERIOD DNA
# ============================================================
def calculate_holding_period_dna(data):
    result = {"valid_count":0,"coverage":0.0,"avg_all":None,"avg_wins":None,"avg_losses":None,"avg_big":None,"recent_avg_wins":None,"recent_avg_big":None}
    if data.empty: return result
    valid = data[data["Holding_Days"].notna() & (data["Holding_Days"]>=0)].copy()
    result["valid_count"] = len(valid); result["coverage"] = len(valid)/len(data)*100 if len(data) else 0
    if valid.empty: return result
    m = calculate_period_metrics(data); wins = valid[valid["P_L_Amount"]>0]; losses = valid[valid["P_L_Amount"]<0]; big = wins[wins["ROI_Percent"]>=m["big_winner_threshold"]]
    recent = data.sort_values(["Exit_Date","Trade_ID"]).tail(20); rw = recent[recent["Holding_Days"].notna() & (recent["P_L_Amount"]>0)]; rb = rw[rw["ROI_Percent"]>=m["big_winner_threshold"]]
    result.update({"avg_all":valid["Holding_Days"].mean(),"avg_wins":wins["Holding_Days"].mean() if not wins.empty else None,"avg_losses":losses["Holding_Days"].mean() if not losses.empty else None,"avg_big":big["Holding_Days"].mean() if not big.empty else None,"recent_avg_wins":rw["Holding_Days"].mean() if not rw.empty else None,"recent_avg_big":rb["Holding_Days"].mean() if not rb.empty else None})
    return result

def create_holding_bucket_table(data):
    x = data[data["Holding_Days"].notna() & (data["Holding_Days"]>=0)].copy()
    if x.empty: return pd.DataFrame()
    x["보유구간"] = pd.cut(x["Holding_Days"],bins=[-0.1,0.9,3.9,10.9,30.9,90.9,np.inf],labels=["당일","1~3일","4~10일","11~30일","31~90일","91일+"],right=True)
    rows=[]
    for name,g in x.groupby("보유구간",observed=False):
        if g.empty: continue
        m=calculate_period_metrics(g); rows.append({"보유구간":str(name),"거래수":len(g),"승률":m["win_rate"],"PF":m["profit_factor"],"기대값":m["expectancy"],"평균수익률":g["ROI_Percent"].mean(),"총손익":g["P_L_Amount"].sum()})
    return pd.DataFrame(rows)

# ============================================================
# 8. MISTAKE COST ENGINE
# ============================================================
def has_mistake(row):
    return bool(str(row.get("Mistake_Tags","")).strip()) or str(row.get("Discipline","")).strip()=="규칙 위반"

def calculate_mistake_cost(data):
    empty = {"total_count":len(data) if data is not None else 0,"violation_count":0,"violation_rate":0.0,"violation_pl":0.0,"normal_count":0,"normal_pl":0.0,"normal_metrics":calculate_period_metrics(pd.DataFrame()),"violation_metrics":calculate_period_metrics(pd.DataFrame()),"tag_table":pd.DataFrame(),"recent_violation_rate":0.0,"previous_violation_rate":0.0,"change_violation_rate":0.0}
    if data is None or data.empty: return empty

    x=data.copy(); x["Has_Mistake"]=x.apply(has_mistake,axis=1); bad=x[x["Has_Mistake"]].copy(); normal=x[~x["Has_Mistake"]].copy()
    tag_rows=[]
    for _,row in bad.iterrows():
        tags=[t.strip() for t in re.split(r"[,|;/]",str(row["Mistake_Tags"]).strip()) if t.strip()]
        if not tags: tags=["규칙 위반(태그 없음)"]
        for tag in tags: tag_rows.append({"실수":tag,"P_L_Amount":row["P_L_Amount"],"ROI_Percent":row["ROI_Percent"],"Trade_ID":row["Trade_ID"]})

    if tag_rows:
        td=pd.DataFrame(tag_rows); table=td.groupby("실수").agg(발생횟수=("Trade_ID","count"),실제손익=("P_L_Amount","sum"),평균수익률=("ROI_Percent","mean")).reset_index().sort_values(["실제손익","발생횟수"],ascending=[True,False])
    else: table=pd.DataFrame(columns=["실수","발생횟수","실제손익","평균수익률"])

    ordered=x.sort_values(["Exit_Date","Trade_ID"]); recent=ordered.tail(min(20,len(ordered)))
    previous=ordered.iloc[max(0,len(ordered)-40):max(0,len(ordered)-20)] if len(ordered)>20 else pd.DataFrame(columns=ordered.columns)
    rr=recent["Has_Mistake"].mean()*100 if not recent.empty else 0; pr=previous["Has_Mistake"].mean()*100 if not previous.empty else 0
    return {"total_count":len(x),"violation_count":len(bad),"violation_rate":len(bad)/len(x)*100,"violation_pl":bad["P_L_Amount"].sum(),"normal_count":len(normal),"normal_pl":normal["P_L_Amount"].sum(),"normal_metrics":calculate_period_metrics(normal),"violation_metrics":calculate_period_metrics(bad),"tag_table":table,"recent_violation_rate":rr,"previous_violation_rate":pr,"change_violation_rate":rr-pr if not previous.empty else 0}

def generate_mistake_insights(mc):
    insights=[]
    if mc["violation_count"]==0: return ["✅ 현재 기록에는 실수/규칙 위반 태그가 없습니다. 앞으로 거래마다 태그를 기록하면 패턴이 누적됩니다."]
    if not mc["tag_table"].empty:
        worst=mc["tag_table"].iloc[0]; frequent=mc["tag_table"].sort_values("발생횟수",ascending=False).iloc[0]
        insights.append(f"💸 기록상 가장 손익이 낮은 실수 유형은 **{worst['실수']}**이며, {int(worst['발생횟수'])}회 거래의 실제 합산 손익은 **{worst['실제손익']:+,.0f}원**입니다.")
        insights.append(f"🔁 가장 자주 기록된 실수는 **{frequent['실수']}**로 {int(frequent['발생횟수'])}회입니다.")
    if mc["normal_count"]>=3 and mc["violation_count"]>=3: insights.append(f"📊 정상 거래 PF는 **{mc['normal_metrics']['profit_factor']:.2f}**, 규칙 위반 거래 PF는 **{mc['violation_metrics']['profit_factor']:.2f}**입니다. 기록상 동반된 성과 차이이며 인과관계를 의미하지 않습니다.")
    if mc["previous_violation_rate"]>0 and mc["change_violation_rate"]>=10: insights.append(f"⚠️ 최근 20거래의 규칙 위반 비율이 직전 구간보다 **{mc['change_violation_rate']:+.1f}%p** 높아졌습니다.")
    return insights[:4]

# ============================================================
# 9. TRADING DNA
# ============================================================
def calculate_trading_dna(data):
    if data.empty: return {}
    ordered=data.sort_values(["Exit_Date","Trade_ID"]).copy(); total=calculate_period_metrics(ordered); n=len(ordered)
    wins=ordered[ordered["P_L_Amount"]>0]; losses=ordered[ordered["P_L_Amount"]<0]

    if not wins.empty and total["gross_profit"]>0:
        top_n=max(1,int(np.ceil(len(wins)*.1))); top_profit=wins.nlargest(top_n,"P_L_Amount")["P_L_Amount"].sum(); top10=top_profit/total["gross_profit"]*100
    else: top_n,top10=0,0

    big=wins[wins["ROI_Percent"]>=total["big_winner_threshold"]].copy(); max_win,max_loss=calculate_max_streaks(ordered); current_type,current=calculate_current_streak(ordered)
    max_loss_pct=abs(losses["ROI_Percent"].min()) if not losses.empty else 0; max_loss_amount=abs(losses["P_L_Amount"].min()) if not losses.empty else 0
    recent=ordered.tail(min(20,n)).copy(); rm=calculate_period_metrics(recent)

    if n>=40: previous=ordered.iloc[n-40:n-20].copy()
    elif n>20: previous=ordered.iloc[:n-20].tail(20).copy()
    else: previous=pd.DataFrame(columns=ordered.columns)

    pm=calculate_period_metrics(previous); has_previous=len(previous)>=5
    keys=["win_rate","profit_factor","reward_risk","expectancy","avg_win_pct","avg_loss_pct","big_winner_rate","big_winner_contribution"]
    changes={k:rm[k]-pm[k] if has_previous else 0 for k in keys}

    if not has_previous: status,icon="데이터 축적 중","🟡"
    else:
        score=0
        score += 2 if changes["expectancy"]>.75 else -2 if changes["expectancy"]<-.75 else 0
        score += 1 if changes["profit_factor"]>.2 else -1 if changes["profit_factor"]<-.2 else 0
        score += 1 if changes["reward_risk"]>.25 else -1 if changes["reward_risk"]<-.25 else 0
        score += 1 if changes["avg_loss_pct"]<-.5 else -1 if changes["avg_loss_pct"]>.5 else 0
        score += 1 if changes["big_winner_rate"]>2 else -1 if changes["big_winner_rate"]<-2 else 0
        status,icon=("개선","🟢") if score>=2 else ("주의","🔴") if score<=-2 else ("안정","🟡")

    wr,rr=total["win_rate"],total["reward_risk"]
    if rr>=2 and wr<50: dtype,desc="🧬 Trend Follower","낮은 승률을 감수하고 큰 수익 거래로 전체 성과를 만드는 추세추종형 구조입니다."
    elif wr>=60 and rr<1.5: dtype,desc="🎯 High Accuracy Trader","높은 승률을 기반으로 수익을 누적하는 고승률형 구조입니다."
    elif rr>=1.5 and wr>=45: dtype,desc="⚖️ Balanced Trader","승률과 손익비가 비교적 균형을 이루는 밸런스형 구조입니다."
    elif top10>=60 or total["big_winner_contribution"]>=60: dtype,desc="🚀 Big Winner Hunter","소수의 큰 수익 거래가 전체 성과에 강한 영향을 주는 구조입니다."
    else: dtype,desc="🔬 Developing Edge","현재 기록에서는 여러 수익 패턴이 혼합되어 있습니다."

    return {"total_count":n,"win_rate":wr,"profit_factor":total["profit_factor"],"reward_risk":rr,"expectancy":total["expectancy"],"avg_win_pct":total["avg_win_pct"],"avg_loss_pct":total["avg_loss_pct"],"gross_profit":total["gross_profit"],"gross_loss":total["gross_loss"],"top10_contribution":top10,"top_n":top_n,"big_winner_threshold":total["big_winner_threshold"],"big_winner_count":len(big),"big_winner_contribution":total["big_winner_contribution"],"max_win_streak":max_win,"max_loss_streak":max_loss,"current_streak_type":current_type,"current_streak":current,"max_loss_pct":max_loss_pct,"max_loss_amount":max_loss_amount,"recent_count":len(recent),"recent_df":recent,"previous_df":previous,"recent_metrics":rm,"previous_metrics":pm,"total_metrics":total,"changes":changes,"has_previous":has_previous,"edge_status":status,"edge_icon":icon,"edge_change":changes["expectancy"],"dna_type":dtype,"dna_description":desc,"big_winners":big}

def detect_edge_drivers(dna):
    if not dna or not dna["has_previous"]: return []
    c=dna["changes"]; candidates=[("승률",c["win_rate"]/5,f"승률 {c['win_rate']:+.1f}%p"),("Profit Factor",c["profit_factor"]*2,f"PF {c['profit_factor']:+.2f}"),("손익비",c["reward_risk"]*1.5,f"손익비 {c['reward_risk']:+.2f}"),("평균 수익률",c["avg_win_pct"]/2,f"평균 수익률 {c['avg_win_pct']:+.2f}%p"),("평균 손실률",-c["avg_loss_pct"]/2,f"평균 손실률 {c['avg_loss_pct']:+.2f}%p"),("Big Winner 비율",c["big_winner_rate"]/4,f"Big Winner 비율 {c['big_winner_rate']:+.1f}%p")]
    return [{"name":n,"direction":"positive" if imp>0 else "negative","text":txt} for n,imp,txt in sorted(candidates,key=lambda z:abs(z[1]),reverse=True)[:3] if abs(imp)>=.15]

def generate_coach_checkpoints(dna):
    out=[]; c=dna["changes"]; total=dna["total_metrics"]
    if dna["has_previous"] and c["avg_loss_pct"]>.75: out.append(f"🛡️ 최근 평균 손실률이 {c['avg_loss_pct']:+.2f}%p 확대됐습니다. 다음 거래에서는 손절 기준 이탈 여부를 기록하세요.")
    if dna["has_previous"] and c["big_winner_rate"]<-3: out.append(f"🚀 최근 Big Winner 비율이 {abs(c['big_winner_rate']):.1f}%p 감소했습니다. 수익 거래를 너무 빨리 청산하고 있지 않은지 확인하세요.")
    if dna["has_previous"] and c["avg_win_pct"]<-1: out.append(f"💎 최근 평균 수익률이 {abs(c['avg_win_pct']):.2f}%p 낮아졌습니다. 큰 추세를 충분히 보유했는지 확인하세요.")
    if dna["has_previous"] and c["profit_factor"]<-.25: out.append(f"📉 최근 PF가 {abs(c['profit_factor']):.2f} 하락했습니다. 손실 크기와 Big Winner 감소를 함께 확인하세요.")
    if total["reward_risk"]>=2 and total["win_rate"]<50: out.append("🧬 장기 구조는 승률보다 손익비 의존도가 높습니다. 손실 제한과 큰 승자 보유가 유지되는지 관찰하세요.")
    if dna["current_streak_type"]=="loss" and dna["current_streak"]>=4: out.append(f"⚠️ 현재 {dna['current_streak']}연속 손실입니다. 전략 변경보다 진입 조건과 손실 크기 변화를 먼저 확인하세요.")
    if not out: out.append("✅ 최근 통계에서 뚜렷한 구조 훼손 신호는 발견되지 않았습니다.")
    return out[:3]

def generate_rule_based_insights(dna):
    out=[]
    if dna["big_winner_contribution"]>=60: out.append(f"🔥 큰 수익 거래가 Gross Profit의 {dna['big_winner_contribution']:.1f}%를 만들고 있습니다.")
    elif dna["big_winner_contribution"]>=35: out.append("🔥 Big Winner가 전체 수익에서 의미 있는 비중을 차지합니다.")
    else: out.append("📊 수익이 여러 거래에 상대적으로 분산되어 있습니다.")
    if dna["top10_contribution"]>=40: out.append("💎 상위 수익 거래의 기여도가 높습니다. 최고 수익 거래의 공통점을 추적할 가치가 있습니다.")
    if dna["reward_risk"]>=2 and dna["win_rate"]<50: out.append("🧬 승률보다 손익비가 성과를 만드는 구조입니다. 평균 손실 통제와 큰 승자 확보가 핵심입니다.")
    if dna["avg_loss_pct"]>0 and dna["max_loss_pct"]>=dna["avg_loss_pct"]*2.5: out.append("⚠️ 최대 손실이 평균 손실보다 상당히 큽니다. 예외적 손실 원인을 확인하세요.")
    if dna["max_loss_streak"]>=6: out.append(f"🧠 과거 최대 연속 손실은 {dna['max_loss_streak']}회입니다.")
    return out

# ============================================================
# 10. TABLE HELPERS
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
# 11. AI COACH
# ============================================================
def build_ai_coach_prompt(dna,checkpoints,drivers,holding,mistake):
    t,p,r=dna["total_metrics"],dna["previous_metrics"],dna["recent_metrics"]
    driver_text="\n".join(f"- {x['text']} ({x['direction']})" for x in drivers) or "- 뚜렷한 변화 없음"
    cp="\n".join(f"- {x}" for x in checkpoints)
    hold_text=f"보유기간 데이터 커버리지 {holding['coverage']:.1f}%, 수익거래 평균 {holding['avg_wins'] if holding['avg_wins'] is not None else '데이터 없음'}일, 손실거래 평균 {holding['avg_losses'] if holding['avg_losses'] is not None else '데이터 없음'}일, Big Winner 평균 {holding['avg_big'] if holding['avg_big'] is not None else '데이터 없음'}일"
    return f"""
당신은 트레이딩 저널 데이터 해석 코치입니다.
제공된 숫자만 사용하고 새로운 숫자를 만들지 마세요.
종목 추천, 미래 예측, 전략의 좋고 나쁨 판단을 하지 마세요.
상관관계를 인과관계로 표현하지 마세요.
추세추종에서는 낮은 승률 자체를 문제라고 하지 마세요.
보유기간과 성과가 함께 변해도 원인으로 단정하지 마세요.
한국어로 간결하고 실전적으로 작성하세요.

[Trading DNA] 유형 {dna['dna_type']} / 전체 {dna['total_count']}건 / Edge {dna['edge_status']}
[전체] 승률 {t['win_rate']:.2f}% / PF {t['profit_factor']:.2f} / 손익비 {t['reward_risk']:.2f} / 기대값 {t['expectancy']:.2f}% / 평균수익 {t['avg_win_pct']:.2f}% / 평균손실 {t['avg_loss_pct']:.2f}% / Big Winner {t['big_winner_rate']:.2f}%
[직전] {p['count']}건 / 승률 {p['win_rate']:.2f}% / PF {p['profit_factor']:.2f} / 손익비 {p['reward_risk']:.2f} / 기대값 {p['expectancy']:.2f}%
[최근] {r['count']}건 / 승률 {r['win_rate']:.2f}% / PF {r['profit_factor']:.2f} / 손익비 {r['reward_risk']:.2f} / 기대값 {r['expectancy']:.2f}%
[보유기간] {hold_text}
[Mistake Cost] 규칙위반 {mistake['violation_count']}건 / {mistake['violation_rate']:.1f}% / 해당 거래 실제 합산손익 {mistake['violation_pl']:+,.0f}원 / 정상 PF {mistake['normal_metrics']['profit_factor']:.2f} / 규칙위반 PF {mistake['violation_metrics']['profit_factor']:.2f}
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
마지막 문장: "이 분석은 매수·매도 추천이 아니라 본인의 매매 행동을 점검하기 위한 트레이딩 저널 분석입니다."
"""

def run_ai_coach(api_key,dna,checkpoints,drivers,holding,mistake):
    genai.configure(api_key=api_key.strip()); model=genai.GenerativeModel("gemini-2.5-flash")
    response=model.generate_content(build_ai_coach_prompt(dna,checkpoints,drivers,holding,mistake))
    if not response.parts: raise ValueError("AI Coach 응답이 없습니다.")
    return response.text.strip()

# ============================================================
# 12. LOAD / MIGRATE
# ============================================================
migrate_trade_schema()
df=load_data()
krx_list=get_krx_list()

# ============================================================
# 13. SIDEBAR AI SCREENSHOT
# ============================================================
st.sidebar.header("📸 AI 영수증 자동 입력")
with st.sidebar.expander("🤖 캡쳐 화면 올리기",expanded=False):
    st.markdown("수익/손실 화면을 올리면 종목명, 매수금액, 수익률을 자동으로 읽습니다.")
    api_key=st.text_input("Gemini API Key",type="password",key="sidebar_api")
    uploaded_file=st.file_uploader("증권사 캡쳐 이미지",type=["png","jpg","jpeg"],key="sidebar_uploader")
    if st.button("🔍 데이터 추출하기",use_container_width=True):
        if not api_key: st.error("Gemini API Key가 필요합니다.")
        elif not uploaded_file: st.error("이미지를 올려주세요.")
        else:
            with st.spinner("AI가 캡쳐를 분석 중입니다..."):
                try:
                    genai.configure(api_key=api_key.strip()); model=genai.GenerativeModel("gemini-2.5-flash")
                    img=Image.open(uploaded_file)
                    if img.mode!="RGB": img=img.convert("RGB")
                    img.thumbnail((800,800))
                    prompt='''한국 주식 증권사 앱 캡쳐 화면에서 종목명, 총 매수금액, 수익률(%)을 추출하세요. 반드시 JSON만 출력하세요. {"ticker":"두산퓨얼셀","buy_amount":2991450,"roi":0.04,"memo":"AI 스캔 완료"}'''
                    response=model.generate_content([prompt,img]); text=response.text.strip(); match=re.search(r"\{.*\}",text,re.DOTALL); data=json.loads(match.group(0) if match else text)
                    st.session_state["ai_ticker"]=str(data.get("ticker","")).strip(); st.session_state["ai_buy_amt"]=int(float(str(data.get("buy_amount",0)).replace(",","").replace("원","").strip() or 0))
                    st.session_state["ai_roi"]=float(str(data.get("roi",0)).replace(",","").replace("%","").strip() or 0); st.session_state["ai_memo"]=str(data.get("memo","📸 AI 분석 자동 입력"))
                    st.session_state["form_reset_trigger"]=st.session_state.get("form_reset_trigger",0)+1; st.success("✅ 분석 성공!")
                except Exception as e: st.error("🚨 이미지 분석에 실패했습니다."); st.write(str(e))

# ============================================================
# 14. NEW TRADE
# ============================================================
if "form_reset_trigger" not in st.session_state: st.session_state["form_reset_trigger"]=0
fc=st.session_state["form_reset_trigger"]; def_ticker=st.session_state.get("ai_ticker",""); def_buy=int(st.session_state.get("ai_buy_amt",0)); def_roi=float(st.session_state.get("ai_roi",0)); def_memo=st.session_state.get("ai_memo","")

st.sidebar.markdown("---"); st.sidebar.header("📝 매매 기록 입력")
with st.sidebar.form("quick_input",clear_on_submit=True):
    entry_date=st.date_input("매수 진입일",datetime.today().date(),key=f"entry_{fc}"); exit_date=st.date_input("매도 청산일",datetime.today().date(),key=f"exit_{fc}")
    ticker=st.text_input("종목명",value=def_ticker,key=f"ticker_{fc}").strip(); buy_amt=st.number_input("총 매수 금액 (원)",min_value=0,value=max(0,def_buy),step=100000,key=f"buy_{fc}")
    roi=st.number_input("수익률 (%)",value=def_roi,format="%.2f",key=f"roi_{fc}"); pn_l=buy_amt*roi/100; sell_amt=buy_amt+pn_l; holding=(exit_date-entry_date).days
    if exit_date>=entry_date: st.info(f"⏱️ 보유기간: **{holding}일**\n\n💰 손익: **{pn_l:+,.0f}원**")
    mistake_tags=st.multiselect("실수 태그 (해당 시 선택)",MISTAKE_OPTIONS,key=f"mistakes_{fc}")
    discipline=st.selectbox("매매 규율",DISCIPLINE_OPTIONS,index=1 if mistake_tags else 0,key=f"discipline_{fc}")
    emotion=st.selectbox("감정 상태",EMOTION_OPTIONS,key=f"emotion_{fc}"); memo=st.text_input("메모",value=def_memo,key=f"memo_{fc}")
    save=st.form_submit_button("💾 기록 저장",use_container_width=True)

    if save:
        if exit_date<entry_date: st.error("청산일은 진입일보다 빠를 수 없습니다.")
        elif not ticker: st.error("종목명을 입력해주세요.")
        elif buy_amt<=0: st.error("매수금액을 입력해주세요.")
        else:
            try:
                final_discipline="규칙 위반" if mistake_tags else discipline
                new=pd.DataFrame([{"Trade_ID":create_new_trade_id(),"Entry_Date":pd.Timestamp(entry_date),"Exit_Date":pd.Timestamp(exit_date),"Holding_Days":holding,"Ticker":ticker,"Buy_Amount":float(buy_amt),"Sell_Amount":float(sell_amt),"P_L_Amount":float(pn_l),"ROI_Percent":float(roi),"Mistake_Tags":" | ".join(mistake_tags),"Emotion":emotion,"Discipline":final_discipline,"Memo":memo}])
                raw=conn.read(worksheet=0,ttl=0); live=normalize_trade_dataframe(raw) if not raw.empty else pd.DataFrame(columns=REQUIRED_COLUMNS)
                updated=normalize_trade_dataframe(pd.concat([live,new],ignore_index=True)); conn.update(worksheet=0,data=prepare_for_sheet(updated))
                for k,v in [("ai_ticker",""),("ai_buy_amt",0),("ai_roi",0.0),("ai_memo","")]: st.session_state[k]=v
                st.session_state["form_reset_trigger"]+=1; st.success(f"✅ {ticker} 저장 완료!"); st.rerun()
            except Exception as e: st.error(f"🚨 거래 저장 실패: {e}")

st.sidebar.caption("⚠️ KRX 종목 리스트 로딩 실패" if krx_list.empty else f"✅ {len(krx_list):,}개 종목 연결됨")

# ============================================================
# 15. MAIN
# ============================================================
st.title("💎 Trading Master Dashboard")
if df.empty: st.info("👈 사이드바에서 매매 기록을 입력하면 대시보드가 활성화됩니다."); st.stop()

analysis_df=df.copy(); analysis_df["Year"]=analysis_df["Exit_Date"].dt.year; analysis_df["YearMonth"]=analysis_df["Exit_Date"].dt.strftime("%Y-%m")
tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8,tab9=st.tabs(["📊 차트","📅 월별","📆 연도별","📋 원본","⚖️ 빅터","🎯 R-배수","🔔 손익 분포","🛠️ 거래 관리","🧠 Trading DNA"])

# ============================================================
# TAB 1
# ============================================================
with tab1:
    st.subheader("🏆 전체 종합 성적표 (Total Legend)")
    m=calculate_period_metrics(analysis_df); total_pl=analysis_df["P_L_Amount"].sum(); wins=analysis_df[analysis_df["P_L_Amount"]>0]; losses=analysis_df[analysis_df["P_L_Amount"]<0]
    avg_profit=wins["P_L_Amount"].mean() if not wins.empty else 0; avg_loss=abs(losses["P_L_Amount"].mean()) if not losses.empty else 0; money_rr=avg_profit/avg_loss if avg_loss>0 else 0; wp=m["win_rate"]/100
    kelly=max(0,(wp-(1-wp)/money_rr)*100) if money_rr>0 else 0
    a,b,c,d,e=st.columns(5); a.metric("💰 누적 총 손익",f"{total_pl:,.0f}원"); b.metric("🎯 전체 승률",f"{m['win_rate']:.1f}%"); c.metric("🔮 기간 기댓값",f"{m['expectancy']:+.2f}%"); d.metric("💎 Profit Factor",f"{m['profit_factor']:.2f}"); e.metric("⚖️ 켈리 베팅 비중",f"{kelly:.1f}%")
    a,b,c,d=st.columns(4); a.metric("평균 수익금",f"{avg_profit:,.0f}원"); b.metric("평균 손실금",f"{avg_loss:,.0f}원"); c.metric("금액 손익비",f"{money_rr:.2f}"); d.metric("총 매수 대금",f"{analysis_df['Buy_Amount'].sum():,.0f}원")
    a,b,c,d=st.columns(4); a.metric("평균 수익률",f"+{m['avg_win_pct']:.2f}%"); b.metric("평균 손실률",f"-{m['avg_loss_pct']:.2f}%"); c.metric("기간 손익비",f"{m['reward_risk']:.2f}"); d.metric("총 거래 횟수",f"{m['count']}회")
    st.divider(); st.subheader("🚀 내 계좌 누적 손익")
    daily=analysis_df.groupby("Exit_Date")["P_L_Amount"].sum().reset_index().sort_values("Exit_Date"); daily["Cumulative"]=daily["P_L_Amount"].cumsum(); st.line_chart(daily.set_index("Exit_Date")["Cumulative"])
    st.subheader("📊 월별 손익 흐름"); st.bar_chart(analysis_df.groupby("YearMonth")["P_L_Amount"].sum())

# ============================================================
# TAB 2 / 3
# ============================================================
with tab2:
    st.subheader("📅 월별 상세 성적표"); rows=[]
    for ym,g in analysis_df.groupby("YearMonth"):
        x=calculate_period_metrics(g); w=g[g["P_L_Amount"]>0]; l=g[g["P_L_Amount"]<0]
        rows.append({"기간":ym,"총 손익":g["P_L_Amount"].sum(),"평균수익":w["P_L_Amount"].mean() if not w.empty else 0,"평균손실":l["P_L_Amount"].mean() if not l.empty else 0,"거래횟수":len(g),"승률":x["win_rate"],"손익비":x["reward_risk"],"PF":x["profit_factor"],"기대수익":x["expectancy"],"매수총액":g["Buy_Amount"].sum()})
    table=pd.DataFrame(rows).sort_values("기간",ascending=False); st.dataframe(table.style.format({"총 손익":"{:+,.0f}원","평균수익":"{:,.0f}원","평균손실":"{:,.0f}원","승률":"{:.1f}%","손익비":"{:.2f}","PF":"{:.2f}","기대수익":"{:+.2f}%","매수총액":"{:,.0f}원"}),use_container_width=True)

with tab3:
    st.subheader("📆 연도별 종합 성적표"); rows=[]
    for year,g in analysis_df.groupby("Year"):
        x=calculate_period_metrics(g); w=g[g["P_L_Amount"]>0]; l=g[g["P_L_Amount"]<0]
        rows.append({"연도":int(year),"총 손익":g["P_L_Amount"].sum(),"평균수익":w["P_L_Amount"].mean() if not w.empty else 0,"평균손실":l["P_L_Amount"].mean() if not l.empty else 0,"거래횟수":len(g),"승률":x["win_rate"],"손익비":x["reward_risk"],"PF":x["profit_factor"],"기대수익":x["expectancy"],"매수총액":g["Buy_Amount"].sum()})
    table=pd.DataFrame(rows).sort_values("연도",ascending=False); st.dataframe(table.style.format({"총 손익":"{:+,.0f}원","평균수익":"{:,.0f}원","평균손실":"{:,.0f}원","승률":"{:.1f}%","손익비":"{:.2f}","PF":"{:.2f}","기대수익":"{:+.2f}%","매수총액":"{:,.0f}원"}),use_container_width=True)

# ============================================================
# TAB 4
# ============================================================
with tab4:
    st.subheader("📋 전체 거래 기록")
    cols=["Entry_Date","Exit_Date","Holding_Days","Ticker","Buy_Amount","Sell_Amount","P_L_Amount","ROI_Percent","Mistake_Tags","Discipline","Emotion","Memo"]
    table=analysis_df.sort_values("Exit_Date",ascending=False)[cols].copy()
    st.dataframe(table.style.format({"Holding_Days":lambda x:"-" if pd.isna(x) else f"{x:.0f}일","Buy_Amount":"{:,.0f}원","Sell_Amount":"{:,.0f}원","P_L_Amount":"{:+,.0f}원","ROI_Percent":"{:+.2f}%"}),use_container_width=True)

# ============================================================
# TAB 5
# ============================================================
with tab5:
    st.subheader("⚖️ Victor Sperandeo Reward-to-Risk Analysis"); st.markdown("**목표 기준: 평균 수익 / 평균 손실 = 3 : 1**")
    period=st.radio("📅 분석 기간",["전체","최근 1개월","최근 3개월","최근 6개월","최근 1년"],horizontal=True,key="vic_period"); vdf=analysis_df.copy(); days={"최근 1개월":30,"최근 3개월":90,"최근 6개월":180,"최근 1년":365}
    if period in days: vdf=vdf[vdf["Exit_Date"]>=pd.Timestamp.today().normalize()-timedelta(days=days[period])]
    if not vdf.empty:
        vm=calculate_period_metrics(vdf); a,b,c=st.columns(3); a.metric("기간 손익비",f"{vm['reward_risk']:.2f} : 1"); b.metric("기간 기댓값",f"{vm['expectancy']:+.2f}%"); c.metric("목표 기준","3.0 : 1")
        target=vm["avg_loss_pct"]*3 if vm["avg_loss_pct"]>0 else 10; chart=vdf.copy(); chart["Color_Hex"]=np.select([chart["ROI_Percent"]>=target,chart["ROI_Percent"]>0],["#00CC00","#F1C40F"],default="#FF4B4B")
        scatter=alt.Chart(chart).mark_circle(size=100).encode(x="Exit_Date:T",y="ROI_Percent:Q",color=alt.Color("Color_Hex:N",scale=None,legend=None),tooltip=["Ticker","Entry_Date","Exit_Date","Holding_Days","ROI_Percent","P_L_Amount"]).interactive()
        rule=alt.Chart(pd.DataFrame({"Target":[target]})).mark_rule(color="blue",strokeDash=[3,3]).encode(y="Target:Q"); st.altair_chart(scatter+rule,use_container_width=True)

# ============================================================
# TAB 6
# ============================================================
with tab6:
    st.subheader("🎯 R-배수 분석"); st.caption("1R = 선택 기간의 평균 손실금")
    period=st.radio("📅 분석 기간",["전체","최근 1개월","최근 3개월","최근 6개월","최근 1년"],horizontal=True,key="r_period"); rdf=analysis_df.copy(); days={"최근 1개월":30,"최근 3개월":90,"최근 6개월":180,"최근 1년":365}
    if period in days: rdf=rdf[rdf["Exit_Date"]>=pd.Timestamp.today().normalize()-timedelta(days=days[period])]
    if not rdf.empty:
        losses=rdf[rdf["P_L_Amount"]<0]; one_r=abs(losses["P_L_Amount"].mean()) if not losses.empty else 1
        if pd.isna(one_r) or one_r<=0: one_r=1
        rdf=rdf.copy(); rdf["R_Value"]=rdf["P_L_Amount"]/one_r; a,b,c=st.columns(3); a.metric("나의 1R",f"{one_r:,.0f}원"); b.metric("평균 R-배수",f"{rdf['R_Value'].mean():.2f}R"); c.metric("최고 R-배수",f"{rdf['R_Value'].max():.2f}R")
        rdf=rdf.sort_values("Exit_Date"); rdf["Cumulative_R"]=rdf["R_Value"].cumsum(); rdf["Trade_Num"]=range(1,len(rdf)+1); st.line_chart(rdf.set_index("Trade_Num")["Cumulative_R"])

# ============================================================
# TAB 7
# ============================================================
with tab7:
    st.subheader("🔔 손익 분포")
    histogram=alt.Chart(analysis_df).mark_bar().encode(x=alt.X("ROI_Percent:Q",bin=alt.Bin(step=2.5)),y="count():Q",color=alt.condition(alt.datum.ROI_Percent>0,alt.value("#00AA00"),alt.value("#FF4444"))).properties(height=400)
    st.altair_chart(histogram,use_container_width=True); skew=analysis_df["ROI_Percent"].skew(); st.info(f"📊 Skewness: {0 if pd.isna(skew) else skew:.2f}")

# ============================================================
# TAB 8 - MANAGEMENT
# ============================================================
with tab8:
    st.subheader("🛠️ 거래 관리")
    manage=analysis_df.sort_values(["Exit_Date","Trade_ID"],ascending=[False,False]).copy()
    manage["Display_Name"]=manage["Exit_Date"].dt.strftime("%Y-%m-%d")+" | "+manage["Ticker"].astype(str)+" | "+manage["ROI_Percent"].map(lambda x:f"{x:+.2f}%")+" | "+manage["P_L_Amount"].map(lambda x:f"{x:+,.0f}원")
    display=dict(zip(manage["Trade_ID"].astype(str),manage["Display_Name"])); tid=st.selectbox("📋 수정/삭제할 거래 선택",options=list(display.keys()),format_func=lambda x:display.get(x,x))
    rows=manage[manage["Trade_ID"].astype(str)==str(tid)]

    if not rows.empty:
        s=rows.iloc[0]; a,b,c,d=st.columns(4); a.metric("종목",s["Ticker"]); b.metric("청산일",s["Exit_Date"].strftime("%Y-%m-%d")); c.metric("보유일수","-" if pd.isna(s["Holding_Days"]) else f"{s['Holding_Days']:.0f}일"); d.metric("손익",f"{s['P_L_Amount']:+,.0f}원")
        st.divider(); st.markdown("### ✏️ 거래 수정")

        current_tags=[t.strip() for t in re.split(r"[,|;/]",str(s["Mistake_Tags"])) if t.strip()]; valid_tags=[t for t in current_tags if t in MISTAKE_OPTIONS]
        has_entry_original=pd.notna(s["Entry_Date"])

        with st.form(f"edit_{tid}"):
            use_entry=st.checkbox("진입일 정보 입력",value=has_entry_original,help="과거 거래의 실제 진입일을 모르면 체크하지 마세요.")
            e_entry=None
            if use_entry:
                default_entry=s["Entry_Date"].date() if has_entry_original else s["Exit_Date"].date()
                e_entry=st.date_input("매수 진입일",value=default_entry)
            else: st.caption("진입일 미입력 상태로 유지됩니다. 보유기간 분석에서는 제외됩니다.")

            e_exit=st.date_input("매도 청산일",value=s["Exit_Date"].date()); e_ticker=st.text_input("종목명",value=str(s["Ticker"]))
            e_buy=st.number_input("매수금액",min_value=0,value=int(round(s["Buy_Amount"])),step=100000); e_roi=st.number_input("수익률 (%)",value=float(s["ROI_Percent"]),format="%.2f")
            e_tags=st.multiselect("실수 태그",MISTAKE_OPTIONS,default=valid_tags); default_disc=1 if str(s["Discipline"])=="규칙 위반" or valid_tags else 0
            e_disc=st.selectbox("매매 규율",DISCIPLINE_OPTIONS,index=default_disc); old_emotion=str(s["Emotion"]); e_emotion=st.selectbox("감정 상태",EMOTION_OPTIONS,index=EMOTION_OPTIONS.index(old_emotion) if old_emotion in EMOTION_OPTIONS else 0)
            e_memo=st.text_area("메모",value=str(s["Memo"])); update_clicked=st.form_submit_button("💾 수정 내용 저장",use_container_width=True)

            if update_clicked:
                if use_entry and e_entry is not None and e_exit<e_entry: st.error("청산일은 진입일보다 빠를 수 없습니다.")
                elif not e_ticker.strip(): st.error("종목명을 입력해주세요.")
                else:
                    try:
                        live=normalize_trade_dataframe(conn.read(worksheet=0,ttl=0)); mask=live["Trade_ID"].astype(str)==str(tid)
                        if not mask.any(): st.error("거래를 찾을 수 없습니다.")
                        else:
                            i=live[mask].index[0]; pl=e_buy*e_roi/100
                            live.at[i,"Entry_Date"]=pd.Timestamp(e_entry) if use_entry and e_entry is not None else pd.NaT
                            live.at[i,"Exit_Date"]=pd.Timestamp(e_exit); live.at[i,"Holding_Days"]=(e_exit-e_entry).days if use_entry and e_entry is not None else np.nan
                            live.at[i,"Ticker"]=e_ticker.strip(); live.at[i,"Buy_Amount"]=float(e_buy); live.at[i,"ROI_Percent"]=float(e_roi); live.at[i,"P_L_Amount"]=float(pl); live.at[i,"Sell_Amount"]=float(e_buy+pl)
                            live.at[i,"Mistake_Tags"]=" | ".join(e_tags); live.at[i,"Discipline"]="규칙 위반" if e_tags else e_disc; live.at[i,"Emotion"]=e_emotion; live.at[i,"Memo"]=e_memo
                            conn.update(worksheet=0,data=prepare_for_sheet(live)); st.success("✅ 거래 수정 완료!"); st.rerun()
                    except Exception as e: st.error(f"수정 실패: {e}")

        st.divider(); confirm=st.checkbox("이 거래를 정말 삭제하겠습니다.")
        if st.button("🗑️ 거래 영구 삭제",disabled=not confirm,use_container_width=True):
            try:
                live=normalize_trade_dataframe(conn.read(worksheet=0,ttl=0)); live=live[live["Trade_ID"].astype(str)!=str(tid)].copy()
                conn.update(worksheet=0,data=prepare_for_sheet(live)); st.success("🗑️ 거래 삭제 완료!"); st.rerun()
            except Exception as e: st.error(f"삭제 실패: {e}")

# ============================================================
# TAB 9 - TRADING DNA
# ============================================================
with tab9:
    st.subheader("🧠 My Trading DNA"); st.caption("장기 Trading DNA, 보유기간, 실수 비용과 최근 Edge 변화를 실제 거래 기록으로 추적합니다.")
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
    a,b,c,d=st.columns(4); a.metric("보유기간 데이터",f"{holding['valid_count']}/{len(analysis_df)}건",f"{holding['coverage']:.1f}%")
    b.metric("수익거래 평균 보유","-" if holding["avg_wins"] is None else f"{holding['avg_wins']:.1f}일"); c.metric("손실거래 평균 보유","-" if holding["avg_losses"] is None else f"{holding['avg_losses']:.1f}일"); d.metric("Big Winner 평균 보유","-" if holding["avg_big"] is None else f"{holding['avg_big']:.1f}일")
    st.caption("보유일수는 달력일 기준이며, 실제 진입일이 없는 기존 거래는 분석에서 제외됩니다.")

    if holding["valid_count"]==0: st.info("기존 거래는 진입일 정보가 없으면 보유기간 분석에서 제외됩니다. 거래 관리에서 실제 진입일을 추가하거나 앞으로 입력되는 거래부터 자동 축적됩니다.")
    else:
        hb=create_holding_bucket_table(analysis_df)
        if not hb.empty: st.dataframe(hb.style.format({"거래수":"{:.0f}건","승률":"{:.1f}%","PF":"{:.2f}","기대값":"{:+.2f}%","평균수익률":"{:+.2f}%","총손익":"{:+,.0f}원"}),use_container_width=True,hide_index=True)
        if holding["avg_wins"] is not None and holding["avg_losses"] is not None:
            if holding["avg_losses"]>holding["avg_wins"]: st.warning(f"⏱️ 기록상 손실 거래 평균 보유기간({holding['avg_losses']:.1f}일)이 수익 거래({holding['avg_wins']:.1f}일)보다 깁니다.")
            else: st.info(f"⏱️ 기록상 수익 거래 평균 보유기간({holding['avg_wins']:.1f}일)이 손실 거래({holding['avg_losses']:.1f}일)보다 깁니다.")

    st.divider(); st.markdown("### 💸 Mistake Cost Engine")
    st.caption("Mistake Cost는 '실수를 안 했으면 벌었을 돈'이 아니라, 실수/규칙위반 태그가 붙은 거래에서 실제 발생한 손익을 집계합니다.")
    a,b,c,d=st.columns(4); a.metric("🚨 규칙 위반 거래",f"{mc['violation_count']}건",f"{mc['violation_rate']:.1f}%"); b.metric("💸 위반 거래 실제 손익",f"{mc['violation_pl']:+,.0f}원"); c.metric("✅ 정상 거래 PF",f"{mc['normal_metrics']['profit_factor']:.2f}"); d.metric("⚠️ 위반 거래 PF",f"{mc['violation_metrics']['profit_factor']:.2f}")

    if mc["violation_count"]>0:
        a,b,c,d=st.columns(4); a.metric("정상 거래수",f"{mc['normal_count']}건"); b.metric("정상 거래 손익",f"{mc['normal_pl']:+,.0f}원"); c.metric("최근 20 위반 비율",f"{mc['recent_violation_rate']:.1f}%"); d.metric("직전 대비",f"{mc['change_violation_rate']:+.1f}%p" if mc["previous_violation_rate"]>0 else "-")
        if not mc["tag_table"].empty:
            st.markdown("#### 🧾 실수 유형별 실제 성과")
            st.dataframe(mc["tag_table"].style.format({"발생횟수":"{:.0f}회","실제손익":"{:+,.0f}원","평균수익률":"{:+.2f}%"}),use_container_width=True,hide_index=True)
            mistake_chart=alt.Chart(mc["tag_table"]).mark_bar().encode(x=alt.X("실수:N",sort="-y"),y="실제손익:Q",color=alt.condition(alt.datum.실제손익>=0,alt.value("#00AA00"),alt.value("#FF4444")),tooltip=["실수","발생횟수","실제손익","평균수익률"]).properties(height=350)
            st.altair_chart(mistake_chart,use_container_width=True)

    st.markdown("#### 🧠 Mistake Coach")
    for x in generate_mistake_insights(mc): st.markdown(f"- {x}")

    st.divider(); st.markdown("### 🛡️ Risk DNA")
    a,b,c,d=st.columns(4); a.metric("평균 손실률",f"-{dna['avg_loss_pct']:.2f}%"); b.metric("최대 손실률",f"-{dna['max_loss_pct']:.2f}%"); c.metric("최대 연속 손실",f"{dna['max_loss_streak']}회"); d.metric("최대 연속 수익",f"{dna['max_win_streak']}회")

    st.divider(); st.markdown("### 📡 Edge Change Detection"); st.markdown(f"## {dna['edge_icon']} 현재 Edge 상태: **{dna['edge_status']}**")
    recent=dna["recent_metrics"]; a,b,c,d=st.columns(4)
    a.metric("최근 20 승률",f"{recent['win_rate']:.1f}%",f"{dna['changes']['win_rate']:+.1f}%p" if dna["has_previous"] else None); b.metric("최근 20 PF",f"{recent['profit_factor']:.2f}",f"{dna['changes']['profit_factor']:+.2f}" if dna["has_previous"] else None)
    c.metric("최근 20 손익비",f"{recent['reward_risk']:.2f}",f"{dna['changes']['reward_risk']:+.2f}" if dna["has_previous"] else None); d.metric("최근 20 기대값",f"{recent['expectancy']:+.2f}%",f"{dna['changes']['expectancy']:+.2f}%p" if dna["has_previous"] else None)

    st.markdown("#### 🔬 전체 vs 직전 20 vs 최근 20")
    if dna["has_previous"]: st.dataframe(create_edge_comparison_table(dna).style.format({"전체":"{:.2f}","직전 20":"{:.2f}","최근 20":"{:.2f}","변화":"{:+.2f}"}),use_container_width=True,hide_index=True)
    else: st.info("직전 구간과 안정적으로 비교하려면 최소 25~40건 정도의 거래 기록을 권장합니다.")

    st.markdown("### 🔍 Edge 변화 원인"); drivers=detect_edge_drivers(dna)
    if drivers:
        for x in drivers:
            if x["direction"]=="positive": st.success("📈 "+x["text"])
            else: st.warning("📉 "+x["text"])
    else: st.info("현재 구간에서는 뚜렷한 Edge 변화 원인이 감지되지 않았습니다.")

    st.divider(); st.markdown("### 📊 어디에서 돈을 벌고 잃는가?")
    buckets=create_roi_bucket_table(analysis_df)
    if not buckets.empty:
        chart=alt.Chart(buckets).mark_bar().encode(x=alt.X("수익률 구간:N",sort=None),y="총손익:Q",color=alt.condition(alt.datum.총손익>0,alt.value("#00AA00"),alt.value("#FF4444")),tooltip=["수익률 구간","거래수","총손익","평균수익률"]).properties(height=380)
        st.altair_chart(chart,use_container_width=True); st.dataframe(buckets.style.format({"거래수":"{:,.0f}건","총손익":"{:+,.0f}원","평균수익률":"{:+.2f}%"}),use_container_width=True,hide_index=True)

    st.divider(); st.markdown("### 🧠 Trading Coach Insights")
    for x in generate_rule_based_insights(dna): st.markdown(f"- {x}")

    st.markdown("### 🎯 다음 거래 체크포인트"); checkpoints=generate_coach_checkpoints(dna)
    for i,x in enumerate(checkpoints,1): st.markdown(f"**{i}.** {x}")

    st.divider(); st.markdown("### 🤖 AI Trading Coach"); st.caption("Python이 실제 거래 통계를 계산하고 AI는 계산된 숫자만 해석합니다.")
    if not api_key: st.info("👈 사이드바의 Gemini API Key를 입력하면 AI Coach를 사용할 수 있습니다.")
    else:
        if st.button("🧠 내 Trading DNA AI 분석",use_container_width=True,type="primary"):
            with st.spinner("AI Coach가 Trading DNA를 분석 중입니다..."):
                try: st.session_state["ai_coach_report"]=run_ai_coach(api_key,dna,checkpoints,drivers,holding,mc)
                except Exception as e: st.error("🚨 AI Coach 분석에 실패했습니다."); st.write(str(e))
        if st.session_state.get("ai_coach_report"): st.success("✅ AI Coach 분석 완료"); st.markdown(st.session_state["ai_coach_report"])

    st.caption("⚠️ Trading Coach는 투자 추천이 아니라 본인의 매매 기록과 행동을 복기하기 위한 분석 도구입니다.")
