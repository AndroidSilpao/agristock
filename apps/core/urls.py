from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('home/', views.home, name='dashboard'),
    path('animals/', views.animal_list, name='animals'),
    path('animals/export/', views.export_animals, name='animals_export'),
    path('animals/add/', views.animal_create, name='animal_add'),
    path('animals/<int:pk>/edit/', views.animal_edit, name='animal_edit'),
    path('animals/<int:pk>/delete/', views.animal_delete, name='animal_delete'),
    path('records/', views.record_list, name='records'),
    path('records/add/', views.record_create, name='record_add'),
    path('records/<int:pk>/edit/', views.record_edit, name='record_edit'),
    path('records/<int:pk>/delete/', views.record_delete, name='record_delete'),
    path('records/export/', views.export_records, name='records_export'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
]