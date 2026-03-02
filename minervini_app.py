import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import altair as alt
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import random
# [NEW] AI 분석을 위한 라이브러리 추가
import json
import google.generativeai as genai
from PIL import Image

# 1. 페이지 설정
st.set_page_config(page_title="Trading Master Dashboard", page_icon="💎", layout="wide")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 설정값 & 상태 영구 저장/불러오기 (Worksheet 1 활용) ---
def load_status():
    """구글 시트 두 번째 탭(1)에서 설정과 기록을 불러옵니다."""
    try:
        df_config = conn.read(worksheet=1, ttl=0)
        if df_config.empty:
            return 20000000, 5000000, [] 
        row = df_config.iloc[0]
        equity = int(row.get('Total_Equity', 20000000))
        max_pos = int(row.get('Max_Position', 5000000))
        history_str = str(row.get('History', ''))
        
        if history_str and history_str != 'nan': history = history_str.split(',')
        else: history = []
        return equity, max_pos, history
    except Exception:
        return 20000000, 5000000, []

def save_status(equity, max_pos, history):
    """설정과 기록을 구글 시트 두 번째 탭(1)에 저장합니다."""
    try:
        history_str = ",".join(history)
        new_df = pd.DataFrame([{'Total_Equity': equity, 'Max_Position': max_pos, 'History': history_str}])
        conn.update(worksheet=1, data=new_df)
    except Exception as e:
        st.error(f"저장 실패: {e}")

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
        if df.empty: return pd.DataFrame(columns=REQUIRED_COLUMNS)
        df = df.dropna(subset=['Date'])
        
        num_cols = ['P_L_Amount', 'ROI_Percent', 'Buy_Amount', 'Sell_Amount']
        for col in num_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
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

# ==========================================
# 사이드바: AI 영수증 캡쳐 분석 모듈
# ==========================================
st.sidebar.header("📸 AI 영수증 자동 입력")
with st.sidebar.expander("🤖 캡쳐 화면 올리기", expanded=False):
    st.markdown("수익/손실 화면을 올리면 알아서 타이핑해드립니다.")
    api_key = st.text_input("Gemini API Key (최초 1회 입력)", type="password", key="sidebar_api")
    uploaded_file = st.file_uploader("증권사 캡쳐 이미지", type=['png', 'jpg', 'jpeg'], key="sidebar_uploader")
    
    if st.button("🔍 데이터 추출하기", use_container_width=True):
        if not api_key:
            st.error("Gemini API Key가 필요합니다.")
        elif not uploaded_file:
            st.error("이미지를 올려주세요.")
        else:
            with st.spinner("김 프로가 캡쳐를 분석 중입니다..."):
                try:
                    clean_api_key = api_key.strip()
                    genai.configure(api_key=clean_api_key)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    img = Image.open(uploaded_file)
                    
                    prompt = """
                    당신은 한국 주식 증권사 앱의 캡쳐 화면을 분석하는 최고 수준의 AI 트레이딩 보조입니다.
                    이미지에서 다음 3가지 데이터를 반드시 추출하세요.
                    1. 종목명 (예: 두산퓨얼셀)
                    2. 매수금액 (콤마(,)를 모두 제거한 순수 숫자만. 예: 2991450)
                    3. 수익률(%) (콤마(,) 및 % 기호를 제거한 순수 숫자만. 예: 0.04)

                    [중요 규칙 - 수익률이 없을 때]
                    화면에 '수익률(%)'이 직접 적혀있지 않고 '손익금액'과 '매수금액'만 있다면, 당신이 직접 수익률을 계산하세요!
                    * 계산식: (손익금액 / 매수금액) * 100
                    * 소수점 셋째 자리에서 반올림하여 둘째 자리까지만 출력하세요.
                    
                    결과는 반드시 아래 JSON 형식으로만 출력하세요. 다른 설명은 절대 추가하지 마세요.
                    {"ticker": "두산퓨얼셀", "buy_amount": 2991450, "roi": 0.04, "memo": "AI 스캔 완료"}
                    """
                    response = model.generate_content([prompt, img])
                    
                    if not response.parts:
                        st.error("🚨 AI가 응답을 반환하지 않았습니다. 이미지가 명확하지 않거나 필터에 걸렸을 수 있습니다.")
                    else:
                        result_text = response.text.strip()
                        if result_text.startswith("```json"):
                            result_text = result_text[7:]
                        if result_text.startswith("```"):
                            result_text = result_text[3:]
                        if result_text.endswith("```"):
                            result_text = result_text[:-3]
                        result_text = result_text.strip()
                        
                        data = json.loads(result_text)
                        
                        st.session_state.ai_ticker = data.get('ticker', '')
                        buy_amt_raw = str(data.get('buy_amount', 0)).replace(',', '')
                        st.session_state.ai_buy_amt = int(float(buy_amt_raw))
                        
                        roi_raw = str(data.get('roi', 0.0)).replace(',', '').replace('%', '')
                        st.session_state.ai_roi = float(roi_raw)
                        
                        st.session_state.ai_memo = data.get('memo', '📸 AI 분석 자동 입력')
                        st.success("✅ 분석 성공! 아래 폼에 입력되었습니다.")
                    
                except Exception as e:
                    st.error("🚨 해독 실패! AI가 반환한 데이터를 이해하지 못했습니다.")
                    with st.expander("🛠️ 김 프로 디버깅 (에러 원인 보기)"):
                        st.write(f"시스템 에러: {e}")
                        if 'result_text' in locals():
                            st.write("AI가 뱉은 원본 데이터:", result_text)

