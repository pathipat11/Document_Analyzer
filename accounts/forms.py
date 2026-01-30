from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm, AuthenticationForm, PasswordResetForm, SetPasswordForm
from .models import UserProfile

User = get_user_model()

# -------------------------
# Tailwind classes (shared)
# -------------------------
BASE_INPUT_CLASS = (
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 "
    "text-sm text-slate-900 placeholder:text-slate-400 shadow-sm "
    "focus:outline-none focus:ring-2 focus:ring-blue-500/40 "
    "dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 "
)

TEXTAREA_CLASS = BASE_INPUT_CLASS + " resize-none"
SELECT_CLASS = BASE_INPUT_CLASS
DATE_CLASS = BASE_INPUT_CLASS

CHECKBOX_CLASS = (
    "h-4 w-4 rounded border-slate-300 text-blue-600 "
    "focus:ring-2 focus:ring-blue-500/40 dark:border-slate-700"
)
FILE_CLASS = (
    "block w-full text-sm text-slate-700 dark:text-slate-200 "
    "file:mr-3 file:rounded-lg file:border-0 "
    "file:bg-slate-200 file:px-3 file:py-2 file:text-sm file:font-medium "
    "hover:file:bg-slate-300 "
    "dark:file:bg-slate-800 dark:hover:file:bg-slate-700"
)

def _append_class(widget, extra: str):
    cur = widget.attrs.get("class", "")
    if extra not in cur:
        widget.attrs["class"] = (cur + " " + extra).strip()

def style_form(form):
    """
    Apply consistent Tailwind classes to all fields in a Django form.
    - TextInput/EmailInput/PasswordInput/NumberInput/etc -> BASE_INPUT_CLASS
    - Textarea -> TEXTAREA_CLASS + rows=4 default
    - Select -> SELECT_CLASS
    - DateInput -> DATE_CLASS (and preserve type="date" if already set)
    - CheckboxInput -> CHECKBOX_CLASS
    - ClearableFileInput/FileInput -> FILE_CLASS
    """
    for name, field in form.fields.items():
        w = field.widget
        cls_name = w.__class__.__name__

        # checkbox
        if isinstance(w, forms.CheckboxInput):
            w.attrs["class"] = CHECKBOX_CLASS
            continue

        # file
        if isinstance(w, (forms.ClearableFileInput, forms.FileInput)):
            w.attrs["class"] = FILE_CLASS
            continue

        # textarea
        if isinstance(w, forms.Textarea):
            w.attrs["class"] = TEXTAREA_CLASS
            w.attrs.setdefault("rows", 4)
            continue

        # select
        if isinstance(w, (forms.Select, forms.SelectMultiple)):
            w.attrs["class"] = SELECT_CLASS
            continue

        # date input
        if isinstance(w, forms.DateInput):
            w.attrs["class"] = DATE_CLASS
            # ให้แน่ใจว่าเป็น date picker
            w.attrs.setdefault("type", "date")
            continue

        # default input
        w.attrs["class"] = BASE_INPUT_CLASS
        if isinstance(w, forms.PasswordInput) or "password" in name:
            _append_class(w, "pr-10")

    return form


# -------------------------
# Register
# -------------------------
class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=False, max_length=150)
    last_name = forms.CharField(required=False, max_length=150)

    phone = forms.CharField(required=False, max_length=30)
    organization = forms.CharField(required=False, max_length=120)
    job_title = forms.CharField(required=False, max_length=120)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "email", "first_name", "last_name", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # placeholders (optional but nice)
        self.fields["username"].widget.attrs.setdefault("placeholder", "Username")
        self.fields["email"].widget.attrs.setdefault("placeholder", "Email")
        self.fields["first_name"].widget.attrs.setdefault("placeholder", "First name")
        self.fields["last_name"].widget.attrs.setdefault("placeholder", "Last name")

        self.fields["phone"].widget.attrs.setdefault("placeholder", "Phone")
        self.fields["organization"].widget.attrs.setdefault("placeholder", "Organization")
        self.fields["job_title"].widget.attrs.setdefault("placeholder", "Job title")

        self.fields["password1"].widget.attrs.setdefault("placeholder", "Password")
        self.fields["password2"].widget.attrs.setdefault("placeholder", "Confirm password")

        style_form(self)

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email


# -------------------------
# Profile edit forms
# -------------------------
class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["email", "first_name", "last_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "phone", "organization", "job_title", "bio", "avatar",
            "address_line1", "address_line2", "city", "state", "postal_code", "country",
            "date_of_birth",
            "notify_email", "notify_product", "notify_security",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # placeholders (optional)
        self.fields["phone"].widget.attrs.setdefault("placeholder", "Phone")
        self.fields["organization"].widget.attrs.setdefault("placeholder", "Organization")
        self.fields["job_title"].widget.attrs.setdefault("placeholder", "Job title")
        self.fields["bio"].widget.attrs.setdefault("placeholder", "Short bio...")
        self.fields["address_line1"].widget.attrs.setdefault("placeholder", "Address line 1")
        self.fields["address_line2"].widget.attrs.setdefault("placeholder", "Address line 2")
        self.fields["city"].widget.attrs.setdefault("placeholder", "City")
        self.fields["state"].widget.attrs.setdefault("placeholder", "State")
        self.fields["postal_code"].widget.attrs.setdefault("placeholder", "Postal code")
        self.fields["country"].widget.attrs.setdefault("placeholder", "Country")

        style_form(self)


# -------------------------
# Password change
# -------------------------
class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # apply consistent style
        style_form(self)

        # placeholders
        self.fields["old_password"].widget.attrs.setdefault("placeholder", "Current password")
        self.fields["new_password1"].widget.attrs.setdefault("placeholder", "New password")
        self.fields["new_password2"].widget.attrs.setdefault("placeholder", "Confirm new password")

class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)
        self.fields["username"].widget.attrs.setdefault("placeholder", "Username")
        self.fields["password"].widget.attrs.setdefault("placeholder", "Password")

class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)
        self.fields["email"].widget.attrs.setdefault("placeholder", "Email")
        

class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)
        self.fields["new_password1"].widget.attrs.setdefault("placeholder", "New password")
        self.fields["new_password2"].widget.attrs.setdefault("placeholder", "Confirm new password")