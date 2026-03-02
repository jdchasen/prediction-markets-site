---
title: "Kalshi Fees (2026): How Much They're Really Eating From Your Profits"
description: "Complete breakdown of Kalshi's fee structure and how to minimize costs. Real examples showing how fees impact your bottom line."
pubDate: 2026-02-22
category: "kalshi"
tags: ["kalshi", "strategies"]
affiliate: "kalshi"
review:
  itemName: "Kalshi"
  itemType: "Product"
  rating: 4.0
faqs:
  - question: "How much does Kalshi charge per trade?"
    answer: "Kalshi charges $0.02 per contract per side. A round-trip trade (buy and sell) costs $0.04 per contract in total fees. There are no monthly, inactivity, or withdrawal fees."
  - question: "How do I reduce fees on Kalshi?"
    answer: "Use limit orders for better price execution, favor holding to settlement over early exits to avoid the sell-side fee, size up on high-conviction trades, and only trade when your edge exceeds 7-8 cents per contract."
  - question: "How do Kalshi fees compare to Polymarket and PredictIt?"
    answer: "Polymarket charges no trading fees (though you pay gas costs and slippage). PredictIt charges 10% of profits plus 5% on withdrawals. Kalshi sits in the middle at $0.02 per contract per side."
---

If you've traded on [Kalshi](https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21&m=true&utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup) for more than a week, you have probably noticed something uncomfortable: your winning trades don't feel like they pay as much as they should, and your losing trades sting more than expected. The reason is fees. Kalshi's fee structure isn't outrageous by exchange standards, but it's significant enough that it can turn a profitable strategy into a losing one if you're not paying close attention.

We run [automated trading systems](/blog/how-to-use-apis-for-automated-prediction-market-trading) on Kalshi that execute hundreds of contracts per day. Fees are the single biggest line item in our cost structure -- larger than losses on bad trades in many weeks. This article breaks down exactly how Kalshi fees work, how they compound on small-edge trades, and what you can do to keep more of your profits.

## How Kalshi's Fee Structure Works

Kalshi charges fees on every contract you trade, and those fees apply on both sides of a transaction: when you enter a position and when you exit it, whether by selling before expiration or holding to settlement.

As of early 2026, the fee structure works as follows:

### Trading Fees (Entry and Exit)

Every time you buy or sell a contract, Kalshi charges a per-contract fee. The current rate is **$0.02 per contract** (2 cents). This applies whether you're a maker (placing a limit order that adds liquidity to the book) or a taker (placing a market order or limit order that fills immediately against an existing resting order).

This means a round trip -- buying a contract and later selling it or holding to settlement -- costs you **$0.04 in fees per contract** at minimum. That might sound trivial, but let's see how it plays out in practice.

### Settlement Fees

When a contract settles, Kalshi doesn't charge an additional settlement fee beyond the standard trading fee that was already applied when you initially bought the contract. However, if you sell before settlement, you pay the trading fee again on the sell side. The net effect is the same: you pay fees on both legs of the trade.

### No Platform or Account Fees

Kalshi doesn't charge monthly fees, inactivity fees, or deposit/[withdrawal fees](/blog/kalshi-withdrawal) for ACH transfers. The only costs are the per-contract trading fees, which keeps things simple.

## The Real Impact: Dollar Examples

Here is where it gets interesting -- and where many traders underestimate the drag.

### Example 1: A Strong Edge Trade

You identify a [weather market](/blog/how-to-trade-weather-markets-on-kalshi) where you believe there's a 75% chance the event occurs, but the contract is priced at $0.60. That's a solid 15-cent edge.

- You buy 50 contracts at $0.60 each: **$30.00 invested**
- Entry fee: 50 x $0.02 = **$1.00**
- The event occurs, contracts settle at $1.00
- Gross profit: 50 x $0.40 = **$20.00**
- Total fees paid: **$1.00**
- Net profit: **$19.00**
- Fee as percentage of gross profit: **5%**

Not bad. On a trade with a genuine 15-cent edge, fees take a manageable bite. This is the kind of trade you want to be making.

### Example 2: A Thin Edge Trade

Now consider a more common scenario. You think a contract priced at $0.52 should be $0.57 -- a 5-cent edge.

- You buy 50 contracts at $0.52 each: **$26.00 invested**
- Entry fee: 50 x $0.02 = **$1.00**
- You sell before settlement at $0.57 when the price moves your way
- Sell fee: 50 x $0.02 = **$1.00**
- Gross profit: 50 x $0.05 = **$2.50**
- Total fees paid: **$2.00**
- Net profit: **$0.50**
- Fee as percentage of gross profit: **80%**

That 5-cent edge just became a 1-cent net edge after fees. And if the price only moves to $0.55 instead of $0.57, you're actually losing money after fees on a trade where your directional call was correct. Use our [Probability Calculator](/tools/probability-calculator) to see exactly how fees shift your breakeven on any contract.

### Example 3: Rapid Scalping

Some traders try to scalp 2-3 cents on quick price movements. Let's see how that works:

