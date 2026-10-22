"""Editorial CSV authority, lossless profile, and invalid merge protection."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as E

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from catalogue_source import generate, read_sources, q

class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stem='resources' if (ROOT/'data/resources.csv').exists() else 'databases'
        cls.csv=ROOT/'data'/f'{cls.stem}.csv'
        cls.extra=ROOT/'data/supplement.json'

    def test_lossless_xml_and_reproducibility(self):
        rows,s=read_sources(self.csv,self.extra)
        raw,report=generate(self.csv,self.extra)
        self.assertEqual(raw,(ROOT/'data'/f'{self.stem}.xml').read_bytes())
        self.assertEqual(raw,generate(self.csv,self.extra)[0])
        records=E.fromstring(raw).findall(q('nihu:records')+'/'+q('nihu:record'))
        self.assertEqual(len(records),len(rows))
        for row,rec in zip(rows,records):
            self.assertEqual(row,{n.get('name'):n.text or '' for n in rec.find(q('nihu:csvRow'))})
        self.assertEqual(report['records'],len(rows))

    def write_fixture(self,base,rows,s):
        csvpath=base/'input.csv'; extra=base/'supplement.json'
        with csvpath.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=s['csv_headers']);w.writeheader();w.writerows(rows)
        extra.write_text(json.dumps(s,ensure_ascii=False),encoding='utf-8')
        return csvpath,extra

    def test_csv_edit_updates_xml_without_changing_sources_or_reading_originals(self):
        rows,s=read_sources(self.csv,self.extra)
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); key=rows[0][s['id_column']]
            old_id=s['records'][key]['attributes']['id']
            rows[0]['English Title']='Edited title & <text>'
            rows[0]['Resource URL']='https://example.org/changed?a=1&b=2'
            paths=self.write_fixture(base,rows,s)
            before=[p.read_bytes() for p in paths]
            original_read=Path.read_text
            def guard(path,*args,**kwargs):
                if path.name != 'supplement.json': raise AssertionError('Unexpected XML/original dependency')
                return original_read(path,*args,**kwargs)
            with patch.object(Path,'read_text',guard): raw,_=generate(*paths)
            rec=E.fromstring(raw).find(q('nihu:records')+'/'+q('nihu:record'))
            self.assertEqual(rec.get('id'),old_id)
            meta=rec.find(q('jpcoar:jpcoar'))
            self.assertIn('Edited title & <text>',[n.text for n in meta.findall(q('dc:title'))])
            self.assertIn(rows[0]['Resource URL'],[n.text for n in meta.findall(q('jpcoar:identifier'))])
            self.assertEqual(before,[p.read_bytes() for p in paths])

    def test_duplicate_missing_unknown_ids_and_conflicting_metadata_fail(self):
        for scenario in ['duplicate','missing','unknown','override']:
            rows,s=read_sources(self.csv,self.extra)
            key=rows[0][s['id_column']]
            if scenario=='duplicate':rows.append(rows[0].copy())
            if scenario=='missing':rows[0][s['id_column']]=''
            if scenario=='unknown':s['records']['not-in-csv']=s['records'][key]
            if scenario=='override':s['records'][key].setdefault('metadata',[]).append({'tag':q('dc:title'),'text':'Hidden override'})
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                paths=self.write_fixture(Path(directory),rows,s)
                with self.assertRaises(ValueError): generate(*paths)

    def test_integrated_xml_can_recover_all_editorial_inputs(self):
        from catalogue_source import extract_sources
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); csv_path=base/'recovered.csv'; extra=base/'supplement.json'
            extract_sources(ROOT/'data'/f'{self.stem}.xml',csv_path,extra)
            original_rows,original_s=read_sources(self.csv,self.extra)
            recovered_rows,recovered_s=read_sources(csv_path,extra)
            self.assertEqual(original_rows,recovered_rows)
            self.assertEqual(original_s,recovered_s)
            self.assertEqual(generate(csv_path,extra)[0],generate(self.csv,self.extra)[0])
            with self.assertRaisesRegex(ValueError,'new files'):
                extract_sources(ROOT/'data'/f'{self.stem}.xml',csv_path,extra)

    def test_duplicate_json_keys_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'supplement.json'
            path.write_text('{"profile_version":"1.1","profile_version":"1.1"}')
            with self.assertRaisesRegex(ValueError,'Duplicate JSON key'):generate(self.csv,path)
