"""Recompute action measures, then join scores and recorded token usage."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse
from common import ROOT,OUTPUT,read,write,save
from behavior import blind_measure
SCORES={}

def one(row):
    """Measure a neutral trace without model, condition, or outcome inputs."""
    target=OUTPUT/'per_session'/(row['model']+'_'+row['job_id']+'.json')
    if target.exists():return read(target)
    behavior,detail=blind_measure(ROOT/row['trace'],row['task'])
    session=ROOT/row['session']
    evaluation=read(session/'expected_evaluation.json')
    score=SCORES[row['model'],row['job_id']]
    assert score['primary_score']==evaluation['primary_score']
    usage=read(session/'usage.json')
    if row['model']=='Claude':
        uncached=usage.get('input_tokens',0)+usage.get('cache_creation_input_tokens',0)
        cached=usage.get('cache_read_input_tokens',0)
        total=uncached+cached+usage['output_tokens']
    else:
        cached=usage.get('cached_input_tokens',0)
        uncached=usage.get('input_tokens',0)-cached
        total=usage['total_tokens']
    result={k:row[k] for k in ['model','job_id','task','topic_id','condition']}
    result.update(behavior,primary_score=score['primary_score'],evaluable=True,
        total_tokens=total,uncached_input_tokens=uncached,cached_input_tokens=cached,output_tokens=usage['output_tokens'])
    write(OUTPUT/'action_details'/(row['model']+'_'+row['job_id']+'.json'),detail)
    write(target,result)
    return result

def main():
    """Process independent traces in parallel and retain per-session caches."""
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args();manifest=read(ROOT/'manifest.json');rows=[]
    SCORES.update({(r['model'],r['job_id']):r for r in read(OUTPUT/'official_selected.json')})
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n,future in enumerate(as_completed([pool.submit(one,r) for r in manifest]),1):
            rows.append(future.result())
            if n%100==0:print('measured',n,'of',len(manifest),flush=True)
    assert len(rows)==3240
    save('metrics.json',sorted(rows,key=lambda r:(r['model'],r['job_id'])))

if __name__=='__main__':main()
