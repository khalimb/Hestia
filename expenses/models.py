import uuid
from django.conf import settings
from django.db import models


class Subject(models.Model):
    """Configurable subject/entity that an expense relates to, e.g. an apartment or car."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='subjects',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def deletion_blocker(self):
        """Reason this entry cannot be deleted, or None. Shared by the API
        viewsets and the MCP tools so the rule lives in one place."""
        if self.is_default:
            return 'Default subjects cannot be deleted.'
        if self.expenses.exists():
            return 'Cannot delete subject with existing expenses.'
        return None


class ExpenseType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='expense_types',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def deletion_blocker(self):
        """Reason this entry cannot be deleted, or None. Shared by the API
        viewsets and the MCP tools so the rule lives in one place."""
        if self.is_default:
            return 'Default expense types cannot be deleted.'
        if self.expenses.exists():
            return 'Cannot delete expense type with existing expenses.'
        return None


class PaymentMethod(models.Model):
    """Global dictionary of how an expense is paid, e.g. Cash, Card, Direct Debit.

    `requires_account` marks methods that draw from a specific account (card,
    direct debit); for those an Expense may also name a PaymentAccount.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    requires_account = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payment_methods',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def deletion_blocker(self):
        """Reason this entry cannot be deleted, or None. Shared by the API
        viewsets and the MCP tools so the rule lives in one place."""
        if self.is_default:
            return 'Default payment methods cannot be deleted.'
        if self.expenses.exists():
            return 'Cannot delete a payment method that is in use by expenses.'
        return None


class PaymentAccount(models.Model):
    """Global dictionary of accounts money is paid from, e.g. a joint current account.

    Named PaymentAccount (not Account) to avoid clashing with the `accounts`
    user-auth app.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payment_accounts',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def deletion_blocker(self):
        """Reason this entry cannot be deleted, or None. Shared by the API
        viewsets and the MCP tools so the rule lives in one place."""
        if self.expenses.exists():
            return 'Cannot delete an account that is in use by expenses.'
        return None


class Expense(models.Model):
    RECURRENCE_CHOICES = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('biannual', 'Biannual'),
        ('annual', 'Annual'),
        ('biennial', 'Biennial'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name='expenses',
        null=True, blank=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='GBP')
    expense_type = models.ForeignKey(
        ExpenseType, on_delete=models.PROTECT, related_name='expenses',
        null=True, blank=True,
    )
    recurrence_type = models.CharField(max_length=20, choices=RECURRENCE_CHOICES)
    # How, from where, and by whom the expense is paid. All optional; `account`
    # is only valid when `payment_method.requires_account` is set (enforced in
    # the serializer so API errors are field-level).
    payment_method = models.ForeignKey(
        PaymentMethod, on_delete=models.PROTECT, related_name='expenses',
        null=True, blank=True,
    )
    account = models.ForeignKey(
        PaymentAccount, on_delete=models.PROTECT, related_name='expenses',
        null=True, blank=True,
    )
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='responsible_expenses',
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='expenses',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.currency} {self.amount})"


class Occurrence(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('partial', 'Partial'),
        ('overdue', 'Overdue'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name='occurrences',
    )
    due_date = models.DateField()
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_date']
        unique_together = ['expense', 'due_date']

    def __str__(self):
        return f"{self.expense.name} - {self.due_date}"
