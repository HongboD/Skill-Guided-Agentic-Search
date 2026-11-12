"""Run and validate one isolated Python search session."""
import json,queue,subprocess,threading,time
from pathlib import Path
from .records import read,append,dump,timestamp
from .session import render_response
from .policy import to_provider
from .gateway import Gateway
from .sandbox import sandbox_command
def _arguments(value):
    """Decode the provider's JSON arguments without changing their content."""
    return json.loads(value) if isinstance(value,str) else value

def execute_loop(directory, request, session, account, *, fixture_url=None, maximum_seconds=None, context_policy=None, venv=None):
    """Run a sandboxed loop and verify every requested and delivered tool result."""
    directory = Path(directory)
    events, delivery, complete, process = ([], [], None, None)
    started = time.monotonic()
    with Gateway(directory, account, fixture_url=fixture_url) as gateway:
        with (directory / 'python_stderr.log').open('w', encoding='utf-8') as err:
            process = subprocess.Popen(sandbox_command(directory, venv), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True, encoding='utf-8', bufsize=1)
            messages = queue.Queue()

            def drain():
                for line in process.stdout:
                    messages.put(line)
                messages.put(None)
            threading.Thread(target=drain, daemon=True).start()
            if context_policy:
                dump(directory / 'context_policy.json', context_policy)
            process.stdin.write(json.dumps({'endpoint': gateway.url, 'request': request, 'context_policy': context_policy, 'forbidden_paths': [str(directory), str(Path(__file__).resolve().parents[1]), str(session.backend.index_path)]}, ensure_ascii=False) + '\n')
            process.stdin.flush()
            try:
                while True:
                    if maximum_seconds is not None and time.monotonic() - started > maximum_seconds:
                        raise RuntimeError('supervisor_session_time_limit')
                    try:
                        line = messages.get(timeout=5)
                    except queue.Empty:
                        dump(directory / 'WORKER_HEARTBEAT.json', {'status': 'RUNNING', 'time': timestamp()})
                        continue
                    if line is None:
                        break
                    row = json.loads(line)
                    row['time'] = timestamp()
                    append(directory / 'python_events.jsonl', row)
                    events.append(row)
                    if row['event'] == 'sandbox_probe':
                        if (row['forbidden_paths_visible'] or row['credential_environment_present']):
                            raise RuntimeError('sandbox_isolation_failed')
                    elif row['event'] == 'context_checkpoint_requested':
                        if not context_policy or context_policy['mode'] != 'python_checkpoint_v1':
                            raise RuntimeError('context_checkpoint_not_enabled')
                        gateway.authorize_checkpoint(row['checkpoint'])
                        process.stdin.write(json.dumps({'checkpoint_authorized': row['checkpoint']}) + '\n')
                        process.stdin.flush()
                    elif row['event'] == 'tool_call':
                        call = row['call']
                        if call.get('name') not in {'search', 'open', 'finish'}:
                            raise RuntimeError('undeclared_tool')
                        arguments = _arguments(call.get('arguments'))
                        response = session.dispatch(call['name'], arguments, call['call_id'])
                        text = render_response(response)
                        supplied = {'call_id': call['call_id'], 'text': text}
                        process.stdin.write(json.dumps(supplied, ensure_ascii=False) + '\n')
                        process.stdin.flush()
                        record = {'call_id': call['call_id'], 'tool': call['name'], 'arguments': arguments, 'actual_returned_text': text, 'success': response.get('ok') is True, 'transport_write_succeeded': True, 'time': timestamp()}
                        append(directory / 'tool_delivery.jsonl', record)
                        delivery.append(record)
                    elif row['event'] == 'agent_failed':
                        raise RuntimeError(row['reason'])
                    elif row['event'] == 'agent_complete':
                        complete = row
                process.wait(timeout=15)
                if process.returncode or complete is None or (not session.finalized):
                    raise RuntimeError('python_agent_did_not_complete')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
    responses = [x['response'] for x in events if x['event'] == 'model_response']
    calls = [c for r in responses for c in r['output'] if c['type'] == 'function_call']
    session_rows = [json.loads(x) for x in (directory / 'session_events.jsonl').read_text(encoding='utf-8').splitlines()]
    intents = [x for x in session_rows if x['event'] == 'tool_intent']
    results = [x for x in session_rows if x['event'] == 'tool_result']
    errors = []
    if len([x for x in events if x['event'] == 'sandbox_probe']) != 1:
        errors.append('sandbox_probe_missing_or_duplicate')
    if not responses or any((c['type'] == 'function_call' for c in responses[-1]['output'])):
        errors.append('incomplete_model_history')
    if [x['call_id'] for x in calls] != [x['call_id'] for x in delivery] or len(calls) != len(intents) or len(intents) != len(results):
        errors.append('call_reconciliation')
    for call, item, result, intent in zip(calls, delivery, results, intents):
        if _arguments(call.get('arguments')) != item['arguments'] or item['arguments'] != intent['arguments'] or item['actual_returned_text'] != result['actual_returned_text']:
            errors.append('tool_data_changed')
    requested_outputs = {item['call_id']: item['actual_returned_text'] for item in delivery}
    observed_outputs = set()
    request_count = 0
    with (directory / 'requests.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            req = json.loads(line)
            request_count += 1
            compact = req.get('tools') == []
            to_provider(req, compaction=compact)
            expected_settings = {k: v for k, v in request.items() if k != 'input'}
            if compact:
                expected_settings.update(tools=[], parallel_tool_calls=False)
            if {k: v for k, v in req.items() if k != 'input'} != expected_settings:
                errors.append('request_settings_changed')
            if req['input'][:len(request['input'])] != request['input']:
                errors.append('initial_instructions_or_prompt_changed')
            for item in req['input']:
                if item.get('type') == 'function_call_output':
                    ident = item.get('call_id')
                    if item.get('output') != requested_outputs.get(ident):
                        errors.append('tool_output_changed')
                    observed_outputs.add(ident)
    if observed_outputs != set(requested_outputs):
        errors.append('tool_output_not_delivered')
    if request_count != len(responses):
        errors.append('incomplete_model_history')
    transport = read(directory / 'transport_audit.json')
    if transport['status'] != 'PASS':
        errors.append('transport_failed')
    audit = {'ok': not errors, 'errors': sorted(set(errors)), 'model_calls': request_count, 'tool_calls': len(calls), 'full_initial_prefix_preserved': not errors, 'request_settings_preserved': not errors, 'max_input_tokens': max((r.get('usage', {}).get('input_tokens', 0) for r in responses)), 'automatic_compactions': complete.get('automatic_compactions', 0), 'tool_output_truncations': 0}
    dump(directory / 'trajectory_audit.json', audit)
    if errors:
        raise RuntimeError('trajectory_validation_failed:' + ','.join(audit['errors']))
    usage = {k: sum((r.get('usage', {}).get(k, 0) for r in responses)) for k in ('input_tokens', 'output_tokens', 'total_tokens')}
    usage['cached_input_tokens'] = sum((r.get('usage', {}).get('input_tokens_details', {}).get('cached_tokens', 0) for r in responses))
    usage['reasoning_output_tokens'] = sum((r.get('usage', {}).get('output_tokens_details', {}).get('reasoning_tokens', 0) for r in responses))
    return {**complete, 'trajectory_audit': audit, 'usage': usage, 'provider_user': gateway.provider_user, 'provider_models': sorted(gateway.models), 'agent': 'Common Python loop + LiteLLM 1.105.0'}
