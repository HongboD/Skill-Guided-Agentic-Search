"""Keep credentials in the controller and deliver complete Responses events."""
from copy import deepcopy
from contextlib import contextmanager
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import IncompleteRead, RemoteDisconnected
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import errno,json,socket,ssl,tempfile,threading,time,uuid
from .records import dump,timestamp
from .policy import to_provider,POLICY_VERSION,COMPACTION_PROMPT,NAMES
INTERRUPTED_RETRY_WAIT_SECONDS=15
RETRYABLE_HTTP_STATUSES=frozenset({500,502,503,504})
MAX_HTTP_RETRY_WAIT_SECONDS=60
def isolated_request(body, user):
    """Add only the provider cache/scheduling identity, never model context."""
    if not isinstance(user, str) or not user.startswith('wsdm27_run_') or len(user) != 43 or any((c not in '0123456789abcdef' for c in user[11:])):
        raise ValueError('invalid_session_provider_user')
    if 'user' in body or 'user_id' in body:
        raise ValueError('unexpected_provider_user')
    return {**body, 'user': user}

class ProviderToolViolation(ValueError):
    """Reject this model session without declaring an account-wide outage."""

    def __init__(self, message, tool=None):
        super().__init__(message)
        self.tool = tool

def from_provider(event, *, compaction=False):
    """Validate provider tool calls without changing the response."""
    value = deepcopy(event)

    def visit(item):
        if isinstance(item, dict):
            kind = item.get('type', '')
            if kind in {'web_search_call', 'custom_tool_call', 'tool_search_call', 'computer_call', 'mcp_call'}:
                raise ProviderToolViolation('provider_returned_forbidden_tool', kind)
            if kind == 'function_call':
                if compaction:
                    raise ProviderToolViolation('compaction_returned_tool_call', item.get('name'))
                name = item.get('name')
                if name not in NAMES:
                    raise ProviderToolViolation('provider_returned_unknown_function', name)
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
    visit(value)
    return value

class NoRedirects(HTTPRedirectHandler):

    def redirect_request(self, *args, **kwargs):
        raise ValueError('provider_redirect_not_allowed')

class InterruptedStream(Exception):
    """A transient transport failure before any model event was delivered."""

    def __init__(self, message, *, retry_wait_seconds=INTERRUPTED_RETRY_WAIT_SECONDS):
        super().__init__(message)
        self.retry_wait_seconds = retry_wait_seconds

def http_retry_wait(headers, *, now=None):
    """Honor a short Retry-After; retain admission hold for a longer outage."""
    value = (headers or {}).get('Retry-After', '').strip()
    delay = INTERRUPTED_RETRY_WAIT_SECONDS
    if value:
        try:
            seconds = int(value) if value.isdigit() else parsedate_to_datetime(value).timestamp() - (time.time() if now is None else now)
            delay = max(delay, seconds)
        except (ValueError, TypeError, OverflowError):
            pass
    return delay if delay <= MAX_HTTP_RETRY_WAIT_SECONDS else None

def transient_connection_error(error):
    """Recognize connection failures before HTTP headers, without retrying refusals by HTTP status."""
    if isinstance(error, HTTPError):
        return False
    cause = error.reason if isinstance(error, URLError) else error
    return isinstance(cause, (TimeoutError, RemoteDisconnected, ssl.SSLEOFError)) or (isinstance(cause, OSError) and cause.errno in {errno.ECONNREFUSED, errno.ECONNRESET, errno.ECONNABORTED, errno.ETIMEDOUT, errno.EHOSTUNREACH, errno.ENETUNREACH, socket.EAI_AGAIN})

