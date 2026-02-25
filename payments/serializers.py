from rest_framework import serializers
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    logged_by_name = serializers.CharField(source='logged_by.first_name', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'occurrence', 'amount_paid', 'currency', 'paid_date',
            'payment_method', 'notes', 'logged_by', 'logged_by_name', 'created_at',
        ]
        read_only_fields = ['id', 'occurrence', 'logged_by', 'created_at']
