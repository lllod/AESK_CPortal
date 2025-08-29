from django.db import models
from django.contrib.auth import get_user_model
import django.utils.timezone
import decimal

from apps.common.models import BaseModel


class Category(models.Model):
    """
    Модель для справочника категорий организации из СТЕК.

    Атрибуты:
        name (str): наименование категории.
    """
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'


class BusinessPlanCategory(models.Model):
    """
    Модель для справочника категорий организации по бизнес-плану из СТЕК.

    Атрибуты:
        name (str): наименование категории.
    """
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = 'Категория по бизнес-плану'
        verbose_name_plural = 'Категории по бизнес-плану'


class Counterparties(BaseModel):
    """
    Основная модель приложения - модель для контрагентов (основные данные из ОФ-9 (СТЕК)) и DaData).

    Атрибуты:
        inn (str): ИНН юридического лица либо индивидуального предпринимателя.
        name_from_excel (str): Наименование из ОФ-9 (СТЕК).
        name_from_dadata (str): Наименование из DaData.
        address_from_excel (str): Адрес из ОФ-9 (СТЕК).
        address_from_dadata (str): Адрес из DaData.
        counterparties_type (str): Тип организации (ЮЛ либо ИП).
        branch_type (str): Тип подразделения (головная либо филиал).
        parent (UUIDField): Указание головной организации, если контрагент является филиалом, иначе Null.
        category (Category): категория, к которой отнесен контрагент.
        business_plan_category (BusinessPlanCategory): категория по бизнес-плану, к которой отнесен контрагент.
        counterparty_contact (CounterpartyContact): контактное лицо контрагента.
        kpp (str): КПП юридического лица.
        ogrn (str): ОГРН контрагента.
        ogrn_date (DateTimeField): дата выдачи ОГРН контрагенту.
        name_full_with_opf (str): полное наименование контрагента.
        okved (str): код ОКВЭД контрагента.
        opf_full (str): полное название организационно-правовой формы контрагента.
        opf_short (str): краткое название организационно-правовой формы контрагента.
        counterparties (Counterparties): контрагент, по которому получены данные из сервиса DaData.
        registration_date (DateTimeField): дата регистрации контрагента.
        liquidation_date (DateTimeField): дата ликвидации контрагента.
    """

    TYPE_CHOICES = [
        ('LEGAL', 'ЮЛ'),
        ('INDIVIDUAL', 'ИП'),
    ]

    BRANCH_CHOICES = [
        ('MAIN', 'Головная организация'),
        ('BRANCH', 'Филиал'),
    ]

    inn = models.CharField(max_length=12, db_index=True)
    name_from_excel = models.CharField(max_length=512)
    name_from_dadata = models.CharField(max_length=512, blank=True, default='')
    address_from_excel = models.CharField(max_length=1024)
    address_from_dadata = models.CharField(max_length=1024, blank=True, default='')
    counterparties_type = models.TextChoices(max_length=10, choices=TYPE_CHOICES, blank=True, default='')
    branch_type = models.TextChoices(max_length=20, choices=BRANCH_CHOICES, blank=True, default='')
    parent = models.ForeignKey('self', blank=True, null=True, on_delete=models.SET_NULL, related_name='branches')
    category = models.ForeignKey(Category, blank=True, null=True, on_delete=models.CASCADE, related_name='categories')
    business_plan_category = models.ForeignKey(BusinessPlanCategory, blank=True, null=True, on_delete=models.CASCADE,
                                               related_name='business_plan_categories')
    counterparty_contact = models.ForeignKey('CounterpartyContact', blank=True, null=True, on_delete=models.CASCADE,
                                             related_name='contact')
    kpp = models.CharField(max_length=9, blank=True, null=True)
    ogrn = models.CharField(max_length=13)
    ogrn_date = models.DateTimeField()
    name_full_with_opf = models.CharField(max_length=512)
    okved = models.CharField(max_length=8)
    opf_full = models.CharField(max_length=64)
    opf_short = models.CharField(max_length=8)
    registration_date = models.DateTimeField()
    liquidation_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['inn', 'counterparties_type', 'branch_type']),
        ]


