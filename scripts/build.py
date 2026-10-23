#!/usr/bin/env python3
"""Generate BrokerWatch SG broker pages, sitemap, robots.txt, llms.txt, and home SEO blocks.

Reads data/brokers.json and data/offers.json. Does not modify those files or any
fee or offer value. No third-party packages.

    python3 scripts/build.py
"""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://k8gmw856mv-a11y.github.io/brokerwatchsg"
HOME_TITLE = "BrokerWatch SG — broker offers & fees tracker (draft)"
HOME_DESCRIPTION = (
    "Factual tracker of Singapore broker sign-up offers and published "
    "stock-trading fees, each with a source and last-checked date. "
    "Not financial advice. (draft)"
)
FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "viewBox='0 0 16 16'%3E%3Crect width='16' height='16' fill='%23222'/%3E%3C/svg%3E"
)
BUTTONDOWN = {
    "https://buttondown.com/api/emails/embed-subscribe/ethanytchan",
    "https://buttondown.com/ethanytchan",
}
FEE_FIELDS = [
    ("us_commission", "US commission"),
    ("sg_commission", "SG commission"),
    ("hk_commission", "HK commission"),
    ("platform_fee", "Platform fee"),
    ("fx_spread", "FX"),
    ("custody", "Custody"),
    ("min_fee", "Min fee"),
    ("referral_program", "Referral programme"),
]
FOOTER = """<footer>
<p><strong>Disclosure:</strong> No referral or affiliate links are published on this site. The site may in future earn a fee from referral links; any such link will be labelled. Information is factual and general only, not a recommendation or financial advice. Where a table is sorted, including the home-page fee calculator, that order is not a recommendation and is not influenced by payments. Check each broker's official terms before acting. Fees exclude 9% GST unless stated.</p>
</footer>"""
COUNTDOWN_JS = """<script>
function endMs(s){return Date.parse(/^\\d{4}-\\d{2}-\\d{2}$/.test(s)?s+'T23:59:59+08:00':s)}
function sgtDay(ms){return new Date(ms+8*36e5).toISOString().slice(0,10)}
(function(){
  var now=Date.now(), today=sgtDay(now);
  document.querySelectorAll('[data-deadline]').forEach(function(el){
    var deadline=el.getAttribute('data-deadline');
    if(!deadline) return;
    var ms=endMs(deadline);
    var day=deadline.slice(0,10);
    var cd=el.querySelector('.cd');
    if(!cd) return;
    var ended=ms<now;
    if(ended){el.classList.add('ended'); cd.textContent='Ended · ended '+day;}
    else {
      var n=Math.round((Date.parse(sgtDay(ms)+'T00:00:00Z')-Date.parse(today+'T00:00:00Z'))/864e5);
      cd.textContent=(n<=0?'Ends today':(n===1?'1 day left':n+' days left'))+' · ends '+day;
    }
  });
})();
</script>"""


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_docs():
    brokers_path = ROOT / "data" / "brokers.json"
    offers_path = ROOT / "data" / "offers.json"
    brokers_doc = json.loads(brokers_path.read_text(encoding="utf-8"))
    offers_doc = json.loads(offers_path.read_text(encoding="utf-8"))
    brokers = brokers_doc["brokers"]
    offers = offers_doc["offers"]
    ids = []
    for broker in brokers:
        slug = broker["id"]
        if not re.fullmatch(r"[a-z0-9_]+", slug):
            sys.exit(f"broker id is not a safe slug: {slug!r}")
        if slug in ids:
            sys.exit(f"duplicate broker id: {slug}")
        ids.append(slug)
    known = set(ids)
    for offer in offers:
        if offer.get("affiliate_link"):
            sys.exit(
                f"affiliate_link is set on {offer.get('id')}; this build does not publish referral links"
            )
        if offer.get("broker") not in known:
            sys.exit(f"offer {offer.get('id')} references unknown broker {offer.get('broker')}")
        deadline = offer.get("deadline")
        if deadline is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", deadline):
            sys.exit(f"offer {offer.get('id')} has an unrecognised deadline: {deadline}")
    return brokers_doc, offers_doc


def long_date(iso: str) -> str:
    dt = date.fromisoformat(iso[:10])
    return f"{dt.day} {dt.strftime('%B %Y')}"


def month_label(iso: str) -> str:
    dt = date.fromisoformat(iso[:10])
    return dt.strftime("%B %Y")


def generated_dates(brokers_doc, offers_doc) -> tuple[str, str]:
    return brokers_doc["generated"], offers_doc["generated"]


def latest_generated(brokers_doc, offers_doc) -> str:
    return max(generated_dates(brokers_doc, offers_doc))


def checked_span(brokers, offers) -> tuple[str, str]:
    found = []
    for broker in brokers:
        for value in broker.values():
            if isinstance(value, dict) and value.get("checked"):
                found.append(value["checked"])
    for offer in offers:
        if offer.get("checked"):
            found.append(offer["checked"])
    if not found:
        sys.exit("no checked dates in dataset")
    return min(found), max(found)


def json_script(obj) -> str:
    payload = json.dumps(obj, ensure_ascii=False, indent=2)
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return '<script type="application/ld+json">\n' + payload + "\n</script>"


def wrap(name: str, inner: str) -> str:
    return f"<!-- BEGIN generated:{name} -->\n{inner.rstrip()}\n<!-- END generated:{name} -->"


