from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import BatchLog

class BatchLogForm(forms.ModelForm):
    class Meta:
        model = BatchLog
        fields = '__all__'  

