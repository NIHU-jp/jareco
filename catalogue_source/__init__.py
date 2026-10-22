"""CSV + supplemental JSON -> lossless NIHU catalogue profile 1.1 (stdlib)."""
import csv
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as E
from urllib.parse import quote

NS = {'nihu':'urn:nihu-local:database-catalogue:1', 'jpcoar':'https://github.com/JPCOAR/schema/blob/master/2.0/', 'dc':'http://purl.org/dc/elements/1.1/', 'dcterms':'http://purl.org/dc/terms/', 'datacite':'https://schema.datacite.org/meta/kernel-4/', 'rdf':'http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'xml':'http://www.w3.org/XML/1998/namespace'}
for prefix, uri in NS.items(): E.register_namespace(prefix,uri)

def q(name):
    prefix, local = name.split(':',1)
    return '{'+NS[prefix]+'}'+local

def pack(node):
    return {'tag':node.tag, 'attributes':dict(node.attrib), 'text':node.text or '', 'children':[pack(c) for c in node]}

def unpack(value):
    if set(value)-{'tag','attributes','text','children'}: raise ValueError('Unknown metadata node keys')
    n=E.Element(value['tag'],dict(sorted(value.get('attributes',{}).items()))); n.text=value.get('text') or None
    n.extend(unpack(c) for c in value.get('children',[])); return n

def split(value):
    return list(dict.fromkeys(s.strip() for s in value.split('|') if s.strip()))

def add(parent,name,text,attrs=None):
    if not text: return None
    n=E.SubElement(parent,q(name),attrs or {}); n.text=text; return n

ORDER = ['title','alternative','creator','contributor','accessRights','rights','rightsHolder','subject','description','publisher','date','language','type','version','identifier','identifierRegistration','relation','temporal','geoLocation','fundingReference','sourceIdentifier','edition','volumeTitle','originalLanguage','extent','format','holdingAgent','datasetSeries','sourceTitle','volume','issue','numPages','pageStart','pageEnd','dissertationNumber','degreeName','dateGranted','degreeGrantor','conference','file','catalog']
def local(tag): return tag.rsplit('}',1)[-1]

def projection(row, profile, warnings):
    n=E.Element(q('jpcoar:jpcoar'))
    bilingual=profile=='institutes'
    if bilingual: add(n,'dc:title',row.get('Japanese Title',''),{q('xml:lang'):'ja'})
    add(n,'dc:title',row.get('English Title',''),{q('xml:lang'):'en'} if bilingual else {})
    if not bilingual: add(n,'dcterms:alternative',row.get('Japanese Title',''),{q('xml:lang'):'ja'})
    for title in split(row.get('Original Title','')):
        # The legacy Original Title column does not itself identify a language.
        if title != row.get('Japanese Title'): add(n,'dcterms:alternative',title)
    creator=E.Element(q('jpcoar:creator'))
    for field,lang in [('Alternative Name of Creator','ja'),('English Name of Creator','en')]:
        add(creator,'jpcoar:creatorName',row.get(field,''),{q('xml:lang'):lang})
    if len(creator): n.append(creator)
    access=row.get('Access Rights','')
    if access in ('open access','restricted access','metadata only access','embargoed access'):
        uri={'open access':'http://purl.org/coar/access_right/c_abf2','metadata only access':'http://purl.org/coar/access_right/c_14cb'}.get(access)
        add(n,'dcterms:accessRights',access,{q('rdf:resource'):uri} if uri else {})
    elif access: warnings.append({'id':row.get('Catalogue ID') or row.get('ID'), 'field':'Access Rights','value':access,'reason':'Unmapped value retained in csvRow, not guessed in JPCOAR'})
    for field,scheme in [('Category','Other'),('DDC subject','DDC'),('LCSH subject','LCSH'),('NDLSH subject','NDLSH')]:
        for value in split(row.get(field,'')): add(n,'jpcoar:subject',value,{'subjectScheme':scheme})
    for field,lang in [('Description (in English)','en'),('Description (in Japanese)','ja')]:
        add(n,'datacite:description',row.get(field,''),{'descriptionType':'Abstract' if bilingual else 'Other',q('xml:lang'):lang})
    for lang in split(row.get('Language of contents','')):
        if re.fullmatch('[a-z]{3}',lang): add(n,'dc:language',lang)
        else: warnings.append({'id':row.get('Catalogue ID') or row.get('ID'),'field':'Language of contents','value':lang,'reason':'Unmapped content language retained in csvRow'})
    url=row.get('Resource URL','')
    if url:
        # Encode illegal URI characters, preserving escapes and query structure.
        add(n,'jpcoar:identifier',quote(url,safe=":/?#@!$&'()*+,;=%"),{'identifierType':'URI'})
    return n

def read_sources(csv_path, supplement_path):
    def unique_object(pairs):
        result={}
        for k,v in pairs:
            if k in result: raise ValueError('Duplicate JSON key: '+k)
            result[k]=v
        return result
    supplement=json.loads(Path(supplement_path).read_text(encoding='utf-8'),object_pairs_hook=unique_object)
    if supplement.get('profile_version')!='1.1': raise ValueError('Unsupported catalogue profile version')
    with Path(csv_path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames != supplement['csv_headers']: raise ValueError('CSV headers differ from the declared profile')
        rows=list(reader)
    id_column=supplement['id_column']; ids=set()
    for row in rows:
        if None in row or any(v is None for v in row.values()): raise ValueError('Malformed CSV row')
        key=row[id_column]
        if not key or key in ids: raise ValueError('Missing or duplicate stable CSV ID: '+key)
        ids.add(key)
    if set(supplement['records'])-ids: raise ValueError('Supplement references an unknown CSV ID')
    if ids-set(supplement['records']): raise ValueError('CSV ID has no supplement; add explicit record settings')
    return rows,supplement

def generate(csv_path,supplement_path):
    rows,s=read_sources(csv_path,supplement_path)
    if s['collection'] not in ('jareco','institutes'): raise ValueError('Unknown collection mapping')
    if set(s)-{'profile_version','collection','id_column','csv_headers','catalogue_attributes','institutions','records','provenance'}: raise ValueError('Unknown supplemental top-level key')
    root=E.Element(q('nihu:catalogue'),dict(sorted(s['catalogue_attributes'].items())))
    institutions=E.SubElement(root,q('nihu:institutions'))
    for institution in s.get('institutions',[]): E.SubElement(institutions,q('nihu:institution'),dict(sorted(institution.items())))
    add(root,'nihu:supplement',json.dumps(s,ensure_ascii=False,sort_keys=True))
    records=E.SubElement(root,q('nihu:records')); warnings=[]; page_ids=set(); xml_ids=set()
    for index,row in enumerate(rows,1):
        key=row[s['id_column']]; extra=s['records'][key]
        if set(extra)-{'attributes','metadata','website','list_summaries','resource_type','classification'}: raise ValueError('Unknown supplemental record key: '+key)
        if set(extra) & set(row): raise ValueError('Supplement must not override CSV columns')
        attrs=extra['attributes'].copy()
        if attrs['id'] in xml_ids: raise ValueError('Duplicate XML ID')
        xml_ids.add(attrs['id'])
        if attrs.get('pageId'):
            if not re.fullmatch('[A-Za-z0-9_-]+',attrs['pageId']) or attrs['pageId'] in page_ids: raise ValueError('Invalid or duplicate page ID')
            page_ids.add(attrs['pageId'])
        rec=E.SubElement(records,q('nihu:record'),dict(sorted(attrs.items())))
        meta=projection(row,s['collection'],warnings)
        # Additional metadata may extend but cannot replace scalar CSV-owned values.
        for item in extra.get('metadata',[]):
            node=unpack(item)
            if node.tag in {q('dc:title'),q('jpcoar:creator'),q('dcterms:accessRights'),q('dc:language')}:
                raise ValueError('Supplement conflicts with CSV-owned metadata: '+node.tag)
            if node.tag==q('dcterms:alternative') and (node.text or '') in {row.get('Original Title'),row.get('Japanese Title')} and node.text:
                raise ValueError('Supplement duplicates CSV title')
            if node.tag==q('datacite:description') and node.get(q('xml:lang')) in ('ja','en') and node.get('descriptionType') in ('Abstract','Other'):
                raise ValueError('Supplement conflicts with CSV description')
            if any(E.tostring(node)==E.tostring(old) for old in meta): raise ValueError('Duplicate supplemental metadata')
            meta.append(node)
        typ=extra.get('resource_type')
        if typ:
            if meta.find(q('dc:type')) is not None: raise ValueError('Duplicate resource type')
            add(meta,'dc:type',typ['value'],{q('rdf:resource'):typ['uri']})
        meta[:]=sorted(meta,key=lambda c:ORDER.index(local(c.tag)) if local(c.tag) in ORDER else len(ORDER))
        rec.append(meta)
        website=json.loads(json.dumps(extra.get('website',{})))
        if s['collection']=='institutes':
            website.setdefault('details',{}).setdefault('ja',{})['url']=row['Resource URL']
        admin={'csv_fields':{k:v for k,v in row.items() if v and k!=s['id_column']},'website':website}
        if extra.get('classification'): admin['classification']=extra['classification']
        add(rec,'nihu:administration',json.dumps(admin,ensure_ascii=False,sort_keys=True))
        for lang,content in sorted(extra.get('list_summaries',{}).items(),key=lambda item:(item[0]!='ja',item[0])): add(rec,'nihu:listSummary',content,{q('xml:lang'):lang,'format':'html'})
        csvrow=E.SubElement(rec,q('nihu:csvRow'),source='canonical',row=str(index))
        for field,value in row.items():
            child=E.SubElement(csvrow,q('nihu:field'),name=field); child.text=value or None
    E.indent(root,space='  ')
    raw=E.tostring(root,encoding='utf-8',xml_declaration=True).replace(b'\r', b'&#13;')+b'\n'
    report={'profile_version':'1.1','records':len(rows),'csv_sha256':hashlib.sha256(Path(csv_path).read_bytes()).hexdigest(),'supplement_sha256':hashlib.sha256(Path(supplement_path).read_bytes()).hexdigest(),'xml_sha256':hashlib.sha256(raw).hexdigest(),'warnings':warnings}
    return raw,report

def compile_sources(csv_path,supplement_path,output,report_path=None):
    if Path(output).resolve() in {Path(csv_path).resolve(), Path(supplement_path).resolve()}:
        raise ValueError('Generated XML must not overwrite editorial sources')
    raw,report=generate(csv_path,supplement_path)
    Path(output).write_bytes(raw)
    if report_path: Path(report_path).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def extract_sources(xml_path, csv_output, supplement_output):
    """Recover the editorial values from an integrated XML, into new files only."""
    destinations=[Path(csv_output),Path(supplement_output)]
    if any(p.exists() for p in destinations) or destinations[0].resolve()==destinations[1].resolve():
        raise ValueError('Recovery destinations must be distinct new files')
    raw=Path(xml_path).read_bytes()
    if b'<!DOCTYPE' in raw.replace(b'\x00',b'').upper(): raise ValueError('DTD is not permitted')
    root=E.fromstring(raw)
    s=json.loads(root.findtext(q('nihu:supplement')))
    rows=[]
    for rec in root.findall(q('nihu:records')+'/'+q('nihu:record')):
        row={n.get('name'):n.text or '' for n in rec.find(q('nihu:csvRow'))}
        if list(row)!=s['csv_headers']:raise ValueError('Stored fields do not match profile headers')
        rows.append(row)
    with destinations[0].open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=s['csv_headers']);writer.writeheader();writer.writerows(rows)
    destinations[1].write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
