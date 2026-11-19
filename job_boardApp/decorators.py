from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def permission_required(permission_code):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            profile = getattr(request.user, 'userprofile', None)
            if profile and permission_code in profile.permissions:
                return view_func(request, *args, **kwargs)
            messages.error(request, "You don't have permission to access this page.")
            return redirect("home-page")
        return _wrapped_view
    return decorator



from django.shortcuts import redirect
from django.contrib import messages
from .models import Subscription

def subscription_required(view_func):
    """Restrict access to users with active subscriptions"""
    def wrapper(request, *args, **kwargs):
        subscription = Subscription.objects.filter(user=request.user).last()
        if not subscription or not subscription.has_access():
            messages.error(request, "❌ Your subscription has expired. Please renew to continue using this page.")
            return redirect("my-subscription")
        return view_func(request, *args, **kwargs)
    return wrapper