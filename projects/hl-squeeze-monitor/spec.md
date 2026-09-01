# Implementation notes

Hyperliquid perpetuals are the immutable universe. A symbol is evaluated only when a conservative direct or explicit alias mapping exists on Binance USDT perpetuals or Bybit USDT linear perpetuals. All funding values are converted to a decimal rate per hour before comparison. The monitor is read-only and contains no order, wallet, or signing code.
