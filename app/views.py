from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_yasg.utils import swagger_auto_schema
from .serializers import (RiskActivitySerializer, RiskCommitteeSerializer, RiskDecisionSerializer,
                          RiskSerializer, MitigationSerializer, DepartmentSerializer)
from .models import (Department, Risk, RiskActivity, RiskCommittee, RiskDecision,
                     Mitigation)


class DepartmentView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=DepartmentSerializer, tags = ['Department'])
    def post(self, request, *args, **kwargs):
        serializer = DepartmentSerializer(data = request.data)
        if serializer.is_valid():
            serializer.save()
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
    permission_classes = [IsAuthenticated] # keyinchalik faqat risk role dagila qo'sha oladigan permission beramiz
    
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
            serializer = DepartmentSerializer(intanse = department, data = request.data, partial = True)
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
    permission_classes = [IsAuthenticated, ]
    
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
    permission_classes = [IsAuthenticated] 
    
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
            serializer = RiskSerializer(intanse = risk, data = request.data, partial = True)
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
    permission_classes = [IsAuthenticated, ]
    
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
    permission_classes = [IsAuthenticated] 
    
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
            serializer = RiskActivitySerializer(intanse = riskactivity, data = request.data, partial = True)
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