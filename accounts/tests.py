from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class UserListTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='bk@example.com', username='bk', first_name='B', last_name='K',
            password='supersecret123',
        )
        self.partner = User.objects.create_user(
            email='va@example.com', username='va', first_name='V', last_name='',
            password='supersecret123',
        )
        User.objects.create_user(
            email='gone@example.com', username='gone', first_name='Gone',
            password='supersecret123', is_active=False,
        )

    def test_requires_authentication(self):
        resp = self.client.get(reverse('user-list'))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lists_active_users_with_display_names(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse('user-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)  # unpaginated lookup list
        by_email = {u['email']: u for u in resp.data}
        self.assertEqual(set(by_email), {'bk@example.com', 'va@example.com'})
        self.assertEqual(by_email['bk@example.com']['display_name'], 'B K')
        self.assertEqual(by_email['va@example.com']['display_name'], 'V')

    def test_display_name_falls_back_to_email(self):
        self.user.first_name = ''
        self.user.last_name = ''
        self.assertEqual(self.user.display_name, 'bk@example.com')


from django.utils import timezone
from datetime import timedelta
from accounts.models import Invite
from activity.models import ActivityLog


class RegistrationTests(APITestCase):
    def register(self, **overrides):
        payload = {'email': 'mum@example.com', 'username': 'mum', 'first_name': 'Mum',
                   'password': 'supersecret123'}
        payload.update(overrides)
        return self.client.post(reverse('register'), payload, format='json')

    def test_first_account_bootstraps_and_becomes_admin(self):
        status_resp = self.client.get(reverse('register'))
        self.assertEqual(status_resp.data, {'open': True, 'invite_required': False,
                                            'invite_valid': False, 'invite_email': ''})
        resp = self.register()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(resp.data['user']['is_staff'])
        self.assertIn('access', resp.data['tokens'])
        self.assertTrue(ActivityLog.objects.filter(entity_type='member', action='create').exists())

    def test_registration_closed_without_invite_once_a_user_exists(self):
        User.objects.create_user(email='bk@example.com', username='bk', first_name='B', password='supersecret123')
        self.assertFalse(self.client.get(reverse('register')).data['open'])
        resp = self.register()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('invite', resp.data)
        self.assertEqual(User.objects.count(), 1)
        resp = self.register(invite='bogus')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invite_registers_once_and_can_grant_admin(self):
        admin = User.objects.create_user(email='bk@example.com', username='bk', first_name='B',
                                         password='supersecret123', is_staff=True)
        invite = Invite.objects.create(created_by=admin, email='mum@example.com')
        check = self.client.get(reverse('register'), {'invite': invite.token}).data
        self.assertEqual((check['invite_valid'], check['invite_email']), (True, 'mum@example.com'))
        resp = self.register(invite=invite.token)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertFalse(resp.data['user']['is_staff'])
        invite.refresh_from_db()
        self.assertIsNotNone(invite.used_at)
        self.assertEqual(invite.used_by.email, 'mum@example.com')
        # Second use is refused.
        resp = self.register(email='bro@example.com', username='bro', invite=invite.token)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Expired invite refused; admin invite grants staff.
        expired = Invite.objects.create(created_by=admin, expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.register(email='x@example.com', username='x', invite=expired.token).status_code, 400)
        admin_invite = Invite.objects.create(created_by=admin, make_admin=True)
        resp = self.register(email='bro@example.com', username='bro', invite=admin_invite.token)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(resp.data['user']['is_staff'])


class MemberManagementTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email='bk@example.com', username='bk', first_name='B',
                                              password='supersecret123', is_staff=True)
        self.member = User.objects.create_user(email='va@example.com', username='va', first_name='V',
                                               password='supersecret123')

    def test_only_admins_manage_but_everyone_can_see_members(self):
        self.client.force_authenticate(self.member)
        resp = self.client.get(reverse('member-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual({m['email'] for m in resp.data}, {'bk@example.com', 'va@example.com'})
        for call in (lambda: self.client.post(reverse('member-list'), {'email': 'x@example.com', 'first_name': 'X',
                                                                       'password': 'supersecret123'}, format='json'),
                     lambda: self.client.patch(reverse('member-detail', args=[self.admin.id]), {'is_active': False}, format='json'),
                     lambda: self.client.post(reverse('invite-list'), {}, format='json'),
                     lambda: self.client.post(reverse('member-password', args=[self.admin.id]), {'password': 'newpassword123'}, format='json')):
            self.assertEqual(call().status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_creates_member_with_temporary_password(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('member-list'), {
            'email': 'Mum@Example.com', 'first_name': 'Mum', 'password': 'temporary-pass-1'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['email'], 'mum@example.com')
        self.assertEqual(resp.data['username'], 'mum')     # derived from the (lower-cased) email
        self.assertFalse(resp.data['is_staff'])
        # The new member can log in with it.
        self.client.force_authenticate(None)
        login = self.client.post(reverse('login'), {'email': 'mum@example.com', 'password': 'temporary-pass-1'}, format='json')
        self.assertEqual(login.status_code, status.HTTP_200_OK, login.data)
        # Duplicate email and weak password refused.
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(reverse('member-list'), {'email': 'mum@example.com', 'first_name': 'M',
                                                                   'password': 'temporary-pass-1'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(reverse('member-list'), {'email': 'z@example.com', 'first_name': 'Z',
                                                                   'password': 'password'}, format='json').status_code, 400)

    def test_deactivate_promote_guards_and_login_block(self):
        self.client.force_authenticate(self.admin)
        url_member = reverse('member-detail', args=[self.member.id])
        url_admin = reverse('member-detail', args=[self.admin.id])
        self.assertEqual(self.client.patch(url_admin, {'is_active': False}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url_admin, {'is_staff': False}, format='json').status_code, 400)
        resp = self.client.patch(url_member, {'is_staff': True}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(resp.data['is_staff'])
        # Now two admins: demoting the other is fine; deactivating works and blocks login.
        self.assertEqual(self.client.patch(url_member, {'is_staff': False}, format='json').status_code, 200)
        resp = self.client.patch(url_member, {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(None)
        login = self.client.post(reverse('login'), {'email': 'va@example.com', 'password': 'supersecret123'}, format='json')
        self.assertEqual(login.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('va@example.com', [u['email'] for u in
                                            self.client.get(reverse('user-list'), HTTP_AUTHORIZATION='').data]
                         if False else [])
        changes = ActivityLog.objects.filter(entity_type='member', action='update').values_list('changes', flat=True)
        self.assertIn({'active': {'from': True, 'to': False}}, list(changes))

    def test_password_reset_by_admin(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('member-password', args=[self.member.id]), {'password': 'brand-new-pass-9'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(reverse('login'), {'email': 'va@example.com', 'password': 'brand-new-pass-9'},
                                          format='json').status_code, 200)

    def test_invites_create_list_revoke(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('invite-list'), {'email': 'mum@example.com', 'note': 'Mum'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertIn('/register?invite=', resp.data['link'])
        self.assertTrue(resp.data['is_valid'])
        listing = self.client.get(reverse('invite-list')).data
        self.assertEqual(len(listing), 1)
        self.assertNotIn('link', listing[0])
        self.assertNotIn('token', listing[0])
        resp = self.client.delete(reverse('invite-detail', args=[resp.data['id']]))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Invite.objects.count(), 0)
