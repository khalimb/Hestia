from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .fx import rates_to_usd
from .models import FxRate, ManualFxRate

User = get_user_model()
OFFLINE = dict(FX_API_BASE='http://127.0.0.1:9', FX_FALLBACK_API_BASE='http://127.0.0.1:9')


@override_settings(**OFFLINE)
class RateChainTests(APITestCase):
    def test_manual_rate_beats_everything_and_usd_is_one(self):
        FxRate.objects.create(date=date(2026, 9, 30), currency='GBP', rate_to_usd='1.25')
        ManualFxRate.objects.create(currency='GBP', units_per_usd='0.5', rate_to_usd='2')
        rates, unconverted, rate_date, sources = rates_to_usd(['GBP', 'USD'], date(2026, 9, 30))
        self.assertEqual(rates, {'GBP': Decimal('2'), 'USD': Decimal('1')})
        self.assertEqual(sources, {'GBP': 'manual', 'USD': 'USD'})
        self.assertEqual(unconverted, [])

    def test_exact_date_cache_is_used_without_network(self):
        FxRate.objects.create(date=date(2026, 9, 30), currency='GBP', rate_to_usd='1.25')
        rates, unconverted, _, sources = rates_to_usd(['GBP'], date(2026, 9, 30))
        self.assertEqual(rates['GBP'], Decimal('1.25'))
        self.assertEqual(sources['GBP'], 'ecb')

    def test_fallback_feed_used_for_currencies_the_ecb_lacks(self):
        with patch('core.fx._fetch_ecb', return_value={'GBP': Decimal('1.25')}), \
             patch('core.fx._fetch_erapi', return_value={'UZS': Decimal('0.00008474')}) as erapi:
            rates, unconverted, _, sources = rates_to_usd(['GBP', 'UZS'], date(2026, 9, 30))
        self.assertEqual(rates['GBP'], Decimal('1.25'))
        self.assertEqual(rates['UZS'], Decimal('0.00008474'))
        self.assertEqual(sources, {'GBP': 'ecb', 'UZS': 'latest'})
        self.assertEqual(unconverted, [])
        erapi.assert_called_once_with(['UZS'])          # only what the ECB did not return
        # Cached: ECB under the requested date, the broad feed under today.
        self.assertEqual(FxRate.objects.get(currency='GBP').date, date(2026, 9, 30))
        uzs = FxRate.objects.get(currency='UZS')
        self.assertEqual((uzs.date, uzs.source), (date.today(), 'erapi'))
        # Second call for a different past date: no network for UZS, today's row reused.
        with patch('core.fx._fetch_ecb', return_value={}) as ecb, \
             patch('core.fx._fetch_erapi', return_value={}) as erapi2:
            rates, unconverted, _, sources = rates_to_usd(['UZS'], date(2026, 8, 31))
        self.assertEqual(sources['UZS'], 'latest')
        erapi2.assert_not_called()

    def test_stale_then_unconverted(self):
        FxRate.objects.create(date=date(2026, 9, 1), currency='UZS', rate_to_usd='0.00008', source='erapi')
        rates, unconverted, _, sources = rates_to_usd(['UZS', 'KGS'], date(2026, 9, 30))
        self.assertEqual(sources['UZS'], 'cached 2026-09-01')
        self.assertEqual(unconverted, ['KGS'])
        self.assertNotIn('KGS', rates)

    def test_future_date_is_capped_at_today(self):
        _, _, rate_date, _ = rates_to_usd([], date.today() + timedelta(days=40))
        self.assertEqual(rate_date, date.today())


class ManualRateEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='bk@example.com', username='bk', first_name='B', password='supersecret123')
        self.client.force_authenticate(self.user)

    def test_set_update_list_delete(self):
        resp = self.client.post(reverse('fx-manual-list'),
                                {'currency': 'uzs', 'units_per_usd': '11800', 'note': 'bank rate'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['currency'], 'UZS')
        self.assertEqual(resp.data['rate_to_usd'], '0.00008475')
        self.assertEqual(resp.data['updated_by_name'], 'B')
        # Same currency again = update, not a duplicate.
        resp = self.client.post(reverse('fx-manual-list'), {'currency': 'UZS', 'units_per_usd': '12000'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(ManualFxRate.objects.count(), 1)
        self.assertEqual(str(ManualFxRate.objects.get().units_per_usd), '12000.000000')
        self.assertEqual(len(self.client.get(reverse('fx-manual-list')).data), 1)
        resp = self.client.delete(reverse('fx-manual-detail', args=['UZS']))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ManualFxRate.objects.count(), 0)

    def test_validation(self):
        for payload in ({'currency': 'USD', 'units_per_usd': '1'},
                        {'currency': 'U', 'units_per_usd': '1'},
                        {'currency': 'UZS', 'units_per_usd': '0'}):
            resp = self.client.post(reverse('fx-manual-list'), payload, format='json')
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, payload)
