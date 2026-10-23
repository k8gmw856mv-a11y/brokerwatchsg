# BrokerWatch SG

Factual, non-advisory tracker of Singapore broker sign-up offers and published fees. Not financial advice. The site is marked draft.

GitHub Pages serves the `main` branch root at <https://k8gmw856mv-a11y.github.io/brokerwatchsg/>.

## Data

- [`data/brokers.json`](data/brokers.json) — published fees. Top-level `generated`, plus a `checked` date on each field.
- [`data/offers.json`](data/offers.json) — sign-up offers, each with a source URL and `checked` date. `affiliate_link` is null; the site does not publish referral links.
- `index.html` embeds the same records for the fee table, offer countdown, and cost-per-trade calculator. Do not change a fee or offer value in only one of these places.

## Regenerate pages

From the repository root, with Python 3 and no extra packages:

```bash
python3 scripts/build.py
```

The script rewrites:

- `brokers/<id>/index.html` — one page per broker in `data/brokers.json`
- `brokers/index.html`
- `sitemap.xml`, `robots.txt`, and `llms.txt`
- the marked blocks in `index.html` (JSON-LD, FAQ, broker links, data links, and the last-updated date)

It checks that the arrays embedded in `index.html` still match the JSON files, and it exits without writing referral links. Commit the script and the generated files together. Edit fee and offer values only in the JSON and the matching embedded copy, after re-checking the cited source.

The countdown, calculator, and Buttondown form stay in `index.html`. `style.css` is the shared stylesheet.
