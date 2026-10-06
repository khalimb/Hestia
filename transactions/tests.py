import json

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from activity.models import ActivityLog
from agents.models import McpToken
from expenses.models import ExpenseType, PaymentMethod, PaymentAccount, Expense, Occurrence
from .models import Transaction

User = get_user_model()


class TransactionTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='bk@example.com', username='bk', first_name='B', last_name='K',
            password='supersecret123',
        )
        self.partner = User.objects.create_user(
            email='va@example.com', username='va', first_name='V', last_name='A',
            password='supersecret123',
        )
        self.takeaway = ExpenseType.objects.create(name='Takeaway')
        self.groceries = ExpenseType.objects.create(name='Groceries')
        self.cash = PaymentMethod.objects.create(name='Cash', is_default=True)
        self.card = PaymentMethod.objects.create(name='Card', requires_account=True, is_default=True)
        self.joint = PaymentAccount.objects.create(name='Joint current')

    def payload(self, **overrides):
        data = {'date': '2026-10-03', 'amount': '23.40', 'currency': 'GBP',
                'merchant': 'Deliveroo', 'expense_type': str(self.takeaway.id)}
        data.update(overrides)
        return data

    def make(self, **overrides):
        fields = dict(date='2026-10-03', amount='23.40', currency='GBP', merchant='Deliveroo',
                      expense_type=self.takeaway, created_by=self.user)
        fields.update(overrides)
        return Transaction.objects.create(**fields)


class TransactionApiTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)

    def test_create_with_category_method_account_and_payer(self):
        resp = self.client.post(reverse('transaction-list'), self.payload(
            payment_method=str(self.card.id), account=str(self.joint.id),
            paid_by=str(self.partner.id)), format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['expense_type_name'], 'Takeaway')
        self.assertEqual(resp.data['account_name'], 'Joint current')
        self.assertEqual(resp.data['paid_by_name'], 'V A')
        self.assertEqual(resp.data['created_by'], self.user.id)
        row = ActivityLog.objects.get(entity_type='transaction')
        self.assertEqual(row.action, 'create')
        self.assertEqual(row.entity_label, 'Deliveroo · 2026-10-03')
        self.assertEqual(row.changes['amount']['to'], '23.40')

    def test_account_rule_shared_with_expenses(self):
        resp = self.client.post(reverse('transaction-list'), self.payload(
            payment_method=str(self.cash.id), account=str(self.joint.id)), format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('account', resp.data)

    def test_list_filters_date_window_category_and_search(self):
        self.make(date='2026-10-03')
        self.make(date='2026-10-20', merchant='Tesco', expense_type=self.groceries, amount='54.10')
        self.make(date='2026-09-28', merchant='Deliveroo again')
        for params, expected in [
            ({'date_from': '2026-10-01', 'date_to': '2026-10-31'}, {'Deliveroo', 'Tesco'}),
            ({'expense_type': str(self.groceries.id)}, {'Tesco'}),
            ({'search': 'deliveroo'}, {'Deliveroo', 'Deliveroo again'}),
        ]:
            resp = self.client.get(reverse('transaction-list'), params)
            self.assertEqual({t['merchant'] for t in resp.data['results']}, expected, params)

    def test_update_and_delete_are_logged(self):
        t = self.make()
        resp = self.client.patch(reverse('transaction-detail', args=[t.id]),
                                 {'amount': '25.00', 'expense_type': str(self.groceries.id)}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        row = ActivityLog.objects.get(entity_type='transaction', action='update')
        self.assertEqual(row.changes['expense_type'], {'from': 'Takeaway', 'to': 'Groceries'})
        resp = self.client.delete(reverse('transaction-detail', args=[t.id]))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Transaction.objects.filter(id=t.id).exists())
        self.assertTrue(ActivityLog.objects.filter(entity_type='transaction', action='delete').exists())

    def test_dictionary_in_use_by_transaction_cannot_be_deleted(self):
        self.make(payment_method=self.card, account=self.joint)
        for url in (reverse('expensetype-detail', args=[self.takeaway.id]),
                    reverse('paymentaccount-detail', args=[self.joint.id])):
            resp = self.client.delete(url)
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, url)
            self.assertIn('transactions', resp.data['detail'])

    def test_dashboard_summary_includes_variable_spend_and_combined_breakdown(self):
        from django.utils import timezone
        today = timezone.now().date()
        rent = ExpenseType.objects.create(name='Rent')
        expense = Expense.objects.create(
            name='Flat', amount='1000.00', currency='GBP', recurrence_type='monthly',
            start_date=today.replace(day=1), expense_type=rent, created_by=self.user)
        Occurrence.objects.create(expense=expense, due_date=today.replace(day=1),
                                  expected_amount='1000.00', currency='GBP')
        self.make(date=today, amount='23.40')
        self.make(date=today, amount='10.00', merchant='Pizza')
        self.make(date=today.replace(day=1), amount='54.10', merchant='Tesco', expense_type=self.groceries)

        resp = self.client.get(reverse('dashboard-summary'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['transaction_currency_totals'],
                         [{'currency': 'GBP', 'total': 87.50, 'count': 3}])
        combined = {c['name']: c for c in resp.data['combined_type_breakdown']}
        self.assertEqual(float(combined['Rent']['recurring']), 1000.0)
        self.assertEqual(float(combined['Rent']['one_off']), 0)
        self.assertEqual(float(combined['Takeaway']['one_off']), 33.40)
        self.assertEqual([c['name'] for c in resp.data['combined_type_breakdown']],
                         ['Rent', 'Groceries', 'Takeaway'])   # sorted by combined total


class TransactionMcpTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.mcp = McpToken.objects.create(user=self.partner, name='claude.ai')
        self.url = f'/mcp/{self.mcp.token}/'

    def call_tool(self, name, arguments=None):
        message = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                   'params': {'name': name, 'arguments': arguments or {}}}
        result = self.client.post(self.url, json.dumps(message),
                                  content_type='application/json').json()['result']
        text = result['content'][0]['text']
        return result['isError'], (json.loads(text) if not result['isError'] else text)

    def test_apply_mixed_batch_then_list_with_totals(self):
        existing = self.make(merchant='Tesco', amount='54.10', expense_type=self.groceries)
        is_error, data = self.call_tool('transactions_apply', {
            'creates': [
                self.payload(),
                self.payload(merchant='Pizza', amount='10.00', date='2026-10-04',
                             payment_method=str(self.card.id), account=str(self.joint.id)),
                self.payload(merchant='Bad', payment_method=str(self.cash.id), account=str(self.joint.id)),
                {'merchant': 'No date', 'amount': '1'},
            ],
            'updates': [{'transaction_id': str(existing.id), 'amount': '60.00'},
                        {'transaction_id': str(existing.id)}],
            'deletes': ['00000000-0000-0000-0000-000000000000'],
        })
        self.assertFalse(is_error, data)
        self.assertEqual(data['counts'], {'applied': 3, 'rejected': 4})
        self.assertEqual([(a['op'], a['index']) for a in data['applied']],
                         [('create', 0), ('create', 1), ('update', 0)])
        rejected = {(r['op'], r['index']): r['errors'] for r in data['rejected']}
        self.assertIn('account', rejected[('create', 2)])
        self.assertIn('date', rejected[('create', 3)])
        self.assertIn('nothing to update', rejected[('update', 1)])
        self.assertIn('unknown transaction', rejected[('delete', 0)])
        self.assertEqual(Transaction.objects.get(merchant='Deliveroo').created_by, self.partner)
        existing.refresh_from_db()
        self.assertEqual(str(existing.amount), '60.00')
        self.assertEqual(ActivityLog.objects.filter(entity_type='transaction', source='mcp').count(), 3)

        is_error, data = self.call_tool('transactions_list', {'date_from': '2026-10-01', 'date_to': '2026-10-31'})
        self.assertFalse(is_error, data)
        self.assertEqual(data['count'], 3)
        self.assertEqual(data['totals'], {'GBP': '93.40'})
        pizza = next(t for t in data['transactions'] if t['merchant'] == 'Pizza')
        self.assertEqual(pizza['account'], 'Joint current')

        is_error, data = self.call_tool('transactions_apply', {'deletes': [str(existing.id)]})
        self.assertFalse(is_error, data)
        self.assertFalse(Transaction.objects.filter(id=existing.id).exists())
        is_error, text = self.call_tool('transactions_apply', {})
        self.assertTrue(is_error)

    def test_prompt_mentions_transactions(self):
        self.client.force_authenticate(self.user)
        prompt = self.client.get(reverse('agents-prompt')).data['prompt']
        self.assertIn('`transactions_apply`', prompt)
        self.assertIn('One-off spending recorded this month', prompt)
        self.assertNotIn('{{', prompt)