class CounterpartiesState(models.Model):
    """
    Модель для состояния контрагентов. Необходимо для отслеживания изменений.

    Атрибуты:
        actuality_date (DateTimeField): дата последних изменений контрагента.
        status (str): текущий статус контрагента.
        code (int): детальный статус контрагента из справочника DaData.
        counterparties (Counterparties): контрагент, к которому относится экземпляр модели.
    """

    STATUS_CHOICES = [
        ('ACTIVE', 'Действующая'),
        ('LIQUIDATING', 'Ликвидируется'),
        ('LIQUIDATED', 'Ликвидирована'),
        ('BANKRUPT', 'Банкротство'),
        ('REORGANIZING', 'В процессе присоединения к другому ЮЛ'),
    ]

    actuality_date = models.DateTimeField()
    status = models.TextChoices(max_length=37, choices=STATUS_CHOICES)
    code = models.IntegerField(blank=True, null=True)
    counterparties = models.ForeignKey(Counterparties, related_name='states', on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'liquidation_date', 'actuality_date']),
        ]


class UploadLog(BaseModel):
    """
    Модель для отслеживания загрузок Excel-файлов с данными из ОФ-9.

    Атрибуты:
        uploaded_by (auth.User): пользователь, который загрузил файл.
        file_name (str): наименование загруженного файла.
        rows_processed (int): количество строк в загруженном файле.
        file (ExcelFiled): загруженный Excel-файл.
    """

    uploaded_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255, default=f'of-9-file-{timezone.now()}.xlsx', blank=True, null=True)
    rows_processed = models.PositiveIntegerField(default=0)
    file = models.FileField(upload_to='uploads/%Y/%m')

    class Meta:
        indexes = [
            models.Index(fields=['uploaded_by']),
        ]


class Contract(BaseModel):
    """
    Модель для информации по договору контрагента.

    Атрибуты:
        contract_number (str): номер договора контрагента.
        contract_date (DateField): дата заключения договора.
        termination_date (DateField): дата расторжения договора.
        district (str): район, в котором располагается контрагент.
        counterparties (Counterparties): контрагент, с которым заключен договор.
    """

    contract_number = models.CharField(max_length=32)
    contract_date = models.DateField(blank=True, null=True)
    termination_date = models.DateField(blank=True, null=True)
    district = models.CharField(max_length=16, blank=True, null=True)
    counterparties = models.ForeignKey(Counterparties, related_name='contracts', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('contract_number', 'counterparties')
        indexes = [
            models.Index(fields=['contract_number']),
        ]


class DebtCredit(models.Model):
    """
    Модель для информации о дебиторской и кредиторской задолженностях контрагента.

    Атрибуты:
        debt_total (Decimal): дебиторская задолженность контрагента.
        debt_acts (Decimal): дебиторская задолженность контрагента, в том числе по актам недоучета.
        debt_current (Decimal): текущая (до 30 дней) дебиторская задолженность контрагента.
        debt_overdue (Decimal): просроченная дебиторская задолженность контрагента.
        debt_origin_date (DteField): дата возникновение задолженности контрагента.
        credit_total (Decimal): кредиторская задолженность контрагента.
        date (DateField): дата обновления данных о дебиторской и/или кредиторской задолженностиях.
        contract (Contract): договор, по котором присутствуют дебиторская и/или кредиторская задолженности.
    """

    debt_total = models.DecimalField(max_digits=21, decimal_places=5, default=Decimal('0.00'), blank=True, null=True)
    debt_acts = models.DecimalField(max_digits=21, decimal_places=5, default=Decimal('0.00'), blank=True, null=True)
    debt_current = models.DecimalField(max_digits=21, decimal_places=5, default=Decimal('0.00'), blank=True, null=True)
    debt_overdue = models.DecimalField(max_digits=21, decimal_places=5, default=Decimal('0.00'), blank=True, null=True)
    debt_origin_date = models.DateField(blank=True, null=True)
    credit_total = models.DecimalField(max_digits=21, decimal_places=5, default=Decimal('0.00'), blank=True, null=True)
    date = models.DateField()
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='debts_and_credits')


class CounterpartyContact(BaseModel):
    """
    Модель для представителя юридического лица либо индивидуального предпринимателя.

    Атрибуты:
        name (str): ФИО представителя контрагента (руководитель либо собственник).
        post (str): занимаемая представителем должность (только для юридического лица).
        start_date (DateTimeField): дата вступления представителем в должность (только для юридического лица).
    """

    name = models.CharField(max_length=128)
    post = models.CharField(max_length=64, blank=True, default='')
    start_date = models.DateTimeField(blank=True, null=True)
