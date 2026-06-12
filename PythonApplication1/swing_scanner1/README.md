# Swing Scanner v15.0 — Patched Build

## What Changed in v14.1 (from v14.05)

### Core Scanner Fixes (`analysis_scan_core.py`)

**Bug #1 — RR Gate Fixed** (biggest impact)
The `risk_reward_ok` gate now uses a dynamic target derived from
`upside_to_resistance` rather than a fixed 6%/8%. Stocks with confirmed
runway to resistance (≥8%) pass with RR ≥ 1.3. Extreme fake RR values
(1:60, 1:80) are capped at 1:5.0 by raising the stop floor from 0.1% to 0.5%.

**Bug #2 — SGX Market-Specific Thresholds**
Added `is_sgx` flag (`.SI` ticker suffix detection). SGX adjustments:
- ATR% penalty threshold lowered: 2.8% → 1.5% (SGX blue chips have lower ATR)
- Volume ratio floor: 1.0 → 0.6 (SGX has lower turnover)
- NDS gate: 8 → 4 for SGX stocks
- QS gate: 9 → 7 for SGX stocks
- Stop floor: 6% → 3% for SGX

**Bug #3 — Discovery Buy Tier**
New `discovery_buy` tier for stocks with Rise Prob ≥ 82% + QS ≥ 8 + NDS ≥ 5
that narrowly miss the full tradeable gate. Shows as `🔍 DISCOVERY BUY` with
`🔍DISCOVERY-BUY` signal tag replacing the old `⚠️PROB-NO-GATE` warning.

**Bug #4 — Near-Miss Buy Tier**
New `near_miss_buy` tier for pullback/continuation setups with QS ≥ 7 +
NDS ≥ 5 + valid RR. Shows as `⚡ NEAR-MISS BUY`. Both new tiers are included
in `Tradeable Buy = YES` with appropriate position-size guidance.

**Bug #5 — Setup-Type Aware NDS Gate**
NDS gate is now setup-type aware:
- Breakout setups: NDS ≥ 8 (unchanged)
- Pullback / continuation: NDS ≥ 6
- SGX any setup: NDS ≥ 4

**Bug #6 — Pullback Volume Confirmation**
Added `pullback_vol_ok = vol_declining AND vr < 1.0`. Pullback setups on
declining volume now receive +2 quality_score and +1 next_day_score bonus
(instead of being penalised for "not having volume confirmation").

**Bug #7 — Support-Aware Stop Calculation**
Pullback setups at MA60 now use MA60×0.993 as the stop; pullbacks at MA20
use MA20×0.993. This gives tighter stops → better RR → more passes.

**Bug #8 — Monday Warning Scoped to Actionable Only**
`⚠️MON` tag now only appends to `✅ BUY`, `🔍 DISCOVERY BUY`, and
`⚡ NEAR-MISS BUY` entries. WATCH/SKIP rows no longer pollute signal lists.

### Long Tab UI (`scan_results_tabs.py`)

- **Top-5 Best Setups panel** at the top of the Long tab (all modes)
  ranked by Quality Score + Next-Day Score + RR.
- **Discovery Buy section** with half-size guidance.
- **Near-Miss Buy expander** with 30%-size guidance.
- **"Blocked By" column** on Watch rows shows the single gate that prevents
  the stock from becoming a buy (e.g. "RR too low (1.7)", "NDS low (5)").
- **Developing watch split**: stocks with QS ≥ 8 shown separately
  from noise-level developing stocks.

## Expected Impact
- US Long tab: ~2 → ~25–35 Tradeable Buys per scan
- SGX Long tab: ~0 → ~5–10 Tradeable Buys per scan

## Run

```bash
pip install -r requirements.txt
streamlit run main.py
```

## Structure

- `main.py` — Streamlit launcher
- `swing_trader_app/app_runtime.py` — UI orchestration and sidebar
- `swing_trader_app/tabs/` — tab renderers (scan_results_tabs.py patched)
- `swing_trader_app/core_runtime/` — scanner engine (analysis_scan_core.py patched)

## v15.0 additions
- Pro 70 / 2.5R strategy mode: a fail-closed, professional-style live filter
  requiring at least 7 of 8 confirmation pillars, including trend,
  institutional participation, clean risk, and both estimated R:R >= 2.5 and
  upside room >= 7%. It also requires strong probability, quality,
  next-day, and multi-category confirmation. It is separate from Strategy
  Finder and should be paper-tested before live use; no future win rate is
  guaranteed.
- SGX strategy filtering fix: Pro 70 / 2.5R, A+ Precision, and Strict now use
  Singapore-aware price and volume/operator gates for `.SI` tickers. This
  prevents SGX scans from going blank just because Singapore stocks often trade
  below the US $5 price gate and with lower volume ratios.
- Pro 70 / 2.5R now has a near-miss watch layer. If no exact Pro 70 buy passes,
  the live strategy can show closest candidates as `WATCH - PRO 70 NEAR MISS`
  with `NEAR MISS - WAIT`, instead of leaving the Long tab blank. These rows are
  not buy signals.
- A+ Precision strategy mode: a live scanner mode for high-selectivity setups.
  It requires clean entry, no trap/chase risk, RR/runway, ATR sanity,
  multi-signal confluence, and volume/operator confirmation. It fails closed:
  if nothing passes, it shows no trade instead of falling back to weak
  Discovery rows.
- Strict and PSM Strategy gates were tightened. They now use the same
  precision-quality ideas and no longer promote weak "best available" rows
  when high-quality setups are absent.
- Strategy Finder tab: historical strategy-template search in Advanced.
  It replays candles with the existing signal engine, compares Balanced,
  Strict, High Conviction, Support Entry, High Volume, Operator Accumulation,
  PSM Proxy and Early Breakout style templates, then ranks by target-before-stop
  win rate, expectancy, PI, drawdown behavior and sample count. The default
  qualification gate is 70% win rate; broad templates below that are marked
  "Below 70%" and the finder generates stricter HP70 variants before showing
  any setup as qualified.
- Strategy Finder now also includes an Improved Exit Profiles section. It tests
  target/stop/horizon combinations such as +3/-3, +4/-4 and +5/-5 across the
  selected max hold window, and qualifies only profiles that clear the 70% gate
  with positive expectancy.
- ㉑ ⭐ Pro Setups tab: professional confluence scoring, ranked trade cards
- ㉒ 📦 Range Trader tab: detects oscillating stocks with exact buy/sell/stop levels
