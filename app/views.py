from datetime import timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .services.risk_activity import create_risk_activity_and_notify, add_user_to_risk_activity
from .services.notification import notify_risk_update, notify_mitigation_update, notify_mitigation_create
from rest_framework.permissions import IsAuthenticated, AllowAny
from .permissions import IsTopManager
from drf_yasg.utils import swagger_auto_schema
from .serializers import (RiskActivitySerializer, RiskCommitteeSerializer, RiskDecisionSerializer,
                          RiskSerializer, MitigationSerializer, DepartmentSerializer, StatusSerializer,
                          CategorySerializer, ReplyRiskActivitySerializer)
from .models import (Department, Category,  Risk, RiskActivity, RiskCommittee, RiskDecition,
                     Mitigation, ReplyRiskActivity)


class DepartmentView(APIView):
    # permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=DepartmentSerializer, tags = ['Department'])
    def post(self, request, *args, **kwargs):
        serializer = DepartmentSerializer(data = request.data)
        if serializer.is_valid():
            instance = serializer.save()
            return Response({
                "data":serializer.data,
                "status":status.HTTP_201_CREATED
            })
        else:
            return Response({
                "error":serializer.errors
            })
            
    @swagger_auto_schema(tags = ['Department'])
    def get(self, request, *args,**kwargs):
        departments = Department.objects.all()
        serializer = DepartmentSerializer(departments, many = True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        

class DepartmentCRUDView(APIView):
    # permission_classes = [IsAuthenticated] # keyinchalik faqat risk role dagila qo'sha oladigan permission beramiz
    
    @swagger_auto_schema(tags = ['Department'])
    def get(self, request, pk, *args, **kwargs):
        department = Department.objects.filter(id = pk).first()
        if department:
            seralizer = DepartmentSerializer(department)
            return Response({
                "data":seralizer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(tags = ['Department'])
    def delete(self, request, pk, *args, **kwargs):
        department = Department.objects.get(id = pk)
        if department:
            department.delete()
            return Response({
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(request_body=DepartmentSerializer, tags = ['Department'])
    def patch(self, request, pk, *args, **kwargs):
        department = Department.objects.filter(id =pk).first()
        if department:
            serializer = DepartmentSerializer(instance = department, data = request.data, partial = True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "data":serializer.data,
                    "status":status.HTTP_200_OK
                })
            else:
                return Response({
                    "errors":serializer.errors
                })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
            
class CategoryView(APIView):
    permission_classes = [IsAuthenticated, IsTopManager]
    
    @swagger_auto_schema(request_body=CategorySerializer, tags = ['Category'])
    def post(self, request, *args, **kwargs):
        serializer = CategorySerializer(data = request.data)
        if serializer.is_valid():
            instance = serializer.save()
            return Response({
                "data":serializer.data,
                "status":status.HTTP_201_CREATED
            })
        else:
            return Response({
                "error":serializer.errors
            })
            
    @swagger_auto_schema(tags = ['Category'])
    def get(self, request, *args,**kwargs):
        departments = Category.objects.all()
        serializer = CategorySerializer(departments, many = True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        

class CategoryCRUDView(APIView):
    permission_classes = [IsAuthenticated, IsTopManager] # keyinchalik faqat risk role dagila qo'sha oladigan permission beramiz
    
    @swagger_auto_schema(tags = ['Category'])
    def get(self, request, pk, *args, **kwargs):
        department = Category.objects.filter(id = pk).first()
        if department:
            seralizer = CategorySerializer(department)
            return Response({
                "data":seralizer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(tags = ['Category'])
    def delete(self, request, pk, *args, **kwargs):
        department = Category.objects.get(id = pk)
        if department:
            department.delete()
            return Response({
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(request_body=CategorySerializer, tags = ['Category'])
    def patch(self, request, pk, *args, **kwargs):
        department = Category.objects.filter(id =pk).first()
        if department:
            serializer = CategorySerializer(instance = department, data = request.data, partial = True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "data":serializer.data,
                    "status":status.HTTP_200_OK
                })
            else:
                return Response({
                    "errors":serializer.errors
                })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
            
class CreateRiskView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(request_body=RiskSerializer, tags=['Risk'])
    def post(self, request, *args, **kwargs):
        serializer = RiskSerializer(data=request.data)

        if serializer.is_valid():
            risk = serializer.save()

            create_risk_activity_and_notify(
                risk=risk,
                actor=risk.owner,     
                action_type="CREATE",
                notes="Risk created"
            )

            return Response({
                "data": serializer.data,
                "status": status.HTTP_200_OK
            })

        return Response({
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
            
    @swagger_auto_schema(tags = ['Risk'])
    def get(self, request, *args, **kwargs):
        risk = Risk.objects.all()
        serializer = RiskSerializer(risk, many = True)
        return Response({
            "data":serializer.data
        })
        
        
class RiskCRUDView(APIView):
    permission_classes = [IsAuthenticated, IsTopManager] 
    
    @swagger_auto_schema(tags = ['Risk'])
    def get(self, request, pk, *args, **kwargs):
        risk = Risk.objects.filter(id = pk).first()
        if risk:
            serializer = RiskSerializer(risk)
            return Response({
                "data":serializer.data
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(tags = ["Risk"])
    def delete(self, request, pk, *args, **kwargs):
        risk = Risk.objects.get(id = pk)
        if risk:
            risk.delete()
            return Response({
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(request_body=RiskSerializer, tags = ['Risk'])
    def patch(self, request, pk, *args, **kwargs):
        risk = Risk.objects.filter(id =pk).first()
        if risk:
            old_risk = Risk.objects.get(id=pk)
            serializer = RiskSerializer(instance = risk, data = request.data, partial = True)
            if serializer.is_valid():
                updated_risk = serializer.save()
                notify_risk_update(old_risk, updated_risk)
                return Response({
                    "data":serializer.data,
                    "status":status.HTTP_200_OK
                })
            else:
                return Response({
                    "errors":serializer.errors
                })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
            
class UserRiskCrudView(APIView):
    # permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=RiskSerializer, tags = ['Risk'])
    def patch(self, request, pk, *args, **kwargs):
        risk = Risk.objects.filter(id =pk).first()
        if risk:
            old_risk = Risk.objects.get(id=pk)
            if old_risk.status == "DRAFT":
                serializer = RiskSerializer(instance = risk, data = request.data, partial = True)
                if serializer.is_valid():
                    updated_risk = serializer.save()
                    notify_risk_update(old_risk, updated_risk)
                    return Response({
                        "data":serializer.data,
                        "status":status.HTTP_200_OK
                    })
                else:
                    return Response({
                        "errors":serializer.errors
                    })
            else:
                return Response({
                    "detail":"This one given for check",
                    "status":status.HTTP_400_BAD_REQUEST
                })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
            
class RiskCloseView(APIView):
    permission_classes = [IsAuthenticated, IsTopManager] #add permission only for risk.derector
    
    @swagger_auto_schema(tag = ['Risk'])
    def get(self, request, pk, *args, **kwargs):
        user = request.user
        risk = Risk.objects.filter(id = pk).first()
        if risk and user == risk.risk_derector:
            risk.status = 'CLOSED'
            risk.is_active = False
            risk.save()
            serializer = RiskSerializer(data = risk)
            return Response({
                "data":serializer.data,
                'status':status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })


class CreateRiskActivityView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(request_body=RiskActivitySerializer, tags = ['RiskActivity'])
    def post(self, request, *args, **kwargs):
        serializer = RiskActivitySerializer(data = request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "data":serializer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "errors":serializer.errors
            })
            
    @swagger_auto_schema(tags = ['RiskActivity'])
    def get(self, request, *args, **kwargs):
        riskactivity = RiskActivity.objects.all()
        serializer = RiskActivitySerializer(riskactivity, many = True)
        return Response({
            "data":serializer.data
        })
        
        
class RiskActivityCRUDView(APIView):
    # permission_classes = [IsAuthenticated] 
    
    @swagger_auto_schema(tags = ['RiskActivity'])
    def get(self, request, pk, *args, **kwargs):
        riskactivity = RiskActivity.objects.filter(id = pk).first()
        if riskactivity:
            serializer = RiskActivitySerializer(riskactivity)
            return Response({
                "data":serializer.data
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    # @swagger_auto_schema(tags = ["RiskActivity"])
    # def delete(self, request, pk, *args, **kwargs):
    #     riskactivity = RiskActivity.objects.get(id = pk)
    #     if riskactivity:
    #         riskactivity.delete()
    #         return Response({
    #             "status":status.HTTP_200_OK
    #         })
    #     else:
    #         return Response({
    #             "status":status.HTTP_404_NOT_FOUND
    #         })
            
    # @swagger_auto_schema(request_body=RiskActivitySerializer, tags = ['RiskActivity'])
    # def patch(self, request, pk, *args, **kwargs):
    #     riskactivity = RiskActivity.objects.filter(id =pk).first()
    #     if riskactivity:
    #         serializer = RiskActivitySerializer(instance = riskactivity, data = request.data, partial = True)
    #         if serializer.is_valid():
    #             serializer.save()
    #             return Response({
    #                 "data":serializer.data,
    #                 "status":status.HTTP_200_OK
    #             })
    #         else:
    #             return Response({
    #                 "errors":serializer.errors
    #             })
    #     else:
    #         return Response({
    #             "status":status.HTTP_404_NOT_FOUND
    #         })
            
            
class CreateRiskCommitteeView(APIView):
    # parser_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(request_body=RiskCommitteeSerializer, tags = ['RiskCommittee'])
    def post(self, request, *args, **kwargs):
        serializer = RiskCommitteeSerializer(data = request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "data":serializer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "errors":serializer.errors
            })
            
    @swagger_auto_schema(tags = ['RiskCommittee'])
    def get(self, request, *args, **kwargs):
        data = RiskCommittee.objects.all()
        serializer = RiskCommitteeSerializer(data, many = True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        
        
class RiskCommitteeCRUDView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(tags = ["RiskCommittee"])
    def get(self, request, pk, *args, **kwargs):
        data = RiskCommittee.objects.filter(id = pk).first()
        if data:
            seralizer = RiskCommitteeSerializer(data)
            return Response({
                "data":seralizer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
    # @swagger_auto_schema(tags = ["RiskCommittee"])
    # def delete(self, request, pk, *args, **kwargs):
    #     data = RiskCommittee.objects.get(id = pk)
    #     if data:
    #         data.delete()
    #         return Response({
    #             "satatus":status.HTTP_200_OK
    #         })
    #     else:
    #         return Response({
    #             "data":"Bunday ma'lumot topilmadi",
    #             "status":status.HTTP_404_NOT_FOUND
    #         })
            
    # @swagger_auto_schema(request_body=RiskCommitteeSerializer, tags = ['RiskCommittee'])
    # def patch(self, request, pk, *args, **kwargs):
    #     data1 = RiskCommittee.objects.filter(id = pk).first()
    #     if data1:
    #         serializer = RiskCommitteeSerializer(instance = data1, data = request.data, partial = True)
    #         if serializer.is_valid():
    #             serializer.save()
    #             return Response({
    #                 "data":serializer.data,
    #                 "status":status.HTTP_200_OK
    #             })
    #         else:
    #             return Response({
    #                 "errors":serializer.errors
    #             })
    #     else:
    #         return Response({
    #             "data":"Bunday ma'lumot topilmadi",
    #             "status":status.HTTP_404_NOT_FOUND
    #         })
            
            
class CreateRiskDecitionView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(request_body=RiskDecisionSerializer, tags = ['RiskDecition'])
    def post(self, request, *args, **kwargs):
        serializer = RiskDecisionSerializer(data = request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "data":serializer.data,
                "status":status.HTTP_201_CREATED
            })
        else:
            return Response({
                "errors":serializer.errors
            })
            
    @swagger_auto_schema(tags = ['RiskDecition'])
    def get(self, request, *args, **kwargs):
        decisition = RiskDecition.objects.all()
        serializer = RiskDecisionSerializer(decisition, many = True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        
        
class RiskDecitionCRUDView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(tags = ['RiskDecition'])
    def get(self, request, pk, *args, **kwargs):
        decisition = RiskDecition.objects.filter(id = pk).first()
        if decisition:
            serializer = RiskDecisionSerializer(decisition)
            return Response({
                "data":serializer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
    # @swagger_auto_schema(tags = ['RiskDecition'])
    # def delete(self, request, pk, *args, **kwargs):
    #     decisition = RiskDecition.objects.filter(id = pk).first()
    #     if decisition:
    #         decisition.delete()
    #         return Response({
    #             "status":status.HTTP_200_OK
    #         })
    #     else:
    #         return Response({
    #             "data":"Bunday ma'lumot topilmadi",
    #             "status":status.HTTP_404_NOT_FOUND
    #         })
            
    # @swagger_auto_schema(request_body=RiskDecisionSerializer, tags = ['RiskDecition'])
    # def patch(self, request, pk, *args, **kwargs):
    #     decisition = RiskDecition.objects.filter(id = pk).first()
    #     if decisition:
    #         serializer = RiskDecisionSerializer(instance = decisition, data = request.data, partial = True)
    #         if serializer.is_valid():
    #             serializer.save()
    #             return Response({
    #                 "data":serializer.data,
    #                 'status':status.HTTP_201_CREATED
    #             })
    #         else:
    #             return Response({
    #                 "errors":serializer.errors
    #             })
    #     else:
    #         return Response({
    #             "data":"Bunday ma'lumot topilmadi",
    #             "status":status.HTTP_404_NOT_FOUND
    #         })
            
            
class CreateMitigationView(APIView):
    permission_classes = [IsAuthenticated, IsTopManager]
    
    @swagger_auto_schema(request_body=MitigationSerializer, tags = ['Mitigation'])
    def post(self, request, *args, **kwargs):
        serialzier = MitigationSerializer(data = request.data)
        if serialzier.is_valid():
            mitigation = serialzier.save()
            notify_mitigation_create(mitigation)
            return Response({
                "data":serialzier.data,
                "status":status.HTTP_201_CREATED
            })
        else:
            return Response({
                "errors":serialzier.errors
            })
            
    @swagger_auto_schema(tags = ['Mitigation'])
    def get(self, request, *args, **kwargs):
        mitigation = Mitigation.objects.all()
        seralizer = MitigationSerializer(mitigation, many =True)
        return Response({
            "data":seralizer.data,
            "status":status.HTTP_200_OK
        })
        

class MitigationCRUDView(APIView):
    permission_classes = [IsAuthenticated, IsTopManager]
    
    @swagger_auto_schema(tags = ['Mitigation'])
    def get(self, request, pk, *args, **kwargs):
        mitigation = Mitigation.objects.filter(id = pk).first()
        if mitigation:
            serializer = MitigationSerializer(mitigation)
            return Response({
                "data":serializer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(tags = ['Mitigation'])
    def delete(self, request, pk, *args, **kwargs):
        mitigation = Mitigation.objects.filter(id = pk).first()
        if mitigation:
            mitigation.delete()
            return Response({
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
    
    @swagger_auto_schema(request_body=MitigationSerializer, tags = ['Mitigation'])
    def patch(self, request, pk, *args, **kwargs):
        mitigation = Mitigation.objects.get(id = pk)
        if mitigation:
            old_mitigation = Mitigation.objects.get(id=pk)
            serializer = MitigationSerializer(instance = mitigation, data = request.data, partial = True)
            if serializer.is_valid():
                updated_mitigation = serializer.save()
                notify_mitigation_update(old_mitigation, updated_mitigation)
                return Response({
                    "data":serializer.data,
                    "status":status.HTTP_201_CREATED
                })
            else:
                return Response({
                    "errors":serializer.errors
                })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
            
class StaffRiskMitigationCRYDView(APIView):
    
    @swagger_auto_schema(request_body=MitigationSerializer, tags = ['Mitigation'])
    def patch(self, request, pk, *args, **kwargs):
        mitigation = Mitigation.objects.get(id = pk)
        if mitigation:
            old_mitigation = Mitigation.objects.get(id=pk)
            serializer = MitigationSerializer(instance = mitigation, data = request.data, partial = True)
            if serializer.is_valid():
                updated_mitigation = serializer.save()
                notify_mitigation_update(old_mitigation, updated_mitigation)
                return Response({
                    "data":serializer.data,
                    "status":status.HTTP_201_CREATED
                })
            else:
                return Response({
                    "errors":serializer.errors
                })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
            
class GetRiskMitigationView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(tags = ['Filters'])
    def get(self, request, pk, *args, **kwargs):
        mitigations = Mitigation.objects.filter(risk_id = pk)
        serializer = MitigationSerializer(mitigations, many =True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        

class FilterRiskByStatusView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(request_body=StatusSerializer, tags = ['Filters'])
    def post(self, request, *args, **kwargs):
        risk = Risk.objects.filter(status = request.data.get("status"))
        if risk:
            serializer = RiskSerializer(risk, many = True)
            return Response({
                "data":serializer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
            
class UpcomingRiskAPIView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        today = timezone.now()
        ten_days_later = today + timedelta(days=10)
        risks = Risk.objects.filter(
            status__in=["OPEN", "IN_PROGRESS", "MITIGATED", "ACCEPTED"],
            due_date__gte=today,
            due_date__lte=ten_days_later
        ).order_by("due_date") 
        serializer = RiskSerializer(risks, many=True)
        return Response(
            {
                "count": risks.count(),
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )
        
        
class ReplyRiskActivityCreateView(APIView):
    # permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=ReplyRiskActivitySerializer, tag = ['ReplyRiskActivity'])
    def post(self, request, *args, **kwargs):
        serializer = ReplyRiskActivitySerializer(data = request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "data":serializer.data,
                "status":status.HTTP_201_CREATED
            })
        else:
            return Response({
                "errors":serializer.errors,
                "status":status.HTTP_400_BAD_REQUEST
            })
        
    @swagger_auto_schema(tag = ['ReplyRiskActivity'])        
    def get(self, request, *args, **kwargs):
        data = ReplyRiskActivity.objects.all()
        serializer = ReplyRiskActivitySerializer(data, many=True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        
        
class ReplyRiskActivityCRUDView(APIView):
    # permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(tag = ['ReplyRiskActivity'])
    def get(self, request, pk, *args, **kwargs):
        data1 = ReplyRiskActivity.objects.filter(id = pk).first()
        if data1:
            serializer = ReplyRiskActivitySerializer(data = data1)
            return Response({
                "data":serializer.data,
                'status':status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_400_BAD_REQUEST
            })
            
    # @swagger_auto_schema(tag = ['ReplyRiskActivity'])
    # def delete(self, request, pk, *args, **kwargs):
    #     data = ReplyRiskActivity.objects.filter(id = pk).first()
    #     if data:
    #         data.delete()
    #         return Response({
    #             "data":"Ma'lumot muvaffaqiyatli o'chirildi",
    #             'status':status.HTTP_200_OK
    #         })
    #     else:
    #         return Response({
    #             "data":"Bunday ma'lumot topilmadi",
    #             "status":status.HTTP_400_BAD_REQUEST
    #         })
            
    @swagger_auto_schema(request_body=ReplyRiskActivitySerializer, tag = ['ReplyRiskActivity'])
    def patch(self, request, pk, *args, **kwargs):
        data1 = ReplyRiskActivity.objects.filter(id = pk).first()
        if data1:
            serializer = ReplyRiskActivitySerializer(instance = data1, data = request.data, partial = True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "data":serializer.data,
                    'status':status.HTTP_200_OK
                })
            else:
                return Response({
                    "errors":serializer.errors,
                    'status':status.HTTP_400_BAD_REQUEST
                })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_400_BAD_REQUEST
            })
            

class AddRecipientToRiskView(APIView):
    
    @swagger_auto_schema(tags=["RiskActivity"])
    def post(self, request, pk):
        risk = get_object_or_404(Risk, pk=pk)
        new_user = request.data.get("user")

        if not new_user:
            return Response(
                {"error": "user field is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        recipient = add_user_to_risk_activity(
            risk=risk,
            new_user=new_user,
            actor=request.user  
        )

        if not recipient:
            return Response(
                {"error": "RiskActivity not found for this risk"},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {"message": f"{new_user} added to risk activity"},
            status=status.HTTP_200_OK
        )
        
        
class UpdateRiskView(APIView):
    
    @swagger_auto_schema(request_body=RiskSerializer, tags=["Risk"])
    def put(self, request, pk):
        risk = get_object_or_404(Risk, pk=pk)
        serializer = RiskSerializer(risk, data=request.data, partial=True)

        if serializer.is_valid():
            updated_risk = serializer.save()

            create_risk_activity_and_notify(
                risk=updated_risk,
                actor=request.user,
                action_type="UPDATE",
                notes="Risk updated"
            )

            extra_users = request.data.get("extra_recipients", [])
            for user in extra_users:
                add_user_to_risk_activity(
                    risk=updated_risk,
                    new_user=user,
                    actor=request.user
                )

            return Response(
                {"data": serializer.data},
                status=status.HTTP_200_OK
            )

        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
        
        
class AssignRiskView(APIView):
    
    @swagger_auto_schema(tags=["Risk"])
    def post(self, request, pk):
        risk = get_object_or_404(Risk, pk=pk)
        assigned_user = request.data.get("user")

        if not assigned_user:
            return Response(
                {"error": "user field is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        add_user_to_risk_activity(
            risk=risk,
            new_user=assigned_user,
            actor=request.user
        )

        create_risk_activity_and_notify(
            risk=risk,
            actor=request.user,
            action_type="ASSIGNMENT",
            notes=f"{assigned_user} assigned to risk"
        )

        return Response(
            {"message": f"{assigned_user} assigned and notified"},
            status=status.HTTP_200_OK
        )


from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import authenticate
import requests
from django.conf import settings
from .auth import KeycloakAuthentication

class GetTokenView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        data = {
            "grant_type": "password",
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
            "username": request.data.get("username"),
            "password": request.data.get("password"),
        }

        response = requests.post(settings.KEYCLOAK_TOKEN_URL, data=data)

        return Response(response.json())


# 🔥 2. TOKEN BILAN USER INFO
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        auth = request.auth or {}  # None bo'lsa bo'sh dict
        return Response({
            "username": request.user.username,
            "email": auth.get("email") or getattr(request.user, "email", None),
            "full_name": auth.get("name") or getattr(request.user, "get_full_name", lambda: None)(),
        })