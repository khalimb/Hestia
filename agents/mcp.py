"""MCP streamable-HTTP endpoint (JSON-RPC 2.0 over POST), Django-native.

Ported from Hierophant's mcp_gateway: the subset a plain tool server needs
(initialize / ping / tools list + call), stateless — no session ids, no SSE
stream; one JSON response per POST is spec-conformant. The token in the
URL is the auth, and it resolves to a user so writes are attributed.
"""
import json

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from activity.context import activity_context

from .models import McpToken, McpSession
from .mcp_tools import TOOL_MAP, TOOLS, ToolError

SUPPORTED_PROTOCOL_VERSIONS = ('2024-11-05', '2025-03-26', '2025-06-18')
SERVER_INFO = {'name': 'hestia', 'version': '1.0.0'}
INSTRUCTIONS = (
    "Hestia — the household's recurring-expense tracker. Reads: dictionaries_get "
    '(call first for ids), expenses_list, expense_get, occurrences_list, '
    'assignment_get. Writes (tools marked WRITE): expense_create, expense_update, '
    'dictionary_create/update/delete, assignment_save. Confirm every write with '
    'the user before calling it, and never invent dictionary ids.'
)


def _rpc_error(message_id, code, message):
    return {'jsonrpc': '2.0', 'id': message_id, 'error': {'code': code, 'message': message}}


def _handle_message(message, user, state):
    """One JSON-RPC message -> response dict, or None for notifications.

    `state` is a per-request dict: {'token', 'session'}. `initialize` creates
    a session and stores it there so the endpoint can emit Mcp-Session-Id.
    """
    if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
        return _rpc_error(None, -32600, 'Invalid Request')
    method = message.get('method', '')
    if 'id' not in message:          # notification — no response
        return None
    message_id = message['id']
    params = message.get('params') or {}

    if method == 'initialize':
        requested = params.get('protocolVersion')
        version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS \
            else SUPPORTED_PROTOCOL_VERSIONS[-1]
        client = params.get('clientInfo') or {}
        state['session'] = McpSession.objects.create(
            token=state['token'], protocol_version=version,
            client_name=str(client.get('name', ''))[:100],
            client_version=str(client.get('version', ''))[:50],
        )
        state['new_session'] = True
        result = {'protocolVersion': version,
                  'capabilities': {'tools': {}},
                  'serverInfo': SERVER_INFO,
                  'instructions': INSTRUCTIONS}
    elif method == 'ping':
        result = {}
    elif method == 'tools/list':
        result = {'tools': [{'name': t['name'], 'description': t['description'],
                             'inputSchema': t['inputSchema']} for t in TOOLS]}
    elif method == 'tools/call':
        tool = TOOL_MAP.get(params.get('name'))
        if tool is None:
            return _rpc_error(message_id, -32602, f"Unknown tool: {params.get('name')!r}")
        arguments = params.get('arguments') or {}
        session = state.get('session')
        if session is not None:
            session.note_tool_call(tool['name'])
        try:
            payload = tool['handler'](arguments, user)
            result = {'content': [{'type': 'text',
                                   'text': json.dumps(payload, ensure_ascii=False, default=str)}],
                      'isError': False}
        except ToolError as e:
            result = {'content': [{'type': 'text', 'text': str(e)}], 'isError': True}
        except Exception as e:  # tool bug — surface it, never 500 the transport
            result = {'content': [{'type': 'text', 'text': f'{type(e).__name__}: {e}'}],
                      'isError': True}
    elif method in ('prompts/list', 'resources/list', 'resources/templates/list'):
        # Not advertised in capabilities; answered leniently for clients that probe.
        key = 'resourceTemplates' if method == 'resources/templates/list' \
            else method.split('/')[1]
        result = {key: []}
    else:
        return _rpc_error(message_id, -32601, f'Method not found: {method}')

    return {'jsonrpc': '2.0', 'id': message_id, 'result': result}


def _resolve_session(request, access):
    """The session the client echoes back via Mcp-Session-Id, if it is one
    of this token's. Lenient: a missing or unknown id just means the call
    is attributed to the token alone, never a refusal."""
    session_id = request.META.get('HTTP_MCP_SESSION_ID', '').strip()
    if not session_id:
        return None
    try:
        return McpSession.objects.filter(pk=session_id, token=access).first()
    except (ValueError, Exception):
        return None


@csrf_exempt
def endpoint(request, token):
    access = McpToken.objects.filter(token=token, active=True).select_related('user').first()
    if access is None or not access.user.is_active:
        return JsonResponse({'error': 'invalid token'}, status=404)
    McpToken.objects.filter(pk=access.pk).update(last_used_at=timezone.now())

    if request.method == 'GET':
        return HttpResponse(status=405)   # no server-initiated stream
    if request.method == 'DELETE':
        session = _resolve_session(request, access)
        if session is not None and session.ended_at is None:
            session.ended_at = timezone.now()
            session.save(update_fields=['ended_at', 'last_seen_at'])
        return HttpResponse(status=202)   # stateless transport — nothing else to tear down
    if request.method != 'POST':
        return HttpResponse(status=405)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(_rpc_error(None, -32700, 'Parse error'), status=400)

    user = access.user
    state = {'token': access, 'session': _resolve_session(request, access)}
    messages = body if isinstance(body, list) else [body]
    responses = []
    with activity_context(actor=user, source='mcp', token=access, session=state['session']):
        for message in messages:
            # Re-enter the context when initialize minted a session mid-batch,
            # so writes in the same batch are attributed to it.
            with activity_context(actor=user, source='mcp', token=access,
                                  session=state['session']):
                rendered = _handle_message(message, user, state)
            if rendered is not None:
                responses.append(rendered)

    session = state.get('session')
    if session is not None:
        session.request_count += 1
        session.save(update_fields=['request_count', 'tool_calls', 'last_seen_at'])

    if not responses:                 # notification(s) only, e.g. notifications/initialized
        response = HttpResponse(status=202)
    elif isinstance(body, list):      # 2025-03-26 batch support
        response = JsonResponse(responses, safe=False)
    else:
        response = JsonResponse(responses[0])
    if state.get('new_session'):
        response['Mcp-Session-Id'] = str(session.id)
    return response
