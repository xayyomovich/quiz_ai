from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from quizapp.models import User
# from aiquiz_project.quizapp.models import User


class UserRegistrationForm(UserCreationForm):
    """User registration form"""
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'First Name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Last Name'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Email'
        })
    )
    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'select select-bordered w-full'
        })
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Confirm Password'
        })
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'role', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.role = self.cleaned_data['role']
        if commit:
            user.save()
        return user


class UserLoginForm(AuthenticationForm):
    """User login form"""
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Email',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Password'
        })
    )


class TestCreationForm(forms.Form):
    """Form for test creation with natural language"""
    prompt = forms.CharField(
        label='What kind of test do you want to create?',
        widget=forms.Textarea(attrs={
            'class': 'textarea textarea-bordered w-full',
            'placeholder': 'Example: "Create 15 intermediate biology questions about photosynthesis"',
            'rows': 3
        }),
        required=False
    )

    # Alternative: Structured form
    topic = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'e.g., Biology, Math, History'
        })
    )
    question_count = forms.IntegerField(
        min_value=1,
        max_value=200,
        initial=10,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': '10'
        })
    )
    difficulty = forms.ChoiceField(
        choices=[
            ('easy', 'Easy'),
            ('intermediate', 'Intermediate'),
            ('hard', 'Hard')
        ],
        initial='intermediate',
        required=False,
        widget=forms.Select(attrs={
            'class': 'select select-bordered w-full'
        })
    )
    language = forms.ChoiceField(
        choices=[
            ('english', 'English'),
            ('uzbek', 'Uzbek'),
            ('russian', 'Russian')
        ],
        initial='english',
        required=False,
        widget=forms.Select(attrs={
            'class': 'select select-bordered w-full'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        prompt = cleaned_data.get('prompt')
        topic = cleaned_data.get('topic')

        # Either prompt OR structured fields must be filled
        if not prompt and not topic:
            raise forms.ValidationError(
                "Please provide either a description or fill in the form fields."
            )

        return cleaned_data


class ManualTestCreationForm(forms.Form):
    """Form for manual test creation by pasting questions and answers"""

    questions_text = forms.CharField(
        label='Paste Questions with Options',
        widget=forms.Textarea(attrs={
            'class': 'textarea textarea-bordered w-full font-mono text-sm',
            'placeholder': '''100 Multiple Choice Questions: Medical & Pharmaceutical Translation
1. What is the correct translation of "analgesic"?
A) Og'riq qoldiruvchi
B) Yallig'lanishga qarshi
C) Allergen
D) Yuqumli
2. "Hypertension" refers to:
A) Qandli diabet
B) Yuqori qon bosimi
C) Past qon bosimi
D) Yurak urishi pasayishi
...''',
            'rows': 15,
            'spellcheck': 'false'
        }),
        required=True,
        help_text='Paste your questions with options. Format: Question number, question text, then options A), B), C), D)'
    )

    answers_text = forms.CharField(
        label='Paste Answer Keys',
        widget=forms.Textarea(attrs={
            'class': 'textarea textarea-bordered w-full font-mono text-sm',
            'placeholder': '''Answer Key: 100 MCQs Medical & Pharmaceutical Translation
1. A) Og'riq qoldiruvchi
2. B) Yuqori qon bosimi
...''',
            'rows': 10,
            'spellcheck': 'false'
        }),
        required=True,
        help_text='Paste answer keys. Format: Question number followed by correct option letter (A, B, C, or D)'
    )

    topic = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'e.g., Medical Translation, Mathematics (optional)'
        }),
        help_text='Optional: Override the topic extracted from title'
    )

    difficulty = forms.ChoiceField(
        choices=[
            ('easy', 'Easy'),
            ('intermediate', 'Intermediate'),
            ('hard', 'Hard')
        ],
        initial='intermediate',
        required=False,
        widget=forms.Select(attrs={
            'class': 'select select-bordered w-full'
        })
    )