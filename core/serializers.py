from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers

from .models import ManualFxRate


class ManualFxRateSerializer(serializers.ModelSerializer):
    """Entered as units per USD; rate_to_usd is derived."""
    # Declared explicitly so the model's unique validator does not block the
    # upsert-by-currency behaviour of create().
    currency = serializers.CharField(max_length=3)
    updated_by_name = serializers.CharField(source='updated_by.display_name', read_only=True, default=None)

    class Meta:
        model = ManualFxRate
        fields = ['currency', 'units_per_usd', 'rate_to_usd', 'note', 'updated_by_name', 'updated_at']
        read_only_fields = ['rate_to_usd', 'updated_by_name', 'updated_at']

    def validate_currency(self, value):
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError('Use a 3-letter currency code, e.g. UZS.')
        if value == 'USD':
            raise serializers.ValidationError('USD is the base currency; it needs no rate.')
        return value

    def validate_units_per_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError('Must be greater than zero.')
        return value

    def _derive(self, validated_data):
        units = validated_data['units_per_usd']
        validated_data['rate_to_usd'] = (Decimal(1) / units).quantize(
            Decimal('0.00000001'), rounding=ROUND_HALF_UP)
        return validated_data

    def create(self, validated_data):
        # Upsert by currency so saving an existing code just updates it.
        validated_data = self._derive(validated_data)
        obj, _ = ManualFxRate.objects.update_or_create(
            currency=validated_data.pop('currency'), defaults=validated_data)
        return obj

    def update(self, instance, validated_data):
        return super().update(instance, self._derive(validated_data))
