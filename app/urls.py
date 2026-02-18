from django.urls import path
from .views import (DepartmentView, DepartmentCRUDView, CreateRiskView, RiskCRUDView, 
                    CreateRiskActivityView, RiskActivityCRUDView, )


urlpatterns = [
     path('api/create/department/', DepartmentView.as_view()),
     path("api/crud/department/<int:pk>/", DepartmentCRUDView.as_view()),
     path('api/create/risk/', CreateRiskView.as_view()),
     path('api/crud/risk/<int:pk>/', RiskCRUDView.as_view()),
     path('api/create/riskactivity/', CreateRiskActivityView.as_view()),
     path('api/crud/riskactivity/<int:pk>/', RiskActivityCRUDView.as_view()),
]
