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

# --- [유지] 한국 종목 리스트 가져오기 ---
@st.cache_data(ttl=3600)
def get_krx_list():
    try:
        df = fdr.StockListing('KRX')
        return df[['Code', 'Name', 'Market']]
    except Exception as e:
        return pd.DataFrame()

# --- [유지] PF 점수표 ---
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
             return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Mistake_Tags', 'Emotion', 'Discipline', 'Memo'])
        
        df = df.dropna(subset=['Date'])
        
        # 숫자 변환
        for col in ['P_L_Amount', 'ROI_Percent']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        # [추가됨] 분석용 새 컬럼이 없으면 기본값 생성 (에러 방지)
        if 'Mistake_Tags' not in df.columns: df['Mistake_Tags'] = "정상매매"
        if 'Emotion' not in df.columns: df['Emotion'] = "평온함"
        if 'Discipline' not in df.columns: df['Discipline'] = "Yes"
        
        return df
    except:
        return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Mistake_Tags', 'Emotion', 'Discipline', 'Memo'])

df = load_data()
krx_list = get_krx_list() 

# --- [사이드바] 입력 양식 (분석 기능 추가됨) ---
st.sidebar.header("📝 매매 기록 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("일자", datetime.today())
    ticker = st.text_input("종목명 (예: 삼성전자)").strip()
    pn_l = st.number_input("손익금 (원)", value=0)
    roi = st.number_input("수익률 (%)", value=0.0, format="%.2f")
    
    st.divider()
    st.caption("🧠 심리 및 원칙 분석")
    
    # 1. 손실 원인 태그
    mistake_options = ["정상매매", "뇌동매매", "추격매수", "손절늦음", "익절너무빠름", "시장하락", "비중위반"]
    tags = st.multiselect("매매 특이사항 (손실 원인)", mistake_options, default=["정상매매"])
    tags_str = ", ".join(tags)
    
    # 2. 감정 상태
    emotion = st.selectbox("매수 당시 감정", ["평온함", "흥분/조급함(FOMO)", "공포", "복수심(화남)", "지루함"])
    
    # 3. 원칙 준수 여부
    discipline = st.radio("원칙을 지켰습니까?", ["Yes (잘한 매매)", "No (반성 필요)"], horizontal=True)
    
    memo = st.text_input("메모")
    
    submit = st.form_submit_button("기록 저장")

    if submit:
        if ticker:
            new_data = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Ticker': ticker,
                'P_L_Amount': pn_l,
                'ROI_Percent': roi,
                'Mistake_Tags': tags_str,
                'Emotion': emotion,
                'Discipline': discipline,
                'Memo': memo
            }])
            
            if df.empty: updated_df = new_data
            else:
                df_temp = load_data()
                df_temp['Date'] = df_temp['Date'].dt.strftime('%Y-%m-%d')
                updated_df = pd.concat([df_temp, new_data], ignore_index=True)

            conn.update(worksheet=0, data=updated_df)
            st.success(f"✅ {ticker} 저장 완료!"); st.rerun()
        else:
            st.error("종목명을 입력해주세요.")

# [상태 표시]
if krx_list.empty:
    st.sidebar.caption("⚠️ 종목 리스트 로딩 실패 (분석 기능은 정상 작동)")
else:
    st.sidebar.caption(f"✅ {len(krx_list):,}개 종목 데이터 연결됨")

# --- [메인 화면] ---
st.title("💎 Trading Master Dashboard")

