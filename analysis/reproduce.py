"""Recompute statistical results from published per-session measurements."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

def main():
    """Recompute analyses without claiming to remeasure raw traces or rankings."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('runs/recomputed'))
    args=parser.parse_args()
    code=Path(__file__).resolve().parent
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    for name in ['metrics.json','all_queries_scores.json','official_baselines.json']:
        shutil.copyfile(code.parent/'results'/name,output/name)
    shutil.copyfile(code.parent/'results/tar_replay_summary.json',output/'tar_replay_rows.json')
    environment=dict(os.environ,SEARCH_REPRO_OUTPUT=str(output),PYTHONDONTWRITEBYTECODE='1')
    steps=[['analyze.py'],['summarize.py'],['tables.py'],['verify.py']]
    for step in steps:
        print('RUN',*step,flush=True)
        subprocess.run([sys.executable,'-B',str(code/step[0]),*step[1:]],env=environment,check=True)

if __name__=='__main__':main()
