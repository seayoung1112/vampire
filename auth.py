#!/usr/bin/python
# -*- coding: utf-8 -*-
from models import User
class AuthManager():
    def __init__(self, db):
        self.db = db
    
    def login(self, user, request_handler):
        request_handler.set_secure_cookie('user', str(user.id), 1)
        
    def authenticate(self, name, password):
        try:
            user = self.db.query(User).filter(User.name==name).filter(User.password==password).one()
        except:
            user = None
        return user
    
    def register(self, name, password, confirmed_password, email):
        if password != confirmed_password:
            return None, '密码和确认密码不匹配'
        try:
            user = User(name, password, email)
            self.db.add(user)

        except:
            return None, '注册中出错'
        self.db.flush()
        return user, '注册成功'