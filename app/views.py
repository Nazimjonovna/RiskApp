from datetime import timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_yasg.utils import swagger_auto_schema
from .serializers import (RiskActivitySerializer, RiskCommitteeSerializer, RiskDecisionSerializer,
                          RiskSerializer, MitigationSerializer, DepartmentSerializer, StatusSerializer,
                          CategorySerializer)
from .models import (Department, Category,  Risk, RiskActivity, RiskCommittee, RiskDecision,
                     Mitigation)


class DepartmentView(APIView):
    # permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=DepartmentSerializer, tags = ['Department'])
    def post(self, request, *args, **kwargs):
        serializer = DepartmentSerializer(data = request.data)
        if serializer.is_valid():
            instance = serializer.save()
            return Response({
                "data":serializer.data,
                "id":instance.id,
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
            serializer = DepartmentSerializer(intance = department, data = request.data, partial = True)
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
    # permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=CategorySerializer, tags = ['Category'])
    def post(self, request, *args, **kwargs):
        serializer = CategorySerializer(data = request.data)
        if serializer.is_valid():
            instance = serializer.save()
            return Response({
                "data":serializer.data,
                "id":instance.id,
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
    # permission_classes = [IsAuthenticated] # keyinchalik faqat risk role dagila qo'sha oladigan permission beramiz
    
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
            serializer = CategorySerializer(intance = department, data = request.data, partial = True)
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
    
    @swagger_auto_schema(request_body=RiskSerializer, tags = ['Risk'])
    def post(self, request, *args, **kwargs):
        serializer = RiskSerializer(data = request.data)
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
            
    @swagger_auto_schema(tags = ['Risk'])
    def get(self, request, *args, **kwargs):
        risk = Risk.objects.all()
        serializer = RiskSerializer(risk, many = True)
        return Response({
            "data":serializer.data
        })
        
        
class RiskCRUDView(APIView):
    # permission_classes = [IsAuthenticated] 
    
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
            serializer = RiskSerializer(intance = risk, data = request.data, partial = True)
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
            
    @swagger_auto_schema(tags = ["RiskActivity"])
    def delete(self, request, pk, *args, **kwargs):
        riskactivity = RiskActivity.objects.get(id = pk)
        if riskactivity:
            riskactivity.delete()
            return Response({
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(request_body=RiskActivitySerializer, tags = ['RiskActivity'])
    def patch(self, request, pk, *args, **kwargs):
        riskactivity = RiskActivity.objects.filter(id =pk).first()
        if riskactivity:
            serializer = RiskActivitySerializer(intance = riskactivity, data = request.data, partial = True)
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
            
    @swagger_auto_schema(tags = ["RiskCommittee"])
    def delete(self, request, pk, *args, **kwargs):
        data = RiskCommittee.objects.get(id = pk)
        if data:
            data.delete()
            return Response({
                "satatus":status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(request_body=RiskCommitteeSerializer, tags = ['RiskCommittee'])
    def patch(self, request, pk, *args, **kwargs):
        data1 = RiskCommittee.objects.filter(id = pk).first()
        if data1:
            serializer = RiskCommitteeSerializer(instance = data1, data = request.data, partial = True)
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
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
            
class CreateRiskDecisionView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(request_body=RiskDecisionSerializer, tags = ['RiskDecision'])
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
            
    @swagger_auto_schema(tags = ['RiskDecision'])
    def get(self, request, *args, **kwargs):
        decisition = RiskDecision.objects.all()
        serializer = RiskDecisionSerializer(decisition, many = True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        
        
class RiskDecisionCRUDView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(tags = ['RiskDecision'])
    def get(self, request, pk, *args, **kwargs):
        decisition = RiskDecision.objects.filter(id = pk).first()
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
            
    @swagger_auto_schema(tags = ['RiskDecision'])
    def delete(self, request, pk, *args, **kwargs):
        decisition = RiskDecision.objects.filter(id = pk).first()
        if decisition:
            decisition.delete
            return Response({
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(request_body=RiskDecisionSerializer, tags = ['RiskDecision'])
    def patch(self, request, pk, *args, **kwargs):
        decisition = RiskDecision.objects.filter(id = pk).first()
        if decisition:
            serializer = RiskDecisionSerializer(instance = decisition, data = request.data, partial = True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "data":serializer.data,
                    'status':status.HTTP_201_CREATED
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
            
            
class CreateMitigationView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(request_body=MitigationSerializer, tags = ['Mitigation'])
    def post(self, request, *args, **kwargs):
        serialzier = MitigationSerializer(data = request.data)
        if serialzier.is_valid():
            serialzier.save()
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
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(tags = ['Mitigation'])
    def get(self, request, pk, *args, **kwargs):
        mitigation = Mitigation.objects.filter(id - pk).first()
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
            serializer = MitigationSerializer(instance = mitigation, data = request.data, partial = True)
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
        risk = Risk.objects.filter(status = request.data)
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