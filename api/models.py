from django.db import models

class UsserInfo(models.Model):
    phone = models.CharField(verbose_name='手机号',max_length=11,unique=True)
    token = models.CharField(verbose_name='用户Toktn',max_length=64,null=True,blank=True)
