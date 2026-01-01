import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import altair as alt
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 페이지 설정
st.set_page_config(page_title="Trading Master Dashboard", page_icon="💎", layout="wide")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(worksheet=0, ttl=0)
        if df.empty:
             return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])
        
        df = df.dropna(subset=['Date'])
        
        # 숫자 변환
        if 'P_L_Amount' in df.columns:
            df['P_L_Amount'] = df['P_L_Amount'].astype(str).str.replace(',', '')
            df['P_L_Amount'] = pd.to_numeric(df['P_L_Amount'], errors='coerce').fillna(0)
        
        if 'ROI_Percent' in df.columns:
            df['ROI_Percent'] = df['ROI_Percent'].astype(str).str.replace('%', '')
            df['ROI_Percent'] = pd.to_numeric(df['ROI_Percent'], errors='coerce').fillna(0)
        
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        return df
    except Exception as e:
        return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])

df = load_data()

# --- [사이드바] 입력 양식 ---
st.sidebar.header("📝 매매 기록 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("일자", datetime.today())
    ticker = st.text_input("종목명").upper()
    pn_l = st.number_input("손익금 (원)", value=0)
    roi = st.number_input("수익률 (%)", value=0.0, format="%.2f")
    memo = st.text_input("메모")
    submit = st.form_submit_button("기록 저장")

    if submit:
        if ticker:
            new_data = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Ticker': ticker,
                'P_L_Amount': pn_l,
                'ROI_Percent': roi,
                'Memo': memo
            }])
            
            df_temp = load_data()
            if df_temp.empty:
                updated_df = new_data
            else:
                df_temp['Date'] = df_temp['Date'].dt.strftime('%Y-%m-%d')
                updated_df = pd.concat([df_temp, new_data], ignore_index=True)

            conn.update(worksheet=0, data=updated_df)
            st.success(f"✅ {ticker} 저장 완료!")
            st.rerun()
        else:
            st.error("종목명을 입력해주세요.")

# --- [메인 화면] ---
st.title("💎 Trading Master Dashboard")

