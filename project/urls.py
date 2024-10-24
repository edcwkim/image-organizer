from django.urls import path

from apps.core.views import Main

urlpatterns = [
    path('', Main.as_view(), name='Main'),
]