def fill(text: str, name: str, inner: str) -> str:
    pattern = re.compile(
        rf"<!-- BEGIN generated:{re.escape(name)} -->.*?<!-- END generated:{re.escape(name)} -->",
        re.S,
    )
    replacement = wrap(name, inner)
    updated, count = pattern.subn(lambda _match: replacement, text, count=1)
    if count != 1:
        sys.exit(f"missing marker in index.html: {name}")
    return updated


def head_html(title: str, description: str, canonical: str, css: str, jsonld: str) -> str:
    return f"""<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="BrokerWatch SG">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:locale" content="en_SG">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="robots" content="index, follow">
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="{esc(css)}">
<link rel="alternate" type="application/json" title="Broker fees" href="{BASE}/data/brokers.json">
<link rel="alternate" type="application/json" title="Sign-up offers" href="{BASE}/data/offers.json">
{jsonld}
</head>"""


def field_bits(label: str, field: dict | None):
    """Return inline pieces (kind, ...) for one published field."""
    field = field or {}
    value = field.get("value")
    bits = []
    if value is None:
        bits.append(("t", f"No {label} figure is recorded in this dataset."))
    else:
        bits.append(("t", f"The published {label} text is: {value}."))
    bits.append(("t", f" Last checked {field.get('checked') or 'not recorded'}."))
    if field.get("verified_on_official_page"):
        bits.append(("t", " Verified on the official page."))
    else:
        bits.append(("t", " Not verified on the official page in this pass."))
    if field.get("source_url"):
        bits.append(("t", " Source: "))
        bits.append(("a", field["source_url"], field["source_url"]))
        bits.append(("t", "."))
    else:
        bits.append(("t", " No source URL is recorded for this field."))
    if field.get("note"):
        bits.append(("t", f" Note: {field['note']}."))
    return bits


def render_bits(bits) -> tuple[str, str]:
    html_parts = []
    text_parts = []
    for bit in bits:
        kind = bit[0]
        if kind == "t":
            html_parts.append(esc(bit[1]))
            text_parts.append(bit[1])
        elif kind == "a":
            href, label = bit[1], bit[2]
            html_parts.append(f'<a href="{esc(href)}">{esc(label)}</a>')
            text_parts.append(label)
        else:
            sys.exit(f"unknown inline bit {kind}")
    return "".join(html_parts), "".join(text_parts)


def us_commission_faq(broker: dict) -> tuple[str, str, str]:
    name = broker["name"]
    question = f"What is the minimum commission for US stocks at {name}?"
    bits = [
        (
            "t",
            "BrokerWatch SG does not calculate a minimum. It quotes the published fields below. ",
        )
    ]
    bits.extend(field_bits("US-stock commission", broker.get("us_commission")))
    min_fee = broker.get("min_fee") or {}
    if min_fee.get("value") is not None:
        bits.append(("t", " "))
        bits.extend(field_bits("min fee", min_fee))
    platform = broker.get("platform_fee") or {}
    if platform.get("value") is not None:
        bits.append(("t", " "))
        bits.extend(field_bits("platform fee", platform))
    page = f"{BASE}/brokers/{broker['id']}/"
    bits.append(("t", " Broker page: "))
    bits.append(("a", page, page))
    bits.append(("t", ". This is not a recommendation or financial advice."))
    html_answer, text_answer = render_bits(bits)
    return question, f"<p>{html_answer}</p>", text_answer


def offer_bits(offer: dict, broker_name: str):
    bits = [
        ("t", f"{broker_name}: {offer['title']}. "),
        ("t", f"Published deadline: {offer.get('deadline') or 'none'}. "),
    ]
    if offer.get("start"):
        bits.append(("t", f"Published start: {offer['start']}. "))
    bits.append(("t", f"Conditions: {offer.get('conditions') or 'none recorded'}. "))
    if offer.get("note"):
        bits.append(("t", f"Note: {offer['note']}. "))
    if offer.get("source_url"):
        bits.append(("t", "Source: "))
        bits.append(("a", offer["source_url"], offer["source_url"]))
        bits.append(("t", f". Last checked {offer.get('checked') or 'not recorded'}."))
    else:
        bits.append(("t", f"No source URL is recorded. Last checked {offer.get('checked') or 'not recorded'}."))
    page = f"{BASE}/brokers/{offer['broker']}/"
    bits.append(("t", " Broker page: "))
    bits.append(("a", page, page))
    bits.append(("t", "."))
    return bits


