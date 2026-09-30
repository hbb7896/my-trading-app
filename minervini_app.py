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
# 4. 기존 거래용 Trade_ID 생성
# ============================================================

def create_legacy_trade_id(row, index):
    """
    기존 Google Sheet에 Trade_ID가 없는 거래에
    고유 ID를 만들어준다.

    중요:
    join() 오류를 막기 위해 모든 값을 str()로 변환한다.
    """

    values = [
        str(index),
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
# 5. 신규 거래 Trade_ID 생성
# ============================================================

def create_new_trade_id():

    timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S%f"
    )

    random_number = random.randint(
        1000,
        9999
    )

    return f"TRD_{timestamp}_{random_number}"


# ============================================================
# 6. 설정값 불러오기
# ============================================================

def load_status():

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
            and
            history_str != "nan"
        ):

            history = history_str.split(",")

        else:

            history = []

        return equity, max_pos, history

    except Exception:

        return 20000000, 5000000, []


# ============================================================
# 7. 설정값 저장
# ============================================================

def save_status(
    equity,
    max_pos,
    history
):

    try:

        history_str = ",".join(
            [str(x) for x in history]
        )

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
            f"설정 저장 실패: {e}"
        )


# ============================================================
# 8. 설정 불러오기
# ============================================================

@st.cache_data(ttl=0)
def load_settings():

    try:

        config_df = conn.read(
            worksheet=1,
            ttl=0
        )

        if not config_df.empty:

            return (
                config_df
                .iloc[0]
                .to_dict()
            )

    except Exception:

        pass

    return {}


saved_config = load_settings()


# ============================================================
# 9. KRX 종목 리스트
# ============================================================

@st.cache_data(ttl=3600)
def get_krx_list():

    try:

        krx_df = fdr.StockListing(
            "KRX"
        )

        return krx_df[
            [
                "Code",
                "Name",
                "Market"
            ]
        ]

    except Exception:

        return pd.DataFrame()


# ============================================================
# 10. 거래 데이터 정리 함수
# ============================================================

def normalize_trade_dataframe(raw_df):

    if raw_df is None or raw_df.empty:

        return pd.DataFrame(
            columns=REQUIRED_COLUMNS
        )

    clean_df = raw_df.copy()

    # --------------------------------------------------------
    # Date가 완전히 없는 행 제거
    # --------------------------------------------------------

    if "Date" not in clean_df.columns:

        clean_df["Date"] = None

    clean_df = clean_df.dropna(
        subset=["Date"]
    ).copy()

    if clean_df.empty:

        return pd.DataFrame(
            columns=REQUIRED_COLUMNS
        )

    # --------------------------------------------------------
    # 필요한 컬럼 생성
    # --------------------------------------------------------

    defaults = {
        "Trade_ID": "",
        "Ticker": "",
        "Buy_Amount": 0.0,
        "Sell_Amount": 0.0,
        "P_L_Amount": 0.0,
        "ROI_Percent": 0.0,
        "Mistake_Tags": "",
        "Emotion": "",
        "Discipline": "",
        "Memo": ""
    }

    for col, default_value in defaults.items():

        if col not in clean_df.columns:

            clean_df[col] = default_value

    # --------------------------------------------------------
    # 숫자형 컬럼 정리
    # --------------------------------------------------------

    numeric_columns = [
        "P_L_Amount",
        "ROI_Percent",
        "Buy_Amount",
        "Sell_Amount"
    ]

    for col in numeric_columns:

        clean_df[col] = (
            clean_df[col]
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
            .str.replace(
                "원",
                "",
                regex=False
            )
            .str.strip()
        )

        clean_df[col] = pd.to_numeric(
            clean_df[col],
            errors="coerce"
        ).fillna(0.0)

    # --------------------------------------------------------
    # 날짜형 변환
    # --------------------------------------------------------

    clean_df["Date"] = pd.to_datetime(
        clean_df["Date"],
        errors="coerce"
    )

    clean_df = clean_df.dropna(
        subset=["Date"]
    ).copy()

    # --------------------------------------------------------
    # 문자열 컬럼 정리
    # --------------------------------------------------------

    string_columns = [
        "Ticker",
        "Mistake_Tags",
        "Emotion",
        "Discipline",
        "Memo"
    ]

    for col in string_columns:

        clean_df[col] = (
            clean_df[col]
            .fillna("")
            .astype(str)
        )

        clean_df.loc[
            clean_df[col].str.lower() == "nan",
            col
        ] = ""

    # --------------------------------------------------------
    # 기존 데이터 중 Buy_Amount가 없는 경우 복원
    # --------------------------------------------------------

    recovery_mask = (
        (clean_df["Buy_Amount"] == 0)
        &
        (clean_df["ROI_Percent"] != 0)
    )

    if recovery_mask.any():

        calculated_buy = (
            clean_df.loc[
                recovery_mask,
                "P_L_Amount"
            ]
            /
            (
                clean_df.loc[
                    recovery_mask,
                    "ROI_Percent"
                ]
                / 100
            )
        ).abs()

        clean_df.loc[
            recovery_mask,
            "Buy_Amount"
        ] = calculated_buy

        clean_df.loc[
            recovery_mask,
            "Sell_Amount"
        ] = (
            clean_df.loc[
                recovery_mask,
                "Buy_Amount"
            ]
            +
            clean_df.loc[
                recovery_mask,
                "P_L_Amount"
            ]
        )

    # --------------------------------------------------------
    # Trade_ID 생성
    # --------------------------------------------------------

    for position, idx in enumerate(
        clean_df.index
    ):

        current_id = clean_df.at[
            idx,
            "Trade_ID"
        ]

        if (
            pd.isna(current_id)
            or
            str(current_id).strip() == ""
            or
            str(current_id).lower() == "nan"
        ):

            clean_df.at[
                idx,
                "Trade_ID"
            ] = create_legacy_trade_id(
                clean_df.loc[idx],
                position
            )

        else:

            clean_df.at[
                idx,
                "Trade_ID"
            ] = str(
                current_id
            )

    # --------------------------------------------------------
    # 컬럼 순서
    # --------------------------------------------------------

    for col in REQUIRED_COLUMNS:

        if col not in clean_df.columns:

            clean_df[col] = ""

    clean_df = clean_df[
        REQUIRED_COLUMNS
    ].copy()

    clean_df.reset_index(
        drop=True,
        inplace=True
    )

    return clean_df


