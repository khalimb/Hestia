from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from .models import Subject, ExpenseType, Expense, Occurrence


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'is_default', 'created_by']
        read_only_fields = ['id', 'is_default', 'created_by']


class ExpenseTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseType
        fields = ['id', 'name', 'is_default', 'created_by']
        read_only_fields = ['id', 'is_default', 'created_by']


class OccurrenceSerializer(serializers.ModelSerializer):
    expense_name = serializers.CharField(source='expense.name', read_only=True)
    total_paid = serializers.SerializerMethodField()

    class Meta:
        model = Occurrence
        fields = [
            'id', 'expense', 'expense_name', 'due_date', 'expected_amount',
            'currency', 'status', 'created_at', 'total_paid',
        ]
        read_only_fields = ['id', 'expense', 'created_at']

    def get_total_paid(self, obj):
        total = obj.payments.aggregate(total=Sum('amount_paid'))['total']
        return str(total) if total else '0.00'


class ExpenseSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, default=None)
    expense_type_name = serializers.CharField(source='expense_type.name', read_only=True, default=None)
    next_occurrence = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = [
            'id', 'name', 'description', 'subject', 'subject_name',
            'amount', 'currency',
            'expense_type', 'expense_type_name',
            'recurrence_type', 'recurrence_day', 'recurrence_month',
            'start_date', 'end_date', 'is_active', 'created_by',
            'created_at', 'updated_at', 'next_occurrence',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_next_occurrence(self, obj):
        occ = obj.occurrences.filter(
            due_date__gte=timezone.now().date(),
            status__in=['pending', 'overdue'],
        ).first()
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
