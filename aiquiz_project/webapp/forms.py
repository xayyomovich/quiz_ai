# webapp/forms.py - UPDATED

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from quizapp.models import User


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

    # NEW: Timer field
    timer_minutes = forms.IntegerField(
        min_value=1,
        max_value=300,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Leave empty for no time limit'
        }),
        help_text='Time limit in minutes (optional)',
        label='Time Limit (minutes)'
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

    # NEW: Timer field
    timer_minutes = forms.IntegerField(
        min_value=1,
        max_value=300,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Leave empty for no time limit'
        }),
        help_text='Time limit in minutes (optional)',
        label='Time Limit (minutes)'
    )


# ============================================
# GROUP TEST FORMS (ADD AT THE END)
# ============================================

class GroupTestCreationForm(forms.Form):
    """Form for creating a group test"""

    group_number = forms.ChoiceField(
        choices=[(i, f'Group-{i}') for i in range(1, 11)],
        widget=forms.Select(attrs={
            'class': 'select select-bordered w-full'
        }),
        help_text='Select which group slot (1-10)'
    )

    test = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        widget=forms.Select(attrs={
            'class': 'select select-bordered w-full'
        }),
        help_text='Select an existing test'
    )

    timer_minutes = forms.IntegerField(
        min_value=1,
        max_value=180,
        initial=20,
        widget=forms.NumberInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': '20'
        }),
        help_text='Time limit in minutes'
    )

    max_group_size = forms.IntegerField(
        min_value=2,
        max_value=20,
        initial=6,
        widget=forms.NumberInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': '6'
        }),
        help_text='Maximum students allowed in this group'
    )

    def __init__(self, teacher=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if teacher:
            # Only show teacher's tests
            self.fields['test'].queryset = Test.objects.filter(teacher=teacher)


class CreateGroupTestDirectForm(forms.Form):
    """Create a group test with open-ended discussion questions"""

    group_number = forms.ChoiceField(
        choices=[(i, f'Group-{i}') for i in range(1, 11)],
        widget=forms.Select(attrs={
            'class': 'select select-bordered w-full'
        }),
        label='Group Number',
        help_text='Select which group slot (1-10)'
    )

    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'e.g., Critical Thinking Challenge'
        }),
        label='Test Title',
        help_text='Give your group test a name'
    )

    questions_and_answers = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'textarea textarea-bordered w-full font-mono text-sm',
            'placeholder': '''Format:
Q1: A girl finds a note in her room. It says: "I have a head and a tail, but no body. I am not alive. People flip me for luck. What am I?" Solve the riddle and explain why.
A1: The riddle is about a coin. A coin has a head and a tail but no body. It's not alive. People flip coins for luck.

Q2: If you have 3 apples and you take away 2, how many do you have? Explain your reasoning.
A2: You have 2 apples because you took them away. The question asks how many YOU have, not how many are left.

Q3: ...
A3: ...''',
            'rows': 20,
            'spellcheck': 'false'
        }),
        label='Questions and Answers',
        help_text='Use format: Q1: question text, A1: answer text, Q2: ..., A2: ...'
    )

    timer_minutes = forms.IntegerField(
        min_value=5,
        max_value=180,
        initial=20,
        widget=forms.NumberInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': '20'
        }),
        label='Time Limit (minutes)',
        help_text='How long students have to complete the test'
    )

    max_group_size = forms.IntegerField(
        min_value=2,
        max_value=20,
        initial=6,
        widget=forms.NumberInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': '6'
        }),
        label='Maximum Students',
        help_text='Maximum students allowed in this group'
    )