from django.urls import path

from . import views

app_name = "badges"

urlpatterns = [
    # Public badge image (ADR 0018), e.g. /badges/3/bild/5e9c22f3….png
    path("badges/<int:pk>/bild/<slug:name>.png", views.badge_image, name="image"),
]
