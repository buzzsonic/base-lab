# Market core v1 VPS package

BTC公開市場データ専用の常駐service。既存wallet collectorのtimer、lock、state、保存先を共有しない。

これは配置可能なpackageであり、まだVPSへ配置・起動していない。配置後は最初の24時間をcanaryとし、`design/forward-market-core-v1/quality_gate.md`で判定する。秘密鍵・注文・署名は不要。
