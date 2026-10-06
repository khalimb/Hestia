from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import AgentImportConfig, IMPORT_TOKEN_PREFIX
from expenses.models import Subject, ExpenseType, PaymentMethod, PaymentAccount, Expense

User = get_user_model()


class AgentImportTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='owner@example.com', username='owner',
            first_name='Owner', password='supersecret123',
        )
        self.other = User.objects.create_user(
            email='other@example.com', username='other',
            first_name='Other', password='supersecret123',
        )
        self.subject = Subject.objects.create(name='42 Oak Street')
        self.etype = ExpenseType.objects.create(name='Rent')

    # --- helpers ---------------------------------------------------------
    def _mint_token(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(reverse('agent-import-token'))
        self.client.force_authenticate(None)
        return resp.data['token']

    # --- token lifecycle -------------------------------------------------
    def test_generate_token_is_scoped_and_prefixed(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(reverse('agent-import-token'))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data['token'].startswith(IMPORT_TOKEN_PREFIX))
        self.assertTrue(AgentImportConfig.objects.get(user=self.user).has_token)

    def test_rotate_then_revoke_token(self):
        first = self._mint_token()
        second = self._mint_token()
        self.assertNotEqual(first, second)  # rotation replaces the old token

        # Old token must no longer authenticate.
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {first}')
        resp = self.client.get(reverse('agent-import-options'))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # Revoke; the current token stops working too.
        self.client.credentials()
        self.client.force_authenticate(self.user)
        self.client.delete(reverse('agent-import-token'))
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {second}')
        resp = self.client.get(reverse('agent-import-options'))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- prompt template + assembly -------------------------------------
    def test_config_returns_default_template_then_accepts_custom(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse('agent-import-config'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('{{subjects}}', resp.data['prompt_template'])
        self.assertFalse(resp.data['is_custom_template'])

        resp = self.client.patch(
            reverse('agent-import-config'),
            {'prompt_template': 'My custom {{subjects}} template'}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['is_custom_template'])

        # Saving blank resets to the default.
        resp = self.client.patch(
            reverse('agent-import-config'),
            {'prompt_template': ''}, format='json',
        )
        self.assertFalse(resp.data['is_custom_template'])

    def test_prompt_assembles_with_token_endpoint_and_options(self):
        token = self._mint_token()
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse('agent-import-prompt'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        prompt = resp.data['prompt']
        self.assertIn(token, prompt)                       # real token embedded
        self.assertIn('/api/v1/agent-import/expenses/', prompt)  # absolute endpoint
        self.assertIn('42 Oak Street', prompt)             # subject populated
        self.assertIn(str(self.subject.id), prompt)        # ...with its id
        self.assertIn('Rent', prompt)                      # expense type populated
        self.assertNotIn('{{', prompt)                     # no unfilled placeholders

    def test_prompt_requires_a_token(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse('agent-import-prompt'))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # --- agent submission ------------------------------------------------
    def test_agent_creates_expense_with_token(self):
        token = self._mint_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        payload = {
            'name': 'Thames Water',
            'amount': '42.50',
            'currency': 'GBP',
            'recurrence_type': 'monthly',
            'start_date': '2026-07-01',
            'subject': str(self.subject.id),
            'expense_type': str(self.etype.id),
        }
        resp = self.client.post(reverse('agent-import-expense-create'), payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        expense = Expense.objects.get(id=resp.data['id'])
        self.assertEqual(expense.created_by, self.user)     # attributed to token owner
        self.assertEqual(expense.subject, self.subject)
        self.assertEqual(expense.expense_type, self.etype)
        self.assertEqual(str(expense.amount), '42.50')

    def test_submission_rejected_without_token(self):
        resp = self.client.post(reverse('agent-import-expense-create'), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer himp_not_a_real_token')
        resp = self.client.post(reverse('agent-import-expense-create'), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- scoping: the import token must NOT unlock the rest of the API ----
    def test_import_token_cannot_access_jwt_endpoints(self):
        token = self._mint_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        # The normal expenses list endpoint uses JWT auth only.
        resp = self.client.get('/api/v1/expenses/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        # And the user's own profile.
        resp = self.client.get('/api/v1/auth/me/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_options_endpoint_lists_subjects_and_types(self):
        token = self._mint_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        resp = self.client.get(reverse('agent-import-options'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = {s['name'] for s in resp.data['subjects']}
        self.assertIn('42 Oak Street', names)
        self.assertIn('monthly', resp.data['recurrence_types'])


class AgentImportPaymentAttributesTests(AgentImportTestCase):
    def setUp(self):
        super().setUp()
        self.direct_debit = PaymentMethod.objects.create(name='Direct Debit', requires_account=True)
        self.cash = PaymentMethod.objects.create(name='Cash', requires_account=False)
        self.joint = PaymentAccount.objects.create(name='Joint current')

    def test_options_include_payment_methods_accounts_and_users(self):
        token = self._mint_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        resp = self.client.get(reverse('agent-import-options'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        methods = {m['name']: m for m in resp.data['payment_methods']}
        self.assertTrue(methods['Direct Debit']['requires_account'])
        self.assertFalse(methods['Cash']['requires_account'])
        self.assertEqual([a['name'] for a in resp.data['accounts']], ['Joint current'])
        users = resp.data['users']
        self.assertEqual({u['display_name'] for u in users}, {'Owner', 'Other'})
        # Ids + names only: no contact details leak to the agent.
        self.assertEqual(set(users[0]), {'id', 'display_name'})

    def test_prompt_lists_payment_methods_with_account_hint(self):
        self._mint_token()
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse('agent-import-prompt'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        prompt = resp.data['prompt']
        self.assertIn(f'- Direct Debit (id: {self.direct_debit.id}, uses an account)', prompt)
        self.assertIn(f'- Cash (id: {self.cash.id})', prompt)
        self.assertNotIn(f'- Cash (id: {self.cash.id}, uses', prompt)
        self.assertIn(f'- Joint current (id: {self.joint.id})', prompt)
        self.assertIn(f'- Owner (id: {self.user.id})', prompt)
        self.assertIn('"payment_method":', prompt)
        self.assertNotIn('{{payment_methods}}', prompt)

    def test_agent_submission_with_payment_attributes(self):
        token = self._mint_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        payload = {
            'name': 'Thames Water', 'amount': '42.50', 'currency': 'GBP',
            'recurrence_type': 'monthly', 'start_date': '2026-07-01',
            'payment_method': str(self.direct_debit.id),
            'account': str(self.joint.id),
            'responsible': str(self.other.id),
        }
        resp = self.client.post(reverse('agent-import-expense-create'), payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        expense = Expense.objects.get(id=resp.data['id'])
        self.assertEqual(expense.payment_method, self.direct_debit)
        self.assertEqual(expense.account, self.joint)
        self.assertEqual(expense.responsible, self.other)

    def test_agent_submission_account_rule_enforced(self):
        token = self._mint_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        payload = {
            'name': 'Window cleaner', 'amount': '20', 'currency': 'GBP',
            'recurrence_type': 'monthly', 'start_date': '2026-07-01',
            'payment_method': str(self.cash.id), 'account': str(self.joint.id),
        }
        resp = self.client.post(reverse('agent-import-expense-create'), payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('account', resp.data)
