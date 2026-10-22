import csv
import hashlib
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from jpcoar_ssg.metadata import read_records, parse_xml, safe_url, preferred
from jpcoar_ssg.build import ROOT, build
from tools.add_ddc import apply_mapping
from tools.classify_resources import classify

NS = 'xmlns:j="https://github.com/JPCOAR/schema/blob/master/2.0/" xmlns:d="http://purl.org/dc/elements/1.1/" xmlns:t="http://purl.org/dc/terms/"'


def xml(body, ns=NS):
    return f'<j:jpcoar {ns}>{body}</j:jpcoar>'.encode()


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class ReaderTests(unittest.TestCase):
    def read(self, raw, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.xml'
            path.write_bytes(raw)
            return read_records(path, **kwargs)

    def test_prefixes_versions_and_single_record(self):
        for version in ['1.0', '2.0']:
            records, _ = self.read(xml('<d:title xml:lang="en">A resource</d:title>', NS.replace('2.0', version)))
            self.assertEqual(records[0]['titles'][0]['value'], 'A resource')

    def test_oai_deleted_and_identifier(self):
        raw = (f'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords><record><header><identifier>oai:example:1</identifier></header><metadata>{xml("<d:title>A</d:title>").decode()}</metadata></record><record><header status="deleted"><identifier>oai:example:2</identifier></header></record></ListRecords></OAI-PMH>').encode()
        records, report = self.read(raw)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['source_id'], 'oai:example:1')
        self.assertEqual(report['deleted_records'], 1)

    def test_entity_repair_opt_in_and_cdata(self):
        raw = xml('<d:title>A&nbsp;B</d:title><t:alternative><![CDATA[C&nbsp;D]]></t:alternative>')
        with self.assertRaisesRegex(ValueError, 'Invalid XML'):
            self.read(raw)
        records, report = self.read(raw, repair_html_entities=True)
        self.assertEqual(records[0]['titles'][0]['value'], 'A B')
        self.assertEqual(records[0]['alternatives'][0]['value'], 'C&nbsp;D')
        self.assertEqual(report['html_entity_repairs'], {'nbsp': 1})
        with self.assertRaises(ValueError):
            self.read(xml('<d:title>&notARealEntity;</d:title>'), repair_html_entities=True)

    def test_dtd_rejected_even_when_utf16(self):
        raw = '<!DOCTYPE x [<!ENTITY attack SYSTEM "file:///etc/passwd">]><x/>'
        for encoding in ['utf-8', 'utf-16']:
            with self.assertRaisesRegex(ValueError, 'DTD'):
                self.read(raw.encode(encoding))

    def test_url_safety_and_doi(self):
        for bad in ['javascript:alert(1)', '//example.org', 'https://example.org\\@evil.test', 'https://x.test/\npath', 'https://user:secret@x.test/', 'https://[bad']:
            self.assertEqual(safe_url(bad), '')
        self.assertEqual(safe_url('10.1234/example', 'DOI'), 'https://doi.org/10.1234/example')
        records, _ = self.read(xml('<d:title>A</d:title><j:identifier>javascript:alert(1)</j:identifier>'))
        self.assertEqual(records[0]['links'], [])

    def test_multilingual_legacy_lang_and_preservation(self):
        body = '<d:title xml:lang="en">English</d:title><t:alternative xml:lang="ja">日本語</t:alternative><x:description xmlns:x="https://schema.datacite.org/meta/kernel-4/" lang="ja">説明</x:description><t:issued>2020</t:issued>'
        records, _ = self.read(xml(body))
        self.assertEqual(preferred(records[0]['descriptions'], 'ja'), '説明')
        self.assertIn('説明', records[0]['search'])
        self.assertIn('issued', [f['name'] for f in records[0]['fields']])

    def test_duplicate_records_are_not_lost(self):
        item = xml('<d:title>A</d:title>').decode()
        records, report = self.read(f'<ListRecords>{item}{item}</ListRecords>'.encode())
        self.assertEqual(len(records), 2)
        self.assertNotEqual(records[0]['id'], records[1]['id'])
        self.assertTrue(report['warnings'])

    def test_empty_or_other_namespaces_rejected(self):
        for raw in [b'<empty/>', b'<jpcoar><title>Wrong namespace</title></jpcoar>']:
            with self.assertRaisesRegex(ValueError, 'No live JPCOAR'):
                self.read(raw)


