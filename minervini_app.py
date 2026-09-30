import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import altair as alt

from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

import random
import json
import re
import hashlib

import google.generativeai as genai
from PIL import Image


# ============================================================
# 1. 페이지 설정
# ============================================================

st.set_page_config(
    page_title="Trading Master Dashboard",
    page_icon="💎",
    layout="wide"
)


# ============================================================
# 2. Google Sheets 연결
# ============================================================

conn = st.connection(
    "gsheets",
    type=GSheetsConnection
)


# ============================================================
# 3. 기본 컬럼 구조
# ============================================================

REQUIRED_COLUMNS = [
    "Trade_ID",
    "Date",
    "Ticker",
    "Buy_Amount",
    "Sell_Amount",
    "P_L_Amount",
    "ROI_Percent",
    "Mistake_Tags",
    "Emotion",
    "Discipline",
    "Memo"
]


# ============================================================
# 4. 기존 거래용 안정적인 Trade_ID 생성
# ============================================================

def create_legacy_trade_id(row, index):
    """
    기존 Google Sheet에 Trade_ID가 없는 거래를 위한 ID.

    random ID를 사용하면 매번 앱을 새로 실행할 때 ID가 바뀌므로
    기존 거래의 주요 데이터를 이용해 동일한 ID를 만들도록 한다.
    """

    values = [
        index,
        str(row.get("Date", "")),
        str(row.get("Ticker", "")),
        str(row.get("Buy_Amount", "")),
        str(row.get("Sell_Amount", "")),
        str(row.get("P_L_Amount", "")),
        str(row.get("ROI_Percent", "")),
        str(row.get("Memo", ""))
    ]

    raw = "|".join(values)

    digest = hashlib.sha1(
        raw.encode("utf-8")
    ).hexdigest()[:12]

    return f"LEGACY_{digest}"


# ============================================================
# 5. 설정값 불러오기
# ============================================================

def load_status():
    """
    Google Sheets 두 번째 탭(worksheet=1)에서
    계좌 설정값과 기록을 불러온다.
    """

    try:

        df_config = conn.read(
            worksheet=1,
            ttl=0
        )

        if df_config.empty:
            return 20000000, 5000000, []

        row = df_config.iloc[0]

        equity = int(
            row.get(
                "Total_Equity",
                20000000
            )
        )

        max_pos = int(
            row.get(
                "Max_Position",
                5000000
            )
        )

        history_str = str(
            row.get(
                "History",
                ""
            )
        )

        if (
            history_str
            and history_str != "nan"
        ):
            history = history_str.split(",")

        else:
            history = []

        return equity, max_pos, history

    except Exception:
        return 20000000, 5000000, []


# ============================================================
# 6. 설정값 저장
# ============================================================

def save_status(
    equity,
    max_pos,
    history
):

    try:

        history_str = ",".join(history)

        df_config = conn.read(
            worksheet=1,
            ttl=0
        )

        if not df_config.empty:

            new_df = df_config.copy()

            new_df.at[
                0,
                "Total_Equity"
            ] = equity

            new_df.at[
                0,
                "Max_Position"
            ] = max_pos

            new_df.at[
                0,
                "History"
            ] = history_str

        else:

            new_df = pd.DataFrame(
                [{
                    "Total_Equity": equity,
                    "Max_Position": max_pos,
                    "History": history_str
                }]
            )

        conn.update(
            worksheet=1,
            data=new_df
        )

    except Exception as e:

        st.error(
            f"저장 실패: {e}"
        )


# ============================================================
# 7. 설정 불러오기
# ============================================================

@st.cache_data(ttl=0)
def load_settings():

    try:

        df = conn.read(
            worksheet=1,
            ttl=0
        )

        if not df.empty:
            return df.iloc[0].to_dict()

    except Exception:
        pass

    return {}


saved_config = load_settings()


# ============================================================
# 8. 한국 종목 리스트
# ============================================================

@st.cache_data(ttl=3600)
def get_krx_list():

    try:

        df = fdr.StockListing(
            "KRX"
        )

        return df[
            ["Code", "Name", "Market"]
        ]

    except Exception:
        return pd.DataFrame()


# ============================================================
# 9. 거래 데이터 불러오기
# ============================================================

def load_data():

    try:

        df = conn.read(
            worksheet=0,
            ttl=0
        )

        # ---------------------------------------------
        # 데이터가 없는 경우
        # ---------------------------------------------

        if df.empty:

            return pd.DataFrame(
                columns=REQUIRED_COLUMNS
            )

        df = df.dropna(
            subset=["Date"]
        ).copy()

        # ---------------------------------------------
        # Trade_ID가 없는 기존 데이터 처리
        # ---------------------------------------------

        if "Trade_ID" not in df.columns:

            df["Trade_ID"] = [
                create_legacy_trade_id(
                    row,
                    index
                )

                for index, row
                in df.iterrows()
            ]

        else:

            for index in df.index:

                current_id = df.at[
                    index,
                    "Trade_ID"
                ]

                if (
                    pd.isna(current_id)
                    or str(current_id).strip() == ""
                ):

                    df.at[
                        index,
                        "Trade_ID"
                    ] = create_legacy_trade_id(
                        df.loc[index],
                        index
                    )

        # ---------------------------------------------
        # 숫자 컬럼
        # ---------------------------------------------

        num_cols = [
            "P_L_Amount",
            "ROI_Percent",
            "Buy_Amount",
            "Sell_Amount"
        ]

        for col in num_cols:

            if col not in df.columns:
                df[col] = 0.0

            df[col] = (
                df[col]
                .astype(str)
                .str.replace(
                    ",",
                    "",
                    regex=False
                )
                .str.replace(
                    "%",
                    "",
                    regex=False
                )
            )

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            ).fillna(0)

        # ---------------------------------------------
        # 날짜
        # ---------------------------------------------

        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

        # ---------------------------------------------
        # 문자열 컬럼
        # ---------------------------------------------

        string_cols = [
            "Ticker",
            "Mistake_Tags",
            "Emotion",
            "Discipline",
            "Memo"
        ]

        for col in string_cols:

            if col not in df.columns:
                df[col] = ""

            df[col] = (
                df[col]
                .fillna("")
                .astype(str)
            )

        # ---------------------------------------------
        # 매수금액이 없는 과거 데이터 보정
        # ---------------------------------------------

        mask = (
            (df["Buy_Amount"] == 0)
            &
            (df["ROI_Percent"] != 0)
        )

        df.loc[
            mask,
            "Buy_Amount"
        ] = (
            df.loc[
                mask,
                "P_L_Amount"
            ]
            /
            (
                df.loc[
                    mask,
                    "ROI_Percent"
                ]
                / 100
            )
        ).abs()

        df.loc[
            mask,
            "Sell_Amount"
        ] = (
            df.loc[
                mask,
                "Buy_Amount"
            ]
            +
            df.loc[
                mask,
                "P_L_Amount"
            ]
        )

        # ---------------------------------------------
        # 필요한 컬럼 보장
        # ---------------------------------------------

        for col in REQUIRED_COLUMNS:

            if col not in df.columns:
                df[col] = ""

        df = df[
            REQUIRED_COLUMNS
        ]

        return df

    except Exception as e:

        st.error(
            f"데이터 불러오기 실패: {e}"
        )

        return pd.DataFrame(
            columns=REQUIRED_COLUMNS
        )


