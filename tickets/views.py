from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
import os

from .models import Ticket, Comment, Attachment, Department
from .forms import TicketForm, CommentForm, AttachmentForm, AssignTicketForm

@login_required
def delete_attachment(request, ticket_id, attachment_id):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('ticket_detail', pk=ticket_id)

    ticket = get_object_or_404(Ticket, pk=ticket_id)
    attachment = get_object_or_404(Attachment, pk=attachment_id, ticket=ticket)
    
    # Check if user has permission to delete the attachment
    if request.user == ticket.created_by or request.user == attachment.uploaded_by or request.user.is_staff:
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
    
    # Get user's departments
    user_departments = request.user.departments.all()
    
    # Start with tickets from user's departments
    tickets = Ticket.objects.filter(department__in=user_departments).order_by('-created_at')
    
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
    
    # Get chart data
    status_data = tickets.values('status').annotate(count=Count('status')).order_by('status')
    priority_data = tickets.values('priority').annotate(count=Count('priority')).order_by('priority')
    
    # Get department distribution
    department_data = tickets.values('department__name').annotate(count=Count('department')).order_by('-count')
    
    # Paginate results
    paginator = Paginator(tickets, 10)  # 10 tickets per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status,
        'priority_filter': priority,
        'search_query': search,
        'departments': user_departments,
        'selected_department': department_id,
        'status_data': list(status_data),
        'priority_data': list(priority_data),
        'department_data': list(department_data),
    }
    return render(request, 'tickets/dashboard.html', context)

@login_required
def my_tickets(request):
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
    if request.user.is_staff:
        departments = request.user.departments.all()
    else:
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
    if not (request.user.is_staff and request.user.departments.filter(id=ticket.department.id).exists()) and request.user != ticket.created_by:
        messages.error(request, "You don't have permission to view this ticket.")
        return redirect('my_tickets')
    
    comments = ticket.comments.all().order_by('created_at')
    attachments = ticket.attachments.all()
    
    # Forms
    comment_form = CommentForm()
    attachment_form = AttachmentForm()
    assign_form = None
    
    # Only create assign form for staff members in the same department
    if request.user.is_staff and request.user.departments.filter(id=ticket.department.id).exists():
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
    
    # Check if the user has permission to update
    if request.user != ticket.created_by and not request.user.is_staff:
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