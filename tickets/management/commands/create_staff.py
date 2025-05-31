from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tickets.models import Department
from getpass import getpass

class Command(BaseCommand):
    help = 'Creates a new staff member and assigns them to departments'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username for the new staff member')
        parser.add_argument('email', type=str, help='Email for the new staff member')
        parser.add_argument('first_name', type=str, help='First name of the staff member')
        parser.add_argument('last_name', type=str, help='Last name of the staff member')
        parser.add_argument('departments', type=str, nargs='+', help='Department codes to assign (space-separated)')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        first_name = options['first_name']
        last_name = options['last_name']
        department_codes = options['departments']

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR(f'User {username} already exists'))
            return

        # Get password securely
        password = getpass('Enter password for new staff member: ')
        confirm_password = getpass('Confirm password: ')

        if password != confirm_password:
            self.stdout.write(self.style.ERROR('Passwords do not match'))
            return

        # Create the user
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=True
            )
            self.stdout.write(self.style.SUCCESS(f'Created staff member: {user.get_full_name()}'))

            # Assign departments
            for dept_code in department_codes:
                try:
                    dept = Department.objects.get(name=dept_code)
                    dept.staff.add(user)
                    self.stdout.write(self.style.SUCCESS(f'Added to department: {dept.get_name_display()}'))
                except Department.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'Department not found: {dept_code}'))

            self.stdout.write(self.style.SUCCESS('Staff member creation completed'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating staff member: {str(e)}')) 