def english_join(items: list[str]) -> str:
    if not items:
        return "none"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def build_faqs(brokers, offers, offers_generated: str):
    by_id = {broker["id"]: broker for broker in brokers}
    month = offers_generated[:7]
    label = month_label(offers_generated)
    in_month = []
    no_end = []
    for offer in offers:
        deadline = offer.get("deadline")
        if deadline is None:
            no_end.append(offer)
        elif deadline[:7] == month:
            in_month.append(offer)

    faqs = []

    seen = []
    for offer in in_month:
        if offer["broker"] not in seen:
            seen.append(offer["broker"])
    names = [by_id[broker_id]["name"] for broker_id in seen]
    intro = (
        f"“This month” here means {label}, the month of data/offers.json generated on {offers_generated}. "
        f"These published sign-up offers have a deadline in {label}, listed in dataset order, not as a ranking. "
        f"Brokers with at least one such offer: {english_join(names)}. "
        "The home-page countdown marks an offer ended only after its published deadline. "
        f"Offer file: {BASE}/data/offers.json."
    )
    if not in_month:
        intro = (
            f"“This month” here means {label}, the month of data/offers.json generated on {offers_generated}. "
            f"No published sign-up offer in the dataset has a deadline in {label}."
        )
    bits = [("t", intro)]
    # The file URL is already plain text in the intro, so it is in both renderings.
    intro_html, intro_text = render_bits(bits)
    items_html = []
    item_lines = []
    for offer in in_month:
        item_html, item_text = render_bits(offer_bits(offer, by_id[offer["broker"]]["name"]))
        items_html.append(f"<li>{item_html}</li>")
        item_lines.append(item_text)
    html_answer = f"<p>{intro_html}</p>"
    text_answer = intro_text
    if items_html:
        html_answer += "<ul>" + "".join(items_html) + "</ul>"
        text_answer += "\n" + "\n".join(f"- {line}" for line in item_lines)
    faqs.append(
        (
            f"Which Singapore brokers have sign-up offers ending in {label}?",
            html_answer,
            text_answer,
        )
    )

    no_end_intro = (
        f"As of data/offers.json generated on {offers_generated}, these published offers have no end date "
        "in the dataset. That means the source did not show one when it was checked, not that the offer runs forever."
    )
    no_items_html = []
    no_lines = []
    for offer in no_end:
        item_html, item_text = render_bits(offer_bits(offer, by_id[offer["broker"]]["name"]))
        no_items_html.append(f"<li>{item_html}</li>")
        no_lines.append(item_text)
    if no_end:
        no_html = f"<p>{esc(no_end_intro)}</p><ul>{''.join(no_items_html)}</ul>"
        no_text = no_end_intro + "\n" + "\n".join(f"- {line}" for line in no_lines)
    else:
        no_html = f"<p>{esc(no_end_intro)} None are recorded without a deadline.</p>"
        no_text = no_end_intro + " None are recorded without a deadline."
    faqs.append(("Which published sign-up offers have no end date?", no_html, no_text))

    for broker in brokers:
        faqs.append(us_commission_faq(broker))

    advice_q = "Does BrokerWatch SG recommend a broker or publish referral links?"
    advice_text = (
        "No. The site records published Singapore broker fees and sign-up offers with source links and last-checked dates. "
        "It does not recommend or rank a broker, and it is not financial advice. "
        "No referral or affiliate links are published. The site may in future earn a fee from a referral link; if one is added it will be labelled. "
        "The site is marked draft. Check each broker's official terms before acting. "
        f"Data files: {BASE}/data/brokers.json and {BASE}/data/offers.json."
    )
    advice_html = f"<p>{esc(advice_text)}</p>"
    faqs.append((advice_q, advice_html, advice_text))
    return faqs


def faq_html(faqs) -> str:
    parts = []
    for question, answer_html, _text in faqs:
        parts.append(f"<article><h3>{esc(question)}</h3>{answer_html}</article>")
    return "\n".join(parts)


def faq_entities(faqs):
    return [
        {
            "@type": "Question",
            "name": question,
            "acceptedAnswer": {"@type": "Answer", "text": text},
        }
        for question, _html, text in faqs
    ]


def home_jsonld(brokers, offers, brokers_doc, offers_doc, faqs) -> str:
    brokers_generated, offers_generated = generated_dates(brokers_doc, offers_doc)
    modified = latest_generated(brokers_doc, offers_doc)
    first_checked, last_checked = checked_span(brokers, offers)
    by_id = {broker["id"]: broker["name"] for broker in brokers}
    same_generated = brokers_generated == offers_generated
    generated_sentence = (
        f"Both files were generated on {brokers_generated}."
        if same_generated
        else f"brokers.json was generated on {brokers_generated}; offers.json was generated on {offers_generated}."
    )
    graph = [
        {
            "@type": "WebSite",
            "@id": BASE + "/#website",
            "name": "BrokerWatch SG",
            "url": BASE + "/",
            "description": HOME_DESCRIPTION,
            "inLanguage": "en",
            "creativeWorkStatus": "Draft",
            "publisher": {"@id": BASE + "/#organization"},
        },
        {
            "@type": "Organization",
            "@id": BASE + "/#organization",
            "name": "BrokerWatch SG",
            "url": BASE + "/",
            "description": "Publishes BrokerWatch SG, a factual tracker of Singapore broker fees and sign-up offers.",
        },
        {
            "@type": "Dataset",
            "@id": BASE + "/#dataset",
            "name": "Singapore broker sign-up offers and published fees",
            "description": (
                "Factual figures for Singapore broker stock-trading fees and sign-up offers. "
                "Each figure has a source URL where one was found, and a last-checked date. "
                f"{generated_sentence} Last-checked dates in this release run from {first_checked} to {last_checked}. "
                "Not financial advice."
            ),
            "url": BASE + "/",
            "dateModified": modified,
            "temporalCoverage": f"{first_checked}/{last_checked}",
            "inLanguage": "en",
            "isAccessibleForFree": True,
            "creativeWorkStatus": "Draft",
            "creator": {"@id": BASE + "/#organization"},
            "distribution": [
                {
                    "@type": "DataDownload",
                    "name": "Broker fees",
                    "encodingFormat": "application/json",
                    "contentUrl": BASE + "/data/brokers.json",
                },
                {
                    "@type": "DataDownload",
                    "name": "Sign-up offers",
                    "encodingFormat": "application/json",
                    "contentUrl": BASE + "/data/offers.json",
                },
            ],
        },
        {
            "@type": "ItemList",
            "@id": BASE + "/#offers",
            "name": "Singapore broker sign-up offers",
            "description": (
                f"Offers in dataset order. offers.json generated {offers_generated}. "
                "Not a ranking."
            ),
            "numberOfItems": len(offers),
            "itemListOrder": "https://schema.org/ItemListUnordered",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index,
                    "name": offer["title"],
                    "url": f"{BASE}/brokers/{offer['broker']}/",
                    "description": (
                        f"{by_id.get(offer['broker'], offer['broker'])}. "
                        f"Published deadline: {offer.get('deadline') or 'none'}. "
                        f"Last checked {offer.get('checked')}. "
                        f"Source: {offer.get('source_url') or 'none recorded'}."
                    ),
                }
                for index, offer in enumerate(offers, start=1)
            ],
        },
        {
            "@type": "ItemList",
            "@id": BASE + "/#fees",
            "name": "Published Singapore broker fee records",
            "description": (
                f"Fee records in dataset order. brokers.json generated {brokers_generated}. "
                f"Last-checked dates run from {first_checked} to {last_checked}. Not a ranking."
            ),
            "numberOfItems": len(brokers),
            "itemListOrder": "https://schema.org/ItemListUnordered",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index,
                    "name": broker["name"],
                    "url": f"{BASE}/brokers/{broker['id']}/",
                    "description": (
                        "Published US-stock commission: "
                        f"{(broker.get('us_commission') or {}).get('value') or 'not recorded'}. "
                        "Last checked "
                        f"{(broker.get('us_commission') or {}).get('checked') or 'not recorded'}."
                    ),
                }
                for index, broker in enumerate(brokers, start=1)
            ],
        },
        {
            "@type": "FAQPage",
            "@id": BASE + "/#faq",
            "url": BASE + "/#faq",
            "isPartOf": {"@id": BASE + "/#website"},
            "mainEntity": faq_entities(faqs),
        },
    ]
    return json_script({"@context": "https://schema.org", "@graph": graph})


