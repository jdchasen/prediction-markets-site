---
title: "The Kelly Criterion for Prediction Markets: A Complete Guide to Optimal Bet Sizing"
description: "Master the Kelly criterion for prediction market trading. Learn the formula, see worked examples with fees, and understand why fractional Kelly is the professional standard."
pubDate: 2026-02-24
category: "strategies"
tags: ["strategies", "kalshi", "probability"]
affiliate: "kalshi"
---

You have found a prediction market contract with positive expected value. You are confident in your edge. The question that determines whether you grow your account or blow it up is: how much should you bet? Too little and you leave money on the table. Too much and a run of bad luck wipes you out. The Kelly criterion answers this question with mathematical precision, and it is the position-sizing framework used by virtually every serious prediction market trader.

## What Is the Kelly Criterion?

The Kelly criterion is a formula developed by John Kelly at Bell Labs in 1956 that calculates the optimal fraction of your bankroll to wager on a bet with positive expected value. "Optimal" here means the bet size that maximizes the long-term growth rate of your wealth.

The key insight is that there is a single bet size that grows your bankroll faster than any other over repeated bets. Bet less than Kelly and you grow more slowly than optimal. Bet more than Kelly and you actually grow slower -- because the oversized bets amplify variance and increase the chance of devastating drawdowns.

Kelly is not a guarantee of profit on any single trade. It is a framework for making the mathematically best sizing decision given your edge, the odds, and the assumption that you will make many similar bets over time.

## The Kelly Formula for Prediction Markets

For a binary prediction market contract, the Kelly fraction is:

**f = (b × p - q) / b**

Where:
- **f** = fraction of bankroll to bet
- **b** = net odds (profit per dollar risked if you win)
- **p** = your estimated probability of winning
- **q** = 1 - p (probability of losing)

In prediction markets, the net odds account for both the contract price and platform fees:

**b = ((1 - price) × (1 - feeRate)) / price**

