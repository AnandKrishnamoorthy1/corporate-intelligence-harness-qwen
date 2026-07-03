"""
Tri-Agent Adversarial Investment Committee
==========================================

A multi-agent orchestration layer that replaces single-shot stock analysis with a
structured, adversarial debate between three distinct Qwen-powered personas:

    1. Bull Analyst   (Quantitative Growth)  - builds the aggressive long thesis
    2. Bear Auditor   (Forensic Risk)        - builds the brutal short thesis
    3. Portfolio Director (Compliance/Chair) - moderates, forces evidence, and issues
                                               a final vetted verdict + confidence score

Design goals (why this matters for the hackathon):
    - Distinct AI personas partition the task (long vs short vs adjudication)
    - Multi-turn debate where agents rebut each other (logic-conflict resolution)
    - The Director grounds every claim in the SAME real market-data payload, so no
      persona can invent facts (shared evidence contract)
    - A single structured verdict object is produced for the downstream trade workflow

The debate is deterministic in *structure* (fixed rounds) but non-deterministic in
*content*, which is exactly the property judges look for in agentic systems.
"""

from __future__ import annotations

import concurrent.futures as _futures
import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from loguru import logger
from pydantic import BaseModel, Field

from app.llm import call_qwen_persona, call_qwen_with_structured_output


# ============================================================================
# DATA MODELS
# ============================================================================

class DebateTurn(BaseModel):
    """A single argument produced by one persona during the committee debate."""

    round_number: int = Field(description="Debate round (1-indexed)")
    persona: str = Field(description="Persona name, e.g. 'Bull Analyst'")
    role: Literal["bull", "bear", "director"] = Field(description="Structural role")
    argument: str = Field(description="The persona's markdown argument for this turn")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class CommitteeVerdict(BaseModel):
    """The Portfolio Director's final, vetted decision after the debate."""

    ticker: str
    verdict: Literal["BUY", "HOLD", "SELL"] = Field(
        description="Final committee recommendation"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Director's confidence in the verdict"
    )
    thesis: str = Field(description="One-paragraph vetted investment thesis")
    bull_points: List[str] = Field(default_factory=list, description="Strongest long arguments")
    bear_points: List[str] = Field(default_factory=list, description="Strongest short arguments")
    key_risks: List[str] = Field(default_factory=list, description="Material risks to monitor")
    dissent: str = Field(
        default="",
        description="Any unresolved disagreement the Director chose to flag",
    )


# ============================================================================
# PERSONA SYSTEM PROMPTS
# ============================================================================

_BULL_SYSTEM = """You are the BULL ANALYST on an institutional investment committee — a
Quantitative Growth specialist. Your mandate is to build the strongest possible
evidence-based LONG (bullish) case for the stock under review.

Rules:
- Argue ONLY from the market-data payload you are given. Cite exact numbers.
- Be aggressive but intellectually honest — no invented fundamentals.
- When rebutting the Bear Auditor, attack their reasoning, not with hand-waving but
  with the data.
- Keep each turn under 180 words. Use tight markdown bullets.
Never output a final recommendation — that is the Director's job."""

_BEAR_SYSTEM = """You are the BEAR AUDITOR on an institutional investment committee — a
Forensic Risk specialist. Your mandate is to build the strongest possible
evidence-based SHORT (bearish) / caution case for the stock under review.

Rules:
- Argue ONLY from the market-data payload you are given. Cite exact numbers.
- Hunt for downside: momentum exhaustion, valuation stretch, volume anomalies, volatility.
- When rebutting the Bull Analyst, dismantle their strongest claim explicitly.
- Keep each turn under 180 words. Use tight markdown bullets.
Never output a final recommendation — that is the Director's job."""

_DIRECTOR_SYSTEM = """You are the PORTFOLIO DIRECTOR chairing an institutional investment
committee, acting as the compliance officer of record. Two analysts (Bull and Bear)
have debated a stock using a shared market-data payload.

Your mandate:
- Weigh both cases strictly on evidence quality, not rhetoric.
- Reward arguments grounded in the data; discount unsupported claims.
- Produce a single vetted verdict (BUY / HOLD / SELL) with a calibrated confidence.
- Confidence must reflect genuine uncertainty: a close debate => lower confidence.
- Surface material risks even when recommending BUY.
You must return ONLY the requested JSON. No prose outside the JSON."""


# ============================================================================
# EVIDENCE FORMATTING
# ============================================================================

def _fmt_sec(val: float) -> str:
    """Format a raw dollar value from SEC as B/M string for evidence display."""
    from app.tools.sec_tools import fmt_sec_value
    return fmt_sec_value(val)


