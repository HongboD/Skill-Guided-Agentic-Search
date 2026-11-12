"""Run the bundled official scorers on exported rankings."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse
import subprocess
import sys
import threading
from common import ROOT,OUTPUT,VENDOR,read,write,save
from score_parser import parse_official_scores
PRINT_LOCK=threading.Lock()

def group_score(key,rows,variant):
    """Evaluate one model/task/condition group and retain complete scorer output."""
    model,task,condition=key
    folder=OUTPUT/'official'/variant/model/task/condition
    folder.mkdir(parents=True,exist_ok=True)
    gold=ROOT/'data/qrels'/task/'qrels.txt'
    if task=='genomics2007':gold=gold.with_name('released_qrels.txt')
    if task=='tar2018_full':
        text=''.join(line+'\n' for line in gold.read_text(encoding='utf-8').splitlines() if line.strip())
        gold=folder/'qrels.txt';gold.write_text(text,encoding='utf-8')
    texts={r['topic_id']:(OUTPUT/'replays'/r['model']/r['job_id']/'run.trec' if variant=='all' else ROOT/r['session']/'run.trec').read_text(encoding='utf-8') for r in rows}
    run=folder/'run.trec';run.write_text(''.join(texts[t] for t in sorted(texts)),encoding='utf-8')
    if task=='tot2023':
        command=[str(VENDOR/'trec_eval/trec_eval'),'-q','-m','ndcg_cut.1000',str(gold),str(run)]
    elif task=='genomics2007':
        command=[sys.executable,str(VENDOR/'genomics2007/trecgen2007_score.py'),str(gold),str(run)]
    else:
        command=[sys.executable,str(VENDOR/'tar2018/tar_eval_2018.py'),'1',str(gold),str(run)]
    process=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='strict')
    (folder/'stdout.txt').write_text(process.stdout,encoding='utf-8')
    (folder/'stderr.txt').write_text(process.stderr,encoding='utf-8')
    if process.returncode:raise RuntimeError('official scorer failed: '+repr(key))
    results=[]
    for row in rows:
        topic=row['topic_id']
        if task=='tar2018_full':
            metrics={v[1]:float(v[2]) for line in process.stdout.splitlines() if len(v:=line.split())==3 and v[0]==topic}
            if not metrics:
                assert not texts[topic]
                metrics=empty_tar(topic,gold)
            primary=metrics['recall@5000']
        elif task=='tot2023' and not texts[topic]:
            metrics={'ndcg_cut_1000':0.0};primary=0.0
        else:
            parsed=parse_official_scores(task,topic,process.stdout)
            primary=parsed['primary_score'];metrics=parsed['topic_scores']
        item={k:row[k] for k in ['model','job_id','task','topic_id','condition']}
        item.update(primary_score=primary,topic_scores=metrics,evaluable=True)
        if variant!='all':
            expected=read(ROOT/row['session']/'expected_evaluation.json')
            assert primary==expected['primary_score'],('primary mismatch',item,expected)
            assert metrics==expected['topic_scores'],('secondary metric mismatch',item,expected)
        results.append(item)
    write(folder/'topic_scores.json',results)
    return results

def empty_tar(topic,gold):
    """Evaluate an empty ranking with the unchanged official Task 1 ruler."""
    import contextlib,io
    sys.path.insert(0,str(VENDOR/'tar2018'))
    from measures.tar_rulers_2018 import TarRulerTask1
    relevant=sum(v[0]==topic and int(v[-1]) in (1,2) for line in gold.read_text(encoding='utf-8').splitlines() if (v:=line.split()))
    ruler=TarRulerTask1(topic,5000,relevant);ruler.finalize()
    stream=io.StringIO()
    with PRINT_LOCK:
        with contextlib.redirect_stdout(stream):ruler.print_scores()
    return {v[1]:float(v[2]) for line in stream.getvalue().splitlines() if len(v:=line.split())==3 and v[0]==topic}

def main():
    """Compile trec_eval locally, then score selected or all-query rankings."""
    parser=argparse.ArgumentParser();parser.add_argument('--variant',choices=['selected','all','baselines'],default='selected')
    parser.add_argument('--workers',type=int,default=2);args=parser.parse_args()
    if not (VENDOR/'trec_eval/trec_eval').exists():
        subprocess.run(['make','trec_eval'],cwd=VENDOR/'trec_eval',check=True)
    rows=read(ROOT/('baseline_manifest.json' if args.variant=='baselines' else 'manifest.json'))
    if args.variant=='baselines':rows=[dict(r,model='fixed_retrieval',job_id=f'{r["task"]}-{r["topic_id"]}-{r["condition"]}-r1') for r in rows]
    groups=defaultdict(list)
    for r in rows:groups[r['model'],r['task'],r['condition']].append(r)
    result=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(group_score,k,v,args.variant):k for k,v in groups.items()}
        for future in as_completed(futures):
            result.extend(future.result());print('official',args.variant,futures[future],flush=True)
    save('official_'+args.variant+'.json',sorted(result,key=lambda r:(r['model'],r['job_id'])))
    if args.variant=='all':
        selected={(r['model'],r['job_id']):r for r in read(OUTPUT/'official_selected.json')}
        save('all_queries_scores.json',[{'setup':r['model'],**{k:r[k] for k in ['job_id','task','topic_id','condition','evaluable']},
            'primary_score':selected[r['model'],r['job_id']]['primary_score'],'all_query_score':r['primary_score'],
            'score_difference':r['primary_score']-selected[r['model'],r['job_id']]['primary_score']} for r in result])

if __name__=='__main__':main()