# AI가 뽑아둔 데이터가 있으면 가져오고, 없으면 기본값 세팅
def_ticker = st.session_state.get('ai_ticker', '')
def_buy_amt = st.session_state.get('ai_buy_amt', 0)
def_roi = st.session_state.get('ai_roi', 0.0)
def_memo = st.session_state.get('ai_memo', '')

# --- 사이드바 입력 ---
st.sidebar.markdown("---")
st.sidebar.header("📝 매매 기록 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("일자", datetime.today())
    ticker = st.text_input("종목명 (예: 삼성전자)", value=def_ticker).strip()
    
    st.markdown("---")
    
    buy_amt = st.number_input("총 매수 금액 (원)", value=def_buy_amt, step=100000)
    roi = st.number_input("수익률 (%)", value=def_roi, format="%.2f")
    
    sell_amt = 0.0; pn_l = 0.0
    if buy_amt != 0:
        pn_l = buy_amt * (roi / 100)
        sell_amt = buy_amt + pn_l
        st.info(f"🧮 **자동 계산 결과**\n- 수익금: {pn_l:,.0f}원\n- 매도금액: {sell_amt:,.0f}원")

    st.markdown("---")
    memo = st.text_input("메모 (특이사항 등)", value=def_memo)
    
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
            
            # 저장 후 AI 기록 찌꺼기 초기화
            if 'ai_ticker' in st.session_state:
                st.session_state.ai_ticker = ""
                st.session_state.ai_buy_amt = 0
                st.session_state.ai_roi = 0.0
                st.session_state.ai_memo = ""
                
            st.success(f"✅ {ticker} 저장 완료! (수익률 {roi:.2f}%)"); st.rerun()
        else: st.error("종목명을 입력해주세요.")

if krx_list.empty: st.sidebar.caption("⚠️ 리스트 로딩 실패")
else: st.sidebar.caption(f"✅ {len(krx_list):,}개 종목 연결됨")

# --- 메인 화면 ---
st.title("💎 Trading Master Dashboard")

if not df.empty:
    # 탭 구성: 시장 풍향계 추가하여 총 12개
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12 = st.tabs([
        "📊 차트", "📅 월별", "📆 연도별", "📋 원본", 
        "⚖️ 빅터 스페란데오", "🎯 R-배수 분석", "🧭 로드맵 점검", "🔔 손익 분포", "🔮 미너비니 시뮬레이터", "🚦 신호등 배팅", "📈 AI 차트 복기", "🚨 시장 풍향계"
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

    # === TAB 10: 신호등 배팅 ===
    with tab10:
        st.subheader("🚦 신호등 배팅 (Progressive Exposure)")
        st.markdown("**\"사장님, 이제 껐다 켜도 다 기억합니다. (Google Sheet 연동)\"**")
        saved_equity, saved_max_pos, saved_history = load_status()
        with st.expander("⚙️ 내 자산 & 배팅 설정 (자동 저장)", expanded=True):
            col_set1, col_set2 = st.columns(2)
            with col_set1: new_equity = st.number_input("💰 나의 총 자산 (Equity)", value=saved_equity, step=1000000)
            with col_set2: new_max_pos = st.number_input("🎯 종목당 최대 배팅금 (Max)", value=saved_max_pos, step=500000)
            if new_equity != saved_equity or new_max_pos != saved_max_pos:
                save_status(new_equity, new_max_pos, saved_history); st.rerun()

        st.divider(); st.markdown("#### 👇 최근 매매 결과 입력")
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("🟢 수익 (WIN)", use_container_width=True): saved_history.append("WIN"); save_status(new_equity, new_max_pos, saved_history); st.rerun()
        with col_btn2:
            if st.button("🔴 손실 (LOSS)", use_container_width=True): saved_history.append("LOSS"); save_status(new_equity, new_max_pos, saved_history); st.rerun()
        with col_btn3:
            if st.button("🔄 기록 초기화", use_container_width=True): saved_history = []; save_status(new_equity, new_max_pos, saved_history); st.rerun()

        current_status = "READY"; rec_percent = 0
        if not saved_history: current_status = "NEUTRAL"; rec_percent = 0.25
        else:
            last_trade = saved_history[-1]
            if last_trade == "LOSS": current_status = "RED"; rec_percent = 0.25
            elif last_trade == "WIN":
                if len(saved_history) >= 2 and saved_history[-2] == "WIN": current_status = "GREEN"; rec_percent = 1.0
                else: current_status = "YELLOW"; rec_percent = 0.50

        rec_money = int(new_max_pos * rec_percent)
        st.divider(); display_history = saved_history[-5:] if len(saved_history) > 5 else saved_history
        st.write(f"📜 **최근 기록 (DB 저장됨):** {' → '.join(display_history)}")
        if current_status == "GREEN": st.success(f"### 🟢 **[초록불] 공격 모드 (100%)**\n# **{rec_money:,.0f} 원** 투입")
        elif current_status == "YELLOW": st.warning(f"### 🟡 **[노란불] 경계 모드 (50%)**\n# **{rec_money:,.0f} 원** 투입")
        elif current_status == "RED": st.error(f"### 🔴 **[빨간불] 방어 모드 (25%)**\n# **{rec_money:,.0f} 원** 투입")
        else: st.info(f"### ⚪ **[준비] 정찰 모드 (25%)**\n# **{rec_money:,.0f} 원** 투입")

    # === TAB 11: AI 차트 복기 ===
    with tab11:
        st.subheader("📈 AI 차트 복기 (마크 미너비니 1:1 과외)")
        st.markdown("**\"매수(B)와 매도(S) 타점이 찍힌 차트를 올리시면, 마크 미너비니가 분석해 드립니다.\"**")
        
        with st.container(border=True):
            api_key_tab11 = st.text_input("🔑 Gemini API Key (사이드바에 입력하셨다면 안 넣으셔도 됩니다.)", 
                                          value=st.session_state.get('sidebar_api', ''), type="password", key="tab11_api")
            
            uploaded_chart = st.file_uploader("📸 자동일지차트(B,S 마크 포함) 업로드", type=['png', 'jpg', 'jpeg'], key="tab11_uploader")
            
            if st.button("🔥 미너비니 등판 (차트 분석 시작)", use_container_width=True):
                if not api_key_tab11:
                    st.error("Gemini API Key를 입력해주세요!")
                elif not uploaded_chart:
                    st.error("차트 이미지를 올려주세요!")
                else:
                    with st.spinner("마크 미너비니가 사장님의 차트를 째려보고 있습니다... 🧐"):
                        try:
                            clean_api = api_key_tab11.strip()
                            genai.configure(api_key=clean_api)
                            model = genai.GenerativeModel('gemini-2.5-flash')
                            chart_img = Image.open(uploaded_chart)
                            
                            prompt_minervini = """
                            당신은 세계적인 주식 트레이더 '마크 미너비니(Mark Minervini)'입니다.
                            첨부된 한국 주식 차트 이미지에는 사용자의 매수(B)와 매도(S) 타점이 표시되어 있습니다.
                            당신의 SEPA 전략, VCP(변동성 축소 패턴) 이론, 그리고 엄격한 리스크 관리 철학을 바탕으로 이 타점들을 냉철하게 평가해주세요.
                            
                            다음 양식에 맞춰 마크다운으로 답변해주세요. 전설적인 트레이더답게 단호하고 객관적인 말투를 사용하세요.

                            ### 📌 종목 및 전반적인 차트 분석 (Stage Analysis)
                            (이평선 배열, 추세, VCP 여부 등 차트의 뼈대를 분석)

                            ### 🟢 B(매수) 타점 평가
                            (돌파 여부, 거래량, 진입 타이밍의 적절성을 분석)

                            ### 🔴 S(매도) 타점 평가
                            (수익을 길게 가져갔는지, 너무 일찍 팔았는지, 손절선은 지켰는지 객관적으로 평가)

                            ### 🏆 미너비니의 최종 등급 (S, A, B, C, F 중 택 1) 및 한줄평
                            (총평 및 개선점)
                            """
                            
                            response = model.generate_content([prompt_minervini, chart_img])
                            
                            if not response.parts:
                                st.error("🚨 AI가 답변을 거부했습니다. (너무 강한 비판을 요구해서 구글 안전 필터에 걸렸을 수 있습니다. 사진을 다시 올려보세요.)")
                            else:
                                st.success("✅ 분석 완료! 아래 피드백을 뼈에 새기십시오.")
                                st.markdown("---")
                                st.markdown(response.text)
                            
                        except Exception as e:
                            st.error("🚨 차트 분석 실패! 이미지가 흐리거나 에러가 발생했습니다.")
                            st.write(f"에러 상세: {e}")

    # === [NEW] TAB 12: 시장 풍향계 (Market Compass) ===
    with tab12:
        st.subheader("🚨 시장 풍향계 (Market Compass)")
        st.markdown("**\"시장을 이기려 하지 마라. 큰손들이 나갈 때는 우리도 도망쳐야 한다.\"** - 윌리엄 오닐")

        with st.spinner("시장 체력 스캔 중... (잠시만 기다려주세요)"):
            try:
                # 데이터 150일치 가져오기 (이평선 계산용)
                start_date = datetime.today() - timedelta(days=150)
                kq = fdr.DataReader('KQ11', start_date)
                ks = fdr.DataReader('KS11', start_date)

                def analyze_index(df, name):
                    # 이동평균선 계산
                    df['21EMA'] = df['Close'].ewm(span=21, adjust=False).mean()
                    df['50SMA'] = df['Close'].rolling(window=50).mean()
                    
                    # 전일 대비 데이터 계산
                    df['Prev_Close'] = df['Close'].shift(1)
                    df['Prev_Vol'] = df['Volume'].shift(1)
                    df['Change_Pct'] = (df['Close'] - df['Prev_Close']) / df['Prev_Close'] * 100

                    # 윌리엄 오닐 분배일 조건: 0.2% 이상 하락 & 거래량 증가
                    df['Dist_Day'] = ((df['Change_Pct'] <= -0.2) & (df['Volume'] > df['Prev_Vol'])).astype(int)

                    # 최근 25거래일 기준 분배일 합계
                    last_25 = df.tail(25)
                    dist_count = last_25['Dist_Day'].sum()
                    
                    current_close = df['Close'].iloc[-1]
                    current_21 = df['21EMA'].iloc[-1]
                    current_50 = df['50SMA'].iloc[-1]

                    return current_close, current_21, current_50, dist_count

                kq_close, kq_21, kq_50, kq_dist = analyze_index(kq, "코스닥")
                ks_close, ks_21, ks_50, ks_dist = analyze_index(ks, "코스피")

                st.markdown("### 📊 현재 시장 상태 (최근 25거래일 기준)")
                c1, c2 = st.columns(2)

                def render_market_status(col, title, close, ema21, sma50, dist):
                    with col:
                        with st.container(border=True):
                            st.markdown(f"#### {title}")
                            st.metric("현재 지수", f"{close:,.2f}")

                            # 분배일 평가 로직
                            if dist >= 5: dist_status = "🔴 **위험** (분배일 5개 이상)"
                            elif dist >= 3: dist_status = "🟡 **주의** (분배일 3~4개)"
                            else: dist_status = "🟢 **안전** (분배일 2개 이하)"

                            # 이평선 추세 평가 로직
                            if close > ema21 and close > sma50: trend_status = "🟢 **상승 추세** (21EMA, 50SMA 위)"
                            elif close < sma50: trend_status = "🔴 **하락 추세** (50SMA 붕괴)"
                            else: trend_status = "🟡 **단기 조정** (21EMA 아래, 50SMA 위)"

                            st.write(f"**카운트:** 누적 분배일 {dist}일 → {dist_status}")
                            st.write(f"**추세선:** {trend_status}")
                            st.divider()

                            # 윌리엄 오닐 & 미너비니 종합 평가
                            if dist >= 5 or close < sma50:
                                st.error("🚨 **[방어 모드]**\n지수가 꺾였습니다. 현금 비중을 늘리고 신규 매수를 멈추세요!")
                            elif dist >= 3 or close < ema21:
                                st.warning("⚠️ **[경계 모드]**\n시장이 지쳐갑니다. 타점을 보수적으로 잡고 비중을 절반으로 줄이세요.")
                            else:
                                st.success("🔥 **[공격 모드]**\n시장이 강세입니다! 주도주 돌파 매매에 적극 참여하세요.")

                render_market_status(c1, "🚀 KOSDAQ (코스닥 - 성장주)", kq_close, kq_21, kq_50, kq_dist)
                render_market_status(c2, "🏢 KOSPI (코스피 - 대형주)", ks_close, ks_21, ks_50, ks_dist)

                st.divider()
                st.info("💡 **분배일(Distribution Day)이란?** 지수가 전일 대비 0.2% 이상 하락하면서 동시에 거래량이 전일보다 증가한 날입니다. 기관 투자자들이 주식을 팔고 나갔다는 강력한 징후이며, 최근 4~5주(25일) 내에 분배일이 5~6개가 누적되면 시장의 천장(Top)으로 간주합니다.")

            except Exception as e:
                st.error("시장 데이터를 불러오는 데 실패했습니다. 장 마감 후 데이터 갱신 중일 수 있습니다.")
                st.write(f"에러 상세: {e}")

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")