# ============================================================
# 11. Google Sheet 저장용 변환
# ============================================================

def prepare_for_sheet(dataframe):

    sheet_df = dataframe.copy()

    if "Date" in sheet_df.columns:

        sheet_df["Date"] = pd.to_datetime(
            sheet_df["Date"],
            errors="coerce"
        ).dt.strftime(
            "%Y-%m-%d"
        )

    for col in REQUIRED_COLUMNS:

        if col not in sheet_df.columns:

            sheet_df[col] = ""

    sheet_df = sheet_df[
        REQUIRED_COLUMNS
    ]

    sheet_df = sheet_df.replace(
        {
            np.nan: "",
            np.inf: "",
            -np.inf: ""
        }
    )

    return sheet_df


# ============================================================
# 12. 데이터 로딩
# ============================================================

def load_data():

    try:

        raw_df = conn.read(
            worksheet=0,
            ttl=0
        )

        return normalize_trade_dataframe(
            raw_df
        )

    except Exception as e:

        st.error(
            f"데이터 불러오기 실패: {e}"
        )

        return pd.DataFrame(
            columns=REQUIRED_COLUMNS
        )


# ============================================================
# 13. 기존 Google Sheet에 Trade_ID 영구 저장
# ============================================================

def migrate_trade_ids():

    try:

        raw_df = conn.read(
            worksheet=0,
            ttl=0
        )

        if raw_df.empty:

            return

        needs_migration = False

        if "Trade_ID" not in raw_df.columns:

            needs_migration = True

        else:

            trade_id_series = (
                raw_df["Trade_ID"]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            if (
                (trade_id_series == "")
                |
                (trade_id_series.str.lower() == "nan")
            ).any():

                needs_migration = True

        if needs_migration:

            migrated_df = normalize_trade_dataframe(
                raw_df
            )

            sheet_df = prepare_for_sheet(
                migrated_df
            )

            conn.update(
                worksheet=0,
                data=sheet_df
            )

    except Exception:
        # 마이그레이션 실패가 앱 전체 실행을 막지 않도록 처리
        pass


# 기존 데이터 ID 보완
migrate_trade_ids()


# ============================================================
# 14. 데이터 최초 로딩
# ============================================================

df = load_data()

krx_list = get_krx_list()


# ============================================================
# 15. 사이드바 AI 캡처 분석
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
        "종목명, 매수금액, 수익률을 자동으로 읽습니다."
    )

    api_key = st.text_input(
        "Gemini API Key",
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
                "AI가 캡쳐를 분석 중입니다..."
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
당신은 한국 주식 증권사 앱 캡쳐 화면을 분석하는
트레이딩 기록 보조 AI입니다.

이미지에서 다음 3개 데이터를 추출하세요.

1. 종목명
2. 총 매수금액
3. 수익률(%)

규칙:

- 금액의 쉼표와 '원'은 제거합니다.
- 수익률의 % 기호는 제거합니다.
- 손실이면 수익률은 음수입니다.
- 화면에 수익률이 없지만 손익금액과 매수금액이 있다면
  (손익금액 / 매수금액) * 100 으로 계산합니다.
- 수익률은 소수점 둘째 자리까지 사용합니다.

반드시 JSON만 출력하세요.

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
                            "🚨 AI 응답이 없습니다."
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

                            clean_json = (
                                result_text
                            )

                        data = json.loads(
                            clean_json
                        )

                        ticker_value = str(
                            data.get(
                                "ticker",
                                ""
                            )
                        ).strip()

                        buy_value = str(
                            data.get(
                                "buy_amount",
                                0
                            )
                        )

                        buy_value = (
                            buy_value
                            .replace(",", "")
                            .replace("원", "")
                            .strip()
                        )

                        roi_value = str(
                            data.get(
                                "roi",
                                0
                            )
                        )

                        roi_value = (
                            roi_value
                            .replace(",", "")
                            .replace("%", "")
                            .strip()
                        )

                        st.session_state[
                            "ai_ticker"
                        ] = ticker_value

                        st.session_state[
                            "ai_buy_amt"
                        ] = int(
                            float(
                                buy_value
                                or 0
                            )
                        )

                        st.session_state[
                            "ai_roi"
                        ] = float(
                            roi_value
                            or 0
                        )

                        st.session_state[
                            "ai_memo"
                        ] = str(
                            data.get(
                                "memo",
                                "📸 AI 분석 자동 입력"
                            )
                        )

                        if (
                            "form_reset_trigger"
                            not in st.session_state
                        ):

                            st.session_state[
                                "form_reset_trigger"
                            ] = 0

                        st.session_state[
                            "form_reset_trigger"
                        ] += 1

                        st.success(
                            "✅ 분석 성공!"
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
                            "🚨 API 사용량 제한에 도달했습니다."
                        )

                        st.warning(
                            "잠시 후 다시 시도해주세요."
                        )

                    else:

                        st.error(
                            "🚨 이미지 분석에 실패했습니다."
                        )

                        with st.expander(
                            "🛠️ 오류 확인"
                        ):

                            st.write(
                                str(e)
                            )


# ============================================================
# 16. AI 입력값 상태
# ============================================================

if (
    "form_reset_trigger"
    not in st.session_state
):

    st.session_state[
        "form_reset_trigger"
    ] = 0


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

fc = st.session_state[
    "form_reset_trigger"
]


# ============================================================
# 17. 사이드바 신규 거래 입력
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
        "종목명",
        value=def_ticker,
        key=f"ticker_{fc}"
    ).strip()

    st.markdown("---")

    buy_amt = st.number_input(
        "총 매수 금액 (원)",
        min_value=0,
        value=max(
            0,
            def_buy_amt
        ),
        step=100000,
        key=f"buy_{fc}"
    )

    roi = st.number_input(
        "수익률 (%)",
        value=def_roi,
        format="%.2f",
        key=f"roi_{fc}"
    )

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

    if buy_amt > 0:

        st.info(
            f"""
🧮 **자동 계산**

수익/손실금: **{pn_l:+,.0f}원**

매도금액: **{sell_amt:,.0f}원**
"""
        )

    memo = st.text_input(
        "메모",
        value=def_memo,
        key=f"memo_{fc}"
    )

    save_button = st.form_submit_button(
        "💾 기록 저장",
        use_container_width=True
    )

    if save_button:

        if not ticker:

            st.error(
                "종목명을 입력해주세요."
            )

        elif buy_amt <= 0:

            st.error(
                "매수금액을 입력해주세요."
            )

        else:

            try:

                new_trade = pd.DataFrame(
                    [{
                        "Trade_ID":
                            create_new_trade_id(),

                        "Date":
                            date.strftime(
                                "%Y-%m-%d"
                            ),

                        "Ticker":
                            ticker,

                        "Buy_Amount":
                            float(buy_amt),

                        "Sell_Amount":
                            float(sell_amt),

                        "P_L_Amount":
                            float(pn_l),

                        "ROI_Percent":
                            float(roi),

                        "Mistake_Tags":
                            "",

                        "Emotion":
                            "",

                        "Discipline":
                            "",

                        "Memo":
                            memo
                    }]
                )

                live_raw = conn.read(
                    worksheet=0,
                    ttl=0
                )

                if live_raw.empty:

                    updated_df = (
                        new_trade.copy()
                    )

                else:

                    live_df = (
                        normalize_trade_dataframe(
                            live_raw
                        )
                    )

                    updated_df = pd.concat(
                        [
                            live_df,
                            new_trade
                        ],
                        ignore_index=True
                    )

                updated_df = (
                    normalize_trade_dataframe(
                        updated_df
                    )
                )

                sheet_df = prepare_for_sheet(
                    updated_df
                )

                conn.update(
                    worksheet=0,
                    data=sheet_df
                )

                st.session_state[
                    "ai_ticker"
                ] = ""

                st.session_state[
                    "ai_buy_amt"
                ] = 0

                st.session_state[
                    "ai_roi"
                ] = 0.0

                st.session_state[
                    "ai_memo"
                ] = ""

                st.session_state[
                    "form_reset_trigger"
                ] += 1

                st.success(
                    f"✅ {ticker} 저장 완료!"
                )

                st.rerun()

            except Exception as e:

                st.error(
                    "🚨 거래 저장에 실패했습니다."
                )

                st.write(
                    f"오류: {e}"
                )


