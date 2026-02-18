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

# --- [NEW] 설정값 & 상태 영구 저장/불러오기 (Worksheet 1) ---
def load_status():
    """구글 시트 두 번째 탭(1)에서 설정과 기록을 불러옵니다."""
    try:
        # worksheet 1은 설정 저장용 (컬럼: Total_Equity, Max_Position, History)
        df_config = conn.read(worksheet=1, ttl=0)
        
        if df_config.empty:
            # 초기값이 없으면 기본값 리턴
            return 20000000, 5000000, []
        
        # 첫 번째 행 가져오기
        row = df_config.iloc[0]
        equity = int(row.get('Total_Equity', 20000000))
        max_pos = int(row.get('Max_Position', 5000000))
        history_str = str(row.get('History', ''))
        
        # 기록 문자열(WIN,LOSS)을 리스트로 변환
        if history_str and history_str != 'nan':
            history = history_str.split(',')
        else:
            history = []
            
        return equity, max_pos, history
    except Exception:
        # 에러 발생 시 기본값
        return 20000000, 5000000, []

def save_status(equity, max_pos, history):
    """설정과 기록을 구글 시트 두 번째 탭(1)에 저장합니다."""
    try:
        history_str = ",".join(history) # 리스트를 문자열로 변환
        new_df = pd.DataFrame([{
            'Total_Equity': equity,
            'Max_Position': max_pos,
            'History': history_str
        }])
        conn.update(worksheet=1, data=new_df)
    except Exception as e:
        st.error(f"저장 실패: {e}")

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
    buy_amt = st.number_input("총 매수 금액 (원)", value=0, step=100000)
    roi = st.number_input("수익률 (%)", value=0.0, format="%.2f")
    
    sell_amt = 0.0; pn_l = 0.0
    if buy_amt != 0:
        pn_l = buy_amt * (roi / 100)
        sell_amt = buy_amt + pn_l
        st.info(f"🧮 **자동 계산 결과**\n- 수익금: {pn_l:,.0f}원\n- 매도금액: {sell_amt:,.0f}원")

    st.markdown("---")
    memo = st.text_input("메모 (특이사항 등)")
    
    if st.form_submit_button("기록 저장"):
        if ticker:
            new_data = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'), 'Ticker': ticker, 'Buy_Amount': buy_amt, 'Sell_Amount': sell_amt,
                'P_L_Amount': pn_l, 'ROI_Percent': roi, 'Mistake_Tags': None, 'Emotion': None, 'Discipline': None, 'Memo': memo
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
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
        "📊 차트", "📅 월별", "📆 연도별", "📋 원본", 
        "⚖️ 빅터 스페란데오", "🎯 R-배수 분석", "🧭 로드맵 점검", "🔔 손익 분포", "🔮 미너비니 시뮬레이터", "🚦 신호등 배팅"
    ])
    
    df['Year'] = df['Date'].dt.year; df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
    total_trades = len(df); wins = df[df['ROI_Percent'] > 0]; losses = df[df['ROI_Percent'] <= 0]
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    avg_win = wins['ROI_Percent'].mean() if not wins.empty else 0; avg_loss = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
    risk_reward_ratio = avg_win / avg_loss if avg_loss > 0 else 0; avg_roi = df['ROI_Percent'].mean()

    # === TAB 1: 차트 ===
    with tab1:
        st.subheader("🏆 전체 종합 성적표 (Total Legend)")
        total_pl = df['P_L_Amount'].sum()
        all_wins = df[df['ROI_Percent'] > 0]; all_losses = df[df['ROI_Percent'] <= 0]
        gross_p = all_wins['P_L_Amount'].sum(); gross_l = abs(all_losses['P_L_Amount'].sum())
        total_pf = gross_p / gross_l if gross_l > 0 else 0
        all_avg_profit_amt = all_wins['P_L_Amount'].mean() if not all_wins.empty else 0
        all_avg_loss_amt = abs(all_losses['P_L_Amount'].mean()) if not all_losses.empty else 0
        money_rr_ratio = all_avg_profit_amt / all_avg_loss_amt if all_avg_loss_amt > 0 else 0
        all_avg_profit_pct = all_wins['ROI_Percent'].mean() if not all_wins.empty else 0
        all_avg_loss_pct = abs(all_losses['ROI_Percent'].mean()) if not all_losses.empty else 0
        period_rr_ratio = all_avg_profit_pct / all_avg_loss_pct if all_avg_loss_pct > 0 else 0
        win_prob = (len(all_wins) / total_trades) if total_trades > 0 else 0; loss_prob = 1 - win_prob
        expectancy = (win_prob * all_avg_profit_pct) - (loss_prob * all_avg_loss_pct)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 누적 총 손익", f"{total_pl:,.0f}원"); m2.metric("🎯 전체 승률", f"{win_rate:.1f}%"); m3.metric("🔮 기간 기댓값", f"{expectancy:.2f}%"); m4.metric("💎 PF", f"{total_pf:.2f}")
        st.divider(); st.markdown("##### 💵 금액 & 기술 성적표")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("평균 수익금", f"{all_avg_profit_amt:,.0f}원"); c2.metric("평균 손실금", f"{all_avg_loss_amt:,.0f}원"); c3.metric("⚖️ 금액 손익비", f"{money_rr_ratio:.2f}"); c4.metric("⚖️ 기간 손익비", f"{period_rr_ratio:.2f}")

        st.divider(); st.subheader("🚀 내 계좌 vs KOSPI 지수")
        daily_df = df.groupby('Date')['P_L_Amount'].sum().reset_index().sort_values('Date')
        daily_df['Cumulative'] = daily_df['P_L_Amount'].cumsum()
        try:
            start = daily_df['Date'].min().strftime('%Y-%m-%d')
            kospi = yf.download("^KS11", start=start, progress=False)['Close'].reset_index(); kospi.columns = ['Date', 'KOSPI']
            kospi['Date'] = pd.to_datetime(kospi['Date']).dt.tz_localize(None)
            base = alt.Chart(daily_df).encode(x='Date:T')
            my_chart = base.mark_line(color='#00AA00', strokeWidth=3).encode(y=alt.Y('Cumulative:Q', title='내 수익'), tooltip=['Date', 'Cumulative'])
            kospi_chart = alt.Chart(kospi).mark_line(color='#FF4444', strokeDash=[5,5]).encode(x='Date:T', y=alt.Y('KOSPI:Q', title='KOSPI', scale=alt.Scale(zero=False)))
            st.altair_chart(alt.layer(my_chart, kospi_chart).resolve_scale(y='independent'), use_container_width=True)
        except: st.line_chart(daily_df.set_index('Date')['Cumulative'])
        st.subheader("📊 월별 손익 흐름"); st.bar_chart(df.groupby('YearMonth')['P_L_Amount'].sum())

    # === TAB 2: 월별 ===
    with tab2:
        st.subheader("📅 월별 상세 성적표")
        monthly_stats = []
        for ym, group in df.groupby('YearMonth'):
            g_wins = group[group['ROI_Percent'] > 0]; g_losses = group[group['ROI_Percent'] <= 0]
            pf = group[group['P_L_Amount'] > 0]['P_L_Amount'].sum() / abs(group[group['P_L_Amount'] <= 0]['P_L_Amount'].sum()) if not group[group['P_L_Amount'] <= 0].empty else 0
            monthly_stats.append({"기간": str(ym), "총 손익": group['P_L_Amount'].sum(), "승률": (len(g_wins)/len(group))*100, "PF": pf})
        st.dataframe(pd.DataFrame(monthly_stats).sort_values("기간", ascending=False).style.format({"총 손익": "{:,.0f}원", "승률": "{:.1f}%", "PF": "{:.2f}"}).background_gradient(subset=['총 손익'], cmap='RdYlGn'), use_container_width=True)

    # === TAB 3: 연도별 ===
    with tab3:
        st.subheader("📆 연도별 종합 성적표")
        yearly_stats = []
        for y, group in df.groupby('Year'):
            g_wins = group[group['ROI_Percent'] > 0]
            pf = group[group['P_L_Amount'] > 0]['P_L_Amount'].sum() / abs(group[group['P_L_Amount'] <= 0]['P_L_Amount'].sum()) if not group[group['P_L_Amount'] <= 0].empty else 0
            yearly_stats.append({"연도": int(y), "총 손익": group['P_L_Amount'].sum(), "승률": (len(g_wins)/len(group))*100, "PF": pf})
        st.dataframe(pd.DataFrame(yearly_stats).sort_values("연도", ascending=False).style.format({"총 손익": "{:,.0f}원", "승률": "{:.1f}%", "PF": "{:.2f}"}).background_gradient(subset=['총 손익'], cmap='Greens'), use_container_width=True)

    # === TAB 4: 원본 ===
    with tab4: st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)

    # === TAB 5: 빅터 스페란데오 ===
    with tab5:
        st.subheader("⚖️ Victor Sperandeo Analysis")
        vic_df = df.copy(); today = datetime.today(); vic_df = vic_df[vic_df['Date'] >= (today - timedelta(days=90))]
        if not vic_df.empty:
            v_wins = vic_df[vic_df['ROI_Percent'] > 0]; v_losses = vic_df[vic_df['ROI_Percent'] <= 0]
            v_avg_win = v_wins['ROI_Percent'].mean() if not v_wins.empty else 0; v_avg_loss = abs(v_losses['ROI_Percent'].mean()) if not v_losses.empty else 0
            v_rr = v_avg_win / v_avg_loss if v_avg_loss > 0 else 0
            st.metric("최근 3개월 손익비", f"{v_rr:.2f} : 1", delta="합격" if v_rr >= 3 else "불합격")
            target = v_avg_loss * 3 if v_avg_loss > 0 else 10
            vic_df['Color'] = np.where((vic_df['ROI_Percent'] >= target) | (vic_df['ROI_Percent'] > 0), "#00CC00", "#FF4B4B")
            st.altair_chart(alt.Chart(vic_df).mark_circle(size=100).encode(x='Date', y='ROI_Percent', color=alt.Color('Color', scale=None), tooltip=['Ticker', 'ROI_Percent']).interactive(), use_container_width=True)
        else: st.info("최근 3개월 데이터가 없습니다.")

    # === TAB 6: R-배수 분석 ===
    with tab6:
        st.subheader("🎯 R-배수 분석")
        r_losses = df[df['P_L_Amount'] < 0]; avg_loss_abs = abs(r_losses['P_L_Amount'].mean()) if not r_losses.empty else 1
        df['R_Value'] = df['P_L_Amount'] / avg_loss_abs
        st.metric("나의 1R (평균 손절금)", f"{avg_loss_abs:,.0f}원")
        line_r = alt.Chart(df.sort_values('Date').reset_index()).mark_line().encode(x=alt.X('index', title='Trade'), y=alt.Y('cumsum_R:Q', title='누적 R')).transform_window(cumsum_R='sum(R_Value)')
        st.altair_chart(line_r, use_container_width=True)

    # === TAB 7: 로드맵 점검 ===
    with tab7:
        st.subheader("🧭 로드맵 점검"); recent = df.sort_values('Date', ascending=False).head(10)
        r_loss = recent[recent['ROI_Percent'] < 0]['ROI_Percent'].mean(); r_win = recent[recent['ROI_Percent'] > 0]['ROI_Percent'].max()
        c1, c2 = st.columns(2)
        c1.metric("최근 10건 평균 손실", f"{r_loss:.2f}%", delta="GOOD" if r_loss >= -4.5 else "BAD")
        c2.metric("최근 10건 최고 수익", f"{r_win:.2f}%", delta="GOOD" if r_win >= 10 else "BAD")

    # === TAB 8: 손익 분포 ===
    with tab8:
        st.subheader("🔔 손익 분포"); 
        hist = alt.Chart(df).mark_bar().encode(x=alt.X('ROI_Percent', bin=alt.Bin(step=2.5)), y='count()', color=alt.condition("datum.ROI_Percent>0", alt.value("green"), alt.value("red")))
        st.altair_chart(hist, use_container_width=True)

    # === TAB 9: 미너비니 시뮬레이터 ===
    with tab9:
        st.subheader("🔮 미너비니 시뮬레이터")
        c1, c2 = st.columns(2)
        sim_seed = c1.number_input("시드머니", value=20000000); sim_pos = c1.number_input("포지션 비율(%)", value=25) / 100
        sim_target = c2.number_input("목표 수익금", value=10000000)
        win_r = win_rate/100; avg_w = avg_win/100; avg_l = avg_loss/100
        edge = (win_r * avg_w) - ((1-win_r) * avg_l)
        if edge > 0:
            per_trade = (sim_seed * sim_pos) * edge
            st.metric("거래당 기대수익", f"{per_trade:,.0f}원")
            st.success(f"목표 달성 예상 거래 횟수: {int(sim_target/per_trade)+1}회")
        else: st.error("기대값이 마이너스입니다.")

    # === TAB 10: [수정완료] 신호등 배팅 (영구 저장 기능 탑재) ===
    with tab10:
        st.subheader("🚦 신호등 배팅 (Progressive Exposure)")
        st.markdown("**\"사장님, 이제 껐다 켜도 다 기억합니다. (Google Sheet 연동)\"**")
        
        # 1. 상태 불러오기 (DB Load)
        saved_equity, saved_max_pos, saved_history = load_status()

        # 2. 설정값 입력 (값이 바뀌면 자동 저장됨)
        with st.expander("⚙️ 내 자산 & 배팅 설정 (자동 저장)", expanded=True):
            col_set1, col_set2 = st.columns(2)
            with col_set1:
                new_equity = st.number_input("💰 나의 총 자산 (Equity)", value=saved_equity, step=1000000)
            with col_set2:
                new_max_pos = st.number_input("🎯 종목당 최대 배팅금 (Max)", value=saved_max_pos, step=500000)
            
            # 값이 변경되었으면 저장
            if new_equity != saved_equity or new_max_pos != saved_max_pos:
                save_status(new_equity, new_max_pos, saved_history)
                st.rerun()

        # 3. 승/패 기록 버튼
        st.divider()
        st.markdown("#### 👇 최근 매매 결과 입력")
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("🟢 수익 (WIN)", use_container_width=True):
                saved_history.append("WIN")
                save_status(new_equity, new_max_pos, saved_history) # 저장 후
                st.rerun() # 새로고침
        with col_btn2:
            if st.button("🔴 손실 (LOSS)", use_container_width=True):
                saved_history.append("LOSS")
                save_status(new_equity, new_max_pos, saved_history)
                st.rerun()
        with col_btn3:
            if st.button("🔄 기록 초기화", use_container_width=True):
                saved_history = []
                save_status(new_equity, new_max_pos, saved_history)
                st.rerun()

        # 4. 로직 계산 (신호등)
        current_status = "READY"
        rec_percent = 0
        
        if not saved_history:
            current_status = "NEUTRAL"
            rec_percent = 0.25 # [요청반영] 초기값 1/4 (25%)
        else:
            last_trade = saved_history[-1]
            if last_trade == "LOSS":
                current_status = "RED" # 방어
                rec_percent = 0.25
            elif last_trade == "WIN":
                if len(saved_history) >= 2 and saved_history[-2] == "WIN":
                    current_status = "GREEN" # 공격
                    rec_percent = 1.0
                else:
                    current_status = "YELLOW" # 경계
                    rec_percent = 0.50

        rec_money = int(new_max_pos * rec_percent)

        # 5. 결과 디스플레이
        st.divider()
        # 최근 5개만 보여주기
        display_history = saved_history[-5:] if len(saved_history) > 5 else saved_history
        st.write(f"📜 **최근 기록 (DB 저장됨):** {' → '.join(display_history)}")
        
        if current_status == "GREEN":
            st.success(f"### 🟢 **[초록불] 공격 모드 (100%)**\n# **{rec_money:,.0f} 원** 투입")
        elif current_status == "YELLOW":
            st.warning(f"### 🟡 **[노란불] 경계 모드 (50%)**\n# **{rec_money:,.0f} 원** 투입")
        elif current_status == "RED":
            st.error(f"### 🔴 **[빨간불] 방어 모드 (25%)**\n# **{rec_money:,.0f} 원** 투입")
        else:
            st.info(f"### ⚪ **[준비] 정찰 모드 (25%)**\n# **{rec_money:,.0f} 원** 투입")

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")
