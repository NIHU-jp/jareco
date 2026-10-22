# Offline JPCOAR 2.0 schemas

The XSD files are unchanged copies of JPCOAR Schema v2.0.0 (2022-12-01),
originally retrieved on 2026-10-19 and copied from the adjacent local
`nihu-database-directory` repository on 2026-10-23.

Upstream: https://github.com/JPCOAR/schema/tree/master/2.0
The XML namespace schema is from https://www.w3.org/2001/03/xml.xsd .

`tools/validate_xml.py` resolves imports against these files only. It does not
fetch schemas or linked resources. Auditing requires the optional lxml package;
ordinary site builds continue to use the Python standard library only.

The experimental catalogue has 501/501 records conforming to the JPCOAR XSD.
The two previously missing URLs were supplied by the user and verified against
provider pages. Unknown access/language values remain in the local
CSV fields rather than guessed standard terms. See data/validation-report.json.

catalogue.xsd is our local profile 1.1, shared with nihu-database-directory;
it is not an upstream JPCOAR schema. See catalogue_source/README.md.
