#!/usr/bin/env python3
"""Ingest manually-downloaded PDFs (from a login-worklist browser sitting)
into the fulltext cache, and report exactly which (bibtexKey, slug)
classification rows now have fulltext evidence available.

Input directory: PDFs named <doi-slug>.pdf (the same slug scheme
classify_citations.py uses -- DOI with non-[a-z0-9._-] chars replaced by
"_"), as harvest/fulltext/build_login_worklist.py's rows are keyed. One
citing DOI can appear in more than one of our papers' citing lists (a
survey or heavily-citing paper citing several corpus papers) -- this
script searches every harvest/citations/<key>.json, not just the paper the
worklist row happened to be built for, so the text lands wherever it's
actually cited.

Extraction: pypdf, same STUB_CHARS=2000 floor as harvest_fulltext.py.
Surrogate-safe write: pypdf's extract_text() occasionally returns lone
surrogate codepoints from malformed embedded font encodings, which a
plain UTF-8 write raises UnicodeEncodeError on; write with
errors='surrogateescape' so a garbled PDF doesn't crash the whole batch.

Output: harvest/fulltext/<key>/<slug>.txt + sidecar (route: "manual",
matching harvest_fulltext.py's sidecar shape) for every (key, slug) pair
where the DOI is cited -- across ALL keys, pilot and non-pilot alike.
Idempotent: a slug already cached "ok" for a key is skipped unless
--refresh.

Prints the affected (key, slug) pairs as JSON to stdout (for the rejudge
step to consume) as well as a human-readable summary to stderr.

    python3 harvest/fulltext/ingest_manual_pdfs.py ~/workspace/nextgen-fulltext
"""
import argparse
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CITATIONS_DIR = os.path.join(ROOT, 'harvest', 'citations')
STUB_CHARS = 2000


def slug_for(citing):
    doi = citing.get('doi')
    if doi:
        return re.sub(r'[^a-z0-9._-]', '_', doi.lower())
    oa = citing.get('openalex')
    if oa:
        return 'oa-' + oa.rsplit('/', 1)[-1]
    s2 = citing.get('s2')
    if s2:
        return 's2-' + s2[:16]
    import hashlib
    return 'noid-' + hashlib.sha1((citing.get('title') or '').encode('utf-8')).hexdigest()[:16]


def extract_text(pdf_path):
    from pypdf import PdfReader
    with open(pdf_path, 'rb') as fh:
        data = fh.read()
    reader = PdfReader(io.BytesIO(data))
    text = []
    for page in reader.pages:
        try:
            text.append(page.extract_text() or '')
        except Exception:
            continue
    return '\n'.join(text).strip()


def build_slug_index():
    """slug -> [keys], built once. A per-PDF full corpus rescan (177 files,
    135MB) is fine for a dozen PDFs (sitting #1) but not for a sitting-2-
    scale batch in the thousands -- same output, one pass instead of N."""
    index = {}
    for path in glob.glob(os.path.join(CITATIONS_DIR, '*.json')):
        key = os.path.basename(path)[:-5]
        if key.startswith('.'):
            continue
        data = json.load(open(path))
        for c in data.get('citing') or []:
            index.setdefault(slug_for(c), set()).add(key)
    return {slug: sorted(keys) for slug, keys in index.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf_dir')
    ap.add_argument('--refresh', action='store_true')
    args = ap.parse_args()

    pdf_dir = os.path.expanduser(args.pdf_dir)
    pdfs = sorted(glob.glob(os.path.join(pdf_dir, '*.pdf')))
    print(f'{len(pdfs)} PDFs found in {pdf_dir}', file=sys.stderr)

    slug_index = build_slug_index()
    print(f'{len(slug_index)} distinct citing-DOI slugs indexed across the corpus', file=sys.stderr)

    affected = []
    stats = {'ok': 0, 'stub': 0, 'extract_fail': 0}
    for pdf_path in pdfs:
        slug = os.path.basename(pdf_path)[:-4]
        keys = slug_index.get(slug, [])
        if not keys:
            print(f'  {slug}: no matching citing record in any harvest/citations/*.json '
                 f'-- skipped', file=sys.stderr)
            continue

        try:
            text = extract_text(pdf_path)
        except Exception as exc:
            print(f'  {slug}: extract failed ({type(exc).__name__}: {exc})', file=sys.stderr)
            stats['extract_fail'] += 1
            continue

        chars = len(text)
        status = 'ok' if chars >= STUB_CHARS else 'stub'
        stats[status] += 1
        print(f'  {slug}: {chars} chars -> {status}, cites {len(keys)} paper(s): '
             f'{keys}', file=sys.stderr)

        for key in keys:
            out_dir = os.path.join(HERE, key)
            os.makedirs(out_dir, exist_ok=True)
            sidecar_path = os.path.join(out_dir, slug + '.json')
            if os.path.exists(sidecar_path) and not args.refresh:
                existing = json.load(open(sidecar_path))
                if existing.get('status') == 'ok':
                    continue
            result = {'doi': None, 'route': 'manual', 'chars': chars, 'status': status,
                     'slug': slug}
            if status == 'ok':
                txt_path = os.path.join(out_dir, slug + '.txt')
                with open(txt_path, 'w', encoding='utf-8', errors='surrogateescape') as fh:
                    fh.write(text)
                affected.append({'key': key, 'slug': slug, 'chars': chars})
            tmp = sidecar_path + '.tmp'
            with open(tmp, 'w') as fh:
                json.dump(result, fh, indent=2)
            os.replace(tmp, sidecar_path)

    print(f'\nextracted: {stats["ok"]} ok, {stats["stub"]} below the 2000-char floor, '
         f'{stats["extract_fail"]} failed to extract', file=sys.stderr)
    print(f'{len(affected)} (key, slug) pairs now have fulltext evidence', file=sys.stderr)
    print(json.dumps(affected, indent=1))


if __name__ == '__main__':
    main()
