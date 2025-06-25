from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, Avg, F, ExpressionWrapper, DurationField
from django.core.paginator import Paginator
import os
import csv
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.utils import timezone
import logging

from .models import Ticket, Comment, Attachment, Department
from .forms import TicketForm, CommentForm, AttachmentForm, AssignTicketForm, StaffCreationForm, StaffEditForm, DepartmentForm
from django.contrib.auth.models import User
from .utils import send_ticket_created_email, send_ticket_resolved_email

# Get a logger
logger = logging.getLogger(__name__)

@login_required
def delete_attachment(request, ticket_id, attachment_id):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('ticket_detail', pk=ticket_id)

    ticket = get_object_or_404(Ticket, pk=ticket_id)
    attachment = get_object_or_404(Attachment, pk=attachment_id, ticket=ticket)
    
    # Check if user has permission to delete the attachment
    if request.user == ticket.created_by or request.user == attachment.uploaded_by or request.user.is_superuser:
        try:
            # Delete the actual file
            if attachment.file:
                file_path = attachment.file.path
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except (OSError, PermissionError) as e:
                        messages.error(request, f'Error deleting file: {str(e)}')
                        return redirect('update_ticket', pk=ticket_id)
            
            # Store the filename for the success message
            filename = os.path.basename(attachment.file.name)
            
            # Delete the attachment record
            attachment.delete()
            
            messages.success(request, f'Attachment "{filename}" was deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting attachment: {str(e)}')
    else:
        messages.error(request, 'You do not have permission to delete this attachment.')
    
    # Return to the previous page (either update or detail view)
    referer = request.META.get('HTTP_REFERER')
    if referer and 'update' in referer:
        return redirect('update_ticket', pk=ticket_id)
    return redirect('ticket_detail', pk=ticket_id)

@login_required
def dashboard(request):
    # If user is not staff, redirect to my_tickets view
    if not request.user.is_staff:
        return redirect('my_tickets')
    
    # Get filter parameters
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    search = request.GET.get('search', '')
    department_id = request.GET.get('department', '')
    
    # If user is superuser (root), show all tickets across all departments
    if request.user.is_superuser:
        tickets = Ticket.objects.all().order_by('-created_at')
        departments = Department.objects.all()
    else:
        # Get user's departments
        user_departments = request.user.departments.all()
        
        # Check if staff user has any departments, if not show a message
        if not user_departments.exists():
            messages.warning(request, "You don't belong to any departments. Please contact an administrator to be assigned to a department.")
        
        # Start with tickets from user's departments
        tickets = Ticket.objects.filter(department__in=user_departments).order_by('-created_at')
        departments = user_departments
    
    # Filter by department if provided
    if department_id:
        tickets = tickets.filter(department_id=department_id)
    
    # Filter by status if provided
    if status:
        tickets = tickets.filter(status=status)
    
    # Filter by priority if provided
    if priority:
        tickets = tickets.filter(priority=priority)
    
    # Search in title and description
    if search:
        tickets = tickets.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search)
        )
    
    # Initialize chart data context variables
    context = {
        'page_obj': None,
        'status_filter': status,
        'priority_filter': priority,
        'search_query': search,
        'departments': departments,
        'selected_department': department_id,
    }
    
    # Only prepare chart data for superusers
    if request.user.is_superuser:
        try:
            # Get chart data with default values for empty results
            status_data = list(tickets.values('status').annotate(count=Count('status')).order_by('status'))
            priority_data = list(tickets.values('priority').annotate(count=Count('priority')).order_by('priority'))
            
            # Get department distribution
            department_data = list(tickets.values('department__name').annotate(count=Count('department')).filter(department__name__isnull=False).order_by('-count'))
            
            # Add chart data to context
            context.update({
                'status_data': status_data,
                'priority_data': priority_data,
                'department_data': department_data,
            })
        except Exception as e:
            # Log the error but continue rendering the page
            print(f"Error preparing chart data: {str(e)}")
            messages.warning(request, "There was an issue loading chart data.")
            context.update({
                'status_data': [],
                'priority_data': [],
                'department_data': [],
            })
    
    # Paginate results
    paginator = Paginator(tickets, 10)  # 10 tickets per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context['page_obj'] = page_obj
    
    return render(request, 'tickets/dashboard.html', context)

