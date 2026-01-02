import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
import altair as alt
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# 1. 페이지 설정
st.set_page_config(page_title="Trading Master Dashboard", page_icon="💎", layout="wide")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# --- [핵심] 한국 종목 리스트 가져오기 ---
@st.cache_data(ttl=86400)
def get_krx_list():
    try:
        # KRX 전체 리스트 가져오기
        df = fdr.StockListing('KRX')
        return df[['Code', 'Name', 'Market']]
    except:
        return pd.DataFrame()

def load_data():
    try:
        df = conn.read(worksheet=0, ttl=0)
        if df.empty:
             return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])
        df = df.dropna(subset=['Date'])
        df['P_L_Amount'] = pd.to_numeric(df['P_L_Amount'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['ROI_Percent'] = pd.to_numeric(df['ROI_Percent'].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        return df
    except:
        return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])

df = load_data()
krx_list = get_krx_list()

# --- [스마트 검색] 종목명으로 코드 찾기 (포함 검색) ---
def find_ticker_smart(name):
    if krx_list.empty:
        return name, "목록 로딩 실패"
    
    # 1. 정확히 일치하는 경우
    exact = krx_list[krx_list['Name'] == name]
    if not exact.empty:
        row = exact.iloc[0]
        suffix = ".KS" if row['Market'] in ['KOSPI', 'KOSPI200'] else ".KQ"
        return row['Code'] + suffix, row['Name']
    
    # 2. 글자가 포함된 경우 (예: '삼성' -> '삼성전자' 검색)
    contains = krx_list[krx_list['Name'].str.contains(name, na=False)]
    if not contains.empty:
        # 가장 짧은 이름이 보통 대장주임 (예: '카카오' vs '카카오뱅크')
        best_match = contains.sort_values(by="Name", key=lambda x: x.str.len()).iloc[0]
        suffix = ".KS" if best_match['Market'] in ['KOSPI', 'KOSPI200'] else ".KQ"
        return best_match['Code'] + suffix, best_match['Name']
        
    return name, "검색 실패"

# --- [사이드바] 입력 ---
with st.sidebar.form("input", clear_on_submit=True):
    st.header("📝 매매 기록")
    date = st.date_input("일자", datetime.today())
    ticker = st.text_input("종목명 (예: 삼성전자)").strip()
    pn_l = st.number_input("손익금", value=0)
    roi = st.number_input("수익률(%)", value=0.0, format="%.2f")
    memo = st.text_input("메모")
    if st.form_submit_button("저장"):
        new_row = pd.DataFrame([{'Date': date.strftime('%Y-%m-%d'), 'Ticker': ticker, 'P_L_Amount': pn_l, 'ROI_Percent': roi, 'Memo': memo}])
        conn.update(worksheet=0, data=pd.concat([load_data(), new_row], ignore_index=True))
        st.success("저장 완료!"); st.rerun()

# --- [메인 화면] ---
st.title("💎 Trading Master Dashboard")

if not df.empty:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 차트", "📅 월별", "📆 연도별", "📋 원본", "❌ 오답노트"])
    
    # 데이터 전처리
    daily_df = df.groupby('Date')['P_L_Amount'].sum().reset_index().sort_values('Date')
    daily_df['Cumulative'] = daily_df['P_L_Amount'].cumsum()

    # === TAB 1: 차트 (수정: 선 그래프로 변경) ===
    with tab1:
        st.subheader("🚀 내 계좌 vs KOSPI")
        try:
            # KOSPI 지수 로딩
            start = daily_df['Date'].min().strftime('%Y-%m-%d')
            kospi = fdr.DataReader('KS11', start).reset_index()
            kospi = kospi[['Date', 'Close']]
            kospi.columns = ['Date', 'KOSPI']
            
            # [변경점] mark_area(면적) -> mark_line(선)으로 변경하여 깔끔하게!
            base = alt.Chart(daily_df).encode(x='Date:T')
            my_chart = base.mark_line(color='#00AA00', strokeWidth=3).encode(
                y=alt.Y('Cumulative:Q', title='내 수익 (원)'),
                tooltip=['Date', 'Cumulative']
            )
            
            market_chart = alt.Chart(kospi).mark_line(color='#FF4444', strokeWidth=2, strokeDash=[5,5]).encode(
                x='Date:T', 
                y=alt.Y('KOSPI:Q', title='KOSPI 지수', scale=alt.Scale(zero=False)),
                tooltip=['Date', 'KOSPI']
            )
            
            st.altair_chart(alt.layer(my_chart, market_chart).resolve_scale(y='independent'), use_container_width=True)
            st.caption("🟢 초록색 실선: 내 수익 / 🔴 빨간색 점선: KOSPI 지수")
            
        except Exception as e:
            st.line_chart(daily_df.set_index('Date')['Cumulative'])
            st.caption(f"차트 로딩 중 경미한 오류: {e}")

        # 지표 표시
        col1, col2, col3 = st.columns(3)
        col1.metric("총 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        col2.metric("승률", f"{(len(df[df['ROI_Percent']>0])/len(df)*100):.1f}%")
        col3.metric("평균 수익률", f"{df['ROI_Percent'].mean():.2f}%")

    # === TAB 2, 3, 4: 표 색상 오류 해결 ===
    with tab2:
        st.subheader("월별 분석")
        monthly = df.groupby(df['Date'].dt.strftime('%Y-%m'))['P_L_Amount'].sum().reset_index()
        st.bar_chart(monthly.set_index('Date'))
        
    with tab3:
        st.subheader("연도별 분석")
        yearly = df.groupby(df['Date'].dt.year)['P_L_Amount'].sum().reset_index()
        yearly.columns = ['Year', 'Total_PL']
        # matplotlib 설치 후 정상 작동하는 코드
        st.dataframe(yearly.style.format({"Total_PL": "{:,.0f}원"}).background_gradient(subset=['Total_PL'], cmap='Greens'), use_container_width=True)
        
    with tab4:
        st.dataframe(df.sort_values('Date', ascending=False))

    # === TAB 5: 오답 노트 (스마트 검색 적용) ===
    with tab5:
        st.subheader("🚩 오답 노트 & 차트 복기")
        # 손실 종목만 필터링
        losses = df[df['ROI_Percent'] < 0].sort_values('Date', ascending=False)
        
        if not losses.empty:
            c1, c2 = st.columns([1, 2])
            with c1:
                target_name = st.selectbox("종목 선택", losses['Ticker'].unique())
                row = losses[losses['Ticker'] == target_name].iloc[0]
                st.error(f"손익: {row['P_L_Amount']:,.0f}원 ({row['ROI_Percent']}%)")
                st.info(f"메모: {row['Memo']}")
                
            with c2:
                # [스마트 검색 실행]
                code, found_name = find_ticker_smart(target_name)
                
                if "실패" in found_name:
                    st.warning(f"'{target_name}' 종목 코드를 찾을 수 없습니다. 정확한 이름을 입력했는지 확인해주세요.")
                else:
                    st.success(f"🔍 검색 결과: **{found_name} ({code})**")
                    try:
                        # 차트 데이터 다운로드
                        chart_data = yf.download(code, start=(datetime.today()-timedelta(days=180)), progress=False)
                        if not chart_data.empty:
                            if isinstance(chart_data.columns, pd.MultiIndex):
                                close_data = chart_data.xs('Close', axis=1, level=0)
                            else:
                                close_data = chart_data['Close']
                            st.line_chart(close_data, color="#FF0000")
                        else:
                            st.warning("데이터가 없습니다. 상장 폐지되었거나 코드가 변경되었을 수 있습니다.")
                    except:
                        st.error("차트 데이터를 가져오는데 실패했습니다.")
        else:
            st.success("손실 난 종목이 없습니다! 훌륭합니다.")
else:
    st.info("데이터를 입력해주세요.")
