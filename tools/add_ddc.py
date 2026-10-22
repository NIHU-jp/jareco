#!/usr/bin/env python3
"""Add explicitly mapped DDC subjects while retaining all original categories."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jpcoar_ssg.metadata import JPCOAR, local, namespace, parse_xml, read_records


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def apply_mapping(source, mapping_path, corrections_path, assignments_path):
    raw, mapping_raw = source.read_bytes(), mapping_path.read_bytes()
    mapping = json.loads(mapping_raw)
    mapping_hash = digest(mapping_raw)
    rules = {}
    for rule in mapping['mappings']:
        if rule['category'] in rules or not re.fullmatch(r'[0-9]{3}(?:\.[0-9]+)?', rule['ddc']):
            raise ValueError('Mapping contains a duplicate category or invalid DDC notation')
        if rule.get('relation') != 'broadMatch':
            raise ValueError('This tool only applies explicit broadMatch rules')
        rules[rule['category']] = rule
    corrections = json.loads(corrections_path.read_text(encoding='utf-8'))
    if corrections['corrected_sha256'] != digest(raw):
        raise ValueError('Input differs from the correction log; reconcile its provenance before adding DDC')
    previous = json.loads(assignments_path.read_text(encoding='utf-8')) if assignments_path.exists() else {}
    if previous.get('output_sha256') == digest(raw) and previous.get('mapping_sha256') == mapping_hash:
        return previous  # An unchanged rerun must not duplicate subjects or audit entries.
    root, _ = parse_xml(raw)
    records, _ = read_records(source)
    parents = {c: p for p in root.iter() for c in p}
    nodes = []
    for n in root.iter():
        if local(n.tag) != 'jpcoar' or namespace(n.tag) not in JPCOAR:
            continue
        p = parents.get(n)
        while p is not None and local(p.tag) != 'record':
            p = parents.get(p)
        if p is not None and any(local(h.tag) == 'header' and h.get('status') == 'deleted' for h in p):
            continue
        nodes.append(n)
    if len(nodes) != len(records):
        raise ValueError('Cannot reconcile XML records and parsed records')
    assignments, changes = [], []
    added_counts = Counter()
    unmapped_counts = Counter()
    old_assignments = {(a['record_id'], a['category'], a['ddc']): a for a in previous.get('assignments', [])}
    for index, (node, record) in enumerate(zip(nodes, records), 1):
        subject_tag = '{' + namespace(node.tag) + '}subject'
        subjects = list(node.findall(subject_tag))
        existing = {(s.text or '').strip() for s in subjects if s.get('subjectScheme') == 'DDC'}
        categories = list(dict.fromkeys((s.text or '').strip() for s in subjects if s.get('subjectScheme') == 'Other'))
        for category in categories:
            rule = rules.get(category)
            if rule is None:
                unmapped_counts[category] += 1
                continue
            code = rule['ddc']
            status = 'already_present'
            if code not in existing:
                # Subject elements must remain before descriptions and later fields.
                last_subject = max(i for i, child in enumerate(node) if child.tag == subject_tag)
                added = ET.Element(subject_tag, subjectScheme='DDC')
                added.text = code
                node.insert(last_subject + 1, added)
                existing.add(code)
                status = 'added'
                added_counts[code] += 1
                changes.append(dict(record=index, title=record['titles'][0]['value'], action='add_mapped_ddc',
                                    before=None, after={'subjectScheme': 'DDC', 'value': code},
                                    source_category=category, mapping=mapping['id'], relation='broadMatch'))
            prior = old_assignments.get((record['id'], category, code))
            if prior and prior['status'] == 'added':
                status = 'added'
            assignments.append(dict(record=index, record_id=record['id'], title=record['titles'][0]['value'],
                                    category=category, ddc=code, status=status, relation='broadMatch',
                                    mapping=mapping['id']))
    if changes:
        for prefix, uri in {'jpcoar': 'https://github.com/JPCOAR/schema/blob/master/2.0/',
                            'dc': 'http://purl.org/dc/elements/1.1/', 'dcterms': 'http://purl.org/dc/terms/',
                            'datacite': 'https://schema.datacite.org/meta/kernel-4/',
                            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'}.items():
            ET.register_namespace(prefix, uri)
        ET.indent(root, space='  ')
        updated = ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
    else:
        updated = raw
    counts = Counter(a['ddc'] for a in assignments)
    report = dict(mapping=mapping['id'], mapping_file=mapping_path.name, mapping_sha256=mapping_hash,
                  input_sha256=digest(raw), output_sha256=digest(updated),
                  policy=mapping['policy'], reference=mapping['source'],
                  assigned_records=len({a['record_id'] for a in assignments}),
                  subject_assignments=len(assignments), assignments_by_ddc=dict(counts),
                  added_this_run=dict(added_counts), unmapped_category_counts=dict(unmapped_counts), assignments=assignments)
    corrections['corrected_sha256'] = digest(updated)
    corrections['policy'] = 'Conservative format repairs and explicitly approved broad DDC additions. Original categories retained; no invented resource types, resource URLs, or relation types.'
    corrections['changes'].extend(changes)
    corrections['correction_counts']['add_mapped_ddc'] = corrections['correction_counts'].get('add_mapped_ddc', 0) + len(changes)
    corrections['ddc_mapping'] = dict(file=mapping_path.name, sha256=mapping_hash, id=mapping['id'])
    source.write_bytes(updated)
    write_json(corrections_path, corrections)
    write_json(assignments_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'data/resources.xml')
    parser.add_argument('--mapping', type=Path, default=ROOT / 'data/ddc-mapping.json')
    parser.add_argument('--corrections', type=Path, default=ROOT / 'data/corrections.json')
    parser.add_argument('--report', type=Path, default=ROOT / 'data/ddc-assignments.json')
    args = parser.parse_args()
    report = apply_mapping(args.input, args.mapping, args.corrections, args.report)
    print(json.dumps({k: report[k] for k in ('assigned_records', 'subject_assignments', 'assignments_by_ddc')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
