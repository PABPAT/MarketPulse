from core.matcher import parse_market, are_markets_comparable, validate_with_groq

test_pairs = [

    # ✅ SHOULD MATCH
    {
        "label": "Fed cut - generic vs specific meeting",
        "a": "Fed rate cut by June 2026?",
        "b": "Will Fed cut 25bps at June 2026 meeting?",
        "expected": True
    },
    {
        "label": "US inflation same threshold",
        "a": "Will US inflation exceed 3% in 2026?",
        "b": "Will CPI rise more than 3% in 2026?",
        "expected": True
    },
    {
        "label": "Fed rate level same threshold same year",
        "a": "Will the upper bound of the target federal funds rate be 3.75% at end of 2026?",
        "b": "Will the upper bound of the federal funds rate be above 3.75% in December 2026?",
        "expected": True
    },
    {
        "label": "Fed cut by meeting month",
        "a": "Fed rate cut by September 2026 meeting?",
        "b": "Will Fed cut rates at September 2026 FOMC?",
        "expected": True
    },
    {
        "label": "US GDP same quarter same threshold",
        "a": "Will US GDP growth in Q1 2026 be above 2.0%?",
        "b": "Will real GDP increase by more than 2.0% in Q1 2026?",
        "expected": True
    },
    {
        "label": "CPI monthly same month close threshold",
        "a": "Will monthly inflation increase by 0.3% in March 2026?",
        "b": "Will CPI rise more than 0.3% in March 2026?",
        "expected": True
    },
    {
        "label": "Recession same year",
        "a": "US recession by end of 2026?",
        "b": "Will the US enter a recession in 2026?",
        "expected": True
    },
    {
        "label": "Fed cut - no month specified both sides",
        "a": "Will the Fed cut rates in 2026?",
        "b": "Will there be a Fed rate cut in 2026?",
        "expected": True
    },
    {
        "label": "CPI threshold within 0.5% tolerance",
        "a": "Will monthly CPI increase by 0.3% in March 2026?",
        "b": "Will CPI rise more than 0.2% in March 2026?",
        "expected": True
    },
    {
        "label": "Fed rate - end of year vs December",
        "a": "Will the federal funds rate be 3.75% at end of 2026?",
        "b": "Will the upper bound of the federal funds rate be above 3.75% in December 2026?",
        "expected": True
    },
    {
        "label": "Q1 vs January — SHOULD match",
        "a": "Will US GDP grow above 2% in Q1 2026?",
        "b": "Will real GDP increase by more than 2% in January 2026?",
        "expected": True
    },
    {
        "label": "Q2 vs June — SHOULD match",
        "a": "Will US GDP grow above 2% in Q2 2026?",
        "b": "Will real GDP increase by more than 2% in June 2026?",
        "expected": True
    },
    {
        "label": "Q3 vs September — SHOULD match",
        "a": "Will US GDP grow above 2% in Q3 2026?",
        "b": "Will real GDP increase by more than 2% in September 2026?",
        "expected": True
    },

    # ❌ SHOULD NOT MATCH
    {
        "label": "China GDP vs US GDP",
        "a": "Will China GDP growth in Q1 2026 be between 3.5 and 4.0%?",
        "b": "Will real GDP increase by more than 1.0% in Q1 2026?",
        "expected": False
    },
    {
        "label": "UK GDP vs US GDP",
        "a": "Will UK GDP growth in Q1 2026 be between 1.5% and 1.8%?",
        "b": "Will real GDP increase by more than 1.0% in Q1 2026?",
        "expected": False
    },
    {
        "label": "Argentina inflation vs US CPI",
        "a": "Will Argentina monthly inflation in March 2026 be less than 2.1%?",
        "b": "Will CPI rise more than 0.3% in March 2026?",
        "expected": False
    },
    {
        "label": "Fed rate 2026 vs 2027",
        "a": "Will the upper bound of the target federal funds rate be 1.75% at end of 2026?",
        "b": "Will the upper bound of the federal funds rate be above 0.50% following Mar 17, 2027?",
        "expected": False
    },
    {
        "label": "CPI 2026 vs 2027",
        "a": "Will US inflation exceed 3% in 2026?",
        "b": "Will CPI rise more than 3% in 2027?",
        "expected": False
    },
    {
        "label": "Fed cut June vs September",
        "a": "Fed rate cut by June 2026 meeting?",
        "b": "Will Fed cut rates at September 2026 FOMC?",
        "expected": False
    },
    {
        "label": "CPI March vs April",
        "a": "Will monthly inflation increase by 0.3% in March 2026?",
        "b": "Will CPI rise more than 0.3% in April 2026?",
        "expected": False
    },
    {
        "label": "Fed rate level 1.75% vs 0.50%",
        "a": "Will the upper bound of the target federal funds rate be 1.75% at end of 2026?",
        "b": "Will the upper bound of the federal funds rate be above 0.50% following Mar 17, 2026?",
        "expected": False
    },
    {
        "label": "GDP 3.5%-4.0% vs 1.0%",
        "a": "Will US GDP growth in Q1 2026 be between 3.5 and 4.0%?",
        "b": "Will real GDP increase by more than 1.0% in Q1 2026?",
        "expected": False
    },
    {
        "label": "CPI 5% vs 3%",
        "a": "Will US inflation exceed 5% in 2026?",
        "b": "Will CPI rise more than 3% in 2026?",
        "expected": False
    },
    {
        "label": "Fed rate vs GDP",
        "a": "Will the Fed cut rates in June 2026?",
        "b": "Will real GDP increase by more than 2.0% in Q2 2026?",
        "expected": False
    },
    {
        "label": "Inflation vs GDP",
        "a": "Will US inflation exceed 3% in 2026?",
        "b": "Will US GDP grow more than 2% in 2026?",
        "expected": False
    },
    {
        "label": "Fed cut count vs rate level",
        "a": "Will 3 Fed rate cuts happen in 2026?",
        "b": "Will the upper bound of the federal funds rate be 3.75% at end of 2026?",
        "expected": False
    },
    {
        "label": "Fed cut yes/no vs rate level",
        "a": "Fed rate hike in 2026?",
        "b": "Will the upper bound of the federal funds rate be above 4.5% in 2026?",
        "expected": False
    },
    {
        "label": "End of year vs November — should NOT match",
        "a": "Will federal funds rate be 3.75% at end of 2026?",
        "b": "Will upper bound be above 3.75% in November 2026?",
        "expected": False
    },
    {
        "label": "Q1 vs April — should NOT match",
        "a": "Will US GDP grow above 2% in Q1 2026?",
        "b": "Will real GDP increase by more than 2% in April 2026?",
        "expected": False
    },
    {
        "label": "Q3 vs October — should NOT match",
        "a": "Will US GDP grow above 2% in Q3 2026?",
        "b": "Will real GDP increase by more than 2% in October 2026?",
        "expected": False
    },
]


