from rest_framework import serializers

from activity.services import ActivityLoggedSerializerMixin

from .models import Payment


class PaymentSerializer(ActivityLoggedSerializerMixin, serializers.ModelSerializer):
    activity_entity = 'payment'
    activity_fields = {
        'amount_paid': 'amount_paid', 'currency': 'currency', 'paid_date': 'paid_date',
        'payment_method': 'payment_method', 'notes': 'notes',
    }
    logged_by_name = serializers.CharField(source='logged_by.first_name', read_only=True)

    def activity_label(self, instance):
        return f"{instance.occurrence.expense.name} · due {instance.occurrence.due_date}"

    class Meta:
        model = Payment
        fields = [
            'id', 'occurrence', 'amount_paid', 'currency', 'paid_date',
            'payment_method', 'notes', 'logged_by', 'logged_by_name', 'created_at',
        ]
        read_only_fields = ['id', 'occurrence', 'logged_by', 'created_at']