def _format_evidence(ticker: str, market_data: Dict[str, Any]) -> str:
    """Render the shared, immutable market-data payload every persona must cite."""

    def _v(key: str, prefix: str = "", suffix: str = "") -> str:
        val = market_data.get(key)
        return f"{prefix}{val}{suffix}" if val else "N/A"

    lines = [
        "SHARED MARKET-DATA PAYLOAD (the ONLY facts any persona may cite)",
        "",
        "=== PRICE / QUOTE ===",
        f"- Ticker:         {ticker}",
        f"- Current Price:  ${market_data.get('price', 'N/A')}",
        f"- Daily Change:   {market_data.get('change', 'N/A')} ({market_data.get('change_percent', 'N/A')}%)",
        f"- Volume:         {market_data.get('volume', 'N/A'):,}" if isinstance(market_data.get('volume'), int) else f"- Volume:         {market_data.get('volume', 'N/A')}",
        f"- As-of:          {market_data.get('timestamp', 'N/A')}",
    ]

    # Fundamentals block — only rendered when OVERVIEW data is present
    fund_lines = []
    _fund_map = [
        ("sector",                        "Sector"),
        ("industry",                      "Industry"),
        ("market_cap",                    "Market Cap",         "$"),
        ("pe_ratio",                      "P/E Ratio (TTM)"),
        ("forward_pe",                    "Forward P/E"),
        ("eps",                           "EPS (TTM)",          "$"),
        ("analyst_target_price",          "Analyst Target",     "$"),
        ("week_52_high",                  "52-Week High",       "$"),
        ("week_52_low",                   "52-Week Low",        "$"),
        ("profit_margin",                 "Profit Margin"),
        ("quarterly_earnings_growth_yoy", "Earnings Growth YoY"),
        ("quarterly_revenue_growth_yoy",  "Revenue Growth YoY"),
        ("revenue_per_share_ttm",         "Revenue/Share TTM",  "$"),
        ("return_on_equity",              "Return on Equity"),
        ("beta",                          "Beta"),
        ("dividend_yield",                "Dividend Yield"),
    ]
    for entry in _fund_map:
        key = entry[0]
        label = entry[1]
        prefix = entry[2] if len(entry) > 2 else ""
        val = market_data.get(key)
        if val:
            fund_lines.append(f"- {label + ':':<30} {prefix}{val}")

    if fund_lines:
        lines.append("")
        lines.append("=== FUNDAMENTALS ===")
        lines.extend(fund_lines)

    lines.append("")
    lines.append(f"- Source: {market_data.get('data_source', 'N/A')}")

    # SEC 10-Q filings block
    sec = market_data.get("sec_filings", {})
    if sec.get("available") and sec.get("quarters"):
        lines.append("")
        lines.append("=== SEC 10-Q FILINGS (AUDITED GROUND TRUTH — last 2 quarters) ===")
        quarters = sec["quarters"]
        _metrics = [
            ("revenue",           "Revenue"),
            ("net_income",        "Net Income"),
            ("gross_profit",      "Gross Profit"),
            ("operating_income",  "Operating Income"),
            ("rd_expense",        "R&D Expense"),
            ("eps_diluted",       None),  # handled specially
            ("cash",              "Cash & Equivalents"),
            ("long_term_debt",    "Long-term Debt"),
            ("free_cash_flow",    "Free Cash Flow"),
            ("total_assets",      "Total Assets"),
            ("shareholders_equity", "Shareholders' Equity"),
        ]
        for i, q in enumerate(quarters):
            lines.append(f"")
            lines.append(
                f"Quarter {i + 1}: Period ending {q.get('period', 'N/A')} "
                f"(Filed: {q.get('filed', 'N/A')})"
            )
            for key, label in _metrics:
                val = q.get(key)
                if val is None:
                    continue
                if key == "eps_diluted":
                    lines.append(f"  - {'EPS (Diluted)':<28} ${val:.2f}")
                else:
                    lines.append(f"  - {label:<28} {_fmt_sec(val)}")
        # QoQ comparison when both quarters available
        if len(quarters) >= 2:
            q_new, q_old = quarters[0], quarters[1]
            comparisons = []
            for key, label in [("revenue", "Revenue"), ("net_income", "Net Income")]:
                v_new = q_new.get(key)
                v_old = q_old.get(key)
                if v_new is not None and v_old and v_old != 0:
                    pct = (v_new - v_old) / abs(v_old) * 100
                    comparisons.append(f"  {label} QoQ: {pct:+.1f}%")
            if comparisons:
                lines.append("")
                lines.append("QoQ Trends (most-recent vs prior quarter):")
                lines.extend(comparisons)

    return "\n".join(lines)


