"""Run portable tests with synthetic inputs and no API credentials."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
for folder in [root, root / 'python_search_agent', root / 'retrieval_baselines']:
    subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover',
                    '-s', 'tests', '-p', 'test_*.py', '-v'], cwd=folder, check=True)
