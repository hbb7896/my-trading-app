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
    # 탭 구성: 총 9개 (마지막 탭 추가됨)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "📊 차트", "📅 월별", "📆 연도별", "📋 원본", 
        "⚖️ 빅터 스페란데오", "🎯 R-배수 분석", "⚖️ 자금 관리 비서", "🕵️ 김대리의 1:1 분석실", "🧭 로드맵 점검"
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

    # === TAB 4: 원본 ===
    with tab4: st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)

    # === TAB 5: 빅터 스페란데오 분석 ===
    with tab5:
        st.subheader("⚖️ Victor Sperandeo's Reward-to-Risk Analysis")
        st.markdown("> **\"최소 3:1의 보상 비율이 나오지 않는 거래는 시작조차 하지 마라.\"** - Victor Sperandeo")
        
        vic_period = st.radio("📅 분석 기간 선택", ["전체", "최근 1개월", "최근 3개월", "최근 6개월", "최근 1년"], horizontal=True, key="vic_radio")
        
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
                    delta="목표 달성" if v_rr_ratio >= 3.0 else "목표 미달")
            with c2:
                st.metric("기간 기댓값 (Edge)", f"{v_expectancy:.2f}%")
            with c3:
                st.metric("빅터의 목표 기준", "3.0 : 1")
            
            st.divider()
            target_roi_period = v_avg_loss * 3 if v_avg_loss > 0 else 10
            conditions = [(vic_df['ROI_Percent'] >= target_roi_period), (vic_df['ROI_Percent'] > 0)]
            colors = ["#00CC00", "#F1C40F"]
            vic_df['Color_Hex'] = np.select(conditions, colors, default="#FF4B4B")
            
            scatter_chart = alt.Chart(vic_df).mark_circle(size=100).encode(
                x=alt.X('Date', title='거래 일자'),
                y=alt.Y('ROI_Percent', title='수익률 (%)'),
                color=alt.Color('Color_Hex', scale=None, legend=None),
                tooltip=['Ticker', 'Date', 'ROI_Percent', 'P_L_Amount']
            ).interactive()
            rule_line = alt.Chart(pd.DataFrame({'y': [target_roi_period]})).mark_rule(color='blue', strokeDash=[3,3]).encode(y='y')
            st.altair_chart(scatter_chart + rule_line, use_container_width=True)
        else:
            st.info(f"📭 선택하신 **{vic_period}**에는 매매 기록이 없습니다.")

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
            else:
                all_losses = df[df['P_L_Amount'] < 0]
                avg_loss_abs = abs(all_losses['P_L_Amount'].mean()) if not all_losses.empty else 1
            
            r_df['R_Value'] = r_df['P_L_Amount'] / avg_loss_abs
            
            c1, c2, c3 = st.columns(3)
            c1.metric(f"나의 1R ({r_period})", f"{avg_loss_abs:,.0f}원")
            c2.metric("평균 R-배수", f"{r_df['R_Value'].mean():.2f}R")
            c3.metric("최고 R-배수", f"{r_df['R_Value'].max():.2f}R")
            
            st.divider()
            df_sorted_r = r_df.sort_values('Date').copy()
            df_sorted_r['Cumulative_R'] = df_sorted_r['R_Value'].cumsum()
            df_sorted_r['Trade_Num'] = range(1, len(df_sorted_r) + 1)
            
            line_r = alt.Chart(df_sorted_r).mark_line(color='blue').encode(
                x=alt.X('Trade_Num', title='거래 횟수'),
                y=alt.Y('Cumulative_R', title='누적 R'),
                tooltip=['Date', 'R_Value', 'Cumulative_R']
            )
            st.altair_chart(line_r, use_container_width=True)
        else:
            st.info(f"📭 선택하신 **{r_period}**에는 매매 기록이 없습니다.")

    # === TAB 7: 자금 관리 비서 (Risk-Free Pyramiding) ===
    with tab7:
        st.subheader("⚖️ 자금 관리 비서 (Position Sizing AI)")
        st.markdown("**\"최근 폼(Form)이 좋으면 사납게! 나쁘면 웅크리게!\"**")
        
        my_total_seed = st.number_input("💰 현재 총 시드머니 (원)", value=16000000, step=1000000)
        st.divider()

        # 최근 매매 분석
        recent_n = 5
        df_sorted = df.sort_values('Date', ascending=False)
        df_recent = df_sorted.head(recent_n)
        
        # 1. 컨디션 진단 (Slump or Fire?)
        if len(df_recent) < 3:
            st.warning("⚠️ 데이터가 부족합니다. 최소 3건 이상의 매매 기록이 필요합니다.")
        else:
            r_wins = df_recent[df_recent['ROI_Percent'] > 0]
            r_win_rate = len(r_wins) / len(df_recent)
            r_net_profit = df_recent['P_L_Amount'].sum()
            
            condition_msg = ""
            bg_color = ""
            
            if r_win_rate <= 0.2 or r_net_profit < 0:
                condition_msg = "🥶 **[SLUMP]** 컨디션 난조! 지금은 몸을 사려야 합니다."
                bg_color = "#ffe6e6" 
            elif r_win_rate <= 0.5:
                condition_msg = "😐 **[NORMAL]** 평범한 흐름입니다. 원칙대로 진행하세요."
                bg_color = "#ffffcc"
            else:
                condition_msg = "🔥 **[ON FIRE]** 폼 미쳤습니다! 사납게 비중을 태우세요!"
                bg_color = "#e6ffe6"

            st.markdown(f"""
            <div style="background-color: {bg_color}; padding: 15px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 20px;">
                <h3 style="margin:0;">{condition_msg}</h3>
            </div>
            """, unsafe_allow_html=True)

        # 2. Risk-Free Pyramiding Calculator
        st.subheader("🦁 [사나운 불타기] Risk-Free Pyramiding 가이드")
        st.markdown("""
        > **"수익이 담보되면 손절을 본전으로 올리고, 공짜로 비중을 태우세요."**
        > 사장님의 무기인 **14R 홈런**의 파괴력을 극대화하는 **[10-15-25 룰]** 계산기입니다.
        """)

        with st.container(border=True):
            c_p1, c_p2 = st.columns([1, 2])
            with c_p1:
                target_price = st.number_input("🎯 현재 주가 (진입가)", value=10000, step=100)
                st.caption("※ 매수하려는 종목의 현재 가격을 입력하세요.")
            
            with c_p2:
                # 계산 로직
                # 1. Entry (10%)
                entry_amt = my_total_seed * 0.10
                entry_qty = int(entry_amt / target_price) if target_price > 0 else 0
                stop_loss_price = int(target_price * 0.97) # -3% Stop
                
                # 2. Scale-Up (15%) -> Total 25%
                trigger_price = int(target_price * 1.03) # +3% Rise
                add_amt = my_total_seed * 0.15
                add_qty = int(add_amt / trigger_price) if trigger_price > 0 else 0
                
                # New Stop Loss (Risk Free) -> Avg Cost
                total_qty = entry_qty + add_qty
                if total_qty > 0:
                    total_amt = (entry_qty * target_price) + (add_qty * trigger_price)
                    avg_cost = int(total_amt / total_qty)
                else:
                    avg_cost = 0
                
                new_stop_loss = int(avg_cost) # 본전 손절 (Risk Free)

                st.markdown(f"""
                #### **📜 [10-15-25] 실행 시나리오**
                
                **Step 1: 🕵️ 정찰병 투입 (10% 비중)**
                - **매수:** {entry_qty:,}주 (약 {entry_amt:,.0f}원)
                - **손절:** **{stop_loss_price:,}원 (-3%)** 칼같이 지킴!
                
                ---
                
                **Step 2: 🔥 불타기 & Risk-Free 선언 (주가가 {trigger_price:,}원 도달 시)**
                - **추가 매수:** {add_qty:,}주 (약 {add_amt:,.0f}원) → **총 비중 25% 완성**
                - **🛑 손절 이동:** **{new_stop_loss:,}원 (평단가)**
                - **효과:** 이제 주가가 떨어져도 **손실은 0원**입니다. 오직 상방만 열려있습니다! 🚀
                """)

    # === TAB 8: 김대리의 1:1 분석실 ===
    with tab8:
        st.subheader("🕵️ 김대리의 1:1 분석실 (My Trading Coach)")
        st.markdown("**\"데이터는 사장님의 모든 습관을 알고 있습니다.\"**")
        
        # 1. 사장님의 정체성 분석
        st.markdown("### 1️⃣ 사장님은 어떤 트레이더인가?")
        
        user_type = ""
        user_desc = ""
        user_icon = ""
        
        if win_rate < 40 and risk_reward_ratio > 2.0:
            user_type = "홈런 타자 (Home Run Hitter)"
            user_desc = "승률은 낮지만(30%대), 한 번 터지면 크게 먹는(2.5배 이상) **전형적인 추세추종형 고수**입니다."
            user_icon = "⚾"
        elif win_rate > 60 and risk_reward_ratio < 1.0:
            user_type = "단타 스캘퍼 (Scalper)"
            user_desc = "자주 이기지만, 수익폭이 작고 한 번의 손실에 취약합니다."
            user_icon = "🔪"
        else:
            user_type = "성장 중인 트레이더"
            user_desc = "아직 뚜렷한 색깔이 나오지 않았습니다. 손익비를 더 키우세요!"
            user_icon = "🌱"
            
        st.info(f"### {user_icon} 당신은 **[{user_type}]** 입니다.\n\n{user_desc}")
        
        st.divider()

        # 2. 팩트 폭격: 손절 시뮬레이션
        st.markdown("### 2️⃣ 팩트 폭격: \"손절만 -3%로 했더라면?\"")
        st.caption("과거 모든 손실 거래를 **-3%**에서 잘랐다고 가정하고 다시 계산해 봅니다.")
        
        if not losses.empty:
            actual_loss_sum = losses['P_L_Amount'].sum()
            simulated_loss_sum = (losses['Buy_Amount'] * -0.03).sum() * -1
            
            deep_losses = losses[losses['ROI_Percent'] < -3].copy()
            shallow_losses = losses[losses['ROI_Percent'] >= -3].copy()
            
            simulated_deep_loss = (deep_losses['Buy_Amount'] * -0.03).sum() * -1
            final_sim_loss = simulated_deep_loss + shallow_losses['P_L_Amount'].sum()
            
            saved_money = final_sim_loss - actual_loss_sum 
            
            col_f1, col_f2 = st.columns(2)
            col_f1.metric("실제 누적 손실", f"{actual_loss_sum:,.0f}원")
            col_f2.metric("칼손절(-3%) 했을 때", f"{final_sim_loss:,.0f}원", f"+{saved_money:,.0f}원 세이브")
            
            if saved_money > 0:
                st.success(f"💸 **보이십니까?** 손절 원칙만 지켰어도 계좌에 **{saved_money:,.0f}원**이 더 있었습니다.")
            else:
                st.write("👏 훌륭합니다! 이미 손절을 아주 짧게 잘 하고 계십니다.")
        else:
            st.write("데이터가 부족하여 시뮬레이션 할 수 없습니다.")

        st.divider()

        # 3. 김대리의 핵심 처방전
        st.markdown("### 3️⃣ 김대리의 핵심 처방전 (Action Plan)")
        
        with st.expander("💊 처방 1: 자금 관리 (10-15-25 룰)", expanded=True):
            st.write("""
            * **초기 진입은 가볍게:** 시드의 **10%** (약 160만 원)
            * **불타기 (Pyramiding):** 수익 확인 후 **+15%** 추가 투입 (약 240만 원)
            * **목표:** '물타기' 절대 금지! 오직 '불타기'로만 비중을 늘리세요.
            """)
            
        with st.expander("💊 처방 2: 손절 원칙 (3/5 룰)", expanded=True):
            st.write("""
            * **-3% 도달 시:** 보유 물량 **50%** 시장가 매도 (일단 도망)
            * **-5% 도달 시:** 나머지 **전량** 매도 (뒤도 돌아보지 마라)
            """)
            
        with st.expander("💊 처방 3: 진입 필터 (3초 체크)", expanded=True):
            st.write("""
            매수 버튼 누르기 전 딱 3 가지만 체크하세요.
            1.  **거래량이 씨가 말랐는가?** (Dry Up)
            2.  **주도 테마인가?** (Leader Sector)
            3.  **VCP 패턴인가?** (Volatility Contraction)
            """)

    # === [NEW] TAB 9: 로드맵 점검 (Roadmap Check) ===
    with tab9:
        st.subheader("🧭 로드맵 이행 점검 (Roadmap Check)")
        st.markdown("**\"김 대리가 내준 3가지 숙제, 잘 하고 계십니까?\"**")
        st.caption("최근 10건의 매매(New)와 그 이전 매매(Old)를 비교 분석합니다.")

        # 데이터 분리 (최근 10건 vs 과거)
        df_sorted = df.sort_values('Date', ascending=False)
        
        if len(df_sorted) < 5:
            st.warning("⚠️ 분석할 데이터가 부족합니다. 최소 5건 이상 매매 후 확인해주세요.")
        else:
            recent_n = 10
            df_recent = df_sorted.head(recent_n) # 최근 (New)
            df_old = df_sorted.iloc[recent_n:]   # 과거 (Old)
            
            if df_old.empty: df_old = df_recent # 데이터 적을 땐 비교군을 자신으로
            
            # --- 숙제 1: 손절은 비용이다. 깎아라 (-4% 목표) ---
            st.markdown("### 1️⃣ 숙제 1: 손절 다이어트 (목표: -4% 이내)")
            
            recent_losses = df_recent[df_recent['ROI_Percent'] < 0]
            old_losses = df_old[df_old['ROI_Percent'] < 0]
            
            r_avg_loss = recent_losses['ROI_Percent'].mean() if not recent_losses.empty else 0.0
            o_avg_loss = old_losses['ROI_Percent'].mean() if not old_losses.empty else 0.0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("과거 평균 손실", f"{o_avg_loss:.2f}%")
            col2.metric("최근 평균 손실 (New)", f"{r_avg_loss:.2f}%", 
                        delta=f"{r_avg_loss - o_avg_loss:.2f}%p" if r_avg_loss > o_avg_loss else None)
            
            with col3:
                if r_avg_loss >= -4.5: # -3% ~ -4.5% 인정
                    st.success("✅ **합격!** 아주 훌륭합니다.")
                elif r_avg_loss > -6.0:
                    st.warning("⚠️ **노력 요함** 조금만 더 줄이세요.")
                else:
                    st.error("❌ **불합격** 아직도 손절이 큽니다.")

            # --- 숙제 2: 타석에 덜 들어서라 (선구안 개선) ---
            st.divider()
            st.markdown("### 2️⃣ 숙제 2: 선구안 개선 (A급 패턴만)")
            st.caption("매매 횟수를 줄이고 승률이나 평균 수익이 개선되었는지 봅니다.")
            
            r_win_rate = (len(df_recent[df_recent['ROI_Percent'] > 0]) / len(df_recent)) * 100
            o_win_rate = (len(df_old[df_old['ROI_Percent'] > 0]) / len(df_old)) * 100
            
            c1, c2, c3 = st.columns(3)
            c1.metric("과거 승률", f"{o_win_rate:.1f}%")
            c2.metric("최근 승률 (New)", f"{r_win_rate:.1f}%", f"{r_win_rate - o_win_rate:.1f}%p")
            
            with c3:
                if r_win_rate >= 40:
                    st.success("✅ **나이스!** 기다림의 미학을 아시는군요.")
                elif r_win_rate >= o_win_rate:
                    st.info("🆗 **유지 중** 나쁘지 않습니다.")
                else:
                    st.error("❌ **뇌동매매 주의** 아무 공이나 휘두르고 계십니다.")

            # --- 숙제 3: 잘될 때 사납게 굴어라 (불타기) ---
            st.divider()
            st.markdown("### 3️⃣ 숙제 3: 홈런 본능 (불타기 & 홀딩)")
            st.caption("이길 때 얼마나 시원하게 먹는지(최고 수익률) 확인합니다.")
            
            recent_wins = df_recent[df_recent['ROI_Percent'] > 0]
            if not recent_wins.empty:
                r_max_win = recent_wins['ROI_Percent'].max()
                r_avg_win = recent_wins['ROI_Percent'].mean()
            else:
                r_max_win = 0
                r_avg_win = 0
                
            k1, k2 = st.columns(2)
            k1.metric("최근 최고 수익률 (홈런)", f"+{r_max_win:.2f}%")
            k2.metric("최근 평균 익절폭", f"+{r_avg_win:.2f}%")
            
            if r_max_win > 15:
                st.success("🔥 **[Perfect]** 역시 홈런 타자! 추세를 제대로 탔습니다.")
            elif r_max_win > 8:
                st.info("👍 **[Good]** 적당한 2루타입니다. 조금만 더 욕심내보세요.")
            else:
                st.warning("먹을 때 너무 짧게 먹습니다. (불타기 부족)")

            # --- 종합 평가 ---
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

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")