- Buy 100 contracts at $0.50: **$50.00 invested**
- Entry fee: 100 x $0.02 = **$2.00**
- Sell at $0.53
- Sell fee: 100 x $0.02 = **$2.00**
- Gross profit: 100 x $0.03 = **$3.00**
- Total fees paid: **$4.00**
- Net profit: **-$1.00**

You made a correct 3-cent call and still lost money. This is why pure scalping strategies are essentially impossible on Kalshi at the current fee level. The math simply doesn't work for edges under 4 cents if you're exiting before settlement. For strategies that do work, see our guide on [making money in prediction markets](/blog/prediction-markets-making-money).

## How Fees Compound Over Time

The examples above show individual trades, but the real damage shows up in your monthly P&L. Consider a trader making 20 trades per day, averaging 30 contracts per trade:

- Daily contracts traded: 600
- Daily fees: 600 x $0.02 = **$12.00 per day** (entry side only)
- If half are round trips (sell before settlement): add another **$6.00**
- Monthly fee drag (20 trading days): **$240 to $360 per month**

To break even on fees alone, you need to generate $240-$360 per month in gross profit before you've made a single dollar. That's the cost of doing business, and it's why edge sizing matters so much.

## Strategies to Minimize Fee Impact

### 1. Only Trade When Your Edge Exceeds the Fee Hurdle

This is the most important rule. For a round-trip trade (buy then sell), your minimum edge needs to be at least 4 cents per contract just to cover fees. In practice, you want at least a 7-8 cent edge to make the trade worthwhile after accounting for the times your edge estimate is wrong. The [Probability Calculator](/tools/probability-calculator) shows your breakeven probability with fees built in, so you can instantly see whether your estimated edge clears the hurdle.

For trades you intend to hold to settlement, the hurdle is lower since you only pay the entry fee -- but you take on more binary risk by not having an exit strategy.

### 2. Use Limit Orders Whenever Possible

While Kalshi doesn't currently differentiate between maker and taker fees, using limit orders gives you better price execution. Instead of hitting the ask at $0.62, post a bid at $0.59. If it fills, you've just gained 3 extra cents of edge for free, which more than covers one side of fees.

Patience with limit orders is one of the simplest ways to improve your net returns. Markets on Kalshi often have wide spreads, and the midpoint is almost always a better entry than the posted ask.

### 3. Favor Settlement Over Early Exit

Every time you sell a position before settlement, you pay an additional $0.02 per contract. If your model says a trade is good, and the event hasn't resolved yet, think carefully before selling just to lock in a few cents of profit. Sometimes the better play is to let it ride to settlement and avoid the exit fee entirely.

That said, there are absolutely situations where taking profit early is correct -- particularly when your edge has evaporated or the risk-reward has shifted. The point isn't to never sell, but to factor the exit fee into your decision. A 3-cent profit on a sell is really a 1-cent profit after fees. Is that worth it, or would you rather hold for the full payout?

### 4. Size Up on High-Conviction Trades

Fees are a fixed cost per contract, not a percentage. This means they hurt small trades disproportionately. If you have a genuine 15-cent edge, trading 10 contracts versus 50 contracts costs you the same percentage in fees but gives you five times the dollar profit. Concentrating your capital on your best opportunities -- rather than spreading it thin across marginal trades -- is one of the most effective ways to improve net returns. The [Kelly criterion](/blog/kelly-criterion-prediction-markets-guide) provides a mathematical framework for sizing up on high-edge trades.

### 5. Track Your Fee Spend Religiously

Download your transaction history from Kalshi regularly and calculate your total fee expense as a percentage of gross profit. You'll also want these records come [tax season](/blog/kalshi-tax-reporting). If fees are eating more than 15-20% of your gross gains, you're probably trading too many marginal setups. Tighten your filters.

## How Kalshi Fees Compare

For context, [Polymarket](https://polymarket.us/1762?utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup) charges no trading fees on most markets, though you pay blockchain gas costs and potential slippage. PredictIt charges 10% of profits plus 5% on withdrawals, which is dramatically worse. Kalshi's fee structure sits in the middle -- fair for a [CFTC-regulated exchange](/blog/is-kalshi-legal), but high enough to matter.

If you're evaluating [which platform to trade on](/platforms), fees should be a primary consideration. A strategy that is profitable on a zero-fee platform might be underwater on Kalshi, and vice versa.

## The Bottom Line

Kalshi fees are not predatory, but they're not trivial either. At $0.02 per contract per side, they create a meaningful hurdle rate that every trader needs to account for. The traders who consistently profit on Kalshi are not the ones finding the most trades -- they're the ones finding trades with enough edge to comfortably clear the fee bar.

Before you place your next trade, ask yourself: is my expected edge at least 3-4x the fee cost? If the answer is no, that trade is probably not worth making. Discipline around fee-adjusted edge is one of the simplest [strategies that separates profitable traders from everyone else](/blog/prediction-market-strategies-finding-edge-as-a-retail-trader), and it costs you nothing to implement.
