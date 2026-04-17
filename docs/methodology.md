# 方法論

`wiki-character-power-index` は、日本語版Wikipediaの本文だけを根拠に、架空キャラクターの強さ、推定IQ、条件フラグを評価します。

このプロジェクトは、原作データベース、ファンWiki、対戦考察サイト、作品解釈ツールではありません。Wikipedia日本語版に書かれている文章を、ルールベースでランキング化するためのパイプラインです。

## 処理フロー

1. `data/seed_characters.yaml` にキャラクター候補を管理する。
2. `src/resolve_ja_wikipedia.py` でURLを日本語版Wikipediaへ解決する。
3. `src/repair_japanese_sources.py` で日本語表示名と安全な作品/一覧ページフォールバックを整える。
4. `src/sync_seed_characters.py` でseedリストを `data/characters.yaml` に同期する。
5. `src/fetch_wikipedia.py` で `wikipedia_url` の日本語版Wikipedia本文を取得する。
6. `src/extract_character_sections.py` で共有ページからキャラクター名に近い見出し・導入文を切り出す。
7. `src/extract_features.py` で本文を文に分割し、強さに関係する文だけを抽出する。
8. 抽出文を `abilities`、`feats`、`statements` に分類する。
9. `src/scoring.py` で決定的なテキストルールを適用し、根拠文を保存する。
10. `src/condition_flags.py` でUI用の条件フラグを作る。
11. `src/ranking.py` で強さランキングまたは推定IQランキングを出力する。
12. `src/battle.py` で2キャラクターを根拠スコアだけで比較する。
13. `src/export_site_data.py` でGitHub Pages用JSONを出力する。

## データ契約

各キャラクターは次の構造を持ちます。

```yaml
name: string
wikipedia_url: string
media_type: manga | anime | movie | comic
universe: string
description_raw: text
extracted:
  abilities: list[string]
  feats: list[string]
  statements: list[string]
scores:
  attack: int
  defense: int
  speed: int
  abilities: int
  feats: int
  scale: int
score_evidence:
  attack: list[object]
  defense: list[object]
  speed: list[object]
  abilities: list[object]
  feats: list[object]
  scale: list[object]
total_score: int
tier: S | A | B | C
iq_score: int
iq_evidence: list[object]
condition_flags: object
condition_evidence: object
```

`score_evidence` は、スコアを監査できるようにするための拡張フィールドです。ランキング表示では必須です。

`iq_score` は実際のIQではありません。日本語版Wikipedia本文に知性、発明、科学、戦略、探偵能力などの表現がどれだけあるかを測る指標です。

`condition_flags` は、Wikipedia本文の語句一致だけで付与されます。現在は、超能力あり、改造あり、技術/装備、魔法/呪い、武器あり、人間以外、神格、宇宙人、ロボット/AI、格闘、軍人/兵士、リーダー、天才/探偵、変身、不死/再生を扱います。

## 日本語版Wikipediaのみの制約

許可するもの:

- `wikipedia_url` に指定された日本語版Wikipedia本文
- MediaWiki API、REST Summary、REST HTML、通常ページHTMLが返すページタイトル、pageid、revision ID、本文
- このリポジトリ内にある決定的な文字列ルール

許可しないもの:

- 原作漫画、アニメ、映画、コミックの知識
- ファンWikiや外部DB
- 個人的な強さ解釈
- Wikipedia本文に書かれていない実績の推測
- 将来スキーマで明示的に追加されていない別ページからの補強

## 500キャラクターの目標

現在のサンプルデータは500キャラクターです。

- 漫画/アニメ: 209件
- 映画: 144件
- Marvel / DCコミック: 147件

日本語版Wikipediaに単独キャラクターページがない場合、登場人物一覧や作品ページをソースにします。そのため、同じ日本語ページを複数キャラクターが共有する場合があります。どのURLへ解決されたかは `data/ja_wikipedia_resolution_report.yaml` で確認できます。

日本語名の正規化と、無関係な検索結果から作品/一覧ページへ置き換えた件数は `data/source_repair_report.yaml` に記録します。

共有ページは `src/extract_character_sections.py` で再処理します。キャラクター名、日本語ラベル、括弧を外した名前、URLフラグメントを別名として使い、見出しまたはキャラクター導入文に一致した場合だけ `description_raw` を置き換えます。REST HTMLが429で制限された場合は、通常の日本語版WikipediaページHTMLを使います。ページ全体の概要を無理に採用せず、一致しないキャラクターは既存本文を維持します。結果は `data/section_extraction_report.yaml` に記録します。

## 再生成手順

```bash
python src/resolve_ja_wikipedia.py --input data/seed_characters.yaml --output data/seed_characters.yaml --report data/ja_wikipedia_resolution_report.yaml --search-fallback
python src/repair_japanese_sources.py
python src/sync_seed_characters.py --reset-derived
python src/fetch_wikipedia.py --source rest-summary --missing-only --sleep 0
python src/extract_character_sections.py --sleep 1 --retries 0 --report data/section_extraction_report.yaml
python src/extract_features.py
python src/scoring.py
python src/condition_flags.py
python src/export_site_data.py
```

公開サンプルは、安定取得のため最初に `rest-summary` を使用し、その後で共有ページだけキャラクター別セクション抽出を行います。`rest-html` を指定すると日本語版WikipediaのHTML本文をプレーンテキスト化して使えますが、短時間に大量取得するとWikipedia側の429制限を受けるため、`--sleep` と `--save-every` の指定を推奨します。

## 将来拡張

- API: ランキング、検索、比較をHTTP APIで返す。
- Web UI: 条件検索、スコア内訳、根拠文表示を強化する。
- 自動更新: Wikipedia revision IDを保存し、更新差分だけ再取得する。
- 複数ページ対応: キャラクター、装備、映画版などのソースを分けて扱う。
- ルール監査: どのルールがランキングに影響しているかを集計する。
- バトル条件: 超能力あり/なし、改造あり/なし、武器あり/なしなどの条件別比較を追加する。
