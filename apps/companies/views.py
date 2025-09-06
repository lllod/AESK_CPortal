from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.serializers import ExcelUploadSerializer
from apps.companies.services import process_excel_file

from datetime import datetime


class ExcelUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ExcelUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file_obj = serializer.validated_data['file']
        start = datetime.now()
        print(f'Время старта: {start}')
        rows = process_excel_file(file_obj, request.user)
        finish = datetime.now()
        print(f'Время окончания: {finish}')
        print(f'Время работы: {finish - start}')
        return Response({'rows_processed': rows}, status=status.HTTP_201_CREATED)
