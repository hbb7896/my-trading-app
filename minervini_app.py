import streamlit as st
import pandas as pd
import numpy as np
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
        df['P_L_Amount'] = df['P_L_Amount'].astype(str).str.replace(',', '')
        df['P_L_Amount'] = pd.to_numeric(df['P_L_Amount'], errors='coerce').fillna(0)
        
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
    # 탭 구성 (화면 분할)
    tab1, tab2, tab3, tab4 = st.tabs(["📊 차트 대시보드", "📅 월별 분석", "📆 연도별 분석", "📋 데이터 원본"])
    
    # 공통 계산
    df['Year'] = df['Date'].dt.year
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
    total_trades = len(df)
    wins = df[df['ROI_Percent'] > 0]
    losses = df[df['ROI_Percent'] <= 0]
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    
    # === TAB 1: 차트 대시보드 (시각화 중심) ===
    with tab1:
        # 상단 요약 카드
        st.subheader("📍 Overall Performance")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("총 누적 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        kpi2.metric("승률 (Win Rate)", f"{win_rate:.1f}%")
        kpi3.metric("최고 수익 (Best)", f"+{df['ROI_Percent'].max():.2f}%")
        kpi4.metric("최악 손실 (Worst)", f"{df['ROI_Percent'].min():.2f}%")
        
        st.divider()
        
        # 그래프 1행: 자산 곡선 + 수익 분포
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("📈 자산 우상향 곡선 (Equity Curve)")
            df_sorted = df.sort_values('Date')
            df_sorted['Cumulative'] = df_sorted['P_L_Amount'].cumsum()
            st.line_chart(df_sorted.set_index('Date')['Cumulative'], color="#00FF00")
            
        with c2:
            st.subheader("⚖️ 손익 분포 (Scatter)")
            # 수익률 분포를 점으로 찍어서 보여줌 (손절 잘 지키는지 확인용)
            st.scatter_chart(
                df,
                x='Date',
                y='ROI_Percent',
                color='ROI_Percent',
                height=300
            )
            st.caption("점이 0선 아래로 깊게 내려가면 손절 원칙 위반입니다!")

        # 그래프 2행: 월별 막대 그래프
        st.subheader("📊 월별 손익 흐름")
        monthly_sum = df.groupby('YearMonth')['P_L_Amount'].sum()
        st.bar_chart(monthly_sum)

    # === TAB 2: 월별 상세 분석 (Monthly) ===
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

    # === TAB 3: 연도별 상세 분석 (Yearly) - NEW! ===
    with tab3:
        st.subheader("📆 연도별 종합 성적표")
        
        yearly_stats = []
        for y, group in df.groupby('Year'):
            g_wins = group[group['ROI_Percent'] > 0]
            g_losses = group[group['ROI_Percent'] <= 0]
            
            # 연도별 핵심 지표 계산
            y_win_rate = (len(g_wins) / len(group)) * 100
            y_avg_gain = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
            y_avg_loss = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
            y_wl_ratio = y_avg_gain / y_avg_loss if y_avg_loss != 0 else 0
            
            # 프로핏 팩터 (총이익 / 총손실)
            y_profit_factor = g_wins['P_L_Amount'].sum() / abs(g_losses['P_L_Amount'].sum()) if g_losses['P_L_Amount'].sum() != 0 else 0
            
            yearly_stats.append({
                "연도": y,
                "총 손익": group['P_L_Amount'].sum(),
                "총 거래수": f"{len(group)}회",
                "승률": f"{y_win_rate:.1f}%",
                "손익비": f"{y_wl_ratio:.2f}",
                "PF (프로핏팩터)": f"{y_profit_factor:.2f}",
                "최고 수익": f"{group['ROI_Percent'].max():.2f}%"
            })
            
        y_df = pd.DataFrame(yearly_stats).sort_values("연도", ascending=False)
        
        # 연도별 데이터 표시 (중요하니까 큼직하게)
        st.dataframe(
            y_df.style.format({"총 손익": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='Greens'),
            use_container_width=True
        )
        
        st.caption("PF(프로핏 팩터)가 1.5 이상이면 아주 훌륭한 시스템입니다.")

    # === TAB 4: 데이터 원본 ===
    with tab4:
        st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")   
