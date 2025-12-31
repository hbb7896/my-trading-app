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
        # 캐시 없이 즉시 로딩 (ttl=0)
        df = conn.read(worksheet=0, ttl=0)
        if df.empty:
             return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])
        
        # 데이터 전처리
        df = df.dropna(subset=['Date'])
        
        # 엑셀 붙여넣기 대비: 콤마(,)와 퍼센트(%) 제거 후 숫자로 변환
        df['P_L_Amount'] = df['P_L_Amount'].astype(str).str.replace(',', '')
        df['P_L_Amount'] = pd.to_numeric(df['P_L_Amount'], errors='coerce').fillna(0)
        
        df['ROI_Percent'] = df['ROI_Percent'].astype(str).str.replace('%', '')
        df['ROI_Percent'] = pd.to_numeric(df['ROI_Percent'], errors='coerce').fillna(0)
        
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        return df
    except Exception as e:
        return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])

df = load_data()

# --- [사이드바] 입력 양식 (기존과 동일) ---
st.sidebar.header("📝 매매 기록 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("Date (일자)", datetime.today())
    ticker = st.text_input("Ticker (종목명)").upper()
    pn_l = st.number_input("P_L (손익금)", value=0)
    roi = st.number_input("ROI (수익률 %)", value=0.0, format="%.2f")
    memo = st.text_input("Memo (비고)")
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
                df_temp = load_data() # 최신 데이터 다시 로드
                df_temp['Date'] = df_temp['Date'].dt.strftime('%Y-%m-%d')
                updated_df = pd.concat([df_temp, new_data], ignore_index=True)

            conn.update(worksheet=0, data=updated_df)
            st.success(f"✅ {ticker} 저장 완료!")
            st.rerun()
        else:
            st.error("종목명을 입력해주세요.")

# --- [메인 화면] 마크 미너비니 스타일 분석 ---
st.title("🏆 Minervini Professional Analytics")

if not df.empty:
    # --- 핵심 지표 계산 (Math of Trading) ---
    total_trades = len(df)
    wins = df[df['ROI_Percent'] > 0]
    losses = df[df['ROI_Percent'] <= 0]
    
    # 1. 승률 (Batting Average)
    batting_avg = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    
    # 2. 평균 손익
    avg_gain = wins['ROI_Percent'].mean() if not wins.empty else 0
    avg_loss = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
    
    # 3. 손익비 (Win/Loss Ratio) - 미너비니는 2:1 이상 권장
    gain_loss_ratio = avg_gain / avg_loss if avg_loss != 0 else 0
    
    # 4. 기대값 (Expectancy) - 한 번 매매할 때 기대되는 수익률
    expectancy = (batting_avg/100 * avg_gain) - ((1-batting_avg/100) * avg_loss)
    
    # 5. 프로핏 팩터 (총 이익 / 총 손실)
    total_profit_sum = wins['P_L_Amount'].sum()
    total_loss_sum = abs(losses['P_L_Amount'].sum())
    profit_factor = total_profit_sum / total_loss_sum if total_loss_sum != 0 else float('inf')

    # --- 1. 상단 스코어보드 ---
    st.subheader("📍 Key Performance Indicators (KPI)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Batting Avg (승률)", f"{batting_avg:.1f}%")
    m2.metric("Win/Loss Ratio (손익비)", f"{gain_loss_ratio:.2f} : 1")
    m3.metric("Expectancy (기대값)", f"{expectancy:.2f}%")
    m4.metric("Profit Factor", f"{profit_factor:.2f}")

    # --- 2. 상세 통계 및 그래프 ---
    st.divider()
    col1, col2 = st.columns([1, 2]) # 왼쪽 1 : 오른쪽 2 비율
    
    with col1:
        st.markdown("### 📊 Trade Stats")
        # 깔끔한 통계 테이블 생성
        stats_df = pd.DataFrame({
            "항목": ["총 매매 횟수", "최대 수익 (1회)", "최대 손실 (1회)", "평균 수익률", "평균 손실률", "총 손익금"],
            "값": [
                f"{total_trades}회", 
                f"{df['ROI_Percent'].max():.2f}%", 
                f"{df['ROI_Percent'].min():.2f}%", 
                f"+{avg_gain:.2f}%", 
                f"-{avg_loss:.2f}%",
                f"{df['P_L_Amount'].sum():,.0f}원"
            ]
        })
        st.table(stats_df.set_index("항목"))

    with col2:
        st.markdown("### 📈 계좌 성장 곡선 (Equity Curve)")
        df_plot = df.sort_values('Date').copy()
        df_plot['Cumulative_PL'] = df_plot['P_L_Amount'].cumsum()
        st.line_chart(df_plot.set_index('Date')['Cumulative_PL'])

    # --- 3. [핵심] 월별 수익 현황 (Hedge Fund Style) ---
    st.divider()
    st.subheader("📅 Monthly Performance Matrix")
    st.caption("연도별/월별 누적 손익을 한눈에 파악하세요.")
    
    df['Year'] = df['Date'].dt.year
    df['Month'] = df['Date'].dt.month
    
    # 피벗 테이블 생성 (행:연도, 열:월, 값:손익합계)
    monthly_pivot = df.pivot_table(
        values='P_L_Amount', 
        index='Year', 
        columns='Month', 
        aggfunc='sum'
    ).fillna(0)
    
    # 1월~12월 컬럼 순서 보장
    for m in range(1, 13):
        if m not in monthly_pivot.columns:
            monthly_pivot[m] = 0
    monthly_pivot = monthly_pivot[range(1, 13)] 
    
    # 컬럼명 영어로 변경 (Jan, Feb...)
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_pivot.columns = month_names
    
    # 연도별 총합계(Total) 컬럼 추가
    monthly_pivot['TOTAL'] = monthly_pivot.sum(axis=1)

    # 색상 입혀서 출력 (수익=초록, 손실=빨강)
    def color_negative_red(val):
        color = 'red' if val < 0 else 'blue' if val > 0 else 'black'
        return f'color: {color}'

    # 천단위 콤마 찍어서 보여주기
    st.dataframe(
        monthly_pivot.style
        .format("{:,.0f}")
        .applymap(color_negative_red)
    )

    # --- 4. 원본 데이터 ---
    with st.expander("🔍 전체 거래 내역 확인하기"):
        st.dataframe(df.sort_values('Date', ascending=False))

else:
    st.info("데이터가 없습니다. 사이드바에서 첫 번째 매매 기록을 입력해 주세요.")


