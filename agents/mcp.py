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

from .models import McpToken
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


def _handle_message(message, user):
    """One JSON-RPC message -> response dict, or None for notifications."""
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


@csrf_exempt
def endpoint(request, token):
    access = McpToken.objects.filter(token=token, active=True).select_related('user').first()
    if access is None or not access.user.is_active:
        return JsonResponse({'error': 'invalid token'}, status=404)
    McpToken.objects.filter(pk=access.pk).update(last_used_at=timezone.now())

    if request.method == 'GET':
        return HttpResponse(status=405)   # no server-initiated stream
    if request.method == 'DELETE':
        return HttpResponse(status=202)   # stateless — nothing to tear down
    if request.method != 'POST':
        return HttpResponse(status=405)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(_rpc_error(None, -32700, 'Parse error'), status=400)

    user = access.user
    if isinstance(body, list):        # 2025-03-26 batch support
        responses = [r for r in (_handle_message(m, user) for m in body) if r is not None]
        if not responses:
            return HttpResponse(status=202)
        return JsonResponse(responses, safe=False)

    response = _handle_message(body, user)
    if response is None:              # notification (e.g. notifications/initialized)
        return HttpResponse(status=202)
    return JsonResponse(response)