Where `price` is the contract price as a decimal (e.g., $0.40 = 0.40) and `feeRate` is 0.07 for [Kalshi](https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21&m=true&utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup) or 0 for [Polymarket](https://polymarket.us/1762?utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup).

### Worked Example 1: Weather Contract on Kalshi

A weather contract is trading at $0.40. Your model estimates a 55% probability the event occurs.

1. **Calculate net odds:** b = (0.60 × 0.93) / 0.40 = 0.558 / 0.40 = **1.395**
2. **Apply Kelly formula:** f = (1.395 × 0.55 - 0.45) / 1.395 = (0.7673 - 0.45) / 1.395 = **22.7%**
3. **Dollar amount:** On a $1,000 bankroll, full Kelly says bet $227

That means buying $227 / $0.40 = **567 contracts**.

### Worked Example 2: Economic Contract on Kalshi

A Fed rate decision contract is trading at $0.70. You estimate a 78% probability of the event.

1. **Net odds:** b = (0.30 × 0.93) / 0.70 = 0.279 / 0.70 = **0.399**
2. **Kelly fraction:** f = (0.399 × 0.78 - 0.22) / 0.399 = (0.3112 - 0.22) / 0.399 = **22.9%**
3. **Dollar amount:** On a $1,000 bankroll, full Kelly says bet $229

Note how both examples suggest roughly the same Kelly fraction despite very different prices. This is because Kelly balances edge against odds -- a bigger edge on longer odds produces a similar sizing recommendation as a smaller edge on shorter odds.

## Why Full Kelly Is Too Aggressive

Here is the uncomfortable truth: full Kelly sizing assumes your probability estimate is perfectly accurate. It is not. Nobody's is.

If you estimate 55% probability and the true probability is actually 48%, your edge is not 15 cents -- it is negative. You are betting 22.7% of your bankroll on a losing proposition. A few trades like this and your account takes a hit that takes months to recover from.

Full Kelly also produces extreme variance. Even with accurate probability estimates, full Kelly generates drawdowns of 50% or more with uncomfortable frequency. Mathematically, this is expected -- the formula maximizes the log-growth rate, not the smoothness of the equity curve.

This is not theoretical. Professional traders, hedge funds, and serious sports bettors almost universally use fractional Kelly rather than full Kelly. The growth rate sacrifice is small; the variance reduction is enormous.

> **Calculate it instantly:** Use our [Kelly Criterion Calculator](/tools/kelly-calculator) to find the optimal bet size for any prediction market trade. Enter your bankroll, contract price, probability estimate, and platform -- it shows full, half, and quarter Kelly with growth rate comparisons.

## Fractional Kelly: The Practical Approach

Fractional Kelly means betting a fraction of what the full Kelly formula recommends. The most common fractions are:

| Fraction | Bet Size (% of Full Kelly) | Growth Rate (% of Full Kelly) | Variance | Best For |
|---|---|---|---|---|
| Full Kelly | 100% | 100% | Very high | Theoretical only |
| 3/4 Kelly | 75% | ~94% | High | Aggressive traders with strong models |
| **1/2 Kelly** | **50%** | **~75%** | **Moderate** | **Most traders (recommended)** |
| 1/4 Kelly | 25% | ~50% | Low | Beginners, uncertain estimates |
| 1/8 Kelly | 12.5% | ~28% | Very low | Maximum safety |

The math is elegant: half Kelly achieves roughly 75% of the optimal growth rate while cutting variance roughly in half. You give up a quarter of your growth to get dramatically smoother returns. For most traders, this is an excellent trade.

### The 5% Cap Rule

Regardless of what Kelly says, never risk more than 5% of your bankroll on a single contract. This is a hard cap that protects against model error, black swan events, and the inevitable surprise where your "80% probability" estimate turns out to be 30%.

If full Kelly suggests 30% of your bankroll and you are using half Kelly (15%), that is still above the 5% cap. In this case, the cap overrides Kelly and you bet 5%.

In practice, this cap rarely binds on half Kelly for contracts priced between $0.20 and $0.80 with moderate edges. It mainly prevents disaster on extreme scenarios where Kelly produces an unusually large recommendation.

## Kelly With Multiple Positions

Real portfolios have multiple simultaneous positions, and Kelly needs to be adjusted for this.

The simplest approach: treat each position independently but use a shared bankroll. When you calculate Kelly for position B, use your current bankroll minus capital already committed to position A. This naturally scales down later positions and prevents over-commitment.

A more rigorous approach accounts for correlation between positions. If two of your positions are both weather contracts in the same region, they are likely to win or lose together. Correlated positions should be sized more conservatively because a simultaneous loss has a compounding impact on your bankroll.

The practical rule: if your total portfolio uses more than 20-25% of your bankroll across all positions (using fractional Kelly), you are likely over-concentrated. Either reduce individual position sizes or use the [Portfolio Calculator](/tools/portfolio-calculator) to check your overall exposure and concentration risk.

## Common Kelly Mistakes

### 1. Using the Wrong Odds

The most common implementation error is calculating odds incorrectly. In prediction markets, your odds are NOT simply (1 - price) / price. You must account for fees. On Kalshi, the correct formula is:

**b = ((1 - price) × 0.93) / price**

Forgetting the 0.93 multiplier overstates your odds and leads to oversizing. On a $0.40 contract, the difference is b = 1.50 (wrong) vs b = 1.395 (correct) -- a 7.5% overstatement that compounds into meaningful over-betting across hundreds of trades.

### 2. Applying Kelly to Negative EV Bets

Kelly only works when expected value is positive. If your probability estimate does not exceed the breakeven probability after fees, Kelly returns zero or a negative number -- meaning "do not bet." Some traders override this because they "feel good" about a trade. Do not do this. Kelly is telling you the trade is a loser on average. Listen. Use the [Probability Calculator](/tools/probability-calculator) to verify positive EV before running Kelly.

### 3. Using a Static Bankroll

Kelly fraction is applied to your current bankroll, not your starting bankroll. If you started with $1,000 and are now at $1,400, Kelly should be calculated on $1,400. If you have drawn down to $700, Kelly should use $700. This self-adjusting property is one of Kelly's key strengths -- it automatically sizes you down after losses and up after wins.

### 4. Ignoring Estimation Uncertainty

If you estimate 60% probability with high confidence (say, based on a well-calibrated weather model with thousands of backtested data points), half Kelly is reasonable. If you estimate 60% with low confidence (a gut feeling on a political outcome), quarter Kelly or less is appropriate. Your Kelly fraction should scale with the reliability of your probability estimate.

## Key Takeaways

- **Kelly tells you how much to bet** given your edge, odds, and bankroll. It maximizes long-term growth.
- **Full Kelly is too aggressive** for real trading. Use half Kelly as your default, quarter Kelly for uncertain estimates.
- **Always account for fees** in your odds calculation. Kalshi's 7% fee on profits reduces your net odds.
- **Cap any single position at 5% of bankroll** regardless of what Kelly recommends.
- **Scale Kelly to your confidence.** Strong models deserve half Kelly. Gut feelings deserve quarter Kelly or less.
- **Recalculate as your bankroll changes.** Kelly uses current capital, not starting capital.
- **Never apply Kelly to negative EV trades.** If Kelly says zero, the trade is not worth taking.

The Kelly criterion is not a guarantee of profits. It is a framework for making the mathematically optimal sizing decision given your inputs. Combined with disciplined [edge identification](/blog/prediction-market-strategies-finding-edge-as-a-retail-trader) and rigorous [probability calculation](/blog/how-to-calculate-implied-probability-prediction-markets), it is the closest thing to a formula for long-term success in prediction markets.
