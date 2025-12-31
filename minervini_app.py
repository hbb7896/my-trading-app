import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 페이지 설정
st.set_page_config(page_title="미너비니 분석기 (Cloud)", page_icon="📈", layout="wide")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # 구글 시트 읽기 (캐시 없이 항상 최신 데이터)
        df = conn.read(worksheet=0, ttl=0)
        
        # 데이터가 비어있으면 빈 프레임 반환
        if df.empty:
             return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])

        # 필수 컬럼이 있는지 확인 (없으면 에러 방지용 빈 프레임)
        required_cols = ['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent']
        if not all(col in df.columns for col in required_cols):
            return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])

        # 날짜가 비어있는 행 제거
        df = df.dropna(subset=['Date'])
        
        # --- [중요] 숫자 변환 로직 (엑셀 붙여넣기 대비) ---
        # 1,000 같은 콤마 제거
        df['P_L_Amount'] = df['P_L_Amount'].astype(str).str.replace(',', '')
        df['P_L_Amount'] = pd.to_numeric(df['P_L_Amount'], errors='coerce').fillna(0)
        
        # 30% 같은 퍼센트 기호 제거
        df['ROI_Percent'] = df['ROI_Percent'].astype(str).str.replace('%', '')
        df['ROI_Percent'] = pd.to_numeric(df['ROI_Percent'], errors='coerce').fillna(0)
            
        # 날짜 변환
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        return df
    except Exception as e:
        # 뭔가 문제 생기면 빈 표 보여주기
        return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])

df = load_data()

# --- [사이드바] 입력 양식 ---
st.sidebar.header("📝 매매 기록 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("Date (일자)", datetime.today())
    ticker = st.text_input("Ticker (종목명)").upper()
    pn_l = st.number_input("P_L (손익금)", value=0, step=1000)
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
                df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
                updated_df = pd.concat([df, new_data], ignore_index=True)

            # 구글 시트 업데이트
            conn.update(worksheet=0, data=updated_df)
            st.success(f"✅ {ticker} 저장 완료!")
            st.rerun()
        else:
            st.error("종목명을 입력해주세요.")

# --- [메인 화면] ---
st.title("📊 Mark Minervini Dashboard (Cloud)")

if not df.empty:
    tab1, tab2, tab3 = st.tabs(["📈 성과 분석", "📅 기간별", "📋 데이터 원본"])
    
    with tab1:
        total = len(df)
        wins = df[df['ROI_Percent'] > 0]
        loss = df[df['ROI_Percent'] <= 0]
        
        win_rate = (len(wins) / total) * 100 if total > 0 else 0
        avg_gain = wins['ROI_Percent'].mean() if not wins.empty else 0
        avg_loss = abs(loss['ROI_Percent'].mean()) if not loss.empty else 0
        expectancy = (win_rate/100 * avg_gain) - ((100-win_rate)/100 * avg_loss)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total P&L", f"{df['P_L_Amount'].sum():,.0f} KRW")
        c2.metric("Win Rate", f"{win_rate:.1f}%")
        c3.metric("Win/Loss Ratio", f"+{avg_gain:.1f}% / -{avg_loss:.1f}%")
        c4.metric("Expectancy", f"{expectancy:.2f}%")
        
        st.divider()
        st.subheader("Equity Curve")
        df_plot = df.sort_values('Date').copy()
        df_plot['Cumulative'] = df_plot['P_L_Amount'].cumsum()
        st.line_chart(df_plot.set_index('Date')['Cumulative'])

    with tab2:
        st.subheader("Period Analysis")
        df['Date'] = pd.to_datetime(df['Date'])
        
        col_m, col_y = st.columns(2)
        with col_m:
            st.caption("Monthly P&L")
            df['Month'] = df['Date'].dt.strftime('%Y-%m')
            st.bar_chart(df.groupby('Month')['P_L_Amount'].sum())
        
        with col_y:
            st.caption("Yearly P&L")
            df['Year'] = df['Date'].dt.strftime('%Y')
            st.bar_chart(df.groupby('Year')['P_L_Amount'].sum())

    with tab3:
        st.caption("Synced with Google Sheets")
        st.dataframe(df.sort_values('Date', ascending=False))

else:
    st.info("👈 사이드바에서 첫 매매 기록을 입력하거나, 구글 시트에 데이터를 붙여넣어주세요!")


