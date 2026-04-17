# wiki-character-power-index

Wikipedia日本語版の記述だけでキャラクターの強さを評価する。

`wiki-character-power-index` は、漫画、アニメ、映画、Marvel / DCコミックのキャラクターを、日本語版Wikipediaに書かれている文章だけを根拠に抽出、採点、ランキング化する小さなPythonプロジェクトです。

公開UI: https://jim-auto.github.io/wiki-character-power-ranking/

## 制約

- 外部知識なし
- 原作知識なし
- ファン解釈なし
- 日本語版Wikipedia本文とメタデータのみを使用
- すべてのスコアに根拠文と一致したルールを残す
- 画像は日本語版Wikipedia由来の表示用サムネイルとWikidata P18のみを使い、採点根拠には使わない

このプロジェクトは「本当に誰が強いか」を決めるものではありません。Wikipedia日本語版の文章に、強さ、能力、実績、知性、影響範囲がどのように書かれているかを、再現可能なルールで数値化するものです。

## リポジトリ構成

```text
/data/
  characters.yaml
  seed_characters.yaml
  ja_wikipedia_resolution_report.yaml
  source_repair_report.yaml
  section_extraction_report.yaml
  image_fetch_report.yaml

/src/
  fetch_wikipedia.py
  fetch_wikipedia_images.py
  extract_character_sections.py
  extract_features.py
  scoring.py
  ranking.py
  battle.py
  sync_seed_characters.py
  resolve_ja_wikipedia.py
  repair_japanese_sources.py
  condition_flags.py
  collection_tags.py
  export_site_data.py

/docs/
  index.html
  styles.css
  app.js
  data/characters.json
  scoring_rules.md
  methodology.md

README.md
requirements.txt
```

## データモデル

```yaml
character:
  name: string
  wikipedia_url: string
  media_type: manga | anime | movie | comic
  universe: string
  collection_tags: list[string]
  description_raw: text
  image_url: string | null
  image_source: string | null
  image_alt: string | null

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
  explicit_iq: int | null
  explicit_iq_evidence: list[object]
  estimated_iq: object
  condition_flags: object
  condition_evidence: object

  versions:
    - label: string
      aliases: list[string]
      source_wikipedia_url: string
      description_raw: text
      extracted: object
      scores: object
      score_evidence: object
      total_score: int
      tier: S | A | B | C
      iq_score: int
      explicit_iq: int | null
      estimated_iq: object
```

`iq_score` は内部名です。UIでは「知性スコア」と表示します。実際のIQではなく、日本語版Wikipedia本文に「天才」「科学者」「戦略」「発明」「探偵」などの知性に関係する表現がどれだけ強く出ているかを示す、根拠文付きの0-10点指標です。
`explicit_iq` は本文に `IQ 200` や `知能指数 180` のような数値が明示されている場合だけ入ります。`estimated_iq` は知性スコアから決定的に作るレンジ目安で、実測IQではありません。

`condition_flags` は、GitHub Pages UIで条件オン/オフ検索をするためのフラグです。超能力あり、改造あり、技術/装備、魔法/呪い、武器あり、人間以外、神格、宇宙人、ロボット/AI、格闘、軍人/兵士、リーダー、天才/探偵、変身、不死/再生を扱います。

`collection_tags` はUIの大分類フィルタ用タグです。現在は `jump_manga`、`marvel`、`dc` を付与します。`image_url` は日本語版Wikipediaの `pageimages` API、または日本語版Wikipediaページに紐づくWikidata P18から取得した表示用サムネイルです。共有ページは作品ロゴや集合画像になりやすいため、画像取得では既定でスキップします。

`versions` はキャラクターの時点別データです。通常キャラと同じ抽出・スコアリングを行い、バトル比較では `A時点` / `B時点` に一致した version のスコアを使用します。最初のサンプルとしてNARUTO系6キャラクターに `中忍試験時点` を追加しています。

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 日本語版Wikipediaへの解決

