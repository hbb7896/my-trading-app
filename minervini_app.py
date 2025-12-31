import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 페이지 설정
st.set_page_config(page_title="Minervini Pro Dashboard", page_icon="🏆", layout="wide")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(worksheet=0, ttl=0)
        if df.empty:
             return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])
        
        # 데이터 전처리
        df = df.dropna(subset=['Date'])
        df['P_L_Amount'] = pd.to_numeric(df['P_L_Amount'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['ROI_Percent'] = pd.to_numeric(df['ROI_Percent'].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        return df
    except Exception as e:
        return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])

df = load_data()

# --- [사이드바] 입력 양식 (기존과 동일) ---
st.sidebar.header("📝 매매 기록 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("Date", datetime.today())
    ticker = st.text_input("Ticker").upper()
    pn_l = st.number_input("P_L (금액)", value=0)
    roi = st.number_input("ROI (%)", value=0.0, format="%.2f")
    memo = st.text_input("Memo")
    submit = st.form_submit_button("기록 저장")

    if submit and ticker:
        new_data = pd.DataFrame([{'Date': date.strftime('%Y-%m-%d'), 'Ticker': ticker, 'P_L_Amount': pn_l, 'ROI_Percent': roi, 'Memo': memo}])
        df_for_up = load_data()
        if not df_for_up.empty:
            df_for_up['Date'] = df_for_up['Date'].dt.strftime('%Y-%m-%d')
            updated_df = pd.concat([df_for_up, new_data], ignore_index=True)
        else:
            updated_df = new_data
        conn.update(worksheet=0, data=updated_df)
        st.success(f"✅ {ticker} 저장 완료!")
        st.rerun()

# --- [메인 화면] 마크 미너비니 스타일 분석 ---
st.title("🏆 Minervini Professional Analytics")

if not df.empty:
    # --- 핵심 지표 계산 ---
    total_trades = len(df)
    wins = df[df['ROI_Percent'] > 0]
    losses = df[df['ROI_Percent'] <= 0]
    
    batting_avg = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    avg_gain = wins['ROI_Percent'].mean() if not wins.empty else 0
    avg_loss = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
    gain_loss_ratio = avg_gain / avg_loss if avg_loss != 0 else 0
    
    # 미너비니 기대값 (Expectancy) = (승률 * 평균수익) - (패율 * 평균손실)
    expectancy = (batting_avg/100 * avg_gain) - ((1-batting_avg/100) * avg_loss)
    
    # 프로핏 팩터 (총 이익 / 총 손실)
    total_profit = wins['P_L_Amount'].sum()
    total_loss = abs(losses['P_L_Amount'].sum())
    profit_factor = total_profit / total_loss if total_loss != 0 else float('inf')

    # --- 1. 상단 스코어보드 ---
    st.subheader("📍 Key Performance Indicators (KPI)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Batting Average (승률)", f"{batting_avg:.1f}%")
    m2.metric("Win/Loss Ratio (손익비)", f"{gain_loss_ratio:.2f} : 1")
    m3.metric("Expectancy (기대값)", f"{expectancy:.2f}%")
    m4.metric("Profit Factor", f"{profit_factor:.2f}")

    # --- 2. 상세 통계 테이블 ---
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Trade Statistics")
        stats_data = {
            "Metric": ["Total Trades (총 매매)", "Largest Win (최대 수익 %)", "Largest Loss (최대 손실 %)", "Avg Holding Gain", "Avg Holding Loss"],
            "Value": [f"{total_trades}회", f"{df['ROI_Percent'].max():.2f}%", f"{df['ROI_Percent'].min():.2f}%", f"{avg_gain:.2f}%", f"{avg_loss:.2f}%"]
        }
        st.table(pd.DataFrame(stats_data))

    with col2:
        st.markdown("### 📉 Equity & Drawdown")
        df_plot = df.sort_values('Date').copy()
        df_plot['Cumulative_PL'] = df_plot['P_L_Amount'].cumsum()
        st.line_chart(df_plot.set_index('Date')['Cumulative_PL'])

    # --- 3. 월별 수익 현황 (미너비니 프로그램의 핵심!) ---
    st.divider()
    st.subheader("📅 Monthly Performance Matrix (Profit/Loss Sum)")
    
    df['Year'] = df['Date'].dt.year
    df['Month'] = df['Date'].dt.month
    
    # 연도/월별 손익 합계 표 만들기
    monthly_pivot = df.pivot_table(
        values='P_L_Amount', 
        index='Year', 
        columns='Month', 
        aggfunc='sum'
    ).fillna(0)
    
    # 1월~12월 컬럼 보장
    for m in range(1, 13):
        if m not in monthly_pivot.columns:
            monthly_pivot[m] = 0
    monthly_pivot = monthly_pivot[range(1, 13)] # 순서 정렬
    monthly_pivot.columns = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # 스타일 적용 (수익은 빨강/초록 등으로 표시하면 좋지만 기본 표로 출력)
    st.dataframe(monthly_pivot.style.format("{:,.0f}").background_gradient(cmap='RdYlGn', axis=None))

    # --- 4. 데이터 상세 로그 ---
    st.divider()
    with st.expander("🔍Raw Data (Edit in Google Sheets)"):
        st.dataframe(df.sort_values('Date', ascending=False))

else:
    st.info("데이터가 없습니다. 사이드바에서 첫 번째 매매 기록을 입력해 주세요.")



