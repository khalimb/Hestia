from rest_framework import serializers
from .models import Bill


class BillSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.first_name', read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = [
            'id', 'expense', 'occurrence', 'file', 'original_filename',
            'file_size', 'content_type', 'uploaded_by', 'uploaded_by_name',
            'uploaded_at', 'download_url',
        ]
        read_only_fields = ['id', 'uploaded_by', 'uploaded_at', 'original_filename', 'file_size', 'content_type']

    def get_download_url(self, obj):
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None
