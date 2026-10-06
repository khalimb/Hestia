from rest_framework import generics

from .models import ManualFxRate
from .serializers import ManualFxRateSerializer


class ManualFxRateListCreateView(generics.ListCreateAPIView):
    """GET: all manual rates. POST {currency, units_per_usd, note?}: set or
    replace the rate for that currency."""
    queryset = ManualFxRate.objects.select_related('updated_by')
    serializer_class = ManualFxRateSerializer
    pagination_class = None

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)


class ManualFxRateDetailView(generics.DestroyAPIView):
    queryset = ManualFxRate.objects.all()
    serializer_class = ManualFxRateSerializer
    lookup_field = 'currency'
