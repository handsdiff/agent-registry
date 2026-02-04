#!/usr/bin/env python3
"""Generate MoltMarkets intelligence report."""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

API_BASE = "https://moltmarkets-api-production.up.railway.app"

def fetch_json(url):
    """Fetch JSON from URL using stdlib."""
    req = urllib.request.Request(url, headers={"User-Agent": "MoltMarketsIntel/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

def fetch_markets():
    """Fetch all active markets."""
    result = fetch_json(f"{API_BASE}/markets")
    return result.get("data", result) if isinstance(result, dict) else result

def fetch_leaderboard():
    """Fetch leaderboard for context."""
    result = fetch_json(f"{API_BASE}/leaderboard")
    return result.get("data", result) if isinstance(result, dict) else result

def analyze_market(market):
    """Analyze a single market for signals."""
    signals = []
    
    # Get current probability
    yes_prob = market.get("probability", 0.5)
    no_prob = 1 - yes_prob
    
    # Get market metadata
    title = market.get("title", "Unknown")
    market_id = market.get("id")
    closes_at = market.get("closes_at")
    total_volume = market.get("total_volume", 0)
    
    # Simple heuristics for now
    # Flag extreme probabilities with low volume (potential mispricing)
    if total_volume < 100:
        if yes_prob > 0.9 or yes_prob < 0.1:
            signals.append({
                "type": "low_volume_extreme",
                "message": f"Extreme odds ({yes_prob:.0%}) with low volume ({total_volume}ŧ) - verify",
                "confidence": "low"
            })
    
    # Flag markets close to resolution
    if closes_at:
        try:
            close_time = datetime.fromisoformat(closes_at.replace("Z", "+00:00"))
            hours_left = (close_time - datetime.now(timezone.utc)).total_seconds() / 3600
            if 0 < hours_left < 2:
                signals.append({
                    "type": "closing_soon",
                    "message": f"Resolves in {hours_left:.1f}h - last chance to trade",
                    "confidence": "high"
                })
        except:
            pass
    
    return {
        "market_id": market_id,
        "title": title,
        "yes_prob": yes_prob,
        "volume": total_volume,
        "signals": signals
    }

def generate_report():
    """Generate full intelligence report."""
    markets = fetch_markets()
    leaderboard = fetch_leaderboard()
    
    # Analyze each market
    analyses = []
    total_volume = 0
    for market in markets:
        if market.get("resolved"):
            continue  # Skip resolved markets
        analysis = analyze_market(market)
        if analysis["signals"]:
            analyses.append(analysis)
        total_volume += market.get("total_volume", 0)
    
    # Build report
    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "active_markets": len([m for m in markets if not m.get("resolved")]),
            "total_volume": total_volume,
            "markets_with_signals": len(analyses)
        },
        "signals": analyses,
        "leaderboard_top5": leaderboard[:5] if leaderboard else [],
        "notes": []
    }
    
    # Add market-wide observations
    if len(analyses) == 0:
        report["notes"].append("No obvious mispricings detected. Markets seem efficient.")
    if total_volume < 500:
        report["notes"].append("Low overall volume - market is quiet.")
    
    return report

def format_report_text(report):
    """Format report for human/agent reading."""
    lines = [
        "📊 MoltMarkets Intelligence Report",
        f"Generated: {report['generated'][:16]}",
        "",
        f"Active Markets: {report['summary']['active_markets']}",
        f"Total Volume: {report['summary']['total_volume']}ŧ",
        f"Markets with Signals: {report['summary']['markets_with_signals']}",
        ""
    ]
    
    if report["signals"]:
        lines.append("🚨 Signals:")
        for analysis in report["signals"]:
            lines.append(f"\n**{analysis['title'][:50]}**")
            lines.append(f"  Odds: {analysis['yes_prob']:.0%} YES | Volume: {analysis['volume']}ŧ")
            for sig in analysis["signals"]:
                lines.append(f"  → {sig['message']}")
    
    if report["notes"]:
        lines.append("\n📝 Notes:")
        for note in report["notes"]:
            lines.append(f"  • {note}")
    
    return "\n".join(lines)

if __name__ == "__main__":
    try:
        report = generate_report()
        
        if "--json" in sys.argv:
            print(json.dumps(report, indent=2))
        else:
            print(format_report_text(report))
            
        # Save to file
        output_dir = Path(__file__).parent / "reports"
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        with open(output_dir / f"report_{timestamp}.json", "w") as f:
            json.dump(report, f, indent=2)
            
    except Exception as e:
        print(f"Error generating report: {e}", file=sys.stderr)
        sys.exit(1)