if not df.empty:
    tab1, tab2, tab3, tab4 = st.tabs(["📊 차트 대시보드", "📅 월별 분석", "📆 연도별 분석", "📋 데이터 원본"])
    
    df['Year'] = df['Date'].dt.year
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
    
    # 핵심 지표 계산
    total_trades = len(df)
    wins = df[df['ROI_Percent'] > 0]
    losses = df[df['ROI_Percent'] <= 0]
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    avg_win = wins['ROI_Percent'].mean() if not wins.empty else 0
    avg_loss = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
    risk_reward_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    avg_roi = df['ROI_Percent'].mean()

    with tab1:
        # 상단 요약 카드
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("총 누적 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        kpi2.metric("승률 (Win Rate)", f"{win_rate:.1f}%")
        kpi3.metric("평균 수익률", f"{avg_roi:.2f}%")
        kpi4.metric("평균 손익비", f"{risk_reward_ratio:.2f}")
        
        st.divider()
        
        st.subheader("🚀 내 계좌 vs KOSPI 지수")
        
        # --- [핵심 수정 부분] 날짜별 데이터 합산 ---
        # 1. 같은 날짜의 손익을 하나로 합칩니다. (그래프 꼬임 방지)
        daily_df = df.groupby('Date')['P_L_Amount'].sum().reset_index().sort_values('Date')
        daily_df['Cumulative'] = daily_df['P_L_Amount'].cumsum()
        
        # 2. 코스피 데이터 가져오기
        try:
            start_date = daily_df['Date'].min()
            end_date = datetime.today()
            kospi = yf.download("^KS11", start=start_date, end=end_date, progress=False)
            
            if isinstance(kospi.columns, pd.MultiIndex):
                kospi = kospi.xs('Close', axis=1, level=0)
            elif 'Close' in kospi.columns:
                kospi = kospi[['Close']]
                
            kospi = kospi.reset_index()
            kospi.columns = ['Date', 'KOSPI']
            kospi['Date'] = pd.to_datetime(kospi['Date']).dt.tz_localize(None)
        except:
            kospi = pd.DataFrame()

        # 3. 차트 그리기
        if not kospi.empty:
            # 내 자산 영역 차트
            base = alt.Chart(daily_df).encode(x=alt.X('Date:T', title='날짜'))
            my_chart = base.mark_area(opacity=0.3, color='#00FF00', line={'color':'#00FF00'}).encode(
                y=alt.Y('Cumulative:Q', title='내 누적 수익 (원)'),
                tooltip=[alt.Tooltip('Date:T', title='날짜'), alt.Tooltip('Cumulative:Q', title='누적손익', format=',.0f')]
            )
            
            # 코스피 선 차트
            kospi_base = alt.Chart(kospi).encode(x='Date:T')
            kospi_chart = kospi_base.mark_line(color='red', strokeWidth=1).encode(
                y=alt.Y('KOSPI:Q', title='KOSPI 지수', scale=alt.Scale(zero=False)),
                tooltip=[alt.Tooltip('Date:T', title='날짜'), alt.Tooltip('KOSPI:Q', title='코스피', format='.2f')]
            )
            
            combined_chart = alt.layer(my_chart, kospi_chart).resolve_scale(
                y='independent'
            ).properties(height=450)
            
            st.altair_chart(combined_chart, use_container_width=True)
        else:
            st.line_chart(daily_df.set_index('Date')['Cumulative'])

        # 월별 막대 그래프
        st.subheader("📊 월별 손익 흐름")
        monthly_sum = df.groupby('YearMonth')['P_L_Amount'].sum()
        st.bar_chart(monthly_sum)

    # 나머지 탭(월별, 연도별, 원본)은 기존과 동일하게 유지
    with tab2:
        st.subheader("📅 월별 상세 성적표")
        monthly_stats = []
        for ym, group in df.groupby('YearMonth'):
            g_wins = group[group['ROI_Percent'] > 0]
            g_losses = group[group['ROI_Percent'] <= 0]
            m_avg_gain = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
            m_avg_loss = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
            m_wl_ratio = m_avg_gain / m_avg_loss if m_avg_loss != 0 else 0
            monthly_stats.append({
                "기간": ym, "총 손익": group['P_L_Amount'].sum(), "거래수": f"{len(group)}회",
                "승률": f"{(len(g_wins)/len(group))*100:.1f}%", "평균수익": f"+{m_avg_gain:.2f}%",
                "평균손실": f"-{m_avg_loss:.2f}%", "손익비": f"{m_wl_ratio:.2f}"
            })
        m_df = pd.DataFrame(monthly_stats).sort_values("기간", ascending=False)
        st.dataframe(m_df.style.format({"총 손익": "{:,.0f}원"}), use_container_width=True)

    with tab3:
        st.subheader("📆 연도별 종합 성적표")
        yearly_stats = []
        for y, group in df.groupby('Year'):
            g_wins = group[group['ROI_Percent'] > 0]; g_losses = group[group['ROI_Percent'] <= 0]
            y_win_rate = (len(g_wins) / len(group)) * 100
            y_avg_gain = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
            y_avg_loss = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
            y_wl_ratio = y_avg_gain / y_avg_loss if y_avg_loss != 0 else 0
            y_pf = g_wins['P_L_Amount'].sum() / abs(g_losses['P_L_Amount'].sum()) if g_losses['P_L_Amount'].sum() != 0 else 0
            yearly_stats.append({
                "연도": y, "총 손익": group['P_L_Amount'].sum(), "총 거래수": f"{len(group)}회",
                "승률": f"{y_win_rate:.1f}%", "손익비": f"{y_wl_ratio:.2f}", "PF": f"{y_pf:.2f}"
            })
        y_df = pd.DataFrame(yearly_stats).sort_values("연도", ascending=False)
        st.dataframe(y_df.style.format({"총 손익": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='Greens'), use_container_width=True)

    with tab4:
        st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)
else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")