@login_required
def my_tickets(request):
    # Prevent staff and superusers from viewing my_tickets
    if request.user.is_staff or request.user.is_superuser:
        messages.warning(request, "Staff and administrators do not have personal tickets.")
        return redirect('dashboard')
    
    # Get filter parameters
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    search = request.GET.get('search', '')
    department_id = request.GET.get('department', '')
    
    # Get user's tickets
    tickets = Ticket.objects.filter(created_by=request.user)
    
    # Apply filters
    if status:
        tickets = tickets.filter(status=status)
    if priority:
        tickets = tickets.filter(priority=priority)
    if department_id:
        tickets = tickets.filter(department_id=department_id)
    if search:
        tickets = tickets.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search)
        )
    
    # Order by most recent
    tickets = tickets.order_by('-created_at')
    
    # Get departments for filter dropdown
    departments = Department.objects.all()
    
    context = {
        'tickets': tickets,
        'status_filter': status,
        'priority_filter': priority,
        'search_query': search,
        'departments': departments,
        'selected_department': department_id,
    }
    return render(request, 'tickets/my_tickets.html', context)

@login_required
def create_ticket(request):
    # Prevent staff and superusers from creating tickets
    if request.user.is_staff or request.user.is_superuser:
        messages.error(request, "Administrators and staff cannot create tickets.")
        if request.user.is_staff:
            return redirect('dashboard')
        else:
            return redirect('my_tickets')
    
    if request.method == 'POST':
        form = TicketForm(request.POST, user=request.user)
        attachment_form = AttachmentForm(request.POST, request.FILES)
        
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = request.user
            ticket.save()
            
            # Handle file attachment only if a file was uploaded
            if 'file' in request.FILES:
                if attachment_form.is_valid():
                    attachment = attachment_form.save(commit=False)
                    attachment.ticket = ticket
                    attachment.uploaded_by = request.user
                    attachment.save()
                    messages.success(request, 'Ticket created with attachment successfully!')
                else:
                    messages.warning(request, 'Ticket created but there was an error with the attachment.')
            else:
                messages.success(request, 'Ticket created successfully!')
            
            # Send email notification
            logger.info(f"About to send email notification for ticket #{ticket.id}")
            try:
                send_ticket_created_email(request, ticket)
                logger.info(f"Email notification sent for ticket #{ticket.id}")
            except Exception as e:
                logger.error(f"Error sending email for ticket #{ticket.id}: {str(e)}")
                messages.warning(request, 'Ticket created but there was an error sending the email notification.')
                
            return redirect('ticket_detail', pk=ticket.pk)
    else:
        form = TicketForm(user=request.user)
        attachment_form = AttachmentForm()
    
    return render(request, 'tickets/create_ticket.html', {
        'form': form,
        'attachment_form': attachment_form
    })

@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    
    # Check if user has access to this ticket
    if not (request.user.is_superuser or (request.user.is_staff and request.user.departments.filter(id=ticket.department.id).exists()) or request.user == ticket.created_by):
        messages.error(request, "You don't have permission to view this ticket.")
        return redirect('my_tickets')
    
    comments = ticket.comments.all().order_by('created_at')
    attachments = ticket.attachments.all()
    
    # Forms
    comment_form = CommentForm()
    attachment_form = AttachmentForm()
    assign_form = None
    
    # Only create assign form for staff members in the same department or superusers
    if request.user.is_staff and not request.user.is_superuser and request.user.departments.filter(id=ticket.department.id).exists():
        assign_form = AssignTicketForm(instance=ticket, department=ticket.department)
    
    # Handle comment submission
    if request.method == 'POST' and 'submit_comment' in request.POST:
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.ticket = ticket
            comment.author = request.user
            comment.save()
            messages.success(request, 'Comment added successfully!')
            return redirect('ticket_detail', pk=pk)
    
    # Handle attachment upload
    if request.method == 'POST' and 'submit_attachment' in request.POST:
        attachment_form = AttachmentForm(request.POST, request.FILES)
        if attachment_form.is_valid():
            attachment = attachment_form.save(commit=False)
            attachment.ticket = ticket
            attachment.uploaded_by = request.user
            attachment.save()
            messages.success(request, 'Attachment uploaded successfully!')
            return redirect('ticket_detail', pk=pk)
    
    # Handle ticket assignment and status update (staff only, not superusers)
    if request.method == 'POST' and 'update_ticket' in request.POST and request.user.is_staff and not request.user.is_superuser:
        old_status = ticket.status
        assign_form = AssignTicketForm(request.POST, instance=ticket, department=ticket.department)
        if assign_form.is_valid():
            updated_ticket = assign_form.save(commit=False)
            
            # Check if resolution notes are provided when resolving a ticket
            if updated_ticket.status == 'resolved' and not updated_ticket.resolution_notes:
                messages.error(request, 'Please provide resolution notes when resolving a ticket.')
                return redirect('ticket_detail', pk=pk)
                
            updated_ticket.save()
            
            # Send email notification if ticket is newly resolved
            if updated_ticket.status == 'resolved' and old_status != 'resolved':
                logger.info(f"About to send resolved notification for ticket #{ticket.id}")
                try:
                    send_ticket_resolved_email(request, updated_ticket)
                    logger.info(f"Resolved notification sent for ticket #{ticket.id}")
                except Exception as e:
                    logger.error(f"Error sending resolved notification for ticket #{ticket.id}: {str(e)}")
                    messages.warning(request, 'Ticket resolved but there was an error sending the email notification.')
                
            messages.success(request, 'Ticket updated successfully!')
            return redirect('ticket_detail', pk=pk)
    
    context = {
        'ticket': ticket,
        'comments': comments,
        'attachments': attachments,
        'comment_form': comment_form,
        'attachment_form': attachment_form,
        'assign_form': assign_form,
    }
    return render(request, 'tickets/ticket_detail.html', context)