def broker_index_html(brokers) -> str:
    items = [
        f'<li><a href="brokers/{esc(broker["id"])}/">{esc(broker["name"])}</a></li>'
        for broker in brokers
    ]
    return "<ul class=\"broker-index\">\n" + "\n".join(items) + "\n</ul>"


def data_links_html(brokers_doc, offers_doc) -> str:
    return f"""<ul>
<li><a href="data/brokers.json">data/brokers.json</a> — published fees, generated {esc(brokers_doc["generated"])}</li>
<li><a href="data/offers.json">data/offers.json</a> — sign-up offers, generated {esc(offers_doc["generated"])}</li>
<li><a href="llms.txt">llms.txt</a> — short site summary for answer engines</li>
<li><a href="sitemap.xml">sitemap.xml</a></li>
</ul>"""


def patch_script(script: str) -> str:
    old_name = "${c[0]=='name'?b.name:cell(b[c[0]])}"
    new_name = '${c[0]==\'name\'?`<a href="brokers/${b.id}/">${b.name}</a>`:cell(b[c[0]])}'
    old_broker = "<small>(${x.broker})</small>"
    new_broker = '<small>(<a href="brokers/${x.broker}/">${(B.find(b=>b.id===x.broker)||{}).name||x.broker}</a>)</small>'
    if script.count(old_name) != 1 or script.count(old_broker) != 1:
        sys.exit("home page script did not contain the expected name and broker placeholders")
    script = script.replace(old_name, new_name, 1).replace(old_broker, new_broker, 1)
    required = [
        "function endMs(s){return Date.parse(/^\\d{4}-\\d{2}-\\d{2}$/.test(s)?s+'T23:59:59+08:00':s)}",
        "function sgtDay(ms){return new Date(ms+8*36e5).toISOString().slice(0,10)}",
        "function fee(c,sh,px){if(!c)return null;",
        "https://buttondown.com/api/emails/embed-subscribe/ethanytchan",
        "fees();calc();offers();",
    ]
    for snippet in required:
        if snippet not in script and snippet not in (ROOT / "index.html").read_text(encoding="utf-8"):
            # form URL lives outside the script; checked against the page later
            if snippet.startswith("https://"):
                continue
            sys.exit("refusing to rewrite index.html; countdown or calculator snippet missing")
    return script


def convert_legacy(page: str) -> str:
    script_match = re.search(r"<script>(.*)</script>", page, re.S)
    form_match = re.search(r"<form\b.*?</form>", page, re.S)
    if not script_match or not form_match:
        sys.exit("legacy index.html is missing its script or newsletter form")
    script = patch_script(script_match.group(1))
    form = form_match.group(0)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{HOME_TITLE}</title>
