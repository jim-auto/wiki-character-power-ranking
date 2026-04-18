# plan.md — 開発ハンドオフ

このドキュメントは、`wiki-character-power-ranking` リポジトリの現状、直近のセッションで行った変更、未解決事項、次に着手すべきタスクをまとめたものです。Codex などの後任エージェントがコンテキストをゼロから把握できるように書いています。

最終更新: 2026-04-18

公開UI: https://jim-auto.github.io/wiki-character-power-ranking/
GitHubリポジトリ: https://github.com/jim-auto/wiki-character-power-ranking

---

## 1. プロジェクト一言

日本語版Wikipediaの本文 **だけ** を根拠に、漫画・アニメ・映画・Marvel/DCのキャラクター501体を採点してランキング化する静的サイト+Pythonパイプライン。

「本当に誰が強いか」を決めるものではなく、「日本語版Wikipediaに強さ・知性・影響範囲がどう書かれているか」を再現可能なルールで数値化する。

### 不変の制約(採点ロジック側)

- 外部知識なし
- 原作知識なし
- ファン解釈なし
- 日本語版Wikipedia本文とメタデータのみ
- すべてのスコアに根拠文と一致ルールを残す
- 画像は日本語版Wikipedia/Wikidata由来のみ。コスプレ等の本人ではない画像は使わない

**例外:** バトル画面の「想像戦闘シーン」は、Wikipedia根拠文 + スコア差を元にしたテンプレ生成の創作テキスト(2026-04-18追加)。「想像・参考」バッジと注釈で原作描写ではないことを明示している。採点には一切影響しない。

---

## 2. ディレクトリ構造

```
data/
  seed_characters.yaml              # 入力のマスター(git管理)
  characters.yaml                   # 派生: 本文+スコア(96MB, gitignore)
  image_fetch_report.yaml           # 画像取得ログ
  openverse_image_report.yaml       # Openverse取得ログ(現在は不採用)
  ja_wikipedia_resolution_report.yaml
  source_repair_report.yaml
  section_extraction_report.yaml

src/
  resolve_ja_wikipedia.py           # seedのURLを日本語版Wikipediaへ解決
  repair_japanese_sources.py        # 無関係な検索フォールバックを修復
  sync_seed_characters.py           # seed → characters.yaml 同期
  fetch_wikipedia.py                # 本文取得(rest-summary / rest-html / action-api)
  extract_character_sections.py     # 共有ページからキャラ別セクション切り出し
  extract_features.py               # 文分割 + 関連文抽出 → abilities/feats/statements
  scoring.py                        # 正規表現ルールで採点 + 明示IQ抽出
  condition_flags.py                # 本文由来の条件フラグ(超能力/武器/etc.)
  collection_tags.py                # ジャンプ漫画/Marvel/DCタグ付け
  fetch_wikipedia_images.py         # pageimages → Wikidata P18 → Commons
  fetch_openverse_images.py         # 【非推奨】コスプレ写真を拾うためUIパイプラインからは外した
  export_site_data.py               # docs/data/characters.json + character-details/*.json 生成
  ranking.py                        # CLIランキング出力
  battle.py                         # CLIバトル比較

docs/
  index.html                        # 静的UI(GitHub Pages公開元)
  app.js                            # フロントエンドロジック
  styles.css                        # CSS
  data/characters.json              # 軽量一覧データ(約3.3MB, git管理)
  data/character-details/*.json     # フル根拠データ(キャラ別分割, git管理)
  methodology.md
  scoring_rules.md

README.md
plan.md                             # このファイル
requirements.txt
```

---

## 3. パイプライン実行順(現状の推奨)

