"""Activity log: rows written by the shared write paths with the right actor,
source, session and diff; the list endpoint; MCP session ids."""
import json

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from agents.models import McpToken, McpSession
from expenses.models import PaymentMethod, PaymentAccount, Expense, Occurrence
from .models import ActivityLog

User = get_user_model()


class ActivityTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='bk@example.com', username='bk', first_name='B', last_name='K',
            password='supersecret123',
        )
        self.partner = User.objects.create_user(
            email='va@example.com', username='va', first_name='V', last_name='A',
            password='supersecret123',
        )
        self.cash = PaymentMethod.objects.create(name='Cash', is_default=True)
        self.dd = PaymentMethod.objects.create(name='Direct Debit', requires_account=True, is_default=True)
        self.joint = PaymentAccount.objects.create(name='Joint current')
        self.mcp = McpToken.objects.create(user=self.partner, name='claude.ai')
        self.mcp_url = f'/mcp/{self.mcp.token}/'

    def payload(self, **overrides):
        data = {'name': 'Council tax', 'amount': '150.00', 'currency': 'GBP',
                'recurrence_type': 'monthly', 'start_date': '2026-10-01'}
        data.update(overrides)
        return data

    def rpc(self, method, params=None, headers=None, message_id=1):
        message = {'jsonrpc': '2.0', 'id': message_id, 'method': method}
        if params is not None:
            message['params'] = params
        return self.client.post(self.mcp_url, json.dumps(message),
                                content_type='application/json', **(headers or {}))


class WebWriteLoggingTests(ActivityTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)

    def test_expense_create_update_deactivate_logged_with_diffs(self):
        resp = self.client.post(reverse('expense-list'), self.payload(
            payment_method=str(self.dd.id), account=str(self.joint.id)), format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        row = ActivityLog.objects.get(action='create', entity_type='expense')
        self.assertEqual(row.actor, self.user)
        self.assertEqual(row.source, 'web')
        self.assertEqual(row.entity_label, 'Council tax')
        self.assertEqual(row.changes['amount'], {'from': None, 'to': '150.00'})
        self.assertEqual(row.changes['payment_method'], {'from': None, 'to': 'Direct Debit'})
        self.assertNotIn('end_date', row.changes)          # blanks omitted on create

        self.client.patch(reverse('expense-detail', args=[resp.data['id']]),
                          {'amount': '160.00', 'payment_method': str(self.cash.id), 'account': None},
                          format='json')
        row = ActivityLog.objects.get(action='update', entity_type='expense')
        self.assertEqual(row.changes, {
            'amount': {'from': '150.00', 'to': '160.00'},
            'payment_method': {'from': 'Direct Debit', 'to': 'Cash'},
            'account': {'from': 'Joint current', 'to': None},
        })

        # A PATCH that changes nothing writes no row.
        self.client.patch(reverse('expense-detail', args=[resp.data['id']]),
                          {'amount': '160.00'}, format='json')
        self.assertEqual(ActivityLog.objects.filter(action='update').count(), 1)

        # Soft delete is logged as an update of is_active.
        self.client.delete(reverse('expense-detail', args=[resp.data['id']]))
        row = ActivityLog.objects.filter(entity_type='expense').order_by('created_at').last()
        self.assertEqual(row.action, 'update')
        self.assertEqual(row.changes, {'is_active': {'from': True, 'to': False}})

    def test_dictionary_delete_logged(self):
        resp = self.client.post(reverse('paymentaccount-list'), {'name': 'Savings'}, format='json')
        self.client.delete(reverse('paymentaccount-detail', args=[resp.data['id']]))
        rows = list(ActivityLog.objects.filter(entity_type='payment_account').order_by('created_at'))
        self.assertEqual([r.action for r in rows], ['create', 'delete'])
        self.assertEqual(rows[1].entity_label, 'Savings')
        self.assertEqual(rows[1].changes['name'], {'from': 'Savings', 'to': None})

    def test_payment_logged_with_expense_label(self):
        expense = Expense.objects.create(created_by=self.user, **self.payload())
        occ = Occurrence.objects.create(expense=expense, due_date='2026-10-01',
                                        expected_amount='150.00', currency='GBP')
        resp = self.client.post(reverse('occurrence-payments', args=[occ.id]), {
            'amount_paid': '150.00', 'currency': 'GBP', 'paid_date': '2026-10-02',
            'payment_method': 'Cash'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        row = ActivityLog.objects.get(entity_type='payment')
        self.assertEqual(row.entity_label, 'Council tax · due 2026-10-01')
        self.assertEqual(row.changes['amount_paid']['to'], '150.00')
        self.client.delete(reverse('payment-detail', args=[resp.data['id']]))
        self.assertTrue(ActivityLog.objects.filter(entity_type='payment', action='delete').exists())


class McpSessionLoggingTests(ActivityTestCase):
    def test_initialize_mints_session_and_writes_are_attributed(self):
        resp = self.rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                       'clientInfo': {'name': 'claude-code', 'version': '2.0'}})
        self.assertEqual(resp.status_code, 200)
        session_id = resp['Mcp-Session-Id']
        session = McpSession.objects.get(pk=session_id)
        self.assertEqual(session.token, self.mcp)
        self.assertEqual(session.client_name, 'claude-code')
        self.assertEqual(session.request_count, 1)

        headers = {'HTTP_MCP_SESSION_ID': session_id}
        self.rpc('tools/call', {'name': 'dictionaries_get', 'arguments': {}}, headers)
        resp = self.rpc('tools/call', {'name': 'expenses_apply', 'arguments': {
            'creates': [self.payload(name='Via MCP', payment_method=str(self.cash.id))]}}, headers)
        self.assertFalse(resp.json()['result']['isError'], resp.json())
        self.assertNotIn('Mcp-Session-Id', resp)   # only emitted on initialize

        row = ActivityLog.objects.get(entity_label='Via MCP')
        self.assertEqual(row.source, 'mcp')
        self.assertEqual(row.actor, self.partner)   # token owner, not any web user
        self.assertEqual(row.token, self.mcp)
        self.assertEqual(str(row.session_id), session_id)
        self.assertEqual(row.via, 'MCP · claude.ai')

        session.refresh_from_db()
        self.assertEqual(session.request_count, 3)
        self.assertEqual(session.tool_calls, {'dictionaries_get': 1, 'expenses_apply': 1})

        # DELETE with the header ends the session.
        resp = self.client.delete(self.mcp_url, **headers)
        self.assertEqual(resp.status_code, 202)
        session.refresh_from_db()
        self.assertIsNotNone(session.ended_at)

    def test_unknown_or_missing_session_header_is_tolerated(self):
        resp = self.rpc('tools/call', {'name': 'dictionary_create', 'arguments': {
            'kind': 'subject', 'name': 'Garage'}},
            {'HTTP_MCP_SESSION_ID': '00000000-0000-0000-0000-000000000000'})
        self.assertFalse(resp.json()['result']['isError'])
        row = ActivityLog.objects.get(entity_label='Garage')
        self.assertIsNone(row.session)
        self.assertEqual(row.token, self.mcp)
        resp = self.rpc('tools/call', {'name': 'dictionary_delete', 'arguments': {
            'kind': 'subject', 'id': str(row.entity_id)}})
        self.assertFalse(resp.json()['result']['isError'])
        self.assertTrue(ActivityLog.objects.filter(entity_label='Garage', action='delete').exists())

    def test_activity_recent_tool(self):
        self.rpc('tools/call', {'name': 'dictionary_create', 'arguments': {
            'kind': 'subject', 'name': 'Garage'}})
        resp = self.rpc('tools/call', {'name': 'activity_recent', 'arguments': {}})
        data = json.loads(resp.json()['result']['content'][0]['text'])
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['activity'][0]['entity'], 'Garage')
        self.assertEqual(data['activity'][0]['who'], 'V A')
        self.assertEqual(data['activity'][0]['via'], 'MCP · claude.ai')


