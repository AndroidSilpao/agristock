from datetime import timedelta
import csv

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator
from urllib.parse import urlencode

from .forms import AnimalForm, FarmRecordForm
from .models import Animal, FarmRecord

User = get_user_model()

MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=1)
INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
LOCKED_MESSAGE = 'Too many failed attempts. Locked for 1 minute.'


def _reset_lock_state(request):
    request.session['failed_attempts'] = 0
    request.session['lock_time'] = None


def _get_lock_state(request):
    failed_attempts = request.session.get('failed_attempts', 0)
    lock_time = request.session.get('lock_time')

    if not lock_time:
        return failed_attempts, None

    try:
        unlock_time = timezone.datetime.fromisoformat(lock_time)
    except (TypeError, ValueError):
        _reset_lock_state(request)
        return 0, None

    if timezone.now() < unlock_time:
        remaining = int((unlock_time - timezone.now()).total_seconds())
        return failed_attempts, remaining

    _reset_lock_state(request)
    return 0, None


def _set_lock_state(request):
    lock_until = timezone.now() + LOCK_DURATION
    request.session['failed_attempts'] = MAX_FAILED_ATTEMPTS
    request.session['lock_time'] = lock_until.isoformat()
    return int(LOCK_DURATION.total_seconds())


def _validate_registration_data(data):
    errors = {}

    username = data.get('username', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    if not username:
        errors['username'] = 'Username is required.'
    elif User.objects.filter(username=username).exists():
        errors['username'] = 'Username already taken.'

    if not first_name:
        errors['first_name'] = 'First name is required.'

    if not last_name:
        errors['last_name'] = 'Last name is required.'

    if not email:
        errors['email'] = 'Email is required.'
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
        else:
            if User.objects.filter(email=email).exists():
                errors['email'] = 'Email already registered.'

    if not password:
        errors['password'] = 'Password is required.'
    elif len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters.'
    else:
        try:
            validate_password(password)
        except ValidationError as exc:
            errors['password'] = ' '.join(exc.messages)

    if password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'

    return errors


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    failed_attempts, remaining = _get_lock_state(request)
    if remaining is not None:
        messages.error(request, f'Too many failed attempts. Try again in {remaining} seconds.')
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    if request.method == 'GET':
        return render(request, 'auth/login.html')

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    user = authenticate(request, username=username, password=password)

    if user is not None:
        _reset_lock_state(request)
        login(request, user)
        return redirect('dashboard')

    failed_attempts += 1
    request.session['failed_attempts'] = failed_attempts
    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        remaining = _set_lock_state(request)
        messages.error(request, LOCKED_MESSAGE)
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    remaining_attempts = MAX_FAILED_ATTEMPTS - failed_attempts
    messages.error(request, f'{INVALID_LOGIN_MESSAGE} {remaining_attempts} attempts remaining.')
    return render(request, 'auth/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required(login_url='login')
def home(request):
    today = timezone.localdate()
    animals = Animal.objects.filter(user=request.user)
    records = FarmRecord.objects.filter(user=request.user)
    month_finance = records.filter(
        record_type=FarmRecord.RecordType.FINANCE,
        record_date__year=today.year,
        record_date__month=today.month,
    )
    income = month_finance.filter(category__iexact='income').aggregate(total=Sum('amount'))['total'] or 0
    expenses = month_finance.filter(category__iexact='expense').aggregate(total=Sum('amount'))['total'] or 0
    upcoming = records.filter(
        record_type=FarmRecord.RecordType.HEALTH,
        next_due_date__lte=today + timedelta(days=30),
    ).select_related('animal').order_by('next_due_date')[:5]

    return render(request, 'home.html', {
        'active_animals': animals.filter(status=Animal.Status.ACTIVE).count(),
        'total_animals': animals.count(),
        'income': income,
        'expenses': expenses,
        'net': income - expenses,
        'feed_records': records.filter(record_type=FarmRecord.RecordType.FEED).count(),
        'health_records': records.filter(record_type=FarmRecord.RecordType.HEALTH).count(),
        'upcoming': upcoming,
        'recent_records': records.select_related('animal')[:6],
        'today': today,
    })


def _farm_records(user, record_type='all', query=''):
    records = FarmRecord.objects.filter(user=user).select_related('animal')
    if record_type != 'all':
        records = records.filter(record_type=record_type)
    if query:
        records = records.filter(
            Q(title__icontains=query)
            | Q(category__icontains=query)
            | Q(notes__icontains=query)
            | Q(animal__tag__icontains=query)
            | Q(animal__name__icontains=query)
        )
    return records


def _farm_animals(user, query='', status=''):
    animals = Animal.objects.filter(user=user)
    if query:
        animals = animals.filter(
            Q(tag__icontains=query)
            | Q(name__icontains=query)
            | Q(species__icontains=query)
            | Q(breed__icontains=query)
        )
    if status in Animal.Status.values:
        animals = animals.filter(status=status)
    return animals


@login_required(login_url='login')
def animal_list(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    page = Paginator(_farm_animals(request.user, query, status), 15).get_page(request.GET.get('page'))
    return render(request, 'livestock/animals.html', {
        'animals': page,
        'query': query,
        'status_filter': status,
        'total_animals': Animal.objects.filter(user=request.user).count(),
    })


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def animal_create(request):
    form = AnimalForm(request.POST if request.method == 'POST' else None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        animal = form.save(commit=False)
        animal.user = request.user
        animal.save()
        messages.success(request, f'{animal.tag} has been added to your herd.')
        return redirect('animals')
    return render(request, 'livestock/form.html', {
        'form': form,
        'form_kind': 'animal',
        'page_title': 'Add an animal',
        'submit_label': 'Save animal',
    })


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def animal_edit(request, pk):
    animal = get_object_or_404(Animal, pk=pk, user=request.user)
    form = AnimalForm(
        request.POST if request.method == 'POST' else None,
        instance=animal,
        user=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{animal.tag} has been updated.')
        return redirect('animals')
    return render(request, 'livestock/form.html', {
        'form': form,
        'form_kind': 'animal',
        'page_title': f'Edit {animal.tag}',
        'submit_label': 'Save changes',
        'animal': animal,
    })


@login_required(login_url='login')
@require_POST
def animal_delete(request, pk):
    animal = get_object_or_404(Animal, pk=pk, user=request.user)
    tag = animal.tag
    animal.delete()
    messages.success(request, f'{tag} has been removed from your herd.')
    return redirect('animals')


@login_required(login_url='login')
def record_list(request):
    record_type = request.GET.get('type', 'all').strip()
    if record_type not in {'all', *FarmRecord.RecordType.values}:
        return HttpResponse('Choose a valid record type.', status=400)
    query = request.GET.get('q', '').strip()
    records = _farm_records(request.user, record_type, query)
    page = Paginator(records, 15).get_page(request.GET.get('page'))
    context = {
        'records': page,
        'query': query,
        'record_type': record_type,
        'record_types': FarmRecord.RecordType.choices,
        'income_total': 0,
        'expense_total': 0,
        'net_total': 0,
        'feed_totals': [],
    }
    if record_type in {'all', FarmRecord.RecordType.FINANCE}:
        finance = _farm_records(request.user, FarmRecord.RecordType.FINANCE, query)
        context['income_total'] = finance.filter(category__iexact='income').aggregate(total=Sum('amount'))['total'] or 0
        context['expense_total'] = finance.filter(category__iexact='expense').aggregate(total=Sum('amount'))['total'] or 0
        context['net_total'] = context['income_total'] - context['expense_total']
    if record_type == FarmRecord.RecordType.FEED:
        context['feed_totals'] = list(
            records.filter(quantity__isnull=False)
            .values('unit')
            .annotate(total=Sum('quantity'))
            .order_by('unit')
        )
    return render(request, 'livestock/records.html', context)


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def record_create(request):
    selected_type = request.GET.get('type', FarmRecord.RecordType.FINANCE)
    if selected_type not in FarmRecord.RecordType.values:
        return HttpResponse('Choose a valid record type.', status=400)
    form = FarmRecordForm(request.POST if request.method == 'POST' else None, user=request.user)
    if request.method == 'GET':
        form.initial['record_type'] = selected_type
        if selected_type == FarmRecord.RecordType.FINANCE:
            form.initial['category'] = 'income'
    else:
        selected_type = request.POST.get('record_type', selected_type)
    if request.method == 'POST' and form.is_valid():
        record = form.save(commit=False)
        record.user = request.user
        record.save()
        messages.success(request, 'Your farm record has been saved.')
        return redirect(f"{reverse('records')}?{urlencode({'type': record.record_type})}")
    return render(request, 'livestock/form.html', {
        'form': form,
        'form_kind': 'record',
        'page_title': 'Add a farm record',
        'submit_label': 'Save record',
        'record_type': selected_type,
    })


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def record_edit(request, pk):
    record = get_object_or_404(FarmRecord, pk=pk, user=request.user)
    form = FarmRecordForm(
        request.POST if request.method == 'POST' else None,
        instance=record,
        user=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        record = form.save()
        messages.success(request, 'Your farm record has been updated.')
        return redirect(f"{reverse('records')}?{urlencode({'type': record.record_type})}")
    return render(request, 'livestock/form.html', {
        'form': form,
        'form_kind': 'record',
        'page_title': f'Edit {record.title}',
        'submit_label': 'Save changes',
        'record': record,
        'record_type': record.record_type,
    })


@login_required(login_url='login')
@require_POST
def record_delete(request, pk):
    record = get_object_or_404(FarmRecord, pk=pk, user=request.user)
    record_type = record.record_type
    record.delete()
    messages.success(request, 'Your farm record has been deleted.')
    return redirect(f"{reverse('records')}?{urlencode({'type': record_type})}")


@login_required(login_url='login')
def export_records(request):
    record_type = request.GET.get('type', 'all').strip()
    if record_type not in {'all', *FarmRecord.RecordType.values}:
        return HttpResponse('Choose a valid record type.', status=400)
    query = request.GET.get('q', '').strip()
    records = _farm_records(request.user, record_type, query)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response.write('\ufeff')
    filename = f'farm-{record_type}-records-{timezone.localdate().isoformat()}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow([
        'Type', 'Date', 'Title', 'Category', 'Animal tag', 'Animal',
        'Quantity', 'Unit', 'Amount', 'Next due date', 'Notes',
    ])
    for record in records:
        writer.writerow([
            record.get_record_type_display(),
            record.record_date.isoformat(),
            _csv_safe(record.title),
            _csv_safe(record.category),
            _csv_safe(record.animal.tag if record.animal else ''),
            _csv_safe(record.animal.name if record.animal else ''),
            record.quantity if record.quantity is not None else '',
            _csv_safe(record.unit),
            record.amount,
            record.next_due_date.isoformat() if record.next_due_date else '',
            _csv_safe(record.notes),
        ])
    return response


def _csv_safe(value):
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')):
        return f"'{value}"
    return value


@login_required(login_url='login')
def export_animals(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    animals = _farm_animals(request.user, query, status)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response.write('\ufeff')
    response['Content-Disposition'] = (
        f'attachment; filename="farm-animals-{timezone.localdate().isoformat()}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow([
        'Tag', 'Name', 'Species', 'Breed', 'Sex', 'Date of birth',
        'Status', 'Purchase value', 'Notes',
    ])
    for animal in animals:
        writer.writerow([
            _csv_safe(animal.tag),
            _csv_safe(animal.name),
            _csv_safe(animal.species),
            _csv_safe(animal.breed),
            animal.get_sex_display(),
            animal.date_of_birth.isoformat() if animal.date_of_birth else '',
            animal.get_status_display(),
            animal.purchase_value,
            _csv_safe(animal.notes),
        ])
    return response


@require_http_methods(['GET', 'POST'])
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'GET':
        return render(request, 'auth/register.html')

    form_data = {
        'username': request.POST.get('username', ''),
        'first_name': request.POST.get('first_name', ''),
        'last_name': request.POST.get('last_name', ''),
        'email': request.POST.get('email', ''),
        'password': request.POST.get('password', ''),
        'confirm_password': request.POST.get('confirm_password', ''),
    }

    errors = _validate_registration_data(form_data)
    if errors:
        return render(request, 'auth/register.html', {'errors': errors, 'form_data': form_data})

    user = User.objects.create_user(
        username=form_data['username'].strip(),
        first_name=form_data['first_name'].strip(),
        last_name=form_data['last_name'].strip(),
        email=form_data['email'].strip(),
        password=form_data['password'],
    )
    login(request, user)
    return redirect('dashboard')