<meta name="description" content="{esc(HOME_DESCRIPTION)}">
<link rel="canonical" href="{BASE}/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="BrokerWatch SG">
<meta property="og:title" content="{esc(HOME_TITLE)}">
<meta property="og:description" content="{esc(HOME_DESCRIPTION)}">
<meta property="og:url" content="{BASE}/">
<meta property="og:locale" content="en_SG">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(HOME_TITLE)}">
<meta name="twitter:description" content="{esc(HOME_DESCRIPTION)}">
<meta name="robots" content="index, follow">
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="style.css">
<link rel="alternate" type="application/json" title="Broker fees" href="{BASE}/data/brokers.json">
<link rel="alternate" type="application/json" title="Sign-up offers" href="{BASE}/data/offers.json">
{wrap("jsonld", "")}
</head>
<body>
<h1>BrokerWatch SG <small>draft · data checked {wrap("checked", "")}</small></h1>
<p class="updated"><strong>Last updated:</strong> {wrap("updated", "")}</p>
<p>Facts only: Singapore broker sign-up offers and published fees, each with its source. Not financial advice.</p>
<h2>Brokers</h2>
<p>One page per broker, in dataset order. Not a ranking.</p>
{wrap("broker-index", "")}
<h2>Offers (soonest deadline first)</h2>
<div id="offers"></div>
<h2>Cost-per-trade calculator</h2>
<p class="calc-controls">Market <select id="mk"><option value="us">US (USD)</option><option value="sg">SG (SGD)</option></select> Shares <input id="sh" value="100" size="6"> Price <input id="px" value="50" size="6"> <small>Broker commission + platform only; excludes GST, exchange/regulatory fees, FX.</small></p>
<div class="table-wrap"><table id="calc"></table></div>
<h2>Fee table <small>(click headers to sort; <span class="nv">orange</span> = not verified on official page)</small></h2>
<p class="scroll-hint">On a small screen, swipe the fee table sideways to see every column. The broker name stays pinned.</p>
<div class="table-wrap table-wide"><table id="fees"></table></div>
<h2 id="faq">FAQ</h2>
<p>Answers are assembled from the JSON files linked below. They quote published figures and name the check date. They are not recommendations.</p>
<div class="faq">
{wrap("faq", "")}
</div>
<h2>Data</h2>
{wrap("data-links", "")}
<h2>Weekly "what changed" newsletter</h2>
{form}
<noscript><p>The offer countdown, fee table, and calculator on this page need JavaScript. The FAQ, broker pages, and JSON files above are static.</p></noscript>
{FOOTER}
<script>{script}</script>
</body>
</html>
<!-- deploy -->
"""


def assert_embedded_matches(page: str, brokers_doc, offers_doc) -> None:
    start = page.find("const B=")
    if start < 0:
        sys.exit("embedded broker array missing from index.html")
    start += len("const B=")
    mid = page.find(",O=", start)
    end = page.find(";\nconst cell", mid)
    if mid < 0 or end < 0:
        sys.exit("could not locate embedded offer array")
    embedded_brokers = json.loads(page[start:mid])
    embedded_offers = json.loads(page[mid + 3 : end])
    if embedded_brokers != brokers_doc["brokers"]:
        sys.exit("embedded brokers in index.html do not match data/brokers.json")
    if embedded_offers != offers_doc["offers"]:
        sys.exit("embedded offers in index.html do not match data/offers.json")


def assert_home_intact(page: str) -> None:
    required = [
        "function endMs(s){return Date.parse(/^\\d{4}-\\d{2}-\\d{2}$/.test(s)?s+'T23:59:59+08:00':s)}",
        "function sgtDay(ms){return new Date(ms+8*36e5).toISOString().slice(0,10)}",
        "function fee(c,sh,px){if(!c)return null;",
        "function sortBy(col){sk=col;dir=-dir;fees()}",
        "fees();calc();offers();",
        'action="https://buttondown.com/api/emails/embed-subscribe/ethanytchan"',
        "window.open('https://buttondown.com/ethanytchan','popupwindow')",
        'name="email"',
        'name="embed"',
        "(draft)",
        "draft · data checked",
        'id="offers"',
        'id="calc"',
        'id="fees"',
        'id="mk"',
        'id="sh"',
        'id="px"',
    ]
    for snippet in required:
        if snippet not in page:
            sys.exit(f"home page lost required snippet: {snippet}")


def fee_block(broker: dict) -> str:
    blocks = []
    for key, label in FEE_FIELDS:
        field = broker.get(key) or {}
        value = field.get("value")
        figure = '<span class="null">Not recorded in this dataset</span>' if value is None else esc(value)
        if value is not None and not field.get("verified_on_official_page"):
            figure = f'<span class="nv">{figure}</span>'
        verified = "Verified on the official page." if field.get("verified_on_official_page") else "Not verified on the official page in this pass."
        source = "No source URL is recorded."
        if field.get("source_url"):
            source = f'Source: <a href="{esc(field["source_url"])}">{esc(field["source_url"])}</a>.'
        note = f"<p class=\"note\">Note: {esc(field['note'])}</p>" if field.get("note") else ""
        blocks.append(
            "<section class=\"fee\">"
            f"<h3>{esc(label)}</h3>"
            f"<p class=\"figure\">{figure}</p>"
            f"<p class=\"meta\">Last checked {esc(field.get('checked') or 'not recorded')}. {verified} {source}</p>"
            f"{note}"
            "</section>"
        )
    if broker.get("notes"):
        blocks.append(f"<section class=\"fee\"><h3>Note recorded on the fee row</h3><p>{esc(broker['notes'])}</p></section>")
    return "\n".join(blocks)


def offer_cards(broker_id: str, offers: list) -> str:
    matched = [offer for offer in offers if offer.get("broker") == broker_id]
    matched.sort(key=lambda offer: (offer.get("deadline") is None, offer.get("deadline") or ""))
    if not matched:
        return "<p>No sign-up offer is recorded for this broker in the current dataset.</p>"
    cards = []
    for offer in matched:
        deadline = offer.get("deadline")
        attr = f' data-deadline="{esc(deadline)}"' if deadline else ""
        if deadline:
            status = f"Published deadline: {deadline}"
        else:
            status = "No end date published"
        start = f"<p>Published start: {esc(offer['start'])}</p>" if offer.get("start") else ""
        note = f"<p>Note: {esc(offer['note'])}</p>" if offer.get("note") else ""
        source = "No source URL is recorded."
        if offer.get("source_url"):
            source = f'Source: <a href="{esc(offer["source_url"])}">{esc(offer["source_url"])}</a>.'
        cards.append(
            f"<div class=\"card\"{attr}>"
            f"<p><strong>{esc(offer['title'])}</strong></p>"
            f"<p class=\"cd\">{esc(status)}</p>"
            f"{start}"
            f"<p>Conditions: {esc(offer.get('conditions') or 'none recorded')}</p>"
            f"{note}"
            f"<p>{source} Last checked {esc(offer.get('checked') or 'not recorded')}.</p>"
            "</div>"
        )
    script = COUNTDOWN_JS if any(offer.get("deadline") for offer in matched) else ""
    return "\n".join(cards) + "\n" + script


def page_document(title: str, description: str, canonical: str, css: str, jsonld: str, body: str) -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n"
        + head_html(title, description, canonical, css, jsonld)
        + "\n<body>\n"
        + body
        + "\n"
        + FOOTER
        + "\n</body>\n</html>\n"
    )


def write_broker_pages(brokers, offers, brokers_doc, offers_doc) -> list[str]:
    modified = latest_generated(brokers_doc, offers_doc)
    directory = ROOT / "brokers"
    keep = {broker["id"] for broker in brokers}
    if directory.exists():
        for child in directory.iterdir():
            if child.is_dir() and child.name not in keep:
                shutil.rmtree(child)
    paths = []
    index_items = []
    for broker in brokers:
        slug = broker["id"]
        canonical = f"{BASE}/brokers/{slug}/"
        title = f"{broker['name']} fees and sign-up offers — BrokerWatch SG (draft)"
        description = (
            f"Published stock-trading fees and sign-up offers for {broker['name']}, "
            "with source links and last-checked dates. Facts only, not financial advice. (draft)"
        )
        us = (broker.get("us_commission") or {}).get("value")
        checked = (broker.get("us_commission") or {}).get("checked")
        index_items.append(
            "<li>"
            f"<a href=\"{esc(slug)}/\">{esc(broker['name'])}</a> — "
            f"published US-stock commission: {esc(us) if us is not None else 'not recorded'}"
            f" (last checked {esc(checked or 'not recorded')})."
            "</li>"
        )
        others = "".join(
            f"<li><a href=\"../{esc(other['id'])}/\">{esc(other['name'])}</a></li>"
            for other in brokers
            if other["id"] != slug
        )
        offer_count = sum(1 for offer in offers if offer.get("broker") == slug)
        jsonld = json_script(
            {
                "@context": "https://schema.org",
                "@graph": [
                    {
                        "@type": "WebPage",
                        "name": title,
                        "url": canonical,
                        "description": description,
                        "dateModified": modified,
                        "isPartOf": {"@type": "WebSite", "name": "BrokerWatch SG", "url": BASE + "/"},
                        "about": {"@type": "Thing", "name": broker["name"]},
                        "creativeWorkStatus": "Draft",
                    },
                    {
                        "@type": "BreadcrumbList",
                        "itemListElement": [
                            {
                                "@type": "ListItem",
                                "position": 1,
                                "name": "BrokerWatch SG",
                                "item": BASE + "/",
                            },
                            {
                                "@type": "ListItem",
                                "position": 2,
                                "name": "Brokers",
                                "item": BASE + "/brokers/",
                            },
                            {
                                "@type": "ListItem",
                                "position": 3,
                                "name": broker["name"],
                                "item": canonical,
                            },
                        ],
                    },
                    {
                        "@type": "ItemList",
                        "name": f"Sign-up offers recorded for {broker['name']}",
                        "numberOfItems": offer_count,
                        "itemListOrder": "https://schema.org/ItemListUnordered",
                        "itemListElement": [
                            {
                                "@type": "ListItem",
                                "position": index,
                                "name": offer["title"],
                                "url": canonical,
                                "description": (
                                    f"Published deadline: {offer.get('deadline') or 'none'}. "
                                    f"Last checked {offer.get('checked')}. "
                                    f"Source: {offer.get('source_url') or 'none recorded'}."
                                ),
                            }
                            for index, offer in enumerate(
                                [offer for offer in offers if offer.get("broker") == slug],
                                start=1,
                            )
                        ],
                    },
                ],
            }
        )
        body = f"""<!-- Generated by scripts/build.py. Do not edit by hand. -->
