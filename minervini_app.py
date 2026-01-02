import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
import altair as alt
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# 1. 페이지 설정
st.set_page_config(page_title="Minervini Master Dashboard", page_icon="💎", layout="wide")

# 2. 구글 시트 및 데이터 로드 설정
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=3600) # 종목 리스트는 1시간마다 업데이트
def get_krx_list():
    df_krx = fdr.StockListing('KRX') # 코스피, 코스닥, 코넥스 전체
    return df_krx[['Code', 'Name', 'Market']]

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

# 데이터 불러오기
df = load_data()
krx_list = get_krx_list()

# --- [함수] 종목명으로 티커 찾기 ---
def find_ticker(name):
    # 1. KRX 리스트에서 이름 검색
    target = krx_list[krx_list['Name'] == name]
    if not target.empty:
        code = target.iloc[0]['Code']
        market = target.iloc[0]['Market']
        suffix = ".KS" if market == 'KOSPI' else ".KQ"
        return code + suffix
    return name # 못 찾으면 입력한 그대로 반환 (미국 주식 등)

# --- [사이드바] 입력 양식 ---
with st.sidebar.form("quick_input", clear_on_submit=True):
    st.header("📝 매매 기록 입력")
    date = st.date_input("일자", datetime.today())
    ticker_input = st.text_input("종목명 (예: 삼성전자)").strip()
    pn_l = st.number_input("손익금 (원)", value=0)
    roi = st.number_input("수익률 (%)", value=0.0, format="%.2f")
    memo = st.text_area("매매 복기 (미너비니 스타일)")
    submit = st.form_submit_button("기록 저장")
    
    if submit and ticker_input:
        new_data = pd.DataFrame([{
            'Date': date.strftime('%Y-%m-%d'), 
            'Ticker': ticker_input, 
            'P_L_Amount': pn_l, 
            'ROI_Percent': roi, 
            'Memo': memo
        }])
        updated_df = pd.concat([load_data(), new_data], ignore_index=True)
        conn.update(worksheet=0, data=updated_df)
        st.success("저장 완료!")
        st.rerun()

# --- [메인 화면] ---
st.title("💎 Trading Master Dashboard")

if not df.empty:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 차트 대시보드", "📅 월별 분석", "📆 연도별 분석", "📋 데이터 원본", "❌ 오답 노트"])
    
    # 공통 데이터 처리 (날짜별 합산으로 그래프 꼬임 방지)
    daily_df = df.groupby('Date')['P_L_Amount'].sum().reset_index().sort_values('Date')
    daily_df['Cumulative'] = daily_df['P_L_Amount'].cumsum()
    
    # --- TAB 1: 차트 대시보드 (KOSPI 연동 강화) ---
    with tab1:
        # 지표 계산
        avg_roi = df['ROI_Percent'].mean()
        wins = df[df['ROI_Percent'] > 0]
        losses = df[df['ROI_Percent'] <= 0]
        rr_ratio = (wins['ROI_Percent'].mean() / abs(losses['ROI_Percent'].mean())) if not losses.empty else 0
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("총 누적 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        kpi2.metric("승률", f"{(len(wins)/len(df))*100:.1f}%")
        kpi3.metric("평균 수익률", f"{avg_roi:.2f}%")
        kpi4.metric("평균 손익비", f"{rr_ratio:.2f}")

        st.divider()
        st.subheader("🚀 내 계좌 vs KOSPI 지수")
        
        try:
            # KOSPI 데이터 호출 안정화
            kospi_data = yf.download("^KS11", start=daily_df['Date'].min(), progress=False)
            if not kospi_data.empty:
                kospi_df = kospi_data[['Close']].reset_index()
                kospi_df.columns = ['Date', 'KOSPI']
                kospi_df['Date'] = pd.to_datetime(kospi_df['Date']).dt.tz_localize(None)
                
                # 이중 축 차트 구성
                base = alt.Chart(daily_df).encode(x='Date:T')
                line1 = base.mark_area(opacity=0.3, color='green').encode(
                    y=alt.Y('Cumulative:Q', title='내 수익 (원)'),
                    tooltip=['Date', 'Cumulative']
                )
                
                line2 = alt.Chart(kospi_df).mark_line(color='red').encode(
                    x='Date:T',
                    y=alt.Y('KOSPI:Q', title='KOSPI 지수', scale=alt.Scale(zero=False)),
                    tooltip=['Date', 'KOSPI']
                )
                
                st.altair_chart(alt.layer(line1, line2).resolve_scale(y='independent'), use_container_width=True)
            else:
                st.line_chart(daily_df.set_index('Date')['Cumulative'])
        except:
            st.line_chart(daily_df.set_index('Date')['Cumulative'])

    # (중간 탭들은 기존 로직 유지...)

    # --- TAB 5: 오답 노트 (자동 종목코드 찾기 포함) ---
    with tab5:
        st.subheader("🚩 실패한 매매 집중 분석")
        failed_trades = df[df['ROI_Percent'] < 0].sort_values('Date', ascending=False)
        
        if not failed_trades.empty:
            col1, col2 = st.columns([1, 2])
            with col1:
                selected_name = st.selectbox("분석할 종목 선택", failed_trades['Ticker'].unique())
                ticker_detail = failed_trades[failed_trades['Ticker'] == selected_name]
                st.table(ticker_detail[['Date', 'ROI_Percent', 'P_L_Amount']])
                st.warning(f"**복기 메모:**\n{ticker_detail.iloc[0]['Memo']}")
            
            with col2:
                # 여기서 마법이 일어납니다: 이름 -> 코드 변환
                real_ticker = find_ticker(selected_name)
                st.write(f"🔍 {selected_name} ({real_ticker}) 차트 분석")
                
                chart_hist = yf.download(real_ticker, start=(datetime.today() - timedelta(days=180)), progress=False)
                if not chart_hist.empty:
                    st.line_chart(chart_hist['Close'], color="#FF4B4B")
                    st.caption("차트를 보며 VCP 패턴과 손절 지점을 복기하세요.")
                else:
                    st.error("차트를 불러올 수 없습니다. 종목명을 정확히 입력했는지 확인해 주세요.")
        else:
            st.success("손실 기록이 없습니다!")



