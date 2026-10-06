"""Default assignment prompt template and the placeholder-fill renderer.

Ported from Hierophant's Assignment flow (ProjectResearchTemplate kind=ASG):
the agent is a practitioner producing a specific deliverable; context is
pulled on demand through the Hestia MCP tools rather than pasted in; the
deliverable is written back with `assignment_save` (or the content-token
PATCH when MCP is unavailable). Editable per user; blank = this default.
"""
from datetime import date, timedelta

from django.db.models import Count, Sum
from django.urls import reverse

from expenses.models import (
    Subject, ExpenseType, PaymentMethod, PaymentAccount, Expense, Occurrence,
)

APP_NAME = 'Hestia'
DASH = '—'

TEMPLATE_VARIABLES = [
    'app_name', 'assignment_topic', 'assignment_id', 'today',
    'household_snapshot', 'mcp_tools', 'writeback_endpoint',
]

DEFAULT_ASSIGNMENT_TEMPLATE = """\
# {{app_name}} Assignment — {{assignment_topic}}

You are a senior practitioner producing a **specific deliverable** for the household \
finances tracked in {{app_name}}, the family's recurring-expense tracker — a monthly bill \
review, a budget draft, a reconciliation, a supplier comparison, a batch of expenses \
entered or corrected, or whatever the brief calls for. A non-final draft is a perfectly \
valid outcome: the point is a concrete artifact the user can iterate on, not polished \
perfection. The user will give you the **brief in this session** — treat their next \
message as that brief.

This is NOT open-ended research. If the session turns into pure information-gathering \
with no deliverable, say so and agree with the user what the deliverable should be before \
continuing.

## Assignment topic (set by the user when they created this assignment)

{{assignment_topic}}

(If the topic above is just a dash, the user did not pre-set one — rely on the brief they \
give you in this session.)

## Household snapshot (as of {{today}})

{{household_snapshot}}

## Context and changes — via the {{app_name}} MCP tools

You are connected to the {{app_name}} MCP server. Pull what you need on demand instead of \
expecting it pasted here, and make changes through the tools rather than describing them:

{{mcp_tools}}

Rules for writes:
- Confirm with the user before creating, editing or deleting anything; show the exact \
values first.
- Use ids from `dictionaries_get` — never invent subjects, types, methods, accounts or \
people. If something is missing, propose adding it and wait for a yes.
- An account may only be set on an expense when its payment method uses one.
- Never put card or account numbers in names, notes or descriptions.

If the MCP tools are unavailable in this session, say so up front, continue with what the \
user gives you, and save the deliverable with the fallback call below.

## How to work

1. Treat the user's next message as the brief. Before drafting, make sure you know what \
the deliverable IS (format, audience, rough length) and what "good" looks like. Ask one or \
two sharp questions if any of that is missing — a wrong-format deliverable is wasted work.
2. Pull context first: `dictionaries_get`, then `expenses_list` / `occurrences_list` for \
the expenses the brief touches, `expense_get` for detail.
3. For anything substantial, propose a short outline and get a nod before writing the full \
draft. For small deliverables, draft directly.
4. Draft in the user's interest, not to impress: concrete, structured, numbers over \
adjectives, no filler. Match tone to the deliverable's audience.
5. Iterate in-session on the user's feedback. Save when they're satisfied with the current \
state — even if it's explicitly a first draft.

## When you're done — save the deliverable

Save the deliverable itself as the assignment body — not a report about it. If it is a \
draft, say so in the summary line, not inside the deliverable text.

Primary — call the `assignment_save` tool with:
- assignment_id: {{assignment_id}}
- title: <deliverable name, e.g. "October bill review">
- summary: <one line: what it is + state, e.g. "First draft, pending VA's review">
- content: <the full deliverable markdown>

Fallback (MCP unavailable) — one HTTP call, no auth header needed:

```
PATCH {{writeback_endpoint}}
Content-Type: application/json

{
  "title": "<deliverable name>",
  "summary": "<one line: what it is + state>",
  "content": "<the full deliverable markdown>"
}
```

A response with "status": "POPUL" means it is saved on {{app_name}}'s Assignments page. \
Confirm to the user with a 2-3 line recap of what was produced and what's still open. If \
the call fails, show the user the error and the exact payload so they can save it manually.
"""


def _month_bounds(today):
    first = today.replace(day=1)
    if today.month == 12:
        nxt = today.replace(year=today.year + 1, month=1, day=1)
    else:
        nxt = today.replace(month=today.month + 1, day=1)
    return first, nxt - timedelta(days=1)


def household_snapshot(today=None):
    """Tiny orientation block: scale of the household the agent is walking
    into. The real data stays behind the MCP tools."""
    today = today or date.today()
    first, last = _month_bounds(today)
    active = Expense.objects.filter(is_active=True).count()
    month = Occurrence.objects.filter(due_date__gte=first, due_date__lte=last)
    totals = month.values('currency').annotate(
        total=Sum('expected_amount'), count=Count('id')).order_by('currency')
    overdue = Occurrence.objects.filter(
        due_date__lt=today, status__in=['pending', 'overdue']).count()
    lines = [f'- Active recurring expenses: {active}']
    if totals:
        parts = [f"{t['currency']} {t['total']:.2f} ({t['count']} due)" for t in totals]
        lines.append(f"- Expected this month ({today.strftime('%B %Y')}): " + ', '.join(parts))
    else:
        lines.append(f"- Expected this month ({today.strftime('%B %Y')}): nothing scheduled")
    lines.append(f'- Overdue occurrences: {overdue}')
    lines.append(
        f'- Dictionaries: {Subject.objects.count()} subjects, '
        f'{ExpenseType.objects.count()} expense types, '
        f'{PaymentMethod.objects.count()} payment methods, '
        f'{PaymentAccount.objects.count()} accounts')
    return '\n'.join(lines)


def mcp_tools_block():
    """Bulleted tool list generated from the registry, so the prompt can
    never drift from what the server actually serves."""
    from .mcp_tools import TOOLS
    return '\n'.join(
        f"- `{t['name']}` — {t['description']}" for t in TOOLS)


def build_assignment_prompt(template, assignment, request):
    replacements = {
        '{{app_name}}': APP_NAME,
        '{{assignment_topic}}': assignment.title or DASH,
        '{{assignment_id}}': str(assignment.id),
        '{{today}}': date.today().isoformat(),
        '{{household_snapshot}}': household_snapshot(),
        '{{mcp_tools}}': mcp_tools_block(),
        '{{writeback_endpoint}}': request.build_absolute_uri(
            reverse('agents-assignment-writeback', args=[assignment.content_token])),
    }
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result
