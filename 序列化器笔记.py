from rest_framework.generics import ListAPIView,CreateAPIView,RetrieveAPIView,DestroyAPIView
from rest_framework.generics import ListCreateAPIView

class NewsText(CreateAPIView):# CreateAPIView 内部自定义了post方法用时不需要再写
    pass