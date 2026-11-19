from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

FORCE_KEY = "force_password_change"


class ForcePasswordChangeMiddleware:
   

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.session.get(FORCE_KEY):
            allowed = {
                reverse("job_boardApp:change_password"),
                reverse("job_boardApp:logout"),
            }
            path = request.path
            if path not in allowed and not path.startswith(settings.STATIC_URL):
                if path.startswith("/api/"):  
                    return JsonResponse({"error": "password_change_required"}, status=403)
                return redirect("job_boardApp:change_password")
        return self.get_response(request)