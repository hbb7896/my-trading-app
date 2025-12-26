import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="미너비니 분석기 v3", page_icon="📊", layout="wide")

# [중요] 파일 이름을 새롭게 바꿔서 기존 에러 파일과 충돌을 피합니다.
FILE_NAME = 'trading_data_final.csv'

def load_data():
    if os.path.exists(FILE_NAME):
        try:
            df = pd.read_csv(FILE_NAME)
            # 에러 방지: 날짜 변환 시 잘못된 데이터는 무시하도록 보강
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            # 날짜가 잘못된 행은 삭제
            df = df.dropna(subset=['Date'])
            return df
        except:
            # 파일이 깨졌을 경우 빈 장부 반환
            return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])
    return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])

def save_data(df):
    df.to_csv(FILE_NAME, index=False, encoding='utf-8-sig')

df = load_data()

# --- [사이드바] 입력 양식 ---
st.sidebar.header("📝 매매 결과 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.sidebar.date_input("날짜", datetime.today())
    ticker = st.sidebar.text_input("종목명").upper()
    pn_l = st.sidebar.number_input("손익금 (원)", value=0)
    roi = st.sidebar.number_input("수익률 (%)", value=0.0, format="%.2f")
    memo = st.sidebar.text_input("메모")
    submit = st.sidebar.form_submit_button("기록 저장")

    if submit:
        if ticker:
            new_row = pd.DataFrame([{'Date': date, 'Ticker': ticker, 'P_L_Amount': pn_l, 'ROI_Percent': roi, 'Memo': memo}])
            df = pd.concat([df, new_row], ignore_index=True)
            save_data(df)
            st.success(f"{ticker} 저장 완료!")
            st.rerun()
        else:
            st.sidebar.error("종목명을 입력해주세요.")

# --- [메인 화면] ---
st.title("📊 Mark Minervini Performance Analyzer")

if len(df) > 0:
    tab1, tab2 = st.tabs(["📈 성과 분석", "⚙️ 데이터 수정/삭제"])
    
    with tab1:
        # 통계 계산
        total_trades = len(df)
        wins = df[df['ROI_Percent'] > 0]
        loss = df[df['ROI_Percent'] <= 0]
        win_rate = (len(wins) / total_trades) * 100
        avg_gain = wins['ROI_Percent'].mean() if not wins.empty else 0
        avg_loss = abs(loss['ROI_Percent'].mean()) if not loss.empty else 0
        expectancy = (win_rate/100 * avg_gain) - ((100-win_rate)/100 * avg_loss)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        c2.metric("승률", f"{win_rate:.1f}%")
        c3.metric("평균 수익/손실", f"{avg_gain:.1f}% / -{avg_loss:.1f}%")
        c4.metric("기대값", f"{expectancy:.2f}%")
        
        st.divider()
        st.subheader("📈 자산 성장 곡선")
        df_plot = df.sort_values('Date')
        df_plot['Cumulative'] = df_plot['P_L_Amount'].cumsum()
        st.line_chart(df_plot.set_index('Date')['Cumulative'])

    with tab2:
        st.subheader("📝 데이터 편집기")
        st.write("표에서 직접 수정 후 반드시 아래 버튼을 눌러주세요.")
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 변경사항 저장"):
            save_data(edited_df)
            st.success("데이터가 업데이트되었습니다!")
            st.rerun()
else:
    st.info("왼쪽 사이드바에서 첫 매매 기록을 입력해 주세요!")

