from django import forms
from django.contrib.auth.models import User
from .models import Ticket, Comment, Attachment, Department

class TicketForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            # If user is superuser, show all departments
            if user.is_superuser:
                self.fields['department'].queryset = Department.objects.all()
            # If user is staff (but not superuser), show their departments
            elif user.is_staff:
                self.fields['department'].queryset = user.departments.all()
            # If user is not staff, show all departments
            else:
                self.fields['department'].queryset = Department.objects.all()
        self.fields['department'].empty_label = None  # Force department selection

    class Meta:
        model = Ticket
        fields = ['title', 'description', 'department', 'priority']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter ticket title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Describe your issue'
            }),
            'department': forms.Select(attrs={
                'class': 'form-select'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'
            })
        }

class AssignTicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['assigned_to', 'status']
        widgets = {
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'})
        }

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show staff members from the same department
        if department:
            self.fields['assigned_to'].queryset = department.staff.all()
        else:
            self.fields['assigned_to'].queryset = User.objects.filter(is_staff=True)
        self.fields['assigned_to'].empty_label = "-- Assign to Staff Member --"

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Write your comment here'
            }),
        }

class AttachmentForm(forms.ModelForm):
    file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.doc,.docx,.txt,.png,.jpg,.jpeg',
        })
    )

    class Meta:
        model = Attachment
        fields = ['file']