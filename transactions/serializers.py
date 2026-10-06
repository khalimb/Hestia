from rest_framework import serializers

from activity.services import ActivityLoggedSerializerMixin
from expenses.serializers import validate_payment_account_rule

from .models import Transaction


class TransactionSerializer(ActivityLoggedSerializerMixin, serializers.ModelSerializer):
    activity_entity = 'transaction'
    activity_fields = {
        'date': 'date', 'amount': 'amount', 'currency': 'currency', 'merchant': 'merchant',
        'notes': 'notes', 'expense_type': 'expense_type_name', 'subject': 'subject_name',
        'payment_method': 'payment_method_name', 'account': 'account_name',
        'paid_by': 'paid_by_name',
    }
    expense_type_name = serializers.CharField(source='expense_type.name', read_only=True, default=None)
    subject_name = serializers.CharField(source='subject.name', read_only=True, default=None)
    payment_method_name = serializers.CharField(
        source='payment_method.name', read_only=True, default=None,
    )
    account_name = serializers.CharField(source='account.name', read_only=True, default=None)
    paid_by_name = serializers.CharField(source='paid_by.display_name', read_only=True, default=None)

    class Meta:
        model = Transaction
        fields = [
            'id', 'date', 'amount', 'currency', 'merchant', 'notes',
            'expense_type', 'expense_type_name', 'subject', 'subject_name',
            'payment_method', 'payment_method_name', 'account', 'account_name',
            'paid_by', 'paid_by_name', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def activity_label(self, instance):
        return f"{instance.merchant} · {instance.date}"

    def validate(self, attrs):
        return validate_payment_account_rule(attrs, self.instance)
