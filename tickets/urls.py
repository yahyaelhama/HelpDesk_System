from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('my-tickets/', views.my_tickets, name='my_tickets'),
    path('tickets/create/', views.create_ticket, name='create_ticket'),
    path('tickets/<int:pk>/', views.ticket_detail, name='ticket_detail'),
    path('tickets/<int:pk>/update/', views.update_ticket, name='update_ticket'),
    path('tickets/<int:ticket_id>/attachments/<int:attachment_id>/delete/', 
         views.delete_attachment, name='delete_attachment'),
         
    # Staff management URLs
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/create/', views.staff_create, name='staff_create'),
    path('staff/create-alt/', views.staff_create_alt, name='staff_create_alt'),
    path('staff/<int:pk>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/edit-user/<int:pk>/', views.staff_edit_alt, name='staff_edit_alt'),
    path('staff/<int:pk>/delete/', views.staff_delete, name='staff_delete'),
]