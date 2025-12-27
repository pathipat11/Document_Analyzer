from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.shortcuts import render, redirect

def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created. Please log in.")
            return redirect("accounts:login")
    else:
        form = UserCreationForm()

    return render(request, "accounts/register.html", {"form": form})

@login_required
def logout_view(request):
    if request.method == "POST":
        logout(request)
        messages.info(request, "You have been logged out.")
        return redirect("accounts:login")

    return redirect("documents:list")

def _style_form(form):
    for name, field in form.fields.items():
        field.widget.attrs["class"] = (
            "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 "
            "dark:border-slate-700 dark:bg-slate-900"
        )
    return form
