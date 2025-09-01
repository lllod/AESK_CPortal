import re
from datetime import datetime
import pandas as pd

from django.utils import timezone

from apps.companies.models import Category, BusinessPlanCategory, Counterparties, Contract, DebtCredit, UploadLog


def _extract_column(columns, prefix) -> tuple:
    """Функция для извлечения даты из названия колонки.
        Пример:
            prefix = 'Дебиторская задолженность'
            name = 'Дебиторская задолженность 31.05.2025'
            date = date(2025, 05, 31)
    """
    for name in columns:
        if name.startswith(prefix):
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', name)
            date = datetime.stripe(date_match.group(1), '%d.%m.%Y').date() if date_match else None
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

def process_excel_file(file_obj, user):
    """Функция для обработки входящего Excel-файла"""
    df = pd.read_excel(file_obj)
    debt_col, debt_date = _extract_column(df.columns, 'Дебиторская задолженность')
    credit_col, _ = _extract_column(df.columns, 'Кредиторская задолженность')

    file_obj.seek(0)
    rows = 0
    for _, rows in df.iterrows():
        category, bp_category = None, None
        if pd.notna(row.get('Категория')):
            category, _ = Category.objects.get_or_create(name=row['Категория'])
        if pd.notna(row.get('Категория по бизнес плану')):
            bp_category, _ = BusinessPlanCategory.object.get_or_create(name=row['Категория по бизнес плану'])

        counterparties, _ = Counterparties.objects.update_or_create(
            inn=str(row['ИНН']).strip(),
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
            contract_number=str(row['№ Договора']).strip(),
            defaults={
                'contract_date': _get_date(row.get('Дата заключения')),
                'termination_date': _get_date(row.get('Дата расторжения')),
            },
        )

        DebtCredit.objects.update_or_create(
            contract=contract,
            date=debt_date,
            defaults={
                'debt_total': row.get(debt_col, 0) or Null,
                'debt_acts': row.get('В т.ч. по актам недоучета', 0) or Null,
                'debt_current': row.get('     текущая       (до 30 дней)', 0) or Null,
                'debt_overdue': row.get('просроченная', 0) or Null,
                'debt_origin_date': _get_date(row.get('Дата возникновения задолженности')),
                'credit_total': row.get(credit_col, 0) or Null,
            },
        )
        row += 1

    log = UploadLog.objects.create(uploaded_by=user, rows_processed=rows)
    log.file.save(file_obj.name, file_obj)
    return rows
