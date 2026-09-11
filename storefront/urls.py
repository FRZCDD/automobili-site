from django.urls import path

from . import views

app_name = "storefront"

urlpatterns = [
    path("", views.LandingView.as_view(), name="landing"),
    path("cars/<slug:car_slug>/", views.CarDetailView.as_view(), name="car_detail"),
    path("leads/submit/", views.LeadSubmitView.as_view(), name="lead_submit"),
]