seedリストのURLを日本語版Wikipediaへ寄せます。Wikidataの日本語版サイトリンクを優先し、必要に応じて日本語版Wikipedia検索にフォールバックします。

```bash
python src/resolve_ja_wikipedia.py \
  --input data/seed_characters.yaml \
  --output data/seed_characters.yaml \
  --report data/ja_wikipedia_resolution_report.yaml \
  --search-fallback
```

単独のキャラクターページが日本語版Wikipediaにない場合は、登場人物一覧や作品ページがソースになることがあります。その場合も `ja.wikipedia.org` の本文だけを使います。

日本語名や誤った検索フォールバックを修復するには、次を実行します。個別ページがないキャラクターは、無関係な検索結果ではなく作品/ユニバースの日本語版Wikipediaページへ寄せます。

```bash
python src/repair_japanese_sources.py
```

一覧ページや作品ページを複数キャラクターが共有している場合は、ページ全体の概要ではなく、キャラクター名の見出しや導入文に近い本文だけを切り出せます。REST HTMLが429で制限された場合は通常の日本語版WikipediaページHTMLにフォールバックします。抽出結果と未一致件数は `data/section_extraction_report.yaml` に記録されます。

```bash
python src/extract_character_sections.py --sleep 1 --retries 0 --report data/section_extraction_report.yaml
```

## データ再生成

```bash
python src/sync_seed_characters.py --reset-derived
python src/fetch_wikipedia.py --source rest-summary --missing-only --sleep 0
python src/extract_character_sections.py --sleep 1 --retries 0 --report data/section_extraction_report.yaml
python src/extract_features.py
python src/scoring.py
python src/condition_flags.py
python src/collection_tags.py
python src/fetch_wikipedia_images.py --sleep 0.5 --report data/image_fetch_report.yaml
python src/export_site_data.py
```

処理内容:

1. seedリストを `data/characters.yaml` に同期する
2. 日本語版Wikipediaから本文を取得する
3. 共有ページの場合はキャラクター名に近いセクションを切り出す
4. 強さに関係する文を抽出する
5. `abilities` / `feats` / `statements` に分類する
6. 強さ、知性スコア、条件フラグをルールベースで付ける
7. ジャンプ漫画、Marvel、DCなどのコレクションタグを付ける
8. 日本語版Wikipediaの表示用サムネイルを取得する
9. GitHub Pages用の `docs/data/characters.json` を出力する

画像取得は採点とは独立しています。`src/fetch_wikipedia_images.py` はまず日本語版Wikipediaの `pageimages` を使い、足りない単独ページだけ日本語版Wikipediaの `pageprops` で紐づくWikidata P18画像へフォールバックします。明らかなロゴやSVGは除外します。サムネイルがないキャラクターはUI側で頭文字プレースホルダーを表示します。

より長い本文を試す場合は、REST HTML本文をプレーンテキスト化するモードも使えます。Wikipedia側の429制限を受けた場合は、`Retry-After` に従って待機するか、`rest-summary` に戻します。

```bash
python src/fetch_wikipedia.py --source rest-html --missing-only --sleep 0.5 --save-every 100
```

## ランキング出力

強さランキング:

```bash
python src/ranking.py --input data/characters.yaml
```

知性スコアランキング:

```bash
python src/ranking.py --ranking-type iq
```

Markdown保存:

```bash
python src/ranking.py --output ranking.md
```

JSON保存:

```bash
python src/ranking.py --format json --output ranking.json
```

## フィルタ

メディア種別:

```bash
python src/ranking.py --media-type manga
```

作品/ユニバース:

```bash
python src/ranking.py --universe MCU
```

スコア範囲:

```bash
python src/ranking.py --min-score 30 --max-score 45
```

特定スコアだけで絞り込み:

```bash
python src/ranking.py --score-key attack --min-score 6
```

知性スコアで絞り込み:

```bash
python src/ranking.py --ranking-type iq --min-score 5
```

GitHub Pages UIでは、条件フィルタをオン/オフできます。URLにも状態が残ります。

```text
?view=power&media=comic&universe=Marvel&conditions=superpower,magic&min=20
```

