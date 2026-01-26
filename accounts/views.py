from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .forms import RegisterForm, UserUpdateForm, ProfileUpdateForm, style_form
from .models import UserProfile

def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.first_name = form.cleaned_data.get("first_name", "")
            user.last_name = form.cleaned_data.get("last_name", "")
            user.save()

            # ensure profile exists + set initial values
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.phone = form.cleaned_data.get("phone", "")
            profile.organization = form.cleaned_data.get("organization", "")
            profile.job_title = form.cleaned_data.get("job_title", "")
            profile.save()

            messages.success(request, "Account created. Please log in.")
            return redirect("accounts:login")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = RegisterForm()

    # form = style_form(form)
    return render(request, "accounts/register.html", {"form": form})


@login_required
def logout_view(request):
    if request.method == "POST":
        logout(request)
        messages.info(request, "You have been logged out.")
        return redirect("documents:home")
    return redirect("documents:list")


@login_required
def profile_view(request):
    _ = getattr(request.user, "profile", None)
    return render(request, "accounts/profile.html", {})


@login_required
def profile_edit(request):
    profile = getattr(request.user, "profile", None)
    if profile is None:
        profile = UserProfile.objects.create(user=request.user)

    if request.method == "POST":
        uform = UserUpdateForm(request.POST, instance=request.user)
        pform = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if uform.is_valid() and pform.is_valid():
            uform.save()
            pform.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
        messages.error(request, "Please fix the errors below.")
    else:
        uform = UserUpdateForm(instance=request.user)
        pform = ProfileUpdateForm(instance=profile)

    return render(request, "accounts/profile_edit.html", {
        "uform": uform,
        "pform": pform,
    })



@login_required
@require_POST
def deactivate_account(request):
    # soft delete (แนะนำ)
    request.user.is_active = False
    request.user.save(update_fields=["is_active"])
    logout(request)
    messages.warning(request, "Your account has been deactivated.")
    return redirect("accounts:login")


@login_required
@require_POST
def delete_account(request):
    # hard delete (ลบ Document ทั้งหมดด้วยเพราะ FK CASCADE)
    uid = request.user.id
    logout(request)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    User.objects.filter(id=uid).delete()
    messages.error(request, "Your account has been deleted.")
    return redirect("accounts:login")
