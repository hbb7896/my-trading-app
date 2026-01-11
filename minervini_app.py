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

# --- PF 가이드 ---
def show_pf_guide():
    with st.expander("ℹ️ 마크 미너비니의 PF(프로핏 팩터) 점수표 보기", expanded=False):
        st.markdown("""
        | PF 범위 | 상태 | 평가 |
        | :--- | :--- | :--- |
        | **1.0 이하** | 🚨 위험 | 손실이 더 큰 상태 |
        | **1.5 ~ 2.0** | 👍 훌륭함 | 안정적 수익 구간 |
        | **3.0 이상** | 💎 전설 | 초고수 (Legendary) |
        """)

# [수정] 오류 방지를 위해 컬럼 목록을 별도 변수로 정의
REQUIRED_COLUMNS = [
    'Date', 'Ticker', 'Buy_Amount', 'Sell_Amount', 'P_L_Amount', 
    'ROI_Percent', 'Mistake_Tags', 'Emotion', 'Discipline', 'Memo'
]

def load_data():
    try:
        df = conn.read(worksheet=0, ttl=0)
        
        # 데이터가 없으면 빈 프레임 반환
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
        
        # 매수금액 역산 로직
        mask = (df['Buy_Amount'] == 0) & (df['ROI_Percent'] != 0)
        df.loc[mask, 'Buy_Amount'] = (df.loc[mask, 'P_L_Amount'] / (df.loc[mask, 'ROI_Percent'] / 100)).abs()
        df.loc[mask, 'Sell_Amount'] = df.loc[mask, 'Buy_Amount'] + df.loc[mask, 'P_L_Amount']

        if 'Mistake_Tags' not in df.columns: df['Mistake_Tags'] = None
        if 'Emotion' not in df.columns: df['Emotion'] = None
        if 'Discipline' not in df.columns: df['Discipline'] = None
        
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
    buy_amt = st.number_input("총 매수 금액 (원)", value=0, step=100000)
    pn_l = st.number_input("실현 손익금 (원)", value=0, step=10000)
    roi = st.number_input("수익률 (%)", value=0.0, format="%.2f")
    
    if buy_amt != 0:
        st.caption(f"💡 예상 매도 금액: {buy_amt + pn_l:,.0f}원")
    
    st.divider()
    st.caption("🧠 습관 분석")
    mistake_options = ["정상매매", "뇌동매매", "추격매수", "손절늦음", "익절너무빠름", "시장하락", "비중위반"]
    tags = st.multiselect("매매 특이사항", mistake_options, default=["정상매매"])
    tags_str = ", ".join(tags)
    emotion = st.selectbox("매수 당시 감정", ["평온함", "흥분/조급함(FOMO)", "공포", "복수심(화남)", "지루함"])
    discipline = st.radio("원칙을 지켰습니까?", ["Yes (잘한 매매)", "No (반성 필요)"], horizontal=True)
    memo = st.text_input("메모")
    
    if st.form_submit_button("기록 저장"):
        if ticker:
            sell_amt = buy_amt + pn_l
            new_data = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'), 'Ticker': ticker, 'Buy_Amount': buy_amt, 'Sell_Amount': sell_amt,
                'P_L_Amount': pn_l, 'ROI_Percent': roi, 'Mistake_Tags': tags_str, 'Emotion': emotion, 'Discipline': discipline, 'Memo': memo
            }])
            if df.empty: updated_df = new_data
            else:
                df_temp = load_data()
                df_temp['Date'] = df_temp['Date'].dt.strftime('%Y-%m-%d')
                updated_df = pd.concat([df_temp, new_data], ignore_index=True)
            conn.update(worksheet=0, data=updated_df)
            st.success(f"✅ {ticker} 저장 완료!"); st.rerun()
        else: st.error("종목명을 입력해주세요.")

if krx_list.empty: st.sidebar.caption("⚠️ 리스트 로딩 실패")
else: st.sidebar.caption(f"✅ {len(krx_list):,}개 종목 연결됨")

# --- 메인 화면 ---
st.title("💎 Trading Master Dashboard")

