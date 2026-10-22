"""Offline SSG: JPCOAR XML -> HTML, browser search and downloadable metadata."""
import argparse
import copy
import csv
import html
import json
import shutil
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from .metadata import JPCOAR, LOCAL, local, namespace, preferred, read_records, parse_xml, safe_url

ROOT = Path(__file__).resolve().parents[1]
FACETS = ("subjects", "creators", "types", "languages", "access", "content_types")
WORDS = {
    "en": dict(collection="RESOURCE COLLECTION", search="Search the collection", query="Keywords",
               hint="Search titles, descriptions, names and other metadata in any language. Separate words with spaces to match all of them.",
               content_types="Contained material type (original metadata)", subjects="Subject", creators="Creator / provider", types="Resource type", languages="Resource language", access="Access rights",
               all="All", reset="Clear filters", results="Resources", found="{visible} of {total} resources",
               details="View details", visit="Visit resource", overview="Description", metadata="All metadata",
               alternate="Other titles", people="Creators and publishers", links="Resource links", back="Back to collection",
               empty="No resources match your search.", previous="Previous", next="Next", page="Page {page} of {pages}",
               download="Download data", source="Source", snapshot="Data snapshot", rights="Data and reuse",
               no_description="No description is included in this record.", untitled="Untitled resource",
               no_link="No usable external link is included in this record.", skip="Skip to resources",
               noscript="JavaScript is disabled. All resources and detail pages remain available; search and filters require JavaScript.",
               xml="JPCOAR XML", original="Experimental catalogue XML", csv="CSV", json="JSON", missing="Not specified"),
    "ja": dict(collection="リソースコレクション", search="リソースを探す", query="キーワード",
               hint="名称・説明・提供元などのメタデータを、言語を問わず検索します。空白で区切ると、すべての語を含む項目を表示します。",
               content_types="収録資料タイプ（元データ）", subjects="主題", creators="作成者・提供元", types="資源タイプ", languages="資料の言語", access="アクセス権",
               all="すべて", reset="絞り込みを解除", results="リソース一覧", found="全{total}件中 {visible}件",
               details="詳細を見る", visit="公開サイトへ", overview="説明", metadata="すべてのメタデータ",
               alternate="別の名称", people="作成者・出版者", links="リソースのリンク", back="一覧へ戻る",
               empty="条件に一致するリソースがありません。", previous="前へ", next="次へ", page="{pages}ページ中 {page}ページ",
               download="データのダウンロード", source="出典", snapshot="データ保存日", rights="データと利用について",
               no_description="この項目には説明が登録されていません。", untitled="名称未登録のリソース",
               no_link="この項目には利用可能な外部リンクが登録されていません。", skip="リソース一覧へ移動",
               noscript="JavaScriptが無効です。全項目の閲覧と詳細ページは利用できますが、検索・絞り込みにはJavaScriptが必要です。",
               xml="JPCOAR XML", original="実験用カタログXML", csv="CSV", json="JSON", missing="記載なし"),
}


def esc(value):
    return html.escape(str(value), quote=True)


def localized(config, key, lang, fallback=""):
    value = config.get(key, {})
    return value.get(lang, value.get("en", fallback)) if isinstance(value, dict) else str(value)


def names(values, lang):
    chosen = [v["value"] for v in values if v["lang"].lower().split("-")[0] == lang]
    if not chosen:
        chosen = [v["value"] for v in values if not v["lang"]] or [v["value"] for v in values]
    return list(dict.fromkeys(chosen))


def display_title(record, lang):
    # Japanese alternative titles often accompany an untagged English dc:title.
    matching = [v for v in record["titles"] + record["alternatives"] if v["lang"].lower().split("-")[0] == lang]
    return preferred(matching or record["titles"], lang) or WORDS[lang]["untitled"]


def facet_values(record, field, lang):
    if field == "creators":
        return names(record["creators"] or record["publishers"], lang)
    return list(dict.fromkeys(v["value"] for v in record[field]))


def language_root(lang, config):
    return "" if lang == config["default_language"] else lang + "/"