コレクションフィルタでは、ジャンプ漫画、Marvel、DCなどの大分類で絞り込めます。

```text
?collection=jump_manga
```

## バトル比較

2人のキャラクターを、すでに計算済みのWikipedia根拠スコアで比較します。

```bash
python src/battle.py --a "孫悟空" --b "バットマン"
```

比較モード:

```bash
python src/battle.py --a "アイアンマン（MCU）" --b "バットマン" --mode power
python src/battle.py --a "アイアンマン（MCU）" --b "バットマン" --mode iq
python src/battle.py --a "アイアンマン（MCU）" --b "バットマン" --mode balanced
python src/battle.py --a "日向ネジ" --b "うちはサスケ" --a-stage "中忍試験時点" --b-stage "中忍試験時点"
```

`battle.py` は完全な架空戦闘シミュレーションではありません。性格、弱点、相性、戦場、原作展開は推測せず、本文に出た根拠文とスコア差だけを表示します。
GitHub Pages UIではA/Bのキャラクター名を検索入力から選べます。`A時点` / `B時点` には「中忍試験時点」などの段階ラベルを入れられます。該当キャラクターに `versions` がある場合は時点候補が表示され、その時点のスコアと根拠文で比較します。時点が見つからない場合は通常データで比較し、その旨を表示します。

## 出力例

```text
# Character Power Ranking

## 1. 五条悟 - 12点 / Tier C
- source: https://ja.wikipedia.org/wiki/五条悟
- media_type: manga
- universe: Jujutsu Kaisen
- scores: attack=5, defense=0, speed=0, abilities=4, feats=0, scale=3
- evidence:
  - attack: （日本語版Wikipedia本文から一致した文） [strong expression / +5]
  - abilities: （日本語版Wikipedia本文から一致した文） [technique expression / +4]
```

実際の出力では、各スコアに対して根拠文、一致したルール、加点値が表示されます。

## GitHub Pages

静的UIは `docs/` にあります。GitHub Pagesでは次の設定で公開できます。

```text
Settings > Pages > Build and deployment
Source: Deploy from a branch
Branch: main
Folder: /docs
```

公開URL:

```text
https://jim-auto.github.io/wiki-character-power-ranking/
```

## 初期データ

現在のサンプルデータは501キャラクターです。全レコードの `wikipedia_url` は日本語版Wikipediaを指します。
GitHub Pages用JSONには、ジャンプ漫画143件、Marvel 105件、DC 76件のコレクションタグが含まれます。日本語版Wikipediaの単独ページと、そのページに紐づくWikidata P18から取得できた表示用サムネイルは166件です。

代表例:

- 孫悟空
- うずまきナルト
- アイアンマン（MCU）
- バットマン
- モンキー・D・ルフィ
- サイタマ
- セーラームーン
- ピカチュウ
- エレン・イェーガー
- ダース・ベイダー
- ヨーダ
- ドクター・ストレンジ（MCU）
- ソー（MCU）
- サノス（MCU）
- スーパーマン
- ワンダーウーマン
- スパイダーマン
- ハルク
- レックス・ルーサー

## スコアリング

スコアリングは `src/scoring.py` の正規表現ルールだけで決まります。

- 弱い表現: `熟練`, `訓練`, `格闘`, `剣術` などは低加点
- 強い表現: `最強`, `超人的`, `無敵`, `破壊`, `壊滅` などは高加点
- 戦績表現: `倒す`, `勝利`, `救う`, `守る`, `戦う` などは `feats` に加点
- 影響範囲: `都市`, `国家`, `世界`, `地球`, `宇宙`, `次元` などは `scale` に加点

詳しくは [docs/scoring_rules.md](docs/scoring_rules.md) を参照してください。

## 将来拡張

- API化
- Web UIの検索、フィルタ、比較機能の拡張
- Wikipedia revision IDを使った自動更新
- 複数ページを根拠に持つキャラクター設計
- ルール変更によるランキング差分レポート
- バトルモードの条件指定追加