# ============================================================
# 10. 최초 데이터 로딩
# ============================================================

df = load_data()

krx_list = get_krx_list()


# ============================================================
# 11. 기존 Google Sheets 데이터에 Trade_ID가 없으면
#     실제 Sheet에도 한 번 저장
# ============================================================

def migrate_trade_ids():

    try:

        live_df = conn.read(
            worksheet=0,
            ttl=0
        )

        if live_df.empty:
            return

        changed = False

        if "Trade_ID" not in live_df.columns:

            live_df["Trade_ID"] = [
                create_legacy_trade_id(
                    row,
                    index
                )

                for index, row
                in live_df.iterrows()
            ]

            changed = True

        else:

            for index in live_df.index:

                current_id = live_df.at[
                    index,
                    "Trade_ID"
                ]

                if (
                    pd.isna(current_id)
                    or str(current_id).strip() == ""
                ):

                    live_df.at[
                        index,
                        "Trade_ID"
                    ] = create_legacy_trade_id(
                        live_df.loc[index],
                        index
                    )

                    changed = True

        if changed:

            conn.update(
                worksheet=0,
                data=live_df
            )

    except Exception:
        pass


# 앱 실행 시 기존 데이터 ID 보완
migrate_trade_ids()


# ============================================================
# 12. 사이드바
#     AI 영수증 자동 입력
# ============================================================

st.sidebar.header(
    "📸 AI 영수증 자동 입력"
)


with st.sidebar.expander(
    "🤖 캡쳐 화면 올리기",
    expanded=False
):

    st.markdown(
        "수익/손실 화면을 올리면 "
        "알아서 타이핑해드립니다."
    )

    api_key = st.text_input(
        "Gemini API Key (최초 1회 입력)",
        type="password",
        key="sidebar_api"
    )

    uploaded_file = st.file_uploader(
        "증권사 캡쳐 이미지",
        type=[
            "png",
            "jpg",
            "jpeg"
        ],
        key="sidebar_uploader"
    )

    if st.button(
        "🔍 데이터 추출하기",
        use_container_width=True
    ):

        if not api_key:

            st.error(
                "Gemini API Key가 필요합니다."
            )

        elif not uploaded_file:

            st.error(
                "이미지를 올려주세요."
            )

        else:

            with st.spinner(
                "김 프로가 캡쳐를 분석 중입니다..."
            ):

                try:

                    clean_api_key = (
                        api_key.strip()
                    )

                    genai.configure(
                        api_key=clean_api_key
                    )

                    model = genai.GenerativeModel(
                        "gemini-2.5-flash"
                    )

                    img = Image.open(
                        uploaded_file
                    )

                    if img.mode != "RGB":

                        img = img.convert(
                            "RGB"
                        )

                    img.thumbnail(
                        (800, 800)
                    )

                    prompt = """
당신은 한국 주식 증권사 앱의 캡쳐 화면을 분석하는
최고 수준의 AI 트레이딩 보조입니다.

이미지에서 다음 데이터를 반드시 추출하세요.

1. 종목명
2. 매수금액
3. 수익률(%)

수익률이 화면에 직접 없고 손익금액과 매수금액만 있다면
다음 공식으로 계산하세요.

수익률 = 손익금액 / 매수금액 * 100

소수점 둘째 자리까지 출력하세요.

결과는 반드시 아래 JSON 형식으로만 출력하세요.

{
    "ticker": "두산퓨얼셀",
    "buy_amount": 2991450,
    "roi": 0.04,
    "memo": "AI 스캔 완료"
}
"""

                    response = model.generate_content(
                        [
                            prompt,
                            img
                        ]
                    )

                    if not response.parts:

                        st.error(
                            "🚨 AI가 응답을 반환하지 않았습니다."
                        )

                    else:

                        result_text = (
                            response.text.strip()
                        )

                        match = re.search(
                            r"\{.*\}",
                            result_text,
                            re.DOTALL
                        )

                        if match:

                            clean_json = (
                                match.group(0)
                            )

                        else:

                            clean_json = result_text

                        data = json.loads(
                            clean_json
                        )

                        st.session_state.ai_ticker = (
                            data.get(
                                "ticker",
                                ""
                            )
                        )

                        buy_amt_raw = (
                            str(
                                data.get(
                                    "buy_amount",
                                    0
                                )
                            )
                            .replace(",", "")
                        )

                        st.session_state.ai_buy_amt = int(
                            float(
                                buy_amt_raw
                            )
                        )

                        roi_raw = (
                            str(
                                data.get(
                                    "roi",
                                    0.0
                                )
                            )
                            .replace(",", "")
                            .replace("%", "")
                        )

                        st.session_state.ai_roi = float(
                            roi_raw
                        )

                        st.session_state.ai_memo = (
                            data.get(
                                "memo",
                                "📸 AI 분석 자동 입력"
                            )
                        )

                        if (
                            "form_reset_trigger"
                            not in st.session_state
                        ):

                            st.session_state.form_reset_trigger = 0

                        st.session_state.form_reset_trigger += 1

                        st.success(
                            "✅ 분석 성공! "
                            "아래 폼에 입력되었습니다."
                        )

                except Exception as e:

                    error_msg = str(e)

                    if (
                        "429" in error_msg
                        or
                        "quota"
                        in error_msg.lower()
                    ):

                        st.error(
                            "🚨 무료 API 호출 제한 초과!"
                        )

                        st.warning(
                            "잠시 후 다시 시도해주세요."
                        )

                    else:

                        st.error(
                            "🚨 해독 실패! "
                            "캡쳐 이미지를 다시 확인해주세요."
                        )

                        with st.expander(
                            "🛠️ 디버깅"
                        ):

                            st.write(
                                f"시스템 에러: {e}"
                            )

                            if "result_text" in locals():

                                st.write(
                                    "AI 원본 데이터:",
                                    result_text
                                )


# ============================================================
# 13. AI 결과 상태
# ============================================================

if (
    "form_reset_trigger"
    not in st.session_state
):

    st.session_state.form_reset_trigger = 0


def_ticker = st.session_state.get(
    "ai_ticker",
    ""
)

def_buy_amt = int(
    st.session_state.get(
        "ai_buy_amt",
        0
    )
)

def_roi = float(
    st.session_state.get(
        "ai_roi",
        0.0
    )
)

def_memo = st.session_state.get(
    "ai_memo",
    ""
)

fc = st.session_state.form_reset_trigger


# ============================================================
# 14. 사이드바 거래 입력
# ============================================================

st.sidebar.markdown("---")

st.sidebar.header(
    "📝 매매 기록 입력"
)