# ============================================================================
# COMMITTEE ENGINE
# ============================================================================

class InvestmentCommittee:
    """
    Orchestrates a multi-round adversarial debate and a moderated verdict.

    Usage:
        committee = InvestmentCommittee(rounds=2)
        transcript, verdict = committee.deliberate(ticker, market_data)
    """

    def __init__(self, rounds: int = 2):
        # Each round = one Bull turn + one Bear turn. Kept small for demo latency/cost.
        self.rounds = max(1, min(rounds, 4))

    # ---- individual persona turns -------------------------------------------------

    def _bull_turn(self, round_no: int, evidence: str, transcript: str) -> DebateTurn:
        prompt = (
            f"{evidence}\n\n"
            f"DEBATE SO FAR:\n{transcript or '(you open the debate)'}\n\n"
            f"Round {round_no}: Deliver the LONG case. If the Bear has spoken, "
            f"rebut their single strongest point using the data above."
        )
        argument = call_qwen_persona(_BULL_SYSTEM, prompt, temperature=0.7)
        logger.info(f"[COMMITTEE] Bull Analyst delivered round {round_no} argument")
        return DebateTurn(
            round_number=round_no, persona="Bull Analyst", role="bull", argument=argument
        )

    def _bear_turn(self, round_no: int, evidence: str, transcript: str) -> DebateTurn:
        prompt = (
            f"{evidence}\n\n"
            f"DEBATE SO FAR:\n{transcript}\n\n"
            f"Round {round_no}: Deliver the SHORT/caution case and dismantle the "
            f"Bull Analyst's strongest claim using the data above."
        )
        argument = call_qwen_persona(_BEAR_SYSTEM, prompt, temperature=0.7)
        logger.info(f"[COMMITTEE] Bear Auditor delivered round {round_no} argument")
        return DebateTurn(
            round_number=round_no, persona="Bear Auditor", role="bear", argument=argument
        )

    def _director_verdict(
        self, ticker: str, evidence: str, transcript: str
    ) -> CommitteeVerdict:
        schema = {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["BUY", "HOLD", "SELL"]},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "thesis": {"type": "string"},
                "bull_points": {"type": "array", "items": {"type": "string"}},
                "bear_points": {"type": "array", "items": {"type": "string"}},
                "key_risks": {"type": "array", "items": {"type": "string"}},
                "dissent": {"type": "string"},
            },
            "required": ["verdict", "confidence", "thesis", "key_risks"],
        }
        prompt = (
            f"{evidence}\n\n"
            f"FULL DEBATE TRANSCRIPT:\n{transcript}\n\n"
            f"Adjudicate the debate for {ticker}. Weigh evidence quality. Return the "
            f"verdict JSON. Confidence must reflect how close the debate was."
        )
        raw = call_qwen_with_structured_output(
            system_prompt=_DIRECTOR_SYSTEM,
            user_message=prompt,
            response_schema=schema,
            temperature=0.4,  # Director is more decisive/less exploratory
        )
        logger.info(
            f"[COMMITTEE] Director verdict: {raw.get('verdict')} "
            f"@ {raw.get('confidence')} confidence"
        )
        return CommitteeVerdict(
            ticker=ticker,
            verdict=raw.get("verdict", "HOLD"),
            confidence=float(raw.get("confidence", 0.5)),
            thesis=raw.get("thesis", ""),
            bull_points=raw.get("bull_points", []),
            bear_points=raw.get("bear_points", []),
            key_risks=raw.get("key_risks", []),
            dissent=raw.get("dissent", ""),
        )

    # ---- orchestration ------------------------------------------------------------

    def deliberate(
        self, ticker: str, market_data: Dict[str, Any]
    ) -> tuple[List[DebateTurn], CommitteeVerdict]:
        """
        Run the full multi-round debate and return (transcript, verdict).

        Parallelism: within each round, Bull and Bear both receive the same
        transcript of *prior* rounds and argue simultaneously via a thread pool.
        This preserves the adversarial rebuttal dynamic (each persona rebuts the
        other's previous-round arguments) while cutting wall-clock time from
        O(2*rounds + 1) sequential Qwen calls to O(rounds + 1) parallel steps.
        """
        logger.info("=" * 80)
        logger.info(f"[COMMITTEE] Convening investment committee for {ticker}")
        logger.info(f"[COMMITTEE] Debate rounds: {self.rounds}")
        logger.info("-" * 80)

        evidence = _format_evidence(ticker, market_data)
        turns: List[DebateTurn] = []

        def render(ts: List[DebateTurn]) -> str:
            return "\n\n".join(
                f"[Round {t.round_number}] {t.persona}:\n{t.argument}" for t in ts
            )

        for r in range(1, self.rounds + 1):
            # Snapshot the transcript BEFORE this round so both personas see
            # the same prior context and can be dispatched simultaneously.
            prior_transcript = render(turns)

            with _futures.ThreadPoolExecutor(max_workers=2) as pool:
                bull_future = pool.submit(self._bull_turn, r, evidence, prior_transcript)
                bear_future = pool.submit(self._bear_turn, r, evidence, prior_transcript)
                bull = bull_future.result()
                bear = bear_future.result()

            turns.extend([bull, bear])

        verdict = self._director_verdict(ticker, evidence, render(turns))
        logger.info("[COMMITTEE] Deliberation complete")
        logger.info("=" * 80)
        return turns, verdict


