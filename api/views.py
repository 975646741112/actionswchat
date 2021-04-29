import re
import random
import uuid
import json
import pathlib
import requests
import token
import os
print('master commit')
from sts.sts import Sts
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django_redis import get_redis_connection
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
# 导入对应产品模块的client models。
from tencentcloud.sms.v20190711 import sms_client, models
from django.conf import settings
from api import models


def phone_validator(value): # validators = [phone_validator] 自定义的验证函数
    if not re.match(r'^(1[3|4|5|6|7|8|9])\d{9}$',value):
        raise ValidationError("手机号格式错误")


class MessageSerializers(serializers.Serializer):
    phone = serializers.CharField(label='手机号',validators=[phone_validator])
# 校验时先内部检验，然后再去自定义函数中去校验，最后使用钩子函数检验
#     def validate_phone(self, value):# 钩子函数
#         pass


class LoginSerializers(serializers.Serializer):
    phone = serializers.CharField(label='手机号',validators=[phone_validator])
    code = serializers.CharField(label='短信验证码')

    def validator_code(self,value):
        if len(value) != 4:
            raise ValidationError('短信格式错误')
        if not value.isdecimal():
            raise ValidationError('短信格式错误')
        phone = self.initial_data.get('phone')
        conn = get_redis_connection()
        code = conn.get('phone')
        if not code:
            raise ValidationError('短信验证码过期')
        if code != value:
            raise ValidationError('验证码错误')
        return value


class MessageView(APIView):
    def get(self,request,*args,**kwargs):
        # 1 获取手机号
        # 2 手机格式进行校验
        ser = MessageSerializers(data=request.query_params)
        if ser.is_valid():
            return Response({'status':False,'message':"手机格式错误"})
        phone = ser.validated_data.get('phone')

        CHINA = '+86'
        phone = '{}{}'.format(CHINA,phone)

        # 3 生成随机验证码
        random_code = random.randint(1000,9999)

        # 4 验证码发到手机上，购买服务器发送短信，腾讯云
        '''
        1 注册腾讯云，开通腾讯云短信，
        2 创建应用：
            SDK APPID = 123322
        3 申请国内短信签名
           个人：公众号
           ID = 364455
           名称 = 菜鸟python开发
        4 申请模板
          Id        模板名称
          932576    pymessage
        5 申请腾讯云API
          Secretid: AKIDTjxZw3VZ0BLH0RTw73xb0A6mNlvpusiH
          Secret key: VcDfrmSLzNVFk9LiQt6i8LK3dx5zlbIw
        6 调用相关接口去发送短信
        '''
        try:
            # 必要步骤：
            # 实例化一个认证对象，入参需要传入腾讯云账户密钥对secretId，secretKey。
            # 这里采用的是从环境变量读取的方式，需要在环境变量中先设置这两个值。
            cred = credential.Credential("AKIDTjxZw3VZ0BLH0RTw73xb0A6mNlvpusiH", "VcDfrmSLzNVFk9LiQt6i8LK3dx5zlbIw")
            # 实例化要请求产品(以sms为例)的client对象
            # 第二个参数是地域信息，可以直接填写字符串ap-guangzhou，或者引用预设的常量
            client = sms_client.SmsClient(cred, "ap-guangzhou")

            req = models.SendSmsRequest()

            # 短信应用ID: 短信SdkAppid在 [短信控制台] 添加应用后生成的实际SdkAppid，示例如1400006666
            req.SmsSdkAppid = "	1305683818"
            # 短信签名内容: 使用 UTF-8 编码，必须填写已审核通过的签名，签名信息可登录 [短信控制台] 查看
            req.Sign = "菜鸟Python开发"

            req.PhoneNumberSet = [phone]
            # 模板 ID: 必须填写已审核通过的模板 ID。模板ID可登录 [短信控制台] 查看
            req.TemplateID = "932576"
            # 模板参数: 若无模板参数，则设置为空
            req.TemplateParamSet = [random_code]

            # 通过client对象调用DescribeInstances方法发起请求。注意请求方法名与请求对象是对应的。
            # 返回的resp是一个DescribeInstancesResponse类的实例，与请求对象对应。
            resp = client.SendSms(req)

            # 输出json格式的字符串回包
            print(resp.to_json_string(indent=2))

        except TencentCloudSDKException as err:
            print(err)
        # 5 把验证码加手机号保留(设置30s过期)
        # 5.1 自己搭建redis服务器(云redis)
        # django 中方便使用redis的模块(django-redis)
        # 设置
        conn = get_redis_connection()
        conn.set(phone,random_code,ex=30)
        return Response({'status':True,'message':"验证码发送成功"})


class LoginView(APIView):

    def post(self,request,*args,**kwargs):
        print(Response.data)
        '''
        1 校验手机号是否合法
        2 校验验证码：redis
          —— 无验证码（验证码过期）
          -- 有验证码（输入错误）
          -- 验证码输入正确通过
        3 获取用户信息（如果存在跳转用户界面/不存在就创建用户）
        4 将一些信息返回给小程序
        '''
        ser = LoginSerializers(data=request.data)
        if not ser.is_valid():
            return Response({'status':False,'message':'验证码错误'})

        # 1 获取用户信息（如果存在跳转用户界面/不存在就创建用户）
        phone = ser.validated_data.get('phone')
        user_obj,flag = models.UsserInfo.objects.get_or_create(phone = phone)# flag = True 新创建的，如果不是新创建的 flag = False
        user_obj.token = str(uuid.uuid4())
        user_obj.save()


        # 2 获取用户信息（如果存在跳转用户界面/不存在就创建用户）
        # user = models.UsserInfo.objects.filter(phone=phone).first()
        # if not user:
        #     models.UsserInfo.objects.create(phone=phone,token = str(uuid.uuid4()))
        # else:
        #     user.token = str(uuid.uuid4())
        #     user.save()

        return Response({'status':True,'data':{'token':user_obj.token,'phone':phone}})


class CredentialView(APIView):

    def get(self,reuqest,*args,**kwargs):
        config = {
            'duration_seconds': 1800,
            'secret_id': os.environ['COS_SECRET_ID'],
            # 固定密钥
            'secret_key': os.environ['COS_SECRET_KEY'],
            # 换成你的 bucket
            'bucket': 'example-1253653367',
            # 换成 bucket 所在地区
            'region': 'ap-guangzhou',
            # 这里改成允许的路径前缀，可以根据自己网站的用户登录态判断允许上传的具体路径
            'allow_prefix': '*',
            # 密钥的权限列表。简单上传和分片需要以下的权限，其他权限列表请看 https://cloud.tencent.com/document/product/436/31923
            'allow_actions': [
                # 简单上传
                'name/cos:PostObject',
                'name/cos:DeleteObject',
            ],

        }
        sts = Sts(config)
        response = sts.get_credential()
        return Response(response)


# get     获取临时cos密钥(临时密钥需要有上传和删除的权限)(url/view)
# get     获取话题接口(1 url  2 序列化  3 view(获取所有的话题（ListApiview）))
# post    提交新闻信息（1 url  2 序列化  3 view（CreateApiview））