@login_required
def update_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    
    # Check if the user has permission to update - only ticket creator or superuser
    if request.user != ticket.created_by and not request.user.is_superuser:
        messages.error(request, "You don't have permission to update this ticket.")
        return redirect('ticket_detail', pk=pk)
    
    if request.method == 'POST':
        form = TicketForm(request.POST, instance=ticket, user=request.user)
        attachment_form = AttachmentForm(request.POST, request.FILES)
        
        if form.is_valid():
            form.save()
            
            # Handle file attachment only if a file was uploaded
            if 'file' in request.FILES:
                if attachment_form.is_valid():
                    attachment = attachment_form.save(commit=False)
                    attachment.ticket = ticket
                    attachment.uploaded_by = request.user
                    attachment.save()
                    messages.success(request, 'Ticket updated with new attachment successfully!')
                else:
                    messages.warning(request, 'Ticket updated but there was an error with the attachment.')
            else:
                messages.success(request, 'Ticket updated successfully!')
            
            return redirect('ticket_detail', pk=pk)
    else:
        form = TicketForm(instance=ticket, user=request.user)
        attachment_form = AttachmentForm()
    
    # Get attachments for the ticket
    attachments = ticket.attachments.all().order_by('-uploaded_at')
    
    context = {
        'form': form,
        'ticket': ticket,
        'attachments': attachments,
        'attachment_form': attachment_form,
    }
    return render(request, 'tickets/update_ticket.html', context)

def superuser_required(function):
    """Decorator to check if the user is a superuser"""
    actual_decorator = user_passes_test(lambda u: u.is_superuser)
    return actual_decorator(function)

@login_required
@superuser_required
def staff_list(request):
    """List all staff members"""
    staff = User.objects.filter(is_staff=True).order_by('username')
    
    context = {
        'staff': staff,
    }
    return render(request, 'tickets/staff/staff_list.html', context)

@login_required
@superuser_required
def staff_create(request):
    """Create a new staff member"""
    if request.method == 'POST':
        form = StaffCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Staff member created successfully!")
            return redirect('staff_list')
    else:
        form = StaffCreationForm()
    
    context = {
        'form': form,
        'title': 'Create Staff Member'
    }
    return render(request, 'tickets/staff/staff_form.html', context)

@login_required
@superuser_required
def staff_edit(request, pk):
    """Edit an existing staff member"""
    try:
        # Get the staff user
        staff = User.objects.get(pk=pk, is_staff=True)
        
        # Don't allow editing superusers unless you're editing yourself
        if staff.is_superuser and staff != request.user:
            messages.error(request, "You cannot edit other superusers.")
            return redirect('staff_list')
        
        if request.method == 'POST':
            # Process the form data
            form = StaffEditForm(request.POST, instance=staff)
            if form.is_valid():
                # Save the form without committing to the database yet
                user = form.save(commit=False)
                # Save the user to the database
                user.save()
                # Save the many-to-many data for the form
                form.save_m2m()
                messages.success(request, "Staff member updated successfully!")
                return redirect('staff_list')
        else:
            # Create a form instance with the staff user data
            form = StaffEditForm(instance=staff)
        
        # Render the form
        context = {
            'form': form,
            'staff': staff,
            'title': 'Edit Staff Member'
        }
        return render(request, 'tickets/staff/staff_form.html', context)
    except User.DoesNotExist:
        messages.error(request, "Staff member not found.")
        return redirect('staff_list')
    except Exception as e:
        messages.error(request, f"Error editing staff: {str(e)}")
        return redirect('staff_list')

