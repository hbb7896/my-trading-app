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
        df_config = conn.read(worksheet=1, ttl=0)
        # 기존 데이터(11번탭 설정 등)가 날아가지 않게 덮어쓰기 방지 처리!
        if not df_config.empty:
            new_df = df_config.copy()
            new_df.at[0, 'Total_Equity'] = equity
            new_df.at[0, 'Max_Position'] = max_pos
            new_df.at[0, 'History'] = history_str
        else:
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

# 최초 화면 로딩 시 데이터 원본 캐싱 (철벽 방어에 활용됨)
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
    
    # 1. 매수 금액 입력
    buy_amt = st.number_input("총 매수 금액 (원)", value=def_buy_amt, step=100000)
    
    # 2. 수익률 입력
    roi = st.number_input("수익률 (%)", value=def_roi, format="%.2f")
    
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
    memo = st.text_input("메모 (특이사항 등)", value=def_memo)
    
    # [🔥 핵심 업데이트: 데이터 증발 철벽 방어 코드]
    if st.form_submit_button("기록 저장"):
        if ticker:
            with st.spinner("안전하게 암호화하여 저장 중입니다... 🛡️"):
                try:
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
                    
                    # 1. 저장 직전에 서버에서 최신 데이터를 다시 불러옵니다.
                    live_df = conn.read(worksheet=0, ttl=0)
                    
                    # 2. 교차 검증 (에러 방지 핵심 로직)
                    if live_df.empty and not df.empty:
                        safe_df = df.copy() 
                        safe_df['Date'] = pd.to_datetime(safe_df['Date']).dt.strftime('%Y-%m-%d')
                        updated_df = pd.concat([safe_df, new_data], ignore_index=True)
                        st.toast("⚠️ 일시적인 통신 지연을 감지하여 안전 모드로 백업 데이터를 활용해 저장했습니다.")
                    
                    elif not live_df.empty:
                        live_df['Date'] = pd.to_datetime(live_df['Date']).dt.strftime('%Y-%m-%d')
                        updated_df = pd.concat([live_df, new_data], ignore_index=True)
                        
                    else:
                        updated_df = new_data
                        
                    # 3. 완벽하게 보호된 데이터를 덮어씌웁니다.
                    conn.update(worksheet=0, data=updated_df)
                    
                    # 저장 후 AI 기록 찌꺼기 초기화
                    if 'ai_ticker' in st.session_state:
                        st.session_state.ai_ticker = ""
                        st.session_state.ai_buy_amt = 0
                        st.session_state.ai_roi = 0.0
                        st.session_state.ai_memo = ""
                        
                    st.success(f"✅ {ticker} 완벽하게 저장 완료! (수익률 {roi:.2f}%)")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"🚨 심각한 통신 오류 감지! 원본 데이터 보호를 위해 저장을 차단했습니다. 새로고침 후 다시 시도하세요.")
                    st.write(f"에러 내용: {e}")
        else: 
            st.error("종목명을 입력해주세요.")

if krx_list.empty: st.sidebar.caption("⚠️ 리스트 로딩 실패")
else: st.sidebar.caption(f"✅ {len(krx_list):,}개 종목 연결됨")

# --- 메인 화면 ---
st.title("💎 Trading Master Dashboard")