@contextmanager
def response_keepalive(progress, interval=10):
    """Send SSE comments during blocked upstream reads; never send model events."""
    stopped = threading.Event()
    errors = []
    progress()

    def pulse():
        while not stopped.wait(interval):
            try:
                progress()
            except Exception as error:
                errors.append(error)
                return
    thread = threading.Thread(target=pulse, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join()
    if errors:
        raise errors[0]

class Gateway:
    """Own one isolated provider identity and one private HTTP endpoint."""
    def __init__(self, directory, account, *, fixture_url=None):
        self.directory, self.account = (Path(directory), account)
        self.fixture = fixture_url is not None
        if self.fixture and urlsplit(fixture_url).hostname != '127.0.0.1':
            raise ValueError('fixture_must_be_loopback')
        self.upstream = fixture_url or account.endpoint
        self.errors, self.requests, self.completed = ([], 0, 0)
        self.api_attempts, self.retries, self.interrupted_attempts = (0, 0, 0)
        self.models = set()
        self.rejected_tools = set()
        self.request_kinds = {'search_agent': 0, 'python_compaction': 0}
        self.route = '/' + uuid.uuid4().hex
        self.provider_user = 'wsdm27_run_' + uuid.uuid4().hex
        self.lock = threading.Lock()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.python_checkpoint = None
        self.last_python_checkpoint = 0

    def record(self, name, value):
        with self.lock, (self.directory / name).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + '\n')

    def _receive_complete(self, request, buffer, *, compaction, progress):
        """Retry one interrupted response before any model event is delivered.

            Transient connection errors before HTTP headers, malformed JSON after
            response.created, and an unterminated first data line at EOF use the
            same one request retry. HTTP 500/502/503/504 also use that shared retry.
            Other HTTP refusals, complete
            malformed initial frames, tool violations, and explicit failed or
            incomplete responses are not retried. A retry reuses the exact Request
            bytes. No partial function call can enter the trajectory.
            """
        retry_wait = INTERRUPTED_RETRY_WAIT_SECONDS
        for attempt in (1, 2):
            buffer.seek(0)
            buffer.truncate()
            if attempt == 2:
                self.retries += 1
                time.sleep(retry_wait)
                progress()
            self.api_attempts += 1
            row = {'request_number': self.requests, 'attempt': attempt, 'started_at_utc': timestamp(), 'retry_wait_seconds': retry_wait if attempt == 2 else 0, 'received_bytes': 0, 'event_count': 0, 'last_event_type': None, 'last_response_status': None, 'done_marker_seen': False, 'response_created_seen': False}
            try:
                try:
                    response = build_opener(NoRedirects()).open(request, timeout=300)
                except HTTPError as error:
                    row['http_status'] = error.code
                    delay = http_retry_wait(error.headers) if error.code in RETRYABLE_HTTP_STATUSES else None
                    if delay is not None:
                        error.close()
                        raise InterruptedStream('provider_http_' + str(error.code), retry_wait_seconds=delay) from None
                    raise
                except (URLError, OSError) as error:
                    if transient_connection_error(error):
                        cause = error.reason if isinstance(error, URLError) else error
                        raise InterruptedStream('provider_connection_' + type(cause).__name__) from None
                    raise
                with response:
                    if 'text/event-stream' not in response.headers.get('Content-Type', ''):
                        raise ValueError('provider_did_not_stream')
                    progress()
                    lines = iter(response)
                    while True:
                        try:
                            raw = next(lines)
                        except StopIteration:
                            raise InterruptedStream('provider_stream_missing_terminal_event') from None
                        except (IncompleteRead, RemoteDisconnected, ConnectionResetError, TimeoutError, ssl.SSLEOFError) as error:
                            raise InterruptedStream(type(error).__name__) from None
                        progress()
                        row['received_bytes'] += len(raw)
                        line = raw.decode('utf-8').rstrip('\r\n')
                        if not line.startswith('data:'):
                            continue
                        data = line[5:].strip()
                        if data == '[DONE]':
                            row['done_marker_seen'] = True
                            continue
                        if not data:
                            continue
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError as error:
                            row['json_error'] = {'message': error.msg, 'position': error.pos, 'frame_bytes': len(raw), 'frame_ended_with_newline': raw.endswith(b'\n')}
                            if row['response_created_seen']:
                                raise InterruptedStream('provider_malformed_json_event') from None
                            if not raw.endswith(b'\n'):
                                raise InterruptedStream('provider_truncated_initial_json_event') from None
                            raise
                        row['event_count'] += 1
                        row['last_event_type'] = event.get('type')
                        if event.get('type') == 'response.created':
                            row['response_created_seen'] = True
                        if isinstance(event.get('response'), dict):
                            row['last_response_status'] = event['response'].get('status')
                        if event.get('error'):
                            raise ValueError('provider_error_frame')
                        try:
                            from_provider(event, compaction=compaction)
                        except ProviderToolViolation as error:
                            self.rejected_tools.add(str(error.tool or '<unnamed>')[:128])
                            self.record('rejected_provider_events.jsonl', {'request_number': self.requests, 'attempt': attempt, 'time': timestamp(), 'reason': str(error), 'compaction': compaction, 'event': event})
                            raise
                        if event.get('type') in {'response.failed', 'response.incomplete', 'error'}:
                            raise ValueError('provider_response_not_completed')
                        buffer.write(json.dumps(event, ensure_ascii=False) + '\n')
                        if event.get('type') == 'response.completed':
                            row.update(status='COMPLETED', completed_at_utc=timestamp())
                            self.record('transport_api_attempts.jsonl', row)
                            buffer.seek(0)
                            return (event.get('response') or {}).get('model')
            except InterruptedStream as error:
                retry_wait = error.retry_wait_seconds
                self.interrupted_attempts += 1
                row.update(status='INTERRUPTED', reason=str(error), ended_at_utc=timestamp(), usage_available=False, model_events_delivered=False)
                self.record('transport_api_attempts.jsonl', row)
                if attempt == 2:
                    raise
            except Exception as error:
                reason = 'provider_http_' + str(error.code) if isinstance(error, HTTPError) else type(error).__name__
                self.record('transport_api_attempts.jsonl', {**row, 'status': 'FAILED', 'reason': reason, 'ended_at_utc': timestamp(), 'model_events_delivered': False})
                raise

    def receive_complete(self, *args, **kwargs):
        try:
            return self._receive_complete(*args, **kwargs)
        except HTTPError as error:
            category = 'provider_http_' + str(error.code)
            safe_detail = {}
            try:
                payload = json.loads(error.read(65536))
                detail = payload.get('error', payload) if isinstance(payload, dict) else payload
                if isinstance(detail, str):
                    detail = {'message': detail}
                if isinstance(detail, dict):
                    code = str(detail.get('code', '')).lower()
                    message = str(detail.get('message', '')).lower()
                    if 'context' in code or ('context' in message and any((x in message for x in ['length', 'maximum', 'limit']))):
                        category = 'provider_context_length_exceeded'
                    for field in ['code', 'type', 'message', 'param']:
                        if field in detail and isinstance(detail[field], (str, int)):
                            value = str(detail[field])[:2000]
                            if self.account is not None:
                                value = value.replace(self.account.api_key(), '[credential removed]')
                            safe_detail[field] = value
            except (ValueError, TypeError, AttributeError, OSError):
                pass
            dump(self.directory / 'provider_failure.json', {'http_status': error.code, 'category': category, 'provider_error': safe_detail})
            raise

    def __enter__(self):
        """Serve a private relay that validates all requests and complete responses."""
        gateway = self

        class Handler(BaseHTTPRequestHandler):

            def log_message(self, *args):
                pass

            def do_POST(self):
                if self.path != gateway.route + '/responses':
                    self.send_error(404)
                    return
                headers_sent, last_keepalive = (False, 0)

                def progress():
                    nonlocal headers_sent, last_keepalive
                    if not headers_sent:
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/event-stream')
                        self.send_header('Connection', 'close')
                        self.end_headers()
                        headers_sent = True
                    if time.monotonic() - last_keepalive >= 10:
                        self.wfile.write(b': awaiting complete provider response\n\n')
                        self.wfile.flush()
                        last_keepalive = time.monotonic()
                try:
                    if self.headers.get('Content-Encoding'):
                        raise ValueError('request_compression_not_supported')
                    body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    gateway.record('requests.jsonl', body)
                    compaction = body.get('tools') == []
                    forwarded = isolated_request(to_provider(body, compaction=compaction), gateway.provider_user)
                    checkpoint = gateway.claim_compaction() if compaction else None
                    gateway.record('provider_requests.jsonl', forwarded)
                    gateway.requests += 1
                    kind = 'python_compaction' if compaction else 'search_agent'
                    gateway.request_kinds[kind] += 1
                    gateway.record('transport_request_kinds.jsonl', {'request_number': gateway.requests, 'kind': kind, 'checkpoint_event': checkpoint, 'time': timestamp()})
                    headers = {'Content-Type': 'application/json', 'Accept': 'text/event-stream'}
                    if not gateway.fixture:
                        headers['Authorization'] = 'Bearer ' + gateway.account.api_key()
                    request = Request(gateway.upstream, data=json.dumps(forwarded, ensure_ascii=False).encode(), headers=headers)
                    with tempfile.NamedTemporaryFile(mode='w+t', encoding='utf-8', prefix='.provider-response-', dir=gateway.directory) as buffer:
                        with response_keepalive(progress):
                            model = gateway.receive_complete(request, buffer, compaction=compaction, progress=lambda: None)
                        for line in buffer:
                            event = json.loads(line)
                            gateway.record('provider_events.jsonl', event)
                            self.wfile.write(('data: ' + line.strip() + '\n\n').encode())
                            self.wfile.flush()
                        if model:
                            gateway.models.add(model)
                        gateway.completed += 1
                except Exception as error:
                    reason = 'provider_http_' + str(error.code) if isinstance(error, HTTPError) else type(error).__name__ + ':' + str(error)
                    gateway.errors.append(reason)
                    if gateway.account is not None and (not isinstance(error, ProviderToolViolation)):
                        gateway.account.hold(reason)
                    if not headers_sent:
                        self.send_response(502)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(b'{"error":{"message":"Experiment transport failed; see controller log."}}')
                finally:
                    self.close_connection = True
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.url = f'http://127.0.0.1:{self.server.server_port}{self.route}'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def authorize_checkpoint(self, number):
        """Authorize exactly one zero-tool request for the next checkpoint."""
        if type(number) is not int or number != self.last_python_checkpoint + 1 or self.python_checkpoint is not None:
            raise ValueError('invalid_python_checkpoint_lifecycle')
        self.python_checkpoint = number
        self.last_python_checkpoint = number
        self.record('python_checkpoint_authorizations.jsonl', {'checkpoint': number, 'origin': 'trusted_python_controller', 'tools': []})

    def claim_compaction(self):
        """Consume a controller authorization before forwarding a summary."""
        if self.python_checkpoint is None:
            raise ValueError('empty_tools_without_python_checkpoint_authorization')
        number, self.python_checkpoint = (self.python_checkpoint, None)
        return {'origin': 'python_controller', 'checkpoint': number}

    def __exit__(self, *args):
        """Close the relay and record request, response, and tool validation counts."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        dump(self.directory/'transport_audit.json', {
            'status':'PASS' if not self.errors and self.requests and self.requests==self.completed else 'FAIL',
            'request_count':self.requests,'completed_responses':self.completed,
            'errors':self.errors,'provider_models':sorted(self.models),'tool_names':sorted(NAMES),
            'api_attempt_count':self.api_attempts,'automatic_retries':self.retries,
            'interrupted_api_attempts':self.interrupted_attempts,'request_kinds':self.request_kinds,
            'fixture_only':self.fixture,'provider_user':self.provider_user,
            'instruction_policy_version':POLICY_VERSION})