with st.sidebar.form(
    "quick_input",
    clear_on_submit=True
):

    date = st.date_input(
        "일자",
        datetime.today()
    )

    ticker = st.text_input(
        "종목명 (예: 삼성전자)",
        value=def_ticker,
        key=f"t_{fc}"
    ).strip()

    st.markdown("---")

    buy_amt = st.number_input(
        "총 매수 금액 (원)",
        value=def_buy_amt,
        step=100000,
        key=f"b_{fc}"
    )

    roi = st.number_input(
        "수익률 (%)",
        value=def_roi,
        format="%.2f",
        key=f"r_{fc}"
    )

    sell_amt = 0.0
    pn_l = 0.0

    if buy_amt != 0:

        pn_l = (
            buy_amt
            *
            (roi / 100)
        )

        sell_amt = (
            buy_amt
            +
            pn_l
        )

        st.info(
            f"""
🧮 **자동 계산 결과**

- 수익금: {pn_l:,.0f}원
- 매도금액: {sell_amt:,.0f}원
"""
        )

    st.markdown("---")

    memo = st.text_input(
        "메모",
        value=def_memo,
        key=f"m_{fc}"
    )

    if st.form_submit_button(
        "기록 저장"
    ):

        if ticker:

            with st.spinner(
                "안전하게 저장 중입니다... 🛡️"
            ):

                try:

                    # ---------------------------------
                    # 새로운 거래 ID 생성
                    # ---------------------------------

                    new_trade_id = (
                        "TRD_"
                        +
                        datetime.now().strftime(
                            "%Y%m%d%H%M%S"
                        )
                        +
                        "_"
                        +
                        str(
                            random.randint(
                                1000,
                                9999
                            )
                        )
                    )

                    new_data = pd.DataFrame(
                        [{
                            "Trade_ID": new_trade_id,
                            "Date": date.strftime(
                                "%Y-%m-%d"
                            ),
                            "Ticker": ticker,
                            "Buy_Amount": buy_amt,
                            "Sell_Amount": sell_amt,
                            "P_L_Amount": pn_l,
                            "ROI_Percent": roi,
                            "Mistake_Tags": "",
                            "Emotion": "",
                            "Discipline": "",
                            "Memo": memo
                        }]
                    )

                    live_df = conn.read(
                        worksheet=0,
                        ttl=0
                    )

                    if live_df.empty:

                        updated_df = new_data

                    else:

                        # 기존 데이터에 Trade_ID 보완
                        if (
                            "Trade_ID"
                            not in live_df.columns
                        ):

                            live_df["Trade_ID"] = [
                                create_legacy_trade_id(
                                    row,
                                    index
                                )

                                for index, row
                                in live_df.iterrows()
                            ]

                        else:

                            for index in live_df.index:

                                if (
                                    pd.isna(
                                        live_df.at[
                                            index,
                                            "Trade_ID"
                                        ]
                                    )
                                    or
                                    str(
                                        live_df.at[
                                            index,
                                            "Trade_ID"
                                        ]
                                    ).strip() == ""
                                ):

                                    live_df.at[
                                        index,
                                        "Trade_ID"
                                    ] = create_legacy_trade_id(
                                        live_df.loc[index],
                                        index
                                    )

                        live_df["Date"] = pd.to_datetime(
                            live_df["Date"],
                            errors="coerce"
                        ).dt.strftime(
                            "%Y-%m-%d"
                        )

                        updated_df = pd.concat(
                            [
                                live_df,
                                new_data
                            ],
                            ignore_index=True
                        )

                    # 컬럼 순서
                    for col in REQUIRED_COLUMNS:

                        if col not in updated_df.columns:
                            updated_df[col] = ""

                    updated_df = updated_df[
                        REQUIRED_COLUMNS
                    ]

                    conn.update(
                        worksheet=0,
                        data=updated_df
                    )

                    # AI 상태 초기화
                    st.session_state.ai_ticker = ""
                    st.session_state.ai_buy_amt = 0
                    st.session_state.ai_roi = 0.0
                    st.session_state.ai_memo = ""

                    st.success(
                        f"✅ {ticker} 저장 완료!"
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        "🚨 저장 실패. "
                        "원본 데이터 보호를 위해 저장을 중단했습니다."
                    )

                    st.write(
                        f"에러 내용: {e}"
                    )

        else:

            st.error(
                "종목명을 입력해주세요."
            )


if krx_list.empty:

    st.sidebar.caption(
        "⚠️ 종목 리스트 로딩 실패"
    )

else:

    st.sidebar.caption(
        f"✅ {len(krx_list):,}개 종목 연결됨"
    )


# ============================================================
# 15. 메인 화면
# ============================================================

st.title(
    "💎 Trading Master Dashboard"
)


# ============================================================
# 데이터가 있는 경우
# ============================================================