# ============================================================================
# REPORT RENDERING + PUBLIC ENTRY POINT
# ============================================================================

def _esc(text: str) -> str:
    """Escape bare $ signs so Streamlit/KaTeX doesn't treat currency as math delimiters."""
    return str(text).replace("$", r"\$")


def render_committee_report(
    ticker: str,
    market_data: Dict[str, Any],
    turns: List[DebateTurn],
    verdict: CommitteeVerdict,
) -> str:
    """Render the full committee proceedings as a judge-friendly markdown report."""
    verdict_emoji = {"BUY": "🟢", "HOLD": "🟡", "SELL": "🔴"}.get(verdict.verdict, "⚪")

    lines: List[str] = []
    lines.append(f"# 🏛️ Investment Committee Verdict: {ticker}")
    lines.append("")
    lines.append(
        f"## {verdict_emoji} Final Verdict: **{verdict.verdict}** "
        f"({verdict.confidence:.0%} confidence)"
    )
    lines.append("")
    lines.append(f"> {_esc(verdict.thesis)}")
    lines.append("")

    lines.append("### 📊 Shared Evidence")
    vol = market_data.get('volume')
    vol_str = f"{vol:,}" if isinstance(vol, int) else str(vol or 'N/A')
    lines.append(
        f"- **Price:** \\${market_data.get('price', 'N/A')} "
        f"&nbsp;|&nbsp; **Change:** {market_data.get('change_percent', 'N/A')}% "
        f"&nbsp;|&nbsp; **Volume:** {vol_str} "
        f"`[1]`"
    )
    lines.append(f"- **As-of:** {market_data.get('timestamp', 'N/A')}")
    lines.append(f"- **Source:** {market_data.get('data_source', 'N/A')}")

    # Fundamentals — shown only when OVERVIEW data was fetched
    _report_fields = [
        ("sector",                        "Sector"),
        ("industry",                      "Industry"),
        ("market_cap",                    "Market Cap",          "\\$"),
        ("pe_ratio",                      "P/E Ratio (TTM)"),
        ("forward_pe",                    "Forward P/E"),
        ("eps",                           "EPS (TTM)",           "\\$"),
        ("analyst_target_price",          "Analyst Target",      "\\$"),
        ("week_52_high",                  "52-Week High",        "\\$"),
        ("week_52_low",                   "52-Week Low",         "\\$"),
        ("profit_margin",                 "Profit Margin"),
        ("quarterly_earnings_growth_yoy", "Earnings Growth YoY"),
        ("quarterly_revenue_growth_yoy",  "Revenue Growth YoY"),
        ("beta",                          "Beta"),
        ("return_on_equity",              "Return on Equity"),
        ("dividend_yield",                "Dividend Yield"),
    ]
    fund_items = []
    for entry in _report_fields:
        key, label = entry[0], entry[1]
        prefix = entry[2] if len(entry) > 2 else ""
        val = market_data.get(key)
        if val:
            fund_items.append(f"- **{label}:** {prefix}{val}")
    if fund_items:
        lines.append("")
        lines.append("#### Fundamental Data `[2]`")
        lines.extend(fund_items)

    # SEC 10-Q filings — shown only when edgartools successfully fetched data
    sec = market_data.get("sec_filings", {})
    if sec.get("available") and sec.get("quarters"):
        lines.append("")
        lines.append("#### 📑 SEC 10-Q Filings (Audited)")
        _sec_display = [
            ("revenue",             "Revenue"),
            ("net_income",          "Net Income"),
            ("gross_profit",        "Gross Profit"),
            ("operating_income",    "Operating Income"),
            ("rd_expense",          "R&D Expense"),
            ("free_cash_flow",      "Free Cash Flow"),
            ("cash",                "Cash & Equivalents"),
            ("long_term_debt",      "Long-term Debt"),
            ("eps_diluted",         "EPS (Diluted)"),
        ]
        for i, q in enumerate(sec["quarters"]):
            cite_num = 3 + i
            label = (
                f"**Q-{i + 1}** (period {q.get('period', 'N/A')}, "
                f"filed {q.get('filed', 'N/A')}) `[{cite_num}]`"
            )
            items = []
            for key, name in _sec_display:
                val = q.get(key)
                if val is None:
                    continue
                if key == "eps_diluted":
                    items.append(f"EPS \\${val:.2f}")
                else:
                    items.append(f"{name} {_esc(_fmt_sec(val))}")
            if items:
                lines.append(f"- {label}: " + " &nbsp;|&nbsp; ".join(items))
        # QoQ trend line
        if len(sec["quarters"]) >= 2:
            q_new, q_old = sec["quarters"][0], sec["quarters"][1]
            trend_parts = []
            for key, name in [("revenue", "Rev"), ("net_income", "NI")]:
                v_new = q_new.get(key)
                v_old = q_old.get(key)
                if v_new is not None and v_old and v_old != 0:
                    pct = (v_new - v_old) / abs(v_old) * 100
                    trend_parts.append(f"{name} QoQ {pct:+.1f}%")
            if trend_parts:
                lines.append(f"- *Trend: {' &nbsp;|&nbsp; '.join(trend_parts)}*")

    # Citation footnotes footer
    _cite_footer = ["---", "**Sources:**"]
    _cite_footer.append("**[1]** Alpha Vantage — Live Quote")
    av_fund_present = any(market_data.get(k) for k in ("pe_ratio", "eps", "sector"))
    if av_fund_present:
        _cite_footer.append(" &nbsp;·&nbsp; **[2]** Alpha Vantage — Company Overview (EDGAR XBRL)")
    if sec.get("available") and sec.get("quarters"):
        for i, q in enumerate(sec["quarters"]):
            _cite_footer.append(f" &nbsp;·&nbsp; **[{3 + i}]** SEC 10-Q (period {q.get('period', 'N/A')})")
    lines.append("")
    lines.append(" ".join(_cite_footer))
    lines.append("")

    if verdict.bull_points:
        lines.append("### 🟢 Strongest Bull Points")
        lines.extend(f"- {_esc(p)}" for p in verdict.bull_points)
        lines.append("")
    if verdict.bear_points:
        lines.append("### 🔴 Strongest Bear Points")
        lines.extend(f"- {_esc(p)}" for p in verdict.bear_points)
        lines.append("")
    if verdict.key_risks:
        lines.append("### ⚠️ Key Risks to Monitor")
        lines.extend(f"- {_esc(r)}" for r in verdict.key_risks)
        lines.append("")
    if verdict.dissent:
        lines.append("### 🧩 Unresolved Dissent")
        lines.append(f"> {_esc(verdict.dissent)}")
        lines.append("")

    lines.append("---")
    lines.append("## 🗣️ Full Debate Transcript")
    lines.append("")
    for t in turns:
        icon = "🟢" if t.role == "bull" else "🔴"
        lines.append(f"**{icon} {t.persona} — Round {t.round_number}**")
        lines.append("")
        lines.append(_esc(t.argument))
        lines.append("")

    lines.append("---")
    lines.append(f"*Committee convened at {datetime.now().isoformat()} — "
                 f"{len(turns)} arguments across {max(t.round_number for t in turns)} rounds.*")
    return "\n".join(lines)


def run_investment_committee(
    ticker: str,
    market_data: Dict[str, Any],
    rounds: int = 2,
) -> Dict[str, Any]:
    """
    Public entry point: run the committee and return a structured result bundle.

    Returns a dict with:
        - verdict:   CommitteeVerdict as dict
        - transcript: list of DebateTurn as dicts
        - report_markdown: rendered proceedings
    """
    committee = InvestmentCommittee(rounds=rounds)
    turns, verdict = committee.deliberate(ticker, market_data)
    report = render_committee_report(ticker, market_data, turns, verdict)
    return {
        "verdict": verdict.model_dump(),
        "transcript": [t.model_dump() for t in turns],
        "report_markdown": report,
    }