```bash
# 初回 or seed追加時
python src/resolve_ja_wikipedia.py --input data/seed_characters.yaml --output data/seed_characters.yaml --report data/ja_wikipedia_resolution_report.yaml --search-fallback
python src/repair_japanese_sources.py
python src/sync_seed_characters.py --reset-derived

# 本文取得
python src/fetch_wikipedia.py --source rest-html --missing-only --sleep 0.5 --save-every 200 --retries 1

# 前処理 + 採点
python src/extract_character_sections.py --sleep 1 --retries 0 --report data/section_extraction_report.yaml
python src/extract_features.py
python src/scoring.py
python src/condition_flags.py
python src/collection_tags.py

# 画像
python src/fetch_wikipedia_images.py --sleep 0.5 --report data/image_fetch_report.yaml

# 公開JSON
python src/export_site_data.py
```

**注意:**
- `rest-html` の全件取得は501件 × 0.5秒 ≈ 4分。途中で `PermissionError` (Windowsのファイルロック)が出ることがある。その場合は短い `description_raw` だけクリアして `--missing-only` で再開するのが安全。
- `fetch_openverse_images.py` は既定パイプラインから外した(コスプレ写真に振れるため)。レガシーとしてコードは残っている。

---

## 4. 現在のデータスナップショット(2026-04-18)

| 指標 | 件数 |
|------|------|
| 総キャラクター | 501 |
| 単独キャラページに解決済み | 多数(詳細は `data/ja_wikipedia_resolution_report.yaml`) |
| `description_raw` ≥500字 | 482 |
| `description_raw` < 500字(短いが空ではないキャラ別説明) | 19 |
| `description_raw` ≤50字(明らかな抽出不足) | 0 |
| 画像あり(Wikipedia/Wikidata由来のみ) | 232 |
| **明示IQあり(`explicit_iq != null`)** | **15** |
| ジャンプ漫画タグ | 143 |
| Marvelタグ | 105 |
| DCタグ | 76 |

### 明示IQ15名の内訳

- 堂上一郎: 300
- 赤井秀一 / 夜神月 / 鵡飼唯 / ロック・リー / 越前リョーマ / 奈良シカマル / 鬼塚英吉 / ペイン: 200
- 戸愚呂弟: 160
- 石谷由来 / 五条龍也 / 阿久根翔: 150
- マキマ / パワー: 134

---

## 5. 直近セッション(2026-04-18)での変更

コミット済みの変更は以下。最後に今回の未コミット作業を追記している。

1. **Drop Openverse cosplay images from site icons** (f19b590)
   - 55件のOpenverse由来画像(コスプレ写真中心)を `characters.yaml` から除去
   - README からOpenverseステップを削除し、UI画像は Wikipedia/Wikidata のみに限定
   - `fetch_openverse_images.py` 自体は残してあるが既定では呼ばない

2. **Add explicit IQ filter toggle** (d68317c)
   - UI: `<input id="explicit-iq-filter">` を条件フィルタ下に追加
   - state: `state.explicitIqOnly`、URLパラメータ `?explicitIq=1`
   - 当初は該当0件(原因は次項)

3. **Fix explicit IQ regex for Japanese word boundaries** (990585c)
   - **重要な罠:** Pythonの `\b` はUnicode対応で、日本語文字(ひらがな/カタカナ/漢字)は `\w` 扱い。したがって `\bIQ\b` は「能力テストでIQ200を超える」のようなJapanese隣接ケースで両端の `\b` がマッチしない
   - `src/scoring.py` の `EXPLICIT_IQ_PATTERNS` を修正: `(?<![A-Za-z])IQ...(?!\d)`
   - rest-html で501件再取得 → 15件ヒット

4. **Stop tracking data/characters.yaml** (42e6f18)
   - `data/characters.yaml` が96MBに肥大したため `.gitignore` に追加
   - `git rm --cached` で履歴からの追跡停止(ただし過去commitに96MB blobは残存)
   - `.claude/` も `.gitignore` に追加

5. **Add imagined battle scene to battle view** (b0e93de)
   - バトル画面に「想像戦闘シーン」セクションを追加
   - `battleImaginaryScene(a, b)` がテンプレ文を組み立てる(LLMなし)
   - 使用する情報: scale/speed/attack/defense/iq スコア差、condition_flags、先頭の根拠文
   - 「想像・参考」バッジ + 注釈で原作描写ではないことを明示

