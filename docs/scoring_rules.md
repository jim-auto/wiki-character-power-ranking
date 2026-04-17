# Scoring Rules

This project scores characters only from text found in each record's `description_raw` and `extracted` fields. Those fields must come from Wikipedia.

No score may be raised because of outside knowledge, original work familiarity, fan interpretation, power-scaling debates, or unstated assumptions.

## Score Dimensions

Each dimension is scored from 0 to 10. Most scores are the capped sum of deterministic text-rule matches. `scale` uses the highest explicit scope found, so repeated mentions of the same scope do not inflate it. Every match stores the sentence, matched rule, and point value in `score_evidence`.

| Dimension | Meaning |
| --- | --- |
| `attack` | Offensive force, attacks, weapons, destructive language, combat language. |
| `defense` | Durability, armor, shielding, survivability, containment, protection. |
| `speed` | Speed wording, flight, teleportation, fast movement. |
| `abilities` | Named powers, techniques, superhuman traits, special equipment, training, intellect. |
| `feats` | Explicit accomplishments such as defeating, saving, protecting, or fighting opponents. |
| `scale` | Textual scope of influence, such as city, nation, planet, world, universe. |

`total_score` is the sum of the six dimensions, so it ranges from 0 to 60.

## Text-Evidence IQ Score

`iq_score` is a separate 0-10 index for ranking intelligence-related wording. It is not a real IQ estimate and must not be read as a psychological measurement.

It is based only on expressions such as:

| Text type | Example expressions | Typical points |
| --- | --- | --- |
| Genius wording | `genius`, `天才` | 5 |
| Invention/science | `inventor`, `engineer`, `scientist`, `発明`, `科学者` | 4 |
| Strategy/tactics | `strategy`, `tactical`, `戦略`, `戦術` | 4 |
| Detective ability | `detective`, `探偵` | 3 |
| Intellect wording | `intellect`, `intellectual`, `知性`, `知能` | 3 |
| Science/technology | `science and technology`, `technology`, `nanotechnology`, `科学`, `技術` | 3 |

## Tier Thresholds

| Tier | Total score |
| --- | --- |
| S | 42-60 |
| A | 30-41 |
| B | 18-29 |
| C | 0-17 |

## Expression Strength

Weak expressions add low points:

| Text type | Example expressions | Typical points |
| --- | --- | --- |
| Skill/training | `trained`, `martial arts`, `fighting skills`, `熟練`, `訓練` | 2-3 |
| Generic action | `fight`, `battle`, `protect`, `戦う`, `守る` | 2-3 |
| Role label | `ninja`, `忍者` | 2 |

Strong expressions add higher points:

| Text type | Example expressions | Typical points |
| --- | --- | --- |
| Superhuman trait | `superhuman`, `超人的` | 5 |
| Top-strength statement | `mightiest`, `strongest`, `最強` | 5 |
| Destruction | `destroy`, `annihilate`, `破壊` | 5 |
| Invulnerability | `invincible`, `invulnerable`, `無敵` | 7 |
| Universe scale | `universe`, `cosmic`, `dimension`, `宇宙`, `次元` | 9 |

## Scale Rules

Scale is deliberately conservative. The text must explicitly mention the scope.

| Scope expression | Points |
| --- | --- |
| `city`, `都市` | 2 |
| `village`, `村` | 3 |
| `nation`, `country`, `国家`, `国` | 5 |
| `world`, `世界` | 6 |
| `planet`, `Earth`, `惑星`, `地球` | 7 |
| `universe`, `cosmic`, `dimension`, `宇宙`, `次元` | 9 |

## Reproducibility

The scorer is intentionally rule-based:

1. It reads only extracted Wikipedia sentences.
2. It applies regular-expression rules in `src/scoring.py`.
3. It sums matched rule points per dimension, except `scale`.
4. It scores `scale` by the highest explicit scope found.
5. It caps each dimension at 10.
6. It stores all matched evidence.

Changing scores requires changing the text or changing the rule table. There is no hidden model judgment.

## Battle Mode

`src/battle.py` compares two characters by already-computed evidence scores.

Modes:

- `power`: compare `total_score`.
- `iq`: compare `iq_score`.
- `balanced`: compare `total_score + iq_score`.

Battle mode is not a complete fictional fight simulation. It does not infer matchups, weaknesses, tactics, setting, or canon outcomes unless those facts are present in the Wikipedia-derived text and score rules.
