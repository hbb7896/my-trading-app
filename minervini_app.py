import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import altair as alt
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import random

# 1. 페이지 설정
st.set_page_config(page_title="Trading Master Dashboard", page_icon="💎", layout="wide")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 설정값 불러오기 ---
@st.cache_data(ttl=0)
def load_settings():
    try:
        df = conn.read(worksheet=1, ttl=0)
        if not df.empty: return df.iloc[0].to_dict()
    except: pass
    return {}

saved_config = load_settings()

# --- 한국 종목 리스트 ---
@st.cache_data(ttl=3600)
def get_krx_list():
    try:
        df = fdr.StockListing('KRX')
        return df[['Code', 'Name', 'Market']]
    except Exception as e:
        return pd.DataFrame()

# [오류 방지] 컬럼 목록 정의
REQUIRED_COLUMNS = [
    'Date', 'Ticker', 'Buy_Amount', 'Sell_Amount', 'P_L_Amount', 
    'ROI_Percent', 'Mistake_Tags', 'Emotion', 'Discipline', 'Memo'
]

def load_data():
    try:
        df = conn.read(worksheet=0, ttl=0)
        
        if df.empty:
             return pd.DataFrame(columns=REQUIRED_COLUMNS)
        
        df = df.dropna(subset=['Date'])
        
        # 숫자 변환
        num_cols = ['P_L_Amount', 'ROI_Percent', 'Buy_Amount', 'Sell_Amount']
        for col in num_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        # 데이터 복구 및 초기화
        if 'Buy_Amount' not in df.columns: df['Buy_Amount'] = 0.0
        if 'Sell_Amount' not in df.columns: df['Sell_Amount'] = 0.0
        
        mask = (df['Buy_Amount'] == 0) & (df['ROI_Percent'] != 0)
        df.loc[mask, 'Buy_Amount'] = (df.loc[mask, 'P_L_Amount'] / (df.loc[mask, 'ROI_Percent'] / 100)).abs()
        df.loc[mask, 'Sell_Amount'] = df.loc[mask, 'Buy_Amount'] + df.loc[mask, 'P_L_Amount']

        for col in ['Mistake_Tags', 'Emotion', 'Discipline', 'Memo']:
            if col not in df.columns: df[col] = None
        
        return df
    except:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

df = load_data()
krx_list = get_krx_list() 

# --- 사이드바 입력 ---
st.sidebar.header("📝 매매 기록 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("일자", datetime.today())
    ticker = st.text_input("종목명 (예: 삼성전자)").strip()
    
    st.markdown("---")
    
    # 1. 매수 금액 입력
    buy_amt = st.number_input("총 매수 금액 (원)", value=0, step=100000)
    
    # 2. 수익률 입력
    roi = st.number_input("수익률 (%)", value=0.0, format="%.2f")
    
    # 변수 초기화 및 자동 계산
    sell_amt = 0.0
    pn_l = 0.0

    if buy_amt != 0:
        pn_l = buy_amt * (roi / 100)
        sell_amt = buy_amt + pn_l
        
        # 계산 결과 미리보기
        st.info(f"""
        🧮 **자동 계산 결과**
        - 수익금: {pn_l:,.0f}원
        - 매도금액: {sell_amt:,.0f}원
        """)

    st.markdown("---")
    memo = st.text_input("메모 (특이사항 등)")
    
    if st.form_submit_button("기록 저장"):
        if ticker:
            new_data = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'), 
                'Ticker': ticker, 
                'Buy_Amount': buy_amt, 
                'Sell_Amount': sell_amt,
                'P_L_Amount': pn_l, 
                'ROI_Percent': roi, 
                'Mistake_Tags': None,
                'Emotion': None,
                'Discipline': None,
                'Memo': memo
            }])
            
            if df.empty: updated_df = new_data
            else:
                df_temp = load_data()
                df_temp['Date'] = df_temp['Date'].dt.strftime('%Y-%m-%d')
                updated_df = pd.concat([df_temp, new_data], ignore_index=True)
            conn.update(worksheet=0, data=updated_df)
            st.success(f"✅ {ticker} 저장 완료! (수익률 {roi:.2f}%)"); st.rerun()
        else: st.error("종목명을 입력해주세요.")

if krx_list.empty: st.sidebar.caption("⚠️ 리스트 로딩 실패")
else: st.sidebar.caption(f"✅ {len(krx_list):,}개 종목 연결됨")

