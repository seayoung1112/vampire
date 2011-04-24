#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging
class Publisher(object):
    def __init__(self):
        self.listeners = []
        self.messages = []
        self.max_message = 10
        self.first_msg_id = 0
        self.last_msg_id = -1
        
    def __add_msg(self, message, func):
        self.last_msg_id = self.last_msg_id + 1
        message['msg_id'] = self.last_msg_id
        self.messages.append((message, func))
        if len(self.messages) > self.max_message:
            self.messages.pop(0)
            self.first_msg_id = self.messages[0][0]['msg_id']
        
    def __get_msg_list(self, handler):
        messages = []
        start_i = handler.msg_id - self.first_msg_id + 1
        if start_i < 0:
            start_i = 0
        for item in self.messages[start_i :]:
            message = item[0]
            func = item[1]
            if func:
                message = func(handler, message)
            messages.append(message)
        return messages
        
    
    def subscribe(self, handler):
        #之前没有接受过的直接设置到最新的消息        
        if handler.msg_id == None:
            handler.msg_id = self.last_msg_id
        #判断是否中间有没有接受到的消息，并发送这些消息
        messages = self.__get_msg_list(handler)
        if len(messages) > 0:
            handler.finish(dict(messages=messages))
            return 
        self.listeners.append(handler)
        print 'new listener added, total %r' %len(self.listeners) 
    
    def publish(self, message, func=None):
        self.__add_msg(message, func)
        print "Sending new message to %r listeners" %len(self.listeners)        
        for handler in self.listeners:
            try:
                if handler.request.connection.stream.closed():
                    continue
                messages = self.__get_msg_list(handler)
                handler.finish(dict(messages=messages))
            except:
                logging.error("Error in waiter callback", exc_info=True)
        self.listeners = []
        
publishers = {}