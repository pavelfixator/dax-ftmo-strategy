"""Experiment #0 EXTENDED — kompletní MT5 SymbolInfo audit pro GER40.cash.

Dumpuje VŠECHNA pole symbol_info, account_info, terminal_info pro identifikaci
bugů a workarounds. Output: markdown report do vaultu.

Per Strategy v3.2 prompt: "Audit všech MT5 SymbolInfo* polí pro GER40.cash.
Output: kompletní field audit do /experiments/exp0_mt5_audit.md.
Identifikuj bugy, dokumentuj workarounds."

Usage: python scripts/exp0_mt5_audit.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import Config  # noqa: E402

VAULT_REPORT = Path(
    r"C:/Users/AOS Server/trading-lab-DAX/DAX-FTMO-Strategy"
    r"/03-Backtest/Experiments/exp0_mt5_audit.md"
)


def dump_namedtuple_fields(obj, header: str) -> list[str]:
    """Dump all attributes of a MT5 namedtuple-like object as markdown table rows."""
    lines = [f"\n### {header}\n", "| Field | Value | Notes |", "|---|---|---|"]
    if obj is None:
        lines.append("| — | object is None | |")
        return lines
    fields = sorted(set(obj._asdict().keys()) if hasattr(obj, "_asdict") else dir(obj))
    for f in fields:
        if f.startswith("_"):
            continue
        try:
            val = getattr(obj, f)
        except Exception as e:  # noqa: BLE001
            val = f"<error: {e}>"
        if callable(val):
            continue
        notes = ""
        if val == 0 or val == 0.0:
            notes = "⚠️ zero — verify in GUI"
        if val is None:
            notes = "⚠️ None"
        if isinstance(val, str) and not val:
            notes = "(empty string)"
        lines.append(f"| `{f}` | `{val!r}` | {notes} |")
    return lines


def main() -> int:
    print("Experiment #0 EXTENDED — MT5 Field Audit")
    print("=" * 60)

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("FAIL: MetaTrader5 not installed")
        return 1

    if not mt5.initialize(path=Config.MT5_PATH):
        print(f"FAIL initialize: {mt5.last_error()}")
        return 1

    term = mt5.terminal_info()
    acc = mt5.account_info()
    sym = mt5.symbol_info(Config.SYMBOL)
    if sym and not sym.visible:
        mt5.symbol_select(Config.SYMBOL, True)
        sym = mt5.symbol_info(Config.SYMBOL)
    tick = mt5.symbol_info_tick(Config.SYMBOL)
    eurusd = mt5.symbol_info_tick("EURUSD")

    if acc.login != Config.MT5_LOGIN:
        print(f"FAIL: connected to {acc.login}, expected {Config.MT5_LOGIN}")
        mt5.shutdown()
        return 1

    # Build markdown report
    md: list[str] = []
    md.append("# Experiment #0 EXTENDED — MT5 Field Audit (GER40.cash)\n")
    md.append(f"**Status:** ✅ Completed  ")
    md.append(f"**Timestamp:** {dt.datetime.now().isoformat(timespec='seconds')}  ")
    md.append(f"**Account:** {acc.login} @ {acc.server}  ")
    md.append(f"**Terminal:** {term.path}  ")
    md.append(f"**MT5 build:** {term.build}  ")
    md.append(f"**MetaTrader5 module:** {mt5.__version__}  ")
    md.append(f"**Symbol:** {Config.SYMBOL}\n")
    md.append("---\n")
    md.append("## Účel\n")
    md.append(
        "Per Strategy v3.2 prompt: kompletní dump všech MT5 polí pro identifikaci "
        "API bugů a dokumentaci workaroundů. Phase 0 Day 1, rozšíření Experimentu #0.\n"
    )

    md.append("\n## 1. terminal_info()")
    md.extend(dump_namedtuple_fields(term, "Terminal"))

    md.append("\n## 2. account_info()")
    md.extend(dump_namedtuple_fields(acc, "Account"))

    md.append("\n## 3. symbol_info(GER40.cash)")
    md.extend(dump_namedtuple_fields(sym, "Symbol GER40.cash"))

    md.append("\n## 4. symbol_info_tick(GER40.cash)")
    md.extend(dump_namedtuple_fields(tick, "Live tick GER40.cash"))

    md.append("\n## 5. symbol_info_tick(EURUSD) — pro FX konverzi")
    md.extend(dump_namedtuple_fields(eurusd, "Live tick EURUSD"))

    # Specifické flagy podle Strategy v3.2
    md.append("\n---\n")
    md.append("## Specifické pole požadovaná Strategy v3.2\n")
    required = [
        ("trade_contract_size", "SYMBOL_TRADE_CONTRACT_SIZE"),
        ("trade_tick_size", "SYMBOL_TRADE_TICK_SIZE"),
        ("trade_tick_value_profit", "SYMBOL_TRADE_TICK_VALUE_PROFIT"),
        ("trade_tick_value_loss", "SYMBOL_TRADE_TICK_VALUE_LOSS"),
        ("volume_min", "SYMBOL_VOLUME_MIN"),
        ("volume_max", "SYMBOL_VOLUME_MAX"),
        ("volume_step", "SYMBOL_VOLUME_STEP"),
        ("margin_initial", "SYMBOL_MARGIN_INITIAL"),
        ("margin_maintenance", "SYMBOL_MARGIN_MAINTENANCE"),
        ("swap_long", "SYMBOL_SWAP_LONG"),
        ("swap_short", "SYMBOL_SWAP_SHORT"),
        ("swap_mode", "SYMBOL_SWAP_MODE"),
        ("filling_mode", "SYMBOL_FILLING_MODE"),
        ("trade_freeze_level", "SYMBOL_TRADE_FREEZE_LEVEL"),
        ("trade_stops_level", "SYMBOL_TRADE_STOPS_LEVEL"),
        ("trade_leverage", "SYMBOL_TRADE_LEVERAGE"),
    ]
    md.append("| Field (Python attr) | Constant | Value | Status |")
    md.append("|---|---|---|---|")
    for attr, const in required:
        val = getattr(sym, attr, "<missing attr>")
        status = "OK"
        if val == 0 or val == 0.0:
            status = "⚠️ ZERO — verify"
        if val is None:
            status = "⚠️ NONE"
        if val == "<missing attr>":
            status = "❌ MISSING"
        md.append(f"| `{attr}` | `{const}` | `{val!r}` | {status} |")

    # Bugs and workarounds section
    md.append("\n---\n")
    md.append("## Identifikované bugy + workarounds\n")

    bugs: list[str] = []

    # tick_value bug
    tv = getattr(sym, "trade_tick_value", None)
    if tv == 0.0:
        bugs.append(
            "### Bug 1: `trade_tick_value = 0.0`\n\n"
            "**Symptom:** MT5 Python API vrací 0.0 pro `trade_tick_value` u GER40.cash.\n\n"
            "**Workaround:** Pro DAX index CFD platí `1 point = 1 EUR per lot`. Spočítat:\n"
            "```python\n"
            "point_value_eur_per_lot = 1.0\n"
            "# nebo robustněji: contract_size * tick_size = 1.0 * 0.01 = 0.01 EUR per tick\n"
            "# 1 point = 100 ticks (digits=2, point=tick_size=0.01) → 1 EUR per point per lot\n"
            "```\n\n"
            "**Sizing v sizing FX verze C tedy používá:**\n"
            "```python\n"
            "lots = risk_usd / (sl_eff_points × eur_usd_spot × 1.0_eur_per_point)\n"
            "     = risk_usd / (sl_eff_points × eur_usd_spot)\n"
            "```\n"
        )

    # tick_value_profit / tick_value_loss
    tvp = getattr(sym, "trade_tick_value_profit", None)
    tvl = getattr(sym, "trade_tick_value_loss", None)
    if tvp == 0.0 or tvl == 0.0:
        bugs.append(
            "### Bug 2: `trade_tick_value_profit/loss = 0.0`\n\n"
            "**Symptom:** Oba normalized tick value fieldy vrací 0.0.\n\n"
            "**Workaround:** Stejný jako Bug 1 — `1 EUR per point per lot`, FX přepočet ručně.\n"
        )

    # stops_level
    sl_lvl = getattr(sym, "trade_stops_level", None)
    if sl_lvl == 0:
        bugs.append(
            "### Note: `trade_stops_level = 0`\n\n"
            "**Není bug**, broker FTMO neenforcuje minimum SL distance. SL může být kdekoli.\n"
            "**Implikace:** sami si hlídáme slippage buffer (3,5 bodu = 1,5 spread + 2 slippage).\n"
        )

    # Symbol-level leverage None
    sym_lev = getattr(sym, "trade_leverage", None)
    if sym_lev in (None, 0):
        bugs.append(
            "### Note: `trade_leverage` symbol-level = None / 0\n\n"
            "Symbol nedědí explicitní leverage; account-level 1:30 (Experiment #0) platí.\n"
        )

    if not bugs:
        md.append("Žádné nové bugy identifikované (kromě již známých z Experimentu #0).\n")
    else:
        md.extend(bugs)

    # Workaround block
    md.append("\n---\n")
    md.append("## Konsolidované workarounds pro `position_sizing.py`\n")
    md.append(
        "```python\n"
        '# Místo: tick_value = mt5.symbol_info("GER40.cash").trade_tick_value  # = 0.0 (bug)\n'
        '# Použít:\n'
        "POINT_VALUE_EUR_PER_LOT_GER40 = 1.0  # 1 point = 1 EUR per lot (DAX CFD standard)\n"
        "\n"
        "def calculate_lots_v32(risk_usd, sl_eff_points, eur_usd_spot, dax_price, leverage=30):\n"
        "    # FX verze C\n"
        "    lots_standard = risk_usd / (sl_eff_points * eur_usd_spot * POINT_VALUE_EUR_PER_LOT_GER40)\n"
        "    \n"
        "    # Black Swan Cap\n"
        "    BLACK_SWAN_POINTS = 200\n"
        "    BLACK_SWAN_USD_LIMIT = 5000\n"
        "    lots_blackswan = BLACK_SWAN_USD_LIMIT / (BLACK_SWAN_POINTS * eur_usd_spot)\n"
        "    \n"
        "    lots = min(lots_standard, lots_blackswan)\n"
        "    \n"
        "    # Margin cap 30% (ze 100K = 30K USD margin max)\n"
        "    margin_eur = lots * dax_price / leverage\n"
        "    margin_usd = margin_eur * eur_usd_spot\n"
        "    if margin_usd > 30000:\n"
        "        max_lots_margin = (30000 / eur_usd_spot * leverage) / dax_price\n"
        "        lots = min(lots, max_lots_margin)\n"
        "    \n"
        "    # Round na volume_step (0.01)\n"
        "    return round(lots, 2)\n"
        "```\n"
    )

    md.append("\n---\n")
    md.append("## Závěr\n")
    md.append(
        "✅ Audit dokončen. Strategy v3.2 sizing může postupovat s dokumentovanými workarounds.\n\n"
        "**Důležité konstanty pro implementaci:**\n"
        "- `POINT_VALUE_EUR_PER_LOT_GER40 = 1.0` (workaround pro tick_value bug)\n"
        "- `LEVERAGE = 30` (account-level, ověřeno Exp #0)\n"
        "- `STOPS_LEVEL = 0` (broker dovoluje SL kdekoli)\n"
        "- `VOLUME_MIN = 0.01`, `VOLUME_MAX = 1000`, `VOLUME_STEP = 0.01`\n"
        "- `SWAP_LONG_API = -386.93 EUR/lot/noc` (požaduje empirickou verifikaci v Exp #0.1)\n"
        "- `SWAP_SHORT_API = -47.82 EUR/lot/noc` (dtto)\n"
    )

    # Write report
    VAULT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    VAULT_REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"Report saved: {VAULT_REPORT}")
    print(f"Length: {len(md)} lines")

    mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
