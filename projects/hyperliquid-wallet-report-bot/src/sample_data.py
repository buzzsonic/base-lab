SAMPLE_SNAPSHOT = {
    "state": {
        "time": 1782136333004,
        "withdrawable": "2.334946",
        "marginSummary": {
            "accountValue": "85.071669",
            "totalNtlPos": "248.210169",
            "totalMarginUsed": "82.736723",
        },
        "assetPositions": [
            {
                "position": {
                    "coin": "RESOLV",
                    "szi": "11131",
                    "entryPx": "0.022053",
                    "unrealizedPnl": "2.737095",
                    "returnOnEquity": "0.0334508582",
                    "leverage": {"type": "cross", "value": 3},
                    "liquidationPx": "0.0175874764",
                    "marginUsed": "82.736723",
                    "positionValue": "248.210169",
                }
            }
        ],
    },
    "mids": {"RESOLV": 0.022279, "TNSR": 0.03982, "HYPE": 67.79},
    "orders": [],
    "fills": [],
}


SAMPLE_FILLS = [
    {"coin": "HYPE", "dir": "Open Long", "px": "70.822", "sz": "23.68", "closedPnl": "0", "fee": "1.080029", "time": 1781997783422},
    {"coin": "HYPE", "dir": "Close Long", "px": "68.591", "sz": "23.68", "closedPnl": "-52.83008", "fee": "1.513784", "time": 1782028423209},
    {"coin": "NEAR", "dir": "Open Long", "px": "2.222", "sz": "502.4", "closedPnl": "0", "fee": "0.718917", "time": 1782028461483},
    {"coin": "NEAR", "dir": "Close Long", "px": "2.2162", "sz": "502.4", "closedPnl": "-2.91392", "fee": "1.037705", "time": 1782029782909},
    {"coin": "HYPE", "dir": "Open Short", "px": "67.7719246264", "sz": "15.39", "closedPnl": "0", "fee": "0.972079", "time": 1782029816653},
    {"coin": "TNSR", "dir": "Open Short", "px": "0.04697", "sz": "6664.6", "closedPnl": "0", "fee": "0.045076", "time": 1782051996907},
    {"coin": "TNSR", "dir": "Close Short", "px": "0.03992", "sz": "3265.7", "closedPnl": "23.023185", "fee": "0.121501", "time": 1782128094455},
    {"coin": "TNSR", "dir": "Close Short", "px": "0.03982", "sz": "3398.9", "closedPnl": "24.300395", "fee": "0.126139", "time": 1782128900748},
    {"coin": "RESOLV", "dir": "Open Short", "px": "0.0235191544", "sz": "17767", "closedPnl": "0", "fee": "0.389447", "time": 1782131090522},
    {"coin": "RESOLV", "dir": "Short > Long", "px": "0.024638", "sz": "32328", "closedPnl": "-19.881273", "fee": "0.742334", "time": 1782131485034},
    {"coin": "RESOLV", "dir": "Close Long", "px": "0.022085", "sz": "14561", "closedPnl": "-37.174233", "fee": "0.299711", "time": 1782134894017},
    {"coin": "RESOLV", "dir": "Open Long", "px": "0.0220531016", "sz": "11131", "closedPnl": "0", "fee": "0.228779", "time": 1782135418711},
]

