def build_downside_scenarios(profile: dict, fin_health: dict, valuation: dict) -> list[dict]:
    """
    Facts-first risk library with estimated directional impact bands.
    These are *scenario impacts*, not predictions.
    """
    risks = []

    # Macroeconomic risks
    risks.append({
        "category": "Macro",
        "scenario": "Enterprise IT spending slowdown (recession / budget tightening)",
        "mechanism": "Lower discretionary software spend reduces new bookings and slows expansion.",
        "impact_band": {
            "revenue_growth": "-10% to -30% vs expected trajectory",
            "margin": "-2 to -8 pts operating margin (mix + sales cycles)",
            "valuation": "multiple compression risk increases"
        }
    })

    risks.append({
        "category": "Macro/Government",
        "scenario": "Government contract timing/budget delays",
        "mechanism": "Procurement delays and program reprioritization reduce near-term revenue recognition.",
        "impact_band": {
            "revenue_growth": "-5% to -20% (timing-driven)",
            "cash_flow": "collection/working capital volatility"
        }
    })

    # Industry disruption risks
    risks.append({
        "category": "Industry",
        "scenario": "Hyperscaler bundling and platform competition (AWS/Azure/GCP)",
        "mechanism": "Bundled analytics + AI tooling pressures pricing and reduces win rates.",
        "impact_band": {
            "revenue_growth": "-15% to -40% over multi-year horizon",
            "margin": "-3 to -10 pts if pricing pressure rises"
        }
    })

    risks.append({
        "category": "Industry",
        "scenario": "Commoditization of AI/data tooling",
        "mechanism": "Differentiation narrows as capabilities become standardized; switching costs fall.",
        "impact_band": {
            "margin": "-5 to -15 pts (pricing pressure)",
            "valuation": "premium multiple becomes harder to justify"
        }
    })

    # Management / execution
    risks.append({
        "category": "Execution",
        "scenario": "Commercial growth deceleration",
        "mechanism": "Slower customer adds and expansion reduces overall growth; sentiment impacts premium valuation.",
        "impact_band": {
            "revenue_growth": "step-down to low-teens possible",
            "valuation": "large multiple compression risk"
        }
    })

    # Financial risks: mostly valuation + dilution
    risks.append({
        "category": "Financial",
        "scenario": "Valuation compression without fundamental decline",
        "mechanism": "Market re-rates premium multiples toward peer band during risk-off or growth normalization.",
        "impact_band": {
            "stock": "-30% to -60% possible from multiple change alone",
        }
    })

    risks.append({
        "category": "Financial",
        "scenario": "Stock-based compensation and dilution",
        "mechanism": "Share count growth reduces per-share earnings power over time.",
        "impact_band": {
            "eps": "5–10% annual headwind if dilution persists",
            "stock": "downside via per-share metric pressure"
        }
    })

    # Company-specific financial red flags from computed health
    flags = fin_health.get("red_flags", [])
    if flags:
        risks.append({
            "category": "Financial (Data flags)",
            "scenario": "Financial statement flags detected",
            "mechanism": "One or more automated flags from statement signals.",
            "flags": flags
        })

    return risks