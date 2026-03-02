---
title: "Prediction Market Arbitrage Guide (2026): Cross-Platform Strategies"
description: "Step-by-step guide to finding arbitrage opportunities between Kalshi and Polymarket. Learn how to identify, calculate, and execute cross-platform arbs with real examples."
pubDate: 2026-02-24
category: "strategies"
tags: ["strategies", "kalshi", "polymarket"]
affiliate: "kalshi"
faqs:
  - question: "What's prediction market arbitrage?"
    answer: "Prediction market arbitrage means buying a contract on one platform where it's cheap and selling the equivalent on another platform where it's expensive, locking in a guaranteed profit regardless of the outcome."
  - question: "Can you arbitrage between Kalshi and Polymarket?"
    answer: "Yes, when both platforms list contracts on the same event. If Kalshi prices YES at 40 cents and Polymarket prices YES at 55 cents, there's a potential arbitrage opportunity -- though fees, execution risk, and settlement differences affect profitability."
  - question: "How much profit can you make from prediction market arbitrage?"
    answer: "Individual arbitrage trades typically yield 2-8% profit after fees. The challenge is finding opportunities, executing before they close, and managing capital across platforms. Automated scanning significantly improves detection speed."
---

Arbitrage in [prediction markets](/blog/what-are-prediction-markets) is the closest thing to a free lunch in trading: buy a contract on one platform where it's cheap, sell (or buy the opposite side on) another platform where it's expensive, and lock in a guaranteed profit regardless of the outcome. In theory, it's risk-free. In practice, fees, execution risk, and settlement differences make it far more nuanced than it appears. This guide walks through exactly how to find, calculate, and execute prediction market arbitrage -- and when to walk away.

## What Is Prediction Market Arbitrage?