6. **未コミットの今回作業**
   - バトル画面のA/Bキャラ選択を `input + datalist` から `<select>` に変更し、501件すべてを確実に選択できるようにした
   - `src/extract_character_sections.py` で見出し階層を考慮し、`h2` 配下の `dt` 本文を即終了しないよう修正
   - 「詳しくは...参照」だけの短い候補より、本文量のある同名候補を優先するようにした
   - `トニー・モンタナ` の seed URL を曖昧さ回避ページから `スカーフェイス_(映画)` に修正
   - パイプラインを `fetch_wikipedia.py --missing-only` → `extract_character_sections.py` → `extract_features.py` → `scoring.py` → `condition_flags.py` → `collection_tags.py` → `export_site_data.py` の順で再実行済み
   - `git filter-repo` で `data/characters.yaml` を履歴から除去し、`main` を force push 済み
   - `docs/data/characters.json` を軽量一覧に変更し、フル根拠は `docs/data/character-details/*.json` にキャラ別分割

---

## 6. 既知の未解決事項 / 技術的負債

### 6.1 Git履歴の肥大(対応済み)

2026-04-18の今回作業で、`git filter-repo --path data/characters.yaml --invert-paths --force` を実行し、`main` を force push 済み。`git rev-list --objects --all` に `data/characters.yaml` は出ない。ローカルの `data/characters.yaml` はgitignore対象として残す。

あわせて、GitHub Pagesが読む `docs/data/characters.json` は約52MBから約3.3MBの軽量一覧に変更した。フル根拠データは `docs/data/character-details/*.json` に501ファイルへ分割し、最大ファイルは約1.2MB。

注意: Git LFSはGitHub Pagesで使えないため、`docs/` 配下の公開データには使わない。

### 6.2 短い description_raw の監視(優先度: 低)

2026-04-18の今回作業で、`description_raw` が50字以下の明らかな抽出不足は0件になった。`ライナー・ブラウン`、`アニ・レオンハート`、`レオリオ`、`アイザック＝ネテロ` は見出し階層修正で長い本文を拾えるようになり、`トニー・モンタナ` は正しい映画ページに修正済み。

現在も500字未満の説明は19件あるが、多くはキャラ別節そのものが短いケース。seed追加後や再取得後は、`python -c "import yaml; Loader=getattr(yaml,'CSafeLoader',yaml.SafeLoader); d=yaml.load(open('data/characters.yaml','r',encoding='utf-8'), Loader=Loader); [print(c['name'], len(c.get('description_raw') or ''), c['wikipedia_url']) for c in d['characters'] if 0<len(c.get('description_raw') or '')<=50]"` で明らかな抽出不足がないか確認する。

### 6.3 明示IQの精度(優先度: 中)

現在は最初にマッチした最大値を採用しているだけ。ロケーションによっては誤検出の可能性あり(例: 「IQ100以下」のような否定文脈)。

現状15件は目視で妥当に見えるが、seed追加後にレビュー必要。`src/scoring.py:186 extract_explicit_iq` の近傍を拡張する。

### 6.4 想像戦闘シーンがテンプレ臭い(優先度: 低、将来LLM)

`battleImaginaryScene()` は決定論的な文型組み立てで、同じペアだと常に同じ文になる。ユーザーは「将来的にはLLMを使うけど今は無し」と明言。

LLM導入時の設計:

- フロントエンド → API経由でAnthropic/OpenAI等に本文根拠文+スコアを渡す
- APIキーの取り扱い(GitHub Pages静的サイトでは隠せないので、別途プロキシバックエンドが必要)
- プロンプトで「Wikipedia根拠文の範囲で想像してください」と制約

---

## 7. 次に着手すべきタスク(優先度順)

### 7.1 seedを増やす(継続的)

現在501件。特にジャンプ漫画以外のアニメ・映画キャラクターを追加する余地あり。`data/seed_characters.yaml` にURL追加 → パイプライン再実行。

