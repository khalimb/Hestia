from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from activity.services import ActivityLoggedSerializerMixin

from .models import (
    Subject, ExpenseType, PaymentMethod, PaymentAccount, Expense, Occurrence,
)


class SubjectSerializer(ActivityLoggedSerializerMixin, serializers.ModelSerializer):
    activity_entity = 'subject'
    activity_fields = {'name': 'name'}

    class Meta:
        model = Subject
        fields = ['id', 'name', 'is_default', 'created_by']
        read_only_fields = ['id', 'is_default', 'created_by']


class ExpenseTypeSerializer(ActivityLoggedSerializerMixin, serializers.ModelSerializer):
    activity_entity = 'expense_type'
    activity_fields = {'name': 'name'}

    class Meta:
        model = ExpenseType
        fields = ['id', 'name', 'is_default', 'created_by']
        read_only_fields = ['id', 'is_default', 'created_by']


class PaymentMethodSerializer(ActivityLoggedSerializerMixin, serializers.ModelSerializer):
    activity_entity = 'payment_method'
    activity_fields = {'name': 'name', 'requires_account': 'requires_account'}

    class Meta:
        model = PaymentMethod
        fields = ['id', 'name', 'requires_account', 'is_default', 'created_by']
        read_only_fields = ['id', 'is_default', 'created_by']


class PaymentAccountSerializer(ActivityLoggedSerializerMixin, serializers.ModelSerializer):
    activity_entity = 'payment_account'
    activity_fields = {'name': 'name', 'notes': 'notes'}

    class Meta:
        model = PaymentAccount
        fields = ['id', 'name', 'notes', 'created_by']
        read_only_fields = ['id', 'created_by']


class OccurrenceSerializer(serializers.ModelSerializer):
    expense_name = serializers.CharField(source='expense.name', read_only=True)
    # The expense's configured method, so payment forms can default to it.
    expense_payment_method_name = serializers.CharField(
        source='expense.payment_method.name', read_only=True, default=None,
    )
    total_paid = serializers.SerializerMethodField()

    class Meta:
        model = Occurrence
        fields = [
            'id', 'expense', 'expense_name', 'expense_payment_method_name',
            'due_date', 'expected_amount',
            'currency', 'status', 'created_at', 'total_paid',
        ]
        read_only_fields = ['id', 'expense', 'created_at']

    def get_total_paid(self, obj):
        total = obj.payments.aggregate(total=Sum('amount_paid'))['total']
        return str(total) if total else '0.00'


class ExpenseSerializer(ActivityLoggedSerializerMixin, serializers.ModelSerializer):
    activity_entity = 'expense'
    # Logged with display names for relations, so a row reads like the UI.
    activity_fields = {
        'name': 'name', 'description': 'description', 'amount': 'amount',
        'currency': 'currency', 'recurrence_type': 'recurrence_type',
        'subject': 'subject_name', 'expense_type': 'expense_type_name',
        'payment_method': 'payment_method_name', 'account': 'account_name',
        'responsible': 'responsible_name', 'start_date': 'start_date',
        'end_date': 'end_date', 'is_active': 'is_active',
    }
    subject_name = serializers.CharField(source='subject.name', read_only=True, default=None)
    expense_type_name = serializers.CharField(source='expense_type.name', read_only=True, default=None)
    payment_method_name = serializers.CharField(
        source='payment_method.name', read_only=True, default=None,
    )
    account_name = serializers.CharField(source='account.name', read_only=True, default=None)
    responsible_name = serializers.CharField(
        source='responsible.display_name', read_only=True, default=None,
    )
    next_occurrence = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = [
            'id', 'name', 'description', 'subject', 'subject_name',
            'amount', 'currency',
            'expense_type', 'expense_type_name',
            'recurrence_type',
            'payment_method', 'payment_method_name',
            'account', 'account_name',
            'responsible', 'responsible_name',
            'start_date', 'end_date', 'is_active', 'created_by',
            'created_at', 'updated_at', 'next_occurrence',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        # An account only makes sense for methods that draw from one (card,
        # direct debit). On partial updates fall back to the stored values so
        # a PATCH that switches the method to e.g. Cash is caught too.
        def effective(field):
            if field in attrs:
                return attrs[field]
            return getattr(self.instance, field, None) if self.instance else None

        method = effective('payment_method')
        account = effective('account')
        if account is not None:
            if method is None:
                raise serializers.ValidationError({
                    'account': 'Choose a payment method that uses an account before setting one.',
                })
            if not method.requires_account:
                raise serializers.ValidationError({
                    'account': f'"{method.name}" does not use an account.',
                })
        return attrs

    def get_next_occurrence(self, obj):
        today = timezone.now().date()
        # Prefer the next upcoming unpaid occurrence
        occ = obj.occurrences.filter(
            due_date__gte=today,
            status__in=['pending', 'overdue'],
        ).first()
        if not occ:
            # Fall back to the most recent unpaid occurrence (overdue)
            occ = obj.occurrences.filter(
                status__in=['pending', 'overdue'],
            ).order_by('-due_date').first()
        if occ:
            return OccurrenceSerializer(occ).data
        return None


class ExpenseDetailSerializer(ExpenseSerializer):
    recent_occurrences = serializers.SerializerMethodField()

    class Meta(ExpenseSerializer.Meta):
        fields = ExpenseSerializer.Meta.fields + ['recent_occurrences']

    def get_recent_occurrences(self, obj):
        occs = obj.occurrences.all()[:10]
        return OccurrenceSerializer(occs, many=True).data