def run_tests():
    print("=" * 70)
    print("MATCHER TEST SUITE")
    print("=" * 70)

    stage1_correct = 0
    stage1_total = 0
    stage2_correct = 0
    stage2_total = 0
    false_positives = []
    false_negatives = []

    for test in test_pairs:
        label = test["label"]
        q_a = test["a"]
        q_b = test["b"]
        expected = test["expected"]

        # Note: kalshi is first arg, polymarket is second
        pa = parse_market(q_a)
        pb = parse_market(q_b)
        s1_result, s1_reason = are_markets_comparable(pb, pa)

        stage1_total += 1

        if not expected and not s1_result:
            stage1_correct += 1
            status = "✅ S1 CORRECT BLOCK"
        elif expected and s1_result:
            stage1_correct += 1
            status = "✅ S1 PASSED"
        elif expected and not s1_result:
            status = "⚠️  S1 FALSE NEGATIVE"
            false_negatives.append({
                "label": label,
                "stage": "Stage 1",
                "reason": s1_reason
            })
        else:
            status = "🚨 S1 FALSE POSITIVE → sending to Groq"
            false_positives.append({
                "label": label,
                "stage": "Stage 1",
                "reason": s1_reason
            })

        print(f"\n[{status}] {label}")
        print(f"  A: {q_a}")
        print(f"  B: {q_b}")
        print(f"  Expected: {expected} | "
              f"Stage 1: {s1_result} — {s1_reason}")

        if s1_result:
            groq_result = validate_with_groq(q_a, q_b)
            groq_comparable = groq_result.get("comparable")
            stage2_total += 1

            if groq_comparable == expected:
                stage2_correct += 1
                groq_status = "✅ GROQ CORRECT"
            elif expected and not groq_comparable:
                groq_status = "⚠️  GROQ FALSE NEGATIVE"
                false_negatives.append({
                    "label": label,
                    "stage": "Groq",
                    "reason": groq_result.get("reason")
                })
            else:
                groq_status = "🚨 GROQ FALSE POSITIVE"
                false_positives.append({
                    "label": label,
                    "stage": "Groq",
                    "reason": groq_result.get("reason")
                })

            print(f"  Stage 2 Groq: {groq_comparable} "
                  f"({groq_result.get('confidence')}) — "
                  f"{groq_result.get('reason')} [{groq_status}]")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Stage 1 accuracy: {stage1_correct}/{stage1_total} "
          f"({round(stage1_correct / stage1_total * 100)}%)")
    if stage2_total > 0:
        print(f"Stage 2 accuracy: {stage2_correct}/{stage2_total} "
              f"({round(stage2_correct / stage2_total * 100)}%)")

    if false_positives:
        print(f"\n🚨 FALSE POSITIVES ({len(false_positives)}):")
        for fp in false_positives:
            print(f"  [{fp['stage']}] {fp['label']}: {fp['reason']}")

    if false_negatives:
        print(f"\n⚠️  FALSE NEGATIVES ({len(false_negatives)}):")
        for fn in false_negatives:
            print(f"  [{fn['stage']}] {fn['label']}: {fn['reason']}")

    print("\nDone.")


if __name__ == "__main__":
    run_tests()