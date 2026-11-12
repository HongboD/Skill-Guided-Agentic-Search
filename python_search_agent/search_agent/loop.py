"""Maintain ordered model history, dispatch three tools, and checkpoint context."""
from copy import deepcopy
import contextlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import sys
import uuid
REPAIR = 'The required finish output is missing. Use finish with one to three valid query IDs from this session. This is the only output-format repair. Keep the same task and strategy.'
TOOLS = {'search', 'open', 'finish'}
SUMMARY_PREFIX = 'Another language model started to solve this problem and produced a summary of its thinking process. You also have access to the state of the tools that were used by that language model. Use this to build on the work that has already been done and avoid duplicating work. Here is the summary produced by the other language model, use the information in this summary to assist with your own analysis:\n'

def emit(value):
    """Send one JSON event to the trusted controller."""
    print(json.dumps(value, ensure_ascii=False, allow_nan=False), flush=True)

def receive():
    """Read one controller message from standard input."""
    line = sys.stdin.readline()
    if not line:
        raise RuntimeError('controller_closed')
    return json.loads(line)

def history_items(response):
    """Retain continuation data and tool calls; omit response item metadata."""
    items = [{k: deepcopy(v) for k, v in item.items() if k not in {'id', 'status'}} for item in response['output']]
    for item in items:
        for part in item.get('content') or []:
            if isinstance(part, dict) and part.get('type') == 'output_text':
                for key in ('annotations', 'logprobs'):
                    if part.get(key) == []:
                        part.pop(key)
    return items

class ResponsesSDK:
    """Send exact Responses payloads through LiteLLM to a session-local relay."""

    def __init__(self, endpoint):
        if importlib.metadata.version('litellm') != '1.105.0':
            raise RuntimeError('pinned_litellm_version_required')
        os.environ.update(LITELLM_LOCAL_MODEL_COST_MAP='True', LITELLM_TELEMETRY='False', DO_NOT_TRACK='1', PYTHON_DOTENV_DISABLED='1')
        with contextlib.redirect_stdout(sys.stderr):
            import litellm
            import httpx
        self.sdk, self.httpx, self.endpoint = (litellm, httpx, endpoint)
        self.registered_models = set()
        self.client = httpx.Client(timeout=None, trust_env=False, follow_redirects=False, transport=httpx.HTTPTransport(retries=0))
        litellm.client_session = self.client
        litellm.drop_params, litellm.num_retries, litellm.cache = (False, 0, None)
        litellm.callbacks = []
        litellm.input_callback = []
        litellm.success_callback = []
        litellm.failure_callback = []
        litellm.telemetry, litellm.set_verbose, litellm.suppress_debug_info = (False, False, True)
        for name in ('LiteLLM', 'LiteLLM Router', 'LiteLLM Proxy', 'httpx', 'httpcore', 'openai'):
            logging.getLogger(name).setLevel(logging.CRITICAL)

    def generate(self, body):
        """Validate the SDK payload and return one complete provider response."""
        model = 'openai/' + body['model']
        if model not in self.registered_models:
            self.sdk.register_model({model: {'litellm_provider': 'openai', 'mode': 'responses', 'supports_native_streaming': True}})
            self.registered_models.add(model)
        original = self.httpx.Client.send
        observed, completed = ([], [])

        def guarded(client, request, *args, **kwargs):
            if request.method != 'POST' or str(request.url) != self.endpoint + '/responses':
                raise RuntimeError('unexpected_http_destination')
            actual = json.loads(request.read())
            if actual != body:
                differences = sorted((k for k in set(actual) | set(body) if actual.get(k) != body.get(k)))
                raise RuntimeError('sdk_changed_frozen_payload:' + ','.join(differences))
            if observed:
                raise RuntimeError('sdk_retry_blocked')
            observed.append(actual)
            response = original(client, request, *args, **kwargs)
            raw = response.read().decode('utf-8')
            for line in raw.splitlines():
                if line.startswith('data:') and line[5:].strip() != '[DONE]':
                    event = json.loads(line[5:])
                    if event.get('type') == 'response.completed':
                        completed.append(event['response'])
            return response
        self.httpx.Client.send = guarded
        try:
            extra = {k: deepcopy(v) for k, v in body.items() if k not in {'model', 'input'}}
            with contextlib.redirect_stdout(sys.stderr):
                stream = self.sdk.responses(model='openai/' + body['model'], input=deepcopy(body['input']), api_base=self.endpoint, api_key='session-local-relay-no-provider-credential', extra_body=extra, stream=True, num_retries=0, max_retries=0, caching=False, drop_params=False, timeout=None)
                for _ in stream:
                    pass
        finally:
            self.httpx.Client.send = original
        if len(observed) != 1 or len(completed) != 1:
            raise RuntimeError('complete_provider_response_required')
        return completed[0]

