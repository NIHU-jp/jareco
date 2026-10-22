"""Read JPCOAR 1.0/2.0, independently of namespace prefixes and wrappers."""
import hashlib
import html.entities
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from urllib.parse import urlsplit

JPCOAR = {f"https://github.com/JPCOAR/schema/blob/master/{v}/" for v in ("1.0", "2.0")}
DC = "http://purl.org/dc/elements/1.1/"
DCT = "http://purl.org/dc/terms/"
DATACITE = {f"{scheme}://schema.datacite.org/meta/kernel-{v}/" for scheme in ("http", "https") for v in ("3", "4")}
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
LOCAL = "urn:jpcoar-static-catalogue:1"
OAI = "http://www.openarchives.org/OAI/2.0/"


def local(tag):
    return tag.rsplit("}", 1)[-1]


def namespace(tag):
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def text(node):
    return " ".join("".join(node.itertext()).split())


def normalize(value):
    return unicodedata.normalize("NFKC", value).casefold()


def safe_url(value, identifier_type=""):
    """Only publish absolute HTTP(S) links; DOI values can be resolved explicitly."""
    value = value.strip()
    if identifier_type.upper() == "DOI" and not value.lower().startswith(("http://", "https://")):
        value = "https://doi.org/" + value.removeprefix("doi:").strip()
    if any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
        return ""
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return ""


def value(node):
    return {"value": text(node), "lang": node.get(XML_LANG, node.get("lang", "")),
            "type": node.get("identifierType", node.get("descriptionType", node.get("subjectScheme", "")))}


def select_values(node, names, namespaces):
    return [value(n) for n in node if local(n.tag) in names and namespace(n.tag) in namespaces and text(n)]


def preferred(values, lang):
    if not values:
        return ""
    for candidate in (lang, "", "en", "ja"):
        for item in values:
            if item["lang"].lower().split("-")[0] == candidate:
                return item["value"]
    return values[0]["value"]


def parse_xml(raw, repair_html_entities=False):
    # Expat does not fetch external entities, but reject all declarations anyway.
    # Removing NULs for this check also detects declarations in UTF-16/32 XML.
    if re.search(br"<!\s*(DOCTYPE|ENTITY)\b", raw.replace(b"\x00", b""), re.I):
        raise ValueError("DTD and entity declarations are not accepted")
    repairs = Counter()
    if repair_html_entities:
        # Compatibility mode deliberately supports UTF-8 exports only.
        source = raw.decode("utf-8-sig")

        def replace(match):
            name = match[1]
            if name in {"amp", "lt", "gt", "quot", "apos"}:
                return match[0]
            decoded = html.entities.html5.get(name + ";")
            if decoded is None:
                return match[0]  # Unknown entities must still fail XML parsing.
            repairs[name] += 1
            return "".join(f"&#{ord(c)};" for c in decoded)

        # CDATA, comments and processing instructions are not XML entity text.
        parts = re.split(r"(<!\[CDATA\[.*?\]\]>|<!--.*?-->|<\?.*?\?>)", source, flags=re.S)
        for i in range(0, len(parts), 2):
            parts[i] = re.sub(r"&([A-Za-z][A-Za-z0-9]+);", replace, parts[i])
        raw = "".join(parts).encode("utf-8")
    try:
        return ET.fromstring(raw), dict(repairs)
    except ET.ParseError as error:
        raise ValueError(f"Invalid XML: {error}") from error


