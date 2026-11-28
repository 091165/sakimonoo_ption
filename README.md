# JPX Derivatives Intelligence Dashboard

日経225先物・オプションのデリバティブ市場分析ダッシュボード。

## 概要

JPXのデリバティブ建玉データを可視化するインタラクティブなダッシュボードです。

- 先物建玉残高の前日比
- オプション取引代金・建玉増減
- 建玉分布（バタフライチャート）
- 大口手口（J-NET）
- サポート/レジスタンス分析・予想レンジ

## データの自動収集

`scripts/fetch_jpx.py` がJPXのページ（[オプション理論価格等情報](https://www.jpx.co.jp/markets/derivatives/option-price/index.html) ほか）の一覧データ（`/automation/markets/derivatives/` 配下のJSON）と取引状況ページのリンクを読み取り、次のファイルを `data/` に保存します。

| 種類 | ファイル名 | JPXの公開時刻（目安） |
|---|---|---|
| 理論価格・IV | `oseYYYYMMDDtp.csv` | 当日 16:40頃 |
| 取引状況 | `YYYYMMDD_derivatives_market_data_whole_day.xlsx` | 当日 17:10頃 |
| 取引参加者別取引高（日通し/夜間 × 立会/J-NET） | `YYYYMMDD_volume_by_participant_*.xlsx` | 当日 17:40頃 |
| 建玉残高 | `YYYYMMDDopen_interest.xlsx` | 当日夕方 |
| 参加者別建玉（週次） | `YYYYMMDD_nk225op_oi_by_tp.xlsx` / `YYYYMMDD_indexfut_oi_by_tp.xlsx` | 月曜 15:30頃（前週金曜分） |

毎日の更新は、Claudeの定期タスクが平日 JST 20:00 ごろに GitHub Actions（`.github/workflows/jpx-analysis.yml`）を手動実行（workflow_dispatch）して行います。建玉残高が出るまで待ってから実行し、そのあとClaudeの分析（`data/manual_assessment_YYYYMMDD.md`）を入れて再実行します。
GitHub側の定時実行（平日 JST 23:07）は、実行が漏れた日の予備です（GitHubの定時実行は数時間遅れることがあります）。新しい日付の建玉残高・J-NET取引高・理論価格がそろったとき（または新しい週次ファイルが出たとき）だけサイトを再生成します。
先物ベーシスは、JPXの清算値段（`rbYYYYMMDD.csv`）のラージ先物の期近の清算価格と、その原資産（日経平均）の差です。
手動で `data/` にファイルを `main` へpushする従来の方法もそのまま使えます。

```
python scripts/fetch_jpx.py --datadir data --dry-run   # 取得対象の確認だけ
python scripts/fetch_jpx.py --datadir data --date 20261104
```

## 技術仕様

- **外部JSライブラリ：ゼロ**（React/Recharts不使用）
- 純粋なHTML + CSS + vanilla JavaScript
- 唯一の外部リソース：Google Fonts
- ファイルサイズ：約30KB

## 公開

GitHub Pagesで `index.html` をホスティング。

## ライセンス

本ダッシュボードは市場分析ツールであり、投資助言ではありません。
