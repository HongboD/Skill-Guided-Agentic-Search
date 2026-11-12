"""Exercise the real SDK and sandbox against a local synthetic provider."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import argparse,json,sys,threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from search_agent.execution import execute_loop
from search_agent.policy import CONTEXT,make_request,to_provider
from search_agent.records import dump
from search_agent.session import Session
from search_agent.loop import SUMMARY_PREFIX

class Backend:
    """Return one local fixture record without accessing a real corpus."""
    index_path=Path('/controller-only-fixture-index')
    def search(self,query,*,offset,page_size,ranking_depth):
        return {'parsed_query':query,'total_hits':1,'ranking':[{'doc_id':'fixture-doc','score':1.0}],
            'hits':[] if offset else [{'doc_id':'fixture-doc','score':1.0,'rank':1,'title':'Fixture','contents':'Fixture content.'}]}
    def get(self,ident):
        return {'id':ident,'title':'Fixture','contents':'Fixture content.','metadata':{}}

def main():
    """Check one checkpoint and three tool calls without credentials or a model."""
    parser=argparse.ArgumentParser();parser.add_argument('--venv',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=False)
    requests=[];errors=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            try:
                assert not self.headers.get('Authorization')
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body);n=len(requests)
                to_provider(body,compaction=n==2)
                assert len({r['user'] for r in requests})==1
                if n in [1,3,4]:
                    name,arguments={1:('search',{'query':'fixture'}),3:('open',{'doc_id':'fixture-doc'}),4:('finish',{'query_ids':['q000001']})}[n]
                    item={'type':'function_call','id':f'fc_{n}','call_id':f'call_{n}','status':'completed','name':name,'arguments':json.dumps(arguments)}
                else:
                    assert n in [2,5]
                    item={'type':'message','id':f'msg_{n}','role':'assistant','status':'completed','content':[{'type':'output_text','text':'Keep q000001.' if n==2 else 'Done.','annotations':[]}]}
                if n==3:assert body['input'][-1]['content'][0]['text']==SUMMARY_PREFIX+'Keep q000001.'
                response={'id':f'resp_{n}','object':'response','created_at':1794099000,'status':'completed','model':'deepseek-flash',
                    'output':[item],'parallel_tool_calls':body['parallel_tool_calls'],'tool_choice':'auto','tools':body['tools'],
                    'temperature':1.,'top_p':1.,'error':None,'incomplete_details':None,'instructions':body['instructions'],'metadata':{},
                    'usage':{'input_tokens':250000 if n==1 else 100,'output_tokens':10,'total_tokens':250010 if n==1 else 110,
                    'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':0}}}
                events=[{'type':'response.created','response':{**response,'status':'in_progress','output':[]}},
                    {'type':'response.output_item.added','output_index':0,'item':item},
                    {'type':'response.output_item.done','output_index':0,'item':item},
                    {'type':'response.completed','response':response}]
                payload=''.join('data: '+json.dumps(e)+'\n\n' for e in events).encode()
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(payload)))
                self.end_headers();self.wfile.write(payload)
            except Exception as error:errors.append(repr(error));self.send_error(400)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        result=execute_loop(output,make_request('Fixture task.',{'model':'deepseek-flash'}),Session(Backend(),output,{'ranking_depth':1000}),None,
            fixture_url=f'http://127.0.0.1:{server.server_port}/responses',maximum_seconds=600,
            context_policy=deepcopy(CONTEXT),venv=Path(args.venv))
        assert result['status']=='PASS' and result['automatic_compactions']==1 and len(requests)==5 and not errors
        report={'status':'PASS','real_model_calls':0,'fixture_requests':5,'summary_requests':1,'tool_calls':3,
            'exact_sdk_payloads':True,'sandbox_isolation':True,'three_tools_only':True,'trajectory_reconciliation':True}
        dump(output/'validation.json',report);print(json.dumps(report))
    finally:server.shutdown();server.server_close()

if __name__=='__main__':main()