class ActivityEndpointTests(ActivityTestCase):
    def test_list_filters_and_requires_auth(self):
        self.assertEqual(self.client.get(reverse('activity-list')).status_code, 401)
        self.client.force_authenticate(self.user)
        resp = self.client.post(reverse('expense-list'), self.payload(), format='json')
        expense_id = resp.data['id']
        self.client.post(reverse('subject-list'), {'name': 'Garage'}, format='json')

        resp = self.client.get(reverse('activity-list'))
        self.assertEqual(resp.data['count'], 2)
        self.assertEqual(resp.data['results'][0]['actor_name'], 'B K')
        self.assertEqual(resp.data['results'][0]['via'], 'Web')

        resp = self.client.get(reverse('activity-list'), {'entity_type': 'expense', 'entity_id': expense_id})
        self.assertEqual(resp.data['count'], 1)
        resp = self.client.get(reverse('activity-list'), {'source': 'mcp'})
        self.assertEqual(resp.data['count'], 0)

    def test_sessions_endpoint_lists_sessions_with_counts(self):
        resp = self.rpc('initialize', {'protocolVersion': '2025-06-18'})
        session_id = resp['Mcp-Session-Id']
        self.rpc('tools/call', {'name': 'dictionary_create', 'arguments': {'kind': 'subject', 'name': 'Garage'}},
                 {'HTTP_MCP_SESSION_ID': session_id})
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse('agents-mcp-sessions'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        row = resp.data[0]
        self.assertEqual(row['id'], session_id)
        self.assertEqual(row['token_name'], 'claude.ai')
        self.assertEqual(row['user_name'], 'V A')
        self.assertEqual(row['tool_calls'], {'dictionary_create': 1})
        self.assertEqual(row['activity_count'], 1)