### 7.2 Wikipedia revision ID の保存と差分更新(優先度: 中)

現在は毎回全件再取得するため、Wikipedia側の429制限に当たりやすい。`description_raw` と一緒に `revision_id` を保存し、差分だけ再取得できると運用が楽になる。`src/fetch_wikipedia.py` の拡張。

### 7.3 条件フィルタとスコアの連動(優先度: 低、要議論)

バトル画面の条件ON/OFFは現状「フラグ照合のみ」で、スコアには反映しない(主観回避のため)。ただしUI上で「武器あり同士だと武器依存キャラが有利」のような直感を反映したい要望が出る可能性。

議論点: 条件による次元別スコア再計算を許可するか? 採点ルールの一貫性を崩すので慎重に。

### 7.4 想像シーンのLLM化(優先度: 未着手、将来)

上記 6.4 参照。

### 7.5 Fandom Wiki 補助ソース化(優先度: 低、要設計)

ユーザーから「Fandom wiki を参考にしてもいいかも」と相談あり。ただし現在の公式スコアは「日本語版Wikipedia本文だけ」を不変条件にしているため、混ぜるなら別レイヤーにする。

推奨案:
- 既存の `total_score` / `iq_score` は日本語版Wikipedia限定のまま維持
- Fandom由来は `supplemental_sources` や `fandom_evidence` として別保存
- UIでは「補助情報」「非公式参考」などのバッジを付け、採点本体とは分離
- 将来、Fandom込みの別モードを作る場合も、Wikipedia-onlyモードを残す

---

## 8. Codex向けガイド: よくある罠

### 8.1 日本語文字の `\w` / `\b` 問題

Python re モジュール(デフォルトUnicode)は日本語文字を `\w` 扱いする。`\bIQ\b` のようなパターンは日本語隣接で動かない。代わりに `(?<![A-Za-z])` / `(?!\d)` のような明示的lookaroundを使う。

### 8.2 Windows のファイルロック

`characters.yaml` の書き込み中に別のプロセス(エディタ、同時読み取り等)が開いていると `temp_path.replace(path)` で `PermissionError WinError 5` が出る。`--save-every` を大きくしてチェックポイント頻度を下げるか、他プロセスを閉じてから実行する。

### 8.3 ファイルエンコーディング

Windows PowerShellのデフォルトはcp932で、日本語を含む出力は文字化けする。デバッグ時は Python スクリプトを `encoding='utf-8'` 明示で開き、ファイルに書き出して確認する。

### 8.4 YAMLファイルサイズ

`data/characters.yaml` は96MB。Read tool の行数制限にかかるため、必要なフィールドだけ `python -c "import yaml; ..."` で抜き出して確認すること。

### 8.5 GitHub Pages の反映遅延

`main` へのpushから公開反映まで数分かかる。即座に見えなくても焦らない。ブラウザ側キャッシュにも注意。

---

## 9. テスト

**現状、自動テストは無い。** スコアリングのルール追加時は手動でサンプルに対する挙動を確認する運用。

将来追加するなら:

- `src/scoring.py` の正規表現マッチングに対するユニットテスト
- `src/extract_features.py` の文分割に対するテスト(日本語の `。` 区切り)
- GitHub Actions で `python -m py_compile src/*.py` 程度はすぐ入れられる

---

## 10. 連絡先 / オーナーシップ

Git user: `jim-auto`
セッション中のペアプロ相手: `rsasaki0109@gmail.com`

作業スタイルのメモ:

- ユーザーは日本語ローマ字で指示を出すことがある(例: 「deploy!」「naganaga to kousin」)
- `/resume` でセッション再開を試みることがある
- `デプロイ` と言われたら `main` にpushする(GitHub Pagesが自動反映)
- 意思決定は短めに、破壊的操作(force-push等)は事前確認

---

以上。Codex が引き継ぐ場合、まず `README.md` → この `plan.md` → `docs/methodology.md` の順で読むと全体像が掴める。不明点は `git log --oneline` と `docs/app.js` 直読が早い。
