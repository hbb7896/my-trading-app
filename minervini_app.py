import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import altair as alt
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# 1. 페이지 설정
st.set_page_config(page_title="Trading Master Dashboard", page_icon="💎", layout="wide")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 설정값 불러오기 ---
@st.cache_data(ttl=0)
def load_settings():
    try:
        df = conn.read(worksheet=1, ttl=0)
        if not df.empty: return df.iloc[0].to_dict()
    except: pass
    return {}

saved_config = load_settings()

# --- 한국 종목 리스트 ---
@st.cache_data(ttl=3600)
def get_krx_list():
    try:
        df = fdr.StockListing('KRX')
        return df[['Code', 'Name', 'Market']]
    except Exception as e:
        return pd.DataFrame()

# --- PF 가이드 ---
def show_pf_guide():
    with st.expander("ℹ️ 마크 미너비니의 PF(프로핏 팩터) 점수표 보기", expanded=False):
        st.markdown("""
        | PF 범위 | 상태 | 평가 |
        | :--- | :--- | :--- |
        | **1.0 이하** | 🚨 위험 | 손실이 더 큰 상태 |
        | **1.5 ~ 2.0** | 👍 훌륭함 | 안정적 수익 구간 |
        | **3.0 이상** | 💎 전설 | 초고수 (Legendary) |
        """)

def load_data():
    try:
        df = conn.read(worksheet=0, ttl=0)
        if df.empty:
             return pd.DataFrame(columns=['Date', 'Ticker', 'Buy_Amount', 'Sell_Amount', 'P_L_Amount', 'ROI_Percent', 'Mistake_Tags', 'Emotion', 'Discipline', 'Memo'])
        
        df = df.dropna(subset=['Date'])
        
        # 숫자 변환
        num_cols = ['P_L_Amount', 'ROI_Percent', 'Buy_Amount', 'Sell_Amount']
        for col in num_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        # 데이터 복구 및 초기화
        if 'Buy_Amount' not in df.columns: df['Buy_Amount'] = 0.0
        if 'Sell_Amount' not in df.columns: df['Sell_Amount'] = 0.0
        
        mask = (df['Buy_Amount'] == 0) & (df['ROI_Percent'] != 0)
        df.loc[mask, 'Buy_Amount'] = (df.loc[mask, 'P_L_Amount'] / (df.loc[mask, 'ROI_Percent'] / 100)).abs()
        df.loc[mask, 'Sell_Amount'] = df.loc[mask, 'Buy_Amount'] + df.loc[mask, 'P_L_Amount']

        if 'Mistake_Tags' not in df.columns: df['Mistake_Tags'] = None
        if 'Emotion' not in df.columns: df['Emotion'] = None
        if 'Discipline' not in df.columns: df['Discipline'] = None
        
        return df
    except:
        return pd.DataFrame(columns=['Date', 'Ticker', 'Buy_Amount', 'Sell_Amount', 'P_L_Amount', 'ROI_Percent', 'Mistake_Tags', 'Emotion', 'Discipline', 'Memo'])

df = load_data()
krx_list = get_krx_list() 

# --- 사이드바 입력 ---
st.sidebar.header("📝 매매 기록 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("일자", datetime.today())
    ticker = st.text_input("종목명 (예: 삼성전자)").strip()
    buy_amt = st.number_input("총 매수 금액 (원)", value=0, step=100000)
    pn_l = st.number_input("실현 손익금 (원)", value=0, step=10000)
    roi = st.number_input("수익률 (%)", value=0.0, format="%.2f")
    
    if buy_amt != 0:
        st.caption(f"💡 예상 매도 금액: {buy_amt + pn_l:,.0f}원")
    
    st.divider()
    st.caption("🧠 습관 분석")
    mistake_options = ["정상매매", "뇌동매매", "추격매수", "손절늦음", "익절너무빠름", "시장하락", "비중위반"]
    tags = st.multiselect("매매 특이사항", mistake_options, default=["정상매매"])
    tags_str = ", ".join(tags)
    emotion = st.selectbox("매수 당시 감정", ["평온함", "흥분/조급함(FOMO)", "공포", "복수심(화남)", "지루함"])
    discipline = st.radio("원칙을 지켰습니까?", ["Yes (잘한 매매)", "No (반성 필요)"], horizontal=True)
    memo = st.text_input("메모")
    
    if st.form_submit_button("기록 저장"):
        if ticker:
            sell_amt = buy_amt + pn_l
            new_data = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'), 'Ticker': ticker, 'Buy_Amount': buy_amt, 'Sell_Amount': sell_amt,
                'P_L_Amount': pn_l, 'ROI_Percent': roi, 'Mistake_Tags': tags_str, 'Emotion': emotion, 'Discipline': discipline, 'Memo': memo
            }])
            if df.empty: updated_df = new_data
            else:
                df_temp = load_data()
                df_temp['Date'] = df_temp['Date'].dt.strftime('%Y-%m-%d')
                updated_df = pd.concat([df_temp, new_data], ignore_index=True)
            conn.update(worksheet=0, data=updated_df)
            st.success(f"✅ {ticker} 저장 완료!"); st.rerun()
        else: st.error("종목명을 입력해주세요.")

if krx_list.empty: st.sidebar.caption("⚠️ 리스트 로딩 실패")
else: st.sidebar.caption(f"✅ {len(krx_list):,}개 종목 연결됨")

# --- 메인 화면 ---
st.title("💎 Trading Master Dashboard")

if not df.empty
