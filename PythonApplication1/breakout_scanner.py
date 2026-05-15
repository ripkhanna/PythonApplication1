import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from openai import OpenAI


SGT = ZoneInfo("Asia/Singapore")

SYSTEM_PROMPT = """
You are a professional stock market analyst specializing in technical analysis,
volume breakouts, 52-week highs, and market movers.

Use live web search to find 10 US-listed stocks breaking out today with high volume.

Search for:
1. Stocks making 52-week highs or breaking key resistance
2. Stocks with unusually high volume, preferably 1.5x to 2x+ average volume
3. Premarket or intraday movers with volume surges
4. News catalysts driving the move
5. Avoid very illiquid penny stocks where possible
6. Prefer stocks above $2 and volume above 1 million shares

Return ONLY valid JSON.
No markdown.
No explanation.
No backticks.

Exact JSON format:
{
  "scan_time": "ISO timestamp",
  "market_summary": "Brief 1-sentence market context",
  "stocks": [
    {
      "ticker": "AAPL",
      "company": "Apple Inc.",
      "price": "189.45",
      "change_pct": "+3.2",
      "volume": "85.4M",
      "avg_volume": "52.1M",
      "volume_ratio": "1.64x",
      "breakout_type": "52-Week High",
      "catalyst": "Brief reason for breakout",
      "strength": "strong",
      "risk_note": "Brief risk note"
    }
  ]
}

Rules:
- Return exactly 10 stocks.
- strength must be one of: explosive, strong, moderate.
- breakout_type must be one of:
  52-Week High, Resistance Break, Gap Up, Earnings Surge, Volume Surge, Pattern Break.
- change_pct must include + or - sign.
- If exact avg volume is not found, estimate from credible public sources and say "approx" inside avg_volume.
- Data must be current from live web search.
"""


def get_client():
    # setx OPENAI_API_KEY "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"
    # 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
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("Missing OPENAI_API_KEY. Set it in Windows environment variables.")
        st.stop()
    return OpenAI(api_key=api_key)


def extract_json(text: str):
    text = text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response.")

    return json.loads(text[start:end + 1])


def run_ai_scan():
    client = get_client()

    user_prompt = f"""
Find exactly 10 US stocks breaking out with high volume right now.

Current date/time in Singapore:
{datetime.now(SGT).strftime('%Y-%m-%d %H:%M:%S SGT')}

Focus on:
- high volume breakouts
- 52-week highs
- market movers
- resistance breaks
- gap ups
- earnings/news catalyst moves

Return only JSON.
"""

    response = client.responses.create(
        model="gpt-5.5",
        tools=[
            {
                "type": "web_search"
            }
        ],
        input=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
    )

    raw_text = response.output_text
    return extract_json(raw_text), raw_text


def strength_badge(value):
    value = str(value).lower()

    if value == "explosive":
        return "🔥 EXPLOSIVE"
    if value == "strong":
        return "⚡ STRONG"
    return "📈 MODERATE"


def main():
    st.set_page_config(
        page_title="AI Live Breakout Scanner",
        layout="wide"
    )

    st.title("⚡ AI Live Breakout Scanner")
    st.caption(
        "Claude-style AI web-search scanner. No yfinance, no IBKR, no Polygon."
    )

    st.warning(
        "This uses AI web search, not an exchange-grade real-time data feed. "
        "Verify price, volume, and spread before trading."
    )

    with st.sidebar:
        st.header("Scanner Settings")

        st.write("Data mode:")
        st.success("AI web-search live data")

        min_strength = st.selectbox(
            "Show strength",
            ["all", "explosive", "strong", "moderate"],
            index=0
        )

        run_btn = st.button("Run Live AI Scan", type="primary")

    if "scan_result" not in st.session_state:
        st.session_state.scan_result = None

    if run_btn or st.session_state.scan_result is None:
        with st.spinner("Searching live market data and finding breakout stocks..."):
            try:
                parsed, raw = run_ai_scan()
                st.session_state.scan_result = parsed
                st.session_state.raw_response = raw
            except Exception as e:
                st.error(f"Scan failed: {e}")
                st.stop()

    result = st.session_state.scan_result

    market_summary = result.get("market_summary", "")
    scan_time = result.get("scan_time", "")

    col1, col2 = st.columns([3, 1])

    with col1:
        st.info(market_summary)

    with col2:
        st.metric(
            "Stocks Found",
            len(result.get("stocks", []))
        )

    stocks = result.get("stocks", [])

    if min_strength != "all":
        stocks = [
            s for s in stocks
            if str(s.get("strength", "")).lower() == min_strength
        ]

    df = pd.DataFrame(stocks)

    if not df.empty:
        df["signal"] = df["strength"].apply(strength_badge)

        preferred_cols = [
            "ticker",
            "company",
            "price",
            "change_pct",
            "volume",
            "avg_volume",
            "volume_ratio",
            "breakout_type",
            "signal",
            "catalyst",
            "risk_note",
        ]

        existing_cols = [c for c in preferred_cols if c in df.columns]

        st.subheader("🔥 10 High-Volume Breakout Stocks")
        st.dataframe(
            df[existing_cols],
            use_container_width=True,
            height=520
        )

        st.subheader("Card View")

        for s in stocks:
            strength = str(s.get("strength", "moderate")).lower()

            if strength == "explosive":
                border_color = "#ff4b4b"
            elif strength == "strong":
                border_color = "#ffa500"
            else:
                border_color = "#2ecc71"

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1, 2, 1, 1])

                with c1:
                    st.markdown(f"### {s.get('ticker', '')}")
                    st.write(strength_badge(strength))

                with c2:
                    st.write(f"**{s.get('company', '')}**")
                    st.write(s.get("catalyst", ""))

                with c3:
                    st.metric(
                        "Price",
                        s.get("price", "N/A"),
                        s.get("change_pct", "")
                    )

                with c4:
                    st.write(f"**Volume:** {s.get('volume', 'N/A')}")
                    st.write(f"**Avg:** {s.get('avg_volume', 'N/A')}")
                    st.write(f"**Ratio:** {s.get('volume_ratio', 'N/A')}")

                st.write(f"**Breakout:** {s.get('breakout_type', '')}")
                st.caption(f"Risk: {s.get('risk_note', 'Verify before trading.')}")

    else:
        st.info("No stocks returned for this filter.")

    st.caption(
        f"Scan time from AI: {scan_time} | Displayed: "
        f"{datetime.now(SGT).strftime('%Y-%m-%d %H:%M:%S SGT')}"
    )

    with st.expander("Raw AI JSON"):
        st.json(result)


if __name__ == "__main__":
    main()
