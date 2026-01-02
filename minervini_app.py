import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import altair as alt
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# 1. 페이지 설정
st.set_page_config(page_title="Trading Master Dashboard", page_icon="💎", layout="wide")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# --- [기능추가] 한국 종목 리스트 가져오기 (캐시 사용으로 속도 향상) ---
@st.cache_data(ttl=86400) # 하루에 한 번만 로딩
def get_krx_list():
    try:
        return fdr.StockListing('KRX')[['Code', 'Name', 'Market']]
    except:
        return pd.DataFrame()

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
krx_list = get_krx_list()

# --- [기능추가] 종목명으로 티커(코드) 찾는 함수 ---
def find_ticker(name):
    # 1. KRX 리스트에서 이름 검색
    if not krx_list.empty:
        target = krx_list[krx_list['Name'] == name]
        if not target.empty:
            code = target.iloc[0]['Code']
            market = target.iloc[0]['Market']
            suffix = ".KS" if market == 'KOSPI' else ".KQ"
            return code + suffix
    return name # 못 찾으면 입력한 그대로 반환

# --- [사이드바] 입력 양식 ---
st.sidebar.header("📝 매매 기록 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("일자", datetime.today())
    # 종목명 입력 시 한글로 써도 됨
    ticker = st.text_input("종목명 (예: 삼성전자)").strip() 
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
    # 탭 구성 (오답 노트 탭 추가)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 차트 대시보드", "📅 월별 분석", "📆 연도별 분석", "📋 데이터 원본", "❌ 오답 노트"])
    
    # 공통 계산
    df['Year'] = df['Date'].dt.year
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
    total_trades = len(df)
    wins = df[df['ROI_Percent'] > 0]
    losses = df[df['ROI_Percent'] <= 0]
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    
    # === TAB 1: 차트 대시보드 (KOSPI 연동 + 그래프 보정) ===
    with tab1:
        st.subheader("📍 Overall Performance")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("총 누적 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        kpi2.metric("승률 (Win Rate)", f"{win_rate:.1f}%")
        kpi3.metric("평균 수익률", f"{df['ROI_Percent'].mean():.2f}%")
        # 손익비 계산 (ZeroDivisionError 방지)
        avg_loss = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
        rr_ratio = (wins['ROI_Percent'].mean() / avg_loss) if avg_loss > 0 else 0
        kpi4.metric("평균 손익비", f"{rr_ratio:.2f}")
        
        st.divider()
        
        # [기능추가] 내 계좌 vs KOSPI 지수 (그래프 꼬임 방지 포함)
        st.subheader("🚀 내 계좌 vs KOSPI 지수")
        
        # 1. 날짜별 합산 (그래프 꼬임 방지)
        daily_df = df.groupby('Date')['P_L_Amount'].sum().reset_index().sort_values('Date')
        daily_df['Cumulative'] = daily_df['P_L_Amount'].cumsum()
        
        # 2. KOSPI 데이터 가져오기 (FinanceDataReader 사용)
        try:
            start_date_str = daily_df['Date'].min().strftime('%Y-%m-%d')
            kospi_df = fdr.DataReader('KS11', start_date_str).reset_index()
            # 컬럼명 통일
            kospi_df = kospi_df[['Date', 'Close']]
            kospi_df.columns = ['Date', 'KOSPI']
            
            # 차트 그리기 (Altair)
            base = alt.Chart(daily_df).encode(x='Date:T')
            my_chart = base.mark_area(opacity=0.3, color='green').encode(
                y=alt.Y('Cumulative:Q', title='내 수익 (원)'),
                tooltip=['Date', 'Cumulative']
            )
            
            market_chart = alt.Chart(kospi_df).mark_line(color='red').encode(
                x='Date:T', 
                y=alt.Y('KOSPI:Q', title='KOSPI 지수', scale=alt.Scale(zero=False)),
                tooltip=['Date', 'KOSPI']
            )
            
            combined_chart = alt.layer(my_chart, market_chart).resolve_scale(y='independent')
            st.altair_chart(combined_chart, use_container_width=True)
            
        except Exception as e:
            # KOSPI 로딩 실패 시 내 차트만 표시
            st.line_chart(daily_df.set_index('Date')['Cumulative'])

        # 월별 막대 그래프
        st.subheader("📊 월별 손익 흐름")
        monthly_sum = df.groupby('YearMonth')['P_L_Amount'].sum()
        st.bar_chart(monthly_sum)

    # === TAB 2, 3, 4: 기존 코드 유지 ===
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
                "기간": ym, "총 손익": group['P_L_Amount'].sum(), "거래수": f"{len(group)}회",
                "승률": f"{(len(g_wins)/len(group))*100:.1f}%", "평균수익": f"+{m_avg_gain:.2f}%",
                "평균손실": f"-{m_avg_loss:.2f}%", "손익비": f"{m_wl_ratio:.2f}"
            })
        m_df = pd.DataFrame(monthly_stats).sort_values("기간", ascending=False)
        st.dataframe(m_df.style.format({"총 손익": "{:,.0f}원"}), use_container_width=True)

    with tab3:
        st.subheader("📆 연도별 종합 성적표")
        yearly_stats = []
        for y, group in df.groupby('Year'):
            g_wins = group[group['ROI_Percent'] > 0]; g_losses = group[group['ROI_Percent'] <= 0]
            y_win_rate = (len(g_wins) / len(group)) * 100
            y_avg_gain = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
            y_avg_loss = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
            y_wl_ratio = y_avg_gain / y_avg_loss if y_avg_loss != 0 else 0
            y_pf = g_wins['P_L_Amount'].sum() / abs(g_losses['P_L_Amount'].sum()) if g_losses['P_L_Amount'].sum() != 0 else 0
            yearly_stats.append({
                "연도": y, "총 손익": group['P_L_Amount'].sum(), "총 거래수": f"{len(group)}회",
                "승률": f"{y_win_rate:.1f}%", "손익비": f"{y_wl_ratio:.2f}", "PF (프로핏팩터)": f"{y_pf:.2f}",
                "최고 수익": f"{group['ROI_Percent'].max():.2f}%"
            })
        y_df = pd.DataFrame(yearly_stats).sort_values("연도", ascending=False)
        st.dataframe(y_df.style.format({"총 손익": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='Greens'), use_container_width=True)

    with tab4:
        st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)

    # === [기능추가] TAB 5: 오답 노트 (자동 차트 연동) ===
    with tab5:
        st.subheader("🚩 실패한 매매 집중 분석 (오답 노트)")
        # 손실 난 기록만 필터링
        failed_trades = df[df['ROI_Percent'] < 0].sort_values('Date', ascending=False)
        
        if not failed_trades.empty:
            col_l, col_r = st.columns([1, 2])
            
            with col_l:
                st.write("📉 손실 종목 리스트")
                selected_name = st.selectbox("분석할 종목을 선택하세요", failed_trades['Ticker'].unique())
                
                # 선택한 종목의 매매 내역 표시
                ticker_detail = failed_trades[failed_trades['Ticker'] == selected_name]
                st.table(ticker_detail[['Date', 'ROI_Percent', 'P_L_Amount']])
                st.info(f"**메모:** {ticker_detail.iloc[0]['Memo']}")
            
            with col_r:
                # 여기서 [자동 종목 찾기] 기능이 실행됨
                real_ticker = find_ticker(selected_name)
                st.write(f"🔍 **{selected_name} ({real_ticker})** 차트 복기")
                
                try:
                    # 최근 6개월 차트 로딩
                    end_dt = datetime.today()
                    start_dt = end_dt - timedelta(days=180)
                    chart_data = yf.download(real_ticker, start=start_dt, end=end_dt, progress=False)
                    
                    if not chart_data.empty:
                        # yfinance 데이터 형식 호환성 처리
                        if isinstance(chart_data.columns, pd.MultiIndex):
                            chart_close = chart_data.xs('Close', axis=1, level=0)
                        else:
                            chart_close = chart_data['Close']
                            
                        st.line_chart(chart_close, color="#FF4B4B")
                        st.caption("💡 차트의 VCP 패턴과 매도 시점을 점검해보세요.")
                    else:
                        st.warning(f"차트를 불러올 수 없습니다. (검색된 코드: {real_ticker})")
                except Exception as e:
                    st.error("차트 로딩 중 오류가 발생했습니다.")
        else:
            st.balloons()
            st.success("🎉 손실 기록이 없습니다! 완벽한 트레이딩입니다.")

else:
    st.info("👈 사이드바에 첫 번째 매매 기록을 입력해보세요!")