# --- 메인 화면 ---
st.title("💎 Trading Master Dashboard")

if not df.empty:
    # 탭 구성: 총 10개
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
        "📊 차트", "📅 월별", "📆 연도별", "📋 원본", 
        "⚖️ 빅터 스페란데오", "🎯 R-배수 분석", "🧭 로드맵 점검", "🔔 손익 분포", "🔮 미너비니 시뮬레이터", "🚦 신호등 배팅"
    ])
    
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

    # === TAB 1: 차트 ===
    with tab1:
        st.subheader("🏆 전체 종합 성적표 (Total Legend)")
        total_pl = df['P_L_Amount'].sum()
        total_cnt = len(df)
        all_wins = df[df['ROI_Percent'] > 0]
        all_losses = df[df['ROI_Percent'] <= 0]
        
        gross_p = all_wins['P_L_Amount'].sum()
        gross_l = abs(all_losses['P_L_Amount'].sum())
        total_pf = gross_p / gross_l if gross_l > 0 else 0
        
        all_avg_profit_amt = all_wins['P_L_Amount'].mean() if not all_wins.empty else 0
        all_avg_loss_amt = abs(all_losses['P_L_Amount'].mean()) if not all_losses.empty else 0
        money_rr_ratio = all_avg_profit_amt / all_avg_loss_amt if all_avg_loss_amt > 0 else 0
        
        all_avg_profit_pct = all_wins['ROI_Percent'].mean() if not all_wins.empty else 0
        all_avg_loss_pct = abs(all_losses['ROI_Percent'].mean()) if not all_losses.empty else 0
        period_rr_ratio = all_avg_profit_pct / all_avg_loss_pct if all_avg_loss_pct > 0 else 0
        
        win_prob = (len(all_wins) / total_cnt) if total_cnt > 0 else 0
        loss_prob = 1 - win_prob
        expectancy = (win_prob * all_avg_profit_pct) - (loss_prob * all_avg_loss_pct)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 누적 총 손익", f"{total_pl:,.0f}원")
        m2.metric("🎯 전체 승률", f"{win_rate:.1f}%", help="총 매매 횟수 중 수익을 낸 매매의 비율입니다.")
        m3.metric("🔮 기간 기댓값 (Edge)", f"{expectancy:.2f}%", help="(승률 × 평균수익%) - (패율 × 평균손실%). 매매를 한 번 할 때마다 계좌가 평균적으로 몇 %씩 성장하는지 보여주는 '수학적 우위'입니다.")
        m4.metric("💎 Profit Factor", f"{total_pf:.2f}", help="총 이익금 ÷ 총 손실금. '번 돈이 잃은 돈보다 몇 배 많은가?'를 나타냅니다. 1.5 이상이면 훌륭하고, 3.0 이상이면 초고수입니다.")
        
        st.divider()
        st.markdown("##### 💵 금액(Money) 성적표 (배짱)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("평균 수익금", f"{all_avg_profit_amt:,.0f}원")
        c2.metric("평균 손실금", f"{all_avg_loss_amt:,.0f}원")
        c3.metric("⚖️ 금액 손익비", f"{money_rr_ratio:.2f}", delta="Good" if money_rr_ratio > 2 else "Bad" if money_rr_ratio < 1 else None, help="평균 수익금 ÷ 평균 손실금. 이 수치가 높다면 '이길 때 크게 베팅(불타기)'을 잘하고 있다는 뜻입니다.")
        c4.metric("🛒 총 매수 대금", f"{df['Buy_Amount'].sum():,.0f}원")

        st.markdown("##### 📊 기간(Technical) 성적표 (기술)")
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("평균 수익률", f"+{all_avg_profit_pct:.2f}%")
        c6.metric("평균 손실률", f"-{all_avg_loss_pct:.2f}%")
        c7.metric("⚖️ 기간 손익비", f"{period_rr_ratio:.2f}", delta="Good" if period_rr_ratio > 2 else "Bad" if period_rr_ratio < 1 else None, help="평균 수익률(%) ÷ 평균 손실률(%). 순수한 차트 분석 및 타점 능력을 보여줍니다.")
        c8.metric("📝 총 거래 횟수", f"{total_cnt:,}회")

        st.divider()
        st.subheader("🚀 내 계좌 vs KOSPI 지수")
        daily_df = df.groupby('Date')['P_L_Amount'].sum().reset_index().sort_values('Date')
        daily_df['Cumulative'] = daily_df['P_L_Amount'].cumsum()
        try:
            start = daily_df['Date'].min().strftime('%Y-%m-%d')
            kospi = yf.download("^KS11", start=start, progress=False)['Close'].reset_index()
            kospi.columns = ['Date', 'KOSPI']
            kospi['Date'] = pd.to_datetime(kospi['Date']).dt.tz_localize(None)
            base = alt.Chart(daily_df).encode(x='Date:T')
            my_chart = base.mark_line(color='#00AA00', strokeWidth=3).encode(y=alt.Y('Cumulative:Q', title='내 수익'), tooltip=['Date', 'Cumulative'])
            kospi_chart = alt.Chart(kospi).mark_line(color='#FF4444', strokeDash=[5,5]).encode(x='Date:T', y=alt.Y('KOSPI:Q', title='KOSPI', scale=alt.Scale(zero=False)))
            st.altair_chart(alt.layer(my_chart, kospi_chart).resolve_scale(y='independent'), use_container_width=True)
        except: st.line_chart(daily_df.set_index('Date')['Cumulative'])
        st.subheader("📊 월별 손익 흐름")
        st.bar_chart(df.groupby('YearMonth')['P_L_Amount'].sum())

    # === TAB 2: 월별 ===
    with tab2:
        st.subheader("📅 월별 상세 성적표")
        monthly_stats = []
        for ym, group in df.groupby('YearMonth'):
            g_wins = group[group['ROI_Percent'] > 0]; g_losses = group[group['ROI_Percent'] <= 0]
            gross_profit = group[group['P_L_Amount'] > 0]['P_L_Amount'].sum()
            gross_loss = abs(group[group['P_L_Amount'] <= 0]['P_L_Amount'].sum())
            m_avg_profit_amt = group[group['P_L_Amount'] > 0]['P_L_Amount'].mean() if not group[group['P_L_Amount'] > 0].empty else 0
            m_avg_loss_amt = group[group['P_L_Amount'] <= 0]['P_L_Amount'].mean() if not group[group['P_L_Amount'] <= 0].empty else 0
            pf = gross_profit / gross_loss if gross_loss > 0 else 0
            m_avg_gain_pct = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
            m_avg_loss_pct = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
            m_wl_ratio = m_avg_gain_pct / m_avg_loss_pct if m_avg_loss_pct > 0 else 0
            m_buy_vol = group['Buy_Amount'].sum()
            m_count = len(group)
            monthly_stats.append({"기간": str(ym), "총 손익": float(group['P_L_Amount'].sum()), "평균수익": float(m_avg_profit_amt), "평균손실": float(m_avg_loss_amt), "거래횟수": int(m_count), "승률": float((len(g_wins)/len(group))*100), "손익비": float(m_wl_ratio), "PF": float(pf), "매수총액": float(m_buy_vol)})
        st.dataframe(pd.DataFrame(monthly_stats).sort_values("기간", ascending=False).style.format({"총 손익": "{:,.0f}원", "평균수익": "{:,.0f}원", "평균손실": "{:,.0f}원", "거래횟수": "{:,}회", "승률": "{:.1f}%", "손익비": "{:.2f}", "PF": "{:.2f}", "매수총액": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='RdYlGn'), use_container_width=True)

    # === TAB 3: 연도별 ===
    with tab3:
        st.subheader("📆 연도별 종합 성적표")
        yearly_stats = []
        for y, group in df.groupby('Year'):
            g_wins = group[group['ROI_Percent'] > 0]; g_losses = group[group['ROI_Percent'] <= 0]
            gross_profit = group[group['P_L_Amount'] > 0]['P_L_Amount'].sum()
            gross_loss = abs(group[group['P_L_Amount'] <= 0]['P_L_Amount'].sum())
            y_avg_profit_amt = group[group['P_L_Amount'] > 0]['P_L_Amount'].mean() if not group[group['P_L_Amount'] > 0].empty else 0
            y_avg_loss_amt = group[group['P_L_Amount'] <= 0]['P_L_Amount'].mean() if not group[group['P_L_Amount'] <= 0].empty else 0
            pf = gross_profit / gross_loss if gross_loss > 0 else 0
            y_avg_gain_pct = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
            y_avg_loss_pct = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
            y_wl_ratio = y_avg_gain_pct / y_avg_loss_pct if y_avg_loss_pct > 0 else 0
            y_buy_vol = group['Buy_Amount'].sum()
            y_count = len(group)
            yearly_stats.append({"연도": int(y), "총 손익": float(group['P_L_Amount'].sum()), "평균수익": float(y_avg_profit_amt), "평균손실": float(y_avg_loss_amt), "거래횟수": int(y_count), "승률": float((len(g_wins)/len(group))*100), "손익비": float(y_wl_ratio), "PF": float(pf), "매수총액": float(y_buy_vol)})
        st.dataframe(pd.DataFrame(yearly_stats).sort_values("연도", ascending=False).style.format({"총 손익": "{:,.0f}원", "평균수익": "{:,.0f}원", "평균손실": "{:,.0f}원", "거래횟수": "{:,}회", "승률": "{:.1f}%", "손익비": "{:.2f}", "PF": "{:.2f}", "매수총액": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='Greens'), use_container_width=True)

    # === TAB 4: 원본 ===
    with tab4: st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)

    # === TAB 5: 빅터 스페란데오 ===
    with tab5:
        st.subheader("⚖️ Victor Sperandeo's Reward-to-Risk Analysis")
        st.markdown("> **\"최소 3:1의 보상 비율이 나오지 않는 거래는 시작조차 하지 마라.\"** - Victor Sperandeo")
        vic_period = st.radio("📅 분석 기간 선택", ["전체", "최근 1개월", "최근 3개월", "최근 6개월", "최근 1년"], horizontal=True, key="vic_radio")
        vic_df = df.copy()
        today = datetime.today()
        if vic_period == "최근 1개월": vic_df = vic_df[vic_df['Date'] >= (today - timedelta(days=30))]
        elif vic_period == "최근 3개월": vic_df = vic_df[vic_df['Date'] >= (today - timedelta(days=90))]
        elif vic_period == "최근 6개월": vic_df = vic_df[vic_df['Date'] >= (today - timedelta(days=180))]
        elif vic_period == "최근 1년": vic_df = vic_df[vic_df['Date'] >= (today - timedelta(days=365))]
        if not vic_df.empty:
            v_wins = vic_df[vic_df['ROI_Percent'] > 0]; v_losses = vic_df[vic_df['ROI_Percent'] <= 0]
            v_win_rate = (len(v_wins) / len(vic_df)) * 100
            v_avg_win = v_wins['ROI_Percent'].mean() if not v_wins.empty else 0
            v_avg_loss = abs(v_losses['ROI_Percent'].mean()) if not v_losses.empty else 0
            v_rr_ratio = v_avg_win / v_avg_loss if v_avg_loss > 0 else 0
            v_win_prob = v_win_rate / 100; v_loss_prob = 1 - v_win_prob
            v_expectancy = (v_win_prob * v_avg_win) - (v_loss_prob * v_avg_loss)
            st.caption(f"🔎 **{vic_period}** 데이터 기준 분석 ({len(vic_df)}건)")
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("기간 손익비 (R/R)", f"{v_rr_ratio:.2f} : 1", delta="목표 달성" if v_rr_ratio >= 3.0 else "목표 미달", help="빅터 스페란데오는 진입 전 기대 수익이 손절폭의 최소 3배 이상인 자리만 매매하라고 했습니다.")
            with c2: st.metric("기간 기댓값 (Edge)", f"{v_expectancy:.2f}%", help="이 매매 규칙을 계속 반복했을 때, 평균적으로 기대할 수 있는 수익률입니다.")
            with c3: st.metric("빅터의 목표 기준", "3.0 : 1", help="손실 1일 때, 수익 3을 목표로 한다는 뜻입니다.")
            st.divider()
            target_roi_period = v_avg_loss * 3 if v_avg_loss > 0 else 10
            conditions = [(vic_df['ROI_Percent'] >= target_roi_period), (vic_df['ROI_Percent'] > 0)]
            colors = ["#00CC00", "#F1C40F"]
            vic_df['Color_Hex'] = np.select(conditions, colors, default="#FF4B4B")
            scatter_chart = alt.Chart(vic_df).mark_circle(size=100).encode(x=alt.X('Date', title='거래 일자'), y=alt.Y('ROI_Percent', title='수익률 (%)'), color=alt.Color('Color_Hex', scale=None, legend=None), tooltip=['Ticker', 'Date', 'ROI_Percent', 'P_L_Amount']).interactive()
            rule_line = alt.Chart(pd.DataFrame({'y': [target_roi_period]})).mark_rule(color='blue', strokeDash=[3,3]).encode(y='y')
            st.altair_chart(scatter_chart + rule_line, use_container_width=True)
        else: st.info(f"📭 선택하신 **{vic_period}**에는 매매 기록이 없습니다.")

    # === TAB 6: R-배수 분석 ===
    with tab6:
        st.subheader("🎯 R-배수 분석 (The Real Score)")
        st.markdown("**'R'은 나의 위험(Risk) 단위입니다.**")
        r_period = st.radio("📅 분석 기간 선택", ["전체", "최근 1개월", "최근 3개월", "최근 6개월", "최근 1년"], horizontal=True, key="r_radio")
        r_df = df.copy()
        today = datetime.today()
        if r_period == "최근 1개월": r_df = r_df[r_df['Date'] >= (today - timedelta(days=30))]
        elif r_period == "최근 3개월": r_df = r_df[r_df['Date'] >= (today - timedelta(days=90))]
        elif r_period == "최근 6개월": r_df = r_df[r_df['Date'] >= (today - timedelta(days=180))]
        elif r_period == "최근 1년": r_df = r_df[r_df['Date'] >= (today - timedelta(days=365))]
        if not r_df.empty:
            r_losses = r_df[r_df['P_L_Amount'] < 0]
            if not r_losses.empty: avg_loss_abs = abs(r_losses['P_L_Amount'].mean())
            else: all_losses = df[df['P_L_Amount'] < 0]; avg_loss_abs = abs(all_losses['P_L_Amount'].mean()) if not all_losses.empty else 1
            r_df['R_Value'] = r_df['P_L_Amount'] / avg_loss_abs
            c1, c2, c3 = st.columns(3)
            c1.metric(f"나의 1R ({r_period})", f"{avg_loss_abs:,.0f}원", help="내가 한 번 손절할 때 잃는 평균 금액입니다. 이것을 '1R'이라는 위험 단위로 사용합니다.")
            c2.metric("평균 R-배수", f"{r_df['R_Value'].mean():.2f}R", help="수익을 냈을 때, 평소 손실금(1R)의 몇 배를 벌었는지 나타냅니다. 예를 들어 2R이면 '손절금의 2배를 벌었다'는 뜻입니다.")
            c3.metric("최고 R-배수", f"{r_df['R_Value'].max():.2f}R", help="기간 내 가장 크게 번 수익이 손절금의 몇 배인지 보여줍니다. 홈런의 크기입니다.")
            st.divider()
            df_sorted_r = r_df.sort_values('Date').copy()
            df_sorted_r['Cumulative_R'] = df_sorted_r['R_Value'].cumsum()
            df_sorted_r['Trade_Num'] = range(1, len(df_sorted_r) + 1)
            line_r = alt.Chart(df_sorted_r).mark_line(color='blue').encode(x=alt.X('Trade_Num', title='거래 횟수'), y=alt.Y('Cumulative_R', title='누적 R'), tooltip=['Date', 'R_Value', 'Cumulative_R'])
            st.altair_chart(line_r, use_container_width=True)
        else: st.info(f"📭 선택하신 **{r_period}**에는 매매 기록이 없습니다.")

    # === TAB 7: 로드맵 점검 ===
    with tab7:
        st.subheader("🧭 로드맵 이행 점검 (Roadmap Check)")
        st.markdown("**\"김 대리가 내준 3가지 숙제, 잘 하고 계십니까?\"**")
        st.caption("최근 10건의 매매(New)와 그 이전 매매(Old)를 비교 분석합니다.")
        df_sorted = df.sort_values('Date', ascending=False)
        if len(df_sorted) < 5: st.warning("⚠️ 분석할 데이터가 부족합니다. 최소 5건 이상 매매 후 확인해주세요.")
        else:
            recent_n = 10; df_recent = df_sorted.head(recent_n); df_old = df_sorted.iloc[recent_n:]
            if df_old.empty: df_old = df_recent
            st.markdown("### 1️⃣ 숙제 1: 손절 다이어트 (목표: -4% 이내)")
            recent_losses = df_recent[df_recent['ROI_Percent'] < 0]; old_losses = df_old[df_old['ROI_Percent'] < 0]
            r_avg_loss = recent_losses['ROI_Percent'].mean() if not recent_losses.empty else 0.0
            o_avg_loss = old_losses['ROI_Percent'].mean() if not old_losses.empty else 0.0
            col1, col2, col3 = st.columns(3)
            col1.metric("과거 평균 손실", f"{o_avg_loss:.2f}%")
            col2.metric("최근 평균 손실 (New)", f"{r_avg_loss:.2f}%", delta=f"{r_avg_loss - o_avg_loss:.2f}%p" if r_avg_loss > o_avg_loss else None)
            with col3:
                if r_avg_loss >= -4.5: st.success("✅ **합격!** 아주 훌륭합니다.")
                elif r_avg_loss > -6.0: st.warning("⚠️ **노력 요함** 조금만 더 줄이세요.")
                else: st.error("❌ **불합격** 아직도 손절이 큽니다.")
            st.divider()
            st.markdown("### 2️⃣ 숙제 2: 선구안 개선 (A급 패턴만)")
            r_win_rate = (len(df_recent[df_recent['ROI_Percent'] > 0]) / len(df_recent)) * 100
            o_win_rate = (len(df_old[df_old['ROI_Percent'] > 0]) / len(df_old)) * 100
            c1, c2, c3 = st.columns(3)
            c1.metric("과거 승률", f"{o_win_rate:.1f}%")
            c2.metric("최근 승률 (New)", f"{r_win_rate:.1f}%", f"{r_win_rate - o_win_rate:.1f}%p")
            with c3:
                if r_win_rate >= 40: st.success("✅ **나이스!** 기다림의 미학을 아시는군요.")
                elif r_win_rate >= o_win_rate: st.info("🆗 **유지 중** 나쁘지 않습니다.")
                else: st.error("❌ **뇌동매매 주의** 아무 공이나 휘두르고 계십니다.")
            st.divider()
            st.markdown("### 3️⃣ 숙제 3: 홈런 본능 (불타기 & 홀딩)")
            recent_wins = df_recent[df_recent['ROI_Percent'] > 0]
            r_max_win = recent_wins['ROI_Percent'].max() if not recent_wins.empty else 0
            r_avg_win = recent_wins['ROI_Percent'].mean() if not recent_wins.empty else 0
            k1, k2 = st.columns(2)
            k1.metric("최근 최고 수익률 (홈런)", f"+{r_max_win:.2f}%")
            k2.metric("최근 평균 익절폭", f"+{r_avg_win:.2f}%")
            if r_max_win > 15: st.success("🔥 **[Perfect]** 역시 홈런 타자! 추세를 제대로 탔습니다.")
            elif r_max_win > 8: st.info("👍 **[Good]** 적당한 2루타입니다. 조금만 더 욕심내보세요.")
            else: st.warning("먹을 때 너무 짧게 먹습니다. (불타기 부족)")
            st.divider()
            score = 0
            if r_avg_loss >= -4.5: score += 1
            if r_win_rate >= 40 or r_win_rate > o_win_rate: score += 1
            if r_max_win > 10: score += 1
            final_msg = ""
            if score == 3: final_msg = "🏆 **[트레이딩 마스터]** 김 대리의 하산 허락이 임박했습니다!"
            elif score == 2: final_msg = "🏃 **[성장 중]** 아주 잘하고 계십니다. 하나만 더 고칩시다."
            else: final_msg = "🐢 **[분발하세요]** 아직 습관이 안 고쳐졌습니다. 원칙을 다시 읽으세요."
            st.subheader(f"종합 판정: {final_msg}")

    # === TAB 8: 손익 분포 ===
    with tab8:
        st.subheader("🔔 손익 분포 (Profit/Loss Distribution)")
        st.markdown("**\"왼쪽(손실)은 짧게, 오른쪽(수익)은 길게! 이것이 이상적인 곡선입니다.\"**")
        bin_step = 2.5; df_dist = df.copy()
        hist_chart = alt.Chart(df_dist).mark_bar().encode(
            x=alt.X('ROI_Percent', bin=alt.Bin(step=bin_step), title='수익률 구간 (%)'),
            y=alt.Y('count()', title='거래 횟수'),
            color=alt.condition(alt.datum.ROI_Percent > 0, alt.value("#00AA00"), alt.value("#FF4444")),
            tooltip=['count()', alt.Tooltip('ROI_Percent', bin=True, title='수익률 구간')]
        ).properties(height=400)
        rule = alt.Chart(pd.DataFrame({'x': [0]})).mark_rule(color='black', strokeDash=[2,2]).encode(x='x')
        st.altair_chart(hist_chart + rule, use_container_width=True)
        skew = df['ROI_Percent'].skew()
        st.info(f"📊 **분포도 분석 (Skewness: {skew:.2f})**")
        if skew > 0.5: st.success("✅ **[Positive Skew]** 아주 훌륭합니다! 꼬리가 오른쪽(수익)으로 길게 뻗은 이상적인 형태입니다.")
        elif skew < -0.5: st.error("🚨 **[Negative Skew]** 위험합니다! 왼쪽(손실) 꼬리가 더 깁니다. 큰 손실 한 방을 조심하세요.")
        else: st.warning("⚠️ **[Symmetric]** 수익과 손실 패턴이 비슷합니다. '손실은 짧게' 원칙을 더 지켜야 합니다.")

    # === TAB 9: 미너비니 시뮬레이터 ===
    with tab9:
        st.subheader("🔮 미너비니 시뮬레이터 (Result-Based Assumption Forecast)")
        st.markdown("**\"목표 금액 달성까지, 몇 번의 매매가 남았을까요?\"**")
        st.caption("출처: 마크 미너비니 <초수익 성장주 투자> '결과 기반 가정 예측'")
        with st.container(border=True):
            st.markdown("#### 1️⃣ 가정 입력 (Assumptions)")
            def_win_rate = float(win_rate) if not np.isnan(win_rate) else 40.0
            def_avg_gain = float(avg_win) if not np.isnan(avg_win) and avg_win > 0 else 10.0
            def_avg_loss = float(avg_loss) if not np.isnan(avg_loss) and avg_loss > 0 else 5.0
            c_in1, c_in2, c_in3 = st.columns(3)
            with c_in1: sim_portfolio = st.number_input("💰 현재 포트폴리오 (Seed)", value=16000000, step=1000000); sim_pos_size_pct = st.number_input("📊 포지션 규모 (%)", value=25.0, step=5.0) / 100
            with c_in2: sim_target_return = st.number_input("🎯 목표 수익률 (%)", value=40.0, step=5.0) / 100; sim_target_amt = sim_portfolio * sim_target_return; st.caption(f"목표 수익금: +{sim_target_amt:,.0f}원")
            with c_in3: sim_win_rate = st.number_input("🎯 승률 (Win Rate %)", value=def_win_rate, step=1.0) / 100; sim_avg_gain = st.number_input("📈 평균 수익 (Avg Gain %)", value=def_avg_gain, step=0.5) / 100; sim_avg_loss = st.number_input("📉 평균 손실 (Avg Loss %)", value=def_avg_loss, step=0.5) / 100
        sim_pos_money = sim_portfolio * sim_pos_size_pct
        sim_loss_rate = 1 - sim_win_rate
        sim_net_exp_pct = (sim_win_rate * sim_avg_gain) - (sim_loss_rate * sim_avg_loss)
        sim_net_exp_money = sim_pos_money * sim_net_exp_pct
        if sim_net_exp_money > 0: trades_needed = sim_target_amt / sim_net_exp_money
        else: trades_needed = float('inf')
        st.divider()
        st.markdown("#### 2️⃣ 시뮬레이션 결과 (Forecast Result)")
        res_col1, res_col2 = st.columns(2)
        with res_col1:
            st.write("📊 **거래별 기대 성과**")
            st.markdown(f"* **포지션 투입금:** {sim_pos_money:,.0f}원\n* **수익 거래 시 평균 수익:** +{sim_pos_money * sim_avg_gain:,.0f}원\n* **손실 거래 시 평균 손실:** -{sim_pos_money * sim_avg_loss:,.0f}원\n* **손익비 (Reward/Risk):** {sim_avg_gain/sim_avg_loss:.2f} : 1")
        with res_col2:
            st.write("💎 **최종 예측 (The Forecast)**")
            if sim_net_exp_money > 0:
                st.metric("1회 거래당 순기대수익 (Edge)", f"{sim_net_exp_pct*100:.2f}% ({sim_net_exp_money:,.0f}원)", help="현재 승률과 손익비를 유지한다고 가정할 때, 한 번 매매할 때마다 계좌가 불어나는 평균 금액입니다.")
                st.success(f"### 🏁 목표 달성까지: **약 {int(trades_needed)+1} 회** 거래 필요")
                st.caption("※ 현재의 승률과 손익비를 **꾸준히 유지한다**는 가정하에 계산된 결과입니다.")
            else:
                st.error("🚨 **[경고] 기대값이 마이너스입니다!**")
                st.markdown("현재 통계로는 아무리 매매해도 계좌가 줄어듭니다. **승률**을 높이거나 **손익비**를 개선하세요.")

    # === TAB 10: 배팅 규모 계산기 (Progressive Exposure) ===
    with tab10:
        st.subheader("🚦 신호등 배팅 (Progressive Exposure)")
        st.markdown("**\"최근 전적에 따라 이번 배팅 금액을 정해드립니다. (신호등 시스템)\"**")
        
        # 1. 설정값 입력
        with st.expander("⚙️ 기본 설정 (내 자산 세팅)", expanded=True):
            col_set1, col_set2 = st.columns(2)
            with col_set1:
                my_total_equity = st.number_input("💰 나의 총 자산 (Equity)", value=20000000, step=1000000, 
                                                  help="주식 계좌에 있는 총 예수금+주식 평가액입니다.")
            with col_set2:
                my_max_position = st.number_input("🎯 종목당 최대 배팅금 (Max)", value=5000000, step=500000,
                                                  help="가장 확실할 때(초록불) 들어갈 최대 금액입니다. 보통 자산의 25%를 잡습니다.")

        # 2. 시뮬레이션 버튼
        st.divider()
        st.markdown("#### 👇 최근 매매 결과를 눌러주세요")
        
        # 세션 상태 초기화 (기록 저장용)
        if 'trade_streak' not in st.session_state:
            st.session_state.trade_streak = [] # 0: Loss, 1: Win

        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("🟢 수익 (WIN)", use_container_width=True):
                st.session_state.trade_streak.append("WIN")
        with col_btn2:
            if st.button("🔴 손실 (LOSS)", use_container_width=True):
                st.session_state.trade_streak.append("LOSS")
        with col_btn3:
            if st.button("🔄 기록 초기화", use_container_width=True):
                st.session_state.trade_streak = []

        # 3. 로직 계산 (신호등)
        history = st.session_state.trade_streak
        current_status = "READY"
        rec_percent = 0
        rec_money = 0
        
        if not history:
            current_status = "NEUTRAL"
            rec_percent = 0.25 # 요청대로 1/4 (25%) 시작
        else:
            last_trade = history[-1]
            
            if last_trade == "LOSS":
                current_status = "RED" # 빨간불 (방어)
                rec_percent = 0.25
            elif last_trade == "WIN":
                if len(history) >= 2 and history[-2] == "WIN":
                    current_status = "GREEN" # 초록불 (공격)
                    rec_percent = 1.0
                else:
                    current_status = "YELLOW" # 노란불 (경계/준비)
                    rec_percent = 0.50

        rec_money = int(my_max_position * rec_percent)

        # 4. 결과 디스플레이
        st.divider()
        st.write(f"📜 **최근 기록:** {' → '.join(history[-5:])}") # 최근 5개만 보여줌
        
        if current_status == "GREEN":
            st.success(f"""
            ### 🟢 **[초록불] 공격 모드 (Full Size)**
            **"감이 좋습니다! 물 들어올 때 노 저으세요."**
            
            # **{rec_money:,.0f} 원** 투입
            (최대 배팅금의 **100%**)
            """)
        elif current_status == "YELLOW":
            st.warning(f"""
            ### 🟡 **[노란불] 경계 모드 (Half Size)**
            **"나쁘지 않지만, 아직 확신하긴 이릅니다. 절반만 들어갑니다."**
            
            # **{rec_money:,.0f} 원** 투입
            (최대 배팅금의 **50%**)
            """)
        elif current_status == "RED":
            st.error(f"""
            ### 🔴 **[빨간불] 방어 모드 (Pilot Size)**
            **"조심하세요! 최근 손실이 있었습니다. 정찰병만 보냅니다."**
            
            # **{rec_money:,.0f} 원** 투입
            (최대 배팅금의 **25%**)
            """)
        else:
            st.info(f"""
            ### ⚪ **[준비] 시작 모드**
            **"첫 진입입니다. 가볍게 정찰병(1/4)부터 보냅시다."**
            
            # **{rec_money:,.0f} 원** 투입
            (최대 배팅금의 **25%**)
            """)

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")
