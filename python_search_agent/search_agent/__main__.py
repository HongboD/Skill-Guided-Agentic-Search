"""Execute one independently configured search session."""
import argparse
from copy import deepcopy
import os
from pathlib import Path
from urllib.parse import urlsplit
from .records import read,dump
from .policy import CONTEXT,POLICY_VERSION,make_request
from .retrieval import LuceneBackend
from .session import Session
from .execution import execute_loop

class Account:
    """Keep the endpoint and API credential in the trusted controller."""
    def __init__(self,deployment):
        self.endpoint=deployment['endpoint']
        if urlsplit(self.endpoint).scheme!='https':raise ValueError('https_provider_endpoint_required')
        self.environment=deployment['api_key_environment']
        if not os.environ.get(self.environment):raise ValueError('API key environment variable is empty')
        self.block_reason=None
    def api_key(self):
        """Read the credential only when the relay sends an upstream request."""
        return os.environ[self.environment]
    def hold(self,reason):
        """Record a transport stop without starting another session."""
        self.block_reason=reason

def main():
    """Configure retrieval, run the isolated loop, and save its final ranking."""
    parser=argparse.ArgumentParser()
    for name in ['prompt-file','index','task','output','deployment','java-home','loop-venv']:
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--publication-dates',nargs=2,metavar=('START','END'))
    args=parser.parse_args()
    if args.task not in {'tot2023','genomics2007','tar2018_full'}:raise ValueError('unsupported_task')
    if (args.task=='tar2018_full') != bool(args.publication_dates):raise ValueError('TAR requires its topic publication date range')
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=False)
    deployment=read(args.deployment);account=Account(deployment)
    os.environ['JAVA_HOME']=str(Path(args.java_home).resolve())
    config=read(Path(__file__).resolve().parents[1]/'retrieval.json')
    config['ranking_depth']=5000 if args.task=='tar2018_full' else 1000
    if args.publication_dates:
        start,end=args.publication_dates
        if not (len(start)==len(end)==8 and start.isdigit() and end.isdigit() and start<=end):raise ValueError('invalid_date_range')
        config['filter_query']=f'publication_date:[{start} TO {end}]'
    prompt=Path(args.prompt_file).read_text(encoding='utf-8')
    (output/'prompt.txt').write_text(prompt,encoding='utf-8')
    request=make_request(prompt,deployment)
    context=deepcopy(CONTEXT);context['trigger_tokens']=deployment.get('context_trigger_tokens',245480)
    seconds=deployment.get('session_seconds')
    if seconds is not None and (type(seconds) is not int or seconds<=0):raise ValueError('invalid_session_seconds')
    if type(context['trigger_tokens']) is not int or context['trigger_tokens']<=0:raise ValueError('invalid_context_trigger')
    dump(output/'request_template.json',{**request,'input':[]})
    dump(output/'settings.json',{'deployment':deployment,'retrieval':config,'instruction_policy':POLICY_VERSION})
    backend=LuceneBackend(Path(args.index),config)
    try:
        session=Session(backend,output,config)
        result=execute_loop(output,request,session,account,context_policy=context,
            maximum_seconds=seconds,venv=Path(args.loop_venv))
        dump(output/'ranking.json',session.selected_ranking())
        dump(output/'result.json',result)
    finally:backend.close()

if __name__=='__main__':main()
