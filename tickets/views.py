from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
import os

from .models import Ticket, Comment, Attachment, Department
from .forms import TicketForm, CommentForm, AttachmentForm, AssignTicketForm, StaffCreationForm, StaffEditForm
from django.contrib.auth.models import User

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
    if request.user.is_superuser or (request.user.is_staff and request.user.departments.filter(id=ticket.department.id).exists()):
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
    
    # Handle ticket assignment and status update (staff only)
    if request.method == 'POST' and 'update_ticket' in request.POST and request.user.is_staff:
        assign_form = AssignTicketForm(request.POST, instance=ticket, department=ticket.department)
        if assign_form.is_valid():
            assign_form.save()
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