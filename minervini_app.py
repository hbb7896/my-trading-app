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
            
            if df.empty:
                updated_df = new_data
            else:
                # 날짜 형식을 문자로 통일해서 합치기
                df_temp = load_data()
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
    # 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs(["📊 차트 대시보드", "📅 월별 분석", "📆 연도별 분석", "📋 데이터 원본"])
    
    # 공통 계산
    df['Year'] = df['Date'].dt.year
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
    
    total_trades = len(df)
    wins = df[df['ROI_Percent'] > 0]
    losses = df[df['ROI_Percent'] <= 0]
    
    # 승률
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    
    # 평균 수익/손실
    avg_win = wins['ROI_Percent'].mean() if not wins.empty else 0
    avg_loss = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
    
    # 손익비 (Profit Factor가 아닌 평균손익비)
    risk_reward_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    # 평균 수익률
    avg_roi = df['ROI_Percent'].mean()

    # === TAB 1: 차트 대시보드 ===
    with tab1:
        # 상단 요약 카드 (요청하신 대로 변경: 최고/최악 삭제 -> 평균수익/손익비 추가)
        st.subheader("📍 Overall Performance")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("총 누적 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        kpi2.metric("승률 (Win Rate)", f"{win_rate:.1f}%")
        kpi3.metric("평균 수익률", f"{avg_roi:.2f}%")
        kpi4.metric("평균 손익비", f"{risk_reward_ratio:.2f}")
        
        st.divider()
        
        # [NEW] 자산 곡선 vs 코스피 지수 비교
        st.subheader("🚀 내 계좌 vs KOSPI 지수")
        
        # 1. 내 자산 데이터 준비
        chart_data = df.sort_values('Date').copy()
        chart_data['Cumulative'] = chart_data['P_L_Amount'].cumsum()
        
        # 2. 코스피 데이터 가져오기 (yfinance)
        try:
            start_date = chart_data['Date'].min()
            end_date = datetime.today()
            kospi = yf.download("^KS11", start=start_date, end=end_date, progress=False)
            
            # yfinance 데이터 구조 처리
            if isinstance(kospi.columns, pd.MultiIndex):
                kospi = kospi.xs('Close', axis=1, level=0) # 종가만 가져오기
            elif 'Close' in kospi.columns:
                kospi = kospi[['Close']]
                
            kospi = kospi.reset_index()
            # 날짜 컬럼 이름 통일 및 시간대 제거
            date_col = 'Date' if 'Date' in kospi.columns else kospi.columns[0]
            kospi[date_col] = pd.to_datetime(kospi[date_col]).dt.tz_localize(None)
            kospi.columns = ['Date', 'KOSPI'] # 컬럼명 단순화
            
        except Exception as e:
            kospi = pd.DataFrame()

        # 3. 차트 그리기 (Altair)
        if not kospi.empty:
            # 내 계좌 (영역 차트)
            base = alt.Chart(chart_data).encode(x='Date:T')
            my_chart = base.mark_area(opacity=0.3, color='#00FF00').encode(
                y=alt.Y('Cumulative:Q', title='내 누적 수익 (원)'),
                tooltip=['Date', 'Cumulative']
            )
            
            # 코스피 (선 차트 - 오른쪽 축 사용)
            kospi_base = alt.Chart(kospi).encode(x='Date:T')
            kospi_chart = kospi_base.mark_line(color='red').encode(
                y=alt.Y('KOSPI:Q', title='KOSPI 지수', scale=alt.Scale(zero=False)),
                tooltip=['Date', 'KOSPI']
            )
            
            # 두 차트 합치기
            combined_chart = alt.layer(my_chart, kospi_chart).resolve_scale(
                y='independent'
            ).properties(height=400)
            
            st.altair_chart(combined_chart, use_container_width=True)
        else:
            # 코스피 로딩 실패 시 내 차트만 표시
            st.line_chart(chart_data.set_index('Date')['Cumulative'])
            st.caption("코스피 데이터를 불러오는 중이거나 실패했습니다.")

        # [기존 기능 유지] 월별 막대 그래프
        st.subheader("📊 월별 손익 흐름")
        monthly_sum = df.groupby('YearMonth')['P_L_Amount'].sum()
        st.bar_chart(monthly_sum)

    # === TAB 2: 월별 상세 분석 ===
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
                "기간": ym,
                "총 손익": group['P_L_Amount'].sum(),
                "거래수": f"{len(group)}회",
                "승률": f"{(len(g_wins)/len(group))*100:.1f}%",
                "평균수익": f"+{m_avg_gain:.2f}%",
                "평균손실": f"-{m_avg_loss:.2f}%",
                "손익비": f"{m_wl_ratio:.2f}"
            })
        m_df = pd.DataFrame(monthly_stats).sort_values("기간", ascending=False)
        st.dataframe(m_df.style.format({"총 손익": "{:,.0f}원"}), use_container_width=True)

    # === TAB 3: 연도별 분석 ===
    with tab3:
        st.subheader("📆 연도별 종합 성적표")
        yearly_stats = []
        for y, group in df.groupby('Year'):
            g_wins = group[group['ROI_Percent'] > 0]
            g_losses = group[group['ROI_Percent'] <= 0]
            y_win_rate = (len(g_wins) / len(group)) * 100
            y_avg_gain = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
            y_avg_loss = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
            y_wl_ratio = y_avg_gain / y_avg_loss if y_avg_loss != 0 else 0
            y_profit_factor = g_wins['P_L_Amount'].sum() / abs(g_losses['P_L_Amount'].sum()) if g_losses['P_L_Amount'].sum() != 0 else 0
            
            yearly_stats.append({
                "연도": y,
                "총 손익": group['P_L_Amount'].sum(),
                "총 거래수": f"{len(group)}회",
                "승률": f"{y_win_rate:.1f}%",
                "손익비": f"{y_wl_ratio:.2f}",
                "PF": f"{y_profit_factor:.2f}"
            })
        y_df = pd.DataFrame(yearly_stats).sort_values("연도", ascending=False)
        st.dataframe(y_df.style.format({"총 손익": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='Greens'), use_container_width=True)

    # === TAB 4: 데이터 원본 ===
    with tab4:
        st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")