<p class="crumb"><a href="../../">BrokerWatch SG</a> / <a href="../">Brokers</a> / {esc(broker['name'])}</p>
<h1>{esc(broker['name'])} <small>draft</small></h1>
<p class="updated"><strong>Last updated:</strong> <time datetime="{esc(modified)}">{esc(long_date(modified))}</time></p>
<p>Published fees and sign-up offers for {esc(broker['name'])}, copied from the cited sources. Dataset generated {esc(modified)}. Not a recommendation or financial advice. Orange text was not verified on the official page in that pass.</p>
<h2>Fees</h2>
{fee_block(broker)}
<h2>Sign-up offers</h2>
<p>Ordered by published deadline. The countdown uses the same end-of-day rule as the home page.</p>
{offer_cards(slug, offers)}
<h2>Other brokers</h2>
<ul class="broker-index">
{others}
</ul>
<p><a href="../../data/brokers.json">data/brokers.json</a> · <a href="../../data/offers.json">data/offers.json</a> · <a href="../../llms.txt">llms.txt</a></p>
"""
        target = directory / slug / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            page_document(title, description, canonical, "../../style.css", jsonld, body),
            encoding="utf-8",
        )
        paths.append(f"brokers/{slug}/")

    index_title = "Broker fees and offers index — BrokerWatch SG (draft)"
    index_description = (
        "Index of Singapore brokers tracked by BrokerWatch SG, in dataset order, "
        "with links to each broker's published fees and sign-up offers. Not a ranking or financial advice. (draft)"
    )
    index_jsonld = json_script(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": index_title,
                    "url": BASE + "/brokers/",
                    "description": index_description,
                    "dateModified": modified,
                    "isPartOf": {"@type": "WebSite", "name": "BrokerWatch SG", "url": BASE + "/"},
                    "creativeWorkStatus": "Draft",
                },
                {
                    "@type": "ItemList",
                    "name": "Tracked Singapore brokers",
                    "numberOfItems": len(brokers),
                    "itemListOrder": "https://schema.org/ItemListUnordered",
                    "itemListElement": [
                        {
                            "@type": "ListItem",
                            "position": index,
                            "name": broker["name"],
                            "url": f"{BASE}/brokers/{broker['id']}/",
                        }
                        for index, broker in enumerate(brokers, start=1)
                    ],
                },
            ],
        }
    )
    index_body = f"""<!-- Generated by scripts/build.py. Do not edit by hand. -->
