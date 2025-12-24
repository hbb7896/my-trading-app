import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="미너비니 매매 분석기", page_icon="📊", layout="wide")

# 파일 이름 설정
FILE_NAME = 'minervini_journal.csv'

# --- [사이드바] 매매 기록 입력 ---
st.sidebar.header("📝 매매 일지 작성")
st.sidebar.caption("매도(청산)가 완료된 건만 입력하세요.")

date = st.sidebar.date_input("매도 날짜", datetime.today())
ticker = st.sidebar.text_input("종목명 (예: 삼성전자, TSLA)").upper()
buy_price = st.sidebar.number_input("평균 매수가", min_value=0.0, format="%.2f")
sell_price = st.sidebar.number_input("평균 매도가", min_value=0.0, format="%.2f")
qty = st.sidebar.number_input("수량 (주)", min_value=1)
memo = st.sidebar.text_input("매매 근거 (셋업)")

if st.sidebar.button("기록 저장 (Save)"):
    if buy_price > 0 and sell_price > 0:
        # 수익금 및 수익률 계산
        pn_l = (sell_price - buy_price) * qty
        roi = ((sell_price - buy_price) / buy_price) * 100
        
        new_data = {
            'Date': [date],
            'Ticker': [ticker],
            'Buy_Price': [buy_price],
            'Sell_Price': [sell_price],
            'Qty': [qty],
            'P_L_Amount': [pn_l],  # 손익금
            'ROI_Percent': [roi],  # 수익률(%)
            'Memo': [memo]
        }
        new_df = pd.DataFrame(new_data)

        if not os.path.exists(FILE_NAME):
            new_df.to_csv(FILE_NAME, index=False, encoding='utf-8-sig')
        else:
            new_df.to_csv(FILE_NAME, mode='a', header=False, index=False, encoding='utf-8-sig')
        st.sidebar.success(f"{ticker} 저장 완료!")
    else:
        st.sidebar.error("가격을 정확히 입력해주세요.")

# --- [메인 화면] 분석 대시보드 ---
st.title("📊 Mark Minervini Style Analyzer")
st.markdown("---")

if os.path.exists(FILE_NAME):
    df = pd.read_csv(FILE_NAME)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # 데이터가 있을 때만 분석 시작
    if len(df) > 0:
        # 1. 핵심 통계 (Minervini Metrics)
        total_trades = len(df)
        wins = df[df['P_L_Amount'] > 0]
        losses = df[df['P_L_Amount'] <= 0]
        
        win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
        loss_rate = 100 - win_rate
        
        avg_gain = wins['ROI_Percent'].mean() if not wins.empty else 0
        avg_loss = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
        
        # 손익비 (Gain/Loss Ratio)
        gl_ratio = (avg_gain / avg_loss) if avg_loss > 0 else 0
        
        # 기대값 (Expectancy) = (승률 x 평균수익) - (패율 x 평균손실)
        expectancy = (win_rate/100 * avg_gain) - (loss_rate/100 * avg_loss)

        # 상단 지표 표시
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 누적 수익금", f"{df['P_L_Amount'].sum():,.0f} 원")
        c2.metric("승률 (Win Rate)", f"{win_rate:.1f}%")
        c3.metric("손익비 (G/L Ratio)", f"1 : {gl_ratio:.2f}")
        c4.metric("거래당 기대 수익", f"{expectancy:.2f}%")

        # 미너비니 코멘트 (자동 조언)
        if gl_ratio < 2:
            st.warning(f"⚠️ 경고: 손익비가 {gl_ratio:.2f}입니다. 미너비니는 최소 1:2 이상을 권장합니다. 손절폭을 줄이거나 수익을 더 길게 가져가세요.")
        else:
            st.success("✅ 훌륭합니다! 손익비가 1:2 이상으로 이상적인 추세추종 구조입니다.")

        st.markdown("---")

        # 2. 차트 분석 (Visuals)
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("📈 계좌 수익 곡선 (Equity Curve)")
            df = df.sort_values('Date')
            df['Cumulative_PL'] = df['P_L_Amount'].cumsum()
            st.line_chart(df.set_index('Date')['Cumulative_PL'])
            
        with col_right:
            st.subheader("📅 월별 수익 현황")
            df['Month'] = df['Date'].dt.strftime('%Y-%m')
            monthly_pl = df.groupby('Month')['P_L_Amount'].sum()
            
            # 색상 설정 (수익은 빨강, 손실은 파랑 - 한국식)
            st.bar_chart(monthly_pl)

        # 3. 상세 데이터 (Data Table)
        with st.expander("📄 전체 매매 기록 보기"):
            # 보기 좋게 정렬 및 포맷팅
            display_df = df[['Date', 'Ticker', 'ROI_Percent', 'P_L_Amount', 'Memo']].copy()
            display_df = display_df.sort_values('Date', ascending=False)
            st.dataframe(display_df.style.format({
                'ROI_Percent': '{:.2f}%',
                'P_L_Amount': '{:,.0f}'
            }))

    else:
        st.info("데이터가 없습니다. 왼쪽 사이드바에서 매매 기록을 추가해주세요.")
else:
    st.info("아직 저장된 매매 기록이 없습니다. 왼쪽 사이드바에서 첫 기록을 남겨보세요!")
