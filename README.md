# wiki-character-power-index

Wikipediaの記述だけでキャラクターの強さを評価する。

`wiki-character-power-index` は、漫画、アニメ、映画、Marvel / DCコミックのキャラクターを、Wikipediaに書かれている文章だけを根拠に抽出、スコアリング、ランキング化するための小さなPythonプロジェクトです。

## Core Constraints

- 外部知識なし。
- 原作知識なし。
- ファン解釈なし。
- テキスト根拠のみ。
- すべてのスコアは根拠文とルールを表示できること。

このプロジェクトは「本当に誰が強いか」を決めるものではありません。Wikipedia上の文章表現から、再現可能なルールでスコアを付けるためのシステムです。

## Repository Structure

```text
/data/
  characters.yaml

/src/
  fetch_wikipedia.py
  extract_features.py
  scoring.py
  ranking.py
  battle.py

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

## Data Model

```yaml
character:
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
```

`score_evidence` は各スコアの根拠を表示するための拡張フィールドです。
`iq_score` は実IQではなく、Wikipedia本文に含まれる知性・戦術・科学・探偵能力などの表現を0-10点化した根拠付き指標です。

## Setup

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

## Usage

### 1. Wikipediaページを取得する

```bash
python src/fetch_wikipedia.py --input data/characters.yaml --output data/characters.yaml
```

リード文だけ取得する場合:

```bash
python src/fetch_wikipedia.py --intro-only
```

### 2. 強さ関連の文章を抽出する

```bash
python src/extract_features.py --input data/characters.yaml --output data/characters.yaml
```

抽出カテゴリ:

- `abilities`: 能力、技、装備、訓練、知性。
- `feats`: 戦績、勝利、保護、救出、戦闘。
- `statements`: 強さやスケールに関係する評価、描写。

### 3. テキスト根拠でスコアリングする

```bash
python src/scoring.py --input data/characters.yaml --output data/characters.yaml
```

スコア項目:

- `attack`
- `defense`
- `speed`
- `abilities`
- `feats`
- `scale`

各項目は0-10点です。`total_score` は6項目の合計で、最大60点です。

### 4. ランキングを出力する

```bash
python src/ranking.py --input data/characters.yaml
```

Markdownファイルに保存:

```bash
python src/ranking.py --output ranking.md
```

JSONで出力:

```bash
python src/ranking.py --format json --output ranking.json
```

GitHub Pages用のJSONを更新:

```bash
python src/export_site_data.py
```

推定IQランキング:

```bash
python src/ranking.py --ranking-type iq
```

## Filters

メディア種別:

```bash
python src/ranking.py --media-type manga
```

ユニバース:

```bash
python src/ranking.py --universe MCU
```

スコア範囲:

```bash
python src/ranking.py --min-score 30 --max-score 45
```

特定スコアだけで範囲指定:

```bash
python src/ranking.py --score-key attack --min-score 6
```

推定IQスコアで範囲指定:

```bash
python src/ranking.py --ranking-type iq --min-score 5
```

## Battle Mode

2人のキャラクターを、Wikipedia根拠スコアだけで比較できます。

```bash
python src/battle.py --a "孫悟空" --b "バットマン"
```

モード:

```bash
python src/battle.py --a "アイアンマン" --b "バットマン" --mode power
python src/battle.py --a "アイアンマン" --b "バットマン" --mode iq
python src/battle.py --a "アイアンマン" --b "バットマン" --mode balanced
```

`battle.py` は完全な架空戦闘シミュレーションではありません。相性、弱点、戦場、原作設定は推測せず、データ内のWikipedia根拠文とスコア差だけを表示します。

## GitHub Pages

静的UIは `docs/` にあります。GitHub Pagesでは次の設定で公開できます。

```text
Settings > Pages > Build and deployment
Source: Deploy from a branch
Branch: main
Folder: /docs
```

このリポジトリ名のまま公開する場合、URLは次の形式です。

```text
https://jim-auto.github.io/wiki-character-power-ranking/
```

データ更新後は、次の順で再生成します。

```bash
python src/extract_features.py
python src/scoring.py
python src/export_site_data.py
```

## Output Example

```text
# Character Power Ranking

## 1. 孫悟空 - 40 pts / Tier A
- source: https://en.wikipedia.org/wiki/Goku
- media_type: manga
- universe: Dragon Ball
- scores: attack=9, defense=3, speed=5, abilities=10, feats=6, scale=7
- evidence:
  - attack: Goku is Earth's mightiest warrior... [strong expression: mightiest, +5]
  - defense: Goku is Earth's mightiest warrior... [protection expression, +3]
  - speed: ...teleportation. [teleportation expression, +5]
```

実際の出力では、各スコアに対して根拠文、マッチしたルール、加点値が表示されます。

## Scoring

スコアリングは `src/scoring.py` のルール表だけで決まります。

例:

- 弱い表現: `trained`, `martial arts`, `熟練` は低加点。
- 強い表現: `mightiest`, `superhuman`, `invincible`, `最強`, `無敵` は高加点。
- `defeat`, `protect`, `battle` などの明示的行動は `feats` に加点。
- `city`, `nation`, `planet`, `universe` などの影響範囲は `scale` に加点。

詳しくは [docs/scoring_rules.md](docs/scoring_rules.md) を参照してください。

## Text-Evidence IQ Ranking

強さとは別に、`iq_score` で推定IQランキングを出せます。

対象表現の例:

- `genius`, `intellect`, `detective`
- `scientist`, `inventor`, `engineer`
- `strategy`, `tactical`
- `天才`, `知性`, `科学`, `技術`, `戦略`, `戦術`, `探偵`

これは「実際のIQ」ではありません。Wikipediaに知性関連の表現がどれだけ強く書かれているかを測るランキングです。

## Sample Data

`data/characters.yaml` には20人分のサンプルキャラクターが入っています。

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
- ソー
- レックス・ルーサー

各キャラクターには、Wikipedia URL、メディア種別、ユニバース、根拠文、スコア、tierが含まれます。

## Methodology

詳細な処理方針は [docs/methodology.md](docs/methodology.md) にあります。

処理フロー:

1. Wikipediaページを取得する。
2. 強さに関係する文章を抽出する。
3. `abilities` / `feats` / `statements` に分類する。
4. 文章表現だけでスコアリングする。
5. フィルタ付きランキングとして出力する。

## Future Extensions

- API化。
- Web UIによる検索、フィルタ、ランキング表示。
- Wikipedia revision IDを使った自動更新。
- 複数Wikipediaページを持つキャラクター記録。
- ルール変更によるランキング差分レポート。
- バトルモードのUI化と比較条件の追加。
