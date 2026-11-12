"""Freeze the search role, task prefix, checkpoint prompt, and tool schemas."""
from copy import deepcopy
from pathlib import Path
import uuid
from .records import read

ROOT=Path(__file__).resolve().parent
POLICY_VERSION='python-search-agent-instructions-1'
BASE_INSTRUCTIONS=(ROOT/'base_prompt.txt').read_text(encoding='utf-8')
TEMPLATE=read(ROOT/'request_template.json')
CONTEXT=read(ROOT/'context_policy.json')
COMPACTION_PROMPT=CONTEXT['summary_prompt']
NAMES={'search','open','finish'}

def to_provider(body,*,compaction=False):
    """Reject any change to instructions or the complete declared tool inventory."""
    if body.get('instructions')!=BASE_INSTRUCTIONS:raise ValueError('search_base_changed')
    if not isinstance(body.get('model'),str) or not body['model']:raise ValueError('model_required')
    if not body.get('stream'):raise ValueError('streaming_required')
    if body.get('previous_response_id') or body.get('conversation'):raise ValueError('explicit_history_required')
    if compaction:
        last={'type':'message','role':'user','content':[{'type':'input_text','text':COMPACTION_PROMPT}]}
        if body.get('tools')!=[] or body.get('input',[])[-1:]!=[last]:raise ValueError('invalid_checkpoint_request')
    elif body.get('tools')!=TEMPLATE['tools']:raise ValueError('tool_contract_changed')
    for item in body.get('input',[]):
        if item.get('role') in {'developer','system'}:raise ValueError('extra_instructions_forbidden')
        if item.get('type')=='additional_tools':raise ValueError('additional_tools_forbidden')
        if item.get('type')=='function_call' and (item.get('name') not in NAMES or item.get('namespace') is not None):
            raise ValueError('undeclared_history_tool')
    return deepcopy(body)

def make_request(prompt,deployment):
    """Create a fresh conversation with the exact supplied task and skill text."""
    body=deepcopy(TEMPLATE)
    body['model']=deployment['model']
    for field in ['reasoning','temperature','top_p','seed','include','text']:
        if field in deployment:
            if deployment[field] is None:body.pop(field,None)
            else:body[field]=deepcopy(deployment[field])
    body['prompt_cache_key']=str(uuid.uuid4())
    body['input']=[{'type':'message','role':'user','content':[{'type':'input_text','text':prompt}]}]
    return to_provider(body)
