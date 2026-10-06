"""MCP transport + tools through the real endpoint, and the owner-facing
token / prompt / config endpoints."""
import json

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from expenses.models import (
    Subject, ExpenseType, PaymentMethod, PaymentAccount, Expense, Occurrence,
)
from .agent_prompt import DEFAULT_AGENT_PROMPT_TEMPLATE
from .models import McpToken, AgentConfig, MCP_TOKEN_PREFIX

User = get_user_model()


class AgentsTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='bk@example.com', username='bk', first_name='B', last_name='K',
            password='supersecret123',
        )
        self.partner = User.objects.create_user(
            email='va@example.com', username='va', first_name='V', last_name='A',
            password='supersecret123',
        )
        self.subject = Subject.objects.create(name='42 Oak Street', is_default=True)
        self.etype = ExpenseType.objects.create(name='Tax', is_default=True)
        self.cash = PaymentMethod.objects.create(name='Cash', is_default=True)
        self.dd = PaymentMethod.objects.create(
            name='Direct Debit', requires_account=True, is_default=True)
        self.joint = PaymentAccount.objects.create(name='Joint current')
        self.mcp = McpToken.objects.create(user=self.user, name='test client')
        self.url = f'/mcp/{self.mcp.token}/'

    # --- helpers ---------------------------------------------------------
    def rpc(self, method, params=None, message_id=1, url=None):
        message = {'jsonrpc': '2.0', 'id': message_id, 'method': method}
        if params is not None:
            message['params'] = params
        return self.client.post(url or self.url, json.dumps(message),
                                content_type='application/json')

    def call_tool(self, name, arguments=None):
        result = self.rpc('tools/call', {'name': name, 'arguments': arguments or {}}
                          ).json()['result']
        text = result['content'][0]['text']
        return result['isError'], (json.loads(text) if not result['isError'] else text)

    def make_expense(self, **overrides):
        fields = dict(name='Council tax', amount='150.00', currency='GBP',
                      recurrence_type='monthly', start_date='2026-10-01',
                      created_by=self.user)
        fields.update(overrides)
        return Expense.objects.create(**fields)

    def create_item(self, **overrides):
        item = {'name': 'Water', 'amount': '35.50', 'recurrence_type': 'monthly',
                'start_date': '2026-10-01'}
        item.update(overrides)
        return item


