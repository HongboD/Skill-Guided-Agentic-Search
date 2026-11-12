"""Evaluate baseline run files with the bundled official scorers."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
from .score_parser import parse_official_scores

ROOT = Path(__file__).resolve().parents[1]


def evaluate(task, run_file, topics, output, *, qrels_path):
    """Return every topic's metrics, including defined empty-run scores."""
    qrels = Path(qrels_path).resolve()
    if not qrels.is_file():
        raise FileNotFoundError('Released judgments are required; see docs/DATA.md')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    run_file = Path(run_file).resolve()
    present = {line.split()[0] for line in run_file.read_text(encoding='utf-8').splitlines() if line.strip()}
    requested = {str(row['topic_id']) for row in topics}
    if present - requested:
        raise ValueError('Run contains topics outside the selected topic set.')
    stdout, stderr = '', ''
    if task == 'tot2023':
        binary = ROOT / 'vendor/trec_eval/trec_eval'
        if not binary.is_file():
            subprocess.run(['make', 'trec_eval'], cwd=binary.parent, check=True)
        command = [str(binary), '-q', '-m', 'ndcg_cut.1000', str(qrels), str(run_file)]
    elif task == 'genomics2007':
        command = [sys.executable, str(ROOT / 'vendor/genomics2007/trecgen2007_score.py'), str(qrels), str(run_file)]
    elif task == 'tar2018_full':
        local_qrels = output / 'qrels.txt'
        local_qrels.write_text(''.join(line + '\n' for line in qrels.read_text(encoding='utf-8-sig').splitlines() if line.strip()), encoding='utf-8')
        command = [sys.executable, str(ROOT / 'vendor/tar2018/tar_eval_2018.py'), '1', str(local_qrels), str(run_file)]
    else:
        raise ValueError('Unknown task.')
    # The Genomics scorer emits zero scores for unsubmitted topics. The other
    # CLIs require at least one submitted record.
    if present or task == 'genomics2007':
        process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        stdout, stderr = process.stdout, process.stderr
        (output / 'stdout.txt').write_text(stdout, encoding='utf-8')
        (output / 'stderr.txt').write_text(stderr, encoding='utf-8')
        if process.returncode:
            raise RuntimeError('Official evaluator failed. See stderr.txt.')
    results = []
    for topic in sorted(requested):
        if task == 'tar2018_full':
            metrics = {parts[1]: float(parts[2]) for line in stdout.splitlines()
                       if len(parts := line.split()) == 3 and parts[0] == topic}
            if not metrics:
                if topic in present:
                    raise ValueError('Evaluator omitted a submitted topic.')
                sys.path.insert(0, str(ROOT / 'vendor/tar2018'))
                from measures.tar_rulers_2018 import TarRulerTask1
                relevant = sum(p[0] == topic and int(p[-1]) in (1, 2)
                                for line in qrels.read_text(encoding='utf-8-sig').splitlines() if (p := line.split()))
                ruler = TarRulerTask1(topic, 5000, relevant)
                ruler.finalize()
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    ruler.print_scores()
                metrics = {p[1]: float(p[2]) for line in stream.getvalue().splitlines() if len(p := line.split()) == 3 and p[0] == topic}
            score = metrics['recall@5000']
        elif task == 'tot2023' and topic not in present:
            metrics, score = {'ndcg_cut_1000': 0.0}, 0.0
        else:
            parsed = parse_official_scores(task, topic, stdout)
            metrics, score = parsed['topic_scores'], parsed['primary_score']
        results.append({'topic_id': topic, 'primary_score': score, 'metrics': metrics})
    report = {'status': 'PASS', 'task': task, 'topics': results,
              'mean_primary_score': sum(row['primary_score'] for row in results) / len(results)}
    (output / 'scores.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report
