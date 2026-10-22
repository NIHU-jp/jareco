import argparse
from pathlib import Path
from . import compile_sources
p=argparse.ArgumentParser(description='Build the integrated XML from canonical CSV + supplemental JSON')
p.add_argument('--csv',type=Path,required=True)
p.add_argument('--supplement',type=Path,default=Path('data/supplement.json'))
p.add_argument('--output',type=Path,required=True)
p.add_argument('--report',type=Path,default=Path('data/source-build-report.json'))
a=p.parse_args()
r=compile_sources(a.csv,a.supplement,a.output,a.report)
print(f"Generated {r['records']} records from CSV + JSON; {len(r['warnings'])} unresolved values retained locally")
