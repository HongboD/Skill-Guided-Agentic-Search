"""Compare independently recomputed tables with packaged reference results."""
import math
import platform
import numpy as np
from common import PROJECT,OUTPUT,read,save

def compare(left,right,path='root'):
    """Require equal fields and values, with a small floating-point tolerance."""
    if isinstance(left,dict):
        assert isinstance(right,dict) and left.keys()==right.keys(),path+' keys'
        for key in left:compare(left[key],right[key],path+'/'+key)
    elif isinstance(left,list):
        assert isinstance(right,list) and len(left)==len(right),path+' length'
        for i,(a,b) in enumerate(zip(left,right)):compare(a,b,path+'/'+str(i))
    elif isinstance(left,(float,int)) and not isinstance(left,bool):
        assert isinstance(right,(float,int)) and math.isclose(left,right,rel_tol=1e-10,abs_tol=1e-9),(path,left,right)
    else:assert left==right,(path,left,right)

def main():
    """Check statistical calculations; raw-data remeasurement is a separate step."""
    ref=PROJECT/'results';checked=[]
    for name in ['analysis.json','diagnostics.json','paper_plot_data.json']:
        compare(read(ref/name),read(OUTPUT/name),name);checked.append(name)
    assert (ref/'paper_tables.md').read_text(encoding='utf-8')==(OUTPUT/'paper_tables.md').read_text(encoding='utf-8')
    checked.append('paper_tables.md')
    assert len(read(OUTPUT/'metrics.json'))==3240
    assert len(read(OUTPUT/'official_baselines.json'))==432
    result={'status':'PASS','matched_sessions':3240,'fixed_baseline_cells':432,
        'input_kind':'published per-session measurements',
        'official_scores_recomputed':False,'raw_behavior_recomputed':False,
        'rankings_replayed':False,'verified_tables':checked,'new_model_calls':0,'new_searches':0}
    result['verification_environment']={'python':platform.python_version(),'numpy':np.__version__,'system':platform.system()}
    save('VERIFICATION.json',result);print(result)

if __name__=='__main__':main()
