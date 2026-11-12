"""Rebuild final rankings and selection diagnostics from saved query lists."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse
import contextlib
import io
import math
import sys
import threading
from common import ROOT,OUTPUT,VENDOR,read,write,save,records
from ranking import reciprocal_rank_fusion,trec_text
sys.path.insert(0,str(VENDOR/'tar2018'))
from measures.eval_measures_2018 import RecallBasedMeasures
PRINT_LOCK=threading.Lock()

def selected_ids(queries,selection):
    """List the actual query IDs used by each diagnostic selection rule."""
    distinct=[];seen=set()
    for q in queries:
        if q['query'].strip() not in seen:
            distinct.append(q['query_id']);seen.add(q['query'].strip())
    k=len(selection['query_ids'])
    return {'selected':selection['query_ids'],'first_k':distinct[:k],'last_k':distinct[-k:],'all':distinct}

def recall(topic,ranking,gold):
    """Return official printed recall and exact recall over document IDs."""
    relevant={doc for doc,v in gold.items() if v in (1,2)}
    metric=RecallBasedMeasures(topic,5000,len(relevant))
    for row in ranking[:5000]:
        value=gold.get(row['doc_id'],0)
        if value<3:metric.update_all(value,value)
    metric.finalize();stream=io.StringIO()
    with PRINT_LOCK:
        with contextlib.redirect_stdout(stream):metric.print_scores()
    score=next(float(line.split()[2]) for line in stream.getvalue().splitlines() if line.split()[1]=='recall@5000')
    exact=len(relevant & {r['doc_id'] for r in ranking[:5000]})/len(relevant)
    assert abs(score-exact)<=.000501
    return score,exact

def one(row,gold):
    """Use identical RRF parameters for selected, all, first-k, and last-k lists."""
    target=OUTPUT/'replays'/row['model']/row['job_id']
    marker=target/'validation.json'
    if marker.exists():
        assert read(marker)['status']=='PASS'
        return read(target/'tar.json') if row['task']=='tar2018_full' else None
    source=ROOT/row['session'];selection=read(source/'selection.json')
    queries=list(records(source/'queries.jsonl'));by_id={q['query_id']:q for q in queries}
    assert len(by_id)==len(queries)
    for q in queries:q['ranking']=[{'doc_id':doc} for doc in q['doc_ids']]
    distinct=[];seen=set()
    for q in queries:
        if q['query'].strip() not in seen:distinct.append(q);seen.add(q['query'].strip())
    def fuse(group):
        return reciprocal_rank_fusion([q['ranking'] for q in group],k=selection['rrf_k'],depth=selection['ranking_depth'])
    selected=fuse([by_id[x] for x in selection['query_ids']]);all_queries=fuse(distinct)
    assert selected==read(source/'ranking.json'),'selected ranking mismatch'
    text,_=trec_text(row['task'],row['topic_id'],selected)
    assert text==(source/'run.trec').read_text(encoding='utf-8'),'official run serialization mismatch'
    target.mkdir(parents=True,exist_ok=True)
    text,_=trec_text(row['task'],row['topic_id'],all_queries)
    (target/'run.trec').write_text(text,encoding='utf-8')
    result=None
    if row['task']=='tar2018_full':
        topic=row['topic_id'];relevant={doc for doc,v in gold[topic].items() if v in (1,2)}
        k=len(selection['query_ids'])
        alternatives={'selected':selected,'all':all_queries,'first_k':fuse(distinct[:k]),'last_k':fuse(distinct[-k:])}
        scores={};exact={}
        for name,ranking in alternatives.items():scores[name],exact[name]=recall(topic,ranking,gold[topic])
        assert scores['selected']==read(source/'expected_evaluation.json')['primary_score']
        union=set();cumulative=[];diagnostics=[]
        for q in distinct:
            found=set(q['doc_ids'])&relevant;new=found-union;union.update(found)
            cumulative.append(len(union)/len(relevant))
            diagnostics.append({'query_id':q['query_id'],'query':q['query'],'total_hits':q['total_hits'],
                'relevant_in_ranking':len(found),'new_relevant':len(new)})
        result={'setup':row['model'],'topic_id':topic,'condition':row['condition'],'job_id':row['job_id'],
            'query_ids':selected_ids(distinct,selection),
            'k':k,'distinct_queries':len(distinct),'scores':scores,'exact_scores':exact,'union_recall':cumulative[-1],
            'union_at_fraction':{str(f):cumulative[max(0,math.ceil(len(distinct)*f)-1)] for f in [.25,.5,.75,1.]},
            'queries_adding_relevant':sum(q['new_relevant']>0 for q in diagnostics),'query_diagnostics':diagnostics,
            'best_single_query_recall':max(q['relevant_in_ranking']/len(relevant) for q in diagnostics),
            'retrieved_relevant_count':len(union),'relevant_denominator':len(relevant)}
        write(target/'tar.json',result)
    write(marker,{'status':'PASS','selected_ranking_reproduced':True,'saved_queries':len(queries),'distinct_queries':len(distinct)})
    return result

def main():
    """Replay all accepted sessions without running a search or model."""
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args();gold={}
    for line in (ROOT/'data/qrels/tar2018_full/qrels.txt').read_text(encoding='utf-8').splitlines():
        if line.strip():topic,_,doc,v=line.split();gold.setdefault(topic,{})[doc]=int(v)
    manifest=read(ROOT/'manifest.json');tar=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n,future in enumerate(as_completed([pool.submit(one,r,gold) for r in manifest]),1):
            result=future.result()
            if result is not None:tar.append(result)
            if n%100==0:print('replayed',n,'of',len(manifest),flush=True)
    assert len(tar)==450
    save('tar_replay_rows.json',sorted(tar,key=lambda r:(r['setup'],r['job_id'])))

if __name__=='__main__':main()
