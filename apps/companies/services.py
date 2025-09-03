from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from itertools import chain
import re
import pandas as pd

from django.utils import timezone

from apps.companies.models import Category, BusinessPlanCategory, Counterparties, Contract, DebtCredit, UploadLog


def _extract_column(columns, prefix) -> tuple:
    """Функция для извлечения даты из названия колонки.
        Пример:
            prefix = 'Дебиторская задолженность'
            name = 'Дебиторская задолженность {31.05.2025}'
            date = date(2025, 05, 31)
    """
    for name in columns:
        if name.startswith(prefix):
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', name)
            date = datetime.strptime(date_match.group(1), '%d.%m.%Y').date() if date_match else None
            return name, date
    return None, None


def _get_date(value) -> datetime:
    """Функция для конвертирования объектов в формат Date."""
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().date()
    if isinstance(value, datetime):
        return value.date()
    return value


def _get_decimal(value) -> Decimal:
    if pd.isna(value):
        return Decimal('0.00000')

    clean_str = str(value).replace(',', '.')

    try:
        return Decimal(clean_str).quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return Decimal('0.00000')


def process_excel_file(file_obj, user) -> int:
    """Функция для обработки входящего Excel-файла"""
    df = pd.read_excel(
        file_obj,
        header=0,
        skiprows=[0, 1, 2, 4, 5, 6],
        usecols=[1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 27, 28, 29, 30, 37, 38],
        decimal=',',
        engine='openpyxl',
    )

    debt_col, debt_date = _extract_column(df.columns, 'Дебиторская задолженность')
    credit_col, _ = _extract_column(df.columns, 'Кредиторская задолженность')

    file_obj.seek(0)
    for _, row in df.iterrows():
        category, bp_category = None, None
        if pd.notna(row.get('Категория')):
            category, _ = Category.objects.get_or_create(name=row['Категория'])
        if pd.notna(row.get('Категория по бизнес плану')):
            bp_category, _ = BusinessPlanCategory.objects.get_or_create(name=row['Категория по бизнес плану'])

        counterparties, _ = Counterparties.objects.update_or_create(
            inn=str(row.get('ИНН')).strip(),
            defaults={
                'name_from_excel': row.get('Наименование предприятия', ''),
                'address_from_excel': row.get('Адрес', ''),
                'district': row.get('Район', ''),
                'category': category,
                'business_plan_category': bp_category,
            },
        )

        contract, _ = Contract.objects.update_or_create(
            counterparties=counterparties,
            contract_number=str(row.get('№ Договора')).strip(),
            defaults={
                'contract_date': _get_date(row.get('Дата заключения')),
                'termination_date': _get_date(row.get('Дата расторжения')),
            },
        )

        DebtCredit.objects.update_or_create(
            contract=contract,
            date=debt_date,
            defaults={
                'debt_total': _get_decimal(row.get(f'{debt_col}')),
                'debt_acts': _get_decimal(row.get('В т.ч. по актам недоучета.1')),
                'debt_current': _get_decimal(row.get('     текущая       (до 30 дней).1')),
                'debt_overdue': _get_decimal(row.get('просроченная.1')),
                'debt_origin_date': _get_date(row.get('Дата возникновения задолженности')),
                'credit_total': _get_decimal(row.get(f'{credit_col}')),
            },
        )

    log = UploadLog.objects.create(uploaded_by=user, rows_processed=len(df))
    log.file.save(file_obj.name, file_obj)
    return len(df)
