from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import re
import pandas as pd

from django.db import transaction

from apps.companies.models import (
    Category,
    BusinessPlanCategory,
    Counterparties,
    Contract,
    DebtCredit,
    UploadLog
)


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
    """Функция для получения корректного значения суммы"""
    if pd.isna(value):
        return Decimal('0.00000')

    clean_str = str(value).replace(',', '.')

    try:
        return Decimal(clean_str).quantize(Decimal('0.00000'), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return Decimal('0.00000')


def _value_changed(old, new) -> bool:
    """Функция для старого и нового параметров"""
    return old != new


def _clean_inn(value) -> str:
    """Функция для нормализации ИНН"""
    if pd.isna(value):
        return ''
    return re.sub(r'\D', '', str(value).rstrip('0')) or ''


def _addr_key(value) -> str:
    if pd.isna(value):
        return ''
    return str(value).strip()


def process_excel_file(file_obj, user) -> int:
    """Функция для обработки входящего Excel-файла"""
    try:
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

        rows = df.to_dict('records')

        with (transaction.atomic()):
            # Категории
            category_names = {r['Категория'] for r in rows if r.get('Категория')}
            categories = {c.name: c for c in Category.objects.filter(name__in=category_names)}
            missing_categories = [Category(name=name) for name in category_names if name not in categories]
            Category.objects.bulk_create(missing_categories, ignore_conflicts=True, batch_size=500)
            if missing_categories:
                new_categories = Category.objects.filter(name__in=[c.name for c in missing_categories])
                categories.update({c.name: c for c in new_categories})

            bp_names = {r['Категория по бизнес плану'] for r in rows if r.get('Категория по бизнес плану')}
            bp_categories = {c.name: c for c in BusinessPlanCategory.objects.filter(name__in=bp_names)}
            missing_bp_categories = [BusinessPlanCategory(name=name) for name in bp_names if name not in bp_categories]
            BusinessPlanCategory.objects.bulk_create(missing_bp_categories, ignore_conflicts=True, batch_size=500)
            if missing_bp_categories:
                new_bp_categories = BusinessPlanCategory.objects.filter(name__in=[c.name for c in missing_bp_categories])
                bp_categories.update({c.name: c for c in new_bp_categories})

            # Контрагенты
            counterparties_rows, failed_counterparties = {}, []
            count = 0
            for r in rows:
                inn = _clean_inn(r.get('ИНН'))
                count += 1
                print('*' * 10)
                print(count)
                print(inn)
                address = _addr_key(r.get('Адрес'))
                key = (inn, address)

                if key not in counterparties_rows:
                    counterparties_rows[key] = r

            inns = {inn for inn, _ in counterparties_rows.keys()}
            existing_counterparties_qs = Counterparties.objects.filter(inn__in=inns)
            existing_counterparties = {(c.inn, _addr_key(c.address_from_excel)): c for c in existing_counterparties_qs}
            new_counterparties, update_counterparties_groups = [], {}
            for (inn, address), r in counterparties_rows.items():
                cat = categories.get(r.get('Категория'))
                bp_cat = bp_categories.get(r.get('Категория по бизнес плану'))
                defaults = {
                    'name_from_excel': r.get('Наименование предприятия', ''),
                    'address_from_excel': address,
                    'district': r.get('Район', ''),
                    'category': cat,
                    'business_plan_category': bp_cat,
                }

                counterparties = existing_counterparties.get((inn, address))

                if counterparties is None:
                    try:
                        new_counterparties.append(Counterparties(
                            inn=inn,
                            **defaults
                        ))
                    except Exception as e:
                        failed_counterparties.append({
                            'ИНН': inn,
                            'Адрес': address,
                            'Наименование предприятия': r.get('Наименование предприятия'),
                            'Ошибка': str(e)
                        })
                    continue

                update_counterparties = []
                for field, new_value in defaults.items():
                    old_value = getattr(counterparties, field)
                    if _value_changed(old_value, new_value):
                        setattr(counterparties, field, new_value)
                        update_counterparties.append(field)

                if update_counterparties:
                    key = tuple(sorted(update_counterparties))
                    update_counterparties_groups.setdefault(key, []).append(counterparties)

            if new_counterparties:
                try:
                    Counterparties.objects.bulk_create(new_counterparties, batch_size=500)
                except Exception as e:
                    for cp in new_counterparties:
                        failed_counterparties.append({
                            'ИНН': cp.inn,
                            'Адрес': cp.address_from_excel,
                            'Наименование предприятия': cp.name_from_excel,
                            'Ошибка': str(e)
                        })

            if failed_counterparties:
                print("Не удалось добавить следующие контрагенты:")
                for failed in failed_counterparties:
                    print(f"ИНН: {failed['ИНН']}")
                    print(f"Адрес: {failed['Адрес']}")
                    print(f"Наименование предприятия: {failed['Наименование предприятия']}")
                    print(f"Ошибка: {failed['Ошибка']}")
                    print("-" * 40)

            for fields_tuple, counterparties in update_counterparties_groups.items():
                Counterparties.objects.bulk_update(
                    counterparties,
                    list(fields_tuple),
                    batch_size=500
                )
            counterparties_qs = Counterparties.objects.filter(inn__in=inns)
            counterparties_map = {(c.inn, _addr_key(c.address_from_excel)): c for c in counterparties_qs}

            # Договоры
            contract_rows = {}
            for r in rows:
                contract_number = str(r.get('№ Договора')).strip()
                if not contract_number:
                    continue
                elif contract_number not in contract_rows:
                    contract_rows[contract_number] = r
            contracts_numbers = list(contract_rows.keys())
            existing_contracts = {c.contract_number: c for c in
                                  Contract.objects.filter(contract_number__in=contracts_numbers).select_related(
                                      'counterparties')}
            new_contracts, update_contracts_groups = [], {}
            for cn, r in contract_rows.items():
                inn = _clean_inn(r.get('ИНН'))
                if not inn:
                    continue
                address = _addr_key(r.get('Адрес'))
                counterparties = counterparties_map.get((inn, address))
                if not counterparties:
                    continue
                defaults = {
                    'contract_date': _get_date(r.get('Дата заключения')),
                    'termination_date': _get_date(r.get('Дата расторжения')),
                    'counterparties': counterparties
                }

                contract = existing_contracts.get(cn)
                if contract is None:
                    new_contracts.append(Contract(
                        contract_number=cn,
                        **defaults
                    ))
                    continue

                update_contracts = []
                for field, new_value in defaults.items():
                    old_value = getattr(contract, field)
                    if _value_changed(old_value, new_value):
                        setattr(contract, field, new_value)
                        update_contracts.append(field)

                if update_contracts:
                    key = tuple(sorted(update_contracts))
                    update_contracts_groups.setdefault(key, []).append(contract)

            if new_contracts:
                Contract.objects.bulk_create(new_contracts, batch_size=500)

            for fields_tuple, contracts in update_contracts_groups.items():
                Contract.objects.bulk_update(
                    contracts,
                    list(fields_tuple),
                    batch_size=500
                )
            contracts_qs = Contract.objects.filter(contract_number__in=contracts_numbers).select_related(
                    'counterparties')
            contracts_map = {c.contract_number: c for c in contracts_qs}

            # Дебиторка/кредиторка
            existing_dc_qs = DebtCredit.objects.filter(contract_id__in=[c.id for c in contracts_map.values()])
            existing_dc = {dc.contract_id: dc for dc in existing_dc_qs}
            new_dc, update_dc_groups = [], {}
            for cn, r in contract_rows.items():
                contract = contracts_map.get(cn)
                if not contract:
                    continue
                defaults = {
                    'debt_total': _get_decimal(r.get(debt_col)),
                    'debt_acts': _get_decimal(r.get('В т.ч. по актам недоучета.1')),
                    'debt_current': _get_decimal(r.get('     текущая       (до 30 дней).1')),
                    'debt_overdue': _get_decimal(r.get('просроченная.1')),
                    'debt_origin_date': _get_date(r.get('Дата возникновения задолженности')),
                    'credit_total': _get_decimal(r.get(credit_col)),
                    'date': debt_date,
                }

                dc = existing_dc.get(contract.id)
                if dc is None:
                    new_dc.append(DebtCredit(
                        contract=contract,
                        **defaults
                    ))
                    continue

                update_dc = []
                for field, new_value in defaults.items():
                    old_value = getattr(dc, field)
                    if _value_changed(old_value, new_value):
                        setattr(dc, field, new_value)
                        update_dc.append(field)

                if update_dc:
                    key = tuple(sorted(update_dc))
                    update_dc_groups.setdefault(key, []).append(dc)

            if new_dc:
                DebtCredit.objects.bulk_create(new_dc, batch_size=500)

            for fields_tuple, items in update_dc_groups.items():
                DebtCredit.objects.bulk_update(
                    items,
                    list(fields_tuple),
                    batch_size=500
                )

            log = UploadLog.objects.create(uploaded_by=user, rows_processed=len(rows))
            file_obj.seek(0)
            log.file.save(file_obj.name, file_obj)

        return len(rows)
    except Exception as exc:
        try:
            log = UploadLog.objects.create(uploaded_by=user, rows_processed=0)
            file_obj.seek(0)
            log.file.save(getattr(file_obj, 'name', 'upload.xlsx'), file_obj)
        except Exception:
            pass
        raise exc
