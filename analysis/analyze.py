"""Compute within-topic contrasts and exploratory model comparisons."""
import json
from collections import Counter
from pathlib import Path
import numpy as np
from common import OUTPUT as OUT, read, save
from inference import paired_summary,holm
TASKS={'tot2023':150,'genomics2007':36,'tar2018_full':30}
CONDITIONS=['S0','S1','S2','S3','S4']
EXPORTS={'GPT':None,'Claude':None,'DeepSeek':None}
def interval(values):
    a = np.asarray(values, dtype=float)
    assert len(a) and np.isfinite(a).all()
    rng = np.random.default_rng(20261106)
    means = rng.choice(a, (10000, len(a))).mean(axis=1)
    return {'n': len(a), 'mean': float(a.mean()), 'interval': np.quantile(means, [0.025, 0.975]).tolist(), 'wins': int((a > 1e-10).sum()), 'ties': int((abs(a) <= 1e-10).sum()), 'losses': int((a < -1e-10).sum())}

def main():
    allrows=read(OUT/'metrics.json')
    look={(r['model'],r['task'],r['topic_id'],r['condition']):r for r in allrows}
    assert len(look)==3240,'duplicate_primary_cell'
    means={};contrasts={};fields=['primary_score','searches','open_successes','docs_per_search','formulation_diversity',
        'lexical_evidence_adoption_rate','zero_hit_rate','paging_rate','repeated_query_rate','unique_parent_documents_seen',
        'total_tokens','uncached_input_tokens','output_tokens','selected_query_count','searches_per_action_batch']
    for model in EXPORTS:
        for task,n in TASKS.items():
            topics=sorted({r['topic_id'] for r in allrows if r['model']==model and r['task']==task});assert len(topics)==n
            for c in CONDITIONS:
                group=[look[model,task,t,c] for t in topics]
                means[f'{model}/{task}/{c}']={f:{'n':len(v:=[r[f] for r in group if r.get(f) is not None]),
                    'mean':float(np.mean(v)) if v else None,'median':float(np.median(v)) if v else None} for f in fields}
            family={}
            for c in CONDITIONS[1:]:
                key=f'{model}/{task}/{c}';base=[look[model,task,t,'S0'] for t in topics];group=[look[model,task,t,c] for t in topics]
                delta=[a['primary_score']-b['primary_score'] for a,b in zip(group,base)]
                p=paired_summary(delta);p.update({k:v for k,v in interval(delta).items() if k in ['wins','ties','losses']})
                family[c]=p['p_value'];behavior={}
                for f in fields[1:]:
                    pairs=[(a[f],b[f]) for a,b in zip(group,base) if a.get(f) is not None and b.get(f) is not None]
                    if pairs:
                        v=interval([a-b for a,b in pairs]);av=np.mean([a for a,b in pairs]);bv=np.mean([b for a,b in pairs])
                        v['ratio_of_means']=float(av/bv) if bv else None;behavior[f]=v
                joint=Counter()
                for d,a,b in zip(delta,group,base):
                    q='higher' if d>1e-10 else 'lower' if d<-1e-10 else 'same'
                    e=a['search_attempts']-b['search_attempts'];e='more' if e>0 else 'fewer' if e<0 else 'same'
                    joint[f'{q}_quality_{e}_searches']+=1
                contrasts[key]={'primary':p,'behavior':behavior,'joint':dict(joint)}
            for c,p in holm(family).items():contrasts[f'{model}/{task}/{c}']['primary']['holm_p']=p
    global_p=holm({k:v['primary']['p_value'] for k,v in contrasts.items() if not k.endswith('/S4')})
    for k,p in global_p.items():contrasts[k]['exploratory_27_contrast_holm_p']=p
    interactions={}
    for a,b in [('DeepSeek','GPT'),('DeepSeek','Claude'),('GPT','Claude')]:
        for task in TASKS:
            topics=sorted({r['topic_id'] for r in allrows if r['task']==task})
            for c in ['S1','S2','S3']:
                delta=[(look[a,task,t,c]['primary_score']-look[a,task,t,'S0']['primary_score'])-
                       (look[b,task,t,c]['primary_score']-look[b,task,t,'S0']['primary_score']) for t in topics]
                interactions[f'{a}-{b}/{task}/{c}']=paired_summary(delta)
    for k,p in holm({k:v['p_value'] for k,v in interactions.items()}).items():interactions[k]['holm_p']=p
    save('analysis.json',{'status':'PASS','sessions':3240,'means':means,'contrasts':contrasts,'cross_model_skill_contrasts':interactions})
    print(json.dumps({'status':'PASS','sessions':3240,'output':str(OUT)}),flush=True)

if __name__=='__main__':main()
