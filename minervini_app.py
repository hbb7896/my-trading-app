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
        
        df = df.dropna(subset=['Date'])
        
        # 숫자 변환 (콤마, % 제거)
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
st.title("🏆 트레이딩 성과 분석 (Deep Dive)")

if not df.empty:
    # --- 1. 전체 트레이딩 요약 (Overall Summary) ---
    st.subheader("📊 전체 트레이딩 요약")
    
    total_trades = len(df)
    wins = df[df['ROI_Percent'] > 0]
    losses = df[df['ROI_Percent'] <= 0]
    
    # 주요 지표 계산
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    avg_gain = wins['ROI_Percent'].mean() if not wins.empty else 0
    avg_loss = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
    wl_ratio = avg_gain / avg_loss if avg_loss != 0 else 0
    total_pl = df['P_L_Amount'].sum()

    # 지표 카드 표시 (요청하신 항목 위주)
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("총 손익", f"{total_pl:,.0f}원")
    kpi2.metric("성공률 (승률)", f"{win_rate:.1f}%")
    kpi3.metric("평균 수익", f"+{avg_gain:.2f}%")
    kpi4.metric("평균 손실", f"-{avg_loss:.2f}%")
    kpi5.metric("손익비 (성공/실패)", f"{wl_ratio:.2f}")

    st.divider()

    # --- 2. [핵심] 월별 상세 성적표 (Monthly Report) ---
    st.subheader("📅 월별 상세 성적표")
    
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
    
    # 월별 그룹화 및 통계 계산 함수
    monthly_stats = []
    
    # 최신 달부터 보이게 정렬 (내림차순)
    for ym, group in df.groupby('YearMonth'):
        g_wins = group[group['ROI_Percent'] > 0]
        g_losses = group[group['ROI_Percent'] <= 0]
        
        m_win_rate = (len(g_wins) / len(group)) * 100
        m_avg_gain = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
        m_avg_loss = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
        m_wl_ratio = m_avg_gain / m_avg_loss if m_avg_loss != 0 else 0
        
        monthly_stats.append({
            "기간": ym,
            "총 손익": group['P_L_Amount'].sum(),
            "총 거래수": f"{len(group)}회",
            "성공률(승률)": f"{m_win_rate:.1f}%",
            "평균 수익": f"+{m_avg_gain:.2f}%",
            "평균 손실": f"-{m_avg_loss:.2f}%",
            "손익비": f"{m_wl_ratio:.2f}"
        })
    
    # 데이터프레임으로 변환 및 역순 정렬 (최신이 위로)
    stats_df = pd.DataFrame(monthly_stats).sort_values("기간", ascending=False)
    
    # 숫자 예쁘게 꾸미기 (색상 적용)
    def style_dataframe(row):
        return ['background-color: #e6fffa' if row.name % 2 == 0 else '' for _ in row]

    # 화면에 표 출력
    st.dataframe(
        stats_df.style.format({"총 손익": "{:,.0f}원"}),
        use_container_width=True,
        hide_index=True
    )

    # --- 3. 그래프 분석 ---
    st.divider()
    g1, g2 = st.columns(2)
    
    with g1:
        st.subheader("📈 자산 곡선 (누적 손익)")
        df_sorted = df.sort_values('Date')
        df_sorted['Cumulative'] = df_sorted['P_L_Amount'].cumsum()
        st.line_chart(df_sorted.set_index('Date')['Cumulative'])
        
    with g2:
        st.subheader("📊 승률 분포")
        # 승/패 파이차트 대신 직관적인 바 차트
        st.bar_chart(pd.DataFrame({
            'Count': [len(wins), len(losses)]
        }, index=['Winning Trades (수익)', 'Losing Trades (손실)']))

    # --- 4. 데이터 원본 ---
    with st.expander("🔍 전체 거래 내역 보기"):
        st.dataframe(df.sort_values('Date', ascending=False))

else:
    st.info("데이터가 없습니다. 매매 기록을 입력하면 통계가 나타납니다.")
