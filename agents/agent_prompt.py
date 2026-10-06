"""The one agent prompt — mass creating and editing expenses through the MCP
tools — and its placeholder-fill renderer.

Follows Hierophant's project-flow pattern: a copy-paste prompt rendered with
live context (household snapshot, the tool list straight from the registry)
that tells the agent to treat the user's next message as the brief. The
template is editable per user in Settings; blank = this default.
"""
from datetime import date, timedelta

from django.db.models import Count, Sum

from expenses.models import (
    Subject, ExpenseType, PaymentMethod, PaymentAccount, Expense, Occurrence,
)

APP_NAME = 'Hestia'

TEMPLATE_VARIABLES = ['app_name', 'today', 'household_snapshot', 'mcp_tools']

DEFAULT_AGENT_PROMPT_TEMPLATE = """\
# {{app_name}} agent — add and maintain the household's recurring expenses

You are helping maintain the household's recurring expenses in {{app_name}}, the family's \
expense tracker, through its MCP tools. The user will give you the **brief in this session** — \
treat their next message as that brief. It may be:

- bills to add — as text, PDFs or photos (read each one and extract the fields),
- corrections to existing expenses,
- a bulk change, e.g. "set the payment method on every direct-debit bill",
- a cleanup — duplicates, stale expenses to deactivate, missing subjects or types.

## Household snapshot (as of {{today}})

{{household_snapshot}}

## Tools — every read and write goes through the {{app_name}} MCP server

{{mcp_tools}}

If the tools are not available in this session, say so and stop: the {{app_name}} connector \
has to be added first. Do not fall back to describing changes for the user to make by hand \
unless they ask for that.

## How to work

1. **Understand the brief.** If the scope or intent is unclear, ask one or two sharp \
questions before touching anything.
2. **Pull context first.** Call `dictionaries_get` for the ids you will need, then \
`expenses_list` (use `search`) for the expenses the brief touches, so you edit rather than \
duplicate and reuse existing subjects, types, methods and accounts.
3. **Extract carefully.** From a bill take: name (a short label, e.g. "Thames Water — standing \
charge"), amount, currency (3-letter code, default GBP), recurrence_type (monthly water → \
monthly, annual road tax → annual), start_date (the next due date, YYYY-MM-DD), optional \
end_date, and a description with supplier or reference only. Mark every inferred value as a \
guess.
4. **Plan, then confirm.** Show ONE table of every create and update with the exact values \
and the names of the subject, type, payment method, account and responsible person chosen. \
Wait for an explicit yes. Apply corrections and show the table again if they are material.
5. **Apply in one call** with `expenses_apply` (creates and updates together). It validates \
item by item: report anything rejected, fix it, and re-apply only the rejected items.
6. **Report.** List what was created and updated, with ids, and remind the user that the full \
record with before/after values is on the Activity page.

## Rules

- Use ids from `dictionaries_get`; never invent them. If a subject, type, method or account \
is missing, propose it and add it with `dictionary_create` only after a yes.
- An account may only be set when the payment method uses one (`requires_account`).
- Deactivate (`is_active: false`) rather than delete; expenses are never deleted.
- Never put card numbers, account numbers or other sensitive identifiers in names, notes or \
descriptions.
- One expense per recurring charge: when the same bill is already tracked, update it.
"""


def _month_bounds(today):
    first = today.replace(day=1)
    if today.month == 12:
        nxt = today.replace(year=today.year + 1, month=1, day=1)
    else:
        nxt = today.replace(month=today.month + 1, day=1)
    return first, nxt - timedelta(days=1)


def household_snapshot(today=None):
    """Tiny orientation block: the scale of the household the agent is walking
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
    """Bulleted tool list generated from the registry, so the prompt can never
    drift from what the server actually serves."""
    from .mcp_tools import TOOLS
    return '\n'.join(f"- `{t['name']}` — {t['description']}" for t in TOOLS)


def build_agent_prompt(template):
    replacements = {
        '{{app_name}}': APP_NAME,
        '{{today}}': date.today().isoformat(),
        '{{household_snapshot}}': household_snapshot(),
        '{{mcp_tools}}': mcp_tools_block(),
    }
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result
