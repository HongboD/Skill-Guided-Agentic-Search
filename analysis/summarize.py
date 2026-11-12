"""Combine action measures, official scores, and saved-ranking replays."""
from collections import defaultdict
import json
from pathlib import Path
import numpy as np
from common import OUTPUT as OUT
from analyze import interval
from inference import paired_summary,holm
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))

def main():
    rows=read(OUT/'metrics.json');analysis=read(OUT/'analysis.json')
    fusion=read(OUT/'all_queries_scores.json');tar=read(OUT/'tar_replay_rows.json')
    assert len(rows)==len(fusion)==3240 and len(tar)==450
    lookup={(r['model'],r['job_id']):r for r in rows}
    byfusion={(r['setup'],r['job_id']):r for r in fusion}
    assert lookup.keys()==byfusion.keys()
    result={'status':'PASS','selection':{},'tar':{},'topic_distributions':{},'same_topic_examples':{},'goal_control_contrasts':{}}
    for model in ['GPT','Claude','DeepSeek']:
        for task in ['tot2023','genomics2007','tar2018_full']:
            group=[r for r in rows if r['model']==model and r['task']==task]
            topics=sorted({r['topic_id'] for r in group})
            loc={(r['topic_id'],r['condition']):r for r in group}
            result['selection'][f'{model}/{task}']={}
            for c in ['S0','S1','S2','S3','S4']:
                scores=[byfusion[model,loc[t,c]['job_id']] for t in topics]
                result['selection'][f'{model}/{task}'][c]={
                    'selected':float(np.mean([r['primary_score'] for r in scores])),
                    'all_query':float(np.mean([r['all_query_score'] for r in scores])),
                    'paired_change':interval([r['score_difference'] for r in scores])}
                if c!='S0':
                    delta=[loc[t,c]['primary_score']-loc[t,'S0']['primary_score'] for t in topics]
                    d=np.asarray(delta)
                    result['topic_distributions'][f'{model}/{task}/{c}']={
                        'leave_one_out_mean_range':[float(((d.sum()-d)/(len(d)-1)).min()),float(((d.sum()-d)/(len(d)-1)).max())],
                        'lower_quality_more_searches':[t for t in topics if loc[t,c]['primary_score']<loc[t,'S0']['primary_score']-1e-10 and loc[t,c]['search_attempts']>loc[t,'S0']['search_attempts']],
                        'baseline_perfect':sum(loc[t,'S0']['primary_score']==1 for t in topics),
                        'baseline_zero':sum(loc[t,'S0']['primary_score']==0 for t in topics),
                        'condition_zero':sum(loc[t,c]['primary_score']==0 for t in topics),
                        'largest_gain_topic':max(topics,key=lambda t:loc[t,c]['primary_score']-loc[t,'S0']['primary_score']),
                        'largest_loss_topic':min(topics,key=lambda t:loc[t,c]['primary_score']-loc[t,'S0']['primary_score'])}
                if c in ['S1','S2','S3']:
                    result['goal_control_contrasts'][f'{model}/{task}/{c}']=paired_summary([loc[t,c]['primary_score']-loc[t,'S4']['primary_score'] for t in topics])
            result['selection'][f'{model}/{task}']['all_conditions']={
                'selected':float(np.mean([r['primary_score'] for r in group])),
                'all_query':float(np.mean([byfusion[model,r['job_id']]['all_query_score'] for r in group])),
                'paired_change':interval([float(np.mean([byfusion[model,loc[t,c]['job_id']]['score_difference']
                    for c in ['S0','S1','S2','S3','S4']])) for t in topics])}
        for c in ['S0','S1','S2','S3','S4','all_conditions']:
            group=[r for r in tar if r['setup']==model and (c=='all_conditions' or r['condition']==c)]
            topics=sorted({r['topic_id'] for r in group});bytopic={t:[r for r in group if r['topic_id']==t] for t in topics}
            result['tar'][f'{model}/{c}']={
                'sessions':len(group),'pool_coverage':float(np.mean([r['union_recall'] for r in group])),
                'selected_exact':float(np.mean([r['exact_scores']['selected'] for r in group])),
                'gap':float(np.mean([r['union_recall']-r['exact_scores']['selected'] for r in group])),
                'means':{name:float(np.mean([r['scores'][name] for r in group])) for name in ['selected','first_k','last_k','all']},
                'first_k_change':interval([float(np.mean([r['scores']['first_k']-r['scores']['selected'] for r in bytopic[t]])) for t in topics]),
                'late_queries_add_relevant_sessions':sum(r['union_recall']>r['union_at_fraction']['0.75']+1e-10 for r in group),
                'fraction_queries_adding_relevant':float(np.mean([r['queries_adding_relevant']/r['distinct_queries'] for r in group]))}
    for k,p in holm({k:v['p_value'] for k,v in result['goal_control_contrasts'].items()}).items():result['goal_control_contrasts'][k]['holm_p']=p
    # Raw query examples are outside this dataset-free code release.
    (OUT/'diagnostics.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    output=[]
    for model in ['GPT','Claude','DeepSeek']:
        for task in ['tot2023','genomics2007','tar2018_full']:
            output.append('\n'+model+' '+task)
            for c in ['S0','S1','S2','S3','S4']:
                m=analysis['means'][f'{model}/{task}/{c}']
                output.append(c+' '+json.dumps({k:round(m[k]['mean'],5) for k in ['primary_score','searches','open_successes','formulation_diversity','lexical_evidence_adoption_rate','zero_hit_rate','total_tokens']}))
            for c in ['S1','S2','S3','S4']:
                v=analysis['contrasts'][f'{model}/{task}/{c}'];output.append(c+'-S0 '+json.dumps(v['primary']))
    output.append('\nTAR '+json.dumps(result['tar']))
    (OUT/'summary.txt').write_text('\n'.join(output)+'\n',encoding='utf-8')
    print('\n'.join(output),flush=True)

if __name__=='__main__':main()