if not df.empty:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 차트 대시보드", "📅 월별 분석", "📆 연도별 분석", "📋 데이터 원본", "❌ 습관 분석"])
    
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

    # === TAB 1: 차트 (기존 유지) ===
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
        except:
            st.line_chart(daily_df.set_index('Date')['Cumulative'])
        
        st.subheader("📊 월별 손익 흐름")
        st.bar_chart(df.groupby('YearMonth')['P_L_Amount'].sum())

    # === TAB 2: 월별 (기존 유지) ===
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
            monthly_stats.append({
                "기간": ym, "총 손익": group['P_L_Amount'].sum(), "승률": f"{(len(g_wins)/len(group))*100:.1f}%",
                "평균수익": f"+{m_avg_gain:.2f}%", "평균손실": f"-{m_avg_loss:.2f}%", "PF": f"{pf:.2f}"
            })
        st.dataframe(pd.DataFrame(monthly_stats).sort_values("기간", ascending=False).style.format({"총 손익": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='RdYlGn'), use_container_width=True)
        show_pf_guide()

    # === TAB 3: 연도별 (기존 유지) ===
    with tab3:
        st.subheader("📆 연도별 종합 성적표")
        yearly_stats = []
        for y, group in df.groupby('Year'):
            g_wins = group[group['ROI_Percent'] > 0]; g_losses = group[group['ROI_Percent'] <= 0]
            gross_profit = group[group['P_L_Amount'] > 0]['P_L_Amount'].sum()
            gross_loss = abs(group[group['P_L_Amount'] <= 0]['P_L_Amount'].sum())
            pf = gross_profit / gross_loss if gross_loss > 0 else 0
            yearly_stats.append({
                "연도": y, "총 손익": group['P_L_Amount'].sum(), "승률": f"{(len(g_wins)/len(group))*100:.1f}%", "PF": f"{pf:.2f}"
            })
        st.dataframe(pd.DataFrame(yearly_stats).sort_values("연도", ascending=False).style.format({"총 손익": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='Greens'), use_container_width=True)
        show_pf_guide()

    # === TAB 4: 원본 (기존 유지) ===
    with tab4:
        st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)

    # === [수정된] TAB 5: 습관 분석 (차트 빼고 통계로 변경) ===
    with tab5:
        st.subheader("🧠 나의 트레이딩 습관 분석 (오답노트)")
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("🛑 **손실 원인 TOP 5**")
            # 태그 분석
            if 'Mistake_Tags' in df.columns:
                all_tags = df['Mistake_Tags'].astype(str).str.split(', ').explode()
                tag_counts = all_tags.value_counts().reset_index()
                tag_counts.columns = ['원인', '횟수']
                # 막대 차트
                base = alt.Chart(tag_counts).encode(
                    x=alt.X('횟수:Q'), y=alt.Y('원인:N', sort='-x'),
                    color=alt.condition(alt.datum.원인 == '정상매매', alt.value('green'), alt.value('red'))
                )
                st.altair_chart(base.mark_bar(), use_container_width=True)
            else:
                st.info("데이터가 쌓이면 분석이 시작됩니다.")

        with c2:
            st.write("⚖️ **원칙 준수율**")
            if 'Discipline' in df.columns:
                d_counts = df['Discipline'].value_counts().reset_index()
                d_counts.columns = ['상태', '횟수']
                pie = alt.Chart(d_counts).mark_arc(innerRadius=50).encode(
                    theta=alt.Theta(field="횟수", type="quantitative"),
                    color=alt.Color(field="상태", type="nominal", scale=alt.Scale(range=['#ff4b4b', '#36bd62']))
                )
                st.altair_chart(pie, use_container_width=True)

        st.divider()
        st.write("📉 **손실 거래 복기**")
        bad = df[df['ROI_Percent'] < 0].sort_values('Date', ascending=False)
        if not bad.empty:
            for i, row in bad.iterrows():
                with st.expander(f"{row['Date'].strftime('%Y-%m-%d')} | {row['Ticker']} | {row['P_L_Amount']:,.0f}원 ({row['ROI_Percent']}%)"):
                    c1, c2 = st.columns(2)
                    c1.markdown(f"**😡 원인:** {row.get('Mistake_Tags', '-')}")
                    c1.markdown(f"**🧠 감정:** {row.get('Emotion', '-')}")
                    c2.markdown(f"**⚖️ 원칙:** {row.get('Discipline', '-')}")
                    st.info(f"📝 메모: {row['Memo']}")
        else:
            st.success("손실 기록이 없습니다!")

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")
