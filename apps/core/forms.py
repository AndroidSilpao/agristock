from django import forms

from .models import Animal, FarmRecord


class FarmFormMixin:
    def add_field_classes(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'


class AnimalForm(FarmFormMixin, forms.ModelForm):
    class Meta:
        model = Animal
        fields = [
            'tag', 'name', 'species', 'breed', 'sex', 'date_of_birth',
            'status', 'purchase_value', 'notes',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'purchase_value': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.add_field_classes()
        self.fields['tag'].widget.attrs.update({'placeholder': 'e.g. COW-024', 'autofocus': True})
        self.fields['species'].widget.attrs.update({'placeholder': 'e.g. Cattle, goat, poultry'})

    def clean_tag(self):
        tag = self.cleaned_data['tag'].strip()
        matching_animals = Animal.objects.filter(user=self.user, tag__iexact=tag)
        if self.instance.pk:
            matching_animals = matching_animals.exclude(pk=self.instance.pk)
        if matching_animals.exists():
            raise forms.ValidationError('This tag is already in use on your farm.')
        return tag


class FarmRecordForm(FarmFormMixin, forms.ModelForm):
    class Meta:
        model = FarmRecord
        fields = [
            'record_type', 'title', 'category', 'record_date', 'animal',
            'quantity', 'unit', 'amount', 'next_due_date', 'notes',
        ]
        widgets = {
            'record_date': forms.DateInput(attrs={'type': 'date'}),
            'next_due_date': forms.DateInput(attrs={'type': 'date'}),
            'quantity': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['animal'].queryset = Animal.objects.filter(user=self.user).order_by('tag')
        self.fields['animal'].required = False
        self.fields['animal'].empty_label = 'Herd-wide livestock record'
        self.fields['quantity'].required = False
        self.fields['amount'].required = False
        self.fields['next_due_date'].required = False
        self.add_field_classes()
        self.fields['category'].widget.attrs.update({
            'list': 'farm-category-options',
            'placeholder': 'Choose or enter a category',
        })

    def clean_animal(self):
        animal = self.cleaned_data.get('animal')
        if animal and animal.user_id != self.user.pk:
            raise forms.ValidationError('Choose an animal from your farm.')
        return animal

    def clean_category(self):
        category = self.cleaned_data['category'].strip()
        if self.cleaned_data.get('record_type') == FarmRecord.RecordType.FINANCE:
            category = category.lower()
            if category not in {'income', 'expense'}:
                raise forms.ValidationError('Choose income or expense for a finance record.')
        return category

    def clean_amount(self):
        return self.cleaned_data.get('amount') or 0
