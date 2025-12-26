import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="미너비니 분석기 v3", page_icon="📊", layout="wide")

FILE_NAME = 'minervini_journal_v3.csv'

# 데이터 로드/저장 함수
def load_data():
    if os.path.exists(FILE_NAME):
        df = pd.read_csv(FILE_NAME)
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])

def save_data(df):
    df.to_csv(FILE_NAME, index=False, encoding='utf-8-sig')

df = load_data()

# --- [사이드바] 초간편 입력 ---
st.sidebar.header("📝 매매 결과 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("날짜", datetime.today())
    ticker = st.text_input("종목명").upper()
    # 사장님이 요청하신 핵심 데이터 2개
    pn_l = st.number_input("손익금 (원)", value=0)
    roi = st.number_input("수익률 (%)", value=0.0, format="%.2f")
    memo = st.text_input("메모 (셋업 종류 등)")
    submit = st.form_submit_button("기록 저장")

    if submit:
        new_row = pd.DataFrame([{'Date': date, 'Ticker': ticker, 'P_L_Amount': pn_l, 'ROI_Percent': roi, 'Memo': memo}])
        df = pd.concat([df, new_row], ignore_index=True)
        save_data(df)
        st.rerun()

# --- [메인 화면] 분석 대시보드 ---
st.title("📊 Mark Minervini Style Performance")

tab1, tab2 = st.tabs(["📈 성과 분석", "⚙️ 데이터 수정/삭제"])

with tab1:
    if len(df) > 0:
        # 미너비니 공식 기반 통계
        total_trades = len(df)
        wins = df[df['ROI_Percent'] > 0]
        losses = df[df['ROI_Percent'] <= 0]
        
        win_rate = (len(wins) / total_trades) * 100
        avg_gain = wins['ROI_Percent'].mean() if not wins.empty else 0
        avg_loss = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
        
        # 기대값 Formula: (Win% * Avg Win) - (Loss% * Avg Loss)
        expectancy = (win_rate/100 * avg_gain) - ((100-win_rate)/100 * avg_loss)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        c2.metric("승률 (Batting Avg)", f"{win_rate:.1f}%")
        c3.metric("평균 수익/손실", f"{avg_gain:.1f}% / -{avg_loss:.1f}%")
        c4.metric("기대값 (Expectancy)", f"{expectancy:.2f}%")

        st.divider()
        st.subheader("📉 자산 성장 곡선 (Equity Curve)")
        df_sorted = df.sort_values('Date')
        df_sorted['Cumulative'] = df_sorted['P_L_Amount'].cumsum()
        st.line_chart(df_sorted.set_index('Date')['Cumulative'])
    else:
        st.info("기록을 먼저 입력해주세요.")

with tab2:
    st.subheader("📝 기록 수정 및 삭제")
    # 편집기에서 직접 수정 가능
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 변경사항 저장"):
        save_data(edited_df)
        st.success("업데이트 완료!")
        st.rerun()
