from django.urls import path
from .views import (DepartmentView, DepartmentCRUDView, CategoryView, CategoryCRUDView, CreateRiskView, RiskCRUDView, 
                    CreateRiskActivityView, RiskActivityCRUDView, CreateRiskCommitteeView,
                    RiskCommitteeCRUDView, CreateRiskDecitionView, RiskDecitionCRUDView,
                    CreateMitigationView, MitigationCRUDView, GetRiskMitigationView,
                    FilterRiskByStatusView, UpcomingRiskAPIView,ReplyRiskActivityCRUDView,
                    ReplyRiskActivityCreateView, UpdateRiskView, AssignRiskView, AddRecipientToRiskView,
                    RiskCloseView, MeView, GetTokenView, UserRiskCrudView, StaffRiskMitigationCRYDView,
                    DepartmentMemberDirectoryView)


urlpatterns = [
     path('api/create/department/', DepartmentView.as_view()),
     path("api/crud/department/<int:pk>/", DepartmentCRUDView.as_view()),
     path('api/create/category/', CategoryView.as_view()),
     path("api/crud/category/<int:pk>/", CategoryCRUDView.as_view()),
     path('api/create/risk/', CreateRiskView.as_view()),
     path('api/crud/risk/<int:pk>/', RiskCRUDView.as_view()),
     path('api/risk/crud/user/<int:pk>/', UserRiskCrudView.as_view()),
     path('api/create/riskactivity/', CreateRiskActivityView.as_view()),
     path('api/crud/riskactivity/<int:pk>/', RiskActivityCRUDView.as_view()),
     path('api/create/riskcommite/', CreateRiskCommitteeView.as_view()),
     path('api/crud/riskcommite/<int:pk>/', RiskCommitteeCRUDView.as_view()),
     path("api/create/decisition/", CreateRiskDecitionView.as_view()),
     path('api/crud/decisition/<int:pk>/', RiskDecitionCRUDView.as_view()),
     path('api/create/mitigation/', CreateMitigationView.as_view()),
     path('api/crud/mitigation/<int:pk>/', MitigationCRUDView.as_view()),
     path('api/crud/mitigation/staff/<int:pk>/', StaffRiskMitigationCRYDView.as_view()),
     path('api/get/mitigation/byrisk/<int:pk>/', GetRiskMitigationView.as_view()),
     path('api/get/risk/bystatus/', FilterRiskByStatusView.as_view()),
     path('api/upcoming/risks/', UpcomingRiskAPIView.as_view()),
     path('api/create/replyriskactivity/', ReplyRiskActivityCreateView.as_view()),
     path("api/crud/replyriskactivity/<int:pk>/", ReplyRiskActivityCRUDView.as_view()),
     path("api/risk/<int:pk>/update/", UpdateRiskView.as_view()),
     path("api/risk/<int:pk>/assign/", AssignRiskView.as_view()), # for add user(kim bo'lsa ham) to rick general chat
     path("api/risk/<int:pk>/add-recipient/", AddRecipientToRiskView.as_view()),  # yangi
     path('api/risk/close/<int:pk>/', RiskCloseView.as_view()), #id risk.id userni requestdan olaman
     path("token/", GetTokenView.as_view()),
     path("me/", MeView.as_view()),
     path("api/directory/department-members/", DepartmentMemberDirectoryView.as_view()),
]
