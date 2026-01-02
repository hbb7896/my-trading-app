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

# --- 한국 종목 리스트 가져오기 ---
@st.cache_data(ttl=86400)
def get_krx_list():
    try:
        return fdr.StockListing('KRX')[['Code', 'Name', 'Market']]
    except:
        return pd.DataFrame()

# --- 스마트 종목 검색 함수 ---
def find_ticker_smart(name, krx_list):
    if krx_list.empty: return name, "목록 로딩 실패"
    
    # 1. 정확히 일치
    exact = krx_list[krx_list['Name'] == name]
    if not exact.empty:
        row = exact.iloc[0]
        suffix = ".KS" if row['Market'] in ['KOSPI', 'KOSPI200'] else ".KQ"
        return row['Code'] + suffix, row['Name']
    
    # 2. 포함된 글자 검색
    contains = krx_list[krx_list['Name'].str.contains(name, na=False)]
    if not contains.empty:
        best = contains.sort_values(by="Name", key=lambda x: x.str.len()).iloc[0]
        suffix = ".KS" if best['Market'] in ['KOSPI', 'KOSPI200'] else ".KQ"
        return best['Code'] + suffix, best['Name']
        
    return name, "검색 실패"

# --- 마크 미너비니 PF 점수표 표시 함수 ---
def show_pf_guide():
    with st.expander("ℹ️ 마크 미너비니의 PF(프로핏 팩터) 점수표 보기", expanded=False):
        st.markdown("""
        ### 📊 트레이딩 시스템 등급표
        | PF 범위 | 상태 | 평가 |
        | :--- | :--- | :--- |
        | **1.0 이하** | 🚨 위험 | 손실이 더 큰 상태 (시스템 점검 필수) |
        | **1.0 ~ 1.5** | ⚠️ 주의 | 겨우 본전이거나 약간 수익 (개선 필요) |
        | **1.5 ~ 2.0** | 👍 훌륭함 | 아주 훌륭한 시스템 (안정적 수익 구간) |
        | **3.0 이상** | 💎 전설 | 마크 미너비니급 초고수 (Legendary) |
        """)
        st.caption("※ 목표: 승률이 낮더라도 손익비를 높여서 **PF 2.0 이상**을 유지하세요.")

def load_data():
    try:
        df = conn.read(worksheet=0, ttl=0)
        if df.empty:
             return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])
        
        df = df.dropna(subset=['Date'])
        
        if 'P_L_Amount' in df.columns:
            df['P_L_Amount'] = df['P_L_Amount'].astype(str).str.replace(',', '')
            df['P_L_Amount'] = pd.to_numeric(df['P_L_Amount'], errors='coerce').fillna(0)
        
        if 'ROI_Percent' in df.columns:
            df['ROI_Percent'] = df['ROI_Percent'].astype(str).str.replace('%', '')
            df['ROI_Percent'] = pd.to_numeric(df['ROI_Percent'], errors='coerce').fillna(0)
        
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        return df
    except Exception as e:
        return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Memo'])

df = load_data()
krx_list = get_krx_list() 

