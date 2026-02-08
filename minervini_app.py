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
    # 탭 구성: 총 10개 (탭 9 수정됨)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
        "📊 차트", "📅 월별", "📆 연도별", "📋 원본", 
        "⚖️ 빅터 스페란데오", "🚥 매매 신호등", "🛡️ 파산 제로", "🛑 매도 검문소", "🔍 롱/숏 진단기", "📉 멘탈 지킴이"
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

    # === TAB 5: 빅터 스페란데오 분석 ===
    with tab5:
        st.subheader("⚖️ Victor Sperandeo's Reward-to-Risk Analysis")
        st.markdown("> **\"최소 3:1의 보상 비율이 나오지 않는 거래는 시작조차 하지 마라.\"** - Victor Sperandeo")
        
        vic_period = st.radio("📅 분석 기간 선택", ["전체", "최근 1개월", "최근 3개월", "최근 6개월", "최근 1년"], horizontal=True)
        
        vic_df = df.copy()
        today = datetime.today()
        
        if vic_period == "최근 1개월":
            vic_df = vic_df[vic_df['Date'] >= (today - timedelta(days=30))]
        elif vic_period == "최근 3개월":
            vic_df = vic_df[vic_df['Date'] >= (today - timedelta(days=90))]
        elif vic_period == "최근 6개월":
            vic_df = vic_df[vic_df['Date'] >= (today - timedelta(days=180))]
        elif vic_period == "최근 1년":
            vic_df = vic_df[vic_df['Date'] >= (today - timedelta(days=365))]
            
        if not vic_df.empty:
            v_wins = vic_df[vic_df['ROI_Percent'] > 0]
            v_losses = vic_df[vic_df['ROI_Percent'] <= 0]
            
            v_win_rate = (len(v_wins) / len(vic_df)) * 100
            v_avg_win = v_wins['ROI_Percent'].mean() if not v_wins.empty else 0
            v_avg_loss = abs(v_losses['ROI_Percent'].mean()) if not v_losses.empty else 0
            v_rr_ratio = v_avg_win / v_avg_loss if v_avg_loss > 0 else 0
            
            v_win_prob = v_win_rate / 100
            v_loss_prob = 1 - v_win_prob
            v_expectancy = (v_win_prob * v_avg_win) - (v_loss_prob * v_avg_loss)
            
            st.caption(f"🔎 **{vic_period}** 데이터 기준 분석 ({len(vic_df)}건)")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("기간 손익비 (R/R)", f"{v_rr_ratio:.2f} : 1",
                    delta="목표 달성" if v_rr_ratio >= 3.0 else "목표 미달",
                    delta_color="normal" if v_rr_ratio >= 3.0 else "inverse")
            with c2:
                st.metric("기간 기댓값 (Edge)", f"{v_expectancy:.2f}%")
            with c3:
                st.metric("빅터의 목표 기준", "3.0 : 1")
                
            st.divider()
            
            target_roi_period = v_avg_loss * 3 if v_avg_loss > 0 else 10
            
            conditions = [
                (vic_df['ROI_Percent'] >= target_roi_period),
                (vic_df['ROI_Percent'] > 0)
            ]
            colors = ["#00CC00", "#F1C40F"]
            vic_df['Color_Hex'] = np.select(conditions, colors, default="#FF4B4B")
            
            st.caption(f"💡 현재 조회 기간의 **평균 손실({v_avg_loss:.1f}%)** 대비 **3배 수익({target_roi_period:.1f}%)** 구간을 표시합니다.")

            scatter_chart = alt.Chart(vic_df).mark_circle(size=100).encode(
                x=alt.X('Date', title='거래 일자'),
                y=alt.Y('ROI_Percent', title='수익률 (%)'),
                color=alt.Color('Color_Hex', scale=None, legend=None),
                tooltip=['Ticker', 'Date', 'ROI_Percent', 'P_L_Amount']
            ).interactive()

            rule_line = alt.Chart(pd.DataFrame({'y': [target_roi_period]})).mark_rule(color='blue', strokeDash=[3,3]).encode(y='y')
            st.altair_chart(scatter_chart + rule_line, use_container_width=True)
            
            if v_expectancy > 0 and v_rr_ratio >= 3.0:
                st.success(f"💎 **[Very Good]** {vic_period} 동안 훌륭한 배팅을 하셨군요! 이 감각 유지하십시오.")
            elif v_expectancy > 0 and v_rr_ratio < 3.0:
                st.warning(f"🔔 **[Check]** {vic_period} 동안 수익은 났지만, 손익비가 3.0 미만입니다. 더 크게 먹는 연습이 필요합니다.")
            else:
                st.error(f"🚨 **[Warning]** {vic_period} 동안 통계적 우위가 무너졌습니다. 매매 횟수를 줄이고 확실한 자리만 노리세요.")
        else:
            st.info(f"📭 선택하신 **{vic_period}**에는 매매 기록이 없습니다.")

    # === TAB 6: 매매 신호등 ===
    with tab6:
        st.subheader("🚥 매매 신호등 (Market Climate & Trading Stance)")
        st.markdown("최근 **10번의 매매**를 분석하여 현재 공격해야 할 때인지, 수비해야 할 때인지 알려줍니다.")
        
        recent_n = 10
        df_recent = df.sort_values('Date', ascending=False).head(recent_n)
        
        if len(df_recent) < 5:
            st.warning(f"⚠️ 데이터가 부족합니다. 최소 5건 이상의 매매 기록이 쌓이면 신호등이 켜집니다. (현재: {len(df_recent)}건)")
        else:
            r_wins = df_recent[df_recent['ROI_Percent'] > 0]
            r_win_rate = (len(r_wins) / len(df_recent)) * 100
            r_total_pl = df_recent['P_L_Amount'].sum()
            
            status = ""; bg_color = ""; advice = ""
            
            if r_win_rate >= 50 and r_total_pl > 0:
                status = "🟢 공격 (AGGRESSIVE)"
                bg_color = "#e6ffe6"
                advice = """
                ### 🚀 **지금은 물 들어온 때입니다! 노 저으세요!**
                * **승률:** 최근 타율이 아주 좋습니다. 시장 리듬과 내 매매가 동기화되어 있습니다.
                * **행동:** 평소 배팅 금액의 **100% ~ 120%**까지 사용해도 좋습니다.
                """
            elif r_win_rate < 30 or r_total_pl < -1000000:
                status = "🔴 수비 (DEFENSIVE)"
                bg_color = "#ffe6e6"
                advice = """
                ### 🛡️ **지금은 웅크려야 할 때입니다.**
                * **상태:** 최근 매매가 꼬여있습니다. 시장이 안 좋거나, 뇌동매매를 하고 있을 수 있습니다.
                * **행동:** 배팅 금액을 평소의 **20% ~ 50%**로 확 줄이세요. 현금을 확보하세요.
                """
            else:
                status = "🟡 경계 (CAUTION)"
                bg_color = "#fffxe6"
                advice = """
                ### 👀 **돌다리도 두들겨 보고 건너세요.**
                * **상태:** 크게 잃지도 않지만, 시원하게 벌리지도 않는 구간입니다.
                * **행동:** 배팅 금액은 평소의 **50% ~ 70%** 정도가 적당합니다.
                """
            
            st.markdown(f"""
            <div style="background-color: {bg_color}; padding: 20px; border-radius: 10px; border: 1px solid #ddd;">
                <h2 style="text-align: center; margin: 0;">{status}</h2>
                <p style="text-align: center;">최근 10회 매매 기준: 승률 <strong>{r_win_rate:.1f}%</strong> | 합산 손익 <strong>{r_total_pl:,.0f}원</strong></p>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(advice)
            
            st.divider()
            st.subheader("📉 최근 10회 손익 추세")
            
            df_chart = df_recent.sort_values('Date', ascending=True).copy()
            df_chart['Trade_Num'] = range(1, len(df_chart) + 1)
            df_chart['Cum_PL'] = df_chart['P_L_Amount'].cumsum()
            
            line = alt.Chart(df_chart).mark_line(point=True, strokeWidth=3).encode(
                x=alt.X('Trade_Num', title='최근 거래 순서'),
                y=alt.Y('Cum_PL', title='누적 손익 (원)'),
                tooltip=['Date', 'Ticker', 'P_L_Amount', 'Cum_PL']
            )
            rule = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='gray', strokeDash=[2,2]).encode(y='y')
            st.altair_chart(line + rule, use_container_width=True)

    # === TAB 7: 파산 제로 ===
    with tab7:
        st.subheader("🛡️ 파산 제로 (Zero Risk of Ruin Simulator)")
        st.markdown("내 매매 기록을 바탕으로 **'몬테카를로 시뮬레이션(미래 1,000번 예측)'**을 돌려 파산 확률이 0%가 되는 **'절대 안전 배팅 비중'**을 찾습니다.")
        
        if len(df) < 10:
            st.warning("⚠️ 정확한 시뮬레이션을 위해 최소 10회 이상의 매매 기록이 필요합니다.")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            ruin_threshold = st.slider("파산 기준 (원금의 몇 % 손실 시 파산?)", 30, 90, 50, 10)
        with col_s2:
            sim_runs = 1000
            st.write(f"🧬 시뮬레이션 횟수: **{sim_runs:,}회** (자동 설정)")

        # 시뮬레이션
        roi_pool = df['ROI_Percent'].dropna().tolist()
        risk_levels = list(range(1, 31))
        ruin_probs = []
        progress_bar = st.progress(0)
        
        for idx, bet_pct in enumerate(risk_levels):
            ruin_count = 0
            for _ in range(sim_runs):
                equity = 100.0
                for _ in range(100):
                    trade_roi = random.choice(roi_pool) 
                    bet_amount = equity * (bet_pct / 100)
                    pnl = bet_amount * (trade_roi / 100)
                    equity += pnl
                    if equity <= (100 - ruin_threshold):
                        ruin_count += 1
                        break
            ruin_probs.append((ruin_count / sim_runs) * 100)
            progress_bar.progress((idx + 1) / len(risk_levels))
        
        progress_bar.empty()
        
        ruin_df = pd.DataFrame({'Bet_Size_Pct': risk_levels, 'Ruin_Prob': ruin_probs})
        
        base_chart = alt.Chart(ruin_df).mark_line(color='red', point=True).encode(
            x=alt.X('Bet_Size_Pct', title='회당 배팅 비중 (%)'),
            y=alt.Y('Ruin_Prob', title='파산 확률 (%)', scale=alt.Scale(domain=[0, 100])),
            tooltip=['Bet_Size_Pct', 'Ruin_Prob']
        )
        
        safe_zone = ruin_df[ruin_df['Ruin_Prob'] == 0]
        max_safe_bet = safe_zone['Bet_Size_Pct'].max() if not safe_zone.empty else 0
        
        st.altair_chart(base_chart, use_container_width=True)
        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            st.metric("파산 확률 0%를 위한 최대 배팅 비중", f"{max_safe_bet}% 이하")
        with c2:
            st.metric("권장 배팅 비중 (보수적)", f"{int(max_safe_bet * 0.5)}% ~ {int(max_safe_bet * 0.8)}%")
            
        if max_safe_bet > 20:
            st.success("💎 **[Strong]** 매매 실력이 훌륭합니다! 20% 이상 배팅해도 파산 위험이 없습니다.")
        elif max_safe_bet > 5:
            st.info(f"🔔 **[Good]** 현재 실력으로는 **{max_safe_bet}%** 비중까지만 안전합니다. 그 이상은 위험합니다.")
        else:
            st.error("🚨 **[Danger]** 파산 위험이 높습니다. 배팅 비중을 극도로 줄이고 실력부터 키우세요.")

    # === TAB 8: 매도 검문소 ===
    with tab8:
        st.subheader("🛑 매도 검문소 (Sell Checkpoint)")
        st.markdown("**'팔까 말까'** 고민될 때, 감정은 빼고 냉정하게 체크해보세요. (추세 추종 매매 기준)")
        
        with st.form("sell_check_form"):
            st.write("🔎 **현재 보유 종목 상태 체크 (Yes/No)**")
            
            c1, c2 = st.columns(2)
            with c1:
                chk1 = st.checkbox("1. 주가가 20일 이동평균선(20MA)을 깨고 내려왔나요?")
                chk2 = st.checkbox("2. 주가가 50일 이동평균선(50MA)을 깨고 내려왔나요? (중요)")
                chk3 = st.checkbox("3. 최근 상승폭의 50% 이상을 반납했나요?")
            with c2:
                chk4 = st.checkbox("4. 거래량이 평소보다 크게 터지면서 하락했나요? (기관 매도 의심)")
                chk5 = st.checkbox("5. 시장(코스피/코스닥)이 하락 추세로 전환되었나요?")
                chk6 = st.checkbox("6. 내가 정한 손절가(Stop Loss)를 건드렸나요? (절대 원칙)")
            
            submitted = st.form_submit_button("판결 내려주세요! 👨‍⚖️")
            
            if submitted:
                risk_score = sum([chk1, chk2, chk3, chk4, chk5, chk6])
                
                st.divider()
                st.markdown(f"### 🎯 진단 결과 (위험 신호: {risk_score}개)")
                
                if chk6: # 손절가 터치는 무조건 매도
                    st.error("🚨 **[긴급 탈출]** 손절가를 건드렸습니다. 이유 불문하고 **전량 매도** 후 생각하세요. 원칙이 생명입니다.")
                elif risk_score >= 4:
                    st.error("🛑 **[매도 강력 권장]** 추세가 완전히 꺾였습니다. **전량 매도**하거나 최소 70% 이상 현금화하세요.")
                elif risk_score >= 2:
                    st.warning("⚠️ **[경고/비중 축소]** 노란불입니다. **30% ~ 50% 분할 매도**하여 수익을 챙기고, 나머지는 본절(매수가)에 스탑로스 거세요.")
                elif risk_score == 1:
                    st.info("👀 **[관망/홀딩]** 아직 추세가 살아있습니다. 하지만 주의 깊게 지켜보세요.")
                else:
                    st.success("🟢 **[강력 홀딩]** 편안하게 즐기세요! 추세는 당신의 친구입니다 (Trend is your friend).")

    # === [수정/통합됨] TAB 9: 롱/숏 진단기 ===
    with tab9:
        st.subheader("🔍 트렌드 스캐너 (Long/Short Strategy)")
        st.markdown("사장님의 원칙에 따라 **상승장(Long)**과 **하락장(Short)** 타점을 모두 분석해 드립니다.")
        
        with st.expander("🔎 종목 분석 입력", expanded=True):
            col_input1, col_input2 = st.columns([2, 1])
            with col_input1:
                vcp_ticker = st.text_input("분석할 종목 코드 (예: 005930, AAPL)", placeholder="티커 입력 후 엔터").strip()
            with col_input2:
                # [NEW] 전략 선택 (롱/숏)
                strategy_type = st.radio("전략 선택", ["🚀 매수 (Long)", "📉 공매도 (Short)"], horizontal=True)
            
            market_cond = st.radio("현재 시장 분위기는?", ["🐂 강세장 (Bull Market)", "🐻 약세장 (Bear Market)"], horizontal=True)
            analyze_btn = st.button("🚀 분석 시작")

        if analyze_btn and vcp_ticker:
            try:
                with st.spinner(f"'{vcp_ticker}' 데이터를 분석 중입니다..."):
                    if vcp_ticker.isdigit(): 
                        stock = yf.Ticker(f"{vcp_ticker}.KS")
                    else:
                        stock = yf.Ticker(vcp_ticker)
                        
                    hist = stock.history(period="2y")
                    
                    if hist.empty:
                        st.error("❌ 데이터를 가져올 수 없습니다. 종목 코드를 확인해주세요.")
                    else:
                        current_price = hist['Close'].iloc[-1]
                        sma_5 = hist['Close'].rolling(window=5).mean().iloc[-1]
                        sma_10 = hist['Close'].rolling(window=10).mean().iloc[-1]
                        sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
                        sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
                        sma_150 = hist['Close'].rolling(window=150).mean().iloc[-1]
                        sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]
                        
                        high_52 = hist['Close'].tail(252).max()
                        low_52 = hist['Close'].tail(252).min()
                        
                        sma_200_prev_month = hist['Close'].rolling(window=200).mean().iloc[-22]
                        
                        # 지수 비교
                        kospi = yf.Ticker("^KS11").history(period="3mo")
                        if not kospi.empty:
                            kospi_ret = (kospi['Close'].iloc[-1] / kospi['Close'].iloc[0]) - 1
                            stock_ret = (hist['Close'].iloc[-1] / hist['Close'].iloc[-60]) - 1
                            
                            if "Long" in strategy_type:
                                relative_strength = stock_ret > (kospi_ret * 3) if kospi_ret > 0 else stock_ret > 0
                            else: # Short Strategy
                                # 숏일 땐 지수보다 더 많이 빠져야 약한 놈임 (하락폭이 3배 크거나)
                                relative_strength = stock_ret < (kospi_ret * 3) if kospi_ret < 0 else stock_ret < 0
                        else:
                            relative_strength = False
                        
                        st.divider()
                        st.markdown(f"### 📋 **[{vcp_ticker}]** {strategy_type} 진단 리스트")
                        st.caption(f"현재가: **{current_price:,.0f}원** (50일선: {sma_50:,.0f}원)")
                        
                        c_chk1, c_chk2 = st.columns(2)
                        
                        # --- [전략별 체크리스트 분기] ---
                        if "Long" in strategy_type:
                            trend_200_up = sma_200 > sma_200_prev_month
                            with c_chk1:
                                st.write("**1. 추세 템플릿 (정배열)**")
                                cond_ma_order = sma_50 > sma_150 > sma_200
                                st.checkbox("이평선 정배열 (50 > 150 > 200)", value=cond_ma_order, disabled=True)
                                st.checkbox("200일선 상승 추세", value=trend_200_up, disabled=True)
                                cond_price_ma = current_price > sma_50
                                st.checkbox("현재가 > 50일 이평선", value=cond_price_ma, disabled=True)
                            
                            with c_chk2:
                                st.write("**2. 모멘텀 & 위치**")
                                cond_near_high = current_price >= (high_52 * 0.75)
                                st.checkbox(f"52주 신고가 근처 (25% 이내)", value=cond_near_high, disabled=True)
                                cond_above_low = current_price >= (low_52 * 1.25)
                                st.checkbox(f"52주 신저가 대비 +25% 이상 상승", value=cond_above_low, disabled=True)
                                st.checkbox("지수보다 3배 강한 상승 (RS)", value=relative_strength, disabled=True)
                                
                        else: # Short Strategy
                            trend_200_down = sma_200 < sma_200_prev_month
                            with c_chk1:
                                st.write("**1. 역추세 템플릿 (역배열)**")
                                # 숏은 역배열이어야 함: 50 < 150 < 200
                                cond_ma_inverse = sma_50 < sma_150 < sma_200
                                st.checkbox("이평선 역배열 (50 < 150 < 200)", value=cond_ma_inverse, disabled=True)
                                st.checkbox("200일선 하락 추세", value=trend_200_down, disabled=True)
                                cond_price_below_ma = current_price < sma_50
                                st.checkbox("현재가 < 50일 이평선 (저항)", value=cond_price_below_ma, disabled=True)
                                
                            with c_chk2:
                                st.write("**2. 하락 모멘텀 & 위치**")
                                # 신저가 근처에 있어야 함 (지하실 파는 중)
                                cond_near_low = current_price <= (low_52 * 1.25) 
                                st.checkbox(f"52주 신저가 근처 (25% 이내)", value=cond_near_low, disabled=True)
                                # 신고가에서는 멀어야 함
                                cond_below_high = current_price <= (high_52 * 0.75)
                                st.checkbox(f"52주 신고가 대비 -25% 이상 하락", value=cond_below_high, disabled=True)
                                st.checkbox("지수보다 약한 하락 (RS Weakness)", value=relative_strength, disabled=True)

                        st.warning("🧐 **사장님의 '눈'으로 직접 확인해야 할 항목**")
                        if "Long" in strategy_type:
                            st.write("- 거래량 실린 돌파 (Volume Breakout)?")
                            st.write("- 손잡이 거래량 감소 (Dry Up)?")
                        else:
                            st.write("- 거래량 실린 하락 이탈 (Breakdown)?")
                            st.write("- 반등 시 거래량 감소 (Weak Rally)?")
                            st.write("- 헤드앤숄더 / 이중천장 패턴?")
                        
                        st.divider()
                        st.markdown("### 🛑 **청산(Exit) 가이드라인**")
                        
                        t_sell1, t_sell2 = st.columns(2)
                        
                        if "Long" in strategy_type:
                            with t_sell1:
                                st.info("🏃 **매수 포지션 익절/손절**")
                                st.markdown(f"""
                                * **1차 방어:** 5일선 이탈 ({sma_5:,.0f})
                                * **2차 방어:** 20일선 이탈 ({sma_20:,.0f})
                                * **최종 방어:** 50일선 이탈 ({sma_50:,.0f})
                                """)
                        else: # Short Exit
                            with t_sell1:
                                st.error("🏃 **공매도 포지션 상환(Cover)**")
                                st.markdown(f"""
                                * **단기 청산:** 5일선 돌파 시 ({sma_5:,.0f})
                                * **추세 청산:** 20일선 돌파 시 ({sma_20:,.0f})
                                * **손절(Stop):** 전고점 or 50일선 돌파 ({sma_50:,.0f})
                                """)
                                
            except Exception as e:
                st.error(f"분석 중 오류가 발생했습니다: {e}")

    # === TAB 10: 멘탈 지킴이 (MDD) ===
    with tab10:
        st.subheader("📉 멘탈 지킴이 (Drawdown Analysis)")
        st.markdown("**\"내 계좌는 지금 물속 얼마나 깊은 곳에 있을까?\"** (전고점 대비 하락폭 분석)")
        
        # 일별 누적 수익금 계산 (Daily Equity Curve)
        daily_df = df.groupby('Date')['P_L_Amount'].sum().reset_index().sort_values('Date')
        daily_df['Cumulative_PL'] = daily_df['P_L_Amount'].cumsum()
        
        # 초기 원금 가정 (MDD % 계산을 위해 필요, 설정값 없으면 1000만원 가정)
        initial_capital = float(saved_config.get('total_account', 10000000.0)) - float(saved_config.get('open_profit', 0.0))
        if initial_capital <= 0: initial_capital = 10000000.0
        
        daily_df['Equity'] = initial_capital + daily_df['Cumulative_PL']
        
        # MDD 계산
        daily_df['Peak'] = daily_df['Equity'].cummax()
        daily_df['Drawdown_Amount'] = daily_df['Equity'] - daily_df['Peak']
        daily_df['Drawdown_Pct'] = (daily_df['Drawdown_Amount'] / daily_df['Peak']) * 100
        
        # 현재 상태
        current_dd = daily_df['Drawdown_Pct'].iloc[-1]
        max_dd = daily_df['Drawdown_Pct'].min()
        
        c1, c2 = st.columns(2)
        with c1:
            st.metric("현재 하락폭 (Current Drawdown)", f"{current_dd:.2f}%", 
                      delta="주의!" if current_dd < -10 else "양호", delta_color="inverse")
        with c2:
            st.metric("역대 최대 하락폭 (Max Drawdown)", f"{max_dd:.2f}%")
            
        st.divider()
        
        # 차트 1: 계좌 잔고 & 전고점 (Equity vs Peak)
        st.write("📈 **계좌 잔고 vs 전고점 (파란색 영역이 고통의 구간)**")
        
        base = alt.Chart(daily_df).encode(x='Date:T')
        
        line_equity = base.mark_line(color='#00AA00').encode(
            y=alt.Y('Equity', title='평가 담보금 (원)'),
            tooltip=['Date', 'Equity']
        )
        
        line_peak = base.mark_line(color='gray', strokeDash=[4,4]).encode(
            y='Peak'
        )
        
        st.altair_chart(line_equity + line_peak, use_container_width=True)
        
        # 차트 2: Underwater Chart (수중 차트)
        st.write("🌊 **수중 차트 (Underwater Chart)**")
        
        area_dd = base.mark_area(color='red', opacity=0.5).encode(
            y=alt.Y('Drawdown_Pct', title='하락률 (%)'),
            tooltip=['Date', 'Drawdown_Pct']
        )
        
        st.altair_chart(area_dd, use_container_width=True)
        
        # 멘탈 케어 메시지
        if current_dd > -5:
            st.success("😎 **[아주 좋습니다]** 전고점 근처입니다. 멘탈이 아주 건강한 상태입니다!")
        elif current_dd > -15:
            st.warning("😐 **[조심하세요]** 계좌가 물에 젖고 있습니다. -15%를 넘어가면 복구가 힘들어집니다. 비중을 줄이세요.")
        else:
            st.error("🚑 **[응급 상황]** 깊은 물에 빠졌습니다. 지금은 '수익'보다 '생존'이 목표입니다. 무조건 수비적으로 하세요.")

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")