def language_links(lang, config, record_id=None):
    depth = 2 if record_id else 0
    prefix = "../" * (depth + (lang != config["default_language"]))
    links = []
    for other in config["languages"]:
        target = language_root(other, config) + (f"records/{record_id}/index.html" if record_id else "index.html")
        label = {"en": "English", "ja": "日本語"}[other]
        if other == lang:
            links.append(f'<span aria-current="page" lang="{other}">{label}</span>')
        else:
            links.append(f'<a href="{prefix}{target}" lang="{other}" hreflang="{other}" data-language>{label}</a>')
    return "".join(links)


def footer(config, lang, prefix):
    w = WORDS[lang]
    source = config.get("source", {})
    url = safe_url(source.get("url", ""))
    source_name = esc(source.get("name", ""))
    source_html = f'<a href="{esc(url)}">{source_name}</a>' if url else source_name
    license = config.get("license", {})
    license_url = safe_url(license.get("url", ""))
    license_html = f'<a href="{esc(license_url)}">{esc(license.get("name", ""))}</a>' if license_url else esc(license.get("name", ""))
    downloads = "".join(f'<a href="{prefix}experimental/{filename}" download>{w[label]}</a>' for filename, label in
                        [("jpcoar.xml", "xml"), ("records.csv", "csv"), ("records.json", "json"), ("catalogue.xml", "original")])
    original = ""
    if config.get("original_input"):
        label = "Original XML distribution (unmodified)" if lang == "en" else "元のXMLの提供（変更なし）"
        original = f'<div><h2>{label}</h2><a href="{prefix}original/index.html">{label}</a></div>'
    experiment = "Experimental SSG data (modified derivative)" if lang == "en" else "実験的SSG用データ（加工版）"
    date = f'<span>{w["snapshot"]}: {esc(source["date"])}</span>' if source.get("date") else ""
    attribution = f'<p>{w["source"]}: {source_html} {date}</p>' if source_name or date else ""
    related_links = []
    for item in config.get("related_sites", []):
        related_url = safe_url(item.get("url", ""))
        if related_url:
            label = localized(item, "title", lang, related_url)
            related_links.append(f'<a href="{esc(related_url)}">{esc(label)}</a>')
    related_title = "Related websites" if lang == "en" else "関連ウェブサイト"
    related = f'<div class="related-sites"><h2>{related_title}</h2><nav aria-label="{related_title}">{" · ".join(related_links)}</nav></div>' if related_links else ""
    return f'''<footer>{original}<div><h2>{experiment}</h2><nav class="downloads" aria-label="{w['download']}">{downloads}</nav></div>
<div class="rights"><h2>{w['rights']}</h2><p>{esc(localized(config, 'license', lang))} {license_html}</p>{attribution}</div>{related}</footer>'''


def shell(config, lang, title, body, prefix, record_id=None, scripts=""):
    site_title = localized(config, "title", lang, "JPCOAR Catalogue")
    home = "../../index.html" if record_id else "index.html"
    return f'''<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(localized(config, 'description', lang))}">
<link rel="stylesheet" href="{prefix}assets/style.css"><meta name="color-scheme" content="light"></head>
<body><a class="skip" href="#main">{WORDS[lang]['skip']}</a>
<header class="site-header"><a class="brand" href="{home}"><span class="brand-mark" aria-hidden="true">R</span><span>{esc(site_title)}</span></a>
<nav class="languages" aria-label="Language">{language_links(lang, config, record_id)}</nav></header>
{body}{footer(config, lang, prefix)}{scripts}</body></html>'''