class TransportTests(AgentsTestCase):
    def test_unknown_or_revoked_token_404(self):
        response = self.client.post(f'/mcp/{MCP_TOKEN_PREFIX}nope/', '{}',
                                    content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.mcp.active = False
        self.mcp.save()
        self.assertEqual(self.rpc('ping').status_code, 404)

    def test_token_of_inactive_user_404(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.rpc('ping').status_code, 404)

    def test_initialize_lists_tools_and_stamps_last_used(self):
        response = self.rpc('initialize', {'protocolVersion': '2025-06-18',
                                           'capabilities': {},
                                           'clientInfo': {'name': 't', 'version': '0'}})
        result = response.json()['result']
        self.assertEqual(result['protocolVersion'], '2025-06-18')
        self.assertEqual(result['serverInfo']['name'], 'hestia')
        self.assertIn('tools', result['capabilities'])
        self.mcp.refresh_from_db()
        self.assertIsNotNone(self.mcp.last_used_at)

        names = {t['name'] for t in self.rpc('tools/list').json()['result']['tools']}
        self.assertEqual(names, {
            'dictionaries_get', 'expenses_list', 'expense_get', 'occurrences_list',
            'transactions_list', 'spend_summary', 'activity_recent', 'expenses_apply',
            'transactions_apply',
            'dictionary_create', 'dictionary_update', 'dictionary_delete',
        })

    def test_notification_202_and_no_slash_no_redirect(self):
        response = self.client.post(
            self.url, json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 202)
        response = self.rpc('ping', url=self.url.rstrip('/'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result'], {})

    def test_unknown_method_tool_and_get(self):
        self.assertEqual(self.rpc('bogus/method').json()['error']['code'], -32601)
        response = self.rpc('tools/call', {'name': 'bogus_tool', 'arguments': {}})
        self.assertEqual(response.json()['error']['code'], -32602)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_batch_messages(self):
        body = [{'jsonrpc': '2.0', 'id': 1, 'method': 'ping'},
                {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'ping'}]
        response = self.client.post(self.url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['id'] for r in response.json()], [1, 2])


class ReadToolTests(AgentsTestCase):
    def test_dictionaries_get(self):
        is_error, data = self.call_tool('dictionaries_get')
        self.assertFalse(is_error, data)
        self.assertEqual([s['name'] for s in data['subjects']], ['42 Oak Street'])
        methods = {m['name']: m for m in data['payment_methods']}
        self.assertTrue(methods['Direct Debit']['requires_account'])
        self.assertFalse(methods['Cash']['requires_account'])
        self.assertEqual([a['name'] for a in data['payment_accounts']], ['Joint current'])
        self.assertEqual({u['display_name'] for u in data['users']}, {'B K', 'V A'})
        self.assertIn('monthly', data['recurrence_types'])

    def test_expenses_list_filters_and_search(self):
        self.make_expense(name='Council tax', payment_method=self.dd, account=self.joint,
                          responsible=self.partner)
        self.make_expense(name='Window cleaner', payment_method=self.cash)
        self.make_expense(name='Old gym', is_active=False)

        is_error, data = self.call_tool('expenses_list')
        self.assertFalse(is_error, data)
        self.assertEqual({e['name'] for e in data['expenses']}, {'Council tax', 'Window cleaner'})
        card = next(e for e in data['expenses'] if e['name'] == 'Council tax')
        self.assertEqual(card['payment_method'], 'Direct Debit')
        self.assertEqual(card['account'], 'Joint current')
        self.assertEqual(card['responsible'], 'V A')

        _, data = self.call_tool('expenses_list', {'is_active': None})
        self.assertEqual(data['count'], 3)
        _, data = self.call_tool('expenses_list', {'payment_method': str(self.cash.id)})
        self.assertEqual([e['name'] for e in data['expenses']], ['Window cleaner'])
        _, data = self.call_tool('expenses_list', {'search': 'council'})
        self.assertEqual(data['count'], 1)

    def test_expense_get_and_unknown_id(self):
        expense = self.make_expense()
        is_error, data = self.call_tool('expense_get', {'expense_id': str(expense.id)})
        self.assertFalse(is_error, data)
        self.assertEqual(data['name'], 'Council tax')
        self.assertIn('recent_occurrences', data)
        is_error, text = self.call_tool('expense_get', {'expense_id': 'not-a-uuid'})
        self.assertTrue(is_error)
        self.assertIn('unknown expense', text)

    def test_occurrences_list_unpaid_default(self):
        expense = self.make_expense()
        Occurrence.objects.create(expense=expense, due_date='2026-10-01',
                                  expected_amount='150.00', currency='GBP', status='overdue')
        Occurrence.objects.create(expense=expense, due_date='2030-01-01',
                                  expected_amount='150.00', currency='GBP', status='pending')
        Occurrence.objects.create(expense=expense, due_date='2026-09-01',
                                  expected_amount='150.00', currency='GBP', status='paid')
        is_error, data = self.call_tool('occurrences_list')
        self.assertFalse(is_error, data)
        self.assertEqual([o['due_date'] for o in data['occurrences']], ['2026-10-01'])
        _, data = self.call_tool('occurrences_list', {'status': 'all'})
        self.assertEqual(data['count'], 3)
        is_error, text = self.call_tool('occurrences_list', {'status': 'bogus'})
        self.assertTrue(is_error)


class ExpensesApplyTests(AgentsTestCase):
    def test_mixed_batch_applies_good_items_and_rejects_bad_ones(self):
        existing = self.make_expense(payment_method=self.dd, account=self.joint)
        is_error, data = self.call_tool('expenses_apply', {
            'creates': [
                self.create_item(expense_type=str(self.etype.id), payment_method=str(self.dd.id),
                                 account=str(self.joint.id), responsible=str(self.partner.id)),
                self.create_item(name='Bad: cash with account', payment_method=str(self.cash.id),
                                 account=str(self.joint.id)),
                self.create_item(name='Bad: no amount', amount=''),
            ],
            'updates': [
                {'expense_id': str(existing.id), 'amount': '160.00'},
                {'expense_id': str(existing.id), 'payment_method': str(self.cash.id)},  # stored account conflicts
                {'expense_id': '00000000-0000-0000-0000-000000000000', 'amount': '1'},
                {'expense_id': str(existing.id)},                                        # nothing to update
            ],
        })
        self.assertFalse(is_error, data)
        self.assertEqual(data['counts'], {'applied': 2, 'rejected': 5})
        ops = [(a['op'], a['index']) for a in data['applied']]
        self.assertEqual(ops, [('create', 0), ('update', 0)])

        water = Expense.objects.get(name='Water')
        self.assertEqual(water.created_by, self.user)       # token owner
        self.assertEqual(water.account, self.joint)
        self.assertTrue(water.occurrences.exists())          # generated in the batch
        self.assertIsNotNone(data['applied'][0]['expense']['next_due'])  # occurrences generated
        existing.refresh_from_db()
        self.assertEqual(str(existing.amount), '160.00')
        self.assertEqual(existing.payment_method, self.dd)   # conflicting update rejected

        rejected = {(r['op'], r['index']): r for r in data['rejected']}
        self.assertIn('account', rejected[('create', 1)]['errors'])
        self.assertIn('amount', rejected[('create', 2)]['errors'])
        self.assertIn('account', rejected[('update', 1)]['errors'])
        self.assertIn('unknown expense', rejected[('update', 2)]['errors'])
        self.assertIn('nothing to update', rejected[('update', 3)]['errors'])
        self.assertFalse(Expense.objects.filter(name__startswith='Bad').exists())

    def test_deactivate_via_update_and_empty_batch(self):
        expense = self.make_expense()
        is_error, data = self.call_tool('expenses_apply', {
            'updates': [{'expense_id': str(expense.id), 'is_active': False}]})
        self.assertFalse(is_error, data)
        expense.refresh_from_db()
        self.assertFalse(expense.is_active)
        is_error, text = self.call_tool('expenses_apply', {})
        self.assertTrue(is_error)
        self.assertIn('creates and/or updates', text)
        is_error, text = self.call_tool('expenses_apply', {'creates': 'nope'})
        self.assertTrue(is_error)


class DictionaryToolTests(AgentsTestCase):
    def test_dictionary_create_update_delete_with_guards(self):
        is_error, data = self.call_tool('dictionary_create', {
            'kind': 'payment_method', 'name': 'Cheque', 'requires_account': True})
        self.assertFalse(is_error, data)
        method = PaymentMethod.objects.get(name='Cheque')
        self.assertTrue(method.requires_account)
        self.assertEqual(method.created_by, self.user)

        is_error, data = self.call_tool('dictionary_update', {
            'kind': 'payment_method', 'id': str(method.id), 'name': 'Cheque (rare)'})
        self.assertFalse(is_error, data)
        self.assertEqual(data['entry']['name'], 'Cheque (rare)')

        is_error, text = self.call_tool('dictionary_create', {'kind': 'subject', 'name': '42 Oak Street'})
        self.assertTrue(is_error)          # unique name
        is_error, text = self.call_tool('dictionary_create', {'kind': 'bogus', 'name': 'x'})
        self.assertTrue(is_error)
        self.assertIn('kind must be one of', text)

        is_error, text = self.call_tool('dictionary_delete', {'kind': 'payment_method', 'id': str(self.cash.id)})
        self.assertTrue(is_error)
        self.assertIn('Default', text)
        self.make_expense(payment_method=method)
        is_error, text = self.call_tool('dictionary_delete', {'kind': 'payment_method', 'id': str(method.id)})
        self.assertTrue(is_error)
        self.assertIn('in use', text)
        is_error, data = self.call_tool('dictionary_delete', {'kind': 'payment_account', 'id': str(self.joint.id)})
        self.assertFalse(is_error, data)
        self.assertFalse(PaymentAccount.objects.filter(id=self.joint.id).exists())


class OwnerEndpointTests(AgentsTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)

    def test_mint_token_returns_full_value_once_then_masked(self):
        resp = self.client.post(reverse('agents-mcp-tokens'), {'name': 'claude.ai'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(resp.data['token'].startswith(MCP_TOKEN_PREFIX))
        self.assertTrue(resp.data['connector_url'].endswith(f"/mcp/{resp.data['token']}/"))
        listing = self.client.get(reverse('agents-mcp-tokens')).data
        self.assertEqual({t['name'] for t in listing}, {'test client', 'claude.ai'})
        for row in listing:
            self.assertNotIn('token', row)
            self.assertIn('…', row['token_masked'])
        self.client.force_authenticate(None)
        self.assertEqual(self.rpc('ping', url=f"/mcp/{resp.data['token']}/").status_code, 200)

    def test_revoke_token_only_own(self):
        other = McpToken.objects.create(user=self.partner, name='partner')
        resp = self.client.delete(reverse('agents-mcp-token', args=[other.id]))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.delete(reverse('agents-mcp-token', args=[self.mcp.id]))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.client.force_authenticate(None)
        self.assertEqual(self.rpc('ping').status_code, 404)

    def test_prompt_renders_live_context_without_placeholders_or_secrets(self):
        self.make_expense()
        resp = self.client.get(reverse('agents-prompt'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        prompt = resp.data['prompt']
        self.assertNotIn('{{', prompt)
        self.assertIn('Hestia agent', prompt)
        self.assertIn('Active recurring expenses: 1', prompt)
        self.assertIn('`expenses_apply`', prompt)          # tool list from the registry
        self.assertIn('`dictionaries_get`', prompt)
        self.assertNotIn(self.mcp.token, prompt)            # no secrets in the prompt
        self.assertEqual(self.client.get(reverse('agents-prompt')).status_code, 200)

    def test_config_default_then_custom_then_reset(self):
        resp = self.client.get(reverse('agents-config'))
        self.assertEqual(resp.data['prompt_template'], DEFAULT_AGENT_PROMPT_TEMPLATE)
        self.assertFalse(resp.data['is_custom_template'])
        self.assertIn('household_snapshot', resp.data['template_variables'])

        resp = self.client.patch(reverse('agents-config'),
                                 {'prompt_template': 'Custom {{app_name}} x'}, format='json')
        self.assertTrue(resp.data['is_custom_template'])
        self.assertEqual(self.client.get(reverse('agents-prompt')).data['prompt'], 'Custom Hestia x')

        self.client.patch(reverse('agents-config'), {'prompt_template': ''}, format='json')
        self.assertEqual(AgentConfig.objects.get(user=self.user).prompt_template, '')
        self.assertNotIn('{{', self.client.get(reverse('agents-prompt')).data['prompt'])
