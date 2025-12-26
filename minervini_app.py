import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="미너비니 분석기 v5", page_icon="📊", layout="wide")

# 파일 이름 (일관성을 위해 v4 파일을 유지하거나 필요시 변경하세요)
FILE_NAME = 'trading_data_v4.csv'

def load_data():
    if os.path.exists(FILE_NAME):
        try:
            df = pd.read_csv(FILE_NAME)
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            return df.dropna(subset=['Date'])
        except:
            pass
    return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])

if 'df' not in st.session_state:
    st.session_state.df = load_data()

def save_data():
    st.session_state.df.to_csv(FILE_NAME, index=False, encoding='utf-8-sig')

# --- [사이드바] 입력 양식 ---
st.sidebar.header("📝 매매 결과 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("날짜", datetime.today())
    ticker = st.text_input("종목명").upper()
    pn_l = st.number_input("손익금 (원)", value=0)
    roi = st.number_input("수익률 (%)", value=0.0, format="%.2f")
    memo = st.text_input("메모")
    submit = st.form_submit_button("기록 저장")

    if submit:
        if ticker:
            new_row = pd.DataFrame([{'Date': date, 'Ticker': ticker, 'P_L_Amount': pn_l, 'ROI_Percent': roi, 'Memo': memo}])
            st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
            save_data()
            st.success(f"{ticker} 저장 성공!")
            st.rerun()
        else:
            st.error("종목명을 입력해주세요.")

# --- [메인 화면] ---
st.title("📊 Mark Minervini Performance Analyzer v5")

df = st.session_state.df

if not df.empty:
    tab1, tab2, tab3, tab4 = st.tabs(["📈 전체 성과", "📅 월별 분석", "🗓️ 년별 분석", "⚙️ 데이터 관리"])
    
    with tab1:
        # 전체 통계
        total_trades = len(df)
        wins = df[df['ROI_Percent'] > 0]
        loss = df[df['ROI_Percent'] <= 0]
        win_rate = (len(wins) / total_trades) * 100
        avg_gain = wins['ROI_Percent'].mean() if not wins.empty else 0
        avg_loss = abs(loss['ROI_Percent'].mean()) if not loss.empty else 0
        expectancy = (win_rate/100 * avg_gain) - ((100-win_rate)/100 * avg_loss)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        c2.metric("전체 승률", f"{win_rate:.1f}%")
        c3.metric("평균 수익/손실", f"{avg_gain:.1f}% / -{avg_loss:.1f}%")
        c4.metric("기대값", f"{expectancy:.2f}%")
        
        st.divider()
        st.subheader("📈 누적 수익 곡선")
        df_plot = df.sort_values('Date')
        df_plot['Cumulative'] = df_plot['P_L_Amount'].cumsum()
        st.line_chart(df_plot.set_index('Date')['Cumulative'])

    # [수정/추가된 분석 로직] 통계 계산 함수
    def get_stats(group):
        total = len(group)
        wins = group[group['ROI_Percent'] > 0]
        loss = group[group['ROI_Percent'] <= 0]
        win_rate = (len(wins) / total) * 100
        avg_gain = wins['ROI_Percent'].mean() if not wins.empty else 0
        avg_loss = abs(loss['ROI_Percent'].mean()) if not loss.empty else 0
        pl_ratio = (avg_gain / avg_loss) if avg_loss > 0 else 0
        return pd.Series({
            '매매횟수': total,
            '승률': f"{win_rate:.1f}%",
            '손익비(P/L)': f"1 : {pl_ratio:.2f}",
            '평균수익': f"{avg_gain:.1f}%",
            '평균손실': f"-{avg_loss:.1f}%",
            '수익금 합계': f"{group['P_L_Amount'].sum():,.0f}원"
        })

    with tab2:
        st.subheader("📅 월별 성과 요약")
        df_month = df.copy()
        df_month['Month'] = df_month['Date'].dt.strftime('%Y-%m')
        monthly_summary = df_month.groupby('Month').apply(get_stats).sort_index(ascending=False)
        st.table(monthly_summary)

    with tab3:
        st.subheader("🗓️ 년별 성과 요약")
        df_year = df.copy()
        df_year['Year'] = df_year['Date'].dt.strftime('%Y')
        yearly_summary = df_year.groupby('Year').apply(get_stats).sort_index(ascending=False)
        st.table(yearly_summary)

    with tab4:
        st.subheader("📝 데이터 편집기")
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 변경사항 저장"):
            st.session_state.df = edited_df
            save_data()
            st.success("데이터 업데이트 완료!")
            st.rerun()
else:
    st.info("기록된 데이터가 없습니다.")

