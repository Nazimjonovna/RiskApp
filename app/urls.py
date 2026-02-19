from django.urls import path
from .views import (DepartmentView, DepartmentCRUDView, CreateRiskView, RiskCRUDView, 
                    CreateRiskActivityView, RiskActivityCRUDView, CreateRiskCommitteeView,
                    RiskCommitteeCRUDView, CreateRiskDecisionView, RiskDecisionCRUDView,
                    CreateMitigationView, MitigationCRUDView, GetRiskMitigationView,
                    FilterRiskByStatusView, UpcomingRiskAPIView, )


urlpatterns = [
     path('api/create/department/', DepartmentView.as_view()),
     path("api/crud/department/<int:pk>/", DepartmentCRUDView.as_view()),
     path('api/create/risk/', CreateRiskView.as_view()),
     path('api/crud/risk/<int:pk>/', RiskCRUDView.as_view()),
     path('api/create/riskactivity/', CreateRiskActivityView.as_view()),
     path('api/crud/riskactivity/<int:pk>/', RiskActivityCRUDView.as_view()),
     path('api/create/riskcommite/', CreateRiskCommitteeView.as_view()),
     path('api/crud/riskcommite/<int:pk>/', RiskCommitteeCRUDView.as_view()),
     path("api/create/decisition/", CreateRiskDecisionView.as_view()),
     path('api/crud/decisition/<int:pk>/', RiskDecisionCRUDView.as_view()),
     path('api/create/mitigation/', CreateMitigationView.as_view()),
     path('api/crud/mitigation/<int:pk>/', MitigationCRUDView.as_view()),
     path('api/get/mitigation/byrisk/<int:pk>/', GetRiskMitigationView.as_view()),
     path('api/get/risk/bystatus/', FilterRiskByStatusView.as_view()),
     path('api/upcoming/risks/', UpcomingRiskAPIView.as_view())
]
