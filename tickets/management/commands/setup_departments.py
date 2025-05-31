from django.core.management.base import BaseCommand
from tickets.models import Department, Ticket
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Sets up initial departments and cleans up existing tickets'

    def handle(self, *args, **kwargs):
        # First, delete all existing tickets
        ticket_count = Ticket.objects.all().count()
        Ticket.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {ticket_count} existing tickets'))

        # Create departments using predefined choices
        departments = [
            {
                'name': 'it_support',
                'description': 'Technical support and infrastructure issues'
            },
            {
                'name': 'customer_service',
                'description': 'General customer inquiries and support'
            },
            {
                'name': 'hr',
                'description': 'Human Resources related inquiries'
            },
            {
                'name': 'finance',
                'description': 'Financial and billing related issues'
            },
            {
                'name': 'operations',
                'description': 'General operations and logistics'
            },
            {
                'name': 'maintenance',
                'description': 'Facility maintenance and repairs'
            },
            {
                'name': 'security',
                'description': 'Security and access control'
            },
            {
                'name': 'sales',
                'description': 'Sales and business development'
            }
        ]

        created_count = 0
        for dept_data in departments:
            dept, created = Department.objects.get_or_create(
                name=dept_data['name'],
                defaults={'description': dept_data['description']}
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created department: {dept.get_name_display()}'))
            else:
                self.stdout.write(self.style.WARNING(f'Department already exists: {dept.get_name_display()}'))

        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} departments')) 