<p class="crumb"><a href="../">BrokerWatch SG</a> / Brokers</p>
<h1>Brokers <small>draft</small></h1>
<p class="updated"><strong>Last updated:</strong> <time datetime="{esc(modified)}">{esc(long_date(modified))}</time></p>
<p>Listed in dataset order. This is not a ranking or a recommendation.</p>
<ul>
{''.join(index_items)}
</ul>
<p><a href="../data/brokers.json">data/brokers.json</a> · <a href="../data/offers.json">data/offers.json</a></p>
"""
    (directory / "index.html").write_text(
        page_document(
            index_title,
            index_description,
            BASE + "/brokers/",
            "../style.css",
            index_jsonld,
            index_body,
        ),
        encoding="utf-8",
    )
    return ["brokers/"] + paths


def write_sitemap(paths: list[str], modified: str) -> None:
    urls = [BASE + "/"] + [BASE + "/" + path for path in paths]
    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in urls:
        body.append("  <url>")
        body.append(f"    <loc>{esc(url)}</loc>")
        body.append(f"    <lastmod>{esc(modified)}</lastmod>")
        body.append("  </url>")
    body.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(body) + "\n", encoding="utf-8")


def write_robots() -> None:
    (ROOT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: "
        + BASE
        + "/sitemap.xml\n",
        encoding="utf-8",
    )


def write_llms(brokers, brokers_doc, offers_doc) -> None:
    brokers_generated, offers_generated = generated_dates(brokers_doc, offers_doc)
    lines = [
        "# BrokerWatch SG",
        "",
        "> Factual, non-advisory tracker of Singapore broker sign-up offers and published stock-trading fees. "
        "Each figure keeps the source URL that was found and a last-checked date. The site is marked (draft). "
        "It is not financial advice. No referral or affiliate links are published. The site may in future earn a fee from a labelled referral link.",
        "",
        "Pages are static HTML on GitHub Pages. The interactive fee table, offer countdown, and cost-per-trade calculator run in the browser from a copy of the JSON embedded in the home page. "
        "Per-broker pages are generated by `python3 scripts/build.py` and quote the same JSON.",
        "",
        "## Data endpoints",
        "",
        f"- [Broker fees]({BASE}/data/brokers.json): object with `generated` ({brokers_generated}) and `brokers`. "
        "Each broker has published commission, platform, FX, custody, min-fee, and referral-programme fields. "
        "A field's `value` is null when nothing was recorded. `verified_on_official_page` false means that pass did not confirm the figure on the official page. "
        "`calc` is only the home-page calculator's simplified commission-plus-platform model, not a published price.",
        f"- [Sign-up offers]({BASE}/data/offers.json): object with `generated` ({offers_generated}) and `offers`. "
        "Each offer has `title`, `start`, `deadline`, `conditions`, `source_url`, `checked`, and `affiliate_link`. "
        "`affiliate_link` is null for every offer. Do not invent a referral URL.",
        "",
        "## Update cadence",
        "",
        "Manual. There is no automatic refresh. "
        f"`data/brokers.json` was generated on {brokers_generated} and `data/offers.json` was generated on {offers_generated}. "
        "Every fee field and every offer has its own `checked` date; use that date, not the page fetch date. "
        "After either JSON file changes, run `python3 scripts/build.py` from the repository root and commit the generated pages. "
        "The home page has a weekly Buttondown signup for a “what changed” note. The form does not change the figures.",
        "",
        "## Pages",
        "",
        f"- [Home]({BASE}/): offer countdown, fee table, cost-per-trade calculator, and FAQ.",
        f"- [Broker index]({BASE}/brokers/): every tracked broker, in dataset order, not ranked.",
    ]
    for broker in brokers:
        us = (broker.get("us_commission") or {}).get("value") or "US commission not recorded"
        lines.append(
            f"- [{broker['name']}]({BASE}/brokers/{broker['id']}/): published fees and recorded sign-up offers. US commission text: {us}."
        )
    lines.extend(
        [
            "",
            "## Optional",
            "",
            f"- [Sitemap]({BASE}/sitemap.xml)",
            f"- [robots.txt]({BASE}/robots.txt)",
            f"- [FAQ]({BASE}/#faq)",
            "",
            "## Disclaimer",
            "",
            "Figures are copied from the cited broker or aggregator pages. Orange text on the site was not verified on the official page in that pass. "
            "Nothing on the site is a recommendation, solicitation, or financial advice. "
            "Fees exclude 9% GST unless the cited source says otherwise. Check the broker's current terms before acting.",
            "",
        ]
    )
    (ROOT / "llms.txt").write_text("\n".join(lines), encoding="utf-8")


def allowed_urls(brokers_doc, offers_doc) -> set[str]:
    raw = json.dumps(brokers_doc) + "\n" + json.dumps(offers_doc)
    found = set(re.findall(r"https?://[^\s\"'\\<>]+", raw))
    found |= BUTTONDOWN
    found.add("https://schema.org")
    return found


def audit_links(allowed: set[str]) -> None:
    files = [ROOT / "index.html", ROOT / "llms.txt", ROOT / "robots.txt", ROOT / "sitemap.xml"]
    files.extend((ROOT / "brokers").rglob("*.html"))
    hrefs = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        hrefs.extend(html.unescape(href) for href in re.findall(r'href="([^"]+)"', text))
        hrefs.extend(re.findall(r"\((https?://[^)\s]+)\)", text))
        hrefs.extend(re.findall(r"^Sitemap:\s*(\S+)", text, re.M))
    for href in hrefs:
        if href.startswith("data:"):
            continue
        if href.startswith("http://") or href.startswith("https://"):
            bare = href.split("#")[0]
            if bare.startswith(BASE + "/") or bare == BASE or bare.rstrip("/") == BASE:
                continue
            if bare not in allowed and bare.rstrip("/") not in {item.rstrip("/") for item in allowed}:
                sys.exit(f"unexpected URL in generated site: {href}")
            continue
        if "${" in href:
            continue
        if href.startswith("//") or href.lower().startswith("javascript:"):
            sys.exit(f"refusing link: {href}")
        if not re.fullmatch(r"(?:\./|\.\./|#|[A-Za-z0-9_./#?-])*", href):
            sys.exit(f"unexpected relative link: {href}")


def parse_jsonld(page: str) -> list:
    blocks = re.findall(
        r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
        page,
        re.S,
    )
    if not blocks:
        sys.exit("JSON-LD block missing")
    return [json.loads(block) for block in blocks]


def main() -> None:
    brokers_doc, offers_doc = load_docs()
    brokers = brokers_doc["brokers"]
    offers = offers_doc["offers"]
    index_path = ROOT / "index.html"
    page = index_path.read_text(encoding="utf-8")
    if "BEGIN generated:faq" not in page:
        page = convert_legacy(page)
    modified = latest_generated(brokers_doc, offers_doc)
    faqs = build_faqs(brokers, offers, offers_doc["generated"])
    page = fill(page, "jsonld", home_jsonld(brokers, offers, brokers_doc, offers_doc, faqs))
    page = fill(page, "checked", esc(offers_doc["generated"] if offers_doc["generated"] == brokers_doc["generated"] else modified))
    page = fill(page, "updated", f'<time datetime="{esc(modified)}">{esc(long_date(modified))}</time>')
    page = fill(page, "broker-index", broker_index_html(brokers))
    page = fill(page, "faq", faq_html(faqs))
    page = fill(page, "data-links", data_links_html(brokers_doc, offers_doc))
    assert_embedded_matches(page, brokers_doc, offers_doc)
    assert_home_intact(page)
    for _question, _html, text in faqs:
        json.dumps(text)
    index_path.write_text(page, encoding="utf-8")
    paths = write_broker_pages(brokers, offers, brokers_doc, offers_doc)
    write_sitemap(paths, modified)
    write_robots()
    write_llms(brokers, brokers_doc, offers_doc)
    audit_links(allowed_urls(brokers_doc, offers_doc))
    parsed = parse_jsonld(page)
    faq_nodes = [node for node in parsed[0]["@graph"] if node["@type"] == "FAQPage"]
    if len(faq_nodes[0]["mainEntity"]) != len(faqs):
        sys.exit("FAQPage JSON-LD does not match the visible FAQ count")
    visible_questions = re.findall(r"<h3>(.*?)</h3>", page)
    ld_questions = [item["name"] for item in faq_nodes[0]["mainEntity"]]
    if visible_questions != ld_questions:
        sys.exit("visible FAQ questions do not match FAQPage JSON-LD")
    for path in (ROOT / "brokers").rglob("*.html"):
        parse_jsonld(path.read_text(encoding="utf-8"))
    print(f"generated {len(paths)} sitemap paths; FAQ entries: {len(faqs)}; last updated {modified}")


if __name__ == "__main__":
    main()
