"""Default agent-import prompt template and the placeholder-fill helper.

The template is what a user copies and pastes into an agent (e.g. Claude Cowork).
It is editable per-user; placeholders in {{double_braces}} are filled by
`build_prompt` with live data (subjects, expense types, endpoint, token).
"""
from datetime import date

from django.urls import reverse

from expenses.models import Subject, ExpenseType, Expense

APP_NAME = 'Hestia'

# Variables a user may use in their template. Surfaced in the Settings UI.
TEMPLATE_VARIABLES = [
    'app_name', 'endpoint', 'options_endpoint', 'token',
    'subjects', 'expense_types', 'recurrence_types', 'today',
]

DEFAULT_PROMPT_TEMPLATE = """\
You are helping me import a household bill into {{app_name}}, my recurring-expense \
tracker. Work through the steps below in order and do not skip the confirmation step.

## Step 1 — Ask for the bill
Ask me to upload a single bill document (PDF, JPG, or PNG). Wait until I provide it \
before continuing.

## Step 2 — Read the bill
Extract these fields. If a value is not on the bill, infer a sensible default and \
clearly mark it as a guess:
- name: a short label for the expense (e.g. "Thames Water — standing charge").
- amount: the recurring charge as a number, e.g. 42.50.
- currency: 3-letter ISO code (default GBP).
- recurrence_type: one of [{{recurrence_types}}]. Infer from the bill (monthly water \
→ "monthly", annual road tax → "annual").
- start_date: when this charge next applies, as YYYY-MM-DD. Use the bill's period or \
due date; default to today ({{today}}) if unclear.
- end_date: YYYY-MM-DD, or null for an ongoing charge.
- description: optional notes such as supplier or account reference. Do NOT include \
full card numbers or other sensitive identifiers.

## Step 3 — Choose the subject and expense type
Pick the single best match from MY configured lists below and use its exact id. If \
nothing fits, use null and tell me why.

Subjects (what the expense is for — a property, a vehicle, etc.):
{{subjects}}

Expense types (the kind of charge):
{{expense_types}}

## Step 4 — Confirm with me
Show me a summary table of every field above, including the names of the subject and \
expense type you chose and which values were guesses. Ask me to confirm or correct. \
Apply any changes I ask for. Do not proceed until I explicitly confirm.

## Step 5 — Submit
After I confirm, create the expense with a single POST request:

  Endpoint: POST {{endpoint}}
  Headers:
    Authorization: Bearer {{token}}
    Content-Type: application/json
  Body (example — replace values, omit fields you don't have):
  {
    "name": "Thames Water — standing charge",
    "amount": "42.50",
    "currency": "GBP",
    "recurrence_type": "monthly",
    "start_date": "2026-07-01",
    "end_date": null,
    "subject": "<id from the Subjects list above, or null>",
    "expense_type": "<id from the Expense types list above, or null>",
    "description": ""
  }

If you cannot make HTTP requests yourself, give me a ready-to-run curl command \
instead, with every value filled in:
  curl -X POST "{{endpoint}}" \\
    -H "Authorization: Bearer {{token}}" \\
    -H "Content-Type: application/json" \\
    -d '{"name":"...","amount":"42.50","currency":"GBP","recurrence_type":"monthly","start_date":"2026-07-01","subject":null,"expense_type":null}'

On success the API returns the created expense as JSON including an "id" — show me \
that id and confirm it worked. On error, show me the HTTP status and the response \
body so I can correct the data and retry.

## Rules
- Treat the Authorization token as a secret. Use it only for the request above; never \
repeat it back to me or send it anywhere else.
- Submit only after I have confirmed, and submit one expense per bill unless I say \
otherwise.
"""


def _format_options(queryset):
    rows = [f"- {obj.name} (id: {obj.id})" for obj in queryset]
    return "\n".join(rows) if rows else "- (none configured yet)"


def build_prompt(template, request, config):
    """Fill a template's {{placeholders}} with live data and absolute URLs.

    `request` is used to build absolute endpoint URLs (correct host + https in
    production via SECURE_PROXY_SSL_HEADER). `config` is the user's
    AgentImportConfig, supplying the submission token.
    """
    recurrence_types = ", ".join(value for value, _ in Expense.RECURRENCE_CHOICES)
    replacements = {
        '{{app_name}}': APP_NAME,
        '{{endpoint}}': request.build_absolute_uri(
            reverse('agent-import-expense-create'),
        ),
        '{{options_endpoint}}': request.build_absolute_uri(
            reverse('agent-import-options'),
        ),
        '{{token}}': config.token or '<NO TOKEN — generate one in Settings>',
        '{{subjects}}': _format_options(Subject.objects.order_by('name')),
        '{{expense_types}}': _format_options(ExpenseType.objects.order_by('name')),
        '{{recurrence_types}}': recurrence_types,
        '{{today}}': date.today().isoformat(),
    }
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result