if not df.empty:
    # 탭 구성: 총 9개 (불필요 탭 삭제 완료)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "📊 차트", "📅 월별", "📆 연도별", "📋 원본", 
        "⚖️ 빅터 스페란데오", "🎯 R-배수 분석", "🧭 로드맵 점검", "🔔 손익 분포", "🧮 깡토의 R 계산기"
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

        # 켈리 기준 (Kelly Criterion) 계산 로직
        if money_rr_ratio > 0:
            kelly_fraction = win_prob - (loss_prob / money_rr_ratio)
            kelly_pct = max(0.0, kelly_fraction * 100) 
        else:
            kelly_pct = 0.0
            
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("💰 누적 총 손익", f"{total_pl:,.0f}원")
        m2.metric("🎯 전체 승률", f"{win_rate:.1f}%", help="총 매매 횟수 중 수익을 낸 매매의 비율입니다.")
        m3.metric("🔮 기간 기댓값 (Edge)", f"{expectancy:.2f}%", help="(승률 × 평균수익%) - (패율 × 평균손실%). 매매를 한 번 할 때마다 계좌가 평균적으로 몇 %씩 성장하는지 보여주는 '수학적 우위'입니다.")
        m4.metric("💎 Profit Factor", f"{total_pf:.2f}", help="총 이익금 ÷ 총 손실금. '번 돈이 잃은 돈보다 몇 배 많은가?'를 나타냅니다. 1.5 이상이면 훌륭하고, 3.0 이상이면 초고수입니다.")
        m5.metric("⚖️ 켈리 베팅 비중", f"{kelly_pct:.1f}%", help="켈리 공식: 사장님의 현재 승률과 손익비를 바탕으로, 계좌를 가장 안전하고 빠르게 불릴 수 있는 '1회 매매당 최적의 자산 투입 비중'입니다.")
        
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

    # === [NEW] TAB 9: 깡토의 R 계산기 & 점진적 베팅 판독기 (구 11번 탭) ===
    with tab9:
        st.subheader("🧮 깡토의 실전 R 계산기 (Position Sizing)")
        st.markdown("**\"매수 버튼을 누르기 전, 내 시드와 감당할 리스크(R)에 맞는 최적의 투입 금액을 계산합니다.\"**")
        
        # [🔥 KEY 업데이트] DB에서 불러온 값을 영구 메모리(session state)에 세팅
        if 'r_seed' not in st.session_state:
            saved_eq, _, _ = load_status() # 기본값은 내 총 자산
            st.session_state.r_seed = int(saved_eq)
        if 'r_risk' not in st.session_state:
            st.session_state.r_risk = float(saved_config.get('R_Risk', 1.0))
        if 'r_sl' not in st.session_state:
            st.session_state.r_sl = float(saved_config.get('R_SL', 8.0))
        if 'r_unit' not in st.session_state:
            st.session_state.r_unit = float(saved_config.get('R_Unit', 1.0))

        with st.container(border=True):
            st.markdown("#### 1️⃣ 나의 투자 기준 입력")
            c1, c2, c3 = st.columns(3)
            
            seed_money = c1.number_input("💰 총 시드머니 (원)", value=st.session_state.r_seed, step=1000000)
            r_pct = c2.number_input("📉 나의 1R 리스크 (%)", value=st.session_state.r_risk, step=0.5, help="총 자산 대비 1회 매매에서 감수할 최대 손실 비율입니다. (보통 1~2%)")
            sl_pct = c3.number_input("✂️ 손절 기준 (%)", value=st.session_state.r_sl, step=1.0, help="이 종목을 샀을 때, 몇 % 하락하면 손절할 것인지 정합니다.")
            
        if seed_money > 0 and sl_pct > 0:
            # 책에 나온 공식 적용
            max_loss_amt = seed_money * (r_pct / 100)
            max_position_amt = max_loss_amt * (100 / sl_pct)
            position_weight = (max_position_amt / seed_money) * 100
            target_profit_pct = sl_pct * 3 # 1:3 손익비 기준
            
            st.markdown("#### 2️⃣ 계산 결과 (Action Plan)")
            res1, res2 = st.columns(2)
            with res1:
                st.info(f"**💡 이 매매의 1R (최대 감수 손실금)**\n### {max_loss_amt:,.0f} 원")
                st.success(f"**🎯 추천 최대 투입 금액 (포지션 사이즈)**\n### {max_position_amt:,.0f} 원")
                st.write(f"👉 총 자산의 **{position_weight:.1f}%** 비중")
                
            with res2:
                st.warning(f"**✂️ 강제 손절 라인 (-1R)**\n### -{sl_pct:.1f}%")
                st.error(f"**🏆 최소 목표 익절 라인 (3R)**\n### +{target_profit_pct:.1f}%")
                st.write(f"👉 손익비 1:3 도달 시 기대 수익금: **{max_loss_amt * 3:,.0f} 원**")
            
            st.divider()
            
            # --- 점진적 베팅(Unit) 판독기 ---
            st.markdown("#### 3️⃣ 점진적 베팅 (Unit) 판독기")
            st.caption("※ 1포지션 = 전체 자산의 25%  /  1유닛 = 1포지션의 25% (전체 자산의 6.25%)")
            
            one_position_amt = seed_money * 0.25
            one_unit_amt = one_position_amt * 0.25
            
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                input_units = st.number_input("🔢 투입할 유닛(Unit) 수를 입력하세요", min_value=0.0, value=st.session_state.r_unit, step=1.0)
            
            if one_unit_amt > 0:
                actual_invest = input_units * one_unit_amt
                current_positions = input_units / 4.0
                
                with col_u2:
                    st.write("")
                    st.write("")
                    st.markdown(f"### 💸 **{actual_invest:,.0f} 원**")
                
                if input_units < 1.0:
                    st.info(f"📊 현재 **{input_units:.1f} 유닛** (정찰병 이하 수준)")
                elif input_units < 2.0:
                    st.success(f"📊 현재 **{input_units:.1f} 유닛** (1유닛 이상 투입 중)")
                elif input_units < 3.0:
                    st.warning(f"📊 현재 **{input_units:.1f} 유닛** (2유닛 이상 투입 중 - 피라미딩)")
                elif input_units < 4.0:
                    st.error(f"📊 현재 **{input_units:.1f} 유닛** (3유닛 이상 투입 중! 비중 꽉 차감)")
                else:
                    st.error(f"🚨 현재 **{current_positions:.1f} 포지션 ({input_units:.1f} 유닛)** (1포지션 100% 이상! 풀베팅 상태)")
            
            st.markdown("---")
            # [NEW] 대시보드 고정용 버튼 (DB 덮어쓰기 안전 로직 적용)
            if st.button("💾 현재 설정값 대시보드에 고정하기 (영구 저장)"):
                st.session_state.r_seed = seed_money
                st.session_state.r_risk = r_pct
                st.session_state.r_sl = sl_pct
                st.session_state.r_unit = input_units
                
                with st.spinner("구글 시트에 설정을 영구 저장 중입니다..."):
                    try:
                        df_config = conn.read(worksheet=1, ttl=0)
                        if not df_config.empty:
                            new_df = df_config.copy()
                            new_df.at[0, 'R_Risk'] = r_pct
                            new_df.at[0, 'R_SL'] = sl_pct
                            new_df.at[0, 'R_Unit'] = input_units
                        else:
                            new_df = pd.DataFrame([{'R_Risk': r_pct, 'R_SL': sl_pct, 'R_Unit': input_units}])
                        conn.update(worksheet=1, data=new_df)
                        st.success("✅ 완벽하게 저장되었습니다! 앱을 껐다 켜도 이 숫자 그대로 유지됩니다.")
                    except Exception as e:
                        st.error(f"저장 실패: {e}")
                
                st.rerun() 

else:
    st.info("👈 사이드바 매매 기록을 입력하면 대시보드가 활성화됩니다.")
