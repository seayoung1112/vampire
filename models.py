#!/usr/bin/python
# -*- coding: utf-8 -*-
from sqlalchemy import  create_engine
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import backref, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import random

engine = create_engine('mysql://vampire:kknd@localhost/vampire', echo=False)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(30), nullable=False, unique=True)
    password = Column(String(30), nullable=False)
    email = Column(String(75), nullable=False, unique=True)
    
    def __init__(self, name, password, email):
        self.name = name
        self.password = password
        self.email = email
  
class GamePlayer(Base):
    __tablename__ = 'game_player'
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    room_id = Column(Integer, ForeignKey('game.id'), primary_key=True)
    user = relationship(User, backref=backref('game_play', uselist=False, cascade='all, delete-orphan'))
    is_host = Column(Boolean, default=False)
    is_questioner = Column(Boolean, default=False)
    
    def __init__(self, user):
        self.user = user
        self.state = 'init'
        
class Message():
    def __init__(self, user, content):
        self.user = user
        self.content = content
        self.time = datetime.now()
    
class Game(Base):
    __tablename__ = 'game'
    id = Column(Integer, primary_key=True)
    name = Column(String(30), nullable=False)
    state = Column(String(10), default='prepare')
    create_time = Column(DateTime, default=datetime.now)
    player_list = relationship(GamePlayer, backref="game", lazy='dynamic', cascade='all, delete-orphan')
    
    @staticmethod
    def create(name, creator):
        game = Game()
        game.name = name
        game.add_user(creator)
        game.player_list[0].is_host = True
        game.player_list[0].is_questioner = True
        game.player_list[0].state = 'prepared'
        game.messages = []
        return game
        
    def add_user(self, user):
        game_player = GamePlayer(user)
        self.player_list.append(game_player)
        
    def start(self):
        self.state = 'set'
        
    def record_message(self, user, content):
        message = Message(user, content)
        self.messages.append(message)
        
    def dispatch_tip(self, riddle, answer):
        self.riddle = riddle
        self.answer = answer
        total_count = self.player_list.count()
        vampire_count = (total_count - 2) / 2
        #for test
        if vampire_count < 1:
            vampire_count = 1
        picked = random.sample(range(total_count), vampire_count + 1)
        for i in range(total_count):
            if self.player_list[i].is_questioner == True:
                self.player_list[i].role = 'questioner'
                self.__speaker_index = (i + 1) % total_count#将首先发言者设置为出题者的下一个
            else:
                self.player_list[i].role = 'innocent'
        count = 0
        for i in range(vampire_count):
            if self.player_list[picked[i]].is_questioner == True:
                continue
            self.player_list[picked[i]].role = 'vampire'
            count = count + 1
        if count < vampire_count:
            print picked[vampire_count]
            self.player_list[picked[vampire_count]].role = 'vampire'
    
    def next_speaker(self):
        self.__speaker_index = (self.__speaker_index + 1) % self.player_list.count
        
    @property
    def speaker(self):
        return self.player_list[self.__speaker_index]
    
    @property
    def can_start(self):
        if self.player_list.count() < 2:
            return False
        for p in self.player_list:
            if p.state != 'prepared':
                return False
        return True
    
    @property
    def host(self):
        return self.player_list.filter(GamePlayer.is_host==True).one().user
    
metadata = Base.metadata 
def create_all():
    metadata.create_all(engine)