@login_required
@superuser_required
def staff_edit_alt(request, pk):
    """Alternative method to edit an existing staff member"""
    try:
        # Get the staff user
        staff = User.objects.get(pk=pk, is_staff=True)
        
        # Don't allow editing superusers unless you're editing yourself
        if staff.is_superuser and staff != request.user:
            messages.error(request, "You cannot edit other superusers.")
            return redirect('staff_list')
        
        if request.method == 'POST':
            # Process the form data manually
            username = request.POST.get('username')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            is_active = request.POST.get('is_active') == 'on'
            department_ids = request.POST.getlist('departments')
            
            # Update the user
            staff.username = username
            staff.first_name = first_name
            staff.last_name = last_name
            staff.email = email
            staff.is_active = is_active
            staff.save()
            
            # Update departments
            departments = Department.objects.filter(id__in=department_ids)
            staff.departments.set(departments)
            
            messages.success(request, "Staff member updated successfully!")
            return redirect('staff_list')
        else:
            # Create a form instance with the staff user data
            form = StaffEditForm(instance=staff)
        
        # Render the form
        context = {
            'form': form,
            'staff': staff,
            'title': 'Edit Staff Member',
            'departments': Department.objects.all(),
            'staff_departments': staff.departments.all().values_list('id', flat=True)
        }
        return render(request, 'tickets/staff/staff_form_alt.html', context)
    except User.DoesNotExist:
        messages.error(request, "Staff member not found.")
        return redirect('staff_list')
    except Exception as e:
        messages.error(request, f"Error editing staff: {str(e)}")
        return redirect('staff_list')

@login_required
@superuser_required
def staff_delete(request, pk):
    """Delete a staff member"""
    staff = get_object_or_404(User, pk=pk, is_staff=True)
    
    # Don't allow deleting superusers
    if staff.is_superuser:
        messages.error(request, "You cannot delete a superuser.")
        return redirect('staff_list')
    
    # Don't allow deleting yourself
    if staff == request.user:
        messages.error(request, "You cannot delete yourself.")
        return redirect('staff_list')
    
    if request.method == 'POST':
        # Get tickets assigned to this staff and reassign them
        assigned_tickets = Ticket.objects.filter(assigned_to=staff)
        for ticket in assigned_tickets:
            ticket.assigned_to = None
            ticket.save()
            
        staff.delete()
        messages.success(request, "Staff member deleted successfully!")
        return redirect('staff_list')
    
    context = {
        'staff': staff,
    }
    return render(request, 'tickets/staff/staff_confirm_delete.html', context)

@login_required
@superuser_required
def staff_create_alt(request):
    """Alternative method to create a new staff member"""
    try:
        if request.method == 'POST':
            # Process the form data manually
            username = request.POST.get('username')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            department_ids = request.POST.getlist('departments')
            
            # Validate the form data
            errors = {}
            
            if not username:
                errors['username'] = ['Username is required.']
            elif User.objects.filter(username=username).exists():
                errors['username'] = ['A user with that username already exists.']
                
            if not password1:
                errors['password1'] = ['Password is required.']
                
            if not password2:
                errors['password2'] = ['Password confirmation is required.']
                
            if password1 and password2 and password1 != password2:
                errors['password2'] = ['The two password fields didn\'t match.']
                
            if not department_ids:
                errors['departments'] = ['At least one department must be selected.']
            
            if errors:
                # If there are errors, render the form again with error messages
                context = {
                    'title': 'Create Staff Member',
                    'errors': errors,
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'departments': Department.objects.all(),
                    'selected_departments': department_ids,
                }
                return render(request, 'tickets/staff/staff_form_create_alt.html', context)
            
            # Create the user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name
            )
            user.is_staff = True
            user.save()
            
            # Add to selected departments
            if department_ids:
                departments = Department.objects.filter(id__in=department_ids)
                user.departments.set(departments)
            
            messages.success(request, "Staff member created successfully!")
            return redirect('staff_list')
        else:
            # Render the form
            context = {
                'title': 'Create Staff Member',
                'departments': Department.objects.all(),
            }
            return render(request, 'tickets/staff/staff_form_create_alt.html', context)
    except Exception as e:
        messages.error(request, f"Error creating staff: {str(e)}")
        return redirect('staff_list')

@login_required
@superuser_required
def delete_ticket(request, pk):
    """Delete a ticket (superuser only)"""
    ticket = get_object_or_404(Ticket, pk=pk)
    
    if request.method == 'POST':
        # Store the department ID for redirection
        department_id = ticket.department_id if ticket.department else None
        
        # Delete the ticket
        ticket.delete()
        messages.success(request, f"Ticket #{pk} has been deleted successfully.")
        
        # Redirect to dashboard with the department filter if available
        if department_id:
            return redirect(f'/?department={department_id}')
        else:
            return redirect('dashboard')
    
    context = {
        'ticket': ticket,
    }
    return render(request, 'tickets/delete_ticket.html', context)

