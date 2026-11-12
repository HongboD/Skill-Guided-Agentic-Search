"""Test tool restrictions, checkpointing, and completion without provider calls."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from search_agent.loop import run,REPAIR,SUMMARY_PREFIX
from search_agent.policy import make_request,CONTEXT,to_provider

def response(items,tokens=10):
    """Create a complete response fixture."""
    return {'status':'completed','error':None,'output':items,'usage':{'input_tokens':tokens,'output_tokens':1}}

def call(name,ident,args):
    """Create a function-call fixture with a distinct identity."""
    return {'type':'function_call','name':name,'call_id':ident,'arguments':json.dumps(args)}

def message(text):
    """Create a normal text-completion fixture."""
    return {'type':'message','role':'assistant','content':[{'type':'output_text','text':text}]}

class LoopTests(unittest.TestCase):
    def setUp(self):
        self.initial=make_request('Fixed task and strategy.',{'model':'fixture'})
    def test_complete_batch_and_results(self):
        replies=iter([response([call('search','a',{'query':'first'}),call('open','b',{'doc_id':'d'})]),response([call('finish','c',{'query_ids':['q000001']})]),response([message('Done')])])
        requests=[];calls=[]
        def generate(body):requests.append(body);return next(replies)
        def dispatch(item):
            calls.append(item)
            return {'call_id':item['call_id'],'text':json.dumps({'ok':True,'finished':item['name']=='finish'})}
        result=run(self.initial,generate,dispatch,lambda e:None)
        self.assertEqual(result['model_calls'],3)
        self.assertEqual([x['call_id'] for x in calls],['a','b','c'])
        self.assertEqual([x['call_id'] for x in requests[1]['input'] if x['type']=='function_call_output'],['a','b'])
    def test_whole_batch_checked_before_dispatch(self):
        called=[]
        with self.assertRaisesRegex(RuntimeError,'undeclared_tool'):
            run(self.initial,lambda b:response([call('search','a',{'query':'x'}),call('exec','b',{})]),lambda c:called.append(c),lambda e:None)
        self.assertEqual(called,[])
    def test_only_one_format_repair(self):
        requests=[]
        def generate(body):requests.append(body);return response([message('Done')])
        with self.assertRaisesRegex(RuntimeError,'finish_missing_after_single_schema_repair'):
            run(self.initial,generate,lambda c:None,lambda e:None)
        self.assertEqual(len(requests),2)
        self.assertEqual(requests[1]['input'][-1]['content'][0]['text'],REPAIR)
    def test_checkpoint_retains_prefix(self):
        replies=iter([response([call('search','a',{'query':'x'})],250000),response([message('Keep q000001')]),response([call('finish','b',{'query_ids':['q000001']})]),response([message('Done')])])
        requests=[];checkpoints=[]
        def generate(body):requests.append(body);to_provider(body,compaction=body['tools']==[]);return next(replies)
        def dispatch(item):return {'call_id':item['call_id'],'text':json.dumps({'ok':True,'finished':item['name']=='finish'})}
        result=run(self.initial,generate,dispatch,lambda e:None,context_policy=deepcopy(CONTEXT),checkpoint=checkpoints.append)
        self.assertEqual(result['automatic_compactions'],1)
        self.assertEqual(requests[1]['tools'],[])
        self.assertEqual(requests[2]['input'][:1],self.initial['input'])
        self.assertEqual(requests[2]['input'][1]['content'][0]['text'],SUMMARY_PREFIX+'Keep q000001')
        self.assertEqual(checkpoints,[1])
    def test_extra_tool_declaration_rejected(self):
        body=deepcopy(self.initial);body['tools'].append({'type':'web_search'})
        with self.assertRaisesRegex(ValueError,'tool_contract_changed'):to_provider(body)

if __name__=='__main__':unittest.main()
