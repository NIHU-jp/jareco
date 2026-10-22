#!/usr/bin/env python3
"""Optional offline JPCOAR 2.0 XSD audit; exits 1 on remaining schema errors."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

try:
    from lxml import etree as E
except ImportError:
    raise SystemExit('XSD auditing requires lxml (optional); see README.md.')

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / 'schema'
JPCOAR = 'https://github.com/JPCOAR/schema/blob/master/2.0/'


class OfflineResolver(E.Resolver):
    def resolve(self, url, public_id, context):
        path = SCHEMAS / url.rsplit('/', 1)[-1]
        if path.is_file():
            return self.resolve_filename(str(path), context)
        raise ValueError(f'No bundled schema for {url}')


def audit(source):
    raw = source.read_bytes()
    if b'<!DOCTYPE' in raw.replace(b'\x00', b'').upper():
        raise ValueError('DTD is not permitted')
    parser = E.XMLParser(no_network=True, resolve_entities=False)
    parser.resolvers.add(OfflineResolver())
    schema = E.XMLSchema(E.parse(str(SCHEMAS / 'jpcoar_scm.xsd'), parser))
    document = E.fromstring(raw, E.XMLParser(no_network=True, resolve_entities=False))
    invalid, errors, valid, total = [], Counter(), 0, 0
    for index, node in enumerate(document.iter('{' + JPCOAR + '}jpcoar'), 1):
        total += 1
        if schema.validate(node):
            valid += 1
        else:
            messages = [entry.message for entry in schema.error_log]
            errors.update(messages)
            invalid.append(dict(record=index, title=node.findtext('{http://purl.org/dc/elements/1.1/}title'), errors=messages))
    if not total:
        raise ValueError('No JPCOAR 2.0 records found')
    return dict(source=source.name, source_sha256=hashlib.sha256(raw).hexdigest(),
                schema='JPCOAR 2.0.0 (2022-12-01)', records=total, valid_records=valid,
                invalid_records=len(invalid), error_counts=dict(errors), records_with_errors=invalid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'data/resources.xml')
    parser.add_argument('--report', type=Path, default=ROOT / 'data/validation-report.json')
    args = parser.parse_args()
    report = audit(args.input)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{report['valid_records']}/{report['records']} records conform to the bundled XSD; {report['invalid_records']} need review.")
    for message, count in Counter(report['error_counts']).most_common():
        print(f'{count}: {message[:220]}' + (' …' if len(message) > 220 else ''))
    raise SystemExit(1 if report['invalid_records'] else 0)


if __name__ == '__main__':
    main()
