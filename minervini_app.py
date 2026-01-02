import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
import altair as alt
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# 1. 페이지 설정
st.set_page_config(page_title="Minervini Master Dashboard", page_icon="💎", layout="wide")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# 한국 종목 리스트 가져오기 (캐시 처리로 속도 향상)
@st.cache_data(ttl=86400)
def get_krx_list():
    return fdr.StockListing('KRX')[['Code', 'Name', 'Market']]

def load_data():
    try:
        df = conn.read(worksheet=0, ttl=0)
        if df.empty:
             return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])
        df = df.dropna(subset=['Date'])
        df['P_L_Amount'] = pd.to_numeric(df['P_L_Amount'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['ROI_Percent'] = pd.to_numeric(df['ROI_Percent'].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        return df
    except:
        return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])

df = load_data()
krx_list = get_krx_list()

# 이름으로 티커 찾는 함수
def find_ticker(name):
    target = krx_list[krx_list['Name'] == name]
    if not target.empty:
        code = target.iloc[0]['Code']
        market = target.iloc[0]['Market']
        suffix = ".KS" if market == 'KOSPI' else ".KQ"
        return code + suffix
    return name

# --- [사이드바] 입력 ---
with st.sidebar.form("input_form", clear_on_submit=True):
    st.header("📝 매매 기록 입력")
    date = st.date_input("일자", datetime.today())
    ticker_name = st.text_input("종목명 (예: 삼성전자)").strip()
    pn_l = st.number_input("손익금 (원)", value=0)
    roi = st.number_input("수익률 (%)", value=0.0, format="%.2f")
    memo = st.text_area("매매 복기")
    if st.form_submit_button("저장"):
        new_data = pd.DataFrame([{'Date': date.strftime('%Y-%m-%d'), 'Ticker': ticker_name, 'P_L_Amount': pn_l, 'ROI_Percent': roi, 'Memo': memo}])
        conn.update(worksheet=0, data=pd.concat([load_data(), new_data], ignore_index=True))
        st.success("저장되었습니다!"); st.rerun()

# --- [메인 화면] ---
st.title("💎 Trading Master Dashboard")

if not df.empty:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 차트 대시보드", "📅 월별 분석", "📆 연도별 분석", "📋 데이터 원본", "❌ 오답 노트"])
    
    with tab1:
        # 지표 요약
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("총 누적 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        kpi2.metric("승률", f"{(len(df[df['ROI_Percent']>0])/len(df))*100:.1f}%")
        kpi3.metric("평균 수익률", f"{df['ROI_Percent'].mean():.2f}%")
        
        st.divider()
        st.subheader("🚀 내 계좌 vs KOSPI 지수")
        
        # 내 자산 데이터 (날짜별 합산)
        daily_df = df.groupby('Date')['P_L_Amount'].sum().reset_index().sort_values('Date')
        daily_df['Cumulative'] = daily_df['P_L_Amount'].cumsum()
        
        # [수정] KOSPI 지수 데이터 (FinanceDataReader 사용으로 안정성 확보)
        try:
            start_date = daily_df['Date'].min().strftime('%Y-%m-%d')
            kospi_df = fdr.DataReader('KS11', start_date).reset_index()
            kospi_df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
            
            base = alt.Chart(daily_df).encode(x='Date:T')
            my_chart = base.mark_area(opacity=0.3, color='green').encode(y=alt.Y('Cumulative:Q', title='내 수익'), tooltip=['Date', 'Cumulative'])
            
            market_chart = alt.Chart(kospi_df).mark_line(color='red').encode(
                x='Date:T', 
                y=alt.Y('Close:Q', title='KOSPI 지수', scale=alt.Scale(zero=False)),
                tooltip=['Date', 'Close']
            )
            st.altair_chart(alt.layer(my_chart, market_chart).resolve_scale(y='independent'), use_container_width=True)
        except:
            st.line_chart(daily_df.set_index('Date')['Cumulative'])

    # 오답 노트 탭
    with tab5:
        st.subheader("🚩 실패한 매매 분석 (오답 노트)")
        failed = df[df['ROI_Percent'] < 0].sort_values('Date', ascending=False)
        if not failed.empty:
            col_l, col_r = st.columns([1, 2])
            with col_l:
                sel_name = st.selectbox("종목 선택", failed['Ticker'].unique())
                st.table(failed[failed['Ticker'] == sel_name][['Date', 'ROI_Percent', 'P_L_Amount']])
                st.info(f"메모: {failed[failed['Ticker'] == sel_name].iloc[0]['Memo']}")
            with col_r:
                t_code = find_ticker(sel_name)
                st.write(f"🔍 {sel_name} ({t_code}) 차트")
                chart_data = yf.download(t_code, start=(datetime.today()-timedelta(days=180)), progress=False)
                if not chart_data.empty: st.line_chart(chart_data['Close'], color="#FF4B4B")
        else:
            st.success("손실 기록이 없습니다!")
