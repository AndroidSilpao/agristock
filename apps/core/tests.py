from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Animal, FarmRecord


class HomeViewTests(TestCase):
    def test_home_renders_for_authenticated_user(self):
        user = get_user_model().objects.create_user(username='admin', password='secret1234')

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')
        self.assertContains(response, 'AgriStock')
        self.assertContains(response, 'Digitize and streamline farm assets and logistics')

    def test_home_requires_login(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 302)


class FarmManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='farmer', password='secret1234')
        self.other_user = get_user_model().objects.create_user(username='neighbor', password='secret1234')
        self.client.force_login(self.user)

    def animal_data(self, **overrides):
        data = {
            'tag': 'COW-024',
            'name': 'Clover',
            'species': 'Cattle',
            'breed': 'Jersey',
            'sex': 'female',
            'date_of_birth': '',
            'status': 'active',
            'purchase_value': '425.00',
            'notes': '',
        }
        data.update(overrides)
        return data

    def record_data(self, **overrides):
        data = {
            'record_type': 'finance',
            'title': 'Milk sales',
            'category': 'income',
            'record_date': '2026-10-16',
            'animal': '',
            'quantity': '',
            'unit': '',
            'amount': '120.00',
            'next_due_date': '',
            'notes': '',
        }
        data.update(overrides)
        return data

    def test_animals_can_be_created_searched_and_updated(self):
        response = self.client.post(reverse('animal_add'), self.animal_data())
        self.assertRedirects(response, reverse('animals'))
        animal = Animal.objects.get(user=self.user, tag='COW-024')

        self.assertContains(self.client.get(reverse('animals') + '?q=Clover'), 'Clover')
        self.assertNotContains(self.client.get(reverse('animals') + '?q=unknown'), 'Clover')

        updated = self.animal_data(tag='COW-024', name='Clover II')
        response = self.client.post(reverse('animal_edit', args=[animal.pk]), updated)
        self.assertRedirects(response, reverse('animals'))
        animal.refresh_from_db()
        self.assertEqual(animal.name, 'Clover II')

    def test_records_are_scoped_calculated_and_exported(self):
        self.client.post(reverse('record_add'), self.record_data())
        self.client.post(
            reverse('record_add'),
            self.record_data(title='Vet supplies', category='expense', amount='30.00'),
        )
        FarmRecord.objects.create(
            user=self.other_user,
            record_type=FarmRecord.RecordType.FINANCE,
            title='Private sale',
            category='income',
            amount='999.00',
        )

        dashboard = self.client.get(reverse('dashboard'))
        self.assertContains(dashboard, '120.00')
        self.assertContains(dashboard, '30.00')
        self.assertNotContains(dashboard, '999.00')

        records = self.client.get(reverse('records') + '?type=finance')
        self.assertContains(records, '90.00')
        self.assertNotContains(records, 'Private sale')

        exported = self.client.get(reverse('records_export') + '?type=finance')
        self.assertEqual(exported.status_code, 200)
        self.assertIn('text/csv', exported['Content-Type'])
        self.assertIn(b'Milk sales', exported.content)
        self.assertNotIn(b'Private sale', exported.content)

    def test_record_rejects_animal_from_another_farm(self):
        other_animal = Animal.objects.create(
            user=self.other_user,
            tag='GOAT-1',
            species='Goat',
        )
        response = self.client.post(
            reverse('record_add'),
            self.record_data(animal=str(other_animal.pk)),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(FarmRecord.objects.filter(user=self.user).exists())

    def test_feed_health_and_animal_exports_work(self):
        animal = Animal.objects.create(
            user=self.user,
            tag='HEN-01',
            species='Poultry',
            name='Pip',
        )
        self.client.post(
            reverse('record_add'),
            self.record_data(
                record_type='feed',
                title='Layer pellets',
                category='concentrate',
                animal=str(animal.pk),
                quantity='18.50',
                unit='kg',
                amount='22.00',
            ),
        )
        due_date = timezone.localdate() + timedelta(days=4)
        self.client.post(
            reverse('record_add'),
            self.record_data(
                record_type='health',
                title='Vaccination',
                category='vaccination',
                animal=str(animal.pk),
                amount='12.00',
                next_due_date=due_date.isoformat(),
            ),
        )

        feed_response = self.client.get(reverse('records') + '?type=feed')
        self.assertContains(feed_response, '18.5')
        self.assertContains(feed_response, 'Layer pellets')
        dashboard = self.client.get(reverse('dashboard'))
        self.assertContains(dashboard, 'Vaccination')

        animal_export = self.client.get(reverse('animals_export'))
        self.assertEqual(animal_export.status_code, 200)
        self.assertIn(b'HEN-01', animal_export.content)

    def test_user_cannot_edit_or_delete_another_farms_record(self):
        record = FarmRecord.objects.create(
            user=self.other_user,
            record_type=FarmRecord.RecordType.FEED,
            title='Private feed log',
            category='hay',
        )

        self.assertEqual(
            self.client.get(reverse('record_edit', args=[record.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('record_delete', args=[record.pk])).status_code,
            404,
        )
        self.assertTrue(FarmRecord.objects.filter(pk=record.pk).exists())
