from django.conf.urls import url
from api import views


urlpatterns = [

    url(r'^login/', views.LoginView.as_view()),
    url(r'^message/', views.MessageView.as_view()),
    url(r'^credential/', views.CredentialView.as_view()),
]