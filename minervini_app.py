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
    # 탭 구성: 총 8개
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📊 차트", "📅 월별", "📆 연도별", "📋 원본", 
        "⚖️ 빅터 스페란데오", "🎯 R-배수 분석", "⚖️ 심플 자금 관리", "🧭 로드맵 점검"
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
        
        with st.expander("ℹ️ 마크 미너비니의 PF(프로핏 팩터) 점수표 보기", expanded=False):
            st.markdown("""
            | PF 범위 | 상태 | 평가 |
            | :--- | :--- | :--- |
            | **1.0 이하** | 🚨 위험 | 손실이 더 큰 상태 |
            | **1.5 ~ 2.0** | 👍 훌륭함 | 안정적 수익 구간 |
            | **3.0 이상** | 💎 전설 | 초고수 (Legendary) |
            """)

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

    # === [UPDATED] TAB 7: 심플 자금 관리 (Simple Money Manager) ===
    with tab7:
        st.subheader("⚖️ 심플 자금 관리 (50-35-15 Rule)")
        st.markdown("**\"복잡한 건 질색! 50% - 35% - 15% 비율만 딱 알려줍니다.\"**")
        
        # 1. 심플 입력창
        with st.container(border=True):
            col_in1, col_in2 = st.columns(2)
            with col_in1:
                total_money = st.number_input("💰 이번 종목 총 투입 예정금 (원)", value=2000000, step=100000)
            with col_in2:
                current_price = st.number_input("🎯 현재 주가 (1차 진입가)", value=70000, step=100)

        # 2. 계산 로직 (50% - 35% - 15%)
        amt1 = total_money * 0.50
        amt2 = total_money * 0.35
        amt3 = total_money * 0.15
        
        qty1 = int(amt1 / current_price) if current_price > 0 else 0
        
        # 2차/3차는 상승 가격 가정 (2차: +2%, 3차: +5%)
        price2 = int(current_price * 1.02)
        qty2 = int(amt2 / price2) if price2 > 0 else 0
        
        price3 = int(current_price * 1.05)
        qty3 = int(amt3 / price3) if price3 > 0 else 0

        # 3. 결과 출력 (카드 형태)
        st.write("")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.success(f"""
            **1️⃣ 1차 진입 (50%)**
            # {amt1:,.0f} 원
            * **{qty1:,} 주** 매수
            * (현재가 즉시 진입)
            """)
            
        with c2:
            st.warning(f"""
            **2️⃣ 2차 불타기 (35%)**
            # {amt2:,.0f} 원
            * **{qty2:,} 주** 매수
            * (수익률 +2% 시점)
            """)
            
        with c3:
            st.error(f"""
            **3️⃣ 3차 막타 (15%)**
            # {amt3:,.0f} 원
            * **{qty3:,} 주** 매수
            * (수익률 +5% 시점)
            """)

        st.caption("※ 주식 수는 예상 진입가(+2%, +5%) 기준으로 계산되었습니다.")

    # === TAB 8: 로드맵 점검 (Roadmap Check) ===
    with tab8:
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