# ============================================================
# 18. 종목 리스트 상태
# ============================================================

if krx_list.empty:

    st.sidebar.caption(
        "⚠️ KRX 종목 리스트 로딩 실패"
    )

else:

    st.sidebar.caption(
        f"✅ {len(krx_list):,}개 종목 연결됨"
    )


# ============================================================
# 19. 메인 화면
# ============================================================

st.title(
    "💎 Trading Master Dashboard"
)


# ============================================================
# 20. 데이터 존재
# ============================================================

if not df.empty:

    # --------------------------------------------------------
    # 색상 함수
    # --------------------------------------------------------

    def color_profit_loss(val):

        try:

            if pd.isna(val):

                return ""

            number = float(val)

            if number > 0:

                return (
                    "color: #FF4444; "
                    "font-weight: bold;"
                )

            elif number < 0:

                return (
                    "color: #0066CC; "
                    "font-weight: bold;"
                )

        except Exception:

            pass

        return ""


    # --------------------------------------------------------
    # 분석용 컬럼
    # --------------------------------------------------------

    analysis_df = df.copy()

    analysis_df["Year"] = (
        analysis_df[
            "Date"
        ].dt.year
    )

    analysis_df["YearMonth"] = (
        analysis_df[
            "Date"
        ].dt.strftime(
            "%Y-%m"
        )
    )


    # --------------------------------------------------------
    # 탭
    # --------------------------------------------------------

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
            "⚖️ 빅터",
            "🎯 R-배수",
            "🔔 손익 분포",
            "🛠️ 거래 관리"
        ]
    )


    # ========================================================
    # TAB 1
    # ========================================================

    with tab1:

        st.subheader(
            "🏆 전체 종합 성적표 (Total Legend)"
        )

        total_cnt = len(
            analysis_df
        )

        total_pl = (
            analysis_df[
                "P_L_Amount"
            ].sum()
        )

        all_wins = analysis_df[
            analysis_df[
                "ROI_Percent"
            ] > 0
        ]

        all_losses = analysis_df[
            analysis_df[
                "ROI_Percent"
            ] <= 0
        ]

        win_rate = (
            len(all_wins)
            /
            total_cnt
            *
            100
            if total_cnt > 0
            else 0
        )

        gross_profit = (
            all_wins[
                "P_L_Amount"
            ].sum()
        )

        gross_loss = abs(
            all_losses[
                "P_L_Amount"
            ].sum()
        )

        total_pf = (
            gross_profit
            /
            gross_loss
            if gross_loss > 0
            else 0
        )

        avg_profit_amt = (
            all_wins[
                "P_L_Amount"
            ].mean()
            if not all_wins.empty
            else 0
        )

        avg_loss_amt = (
            abs(
                all_losses[
                    "P_L_Amount"
                ].mean()
            )
            if not all_losses.empty
            else 0
        )

        money_rr = (
            avg_profit_amt
            /
            avg_loss_amt
            if avg_loss_amt > 0
            else 0
        )

        avg_profit_pct = (
            all_wins[
                "ROI_Percent"
            ].mean()
            if not all_wins.empty
            else 0
        )

        avg_loss_pct = (
            abs(
                all_losses[
                    "ROI_Percent"
                ].mean()
            )
            if not all_losses.empty
            else 0
        )

        period_rr = (
            avg_profit_pct
            /
            avg_loss_pct
            if avg_loss_pct > 0
            else 0
        )

        win_probability = (
            len(all_wins)
            /
            total_cnt
            if total_cnt > 0
            else 0
        )

        loss_probability = (
            1
            -
            win_probability
        )

        expectancy = (
            win_probability
            *
            avg_profit_pct
        ) - (
            loss_probability
            *
            avg_loss_pct
        )

        if money_rr > 0:

            kelly_fraction = (
                win_probability
                -
                (
                    loss_probability
                    /
                    money_rr
                )
            )

            kelly_pct = max(
                0.0,
                kelly_fraction * 100
            )

        else:

            kelly_pct = 0.0


        m1, m2, m3, m4, m5 = st.columns(
            5
        )

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
            "##### 💵 금액(Money) 성적표"
        )

        c1, c2, c3, c4 = st.columns(
            4
        )

        c1.metric(
            "평균 수익금",
            f"{avg_profit_amt:,.0f}원"
        )

        c2.metric(
            "평균 손실금",
            f"{avg_loss_amt:,.0f}원"
        )

        c3.metric(
            "⚖️ 금액 손익비",
            f"{money_rr:.2f}"
        )

        c4.metric(
            "🛒 총 매수 대금",
            f"{analysis_df['Buy_Amount'].sum():,.0f}원"
        )


        st.markdown(
            "##### 📊 기간(Technical) 성적표"
        )

        c5, c6, c7, c8 = st.columns(
            4
        )

        c5.metric(
            "평균 수익률",
            f"+{avg_profit_pct:.2f}%"
        )

        c6.metric(
            "평균 손실률",
            f"-{avg_loss_pct:.2f}%"
        )

        c7.metric(
            "⚖️ 기간 손익비",
            f"{period_rr:.2f}"
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
            analysis_df
            .groupby(
                "Date"
            )[
                "P_L_Amount"
            ]
            .sum()
            .reset_index()
            .sort_values(
                "Date"
            )
        )

        daily_df[
            "Cumulative"
        ] = (
            daily_df[
                "P_L_Amount"
            ].cumsum()
        )

        try:

            start_date = (
                daily_df[
                    "Date"
                ]
                .min()
                .strftime(
                    "%Y-%m-%d"
                )
            )

            kospi_raw = yf.download(
                "^KS11",
                start=start_date,
                progress=False,
                auto_adjust=False
            )

            if (
                kospi_raw is not None
                and
                not kospi_raw.empty
            ):

                if isinstance(
                    kospi_raw.columns,
                    pd.MultiIndex
                ):

                    kospi_close = (
                        kospi_raw[
                            "Close"
                        ]
                        .iloc[:, 0]
                    )

                else:

                    kospi_close = (
                        kospi_raw[
                            "Close"
                        ]
                    )

                kospi = (
                    kospi_close
                    .reset_index()
                )

                kospi.columns = [
                    "Date",
                    "KOSPI"
                ]

                kospi["Date"] = (
                    pd.to_datetime(
                        kospi["Date"]
                    )
                    .dt.tz_localize(
                        None
                    )
                )

                my_chart = (
                    alt.Chart(
                        daily_df
                    )
                    .mark_line(
                        color="#00AA00",
                        strokeWidth=3
                    )
                    .encode(
                        x=alt.X(
                            "Date:T",
                            title="Date"
                        ),
                        y=alt.Y(
                            "Cumulative:Q",
                            title="내 누적 손익"
                        ),
                        tooltip=[
                            alt.Tooltip(
                                "Date:T"
                            ),
                            alt.Tooltip(
                                "Cumulative:Q",
                                format=",.0f"
                            )
                        ]
                    )
                )

                kospi_chart = (
                    alt.Chart(
                        kospi
                    )
                    .mark_line(
                        color="#FF4444",
                        strokeDash=[
                            5,
                            5
                        ]
                    )
                    .encode(
                        x=alt.X(
                            "Date:T"
                        ),
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

            else:

                st.line_chart(
                    daily_df.set_index(
                        "Date"
                    )[
                        "Cumulative"
                    ]
                )

        except Exception:

            st.line_chart(
                daily_df.set_index(
                    "Date"
                )[
                    "Cumulative"
                ]
            )


        st.subheader(
            "📊 월별 손익 흐름"
        )

        monthly_chart_data = (
            analysis_df
            .groupby(
                "YearMonth"
            )[
                "P_L_Amount"
            ]
            .sum()
        )

        st.bar_chart(
            monthly_chart_data
        )


    # ========================================================
    # TAB 2
    # ========================================================

    with tab2:

        st.subheader(
            "📅 월별 상세 성적표"
        )

        monthly_stats = []

        for ym, group in analysis_df.groupby(
            "YearMonth"
        ):

            g_wins = group[
                group[
                    "ROI_Percent"
                ] > 0
            ]

            g_losses = group[
                group[
                    "ROI_Percent"
                ] <= 0
            ]

            gross_profit = (
                group[
                    group[
                        "P_L_Amount"
                    ] > 0
                ][
                    "P_L_Amount"
                ].sum()
            )

            gross_loss = abs(
                group[
                    group[
                        "P_L_Amount"
                    ] <= 0
                ][
                    "P_L_Amount"
                ].sum()
            )

            avg_profit_amount = (
                group[
                    group[
                        "P_L_Amount"
                    ] > 0
                ][
                    "P_L_Amount"
                ].mean()
                if not group[
                    group[
                        "P_L_Amount"
                    ] > 0
                ].empty
                else 0
            )

            avg_loss_amount = (
                group[
                    group[
                        "P_L_Amount"
                    ] <= 0
                ][
                    "P_L_Amount"
                ].mean()
                if not group[
                    group[
                        "P_L_Amount"
                    ] <= 0
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

            avg_gain_pct = (
                g_wins[
                    "ROI_Percent"
                ].mean()
                if not g_wins.empty
                else 0
            )

            avg_loss_pct_month = (
                abs(
                    g_losses[
                        "ROI_Percent"
                    ].mean()
                )
                if not g_losses.empty
                else 0
            )

            rr = (
                avg_gain_pct
                /
                avg_loss_pct_month
                if avg_loss_pct_month > 0
                else 0
            )

            count = len(
                group
            )

            win_prob = (
                len(g_wins)
                /
                count
                if count > 0
                else 0
            )

            loss_prob = (
                1
                -
                win_prob
            )

            exp_value = (
                win_prob
                *
                avg_gain_pct
            ) - (
                loss_prob
                *
                avg_loss_pct_month
            )

            monthly_stats.append(
                {
                    "기간":
                        str(ym),

                    "총 손익":
                        float(
                            group[
                                "P_L_Amount"
                            ].sum()
                        ),

                    "평균수익":
                        float(
                            avg_profit_amount
                        ),

                    "평균손실":
                        float(
                            avg_loss_amount
                        ),

                    "거래횟수":
                        int(
                            count
                        ),

                    "승률":
                        float(
                            win_prob * 100
                        ),

                    "손익비":
                        float(
                            rr
                        ),

                    "PF":
                        float(
                            pf
                        ),

                    "기대수익":
                        float(
                            exp_value
                        ),

                    "매수총액":
                        float(
                            group[
                                "Buy_Amount"
                            ].sum()
                        )
                }
            )

        monthly_table = pd.DataFrame(
            monthly_stats
        )

        if not monthly_table.empty:

            monthly_table = (
                monthly_table
                .sort_values(
                    "기간",
                    ascending=False
                )
            )

            format_monthly = {
                "총 손익":
                    "{:+,.0f}원",

                "평균수익":
                    "{:,.0f}원",

                "평균손실":
                    "{:,.0f}원",

                "거래횟수":
                    "{:,}회",

                "승률":
                    "{:.1f}%",

                "손익비":
                    "{:.2f}",

                "PF":
                    "{:.2f}",

                "기대수익":
                    "{:+.2f}%",

                "매수총액":
                    "{:,.0f}원"
            }

            try:

                styled_monthly = (
                    monthly_table.style
                    .map(
                        color_profit_loss,
                        subset=[
                            "총 손익",
                            "기대수익"
                        ]
                    )
                    .format(
                        format_monthly
                    )
                )

            except AttributeError:

                styled_monthly = (
                    monthly_table.style
                    .applymap(
                        color_profit_loss,
                        subset=[
                            "총 손익",
                            "기대수익"
                        ]
                    )
                    .format(
                        format_monthly
                    )
                )

            st.dataframe(
                styled_monthly,
                use_container_width=True
            )


    # ========================================================
    # TAB 3
    # ========================================================

    with tab3:

        st.subheader(
            "📆 연도별 종합 성적표"
        )

        yearly_stats = []

        for year, group in analysis_df.groupby(
            "Year"
        ):

            g_wins = group[
                group[
                    "ROI_Percent"
                ] > 0
            ]

            g_losses = group[
                group[
                    "ROI_Percent"
                ] <= 0
            ]

            gross_profit = (
                group[
                    group[
                        "P_L_Amount"
                    ] > 0
                ][
                    "P_L_Amount"
                ].sum()
            )

            gross_loss = abs(
                group[
                    group[
                        "P_L_Amount"
                    ] <= 0
                ][
                    "P_L_Amount"
                ].sum()
            )

            avg_profit_amount = (
                group[
                    group[
                        "P_L_Amount"
                    ] > 0
                ][
                    "P_L_Amount"
                ].mean()
                if not group[
                    group[
                        "P_L_Amount"
                    ] > 0
                ].empty
                else 0
            )

            avg_loss_amount = (
                group[
                    group[
                        "P_L_Amount"
                    ] <= 0
                ][
                    "P_L_Amount"
                ].mean()
                if not group[
                    group[
                        "P_L_Amount"
                    ] <= 0
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

            avg_gain_pct = (
                g_wins[
                    "ROI_Percent"
                ].mean()
                if not g_wins.empty
                else 0
            )

            avg_loss_pct_year = (
                abs(
                    g_losses[
                        "ROI_Percent"
                    ].mean()
                )
                if not g_losses.empty
                else 0
            )

            rr = (
                avg_gain_pct
                /
                avg_loss_pct_year
                if avg_loss_pct_year > 0
                else 0
            )

            count = len(
                group
            )

            win_prob = (
                len(g_wins)
                /
                count
                if count > 0
                else 0
            )

            loss_prob = (
                1
                -
                win_prob
            )

            exp_value = (
                win_prob
                *
                avg_gain_pct
            ) - (
                loss_prob
                *
                avg_loss_pct_year
            )

            yearly_stats.append(
                {
                    "연도":
                        int(year),

                    "총 손익":
                        float(
                            group[
                                "P_L_Amount"
                            ].sum()
                        ),

                    "평균수익":
                        float(
                            avg_profit_amount
                        ),

                    "평균손실":
                        float(
                            avg_loss_amount
                        ),

                    "거래횟수":
                        int(
                            count
                        ),

                    "승률":
                        float(
                            win_prob * 100
                        ),

                    "손익비":
                        float(
                            rr
                        ),

                    "PF":
                        float(
                            pf
                        ),

                    "기대수익":
                        float(
                            exp_value
                        ),

                    "매수총액":
                        float(
                            group[
                                "Buy_Amount"
                            ].sum()
                        )
                }
            )

        yearly_table = pd.DataFrame(
            yearly_stats
        )

        if not yearly_table.empty:

            yearly_table = (
                yearly_table
                .sort_values(
                    "연도",
                    ascending=False
                )
            )

            format_yearly = {
                "총 손익":
                    "{:+,.0f}원",

                "평균수익":
                    "{:,.0f}원",

                "평균손실":
                    "{:,.0f}원",

                "거래횟수":
                    "{:,}회",

                "승률":
                    "{:.1f}%",

                "손익비":
                    "{:.2f}",

                "PF":
                    "{:.2f}",

                "기대수익":
                    "{:+.2f}%",

                "매수총액":
                    "{:,.0f}원"
            }

            try:

                styled_yearly = (
                    yearly_table.style
                    .map(
                        color_profit_loss,
                        subset=[
                            "총 손익",
                            "기대수익"
                        ]
                    )
                    .format(
                        format_yearly
                    )
                )

            except AttributeError:

                styled_yearly = (
                    yearly_table.style
                    .applymap(
                        color_profit_loss,
                        subset=[
                            "총 손익",
                            "기대수익"
                        ]
                    )
                    .format(
                        format_yearly
                    )
                )

            st.dataframe(
                styled_yearly,
                use_container_width=True
            )


    # ========================================================
    # TAB 4
    # ========================================================

    with tab4:

        st.subheader(
            "📋 전체 거래 기록"
        )

        original_table = (
            analysis_df
            .sort_values(
                "Date",
                ascending=False
            )
            .copy()
        )

        display_columns = [
            "Date",
            "Ticker",
            "Buy_Amount",
            "Sell_Amount",
            "P_L_Amount",
            "ROI_Percent",
            "Memo"
        ]

        original_table = (
            original_table[
                display_columns
            ]
        )

        try:

            styled_original = (
                original_table.style
                .map(
                    color_profit_loss,
                    subset=[
                        "ROI_Percent",
                        "P_L_Amount"
                    ]
                )
                .format(
                    {
                        "Buy_Amount":
                            "{:,.0f}원",

                        "Sell_Amount":
                            "{:,.0f}원",

                        "P_L_Amount":
                            "{:+,.0f}원",

                        "ROI_Percent":
                            "{:+.2f}%"
                    }
                )
            )

        except AttributeError:

            styled_original = (
                original_table.style
                .applymap(
                    color_profit_loss,
                    subset=[
                        "ROI_Percent",
                        "P_L_Amount"
                    ]
                )
                .format(
                    {
                        "Buy_Amount":
                            "{:,.0f}원",

                        "Sell_Amount":
                            "{:,.0f}원",

                        "P_L_Amount":
                            "{:+,.0f}원",

                        "ROI_Percent":
                            "{:+.2f}%"
                    }
                )
            )

        st.dataframe(
            styled_original,
            use_container_width=True
        )


    # ========================================================
    # TAB 5
    # ========================================================

    with tab5:

        st.subheader(
            "⚖️ Victor Sperandeo Reward-to-Risk Analysis"
        )

        st.markdown(
            "**목표 기준: 평균 수익 / 평균 손실 = 3 : 1**"
        )

        vic_period = st.radio(
            "📅 분석 기간",
            [
                "전체",
                "최근 1개월",
                "최근 3개월",
                "최근 6개월",
                "최근 1년"
            ],
            horizontal=True,
            key="vic_period"
        )

        vic_df = (
            analysis_df.copy()
        )

        today = pd.Timestamp.today().normalize()

        if vic_period == "최근 1개월":

            vic_df = vic_df[
                vic_df["Date"]
                >=
                today
                -
                timedelta(days=30)
            ]

        elif vic_period == "최근 3개월":

            vic_df = vic_df[
                vic_df["Date"]
                >=
                today
                -
                timedelta(days=90)
            ]

        elif vic_period == "최근 6개월":

            vic_df = vic_df[
                vic_df["Date"]
                >=
                today
                -
                timedelta(days=180)
            ]

        elif vic_period == "최근 1년":

            vic_df = vic_df[
                vic_df["Date"]
                >=
                today
                -
                timedelta(days=365)
            ]


        if not vic_df.empty:

            v_wins = vic_df[
                vic_df[
                    "ROI_Percent"
                ] > 0
            ]

            v_losses = vic_df[
                vic_df[
                    "ROI_Percent"
                ] <= 0
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

            v_avg_loss = (
                abs(
                    v_losses[
                        "ROI_Percent"
                    ].mean()
                )
                if not v_losses.empty
                else 0
            )

            v_rr = (
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
                1
                -
                v_win_prob
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

            v1, v2, v3 = st.columns(
                3
            )

            v1.metric(
                "기간 손익비",
                f"{v_rr:.2f} : 1"
            )

            v2.metric(
                "기간 기댓값",
                f"{v_expectancy:.2f}%"
            )

            v3.metric(
                "목표 기준",
                "3.0 : 1"
            )

            target_roi = (
                v_avg_loss
                *
                3
                if v_avg_loss > 0
                else 10
            )

            vic_chart_df = (
                vic_df.copy()
            )

            conditions = [
                vic_chart_df[
                    "ROI_Percent"
                ] >= target_roi,

                vic_chart_df[
                    "ROI_Percent"
                ] > 0
            ]

            chart_colors = [
                "#00CC00",
                "#F1C40F"
            ]

            vic_chart_df[
                "Color_Hex"
            ] = np.select(
                conditions,
                chart_colors,
                default="#FF4B4B"
            )

            scatter_chart = (
                alt.Chart(
                    vic_chart_df
                )
                .mark_circle(
                    size=100
                )
                .encode(
                    x=alt.X(
                        "Date:T",
                        title="거래 일자"
                    ),
                    y=alt.Y(
                        "ROI_Percent:Q",
                        title="수익률 (%)"
                    ),
                    color=alt.Color(
                        "Color_Hex:N",
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

            rule_data = pd.DataFrame(
                {
                    "Target": [
                        target_roi
                    ]
                }
            )

            rule_chart = (
                alt.Chart(
                    rule_data
                )
                .mark_rule(
                    color="blue",
                    strokeDash=[
                        3,
                        3
                    ]
                )
                .encode(
                    y="Target:Q"
                )
            )

            st.altair_chart(
                scatter_chart
                +
                rule_chart,
                use_container_width=True
            )

        else:

            st.info(
                "선택한 기간에 거래 기록이 없습니다."
            )


    # ========================================================
    # TAB 6
    # ========================================================

    with tab6:

        st.subheader(
            "🎯 R-배수 분석"
        )

        st.caption(
            "1R = 선택 기간의 평균 손실금"
        )

        r_period = st.radio(
            "📅 분석 기간",
            [
                "전체",
                "최근 1개월",
                "최근 3개월",
                "최근 6개월",
                "최근 1년"
            ],
            horizontal=True,
            key="r_period"
        )

        r_df = (
            analysis_df.copy()
        )

        today = pd.Timestamp.today().normalize()

        if r_period == "최근 1개월":

            r_df = r_df[
                r_df["Date"]
                >=
                today
                -
                timedelta(days=30)
            ]

        elif r_period == "최근 3개월":

            r_df = r_df[
                r_df["Date"]
                >=
                today
                -
                timedelta(days=90)
            ]

        elif r_period == "최근 6개월":

            r_df = r_df[
                r_df["Date"]
                >=
                today
                -
                timedelta(days=180)
            ]

        elif r_period == "최근 1년":

            r_df = r_df[
                r_df["Date"]
                >=
                today
                -
                timedelta(days=365)
            ]


        if not r_df.empty:

            r_losses = r_df[
                r_df[
                    "P_L_Amount"
                ] < 0
            ]

            if not r_losses.empty:

                one_r = abs(
                    r_losses[
                        "P_L_Amount"
                    ].mean()
                )

            else:

                all_loss_data = (
                    analysis_df[
                        analysis_df[
                            "P_L_Amount"
                        ] < 0
                    ]
                )

                one_r = (
                    abs(
                        all_loss_data[
                            "P_L_Amount"
                        ].mean()
                    )
                    if not all_loss_data.empty
                    else 1
                )

            if (
                pd.isna(one_r)
                or
                one_r <= 0
            ):

                one_r = 1

            r_df[
                "R_Value"
            ] = (
                r_df[
                    "P_L_Amount"
                ]
                /
                one_r
            )

            r1, r2, r3 = st.columns(
                3
            )

            r1.metric(
                "나의 1R",
                f"{one_r:,.0f}원"
            )

            r2.metric(
                "평균 R-배수",
                f"{r_df['R_Value'].mean():.2f}R"
            )

            r3.metric(
                "최고 R-배수",
                f"{r_df['R_Value'].max():.2f}R"
            )

            r_chart_df = (
                r_df
                .sort_values(
                    "Date"
                )
                .copy()
            )

            r_chart_df[
                "Cumulative_R"
            ] = (
                r_chart_df[
                    "R_Value"
                ].cumsum()
            )

            r_chart_df[
                "Trade_Num"
            ] = range(
                1,
                len(
                    r_chart_df
                )
                +
                1
            )

            r_chart = (
                alt.Chart(
                    r_chart_df
                )
                .mark_line(
                    color="blue"
                )
                .encode(
                    x=alt.X(
                        "Trade_Num:Q",
                        title="거래 횟수"
                    ),
                    y=alt.Y(
                        "Cumulative_R:Q",
                        title="누적 R"
                    ),
                    tooltip=[
                        "Date",
                        "Ticker",
                        "R_Value",
                        "Cumulative_R"
                    ]
                )
            )

            st.altair_chart(
                r_chart,
                use_container_width=True
            )

        else:

            st.info(
                "선택한 기간에 거래 기록이 없습니다."
            )


    # ========================================================
    # TAB 7
    # ========================================================

    with tab7:

        st.subheader(
            "🔔 손익 분포"
        )

        st.markdown(
            "**손실은 짧게, 수익은 길게.**"
        )

        distribution_df = (
            analysis_df.copy()
        )

        histogram = (
            alt.Chart(
                distribution_df
            )
            .mark_bar()
            .encode(
                x=alt.X(
                    "ROI_Percent:Q",
                    bin=alt.Bin(
                        step=2.5
                    ),
                    title="수익률 구간 (%)"
                ),
                y=alt.Y(
                    "count():Q",
                    title="거래 횟수"
                ),
                color=alt.condition(
                    alt.datum.ROI_Percent > 0,
                    alt.value(
                        "#00AA00"
                    ),
                    alt.value(
                        "#FF4444"
                    )
                ),
                tooltip=[
                    alt.Tooltip(
                        "count():Q",
                        title="거래 횟수"
                    )
                ]
            )
            .properties(
                height=400
            )
        )

        zero_rule = (
            alt.Chart(
                pd.DataFrame(
                    {
                        "Zero": [
                            0
                        ]
                    }
                )
            )
            .mark_rule(
                color="black",
                strokeDash=[
                    2,
                    2
                ]
            )
            .encode(
                x="Zero:Q"
            )
        )

        st.altair_chart(
            histogram
            +
            zero_rule,
            use_container_width=True
        )

        skewness = (
            distribution_df[
                "ROI_Percent"
            ].skew()
        )

        if pd.isna(
            skewness
        ):

            skewness = 0

        st.info(
            f"📊 Skewness: {skewness:.2f}"
        )

        if skewness > 0.5:

            st.success(
                "✅ 수익 쪽 꼬리가 더 긴 Positive Skew입니다."
            )

        elif skewness < -0.5:

            st.error(
                "🚨 손실 쪽 꼬리가 더 긴 Negative Skew입니다."
            )

        else:

            st.warning(
                "⚠️ 수익과 손실 분포가 비교적 대칭적입니다."
            )


    # ========================================================
    # TAB 8
    # 거래 상세 → 수정 → 삭제
    # ========================================================

    with tab8:

        st.subheader(
            "🛠️ 거래 관리"
        )

        st.caption(
            "거래를 선택해 상세 내용을 확인하고 "
            "수정하거나 삭제할 수 있습니다."
        )


        # ----------------------------------------------------
        # 거래 목록
        # ----------------------------------------------------

        manage_df = (
            analysis_df
            .sort_values(
                [
                    "Date",
                    "Trade_ID"
                ],
                ascending=[
                    False,
                    False
                ]
            )
            .copy()
        )

        manage_df[
            "Display_Name"
        ] = (
            manage_df[
                "Date"
            ].dt.strftime(
                "%Y-%m-%d"
            )
            +
            " | "
            +
            manage_df[
                "Ticker"
            ].astype(str)
            +
            " | "
            +
            manage_df[
                "ROI_Percent"
            ].map(
                lambda x:
                    f"{x:+.2f}%"
            )
            +
            " | "
            +
            manage_df[
                "P_L_Amount"
            ].map(
                lambda x:
                    f"{x:+,.0f}원"
            )
        )


        display_map = dict(
            zip(
                manage_df[
                    "Trade_ID"
                ].astype(str),

                manage_df[
                    "Display_Name"
                ]
            )
        )


        selected_trade_id = st.selectbox(
            "📋 수정/삭제할 거래 선택",
            options=list(
                display_map.keys()
            ),
            format_func=lambda x:
                display_map.get(
                    x,
                    x
                ),
            key="selected_trade_id"
        )


        selected_rows = (
            manage_df[
                manage_df[
                    "Trade_ID"
                ].astype(str)
                ==
                str(
                    selected_trade_id
                )
            ]
        )


        if not selected_rows.empty:

            selected = (
                selected_rows
                .iloc[0]
            )


            # ------------------------------------------------
            # 상세보기
            # ------------------------------------------------

            st.divider()

            st.markdown(
                "### 🔎 거래 상세보기"
            )

            d1, d2, d3, d4 = st.columns(
                4
            )

            d1.metric(
                "종목",
                str(
                    selected[
                        "Ticker"
                    ]
                )
            )

            d2.metric(
                "거래일",
                selected[
                    "Date"
                ].strftime(
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


            d5, d6 = st.columns(
                2
            )

            d5.metric(
                "매수금액",
                f"{selected['Buy_Amount']:,.0f}원"
            )

            d6.metric(
                "매도금액",
                f"{selected['Sell_Amount']:,.0f}원"
            )


            if (
                str(
                    selected[
                        "Memo"
                    ]
                ).strip()
            ):

                st.info(
                    f"📝 {selected['Memo']}"
                )


            # ------------------------------------------------
            # 수정 폼
            # ------------------------------------------------

            st.divider()

            st.markdown(
                "### ✏️ 거래 수정"
            )

            with st.form(
                f"edit_form_{selected_trade_id}"
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

                edit_col1, edit_col2 = st.columns(
                    2
                )

                with edit_col1:

                    edit_buy = st.number_input(
                        "매수금액 (원)",
                        min_value=0,
                        value=max(
                            0,
                            int(
                                round(
                                    selected[
                                        "Buy_Amount"
                                    ]
                                )
                            )
                        ),
                        step=100000
                    )

                with edit_col2:

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
                    (
                        edit_roi
                        /
                        100
                    )
                )

                edit_sell = (
                    edit_buy
                    +
                    edit_pl
                )


                st.info(
                    f"""
🧮 **수정 후 계산**

손익: **{edit_pl:+,.0f}원**

매도금액: **{edit_sell:,.0f}원**
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


                update_trade = st.form_submit_button(
                    "💾 수정 내용 저장",
                    use_container_width=True
                )


                if update_trade:

                    if not edit_ticker.strip():

                        st.error(
                            "종목명을 입력해주세요."
                        )

                    elif edit_buy <= 0:

                        st.error(
                            "매수금액을 입력해주세요."
                        )

                    else:

                        try:

                            live_raw = conn.read(
                                worksheet=0,
                                ttl=0
                            )

                            live_df = (
                                normalize_trade_dataframe(
                                    live_raw
                                )
                            )

                            target_mask = (
                                live_df[
                                    "Trade_ID"
                                ].astype(str)
                                ==
                                str(
                                    selected_trade_id
                                )
                            )

                            if not target_mask.any():

                                st.error(
                                    "🚨 수정하려는 거래를 찾을 수 없습니다."
                                )

                            else:

                                target_index = (
                                    live_df[
                                        target_mask
                                    ].index[0]
                                )

                                live_df.at[
                                    target_index,
                                    "Date"
                                ] = pd.Timestamp(
                                    edit_date
                                )

                                live_df.at[
                                    target_index,
                                    "Ticker"
                                ] = (
                                    edit_ticker
                                    .strip()
                                )

                                live_df.at[
                                    target_index,
                                    "Buy_Amount"
                                ] = float(
                                    edit_buy
                                )

                                live_df.at[
                                    target_index,
                                    "Sell_Amount"
                                ] = float(
                                    edit_sell
                                )

                                live_df.at[
                                    target_index,
                                    "P_L_Amount"
                                ] = float(
                                    edit_pl
                                )

                                live_df.at[
                                    target_index,
                                    "ROI_Percent"
                                ] = float(
                                    edit_roi
                                )

                                live_df.at[
                                    target_index,
                                    "Memo"
                                ] = (
                                    edit_memo
                                )

                                sheet_df = (
                                    prepare_for_sheet(
                                        live_df
                                    )
                                )

                                conn.update(
                                    worksheet=0,
                                    data=sheet_df
                                )

                                st.success(
                                    "✅ 거래 수정 완료!"
                                )

                                st.rerun()

                        except Exception as e:

                            st.error(
                                f"🚨 거래 수정 실패: {e}"
                            )


            # ------------------------------------------------
            # 삭제
            # ------------------------------------------------

            st.divider()

            st.markdown(
                "### 🗑️ 거래 삭제"
            )

            st.warning(
                f"""
삭제 대상

**{selected['Ticker']}**

{selected['Date'].strftime('%Y-%m-%d')}

수익률: **{selected['ROI_Percent']:+.2f}%**

손익: **{selected['P_L_Amount']:+,.0f}원**

삭제하면 Google Sheets에서도 제거됩니다.
"""
            )


            delete_confirm = st.checkbox(
                "이 거래를 정말 삭제하겠습니다.",
                key=f"delete_confirm_{selected_trade_id}"
            )


            delete_button = st.button(
                "🗑️ 거래 영구 삭제",
                disabled=not delete_confirm,
                use_container_width=True,
                key=f"delete_button_{selected_trade_id}"
            )


            if delete_button:

                try:

                    live_raw = conn.read(
                        worksheet=0,
                        ttl=0
                    )

                    live_df = (
                        normalize_trade_dataframe(
                            live_raw
                        )
                    )

                    before_count = len(
                        live_df
                    )

                    live_df = (
                        live_df[
                            live_df[
                                "Trade_ID"
                            ].astype(str)
                            !=
                            str(
                                selected_trade_id
                            )
                        ]
                        .copy()
                    )

                    after_count = len(
                        live_df
                    )

                    if (
                        before_count
                        ==
                        after_count
                    ):

                        st.error(
                            "🚨 삭제할 거래를 찾을 수 없습니다."
                        )

                    else:

                        sheet_df = (
                            prepare_for_sheet(
                                live_df
                            )
                        )

                        conn.update(
                            worksheet=0,
                            data=sheet_df
                        )

                        st.success(
                            "🗑️ 거래가 삭제되었습니다."
                        )

                        st.rerun()

                except Exception as e:

                    st.error(
                        f"🚨 거래 삭제 실패: {e}"
                    )


# ============================================================
# 21. 데이터 없음
# ============================================================

else:

    st.info(
        "👈 사이드바에서 매매 기록을 입력하면 "
        "대시보드가 활성화됩니다."
    )