if not df.empty:

    # ========================================================
    # 수익 / 손실 색상
    # ========================================================

    def color_profit_loss(val):

        try:

            if pd.isna(val):
                return ""

            if float(val) > 0:

                return (
                    "color: #FF4444; "
                    "font-weight: bold;"
                )

            elif float(val) < 0:

                return (
                    "color: #0066CC; "
                    "font-weight: bold;"
                )

        except Exception:
            pass

        return ""


    # ========================================================
    # 탭
    # ========================================================

    (
        tab1,
        tab2,
        tab3,
        tab4,
        tab5,
        tab6,
        tab7,
        tab8
    ) = st.tabs(
        [
            "📊 차트",
            "📅 월별",
            "📆 연도별",
            "📋 원본",
            "⚖️ 빅터 스페란데오",
            "🎯 R-배수 분석",
            "🔔 손익 분포",
            "🛠️ 거래 관리"
        ]
    )


    # ========================================================
    # 공통 날짜 정보
    # ========================================================

    df["Year"] = (
        df["Date"].dt.year
    )

    df["YearMonth"] = (
        df["Date"].dt.strftime(
            "%Y-%m"
        )
    )


    # ========================================================
    # 전체 통계
    # ========================================================

    total_trades = len(df)

    wins = df[
        df["ROI_Percent"] > 0
    ]

    losses = df[
        df["ROI_Percent"] <= 0
    ]

    win_rate = (
        len(wins)
        /
        total_trades
        *
        100
        if total_trades > 0
        else 0
    )

    avg_win = (
        wins["ROI_Percent"].mean()
        if not wins.empty
        else 0
    )

    avg_loss = (
        abs(
            losses["ROI_Percent"].mean()
        )
        if not losses.empty
        else 0
    )

    risk_reward_ratio = (
        avg_win
        /
        avg_loss
        if avg_loss > 0
        else 0
    )

    avg_roi = (
        df["ROI_Percent"].mean()
    )


    # ========================================================
    # TAB 1 : 차트
    # ========================================================

    with tab1:

        st.subheader(
            "🏆 전체 종합 성적표"
        )

        total_pl = (
            df["P_L_Amount"].sum()
        )

        total_cnt = len(df)

        all_wins = df[
            df["ROI_Percent"] > 0
        ]

        all_losses = df[
            df["ROI_Percent"] <= 0
        ]

        gross_p = (
            all_wins["P_L_Amount"].sum()
        )

        gross_l = abs(
            all_losses[
                "P_L_Amount"
            ].sum()
        )

        total_pf = (
            gross_p / gross_l
            if gross_l > 0
            else 0
        )

        all_avg_profit_amt = (
            all_wins[
                "P_L_Amount"
            ].mean()
            if not all_wins.empty
            else 0
        )

        all_avg_loss_amt = abs(
            all_losses[
                "P_L_Amount"
            ].mean()
        ) if not all_losses.empty else 0

        money_rr_ratio = (
            all_avg_profit_amt
            /
            all_avg_loss_amt
            if all_avg_loss_amt > 0
            else 0
        )

        all_avg_profit_pct = (
            all_wins[
                "ROI_Percent"
            ].mean()
            if not all_wins.empty
            else 0
        )

        all_avg_loss_pct = abs(
            all_losses[
                "ROI_Percent"
            ].mean()
        ) if not all_losses.empty else 0

        period_rr_ratio = (
            all_avg_profit_pct
            /
            all_avg_loss_pct
            if all_avg_loss_pct > 0
            else 0
        )

        win_prob = (
            len(all_wins)
            /
            total_cnt
            if total_cnt > 0
            else 0
        )

        loss_prob = (
            1 - win_prob
        )

        expectancy = (
            win_prob
            *
            all_avg_profit_pct
        ) - (
            loss_prob
            *
            all_avg_loss_pct
        )

        if money_rr_ratio > 0:

            kelly_fraction = (
                win_prob
                -
                (
                    loss_prob
                    /
                    money_rr_ratio
                )
            )

            kelly_pct = max(
                0.0,
                kelly_fraction * 100
            )

        else:

            kelly_pct = 0.0


        m1, m2, m3, m4, m5 = st.columns(5)

        m1.metric(
            "💰 누적 총 손익",
            f"{total_pl:,.0f}원"
        )

        m2.metric(
            "🎯 전체 승률",
            f"{win_rate:.1f}%"
        )

        m3.metric(
            "🔮 기간 기댓값",
            f"{expectancy:.2f}%"
        )

        m4.metric(
            "💎 Profit Factor",
            f"{total_pf:.2f}"
        )

        m5.metric(
            "⚖️ 켈리 베팅 비중",
            f"{kelly_pct:.1f}%"
        )


        st.divider()

        st.markdown(
            "##### 💵 금액 성적표"
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "평균 수익금",
            f"{all_avg_profit_amt:,.0f}원"
        )

        c2.metric(
            "평균 손실금",
            f"{all_avg_loss_amt:,.0f}원"
        )

        c3.metric(
            "⚖️ 금액 손익비",
            f"{money_rr_ratio:.2f}"
        )

        c4.metric(
            "🛒 총 매수 대금",
            f"{df['Buy_Amount'].sum():,.0f}원"
        )


        st.markdown(
            "##### 📊 기간 성적표"
        )

        c5, c6, c7, c8 = st.columns(4)

        c5.metric(
            "평균 수익률",
            f"+{all_avg_profit_pct:.2f}%"
        )

        c6.metric(
            "평균 손실률",
            f"-{all_avg_loss_pct:.2f}%"
        )

        c7.metric(
            "⚖️ 기간 손익비",
            f"{period_rr_ratio:.2f}"
        )

        c8.metric(
            "📝 총 거래 횟수",
            f"{total_cnt:,}회"
        )


        st.divider()

        st.subheader(
            "🚀 내 계좌 vs KOSPI 지수"
        )

        daily_df = (
            df
            .groupby("Date")[
                "P_L_Amount"
            ]
            .sum()
            .reset_index()
            .sort_values("Date")
        )

        daily_df["Cumulative"] = (
            daily_df["P_L_Amount"]
            .cumsum()
        )

        try:

            start = (
                daily_df["Date"]
                .min()
                .strftime("%Y-%m-%d")
            )

            kospi = yf.download(
                "^KS11",
                start=start,
                progress=False
            )["Close"].reset_index()

            kospi.columns = [
                "Date",
                "KOSPI"
            ]

            kospi["Date"] = pd.to_datetime(
                kospi["Date"]
            ).dt.tz_localize(None)

            base = alt.Chart(
                daily_df
            ).encode(
                x="Date:T"
            )

            my_chart = (
                base
                .mark_line(
                    color="#00AA00",
                    strokeWidth=3
                )
                .encode(
                    y=alt.Y(
                        "Cumulative:Q",
                        title="내 수익"
                    ),
                    tooltip=[
                        "Date",
                        "Cumulative"
                    ]
                )
            )

            kospi_chart = (
                alt.Chart(kospi)
                .mark_line(
                    color="#FF4444",
                    strokeDash=[5, 5]
                )
                .encode(
                    x="Date:T",
                    y=alt.Y(
                        "KOSPI:Q",
                        title="KOSPI",
                        scale=alt.Scale(
                            zero=False
                        )
                    )
                )
            )

            st.altair_chart(
                alt.layer(
                    my_chart,
                    kospi_chart
                ).resolve_scale(
                    y="independent"
                ),
                use_container_width=True
            )

        except Exception:

            st.line_chart(
                daily_df.set_index(
                    "Date"
                )["Cumulative"]
            )


        st.subheader(
            "📊 월별 손익 흐름"
        )

        st.bar_chart(
            df.groupby(
                "YearMonth"
            )[
                "P_L_Amount"
            ].sum()
        )


    # ========================================================
    # TAB 2 : 월별
    # ========================================================

    with tab2:

        st.subheader(
            "📅 월별 상세 성적표"
        )

        monthly_stats = []

        for ym, group in df.groupby(
            "YearMonth"
        ):

            g_wins = group[
                group["ROI_Percent"] > 0
            ]

            g_losses = group[
                group["ROI_Percent"] <= 0
            ]

            gross_profit = (
                group[
                    group["P_L_Amount"] > 0
                ]["P_L_Amount"].sum()
            )

            gross_loss = abs(
                group[
                    group["P_L_Amount"] <= 0
                ]["P_L_Amount"].sum()
            )

            m_avg_profit_amt = (
                group[
                    group["P_L_Amount"] > 0
                ]["P_L_Amount"].mean()
                if not group[
                    group["P_L_Amount"] > 0
                ].empty
                else 0
            )

            m_avg_loss_amt = (
                group[
                    group["P_L_Amount"] <= 0
                ]["P_L_Amount"].mean()
                if not group[
                    group["P_L_Amount"] <= 0
                ].empty
                else 0
            )

            pf = (
                gross_profit
                /
                gross_loss
                if gross_loss > 0
                else 0
            )

            m_avg_gain_pct = (
                g_wins[
                    "ROI_Percent"
                ].mean()
                if not g_wins.empty
                else 0
            )

            m_avg_loss_pct = abs(
                g_losses[
                    "ROI_Percent"
                ].mean()
            ) if not g_losses.empty else 0

            m_wl_ratio = (
                m_avg_gain_pct
                /
                m_avg_loss_pct
                if m_avg_loss_pct > 0
                else 0
            )

            m_buy_vol = (
                group[
                    "Buy_Amount"
                ].sum()
            )

            m_count = len(group)

            win_prob = (
                len(g_wins)
                /
                m_count
                if m_count > 0
                else 0
            )

            loss_prob = (
                1 - win_prob
            )

            m_expectancy = (
                win_prob
                *
                m_avg_gain_pct
            ) - (
                loss_prob
                *
                m_avg_loss_pct
            )

            monthly_stats.append(
                {
                    "기간": str(ym),
                    "총 손익": float(
                        group[
                            "P_L_Amount"
                        ].sum()
                    ),
                    "평균수익": float(
                        m_avg_profit_amt
                    ),
                    "평균손실": float(
                        m_avg_loss_amt
                    ),
                    "거래횟수": int(
                        m_count
                    ),
                    "승률": float(
                        win_prob * 100
                    ),
                    "손익비": float(
                        m_wl_ratio
                    ),
                    "PF": float(
                        pf
                    ),
                    "기대수익": float(
                        m_expectancy
                    ),
                    "매수총액": float(
                        m_buy_vol
                    )
                }
            )

        df_monthly = (
            pd.DataFrame(
                monthly_stats
            )
            .sort_values(
                "기간",
                ascending=False
            )
        )

        format_dict_m = {
            "총 손익": "{:+,.0f}원",
            "평균수익": "{:,.0f}원",
            "평균손실": "{:,.0f}원",
            "거래횟수": "{:,}회",
            "승률": "{:.1f}%",
            "손익비": "{:.2f}",
            "PF": "{:.2f}",
            "기대수익": "{:+.2f}%",
            "매수총액": "{:,.0f}원"
        }

        try:

            styled_monthly = (
                df_monthly.style
                .map(
                    color_profit_loss,
                    subset=[
                        "총 손익",
                        "기대수익"
                    ]
                )
                .format(
                    format_dict_m
                )
            )

        except AttributeError:

            styled_monthly = (
                df_monthly.style
                .applymap(
                    color_profit_loss,
                    subset=[
                        "총 손익",
                        "기대수익"
                    ]
                )
                .format(
                    format_dict_m
                )
            )

        st.dataframe(
            styled_monthly,
            use_container_width=True
        )


    # ========================================================
    # TAB 3 : 연도별
    # ========================================================

    with tab3:

        st.subheader(
            "📆 연도별 종합 성적표"
        )

        yearly_stats = []

        for y, group in df.groupby(
            "Year"
        ):

            g_wins = group[
                group["ROI_Percent"] > 0
            ]

            g_losses = group[
                group["ROI_Percent"] <= 0
            ]

            gross_profit = (
                group[
                    group["P_L_Amount"] > 0
                ]["P_L_Amount"].sum()
            )

            gross_loss = abs(
                group[
                    group["P_L_Amount"] <= 0
                ]["P_L_Amount"].sum()
            )

            y_avg_profit_amt = (
                group[
                    group["P_L_Amount"] > 0
                ]["P_L_Amount"].mean()
                if not group[
                    group["P_L_Amount"] > 0
                ].empty
                else 0
            )

            y_avg_loss_amt = (
                group[
                    group["P_L_Amount"] <= 0
                ]["P_L_Amount"].mean()
                if not group[
                    group["P_L_Amount"] <= 0
                ].empty
                else 0
            )

            pf = (
                gross_profit
                /
                gross_loss
                if gross_loss > 0
                else 0
            )

            y_avg_gain_pct = (
                g_wins[
                    "ROI_Percent"
                ].mean()
                if not g_wins.empty
                else 0
            )

            y_avg_loss_pct = abs(
                g_losses[
                    "ROI_Percent"
                ].mean()
            ) if not g_losses.empty else 0

            y_wl_ratio = (
                y_avg_gain_pct
                /
                y_avg_loss_pct
                if y_avg_loss_pct > 0
                else 0
            )

            y_buy_vol = (
                group[
                    "Buy_Amount"
                ].sum()
            )

            y_count = len(group)

            win_prob = (
                len(g_wins)
                /
                y_count
                if y_count > 0
                else 0
            )

            loss_prob = (
                1 - win_prob
            )

            y_expectancy = (
                win_prob
                *
                y_avg_gain_pct
            ) - (
                loss_prob
                *
                y_avg_loss_pct
            )

            yearly_stats.append(
                {
                    "연도": int(y),
                    "총 손익": float(
                        group[
                            "P_L_Amount"
                        ].sum()
                    ),
                    "평균수익": float(
                        y_avg_profit_amt
                    ),
                    "평균손실": float(
                        y_avg_loss_amt
                    ),
                    "거래횟수": int(
                        y_count
                    ),
                    "승률": float(
                        win_prob * 100
                    ),
                    "손익비": float(
                        y_wl_ratio
                    ),
                    "PF": float(
                        pf
                    ),
                    "기대수익": float(
                        y_expectancy
                    ),
                    "매수총액": float(
                        y_buy_vol
                    )
                }
            )

        df_yearly = (
            pd.DataFrame(
                yearly_stats
            )
            .sort_values(
                "연도",
                ascending=False
            )
        )

        format_dict_y = {
            "총 손익": "{:+,.0f}원",
            "평균수익": "{:,.0f}원",
            "평균손실": "{:,.0f}원",
            "거래횟수": "{:,}회",
            "승률": "{:.1f}%",
            "손익비": "{:.2f}",
            "PF": "{:.2f}",
            "기대수익": "{:+.2f}%",
            "매수총액": "{:,.0f}원"
        }

        try:

            styled_yearly = (
                df_yearly.style
                .map(
                    color_profit_loss,
                    subset=[
                        "총 손익",
                        "기대수익"
                    ]
                )
                .format(
                    format_dict_y
                )
            )

        except AttributeError:

            styled_yearly = (
                df_yearly.style
                .applymap(
                    color_profit_loss,
                    subset=[
                        "총 손익",
                        "기대수익"
                    ]
                )
                .format(
                    format_dict_y
                )
            )

        st.dataframe(
            styled_yearly,
            use_container_width=True
        )


    # ========================================================
    # TAB 4 : 원본
    # ========================================================

    with tab4:

        df_sorted = (
            df
            .sort_values(
                "Date",
                ascending=False
            )
        )

        display_cols = [
            "Date",
            "Ticker",
            "Buy_Amount",
            "Sell_Amount",
            "P_L_Amount",
            "ROI_Percent",
            "Memo"
        ]

        display_df = df_sorted[
            display_cols
        ].copy()

        try:

            styled_df = (
                display_df.style
                .map(
                    color_profit_loss,
                    subset=[
                        "ROI_Percent",
                        "P_L_Amount"
                    ]
                )
                .format(
                    {
                        "Buy_Amount": "{:,.0f}",
                        "Sell_Amount": "{:,.0f}",
                        "ROI_Percent": "{:+.2f}%",
                        "P_L_Amount": "{:+,.0f}"
                    }
                )
            )

        except AttributeError:

            styled_df = (
                display_df.style
                .applymap(
                    color_profit_loss,
                    subset=[
                        "ROI_Percent",
                        "P_L_Amount"
                    ]
                )
                .format(
                    {
                        "Buy_Amount": "{:,.0f}",
                        "Sell_Amount": "{:,.0f}",
                        "ROI_Percent": "{:+.2f}%",
                        "P_L_Amount": "{:+,.0f}"
                    }
                )
            )

        st.dataframe(
            styled_df,
            use_container_width=True
        )


    # ========================================================
    # TAB 5 : Victor Sperandeo
    # ========================================================

    with tab5:

        st.subheader(
            "⚖️ Victor Sperandeo's Reward-to-Risk Analysis"
        )

        st.markdown(
            "> **\"최소 3:1의 보상 비율이 나오지 않는 거래는 시작조차 하지 마라.\"**"
        )

        vic_period = st.radio(
            "📅 분석 기간 선택",
            [
                "전체",
                "최근 1개월",
                "최근 3개월",
                "최근 6개월",
                "최근 1년"
            ],
            horizontal=True,
            key="vic_radio"
        )

        vic_df = df.copy()

        today = datetime.today()

        if vic_period == "최근 1개월":

            vic_df = vic_df[
                vic_df["Date"]
                >=
                (
                    today
                    -
                    timedelta(days=30)
                )
            ]

        elif vic_period == "최근 3개월":

            vic_df = vic_df[
                vic_df["Date"]
                >=
                (
                    today
                    -
                    timedelta(days=90)
                )
            ]

        elif vic_period == "최근 6개월":

            vic_df = vic_df[
                vic_df["Date"]
                >=
                (
                    today
                    -
                    timedelta(days=180)
                )
            ]

        elif vic_period == "최근 1년":

            vic_df = vic_df[
                vic_df["Date"]
                >=
                (
                    today
                    -
                    timedelta(days=365)
                )
            ]

        if not vic_df.empty:

            v_wins = vic_df[
                vic_df["ROI_Percent"] > 0
            ]

            v_losses = vic_df[
                vic_df["ROI_Percent"] <= 0
            ]

            v_win_rate = (
                len(v_wins)
                /
                len(vic_df)
                *
                100
            )

            v_avg_win = (
                v_wins[
                    "ROI_Percent"
                ].mean()
                if not v_wins.empty
                else 0
            )

            v_avg_loss = abs(
                v_losses[
                    "ROI_Percent"
                ].mean()
            ) if not v_losses.empty else 0

            v_rr_ratio = (
                v_avg_win
                /
                v_avg_loss
                if v_avg_loss > 0
                else 0
            )

            v_win_prob = (
                v_win_rate / 100
            )

            v_loss_prob = (
                1 - v_win_prob
            )

            v_expectancy = (
                v_win_prob
                *
                v_avg_win
            ) - (
                v_loss_prob
                *
                v_avg_loss
            )

            st.caption(
                f"🔎 **{vic_period}** 데이터 기준 분석 ({len(vic_df)}건)"
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "기간 손익비",
                f"{v_rr_ratio:.2f} : 1"
            )

            c2.metric(
                "기간 기댓값",
                f"{v_expectancy:.2f}%"
            )

            c3.metric(
                "빅터의 목표 기준",
                "3.0 : 1"
            )

            st.divider()

            target_roi_period = (
                v_avg_loss * 3
                if v_avg_loss > 0
                else 10
            )

            conditions = [
                (
                    vic_df["ROI_Percent"]
                    >= target_roi_period
                ),
                (
                    vic_df["ROI_Percent"] > 0
                )
            ]

            colors = [
                "#00CC00",
                "#F1C40F"
            ]

            vic_df["Color_Hex"] = np.select(
                conditions,
                colors,
                default="#FF4B4B"
            )

            scatter_chart = (
                alt.Chart(vic_df)
                .mark_circle(size=100)
                .encode(
                    x=alt.X(
                        "Date",
                        title="거래 일자"
                    ),
                    y=alt.Y(
                        "ROI_Percent",
                        title="수익률 (%)"
                    ),
                    color=alt.Color(
                        "Color_Hex",
                        scale=None,
                        legend=None
                    ),
                    tooltip=[
                        "Ticker",
                        "Date",
                        "ROI_Percent",
                        "P_L_Amount"
                    ]
                )
                .interactive()
            )

            rule_line = (
                alt.Chart(
                    pd.DataFrame(
                        {
                            "y": [
                                target_roi_period
                            ]
                        }
                    )
                )
                .mark_rule(
                    color="blue",
                    strokeDash=[3, 3]
                )
                .encode(
                    y="y"
                )
            )

            st.altair_chart(
                scatter_chart + rule_line,
                use_container_width=True
            )

        else:

            st.info(
                f"📭 선택하신 **{vic_period}**에는 매매 기록이 없습니다."
            )


    # ========================================================
    # TAB 6 : R 배수
    # ========================================================

    with tab6:

        st.subheader(
            "🎯 R-배수 분석"
        )

        st.markdown(
            "**'R'은 나의 위험(Risk) 단위입니다.**"
        )

        r_period = st.radio(
            "📅 분석 기간 선택",
            [
                "전체",
                "최근 1개월",
                "최근 3개월",
                "최근 6개월",
                "최근 1년"
            ],
            horizontal=True,
            key="r_radio"
        )

        r_df = df.copy()

        today = datetime.today()

        if r_period == "최근 1개월":

            r_df = r_df[
                r_df["Date"]
                >=
                today - timedelta(days=30)
            ]

        elif r_period == "최근 3개월":

            r_df = r_df[
                r_df["Date"]
                >=
                today - timedelta(days=90)
            ]

        elif r_period == "최근 6개월":

            r_df = r_df[
                r_df["Date"]
                >=
                today - timedelta(days=180)
            ]

        elif r_period == "최근 1년":

            r_df = r_df[
                r_df["Date"]
                >=
                today - timedelta(days=365)
            ]

        if not r_df.empty:

            r_losses = r_df[
                r_df["P_L_Amount"] < 0
            ]

            if not r_losses.empty:

                avg_loss_abs = abs(
                    r_losses[
                        "P_L_Amount"
                    ].mean()
                )

            else:

                all_losses = df[
                    df["P_L_Amount"] < 0
                ]

                avg_loss_abs = (
                    abs(
                        all_losses[
                            "P_L_Amount"
                        ].mean()
                    )
                    if not all_losses.empty
                    else 1
                )

            r_df["R_Value"] = (
                r_df["P_L_Amount"]
                /
                avg_loss_abs
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                f"나의 1R ({r_period})",
                f"{avg_loss_abs:,.0f}원"
            )

            c2.metric(
                "평균 R-배수",
                f"{r_df['R_Value'].mean():.2f}R"
            )

            c3.metric(
                "최고 R-배수",
                f"{r_df['R_Value'].max():.2f}R"
            )

            st.divider()

            df_sorted_r = (
                r_df
                .sort_values("Date")
                .copy()
            )

            df_sorted_r[
                "Cumulative_R"
            ] = (
                df_sorted_r[
                    "R_Value"
                ].cumsum()
            )

            df_sorted_r[
                "Trade_Num"
            ] = range(
                1,
                len(df_sorted_r) + 1
            )

            line_r = (
                alt.Chart(df_sorted_r)
                .mark_line(color="blue")
                .encode(
                    x=alt.X(
                        "Trade_Num",
                        title="거래 횟수"
                    ),
                    y=alt.Y(
                        "Cumulative_R",
                        title="누적 R"
                    ),
                    tooltip=[
                        "Date",
                        "R_Value",
                        "Cumulative_R"
                    ]
                )
            )

            st.altair_chart(
                line_r,
                use_container_width=True
            )

        else:

            st.info(
                f"📭 선택하신 **{r_period}**에는 매매 기록이 없습니다."
            )


    # ========================================================
    # TAB 7 : 손익 분포
    # ========================================================

    with tab7:

        st.subheader(
            "🔔 손익 분포"
        )

        st.markdown(
            "**왼쪽(손실)은 짧게, 오른쪽(수익)은 길게!**"
        )

        bin_step = 2.5

        df_dist = df.copy()

        hist_chart = (
            alt.Chart(df_dist)
            .mark_bar()
            .encode(
                x=alt.X(
                    "ROI_Percent",
                    bin=alt.Bin(
                        step=bin_step
                    ),
                    title="수익률 구간 (%)"
                ),
                y=alt.Y(
                    "count()",
                    title="거래 횟수"
                ),
                color=alt.condition(
                    alt.datum.ROI_Percent > 0,
                    alt.value("#00AA00"),
                    alt.value("#FF4444")
                ),
                tooltip=[
                    "count()",
                    alt.Tooltip(
                        "ROI_Percent",
                        bin=True,
                        title="수익률 구간"
                    )
                ]
            )
            .properties(
                height=400
            )
        )

        rule = (
            alt.Chart(
                pd.DataFrame(
                    {"x": [0]}
                )
            )
            .mark_rule(
                color="black",
                strokeDash=[2, 2]
            )
            .encode(
                x="x"
            )
        )

        st.altair_chart(
            hist_chart + rule,
            use_container_width=True
        )

        skew = (
            df["ROI_Percent"].skew()
        )

        st.info(
            f"📊 **분포도 분석 "
            f"(Skewness: {skew:.2f})**"
        )

        if skew > 0.5:

            st.success(
                "✅ Positive Skew — "
                "수익 쪽 꼬리가 길게 나타납니다."
            )

        elif skew < -0.5:

            st.error(
                "🚨 Negative Skew — "
                "손실 쪽 꼬리가 길게 나타납니다."
            )

        else:

            st.warning(
                "⚠️ Symmetric — "
                "수익과 손실 패턴이 비슷합니다."
            )


    # ========================================================
    # TAB 8 : 거래 관리
    # ========================================================

    with tab8:

        st.subheader(
            "🛠️ 거래 관리"
        )

        st.caption(
            "거래를 선택하면 상세 내용을 확인하고 "
            "수정하거나 삭제할 수 있습니다."
        )

        # ----------------------------------------------------
        # 거래 목록
        # ----------------------------------------------------

        manage_df = df.copy()

        manage_df = (
            manage_df
            .sort_values(
                "Date",
                ascending=False
            )
        )

        manage_df["표시"] = (
            manage_df["Date"]
            .dt.strftime(
                "%Y-%m-%d"
            )
            +
            "  |  "
            +
            manage_df["Ticker"]
            +
            "  |  "
            +
            manage_df[
                "ROI_Percent"
            ].map(
                lambda x:
                f"{x:+.2f}%"
            )
            +
            "  |  "
            +
            manage_df[
                "P_L_Amount"
            ].map(
                lambda x:
                f"{x:+,.0f}원"
            )
        )

        st.markdown(
            "### 📋 거래 선택"
        )

        selected_id = st.selectbox(
            "수정 또는 삭제할 거래",
            options=manage_df[
                "Trade_ID"
            ].tolist(),
            format_func=lambda x:
                manage_df.loc[
                    manage_df[
                        "Trade_ID"
                    ] == x,
                    "표시"
                ].iloc[0],
            key="trade_manager_select"
        )


        # ----------------------------------------------------
        # 선택 거래
        # ----------------------------------------------------

        selected_rows = manage_df[
            manage_df[
                "Trade_ID"
            ] == selected_id
        ]

        if not selected_rows.empty:

            selected = (
                selected_rows.iloc[0]
            )

            st.divider()

            st.markdown(
                "### 🔎 거래 상세"
            )

            d1, d2, d3, d4 = st.columns(4)

            d1.metric(
                "종목",
                selected["Ticker"]
            )

            d2.metric(
                "거래일",
                selected["Date"].strftime(
                    "%Y-%m-%d"
                )
            )

            d3.metric(
                "수익률",
                f"{selected['ROI_Percent']:+.2f}%"
            )

            d4.metric(
                "손익",
                f"{selected['P_L_Amount']:+,.0f}원"
            )

            d5, d6 = st.columns(2)

            d5.metric(
                "매수금액",
                f"{selected['Buy_Amount']:,.0f}원"
            )

            d6.metric(
                "매도금액",
                f"{selected['Sell_Amount']:,.0f}원"
            )

            if str(
                selected["Memo"]
            ).strip():

                st.info(
                    f"📝 메모: {selected['Memo']}"
                )


            # =================================================
            # 수정
            # =================================================

            st.divider()

            st.markdown(
                "### ✏️ 거래 수정"
            )

            with st.form(
                f"edit_trade_form_{selected_id}"
            ):

                edit_date = st.date_input(
                    "거래일",
                    value=selected[
                        "Date"
                    ].date()
                )

                edit_ticker = st.text_input(
                    "종목명",
                    value=str(
                        selected[
                            "Ticker"
                        ]
                    )
                )

                e1, e2 = st.columns(2)

                with e1:

                    edit_buy = st.number_input(
                        "매수금액",
                        min_value=0,
                        value=int(
                            selected[
                                "Buy_Amount"
                            ]
                        ),
                        step=100000
                    )

                with e2:

                    edit_roi = st.number_input(
                        "수익률 (%)",
                        value=float(
                            selected[
                                "ROI_Percent"
                            ]
                        ),
                        format="%.2f"
                    )

                edit_pl = (
                    edit_buy
                    *
                    edit_roi
                    /
                    100
                )

                edit_sell = (
                    edit_buy
                    +
                    edit_pl
                )

                st.info(
                    f"""
🧮 **수정 후 자동 계산**

- 손익: {edit_pl:+,.0f}원
- 매도금액: {edit_sell:,.0f}원
"""
                )

                edit_memo = st.text_area(
                    "메모",
                    value=str(
                        selected[
                            "Memo"
                        ]
                    ),
                    height=100
                )

                update_button = st.form_submit_button(
                    "💾 거래 수정 저장",
                    use_container_width=True
                )


                # ---------------------------------------------
                # 수정 실행
                # ---------------------------------------------

                if update_button:

                    if not edit_ticker.strip():

                        st.error(
                            "종목명을 입력해주세요."
                        )

                    else:

                        try:

                            live_df = conn.read(
                                worksheet=0,
                                ttl=0
                            )

                            if live_df.empty:

                                st.error(
                                    "Google Sheets에 "
                                    "거래 데이터가 없습니다."
                                )

                            else:

                                # ---------------------------------
                                # Trade_ID 보완
                                # ---------------------------------

                                if (
                                    "Trade_ID"
                                    not in live_df.columns
                                ):

                                    live_df[
                                        "Trade_ID"
                                    ] = [
                                        create_legacy_trade_id(
                                            row,
                                            index
                                        )

                                        for index, row
                                        in live_df.iterrows()
                                    ]

                                else:

                                    for index in live_df.index:

                                        current_id = (
                                            live_df.at[
                                                index,
                                                "Trade_ID"
                                            ]
                                        )

                                        if (
                                            pd.isna(
                                                current_id
                                            )
                                            or
                                            str(
                                                current_id
                                            ).strip() == ""
                                        ):

                                            live_df.at[
                                                index,
                                                "Trade_ID"
                                            ] = create_legacy_trade_id(
                                                live_df.loc[
                                                    index
                                                ],
                                                index
                                            )

                                # ---------------------------------
                                # 선택 거래 찾기
                                # ---------------------------------

                                target_idx = (
                                    live_df.index[
                                        live_df[
                                            "Trade_ID"
                                        ].astype(str)
                                        ==
                                        str(selected_id)
                                    ]
                                )

                                if len(
                                    target_idx
                                ) == 0:

                                    st.error(
                                        "수정하려는 거래를 "
                                        "찾을 수 없습니다."
                                    )

                                else:

                                    idx = target_idx[0]

                                    # -----------------------------
                                    # 데이터 수정
                                    # -----------------------------

                                    live_df.at[
                                        idx,
                                        "Date"
                                    ] = edit_date.strftime(
                                        "%Y-%m-%d"
                                    )

                                    live_df.at[
                                        idx,
                                        "Ticker"
                                    ] = edit_ticker.strip()

                                    live_df.at[
                                        idx,
                                        "Buy_Amount"
                                    ] = edit_buy

                                    live_df.at[
                                        idx,
                                        "Sell_Amount"
                                    ] = edit_sell

                                    live_df.at[
                                        idx,
                                        "P_L_Amount"
                                    ] = edit_pl

                                    live_df.at[
                                        idx,
                                        "ROI_Percent"
                                    ] = edit_roi

                                    live_df.at[
                                        idx,
                                        "Memo"
                                    ] = edit_memo

                                    # -----------------------------
                                    # 컬럼 보장
                                    # -----------------------------

                                    for col in REQUIRED_COLUMNS:

                                        if (
                                            col
                                            not in live_df.columns
                                        ):

                                            live_df[
                                                col
                                            ] = ""

                                    live_df = live_df[
                                        REQUIRED_COLUMNS
                                    ]

                                    # -----------------------------
                                    # Google Sheets 저장
                                    # -----------------------------

                                    conn.update(
                                        worksheet=0,
                                        data=live_df
                                    )

                                    st.success(
                                        f"✅ {edit_ticker} "
                                        f"거래가 수정되었습니다."
                                    )

                                    st.rerun()

                        except Exception as e:

                            st.error(
                                f"🚨 거래 수정 중 오류: {e}"
                            )


            # =================================================
            # 삭제
            # =================================================

            st.divider()

            st.markdown(
                "### 🗑️ 거래 삭제"
            )

            st.warning(
                f"""
⚠️ **삭제 대상**

종목: **{selected['Ticker']}**

거래일: **{selected['Date'].strftime('%Y-%m-%d')}**

수익률: **{selected['ROI_Percent']:+.2f}%**

손익: **{selected['P_L_Amount']:+,.0f}원**

삭제하면 Google Sheets에서도 해당 거래가 제거됩니다.
"""
            )

            delete_confirm = st.checkbox(
                "위 거래를 정말 삭제하겠습니다.",
                key=f"delete_confirm_{selected_id}"
            )

            delete_button = st.button(
                "🗑️ 이 거래 영구 삭제",
                disabled=not delete_confirm,
                use_container_width=True,
                key=f"delete_button_{selected_id}"
            )

            if delete_button:

                try:

                    live_df = conn.read(
                        worksheet=0,
                        ttl=0
                    )

                    if live_df.empty:

                        st.error(
                            "삭제할 데이터가 없습니다."
                        )

                    else:

                        # -----------------------------------------
                        # Trade_ID 보완
                        # -----------------------------------------

                        if (
                            "Trade_ID"
                            not in live_df.columns
                        ):

                            live_df[
                                "Trade_ID"
                            ] = [
                                create_legacy_trade_id(
                                    row,
                                    index
                                )

                                for index, row
                                in live_df.iterrows()
                            ]

                        else:

                            for index in live_df.index:

                                current_id = (
                                    live_df.at[
                                        index,
                                        "Trade_ID"
                                    ]
                                )

                                if (
                                    pd.isna(
                                        current_id
                                    )
                                    or
                                    str(
                                        current_id
                                    ).strip() == ""
                                ):

                                    live_df.at[
                                        index,
                                        "Trade_ID"
                                    ] = create_legacy_trade_id(
                                        live_df.loc[
                                            index
                                        ],
                                        index
                                    )

                        original_count = len(
                            live_df
                        )

                        # -----------------------------------------
                        # 선택 거래 삭제
                        # -----------------------------------------

                        live_df = live_df[
                            live_df[
                                "Trade_ID"
                            ].astype(str)
                            !=
                            str(selected_id)
                        ].copy()

                        if (
                            len(live_df)
                            ==
                            original_count
                        ):

                            st.error(
                                "삭제하려는 거래를 "
                                "찾지 못했습니다."
                            )

                        else:

                            # 컬럼 순서
                            for col in REQUIRED_COLUMNS:

                                if (
                                    col
                                    not in live_df.columns
                                ):

                                    live_df[
                                        col
                                    ] = ""

                            live_df = live_df[
                                REQUIRED_COLUMNS
                            ]

                            conn.update(
                                worksheet=0,
                                data=live_df
                            )

                            st.success(
                                f"🗑️ {selected['Ticker']} "
                                f"거래가 삭제되었습니다."
                            )

                            st.rerun()

                except Exception as e:

                    st.error(
                        f"🚨 거래 삭제 중 오류: {e}"
                    )


# ============================================================
# 데이터가 없는 경우
# ============================================================

else:

    st.info(
        "👈 사이드바에서 매매 기록을 입력하면 "
        "대시보드가 활성화됩니다."
                    )