# --- [사이드바] 입력 양식 ---
st.sidebar.header("📝 매매 기록 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("일자", datetime.today())
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 차트 대시보드", "📅 월별 분석", "📆 연도별 분석", "📋 데이터 원본", "❌ 오답 노트"])
    
    # 공통 계산
    df['Year'] = df['Date'].dt.year
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
    
    total_trades = len(df)
    wins = df[df['ROI_Percent'] > 0]
    losses = df[df['ROI_Percent'] <= 0]
    
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    avg_win = wins['ROI_Percent'].mean() if not wins.empty else 0
    avg_loss = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
    risk_reward_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    avg_roi = df['ROI_Percent'].mean()

    # === TAB 1: 차트 대시보드 ===
    with tab1:
        st.subheader("📍 Overall Performance")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("총 누적 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        kpi2.metric("승률 (Win Rate)", f"{win_rate:.1f}%")
        kpi3.metric("평균 수익률", f"{avg_roi:.2f}%")
        kpi4.metric("평균 손익비", f"{risk_reward_ratio:.2f}")
        
        st.divider()
        st.subheader("🚀 내 계좌 vs KOSPI 지수")
        
        daily_df = df.groupby('Date')['P_L_Amount'].sum().reset_index().sort_values('Date')
        daily_df['Cumulative'] = daily_df['P_L_Amount'].cumsum()
        
        try:
            start_date_str = daily_df['Date'].min().strftime('%Y-%m-%d')
            kospi = fdr.DataReader('KS11', start_date_str).reset_index()
            kospi = kospi[['Date', 'Close']]
            kospi.columns = ['Date', 'KOSPI']
            
            base = alt.Chart(daily_df).encode(x='Date:T')
            my_chart = base.mark_line(color='#00AA00', strokeWidth=3).encode(
                y=alt.Y('Cumulative:Q', title='내 누적 수익 (원)'),
                tooltip=['Date', 'Cumulative']
            )
            kospi_chart = alt.Chart(kospi).mark_line(color='#FF4444', strokeDash=[5,5]).encode(
                x='Date:T',
                y=alt.Y('KOSPI:Q', title='KOSPI 지수', scale=alt.Scale(zero=False)),
                tooltip=['Date', 'KOSPI']
            )
            st.altair_chart(alt.layer(my_chart, kospi_chart).resolve_scale(y='independent'), use_container_width=True)
            
        except Exception as e:
            st.line_chart(daily_df.set_index('Date')['Cumulative'])

        st.subheader("📊 월별 손익 흐름")
        monthly_sum = df.groupby('YearMonth')['P_L_Amount'].sum()
        st.bar_chart(monthly_sum)

    # === TAB 2: 월별 상세 분석 ===
    with tab2:
        st.subheader("📅 월별 상세 성적표")
        monthly_stats = []
        for ym, group in df.groupby('YearMonth'):
            g_wins = group[group['ROI_Percent'] > 0]
            g_losses = group[group['ROI_Percent'] <= 0]
            
            # [수정완료] 잘렸던 코드를 완벽하게 복구했습니다
            gross_profit = group[group['P_L_Amount'] > 0]['P_L_Amount'].sum()
            gross_loss = abs(group[group['P_L_Amount'] <= 0]['P_L_Amount'].sum())
            pf = gross_profit / gross_loss if gross_loss > 0 else 0
            
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
                "손익비": f"{m_wl_ratio:.2f}",
                "PF": f"{pf:.2f}"
            })
        m_df = pd.DataFrame(monthly_stats).sort_values("기간", ascending=False)
        st.dataframe(m_df.style.format({"총 손익": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='RdYlGn', vmin=-100000, vmax=100000), use_container_width=True)
        
        show_pf_guide()

    # === TAB 3: 연도별 분석 ===
    with tab3:
        st.subheader("📆 연도별 종합 성적표")
        yearly_stats = []
        for y, group in df.groupby('Year'):
            g_wins = group[group['ROI_Percent'] > 0]; g_losses = group[group['ROI_Percent'] <= 0]
            y_win_rate = (len(g_wins) / len(group)) * 100
            y_avg_gain = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
            y_avg_loss = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
            y_wl_ratio = y_avg_gain / y_avg_loss if y_avg_loss != 0 else 0
            y_profit_factor = g_wins['P_L_Amount'].sum() / abs(g_losses['P_L_Amount'].sum()) if g_losses['P_L_Amount'].sum() != 0 else 0
            
            yearly_stats.append({
                "연도": y, "총 손익": group['P_L_Amount'].sum(), "총 거래수": f"{len(group)}회",
                "승률": f"{y_win_rate:.1f}%", "손익비": f"{y_wl_ratio:.2f}", "PF": f"{y_profit_factor:.2f}"
            })
        y_df = pd.DataFrame(yearly_stats).sort_values("연도", ascending=False)
        st.dataframe(y_df.style.format({"총 손익": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='Greens'), use_container_width=True)
        
        show_pf_guide()

    # === TAB 4: 데이터 원본 ===
    with tab4:
        st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)

    # === TAB 5: 오답 노트 ===
    with tab5:
        st.subheader("🚩 오답 노트 & 차트 복기")
        losses = df[df['ROI_Percent'] < 0].sort_values('Date', ascending=False)
        
        if not losses.empty:
            c1, c2 = st.columns([1, 2])
            with c1:
                target_name = st.selectbox("손실 종목 선택", losses['Ticker'].unique())
                row = losses[losses['Ticker'] == target_name].iloc[0]
                st.error(f"손익: {row['P_L_Amount']:,.0f}원 ({row['ROI_Percent']}%)")
                st.info(f"메모: {row['Memo']}")
                
            with c2:
                code, found_name = find_ticker_smart(target_name, krx_list)
                if "실패" in found_name:
                    st.warning(f"'{target_name}' 코드를 못 찾았습니다.")
                else:
                    st.success(f"🔍 검색: **{found_name} ({code})**")
                    try:
                        chart_data = yf.download(code, start=(datetime.today()-timedelta(days=180)), progress=False)
                        if not chart_data.empty:
                            if isinstance(chart_data.columns, pd.MultiIndex):
                                close_data = chart_data.xs('Close', axis=1, level=0)
                            else:
                                close_data = chart_data['Close']
                            st.line_chart(close_data, color="#FF0000")
                        else:
                            st.warning("차트 데이터가 없습니다.")
                    except:
                        st.error("차트 로딩 실패")
        else:
            st.success("손실 기록이 없습니다! 훌륭합니다.")

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")

