from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('chatbot/', views.chatbot_response, name='chatbot_response'),
    path('api/fetch-elements/', views.fetch_elements, name='fetch_elements'),
]
