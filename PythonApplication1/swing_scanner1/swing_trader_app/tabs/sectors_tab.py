"""Sectors Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_sectors(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("🗺️ Sector Heatmap")

    if market_sel == "🇺🇸 US":
        st.caption("US Sector ETFs · Refreshes every 15 min")
        sector_df = get_sector_performance()
    elif market_sel == "🇸🇬 SGX":
        st.caption("SGX sector groups (avg return) · Prices in S$ · Refreshes every 15 min")
        sector_df = get_sg_sector_performance()
        st.info("ℹ️ SGX has no liquid sector ETFs — sectors are computed as the average return of constituent stocks.")
    else:
        st.caption("NSE Sector Indices · Prices in ₹ · Refreshes every 15 min")
        sector_df = get_india_sector_performance()
        # Show Nifty 50 banner
        nifty = sector_df[sector_df["ETF"] == "^NSEI"]
        if not nifty.empty:
            n50p = nifty.iloc[0]["Today %"]
            n50v = nifty.iloc[0]["Price"]
            cc1, cc2 = st.columns(2)
            cc1.metric("🇮🇳 Nifty 50", f"₹{n50v:,.0f}", f"{n50p:+.2f}%")
            cc2.metric("Session", "NSE 09:15–15:30 IST")
        sector_df = sector_df[sector_df["ETF"] != "^NSEI"]

    if sector_df.empty or "Today %" not in sector_df.columns:
        st.warning(
            "Could not fetch sector data.\n\n"
            "- Markets may be closed (weekend/holiday)\n"
            "- Try: `pip install --upgrade yfinance`"
        )
    else:
        def tile_color(pct):
            if   pct >  2.0: return "#1a7a3a","#ffffff"
            elif pct >  0.5: return "#27ae60","#ffffff"
            elif pct >  0.1: return "#a9dfbf","#145a32"
            elif pct < -2.0: return "#922b21","#ffffff"
            elif pct < -0.5: return "#e74c3c","#ffffff"
            elif pct < -0.1: return "#f5b7b1","#7b241c"
            else:            return "#e8e8e8","#555555"

        p_sym = "₹" if market_sel == "🇮🇳 India" else ("HK$" if market_sel == "🇭🇰 HK" else ("S$" if market_sel == "🇸🇬 SGX" else "$"))
        html = "<div style='display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:16px'>"
        for _, row in sector_df.iterrows():
            bg, fg = tile_color(row["Today %"])
            arrow  = "▲" if row["Today %"] > 0 else ("▼" if row["Today %"] < 0 else "—")
            fived  = row.get("5d %", 0.0)
            html += (
                f"<div style='background:{bg};color:{fg};border-radius:8px;padding:10px 12px'>"
                f"<div style='font-size:10px;font-weight:700;opacity:.8'>{row['ETF']}</div>"
                f"<div style='font-size:13px;font-weight:700;margin:2px 0'>{row['Sector']}</div>"
                f"<div style='font-size:22px;font-weight:800'>{arrow} {row['Today %']:+.2f}%</div>"
                f"<div style='font-size:11px;opacity:.85'>5d: {fived:+.2f}%  ·  {p_sym}{row['Price']:,.0f}</div>"
                f"</div>"
            )
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

        green_list = sector_df[sector_df["Today %"] >  0.1]["Sector"].tolist()
        red_list   = sector_df[sector_df["Today %"] < -0.1]["Sector"].tolist()
        flat_list  = sector_df[
            (sector_df["Today %"] >= -0.1) & (sector_df["Today %"] <= 0.1)
        ]["Sector"].tolist()

        cg, cr = st.columns(2)
        with cg:
            body = " · ".join(f"**{s}** {sector_df.loc[sector_df['Sector']==s,'Today %'].values[0]:+.2f}%" for s in green_list)
            st.success(f"🟢 **{len(green_list)} Green**\n\n{body}" if body else "🟢 No green sectors")
        with cr:
            body = " · ".join(f"**{s}** {sector_df.loc[sector_df['Sector']==s,'Today %'].values[0]:+.2f}%" for s in red_list)
            st.error(f"🔴 **{len(red_list)} Red**\n\n{body}" if body else "🔴 No red sectors")
        if flat_list:
            st.info("⚪ **Flat:** " + " · ".join(flat_list))

