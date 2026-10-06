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