def read_records(path, repair_html_entities=False):
    raw = path.read_bytes()
    root, repairs = parse_xml(raw, repair_html_entities)
    parents = {child: parent for parent in root.iter() for child in parent}
    entries, warnings, ids = [], [], Counter()
    deleted = 0
    for node in root.iter():
        if local(node.tag) != "jpcoar" or namespace(node.tag) not in JPCOAR:
            continue
        wrapper = parents.get(node)
        while wrapper is not None and local(wrapper.tag) != "record":
            wrapper = parents.get(wrapper)
        header = next((n for n in wrapper if local(n.tag) == "header" and namespace(n.tag) in (OAI, "")), None) if wrapper is not None else None
        if header is not None and header.get("status") == "deleted":
            deleted += 1
            continue
        stable_page_id = wrapper.get("pageId", "") if wrapper is not None else ""
        source_id = next((text(n) for n in header if local(n.tag) == "identifier"), "") if header is not None else ""
        if not source_id and wrapper is not None:
            source_id = wrapper.get("id", "")
        titles = select_values(node, {"title"}, {DC})
        alternatives = select_values(node, {"alternative"}, {DCT})
        descriptions = select_values(node, {"description"}, DATACITE | {DC, DCT})
        creators = [value(n) for p in node if local(p.tag) == "creator" and namespace(p.tag) in JPCOAR
                    for n in p if local(n.tag) == "creatorName" and text(n)]
        publishers = select_values(node, {"publisher"}, {DC}) + [value(n) for p in node
                     if local(p.tag) == "publisher" and namespace(p.tag) in JPCOAR
                     for n in p if local(n.tag) == "publisherName" and text(n)]
        subjects = select_values(node, {"subject"}, JPCOAR | {DC})
        types = select_values(node, {"type"}, {DC})
        content_types = [value(n) for n in wrapper if n.tag == "{" + LOCAL + "}contentType" and text(n)] if wrapper is not None else []
        csv_row = wrapper.find("{urn:nihu-local:database-catalogue:1}csvRow") if wrapper is not None else None
        source_fields = {n.get("name"): n.text or "" for n in csv_row} if csv_row is not None else {}
        if source_fields:
            content_types = [{"value": v.strip(), "lang": "", "type": ""} for v in source_fields.get("Types of contents", "").split("|") if v.strip()]
        languages = select_values(node, {"language"}, {DC})
        access = select_values(node, {"accessRights"}, {DCT})
        identifiers = select_values(node, {"identifier"}, JPCOAR | {DC})
        links = list(dict.fromkeys(u for item in identifiers if (u := safe_url(item["value"], item["type"]))))
        identity = source_id or json.dumps([titles, creators, identifiers], ensure_ascii=False, sort_keys=True)
        base_id = hashlib.sha256(identity.encode()).hexdigest()[:20]
        ids[base_id] += 1
        record_id = stable_page_id or (base_id if ids[base_id] == 1 else f"{base_id}-{ids[base_id]}")
        if ids[base_id] > 1:
            warnings.append(f"Repeated identity retained as {record_id}")
        if not titles:
            warnings.append(f"{record_id}: missing dc:title; using a display placeholder")
        if not links:
            warnings.append(f"{record_id}: no usable HTTP(S)/DOI identifier; retained without an external link")
        # Keep all fields as plain text, including metadata not used by the UI.
        # This is a display/search projection; the original XML is also shipped.
        fields = []

        def flatten(element, prefix=""):
            label = prefix + local(element.tag)
            if len(element):
                for child in element:
                    flatten(child, label + " / ")
            elif text(element):
                fields.append({"name": label, **value(element),
                               "attributes": {local(k): v for k, v in element.attrib.items()}})

        for child in node:
            flatten(child)
        for item in content_types:
            fields.append({"name": "Types of contents (CSV)" if source_fields else "contentType (local; original dc:type)", **item, "attributes": {"sourceField": "Types of contents" if source_fields else "dc:type"}})
        for key, val in source_fields.items():
            if val: fields.append({"name": "CSV / " + key, "value": val, "lang": "", "type": "", "attributes": {}})
        entries.append(dict(id=record_id, source_id=source_id, titles=titles, alternatives=alternatives,
                            descriptions=descriptions, creators=creators, publishers=publishers,
                            subjects=subjects, types=types, content_types=content_types, languages=languages, access=access,
                            identifiers=identifiers, links=links, fields=fields, source_fields=source_fields,
                            search=normalize(" ".join([source_id] + [f["value"] for f in fields]))))
    # Tombstones generally have no metadata, so count them separately.
    deleted = sum(1 for n in root.iter() if local(n.tag) == "header" and namespace(n.tag) in (OAI, "") and n.get("status") == "deleted")
    if not entries:
        raise ValueError("No live JPCOAR 1.0/2.0 records found; output was not changed")
    return entries, {"records": len(entries), "deleted_records": deleted,
                     "html_entity_repairs": repairs, "warnings": warnings,
                     "source_sha256": hashlib.sha256(raw).hexdigest()}