@login_required
@superuser_required
def department_list(request):
    """List all departments"""
    departments = Department.objects.all().order_by('name')
    
    context = {
        'departments': departments,
    }
    return render(request, 'tickets/departments/department_list.html', context)

@login_required
@superuser_required
def department_create(request):
    """Create a new department"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        staff_ids = request.POST.getlist('staff')
        
        # Validate form data
        errors = {}
        
        if not name:
            errors['name'] = ['Department name is required.']
        elif Department.objects.filter(name=name).exists():
            errors['name'] = ['A department with this name already exists.']
        
        if errors:
            # If there are errors, render the form again with error messages
            context = {
                'title': 'Create Department',
                'errors': errors,
                'name': name,
                'description': description,
                'staff': User.objects.filter(is_staff=True),
                'selected_staff': staff_ids,
            }
            return render(request, 'tickets/departments/department_form.html', context)
        
        # Create the department
        department = Department.objects.create(
            name=name,
            description=description
        )
        
        # Add staff members
        if staff_ids:
            staff = User.objects.filter(id__in=staff_ids, is_staff=True)
            department.staff.set(staff)
        
        messages.success(request, "Department created successfully!")
        return redirect('department_list')
    
    # GET request - show the form
    context = {
        'title': 'Create Department',
        'staff': User.objects.filter(is_staff=True),
    }
    return render(request, 'tickets/departments/department_form.html', context)

@login_required
@superuser_required
def department_edit(request, pk):
    """Edit an existing department"""
    department = get_object_or_404(Department, pk=pk)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        staff_ids = request.POST.getlist('staff')
        
        # Validate form data
        errors = {}
        
        if not name:
            errors['name'] = ['Department name is required.']
        elif Department.objects.filter(name=name).exclude(pk=pk).exists():
            errors['name'] = ['A department with this name already exists.']
        
        if errors:
            # If there are errors, render the form again with error messages
            context = {
                'title': 'Edit Department',
                'department': department,
                'errors': errors,
                'name': name,
                'description': description,
                'staff': User.objects.filter(is_staff=True),
                'selected_staff': staff_ids,
            }
            return render(request, 'tickets/departments/department_form.html', context)
        
        # Update the department
        department.name = name
        department.description = description
        department.save()
        
        # Update staff members
        if staff_ids:
            staff = User.objects.filter(id__in=staff_ids, is_staff=True)
            department.staff.set(staff)
        else:
            department.staff.clear()
        
        messages.success(request, "Department updated successfully!")
        return redirect('department_list')
    
    # GET request - show the form with current data
    context = {
        'title': 'Edit Department',
        'department': department,
        'name': department.name,
        'description': department.description,
        'staff': User.objects.filter(is_staff=True),
        'selected_staff': [str(staff.id) for staff in department.staff.all()],
    }
    return render(request, 'tickets/departments/department_form.html', context)

@login_required
@superuser_required
def department_delete(request, pk):
    """Delete a department"""
    department = get_object_or_404(Department, pk=pk)
    
    # Check if there are tickets associated with this department
    if Ticket.objects.filter(department=department).exists():
        messages.error(request, "Cannot delete department with associated tickets. Reassign tickets first.")
        return redirect('department_list')
    
    if request.method == 'POST':
        department.delete()
        messages.success(request, "Department deleted successfully!")
        return redirect('department_list')
    
    context = {
        'department': department,
    }
    return render(request, 'tickets/departments/department_confirm_delete.html', context)

@login_required
@superuser_required
def ticket_report(request):
    """Generate a report with ticket statistics for superusers"""
    # Get filter parameters
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    department_id = request.GET.get('department', '')
    format_type = request.GET.get('format', '')
    
    # Default to last 30 days if no dates provided
    today = datetime.now().date()
    if not start_date_str:
        start_date = today - timedelta(days=30)
    else:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today - timedelta(days=30)
            messages.warning(request, "Invalid start date format. Using last 30 days.")
    
    if not end_date_str:
        end_date = today
    else:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = today
            messages.warning(request, "Invalid end date format. Using today as end date.")
    
    # Base queryset for tickets in the date range
    tickets = Ticket.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )
    
    # Filter by department if provided
    if department_id:
        tickets = tickets.filter(department_id=department_id)
    
    # Calculate statistics
    total_tickets = tickets.count()
    new_tickets = tickets.filter(status='new').count()
    in_progress_tickets = tickets.filter(status='in_progress').count()
    pending_tickets = tickets.filter(status='pending').count()
    resolved_tickets = tickets.filter(status='resolved').count()
    closed_tickets = tickets.filter(status='closed').count()
    
    # Calculate percentage of resolved/closed tickets
    resolution_rate = 0
    if total_tickets > 0:
        resolution_rate = ((resolved_tickets + closed_tickets) / total_tickets) * 100
    
    # Calculate average resolution time for resolved and closed tickets
    resolved_closed_tickets = tickets.filter(
        Q(status='resolved') | Q(status='closed'),
        updated_at__isnull=False
    )
    
    # Use ExpressionWrapper to calculate duration
    resolution_time = ExpressionWrapper(
        F('updated_at') - F('created_at'),
        output_field=DurationField()
    )
    
    avg_resolution_time = resolved_closed_tickets.annotate(
        resolution_time=resolution_time
    ).aggregate(avg_time=Avg('resolution_time'))
    
    # Calculate tickets by priority
    low_priority = tickets.filter(priority='low').count()
    medium_priority = tickets.filter(priority='medium').count()
    high_priority = tickets.filter(priority='high').count()
    urgent_priority = tickets.filter(priority='urgent').count()
    
    # Calculate tickets by department
    department_stats = tickets.values('department__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Calculate tickets created per day for trend analysis
    tickets_per_day = tickets.annotate(
        day=TruncDay('created_at')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    # Calculate tickets with no staff assigned
    unassigned_tickets = tickets.filter(assigned_to__isnull=True).count()
    
    # Calculate average tickets per day
    days_in_range = (end_date - start_date).days + 1
    avg_tickets_per_day = total_tickets / days_in_range if days_in_range > 0 else 0
    
    # Get all departments for filter dropdown
    departments = Department.objects.all()
    
    # Prepare data for CSV export
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="ticket_report_{today}.csv"'
        
        writer = csv.writer(response)
        
        # Helper function to create table borders
        def add_table_border(width=50):
            writer.writerow(['+' + '-' * width + '+'])
            
        def add_table_header(title, width=50):
            writer.writerow(['+' + '-' * width + '+'])
            padding = (width - len(title)) // 2
            writer.writerow(['|' + ' ' * padding + title + ' ' * (width - len(title) - padding) + '|'])
            writer.writerow(['+' + '-' * width + '+'])
        
        # Header with title and date range
        add_table_header('HELPDESK TICKET REPORT', 70)
        writer.writerow(['| Report generated on: ' + today.strftime("%Y-%m-%d %H:%M:%S") + ' ' * 30 + '|'])
        writer.writerow(['| Date range: ' + f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}" + ' ' * 36 + '|'])
        if department_id:
            department = Department.objects.get(id=department_id)
            dept_info = f"Department: {department.name}"
            writer.writerow(['| ' + dept_info + ' ' * (68 - len(dept_info)) + '|'])
        else:
            writer.writerow(['| Department: All Departments' + ' ' * 42 + '|'])
        writer.writerow(['+' + '-' * 70 + '+'])
        writer.writerow([])
        
        # Summary statistics table with visual formatting
        add_table_header('SUMMARY STATISTICS', 60)
        writer.writerow(['| Metric' + ' ' * 25 + '| Value' + ' ' * 23 + '|'])
        writer.writerow(['|' + '-' * 31 + '|' + '-' * 28 + '|'])
        
        def add_stat_row(metric, value):
            metric_str = f"| {metric}"
            value_str = f"| {value}"
            writer.writerow([metric_str + ' ' * (31 - len(metric_str)) + value_str + ' ' * (28 - len(value_str)) + '|'])
        
        add_stat_row('Total Tickets', total_tickets)
        add_stat_row('New Tickets', new_tickets)
        add_stat_row('In Progress Tickets', in_progress_tickets)
        add_stat_row('Pending Tickets', pending_tickets)
        add_stat_row('Resolved Tickets', resolved_tickets)
        add_stat_row('Closed Tickets', closed_tickets)
        add_stat_row('Unassigned Tickets', unassigned_tickets)
        add_stat_row('Resolution Rate', f'{resolution_rate:.2f}%')
        add_stat_row('Average Tickets Per Day', f'{avg_tickets_per_day:.2f}')
        
        # Average resolution time
        avg_time = avg_resolution_time.get('avg_time')
        if avg_time:
            days = avg_time.days
            seconds = avg_time.seconds
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            add_stat_row('Average Resolution Time', f'{days} days, {hours} hours, {minutes} minutes')
        else:
            add_stat_row('Average Resolution Time', 'N/A')
            
        writer.writerow(['|' + '-' * 31 + '|' + '-' * 28 + '|'])
        writer.writerow(['+' + '-' * 60 + '+'])
        writer.writerow([])
        
        # Tickets by priority table with visual formatting
        add_table_header('TICKETS BY PRIORITY', 60)
        writer.writerow(['| Priority' + ' ' * 12 + '| Count' + ' ' * 5 + '| Percentage' + ' ' * 9 + '|'])
        writer.writerow(['|' + '-' * 20 + '|' + '-' * 10 + '|' + '-' * 19 + '|'])
        
        def add_priority_row(priority, count, percentage):
            priority_str = f"| {priority}"
            count_str = f"| {count}"
            percentage_str = f"| {percentage}"
            writer.writerow([
                priority_str + ' ' * (20 - len(priority_str)) + 
                count_str + ' ' * (10 - len(count_str)) + 
                percentage_str + ' ' * (19 - len(percentage_str)) + '|'
            ])
        
        add_priority_row('Low', low_priority, f'{(low_priority/total_tickets*100):.1f}%' if total_tickets > 0 else '0.0%')
        add_priority_row('Medium', medium_priority, f'{(medium_priority/total_tickets*100):.1f}%' if total_tickets > 0 else '0.0%')
        add_priority_row('High', high_priority, f'{(high_priority/total_tickets*100):.1f}%' if total_tickets > 0 else '0.0%')
        add_priority_row('Urgent', urgent_priority, f'{(urgent_priority/total_tickets*100):.1f}%' if total_tickets > 0 else '0.0%')
        
        writer.writerow(['|' + '-' * 20 + '|' + '-' * 10 + '|' + '-' * 19 + '|'])
        writer.writerow(['+' + '-' * 60 + '+'])
        writer.writerow([])
        
        # Tickets by department table with visual formatting
        add_table_header('TICKETS BY DEPARTMENT', 70)
        writer.writerow(['| Department' + ' ' * 20 + '| Count' + ' ' * 5 + '| Percentage' + ' ' * 9 + '|'])
        writer.writerow(['|' + '-' * 30 + '|' + '-' * 10 + '|' + '-' * 19 + '|'])
        
        for dept in department_stats:
            dept_name = dept['department__name'] or 'No Department'
            if len(dept_name) > 27:
                dept_name = dept_name[:24] + '...'
            dept_count = dept['count']
            dept_percentage = f'{(dept_count/total_tickets*100):.1f}%' if total_tickets > 0 else '0.0%'
            
            dept_str = f"| {dept_name}"
            count_str = f"| {dept_count}"
            percentage_str = f"| {dept_percentage}"
            
            writer.writerow([
                dept_str + ' ' * (30 - len(dept_str)) + 
                count_str + ' ' * (10 - len(count_str)) + 
                percentage_str + ' ' * (19 - len(percentage_str)) + '|'
            ])
        
        writer.writerow(['|' + '-' * 30 + '|' + '-' * 10 + '|' + '-' * 19 + '|'])
        writer.writerow(['+' + '-' * 70 + '+'])
        writer.writerow([])
        
        # Daily ticket trend table with visual formatting
        add_table_header('DAILY TICKET TREND', 50)
        writer.writerow(['| Date' + ' ' * 11 + '| Number of Tickets' + ' ' * 10 + '|'])
        writer.writerow(['|' + '-' * 15 + '|' + '-' * 24 + '|'])
        
        for day_data in tickets_per_day:
            date_str = f"| {day_data['day'].strftime('%Y-%m-%d')}"
            count_str = f"| {day_data['count']}"
            writer.writerow([
                date_str + ' ' * (15 - len(date_str)) + 
                count_str + ' ' * (24 - len(count_str)) + '|'
            ])
        
        writer.writerow(['|' + '-' * 15 + '|' + '-' * 24 + '|'])
        writer.writerow(['+' + '-' * 50 + '+'])
        writer.writerow([])
        
        # Detailed ticket list with visual formatting - using a wider table
        add_table_header('DETAILED TICKET LIST', 120)
        
        # Define column widths
        col_widths = {
            'id': 5,
            'title': 25,
            'status': 12,
            'priority': 10,
            'department': 15,
            'created_by': 12,
            'created_at': 16,
            'updated_at': 16,
            'resolution': 15
        }
        
        # Create header row
        header_row = '| ID' + ' ' * (col_widths['id'] - 2)
        header_row += '| Title' + ' ' * (col_widths['title'] - 5)
        header_row += '| Status' + ' ' * (col_widths['status'] - 6)
        header_row += '| Priority' + ' ' * (col_widths['priority'] - 8)
        header_row += '| Department' + ' ' * (col_widths['department'] - 10)
        header_row += '| Created By' + ' ' * (col_widths['created_by'] - 10)
        header_row += '| Created At' + ' ' * (col_widths['created_at'] - 10)
        header_row += '| Updated At' + ' ' * (col_widths['updated_at'] - 10)
        header_row += '| Resolution' + ' ' * (col_widths['resolution'] - 10) + '|'
        
        writer.writerow([header_row])
        
        # Create separator row
        separator = '|' + '-' * col_widths['id']
        separator += '|' + '-' * col_widths['title']
        separator += '|' + '-' * col_widths['status']
        separator += '|' + '-' * col_widths['priority']
        separator += '|' + '-' * col_widths['department']
        separator += '|' + '-' * col_widths['created_by']
        separator += '|' + '-' * col_widths['created_at']
        separator += '|' + '-' * col_widths['updated_at']
        separator += '|' + '-' * col_widths['resolution'] + '|'
        
        writer.writerow([separator])
        
        # Add ticket data rows
        for ticket in tickets:
            resolution_time = 'N/A'
            if ticket.status in ['resolved', 'closed'] and ticket.updated_at:
                delta = ticket.updated_at - ticket.created_at
                days = delta.days
                seconds = delta.seconds
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                resolution_time = f'{days}d {hours}h {minutes}m'
            
            # Format title with truncation if needed
            title = ticket.title
            if len(title) > col_widths['title'] - 3:
                title = title[:col_widths['title'] - 6] + '...'
                
            # Format department with truncation if needed
            department = ticket.department.name if ticket.department else 'No Department'
            if len(department) > col_widths['department'] - 3:
                department = department[:col_widths['department'] - 6] + '...'
                
            # Format username with truncation if needed
            username = ticket.created_by.username
            if len(username) > col_widths['created_by'] - 3:
                username = username[:col_widths['created_by'] - 6] + '...'
            
            # Build the data row
            data_row = f"| {ticket.id}" + ' ' * (col_widths['id'] - len(str(ticket.id)) - 1)
            data_row += f"| {title}" + ' ' * (col_widths['title'] - len(title) - 1)
            data_row += f"| {ticket.get_status_display()}" + ' ' * (col_widths['status'] - len(ticket.get_status_display()) - 1)
            data_row += f"| {ticket.get_priority_display()}" + ' ' * (col_widths['priority'] - len(ticket.get_priority_display()) - 1)
            data_row += f"| {department}" + ' ' * (col_widths['department'] - len(department) - 1)
            data_row += f"| {username}" + ' ' * (col_widths['created_by'] - len(username) - 1)
            
            created_at = ticket.created_at.strftime('%Y-%m-%d %H:%M')
            data_row += f"| {created_at}" + ' ' * (col_widths['created_at'] - len(created_at) - 1)
            
            updated_at = ticket.updated_at.strftime('%Y-%m-%d %H:%M') if ticket.updated_at else 'N/A'
            data_row += f"| {updated_at}" + ' ' * (col_widths['updated_at'] - len(updated_at) - 1)
            
            data_row += f"| {resolution_time}" + ' ' * (col_widths['resolution'] - len(resolution_time) - 1) + '|'
            
            writer.writerow([data_row])
        
        writer.writerow([separator])
        writer.writerow(['+' + '-' * 120 + '+'])
        writer.writerow([])
        writer.writerow(['+' + '-' * 70 + '+'])
        writer.writerow(['|' + ' ' * 25 + 'END OF REPORT' + ' ' * 25 + '|'])
        writer.writerow(['+' + '-' * 70 + '+'])
        
        return response
    
    # Prepare context for HTML template
    context = {
        'tickets': tickets,
        'total_tickets': total_tickets,
        'new_tickets': new_tickets,
        'in_progress_tickets': in_progress_tickets,
        'pending_tickets': pending_tickets,
        'resolved_tickets': resolved_tickets,
        'closed_tickets': closed_tickets,
        'avg_resolution_time': avg_resolution_time.get('avg_time'),
        'low_priority': low_priority,
        'medium_priority': medium_priority,
        'high_priority': high_priority,
        'urgent_priority': urgent_priority,
        'department_stats': department_stats,
        'tickets_per_day': tickets_per_day,
        'start_date': start_date,
        'end_date': end_date,
        'departments': departments,
        'selected_department': department_id,
        'unassigned_tickets': unassigned_tickets,
        'resolution_rate': resolution_rate,
        'avg_tickets_per_day': avg_tickets_per_day,
    }
    
    return render(request, 'tickets/reports/ticket_report.html', context)

# 5. Configure URLs in helpdesk_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('tickets.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)