Arbitrage is the simultaneous purchase and sale of equivalent contracts at different prices to capture a risk-free profit. In prediction markets, this most commonly occurs when the same event is listed on both [Kalshi](https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21&m=true&utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup) and [Polymarket](https://polymarket.us/1762?utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup) at different prices.

The basic logic: if a YES [event contract](/blog/what-are-event-contracts) on an event trades at $0.55 on Kalshi and $0.60 on Polymarket, or if you can buy YES on Kalshi for $0.55 and NO on Polymarket for $0.35 (implying YES at $0.65), the price difference creates an opportunity. If the prices on both platforms for a YES and the equivalent NO sum to less than $1.00 (after fees), you can profit.

Why do these discrepancies exist? Different platforms have different participant pools, different [fee structures](/blog/kalshi-fees-explained), different liquidity profiles, and different information propagation speeds. A news event might reprice a contract on Polymarket (which has deeper liquidity and faster-moving crypto-native traders) before Kalshi's order book adjusts. Or vice versa -- Kalshi traders with domain expertise in weather or economics might price those contracts more accurately while Polymarket lags.

## How to Identify an Arb

Finding genuine arbitrage requires a systematic approach. Here's the three-step process.

### Step 1: Find Overlapping Markets

Look for events that are listed on both Kalshi and Polymarket with identical (or nearly identical) resolution criteria. Common overlapping categories include:

- Federal Reserve rate decisions
- CPI and economic data releases
- [Bitcoin](/blog/will-bitcoin-hit-75000-in-2026-price-prediction-and-market-odds) and [Ethereum](/blog/will-ethereum-reach-4500-in-2026-what-prediction-markets-say) price milestones
- Major political outcomes
- Election results

The resolution criteria must match. "Will Bitcoin exceed $100,000 by December 31?" on Kalshi and "Bitcoin above $100K on Dec 31" on Polymarket are likely the same contract -- but verify the exact settlement source, time, and boundary conditions. A contract that settles at 11:59 PM ET on one platform and 00:00 UTC on another isn't the same contract.

### Step 2: Compare Prices Across Both Sides

A real arbitrage requires the combined cost of covering both outcomes to be less than $1.00. Here's the math:

**Arb exists if: Kalshi YES price + Polymarket NO price < $1.00**

(Or any combination where you buy YES on one platform and NO on the other, and the total cost is under $1.00.)

### Step 3: Account for Fees on Both Sides

This is where most apparent arbs die. You must calculate the net profit after fees on both platforms, for both possible outcomes.

**Scenario A (Event occurs):** Your Kalshi YES wins, your Polymarket NO loses.
- Kalshi: receive $1.00, pay fee on profit, net = cost + (1 - cost) × 0.93
- Polymarket: lose your NO cost entirely

**Scenario B (Event doesn't occur):** Your Kalshi YES loses, your Polymarket NO wins.
- Kalshi: lose your YES cost entirely
- Polymarket: receive $1.00, net = cost + (1 - cost)

For the arb to be real, **both scenarios must be profitable** after fees.

### Worked Example: Fed Rate Cut Decision

Suppose:
- Kalshi YES (Fed cuts rates): $0.35
- Polymarket NO (Fed doesn't cut): $0.58

Total cost: $0.35 + $0.58 = **$0.93**

Now calculate both outcomes:

**If the Fed cuts (Kalshi YES wins):**
- Kalshi profit: ($1.00 - $0.35) × 0.93 = $0.6045 net profit → Total return = $0.35 + $0.6045 = $0.9545
- Polymarket loss: -$0.58
- Net: $0.9545 - $0.58 = **+$0.3745** ... wait, but total investment was $0.93
- Combined return: $0.9545 (Kalshi payout) + $0.00 (Poly NO expires worthless) = $0.9545
- Net profit: $0.9545 - $0.93 = **+$0.0245**

**If the Fed doesn't cut (Polymarket NO wins):**
- Kalshi loss: -$0.35
- Polymarket profit: $1.00 - $0.58 = $0.42 net profit → Total return = $0.58 + $0.42 = $1.00
- Combined return: $0.00 (Kalshi YES expires worthless) + $1.00 (Poly NO payout) = $1.00
- Net profit: $1.00 - $0.93 = **+$0.07**

Both scenarios are profitable. This is a valid arb with a guaranteed profit between $0.02 and $0.07 per contract pair, depending on the outcome.

> **Find arbs automatically:** Use our [Arbitrage Scanner](/tools/arbitrage-scanner) to calculate guaranteed profits after fees for any cross-platform price discrepancy. Enter prices from both platforms and see instantly whether a real arb exists.

## The Fee Calculation That Kills Most Arbs

Most price discrepancies between Kalshi and Polymarket are small -- 2 to 5 cents. After accounting for Kalshi's 7% fee on profits, that slim margin often evaporates entirely.

### Counter-Example: The Arb That Is Not an Arb

Suppose:
- Kalshi YES: $0.48
- Polymarket NO: $0.49

Total cost: $0.97. Looks like a potential 3-cent arb before fees.

**If YES wins:**
- Kalshi: ($1.00 - $0.48) × 0.93 = $0.4836 profit → Return = $0.9636
- Net: $0.9636 - $0.97 = **-$0.0064** (LOSS)

The Kalshi fee turned a 3-cent gross arb into a loss on one scenario. This isn't a valid arb. You must be profitable in BOTH scenarios, and even a small fee can flip the math.

**Rule of thumb:** On Kalshi, the fee erodes roughly 3.5 cents per contract on mid-priced contracts (around $0.50). Any cross-platform spread smaller than 4-5 cents after Kalshi fees is almost certainly not a profitable arb. The calculator handles this precisely, but knowing the approximate threshold saves you from chasing phantom opportunities.

## The Execution Checklist

When you've identified a genuine arb, execute it methodically:

1. **Verify resolution criteria match.** Read the settlement rules on both platforms. Same event name isn't enough -- confirm the data source, settlement time, and boundary conditions are identical.

2. **Check order book depth on both sides.** An arb at the top of book is meaningless if there are only 5 contracts available. You need enough liquidity to fill your desired size on both platforms simultaneously.

3. **Calculate exact profit for both scenarios.** Use the [Arbitrage Scanner](/tools/arbitrage-scanner) or run the math manually. Both outcomes must show positive net profit after all fees.

4. **Execute both legs as close to simultaneously as possible.** Place both orders within seconds. If you execute one leg and the other side moves before you fill, you no longer have an arb -- you have a directional bet. [Automated trading via API](/blog/how-to-use-apis-for-automated-prediction-market-trading) can help close both legs within seconds.

5. **Confirm both fills.** Check that both orders are fully filled at your expected prices. Partial fills on one leg leave you with an imbalanced position.

6. **Wait for settlement.** Once both legs are filled, there's nothing more to do. One side will pay out $1.00, the other will expire at $0.00, and your guaranteed profit is locked in.

## Risks That Are Not Priced In

Arbitrage in prediction markets isn't truly "risk-free" the way textbook arbitrage is. There are several risks that even a valid arb can't eliminate.

### Execution Risk

Prices move. If you buy YES on Kalshi at $0.35 and then switch to Polymarket to buy NO, the NO price might have moved from $0.58 to $0.63 in the 30 seconds it took you to switch platforms. Your arb just disappeared. This risk increases during volatile periods -- exactly when the biggest price discrepancies tend to appear.

### Settlement Difference Risk

Even when two contracts appear to cover the same event, subtle differences in settlement rules can create situations where one platform resolves YES and the other also resolves YES on what you thought was the opposite side. Read the fine print carefully. Different settlement sources, rounding rules, or edge-case definitions can cause both legs to lose.

### Liquidity Risk

Thin order books mean you might not be able to fill your desired size on both legs. Worse, if you need to exit one leg early (because the other leg didn't fill), you might face wide spreads that eat into your profits or turn the trade negative.

### Capital Lockup

Prediction market contracts tie up your capital until settlement, which could be days, weeks, or months away. A 3% guaranteed return sounds good until you realize your capital is locked for 60 days. Annualized, that 3% over 60 days is roughly 18% -- still decent. But if settlement is 6 months away, the same 3% annualizes to just 6%. Consider the opportunity cost of locked capital. The [Kelly criterion](/blog/kelly-criterion-prediction-markets-guide) can help you decide whether the annualized return justifies the capital commitment.

### Regulatory Risk

You're operating across two platforms with very different regulatory statuses. [Kalshi is CFTC-regulated](/blog/is-kalshi-legal); Polymarket is not. If one platform faces regulatory action, freezes funds, or disputes a settlement, your "risk-free" profit is suddenly at risk. For more on these differences, see our [Kalshi vs Polymarket comparison](/blog/kalshi-vs-polymarket-which-platform-should-you-use).

## Is Arb Worth It?

Let's be honest: prediction market arbitrage is rarely the primary profit driver for active traders. The opportunities are infrequent, the spreads are thin, and execution complexity adds friction. Where it does add value:

- **Low-risk capital deployment.** If you have idle capital on two platforms, arbs put that capital to work with near-zero directional risk.
- **Learning the mechanics.** Arb hunting forces you to understand both platforms deeply -- order books, fees, settlement rules, and execution. That knowledge pays dividends when you move to directional trading.
- **Supplemental income.** A few arbs per month at 2-5% per trade on moderate size adds up, especially if settlement is quick. Browse [live odds across platforms](/odds) to spot price discrepancies as they appear.

For most traders, the higher-return path is developing directional edge through better probability estimates, as outlined in our [strategies guide](/blog/prediction-market-strategies-finding-edge-as-a-retail-trader). But arbitrage is a useful tool in the toolkit, and when a genuine opportunity appears, the math is straightforward and the risk is minimal.

## Key Takeaways

- **Arbitrage = buying both sides across platforms for less than $1.00.** Profit is guaranteed if both scenarios are profitable after fees.
- **Fees kill most apparent arbs.** Kalshi's 7% profit fee means you need at least a 4-5 cent gross spread before an arb is viable.
- **Always check both scenarios.** A trade that profits in one outcome but loses in the other isn't an arb -- it's a directional bet.
- **Verify resolution criteria match exactly.** Same event name doesn't guarantee same settlement rules.
- **Execute both legs simultaneously.** Delayed execution on one side turns a risk-free trade into a risky one.
- **Account for capital lockup.** Annualize your return based on time to settlement, not just the raw percentage.
- **Arbs are supplemental, not primary.** The big money in prediction markets comes from directional edge, not from arbitrage. But when arbs appear, take them.