def run(initial, generate, dispatch, record=emit, *, context_policy=None, checkpoint=None):
    """Run until valid finish and normal completion; allow one output-format repair."""
    body = deepcopy(initial)
    seen, turns, repairs, finished = (set(), 0, 0, False)
    compactions, estimated_tokens = (0, 0)
    policy = context_policy or {}
    while True:
        if policy.get('mode') == 'python_checkpoint_v1' and (not finished) and (estimated_tokens >= policy['trigger_tokens']):
            if checkpoint is None:
                raise RuntimeError('checkpoint_controller_required')
            compactions += 1
            checkpoint(compactions)
            summary_request = deepcopy(body)
            summary_request.update(tools=[], parallel_tool_calls=False)
            summary_request['input'].append({'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': policy['summary_prompt']}]})
            turns += 1
            summary_response = generate(summary_request)
            if summary_response.get('status') != 'completed' or summary_response.get('error') or any((x.get('type') not in {'reasoning', 'message'} for x in summary_response.get('output', []))):
                raise RuntimeError('invalid_context_summary_response')
            text = '\n'.join((part['text'] for item in summary_response.get('output', []) if item.get('type') == 'message' and item.get('role') == 'assistant' for part in item.get('content', []) if part.get('type') == 'output_text'))
            if not text.strip():
                raise RuntimeError('empty_context_summary')
            record({'event': 'model_response', 'model_call': turns, 'request_kind': 'python_compaction', 'response': summary_response})
            body = deepcopy(initial)
            body['input'].append({'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': SUMMARY_PREFIX + text}]})
            record({'event': 'context_checkpoint_applied', 'checkpoint': compactions})
            estimated_tokens = 0
        turns += 1
        response = generate(deepcopy(body))
        if response.get('status') != 'completed' or response.get('error'):
            raise RuntimeError('model_response_not_complete')
        items = response.get('output')
        if not isinstance(items, list) or any((x.get('type') not in {'reasoning', 'message', 'function_call'} for x in items)):
            raise RuntimeError('undeclared_model_output')
        calls = [x for x in items if x['type'] == 'function_call']
        batch = set()
        for call in calls:
            ident = call.get('call_id')
            if call.get('name') not in TOOLS or call.get('namespace') is not None:
                raise RuntimeError('undeclared_tool')
            if not isinstance(ident, str) or not ident or ident in seen or (ident in batch):
                raise RuntimeError('duplicate_or_missing_call_id')
            batch.add(ident)
        seen.update(batch)
        record({'event': 'model_response', 'model_call': turns, 'response': response})
        body['input'].extend(history_items(response))
        usage = response.get('usage') or {}
        estimated_tokens = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
        if calls:
            for call in calls:
                delivered = dispatch(call)
                if delivered['call_id'] != call['call_id']:
                    raise RuntimeError('tool_result_id_mismatch')
                text = delivered['text']
                result = json.loads(text)
                if call['name'] == 'finish' and result.get('ok') is True and (result.get('finished') is True):
                    finished = True
                body['input'].append({'type': 'function_call_output', 'id': 'fco_' + uuid.uuid4().hex, 'call_id': call['call_id'], 'output': text})
                estimated_tokens += (len(text.encode('utf-8')) + 3) // 4
            continue
        if finished:
            return {'status': 'PASS', 'model_calls': turns, 'schema_repairs': repairs, 'context_policy': policy.get('mode', 'python_full_history'), 'automatic_compactions': compactions}
        if repairs:
            raise RuntimeError('finish_missing_after_single_schema_repair')
        repairs += 1
        body['input'].append({'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': REPAIR}]})
        record({'event': 'schema_repair', 'text': REPAIR})

def main():
    """Verify the worker boundary and connect the loop to its private relay."""
    initial = receive()
    emit({'event': 'sandbox_probe',
          'forbidden_paths_visible': [p for p in initial.get('forbidden_paths', []) if Path(p).exists()],
          'credential_environment_present': any(k in os.environ for k in
              ('SEARCH_API_KEY','OPENAI_API_KEY','DEEPSEEK_API_KEY','ANTHROPIC_API_KEY','GOOGLE_API_KEY')),
          'cwd': os.getcwd(), 'litellm': importlib.metadata.version('litellm')})
    transport = ResponsesSDK(initial['endpoint'])

    def dispatch(call):
        emit({'event': 'tool_call', 'call': call})
        return receive()

    def checkpoint(number):
        emit({'event': 'context_checkpoint_requested', 'checkpoint': number})
        if receive() != {'checkpoint_authorized': number}:
            raise RuntimeError('checkpoint_not_authorized')
    try:
        emit({'event': 'agent_complete', **run(initial['request'], transport.generate, dispatch, context_policy=initial.get('context_policy'), checkpoint=checkpoint)})
    finally:
        transport.client.close()
if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        emit({'event': 'agent_failed', 'reason': type(error).__name__ + ':' + str(error)})
        raise SystemExit(1)