class BuildTests(unittest.TestCase):
    def test_corrected_source_and_provenance(self):
        corrections = json.loads((ROOT / 'data/corrections.json').read_text())
        self.assertEqual(corrections['source_sha256'], hashlib.sha256((ROOT / 'data/1792652897.xml').read_bytes()).hexdigest())
        self.assertEqual(corrections['corrected_sha256'], hashlib.sha256((ROOT / 'data/resources.xml').read_bytes()).hexdigest())
        original, _ = read_records(ROOT / 'data/1792652897.xml', True)
        corrected, report = read_records(ROOT / 'data/resources.xml')
        rules = {r['category']: r['ddc'] for r in json.loads((ROOT / 'data/ddc-mapping.json').read_text())['mappings']}
        self.assertEqual(len(original), len(corrected))
        self.assertEqual(report['html_entity_repairs'], {})
        for before, after in zip(original, corrected):
            for field in ['titles', 'alternatives', 'creators', 'publishers', 'access']:
                self.assertEqual(before[field], after[field])
            self.assertEqual([v['value'] for v in before['types']], [v['value'] for v in after['content_types']])
            self.assertEqual(len(after['types']), 1)
            for field in ['descriptions', 'identifiers']:
                self.assertEqual([v['value'] for v in before[field]], [v['value'] for v in after[field]])
            existing = {s['value'] for s in before['subjects'] if s['type'] == 'DDC'}
            additions = list(dict.fromkeys(rules[s['value']] for s in before['subjects'] if s['value'] in rules and rules[s['value']] not in existing))
            self.assertEqual([s['value'] for s in after['subjects']], [s['value'] for s in before['subjects']] + additions)
        self.assertEqual(corrections['correction_counts']['lang_to_xml_lang'], 315)
        self.assertEqual(corrections['correction_counts']['add_mapped_ddc'], 303)
        ddc_report = json.loads((ROOT / 'data/ddc-assignments.json').read_text())
        types = json.loads((ROOT / 'data/resource-type-assignments.json').read_text())
        self.assertEqual(ddc_report['output_sha256'], types['input_sha256'])
        self.assertEqual(types['output_sha256'], corrections['corrected_sha256'])
        self.assertEqual(types['type_counts'], {'interactive resource': 485, 'dataset': 14, 'software': 2})
        self.assertEqual(ddc_report['mapping_sha256'], hashlib.sha256((ROOT / 'data/ddc-mapping.json').read_bytes()).hexdigest())
        self.assertEqual(ddc_report['assigned_records'], 297)
        self.assertEqual(ddc_report['assignments_by_ddc'], {'700': 150, '900': 131, '200': 22})

    def test_classification_is_idempotent_and_checks_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            paths = [base / name for name in ('resources.xml', 'corrections.json', 'resource-type-assignments.json')]
            for path in paths:
                path.write_bytes((ROOT / 'data' / path.name).read_bytes())
            source, corrections, report = paths
            before = [p.read_bytes() for p in paths]
            classify(source, ROOT / 'data/resource-type-policy.json', corrections, report)
            self.assertEqual(before, [p.read_bytes() for p in paths])
            source.write_bytes(source.read_bytes() + b' ')
            modified = source.read_bytes()
            with self.assertRaisesRegex(ValueError, 'provenance'):
                classify(source, ROOT / 'data/resource-type-policy.json', corrections, report)
            self.assertEqual(source.read_bytes(), modified)

    def test_ddc_addition_is_idempotent_and_preserves_unmapped_and_existing_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source, corrections, report_path = base / 'input.xml', base / 'corrections.json', base / 'ddc.json'
            source.write_bytes(xml('<d:title>Mixed collection</d:title><j:subject subjectScheme="Other">History</j:subject><j:subject subjectScheme="Other">Arts and Crafts</j:subject><j:subject subjectScheme="Other">Maps and Geology</j:subject><j:subject subjectScheme="DDC">708</j:subject>'))
            corrections.write_text(json.dumps({'corrected_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'changes': [], 'correction_counts': {}}))
            mapping = ROOT / 'data/ddc-mapping.json'
            report = apply_mapping(source, mapping, corrections, report_path)
            record = read_records(source)[0][0]
            self.assertEqual([s['value'] for s in record['subjects'] if s['type'] == 'DDC'], ['708', '900', '700'])
            self.assertEqual([s['value'] for s in record['subjects'] if s['type'] == 'Other'], ['History', 'Arts and Crafts', 'Maps and Geology'])
            self.assertEqual(report['unmapped_category_counts'], {'Maps and Geology': 1})
            first = [p.read_bytes() for p in (source, corrections, report_path)]
            apply_mapping(source, mapping, corrections, report_path)
            self.assertEqual(first, [p.read_bytes() for p in (source, corrections, report_path)])

    def test_ddc_provenance_mismatch_does_not_modify_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source, corrections = base / 'input.xml', base / 'corrections.json'
            original = xml('<d:title>A</d:title><j:subject subjectScheme="Other">History</j:subject>')
            source.write_bytes(original)
            corrections.write_text(json.dumps({'corrected_sha256': 'not-the-input-hash'}))
            with self.assertRaisesRegex(ValueError, 'provenance'):
                apply_mapping(source, ROOT / 'data/ddc-mapping.json', corrections, base / 'report.json')
            self.assertEqual(source.read_bytes(), original)

    def test_real_export_and_all_local_links_under_a_subpath(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = (Path(temporary) / 'project-subpath').resolve()
            report = build(ROOT / 'site.toml', output)
            self.assertEqual(report['records'], 501)
            self.assertEqual(report['html_entity_repairs'], {})
            self.assertEqual((output / 'experimental/catalogue.xml').read_bytes(), (ROOT / 'data/resources.xml').read_bytes())
            self.assertEqual(len(ET.parse(output / 'experimental/jpcoar.xml').getroot()), 501)
            records = json.loads((output / 'experimental/records.json').read_text())
            self.assertEqual(len(records), 501)
            with (output / 'experimental/records.csv').open(encoding='utf-8-sig', newline='') as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 501)
            pages = list(output.rglob('*.html'))
            self.assertEqual(len(pages), 1005)
            self.assertEqual((output / 'original/1792652897.xml').read_bytes(), (ROOT / 'data/1792652897.xml').read_bytes())
            exported = ET.parse(output / 'experimental/jpcoar.xml').getroot()
            self.assertFalse(any(e.tag.startswith('{urn:jpcoar-static-catalogue:1}') for e in exported.iter()))
            notes = [e.text for e in exported.iter() if e.text and e.text.startswith('Contained material types (from original dc:type metadata):')]
            self.assertEqual(len(notes), 8)
            self.assertEqual(sum(len(r['content_types']) for r in records), 9)
            for path in pages:
                parser = Tags()
                parser.feed(path.read_text())
                for tag, attrs in parser.tags:
                    target = attrs.get('href', attrs.get('src', ''))
                    parts = urlsplit(target)
                    if not target or parts.scheme or target.startswith('#'):
                        continue
                    self.assertFalse(target.startswith('/'), (path, target))
                    resolved = (path.parent / unquote(parts.path)).resolve()
                    self.assertTrue(resolved.is_relative_to(output), (path, target))
                    self.assertTrue(resolved.exists(), (path, target))

    def test_minimal_generic_config_html_safety_and_failed_build_preserves_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source, config, output = base / 'source.xml', base / 'site.toml', base / 'site'
            source.write_bytes(xml('<d:title>&lt;script&gt;alert(1)&lt;/script&gt;</d:title><j:identifier>javascript:alert(1)</j:identifier><t:alternative>=SUM(1,2)</t:alternative>'))
            config.write_text('input="source.xml"\nlanguages=["ja"]\ndefault_language="ja"\n', encoding='utf-8')
            build(config, output)
            page = (output / 'index.html').read_text()
            self.assertFalse((output / 'original').exists())
            self.assertIn('&lt;script&gt;', page)
            self.assertNotIn('<script>alert', page)
            parser = Tags()
            parser.feed(page)
            self.assertFalse(any(a.get('href', '').startswith('javascript:') for _, a in parser.tags))
            with (output / 'experimental/records.csv').open(encoding='utf-8-sig', newline='') as handle:
                self.assertEqual(next(csv.DictReader(handle))['alternatives'], "'=SUM(1,2)")
            source.write_text('<bad/>')
            with self.assertRaises(ValueError):
                build(config, output)
            self.assertEqual((output / 'index.html').read_text(), page)

    def test_output_protection(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'marker'):
                build(ROOT / 'site.toml', directory)
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            build(ROOT / 'site.toml', ROOT)


if __name__ == '__main__':
    unittest.main()
