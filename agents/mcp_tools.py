"""MCP tool registry for Hestia — thin wrappers over the same serializers the
REST API uses, so validation rules (e.g. account-only-with-qualifying-method)
and delete guards are never forked.

Every handler takes (args, user): `user` is the owner of the MCP token the
request came in on, and is recorded as created_by on anything the tool makes.
Read tools and WRITE tools are kept apart so the operator can leave reads on
"always allow" in the client while keeping writes prompting.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from expenses.models import (
    Subject, ExpenseType, PaymentMethod, PaymentAccount, Expense, Occurrence,
)
from expenses.serializers import (
    SubjectSerializer, ExpenseTypeSerializer, PaymentMethodSerializer,
    PaymentAccountSerializer, ExpenseSerializer, ExpenseDetailSerializer,
    OccurrenceSerializer,
)
from expenses.services import force_generate_occurrences
from activity.models import ActivityLog
from activity.services import delete_logged
from .models import Assignment


class ToolError(Exception):
    """User-facing tool failure (unknown id, bad argument, validation)."""


DICTIONARIES = {
    'subject': (Subject, SubjectSerializer),
    'expense_type': (ExpenseType, ExpenseTypeSerializer),
    'payment_method': (PaymentMethod, PaymentMethodSerializer),
    'payment_account': (PaymentAccount, PaymentAccountSerializer),
}
DICTIONARY_KINDS = list(DICTIONARIES)

EXPENSE_WRITABLE = (
    'name', 'description', 'subject', 'expense_type', 'amount', 'currency',
    'recurrence_type', 'payment_method', 'account', 'responsible',
    'start_date', 'end_date', 'is_active',
)


# ------------------------------------------------------------------ helpers

def _raise_validation(serializer):
    parts = []
    for field, messages in serializer.errors.items():
        if isinstance(messages, (list, tuple)):
            text = '; '.join(str(m) for m in messages)
        else:
            text = str(messages)
        parts.append(f'{field}: {text}')
    raise ToolError('validation failed — ' + ' | '.join(parts))


def _get_or_error(model, pk, label):
    try:
        return model.objects.get(pk=pk)
    except (model.DoesNotExist, ValidationError, ValueError, TypeError):
        # ValidationError: Django rejects a malformed UUID before querying.
        raise ToolError(f'unknown {label} id {pk!r}')


def _dictionary(kind):
    if kind not in DICTIONARIES:
        raise ToolError(f'kind must be one of {DICTIONARY_KINDS}, got {kind!r}')
    return DICTIONARIES[kind]


def _limit(args, default=50, maximum=200):
    try:
        return max(1, min(int(args.get('limit', default)), maximum))
    except (TypeError, ValueError):
        raise ToolError('limit must be an integer')


def _expense_card(data):
    """Token-lean projection of ExpenseSerializer output."""
    nxt = data.get('next_occurrence') or {}
    return {
        'id': data['id'], 'name': data['name'],
        'amount': data['amount'], 'currency': data['currency'],
        'recurrence_type': data['recurrence_type'],
        'subject': data.get('subject_name'),
        'expense_type': data.get('expense_type_name'),
        'payment_method': data.get('payment_method_name'),
        'account': data.get('account_name'),
        'responsible': data.get('responsible_name'),
        'start_date': data['start_date'], 'end_date': data.get('end_date'),
        'is_active': data['is_active'],
        'next_due': nxt.get('due_date'), 'next_status': nxt.get('status'),
    }


def _dictionary_row(kind, data):
    row = {'id': data['id'], 'name': data['name']}
    if kind == 'payment_method':
        row['requires_account'] = data['requires_account']
    if kind == 'payment_account':
        row['notes'] = data.get('notes', '')
    if 'is_default' in data:
        row['is_default'] = data['is_default']
    return row


def _occurrence_row(occ):
    data = OccurrenceSerializer(occ).data
    return {
        'id': data['id'], 'expense_id': data['expense'],
        'expense_name': data['expense_name'], 'due_date': data['due_date'],
        'expected_amount': data['expected_amount'], 'currency': data['currency'],
        'status': data['status'], 'total_paid': data['total_paid'],
    }


# ------------------------------------------------------------------ reads

def dictionaries_get(args, user):
    out = {}
    for kind, (model, serializer_cls) in DICTIONARIES.items():
        rows = serializer_cls(model.objects.order_by('name'), many=True).data
        out[kind + 's'] = [_dictionary_row(kind, r) for r in rows]
    out['users'] = [
        {'id': str(u.id), 'display_name': u.display_name}
        for u in get_user_model().objects.filter(is_active=True)
        .order_by('first_name', 'last_name')
    ]
    out['recurrence_types'] = [value for value, _ in Expense.RECURRENCE_CHOICES]
    out['default_currency'] = 'GBP'
    out['note'] = ('Use these ids in expense_create / expense_update. payment_methods '
                   'with requires_account=true may carry an account; others must not.')
    return out


def expenses_list(args, user):
    qs = Expense.objects.select_related(
        'subject', 'expense_type', 'payment_method', 'account', 'responsible',
    )
    is_active = args.get('is_active', True)
    if is_active is not None:
        qs = qs.filter(is_active=bool(is_active))
    for field in ('subject', 'expense_type', 'payment_method', 'account', 'responsible'):
        if args.get(field):
            qs = qs.filter(**{f'{field}_id': args[field]})
    search = str(args.get('search', '')).strip()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
    limit = _limit(args)
    try:
        rows = ExpenseSerializer(qs.order_by('name')[:limit], many=True).data
    except ValidationError as e:  # malformed uuid in a filter
        raise ToolError(f'bad filter: {e}')
    return {'count': len(rows), 'expenses': [_expense_card(r) for r in rows]}


def expense_get(args, user):
    expense = _get_or_error(Expense, args.get('expense_id'), 'expense')
    return ExpenseDetailSerializer(expense).data


def occurrences_list(args, user):
    qs = Occurrence.objects.select_related('expense', 'expense__payment_method')
    status = args.get('status', 'unpaid')
    if status == 'unpaid':
        qs = qs.filter(status__in=['pending', 'overdue'])
    elif status and status != 'all':
        if status not in dict(Occurrence.STATUS_CHOICES):
            raise ToolError("status must be one of unpaid, all, pending, paid, partial, overdue")
        qs = qs.filter(status=status)
    if args.get('expense_id'):
        qs = qs.filter(expense_id=args['expense_id'])
    today = timezone.now().date()
    date_from = args.get('date_from')
    date_to = args.get('date_to')
    if date_from:
        qs = qs.filter(due_date__gte=date_from)
    if date_to:
        qs = qs.filter(due_date__lte=date_to)
    if not date_from and not date_to and status == 'unpaid':
        # Sensible default window: everything overdue plus the next 60 days.
        qs = qs.filter(due_date__lte=today + timedelta(days=60))
    limit = _limit(args)
    try:
        rows = [_occurrence_row(o) for o in qs.order_by('due_date')[:limit]]
    except ValidationError as e:
        raise ToolError(f'bad filter: {e}')
    return {'today': today.isoformat(), 'count': len(rows), 'occurrences': rows}


def assignment_get(args, user):
    assignment = _get_or_error(Assignment, args.get('assignment_id'), 'assignment')
    return {
        'id': str(assignment.id), 'title': assignment.title,
        'status': assignment.status, 'summary': assignment.summary,
        'content': assignment.content,
        'started_at': assignment.started_at.isoformat(),
        'populated_at': assignment.populated_at.isoformat() if assignment.populated_at else None,
    }


def activity_recent(args, user):
    """Change log, newest first — what people and agents did."""
    qs = ActivityLog.objects.select_related('actor', 'token')
    try:
        days = int(args.get('days', 7))
    except (TypeError, ValueError):
        raise ToolError('days must be an integer')
    if days > 0:
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days))
    if args.get('entity_type'):
        qs = qs.filter(entity_type=args['entity_type'])
    if args.get('entity_id'):
        qs = qs.filter(entity_id=args['entity_id'])
    if args.get('source'):
        qs = qs.filter(source=args['source'])
    limit = _limit(args, default=50, maximum=200)
    try:
        rows = list(qs[:limit])
    except ValidationError as e:
        raise ToolError(f'bad filter: {e}')
    return {'count': len(rows), 'activity': [{
        'at': row.created_at.isoformat(timespec='minutes'),
        'who': row.actor.display_name if row.actor else None,
        'via': row.via, 'action': row.action,
        'entity_type': row.entity_type, 'entity_id': str(row.entity_id),
        'entity': row.entity_label, 'changes': row.changes,
    } for row in rows]}


# ------------------------------------------------------------------ writes

def _expense_fields(args):
    return {k: args[k] for k in EXPENSE_WRITABLE if k in args}


def expense_create(args, user):
    fields = _expense_fields(args)
    serializer = ExpenseSerializer(data=fields)
    if not serializer.is_valid():
        _raise_validation(serializer)
    expense = serializer.save(created_by=user)
    force_generate_occurrences()
    expense.refresh_from_db()
    return {'created': True, 'expense': _expense_card(ExpenseSerializer(expense).data)}


def expense_update(args, user):
    expense = _get_or_error(Expense, args.get('expense_id'), 'expense')
    fields = _expense_fields(args)
    if not fields:
        raise ToolError(f'nothing to update; writable fields: {list(EXPENSE_WRITABLE)}')
    serializer = ExpenseSerializer(expense, data=fields, partial=True)
    if not serializer.is_valid():
        _raise_validation(serializer)
    expense = serializer.save()
    force_generate_occurrences()
    expense.refresh_from_db()
    return {'updated': sorted(fields), 'expense': _expense_card(ExpenseSerializer(expense).data)}


def dictionary_create(args, user):
    kind = args.get('kind')
    model, serializer_cls = _dictionary(kind)
    serializer = serializer_cls(data={k: v for k, v in args.items() if k != 'kind'})
    if not serializer.is_valid():
        _raise_validation(serializer)
    obj = serializer.save(created_by=user)
    return {'created': True, 'kind': kind,
            'entry': _dictionary_row(kind, serializer_cls(obj).data)}


def dictionary_update(args, user):
    kind = args.get('kind')
    model, serializer_cls = _dictionary(kind)
    obj = _get_or_error(model, args.get('id'), kind)
    fields = {k: v for k, v in args.items() if k not in ('kind', 'id')}
    if not fields:
        raise ToolError('nothing to update')
    serializer = serializer_cls(obj, data=fields, partial=True)
    if not serializer.is_valid():
        _raise_validation(serializer)
    obj = serializer.save()
    return {'updated': sorted(fields), 'kind': kind,
            'entry': _dictionary_row(kind, serializer_cls(obj).data)}


def dictionary_delete(args, user):
    kind = args.get('kind')
    model, serializer_cls = _dictionary(kind)
    obj = _get_or_error(model, args.get('id'), kind)
    blocker = obj.deletion_blocker()
    if blocker:
        raise ToolError(blocker)
    name = obj.name
    delete_logged(serializer_cls, obj)
    return {'deleted': True, 'kind': kind, 'name': name}


def assignment_save(args, user):
    assignment = _get_or_error(Assignment, args.get('assignment_id'), 'assignment')
    content = str(args.get('content') or '').strip()
    if not content:
        raise ToolError('content is required (the deliverable markdown)')
    assignment.save_deliverable(
        title=str(args.get('title') or '').strip(),
        summary=str(args.get('summary') or '').strip(),
        content=content,
    )
    return {'saved': True, 'id': str(assignment.id), 'status': assignment.status,
            'title': assignment.title}


# ------------------------------------------------------------------ registry

_UUID = {'type': 'string', 'description': 'uuid'}
_DICT_KIND = {'type': 'string', 'enum': DICTIONARY_KINDS}
_EXPENSE_PROPS = {
    'name': {'type': 'string'},
    'description': {'type': 'string'},
    'amount': {'type': ['string', 'number'], 'description': 'e.g. "42.50"'},
    'currency': {'type': 'string', 'description': '3-letter ISO code, default GBP'},
    'recurrence_type': {'type': 'string',
                        'enum': [value for value, _ in Expense.RECURRENCE_CHOICES]},
    'start_date': {'type': 'string', 'description': 'YYYY-MM-DD; first due date'},
    'end_date': {'type': ['string', 'null'], 'description': 'YYYY-MM-DD or null'},
    'subject': {'type': ['string', 'null'], 'description': 'subject id or null'},
    'expense_type': {'type': ['string', 'null'], 'description': 'expense_type id or null'},
    'payment_method': {'type': ['string', 'null'], 'description': 'payment_method id or null'},
    'account': {'type': ['string', 'null'],
                'description': 'payment_account id; only when the method requires_account'},
    'responsible': {'type': ['string', 'null'], 'description': 'user id or null'},
    'is_active': {'type': 'boolean'},
}

TOOLS = [
    # --- read ---
    {'name': 'dictionaries_get',
     'description': 'All lookup lists in one call: subjects, expense types, payment '
                    'methods (with requires_account), payment accounts, household '
                    'users, recurrence types. Call this before creating or editing.',
     'inputSchema': {'type': 'object', 'properties': {}},
     'handler': dictionaries_get},
    {'name': 'expenses_list',
     'description': 'Recurring expenses as compact cards (names resolved, next due). '
                    'Filters by dictionary ids and a name/description search. '
                    'Active only by default; pass is_active=false for inactive, '
                    'null for all.',
     'inputSchema': {'type': 'object', 'properties': {
         'is_active': {'type': ['boolean', 'null'], 'default': True},
         'subject': _UUID, 'expense_type': _UUID, 'payment_method': _UUID,
         'account': _UUID, 'responsible': _UUID,
         'search': {'type': 'string'},
         'limit': {'type': 'integer', 'default': 50}}},
     'handler': expenses_list},
    {'name': 'expense_get',
     'description': 'Full record of one expense, including its recent occurrences '
                    '(due dates, expected vs paid, status).',
     'inputSchema': {'type': 'object', 'properties': {'expense_id': _UUID},
                     'required': ['expense_id']},
     'handler': expense_get},
    {'name': 'occurrences_list',
     'description': 'Scheduled payments (occurrences). status: unpaid (default: '
                    'pending+overdue, overdue plus next 60 days), all, pending, '
                    'paid, partial, overdue. Optional date window and expense_id.',
     'inputSchema': {'type': 'object', 'properties': {
         'status': {'type': 'string', 'default': 'unpaid'},
         'expense_id': _UUID,
         'date_from': {'type': 'string', 'description': 'YYYY-MM-DD'},
         'date_to': {'type': 'string', 'description': 'YYYY-MM-DD'},
         'limit': {'type': 'integer', 'default': 50}}},
     'handler': occurrences_list},
    {'name': 'assignment_get',
     'description': 'One assignment doc: topic, status, summary, saved content.',
     'inputSchema': {'type': 'object', 'properties': {'assignment_id': _UUID},
                     'required': ['assignment_id']},
     'handler': assignment_get},
    {'name': 'activity_recent',
     'description': 'Change log, newest first: who changed what, through which door '
                    '(web, MCP client, agent import), with before/after values. '
                    'Defaults to the last 7 days; days=0 for all time. Filter by '
                    'entity_type, entity_id, source (web | mcp | import).',
     'inputSchema': {'type': 'object', 'properties': {
         'days': {'type': 'integer', 'default': 7},
         'entity_type': {'type': 'string'}, 'entity_id': _UUID,
         'source': {'type': 'string', 'enum': ['web', 'mcp', 'import', 'system']},
         'limit': {'type': 'integer', 'default': 50}}},
     'handler': activity_recent},
    # --- write ---
    {'name': 'expense_create',
     'description': 'WRITE: create a recurring expense. Validates like the API: '
                    'account only with a method that requires_account. Occurrences '
                    'are generated immediately.',
     'inputSchema': {'type': 'object', 'properties': _EXPENSE_PROPS,
                     'required': ['name', 'amount', 'recurrence_type', 'start_date']},
     'handler': expense_create},
    {'name': 'expense_update',
     'description': 'WRITE: partial update of an expense (any subset of the create '
                    'fields). Set is_active=false to deactivate instead of deleting.',
     'inputSchema': {'type': 'object',
                     'properties': {'expense_id': _UUID, **_EXPENSE_PROPS},
                     'required': ['expense_id']},
     'handler': expense_update},
    {'name': 'dictionary_create',
     'description': 'WRITE: add a dictionary entry. kind: subject | expense_type | '
                    'payment_method (name, requires_account) | payment_account '
                    '(name, notes). Names are unique per kind.',
     'inputSchema': {'type': 'object', 'properties': {
         'kind': _DICT_KIND, 'name': {'type': 'string'},
         'requires_account': {'type': 'boolean'}, 'notes': {'type': 'string'}},
                     'required': ['kind', 'name']},
     'handler': dictionary_create},
    {'name': 'dictionary_update',
     'description': 'WRITE: rename or edit a dictionary entry (same fields as '
                    'dictionary_create, by kind + id).',
     'inputSchema': {'type': 'object', 'properties': {
         'kind': _DICT_KIND, 'id': _UUID, 'name': {'type': 'string'},
         'requires_account': {'type': 'boolean'}, 'notes': {'type': 'string'}},
                     'required': ['kind', 'id']},
     'handler': dictionary_update},
    {'name': 'dictionary_delete',
     'description': 'WRITE: delete a dictionary entry. Refused for default entries '
                    'and for entries still used by expenses.',
     'inputSchema': {'type': 'object', 'properties': {'kind': _DICT_KIND, 'id': _UUID},
                     'required': ['kind', 'id']},
     'handler': dictionary_delete},
    {'name': 'assignment_save',
     'description': 'WRITE: save a finished deliverable onto an assignment doc '
                    '(title, one-line summary, full markdown content). Marks it '
                    'saved; re-saving overwrites.',
     'inputSchema': {'type': 'object', 'properties': {
         'assignment_id': _UUID, 'title': {'type': 'string'},
         'summary': {'type': 'string'}, 'content': {'type': 'string'}},
                     'required': ['assignment_id', 'content']},
     'handler': assignment_save},
]
TOOL_MAP = {tool['name']: tool for tool in TOOLS}
