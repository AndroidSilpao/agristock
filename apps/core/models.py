from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Animal(models.Model):
    class Sex(models.TextChoices):
        FEMALE = 'female', 'Female'
        MALE = 'male', 'Male'
        UNKNOWN = 'unknown', 'Unknown'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        SOLD = 'sold', 'Sold'
        DECEASED = 'deceased', 'Deceased'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='farm_animals',
    )
    tag = models.CharField(max_length=40)
    name = models.CharField(max_length=80, blank=True)
    species = models.CharField(max_length=50)
    breed = models.CharField(max_length=80, blank=True)
    sex = models.CharField(max_length=10, choices=Sex.choices, default=Sex.UNKNOWN)
    date_of_birth = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    purchase_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tag']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'tag'],
                name='unique_farm_animal_tag_per_user',
            ),
        ]

    def __str__(self):
        return f'{self.tag} — {self.name or self.species}'


class FarmRecord(models.Model):
    class RecordType(models.TextChoices):
        FINANCE = 'finance', 'Livestock finance'
        FEED = 'feed', 'Livestock feed'
        HEALTH = 'health', 'Livestock health'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='farm_records',
    )
    record_type = models.CharField(max_length=10, choices=RecordType.choices)
    title = models.CharField(max_length=120)
    category = models.CharField(max_length=40)
    record_date = models.DateField(default=timezone.localdate)
    animal = models.ForeignKey(
        Animal,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='records',
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    unit = models.CharField(max_length=20, blank=True)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    next_due_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-record_date', '-created_at']

    def __str__(self):
        return f'{self.get_record_type_display()}: {self.title}'