if not df.empty:
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 차트", "📅 월별", "📆 연도별", "📋 원본", "⚖️ 빅터 스페란데오", "🧮 수익쿠션"])
    
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
        st.subheader("📍 Overall Performance")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("총 누적 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        kpi2.metric("승률", f"{win_rate:.1f}%")
        kpi3.metric("평균 수익률", f"{avg_roi:.2f}%")
        kpi4.metric("평균 손익비", f"{risk_reward_ratio:.2f}")
        
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
            pf = gross_profit / gross_loss if gross_loss > 0 else 0
            m_avg_gain = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
            m_avg_loss = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
            m_wl_ratio = m_avg_gain / m_avg_loss if m_avg_loss > 0 else 0
            m_buy_vol = group['Buy_Amount'].sum()
            
            monthly_stats.append({
                "기간": str(ym), "총 손익": float(group['P_L_Amount'].sum()), "승률": float((len(g_wins)/len(group))*100), 
                "손익비": float(m_wl_ratio), "PF": float(pf), "매수총액": float(m_buy_vol)
            })
        st.dataframe(pd.DataFrame(monthly_stats).sort_values("기간", ascending=False).style.format({"총 손익": "{:,.0f}원", "승률": "{:.1f}%", "손익비": "{:.2f}", "PF": "{:.2f}", "매수총액": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='RdYlGn'), use_container_width=True)
        show_pf_guide()

    # === TAB 3: 연도별 ===
    with tab3:
        st.subheader("📆 연도별 종합 성적표")
        yearly_stats = []
        for y, group in df.groupby('Year'):
            g_wins = group[group['ROI_Percent'] > 0]; g_losses = group[group['ROI_Percent'] <= 0]
            gross_profit = group[group['P_L_Amount'] > 0]['P_L_Amount'].sum()
            gross_loss = abs(group[group['P_L_Amount'] <= 0]['P_L_Amount'].sum())
            pf = gross_profit / gross_loss if gross_loss > 0 else 0
            y_avg_gain = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
            y_avg_loss = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
            y_wl_ratio = y_avg_gain / y_avg_loss if y_avg_loss > 0 else 0
            y_buy_vol = group['Buy_Amount'].sum()
            
            yearly_stats.append({
                "연도": int(y), "총 손익": float(group['P_L_Amount'].sum()), "승률": float((len(g_wins)/len(group))*100), 
                "손익비": float(y_wl_ratio), "PF": float(pf), "매수총액": float(y_buy_vol)
            })
        st.dataframe(pd.DataFrame(yearly_stats).sort_values("연도", ascending=False).style.format({"총 손익": "{:,.0f}원", "승률": "{:.1f}%", "손익비": "{:.2f}", "PF": "{:.2f}", "매수총액": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='Greens'), use_container_width=True)
        show_pf_guide()

    # === TAB 4: 원본 ===
    with tab4: st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)

    # === [NEW] TAB 5: 빅터 스페란데오 분석 ===
    with tab5:
        st.subheader("⚖️ Victor Sperandeo's Reward-to-Risk Analysis")
        st.markdown("> **\"최소 3:1의 보상 비율이 나오지 않는 거래는 시작조차 하지 마라.\"** - Victor Sperandeo")
        
        # 1. 계산 (승률, 기댓값, RR)
        win_prob = win_rate / 100
        loss_prob = 1 - win_prob
        # 기댓값 = (승률 * 평균수익) - (패율 * 평균손실)
        expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)
        
        # 2. 메트릭 표시
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "현재 계좌 손익비 (R/R)", 
                f"{risk_reward_ratio:.2f} : 1",
                delta="목표 달성 (3:1 이상)" if risk_reward_ratio >= 3.0 else f"목표 미달 (-{3.0 - risk_reward_ratio:.2f})",
                delta_color="normal" if risk_reward_ratio >= 3.0 else "inverse"
            )
            
        with col2:
            st.metric(
                "거래당 기댓값 (Edge)", 
                f"{expectancy:.2f}%",
                help="한 번 거래할 때마다 통계적으로 기대할 수 있는 수익률입니다. 양수여야 계좌가 우상향합니다."
            )
            
        with col3:
            st.metric("빅터의 목표 기준", "3.0 : 1")
            
        st.divider()
        
        # 3. 빅터 스페란데오 차트 (3:1 가이드라인)
        st.subheader("🎯 3:1 원칙 준수 여부 시각화")
        
        # 시각화를 위한 데이터 가공 (손실은 양수로 변환하여 비교)
        scatter_df = df.copy()
        
        # 차트 그리기
        # 기준선: 내 평균 손실의 3배가 되는 지점
        target_roi = avg_loss * 3
        
        st.caption(f"💡 아래 차트에서 **초록색 점**은 빅터 스페란데오의 기준(평균 손실 {avg_loss:.1f}%의 3배인 {target_roi:.1f}% 이상 수익)을 충족한 **'질 좋은 거래'**입니다.")

        scatter_chart = alt.Chart(scatter_df).mark_circle(size=100).encode(
            x=alt.X('Date', title='거래 일자'),
            y=alt.Y('ROI_Percent', title='수익률 (%)'),
            color=alt.condition(
                alt.datum.ROI_Percent >= target_roi, 
                alt.value("#00CC00"),  # 3배 이상 수익 (초록)
                alt.condition(
                    alt.datum.ROI_Percent > 0,
                    alt.value("#F1C40F"), # 수익은 났지만 3배 미만 (노랑)
                    alt.value("#FF4B4B")  # 손실 (빨강)
                )
            ),
            tooltip=['Ticker', 'Date', 'ROI_Percent', 'P_L_Amount']
        ).interactive()

        # 3:1 기준선 (Target Line)
        rule_line = alt.Chart(pd.DataFrame({'y': [target_roi]})).mark_rule(color='blue', strokeDash=[3,3]).encode(y='y')
        
        st.altair_chart(scatter_chart + rule_line, use_container_width=True)

        # 4. 분석 코멘트
        st.info("🔵 **파란 점선**은 현재 평균 손실 대비 3배 수익 구간을 의미합니다. 점들이 이 선 위에 많이 위치할수록 빅터 스페란데오가 말하는 '건전한 도박'을 하고 있는 것입니다.")

        st.divider()
        
        # 5. 진단 메시지
        st.subheader("🩺 Trader Vic's Prescription")
        if expectancy > 0 and risk_reward_ratio >= 3.0:
            st.success("💎 **[전설적인 상태]** 훌륭합니다! 높은 손익비와 양의 기댓값을 유지하고 있습니다. 지금의 원칙을 강력하게 고수하세요.")
        elif expectancy > 0 and risk_reward_ratio < 3.0:
            st.warning(f"🔔 **[개선 필요]** 계좌는 우상향 중(기댓값 +)이나, 손익비({risk_reward_ratio:.2f})가 3.0에 미치지 못합니다. 이익을 조금 더 길게 가져가는 연습이 필요합니다.")
        else:
            st.error("🚨 **[위험 경보]** 현재 통계적 우위(Edge)가 없습니다. 매매 횟수를 줄이고, 확실한 3:1 자리에만 진입하는 인내심이 필요합니다.")

    # === TAB 6: 수익쿠션 계산기 ===
    with tab6:
        st.subheader("🧮 수익 쿠션 계산기 (Position Sizing)")
        st.info("💡 **팁:** 값을 입력하고 아래 **[💾 설정 저장하기]** 버튼을 누르면, 앱을 껐다 켜도 값이 유지됩니다!")
        
        default_account = float(saved_config.get('total_account', 10000000.0))
        default_profit = float(saved_config.get('open_profit', 0.0))
        default_buy = float(saved_config.get('current_buy_amt', 5000000.0))
        default_loss_pct = float(saved_config.get('loss_cut_pct', 5.0))
        
        with st.form("cushion_form"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### 1️⃣ 내 자산 입력")
                total_account = st.number_input("총 추정자산 (예수금+주식)", value=default_account, step=100000.0)
                open_profit = st.number_input("현재 총 수익금 (평가손익)", value=default_profit, step=10000.0)
            with c2:
                st.markdown("### 2️⃣ 리스크 시뮬레이션")
                current_buy_amt = st.number_input("현재 보유주식 총 매수금액", value=default_buy, step=100000.0)
                loss_cut_pct = st.number_input("평균 손절 계획 (%)", value=default_loss_pct, step=0.5)
            
            if st.form_submit_button("💾 설정 저장하기"):
                new_config = pd.DataFrame([{'total_account': total_account, 'open_profit': open_profit, 'current_buy_amt': current_buy_amt, 'loss_cut_pct': loss_cut_pct}])
                conn.update(worksheet=1, data=new_config)
                st.toast("✅ 저장 완료!"); st.rerun()

        open_risk = current_buy_amt * (loss_cut_pct / 100)
        st.divider(); st.error(f"📉 모든 종목 손절 시 예상 손실금: **-{open_risk:,.0f}원**")
        
        st.subheader("🛡️ 안전한 베팅 금액 계산 (역산)")
        safety_margin = st.slider("현재 수익금의 몇 %만 쿠션으로 사용할까요?", 10, 100, 50, 10)
        
        if open_profit > 0:
            safe_cushion = open_profit * (safety_margin / 100)
            target_sl_pct = st.slider("신규 진입 종목의 손절폭 (%)", 1.0, 30.0, 5.0, 0.5)
            investable = safe_cushion / (target_sl_pct / 100)
            cushion_percent = (open_profit / total_account) * 100 if total_account > 0 else 0
            st.markdown(f"""
            #### 📊 현재 수익 쿠션: **{cushion_percent:.2f}%**
            #### 💰 추천 매수 금액: **:blue[{investable:,.0f}원]** (손절 {target_sl_pct}% 기준)
            """)
            if open_profit > open_risk: st.success("💎 **House Money 상태!** 안전합니다.")
            else: st.warning("⚠️ **주의:** 리스크가 수익금을 초과했습니다.")
        else: st.warning("⚠️ 현재 수익 쿠션이 없어서 계산할 수 없습니다.")

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")
