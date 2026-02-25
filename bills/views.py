from django.conf import settings
from rest_framework import generics, parsers, serializers, status
from rest_framework.response import Response
from expenses.models import Expense
from .models import Bill
from .serializers import BillSerializer


class ExpenseBillListCreateView(generics.ListCreateAPIView):
    serializer_class = BillSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        return Bill.objects.filter(expense_id=self.kwargs['expense_id'])

    def perform_create(self, serializer):
        expense = Expense.objects.get(pk=self.kwargs['expense_id'])
        uploaded_file = self.request.FILES.get('file')
        if not uploaded_file:
            raise serializers.ValidationError({'file': 'No file provided.'})
        if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            raise serializers.ValidationError({'file': 'File too large. Max 25MB.'})
        if uploaded_file.content_type not in settings.ALLOWED_UPLOAD_TYPES:
            raise serializers.ValidationError({'file': 'Invalid file type. Allowed: PDF, JPEG, PNG.'})
        serializer.save(
            expense=expense,
            uploaded_by=self.request.user,
            original_filename=uploaded_file.name,
            file_size=uploaded_file.size,
            content_type=uploaded_file.content_type,
        )


class BillDetailView(generics.RetrieveDestroyAPIView):
    queryset = Bill.objects.all()
    serializer_class = BillSerializer

    def perform_destroy(self, instance):
        instance.file.delete(save=False)
        instance.delete()
