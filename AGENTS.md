# JPCOAR static catalogue

- This is an independent repository. Never stage it in an outer repository.
- Keep the generator generic: JPCOAR parsing belongs in `jpcoar_ssg/`, collection-specific titles, licensing, and facets in `site.toml`.
- `data/resources.xml` is the corrected, editable source for site builds. The user explicitly authorizes correcting inconsistent source metadata. Preserve the original `data/1792652897.xml` as provenance and record corrections in `data/corrections.json`. Never invent missing values merely to pass schema validation.
- The user approved additive, broad DDC mapping for History → 900, Arts and Crafts → 700, and Religious Studies → 200. Keep original categories and existing numeric classifications. Mapping policy and provenance live in `data/ddc-mapping.json` and `data/ddc-assignments.json`.
- No server-side runtime or external search service. Generated links must work under a GitHub Pages repository subpath.
- Keep intake notes and task logs outside this repository. No files larger than 50 MB.
- Run `sh check.sh` and `sh build.sh` after substantive changes. Inspect `git status --short` and `git diff --cached --stat` before any commit.

- The user approved provisional entity-level resource types: interactive resource by default, dataset/software only for reviewed exceptions in data/resource-type-policy.json. Preserve legacy dc:type labels separately, never as the new entity classification.
- Keep the unmodified original XML distribution under original/ separate from the experimental SSG and its modified XML/CSV/JSON under experimental/. Label experimental derivatives explicitly.
