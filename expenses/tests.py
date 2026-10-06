from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import PaymentMethod, PaymentAccount, Expense

User = get_user_model()


class PaymentAttributesTestCase(APITestCase):
    """Shared fixtures: two family members, a cash method, a direct-debit
    method that uses an account, and one account."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='bk@example.com', username='bk', first_name='B', last_name='K',
            password='supersecret123',
        )
        self.partner = User.objects.create_user(
            email='va@example.com', username='va', first_name='V', last_name='A',
            password='supersecret123',
        )
        self.cash = PaymentMethod.objects.create(name='Cash', requires_account=False, is_default=True)
        self.direct_debit = PaymentMethod.objects.create(
            name='Direct Debit', requires_account=True, is_default=True,
        )
        self.joint = PaymentAccount.objects.create(name='Joint current')
        self.client.force_authenticate(self.user)

    def _expense_payload(self, **overrides):
        payload = {
            'name': 'Council tax',
            'amount': '150.00',
            'currency': 'GBP',
            'recurrence_type': 'monthly',
            'start_date': '2026-10-01',
        }
        payload.update(overrides)
        return payload


class ExpensePaymentAttributesTests(PaymentAttributesTestCase):
    def test_create_with_method_account_and_responsible(self):
        resp = self.client.post(reverse('expense-list'), self._expense_payload(
            payment_method=str(self.direct_debit.id),
            account=str(self.joint.id),
            responsible=str(self.partner.id),
        ), format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['payment_method_name'], 'Direct Debit')
        self.assertEqual(resp.data['account_name'], 'Joint current')
        self.assertEqual(resp.data['responsible_name'], 'V A')

    def test_all_three_are_optional(self):
        resp = self.client.post(reverse('expense-list'), self._expense_payload(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertIsNone(resp.data['payment_method'])
        self.assertIsNone(resp.data['account'])
        self.assertIsNone(resp.data['responsible'])
        self.assertIsNone(resp.data['payment_method_name'])
        self.assertIsNone(resp.data['responsible_name'])

    def test_account_rejected_without_a_payment_method(self):
        resp = self.client.post(reverse('expense-list'), self._expense_payload(
            account=str(self.joint.id),
        ), format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('account', resp.data)

    def test_account_rejected_when_method_does_not_use_one(self):
        resp = self.client.post(reverse('expense-list'), self._expense_payload(
            payment_method=str(self.cash.id),
            account=str(self.joint.id),
        ), format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('account', resp.data)
        self.assertIn('Cash', str(resp.data['account']))

    def test_account_optional_even_when_method_uses_one(self):
        resp = self.client.post(reverse('expense-list'), self._expense_payload(
            payment_method=str(self.direct_debit.id),
        ), format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertIsNone(resp.data['account'])

    def test_patch_switching_method_to_cash_keeps_rule_against_stored_account(self):
        expense = Expense.objects.create(
            created_by=self.user, payment_method=self.direct_debit, account=self.joint,
            **self._expense_payload(),
        )
        resp = self.client.patch(
            reverse('expense-detail', args=[expense.id]),
            {'payment_method': str(self.cash.id)}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('account', resp.data)
        expense.refresh_from_db()
        self.assertEqual(expense.payment_method, self.direct_debit)

    def test_patch_switching_method_and_clearing_account_together_is_allowed(self):
        expense = Expense.objects.create(
            created_by=self.user, payment_method=self.direct_debit, account=self.joint,
            **self._expense_payload(),
        )
        resp = self.client.patch(
            reverse('expense-detail', args=[expense.id]),
            {'payment_method': str(self.cash.id), 'account': None}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['payment_method_name'], 'Cash')
        self.assertIsNone(resp.data['account'])

    def test_list_filters_by_payment_method_account_and_responsible(self):
        Expense.objects.create(
            created_by=self.user, payment_method=self.direct_debit, account=self.joint,
            responsible=self.partner, **self._expense_payload(name='DD one'),
        )
        Expense.objects.create(
            created_by=self.user, payment_method=self.cash,
            **self._expense_payload(name='Cash one'),
        )
        for params, expected in [
            ({'payment_method': str(self.direct_debit.id)}, {'DD one'}),
            ({'account': str(self.joint.id)}, {'DD one'}),
            ({'responsible': str(self.partner.id)}, {'DD one'}),
            ({'payment_method': str(self.cash.id)}, {'Cash one'}),
        ]:
            resp = self.client.get(reverse('expense-list'), params)
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            self.assertEqual({e['name'] for e in resp.data['results']}, expected, params)


class DictionaryDeleteGuardTests(PaymentAttributesTestCase):
    def test_default_payment_method_cannot_be_deleted(self):
        resp = self.client.delete(reverse('paymentmethod-detail', args=[self.cash.id]))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(PaymentMethod.objects.filter(id=self.cash.id).exists())

    def test_payment_method_in_use_cannot_be_deleted(self):
        custom = PaymentMethod.objects.create(name='Cheque', created_by=self.user)
        Expense.objects.create(created_by=self.user, payment_method=custom, **self._expense_payload())
        resp = self.client.delete(reverse('paymentmethod-detail', args=[custom.id]))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('in use', resp.data['detail'])

    def test_unused_custom_payment_method_deletes(self):
        custom = PaymentMethod.objects.create(name='Cheque', created_by=self.user)
        resp = self.client.delete(reverse('paymentmethod-detail', args=[custom.id]))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_account_in_use_cannot_be_deleted(self):
        Expense.objects.create(
            created_by=self.user, payment_method=self.direct_debit, account=self.joint,
            **self._expense_payload(),
        )
        resp = self.client.delete(reverse('paymentaccount-detail', args=[self.joint.id]))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(PaymentAccount.objects.filter(id=self.joint.id).exists())

    def test_unused_account_deletes(self):
        resp = self.client.delete(reverse('paymentaccount-detail', args=[self.joint.id]))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_create_dictionary_entries_records_creator(self):
        resp = self.client.post(
            reverse('paymentmethod-list'), {'name': 'Cheque', 'requires_account': True}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['created_by'], self.user.id)
        self.assertTrue(resp.data['requires_account'])
        self.assertFalse(resp.data['is_default'])

        resp = self.client.post(
            reverse('paymentaccount-list'), {'name': 'Savings', 'notes': 'rainy day'}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['created_by'], self.user.id)