def render_index(records, config, lang):
    w = WORDS[lang]
    prefix = "./" if lang == config["default_language"] else "../"
    facets, search_records = [], []
    for field in config["facets"]:
        counts = Counter(v for r in records for v in facet_values(r, field, lang))
        if not counts:
            continue
        options = "".join(f'<option value="{esc(v)}">{esc(v)} ({count})</option>' for v, count in sorted(counts.items(), key=lambda p: p[0].casefold()))
        facets.append(f'<label class="facet">{w[field]}<select name="{field}" id="{field}"><option value="">{w["all"]}</option>{options}</select></label>')
    cards = []
    for index, r in enumerate(records):
        title = display_title(r, lang)
        description = preferred(r["descriptions"], lang)
        providers = " · ".join(names(r["creators"] or r["publishers"], lang))
        alternate = [v["value"] for v in r["titles"] + r["alternatives"] if v["value"] != title]
        alternate_html = f'<p class="alternate">{esc(" · ".join(dict.fromkeys(alternate)))}</p>' if alternate else ""
        tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in facet_values(r, "subjects", lang)[:3])
        external = f'<a class="external" href="{esc(r["links"][0])}" target="_blank" rel="noopener noreferrer">{w["visit"]} ↗</a>' if r["links"] else ""
        cards.append(f'''<article class="resource" data-index="{index}"><div class="resource-heading"><span class="number">{index + 1:03d}</span>
<div><h3><a href="records/{r['id']}/index.html">{esc(title)}</a></h3>{alternate_html}<p class="provider">{esc(providers)}</p></div></div>
<p class="summary">{esc(description or w['no_description'])}</p><div class="resource-bottom"><div class="tags">{tags}</div>{external}</div></article>''')
        search_records.append({"search": r["search"], **{field: facet_values(r, field, lang) for field in config["facets"]}})
    payload = json.dumps({"records": search_records, "pageSize": config["page_size"], "words": w}, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("&", "\\u0026")
    notice = localized(config, "notice", lang)
    notice_text = esc(notice)
    notice_link_text = localized(config, "notice_original_link", lang)
    if config.get("original_input") and notice_link_text and notice_link_text in notice:
        label = esc(notice_link_text)
        filename = esc(Path(config["original_input"]).name)
        notice_text = notice_text.replace(label, f'<a href="{prefix}original/{filename}" download>{label}</a>', 1)
    notice_html = f'<aside class="notice">{notice_text}</aside>' if notice else ""
    body = f'''<main id="main"><section class="hero"><p class="eyebrow">{w['collection']}</p><div class="hero-row"><h1>{esc(localized(config, 'title', lang, 'JPCOAR Catalogue'))}</h1>
<div class="total"><strong>{len(records)}</strong><span>{w['results']}</span></div></div><p class="intro">{esc(localized(config, 'description', lang))}</p>{notice_html}</section>
<section class="finder" aria-labelledby="finder-title"><h2 id="finder-title">{w['search']}</h2>
<form id="search-form" method="get"><div class="query-row"><label for="q">{w['query']}</label><div class="query-controls"><input id="q" name="q" type="search" autocomplete="off" placeholder="{esc(w['query'])}" aria-describedby="search-help"><button type="submit">{w['search']}</button></div></div>
<p class="hint" id="search-help">{w['hint']}</p><div class="facets">{''.join(facets)}</div><button type="button" id="reset" class="text-button">{w['reset']}</button></form></section>
<section class="results" aria-labelledby="results-title"><div class="results-heading"><h2 id="results-title">{w['results']}</h2><p id="count" role="status" aria-live="polite">{w['found'].format(visible=len(records), total=len(records))}</p></div>
<noscript><p class="notice">{w['noscript']}</p></noscript><p id="empty" class="empty" hidden>{w['empty']}</p><div id="resources">{''.join(cards)}</div>
<nav id="pagination" class="pagination" aria-label="{w['results']}" hidden><button id="previous" type="button">← {w['previous']}</button><span id="page-status"></span><button id="next" type="button">{w['next']} →</button></nav></section></main>'''
    scripts = f'<script type="application/json" id="search-data">{payload}</script><script src="{prefix}assets/search.js" defer></script>'
    return shell(config, lang, localized(config, "title", lang, "JPCOAR Catalogue"), body, prefix, scripts=scripts)


def render_detail(record, config, lang):
    w = WORDS[lang]
    prefix = "../../" if lang == config["default_language"] else "../../../"
    title = display_title(record, lang)
    alternatives = list(dict.fromkeys(v["value"] for v in record["titles"] + record["alternatives"] if v["value"] != title))
    alternate_html = f'<p class="detail-alternate">{esc(" · ".join(alternatives))}</p>' if alternatives else ""
    descriptions = record["descriptions"]
    primary = preferred(descriptions, lang)
    description_html = f'<p class="description">{esc(primary or w["no_description"])}</p>'
    others = [v for v in descriptions if v["value"] != primary]
    if others:
        description_html += '<details class="other-descriptions"><summary>' + ("Other descriptions" if lang == "en" else "別言語・その他の説明") + '</summary>' + ''.join(f'<p class="description" lang="{esc(v["lang"])}">{esc(v["value"])}</p>' for v in others) + '</details>'
    links = ''.join(f'<li><a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(url)} ↗</a></li>' for url in record["links"])
    link_html = f'<ul class="detail-links">{links}</ul>' if links else f'<p>{w["no_link"]}</p>'
    rows = []
    for f in record["fields"]:
        attributes = " · ".join(f"{k}: {v}" for k, v in f["attributes"].items())
        rows.append(f'<tr><th scope="row">{esc(f["name"])}<small>{esc(attributes)}</small></th><td>{esc(f["value"])}</td></tr>')
    body = f'''<main id="main" class="detail"><a class="back" href="../../index.html">← {w['back']}</a><p class="eyebrow">{w['collection']}</p>
<h1>{esc(title)}</h1>{alternate_html}<p class="provider">{esc(' · '.join(names(record['creators'] + record['publishers'], lang)))}</p>
<section><h2>{w['overview']}</h2>{description_html}</section><section><h2>{w['links']}</h2>{link_html}</section>
<section><h2>{w['metadata']}</h2><div class="metadata-table"><table><tbody>{''.join(rows)}</tbody></table></div></section></main>'''
    return shell(config, lang, title + " | " + localized(config, "title", lang, "JPCOAR Catalogue"), body, prefix, record["id"],
                 scripts=f'<script src="{prefix}assets/search.js" defer></script>')


def csv_safe(value):
    # Spreadsheet software must not execute a title or description as a formula.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def write_data(output, input_path, records, config, report):
    data = output / "experimental"
    data.mkdir()
    shutil.copyfile(input_path, data / "catalogue.xml")
    root, _ = parse_xml(input_path.read_bytes(), config.get("repair_html_entities", False))
    collection = ET.Element("ListRecords")
    # Match the reader: skip metadata belonging to OAI deleted records.
    parents = {c: p for p in root.iter() for c in p}
    for n in root.iter():
        if local(n.tag) != "jpcoar" or namespace(n.tag) not in JPCOAR:
            continue
        p = parents.get(n)
        while p is not None and local(p.tag) != "record":
            p = parents.get(p)
        if p is not None and any(local(h.tag) == "header" and h.get("status") == "deleted" for h in p):
            continue
        metadata = ET.SubElement(ET.SubElement(collection, "record"), "metadata")
        exported = copy.deepcopy(n)
        legacy = [e.text for e in p if e.tag == "{" + LOCAL + "}contentType" and e.text] if p is not None else []
        if legacy:
            note = ET.Element("{https://schema.datacite.org/meta/kernel-4/}description", {"descriptionType": "Other"})
            note.text = "Contained material types (from original dc:type metadata): " + "; ".join(legacy)
            # description precedes publisher, date, language and type in JPCOAR.
            earlier = {"title", "alternative", "creator", "contributor", "accessRights", "rights", "rightsHolder", "subject", "description"}
            position = next((i for i, child in enumerate(exported) if local(child.tag) not in earlier), len(exported))
            exported.insert(position, note)
        metadata.append(exported)
    ET.ElementTree(collection).write(data / "jpcoar.xml", encoding="utf-8", xml_declaration=True)
    (data / "records.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (data / "records.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        fields = ("titles", "alternatives", "descriptions", "creators", "publishers", "subjects", "types", "content_types", "languages", "access", "identifiers")
        writer.writerow(["id", "source_id", *fields])
        for r in records:
            writer.writerow([r["id"], csv_safe(r["source_id"]), *[csv_safe(" | ".join(v["value"] for v in r[f])) for f in fields]])
    (data / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(config_path, output):
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    config.setdefault("default_language", "en")
    config.setdefault("languages", [config["default_language"]])
    config.setdefault("facets", list(FACETS))
    config.setdefault("page_size", 20)
    if not config["languages"] or len(set(config["languages"])) != len(config["languages"]) or any(l not in WORDS for l in config["languages"]) or config["default_language"] not in config["languages"]:
        raise ValueError("languages must be a unique nonempty subset of en/ja including default_language")
    if any(f not in FACETS for f in config["facets"]) or len(set(config["facets"])) != len(config["facets"]):
        raise ValueError(f"facets must be unique entries from {FACETS}")
    if not isinstance(config["page_size"], int) or not 1 <= config["page_size"] <= 200:
        raise ValueError("page_size must be between 1 and 200")
    input_path = (config_path.parent / config["input"]).resolve()
    original_path = (config_path.parent / config["original_input"]).resolve() if config.get("original_input") else None
    protected = (ROOT, config_path, input_path) + ((original_path,) if original_path else ())
    if any(p.is_relative_to(output) for p in protected) or output.is_relative_to(ROOT / "assets") or output.is_relative_to(ROOT / "jpcoar_ssg"):
        raise ValueError("Output would overwrite source files")
    if output.exists() and (not output.is_dir() or not (output / ".jpcoar-ssg").is_file()):
        raise ValueError("Refusing to replace an existing output without a .jpcoar-ssg marker")
    records, report = read_records(input_path, config.get("repair_html_entities", False))
    report["source_file"] = input_path.name
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".jpcoar-build-", dir=output.parent) as temporary:
        stage = Path(temporary) / "site"
        stage.mkdir()
        shutil.copytree(ROOT / "assets", stage / "assets")
        for lang in config["languages"]:
            directory = stage / language_root(lang, config)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "index.html").write_text(render_index(records, config, lang), encoding="utf-8")
            for record in records:
                detail = directory / "records" / record["id"]
                detail.mkdir(parents=True)
                (detail / "index.html").write_text(render_detail(record, config, lang), encoding="utf-8")
        if original_path:
            original = stage / "original"
            original.mkdir()
            shutil.copyfile(original_path, original / original_path.name)
            (original / "index.html").write_text(f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>元のXML / Original XML</title><link rel="stylesheet" href="../assets/style.css"></head><body><main id="main"><h1>元のXML / Original XML</h1><p>元サイトから取得したXMLを、内容を変更せずに提供しています。実験的な静的検索サイトおよび加工版XMLとは別の配布物です。元データに含まれる不整合もそのまま残しています。</p><p lang="en">This is the original XML as provided, unchanged, including any source inconsistencies. It is distributed separately from the experimental static catalogue and its modified XML.</p><p><a download href="{esc(original_path.name)}">{esc(original_path.name)}</a></p><p>Resource Links in the Resource Guide by NIHU DH — <a href="https://creativecommons.org/publicdomain/zero/1.0/">CC0 1.0</a></p><p>一括利用の際は本ガイドへの謝辞・出典表記をいただけますと幸いです（任意）。Acknowledgment of the Resource Guide would be appreciated when using the collection as a whole.</p><p><a href="../index.html">実験的SSG / Experimental catalogue</a></p></main></body></html>''', encoding="utf-8")
        write_data(stage, input_path, records, config, report)
        (stage / ".nojekyll").touch()
        (stage / ".jpcoar-ssg").write_text("Generated output; safe to replace.\n", encoding="utf-8")
        if output.exists():
            # Roll back if the final rename fails. Validation/rendering already finished.
            backup = Path(temporary) / "previous"
            output.rename(backup)
            try:
                stage.rename(output)
            except OSError:
                backup.rename(output)
                raise
        else:
            stage.rename(output)
    print(f"Built {len(records)} records in {', '.join(config['languages'])} -> {output}")
    if report["html_entity_repairs"]:
        print("Compatibility repairs:", json.dumps(report["html_entity_repairs"]))
    for warning in report["warnings"]:
        print("Warning:", warning)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "site.toml")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    try:
        build(args.config, args.output)
    except (ValueError, KeyError, OSError, UnicodeError) as error:
        parser.exit(1, f"Build failed: {error}\n")
