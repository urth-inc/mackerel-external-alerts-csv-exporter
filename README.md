# Mackerel External Alerts CSV Exporter
[Mackerel](https://mackerel.io/)の外形監視のアラートをCSVに出力するスクリプト
[Mackerel API](https://mackerel.io/ja/api-docs/)を使用
前月分を取得する

## requirements
- Python >= 3.9

## 使い方
```sh
MACKEREL_API_KEY=<Mackerel API Key> python3 external_alert.py
```
`./output/external_alerts.csv` に外形監視のアラートレポートが出力される。

## 特徴
標準ライブラリのみで実装しているため、Python環境があれば動作する。
