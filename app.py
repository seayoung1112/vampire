#!/usr/bin/python
# -*- coding: utf-8 -*-
import tornado.ioloop
import tornado.web
import os
from sqlalchemy.orm import scoped_session, sessionmaker
from auth import AuthManager
from models import *
from pubsub import Publisher, publishers

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [(r"/", MainHandler),
                    (r'/login', LoginHandler),
                    (r'/register', RegisterHandler),
                    (r'/createGame', CreateGameHandler),
                    (r'/game', GameHandler),
                    (r'/joinGame/([0-9]+)', JoinGameHandler),
                    (r'/quitGame', QuitGameHandler),
                    (r'/roomAction', RoomActionHandler),
                    (r'/setQuestion', SetQuestionHandler),
                    (r'/subscribe/(\w+)', SubscribeHandler),
                    (r'/inTurn/(\w+)', InTurnActionHandler),
                    (r'/chat', ChatHandler),
                    ]
        settings = dict(
            cookie_secret="43oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url="/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            debug=True,
            )
        self.db = scoped_session(sessionmaker(bind=engine))
        self.db.query(Game).delete()
        self.db.query(GamePlayer).delete()
        self.db.commit()
        create_all()
        self.auth = AuthManager(self.db)
        publishers['hall'] = Publisher()
        tornado.web.Application.__init__(self, handlers, **settings)

class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        user_id = self.get_secure_cookie('user')
        if not user_id:
            return None 
        return self.db.query(User).get(user_id)
    @property
    def db(self):
        return self.application.db
    @property
    def auth(self):
        return self.application.auth

class MainHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        if self.db.query(GamePlayer).filter(GamePlayer.user==self.current_user).count() > 0:
            self.redirect('/game')
            return
        games = self.db.query(Game)
        self.render('hall/index.html', games=games)
                
class SubscribeHandler(BaseHandler):
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def post(self, channel):
        publisher = publishers[channel]
        self.msg_id = self.get_argument('msg_id', None)
        if self.msg_id:
            self.msg_id = int(self.msg_id)
        if publisher:
            publisher.subscribe(self)
        else:
            self.write('this channel does not exist!')        

class LoginHandler(BaseHandler):
    def get(self):
        self.render('auth/login.html')
    
    def post(self):
        name = self.get_argument('name')
        password = self.get_argument('password')
        user = self.auth.authenticate(name, password)
        if user:
            self.auth.login(user, self)
            self.redirect('/')
        else:
            self.write('can not log in')
        
class RegisterHandler(BaseHandler):
    def get(self):
        self.render('auth/register.html')
        
    def post(self):
        name = self.get_argument('name')
        password = self.get_argument('password')
        confirmed_password = self.get_argument('confirmed_password')
        email = self.get_argument('email')
        user, message = self.auth.register(name, password, confirmed_password, email)
        if user:
            self.auth.login(user, self)
        else:
            self.write(message)
        self.redirect('/')
        
class HallMessager(object):
    @staticmethod
    def publish(handler, type, game):
        message = {'type':type,
                   'id':game.id,}
        if type != 'delete':
            message['html'] = handler.render_string('game/game_unit.html', game=game)
        print 'pubsh hall message'
        publishers['hall'].publish(message)

@property       
def game_channel(self):
    return 'game' + str(self.id)
Game.channel = game_channel

class CreateGameHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        name = self.get_argument('name')
        user = self.current_user        
        if self.db.query(GamePlayer).filter(GamePlayer.user==self.current_user).count() > 0:
            self.write(u'你已经在房间' + str(user.game_play.game.id) + u'里')
            return
        game = Game.create(name, user)
        publishers[game.channel] = Publisher()
        HallMessager.publish(self, 'add', game)
        self.db.add(game)
        self.redirect('/game')
        
class QuitGameHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        game_player = self.db.query(GamePlayer).filter(GamePlayer.user==self.current_user).one()
        game = game_player.game
        self.db.delete(game_player)
        if game.player_list.count() == 0:
            self.db.delete(game)            
            publishers.pop(game.channel)
            print '%s poped' %game.channel
            HallMessager.publish(self, 'delete', game)
        else:
            if game_player.is_host:
                #change host
                game.player_list[0].is_host = True
                game.player_list[0].state = 'prepared'
            HallMessager.publish(self, 'update', game)
            message = {'type': 'user-leave', 'user_id': self.current_user.id, 'host_id': game.player_list[0].user_id, 'can_start': game.can_start}
            publishers[game.channel].publish(message)
        self.redirect('/')
        
class JoinGameHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, game_id):
        user = self.current_user
        game = self.db.query(Game).get(game_id)
        if self.db.query(GamePlayer).filter(GamePlayer.user==self.current_user).count() > 0:
            self.write(u'你已经在房间' + str(user.game_play.game.id) + u'里')
            return
        else:
            game.add_user(user)
        #notify hall
        HallMessager.publish(self, 'update', game)
        message = {'type': 'user-join', 'html': self.render_string('player/player_unit.html', user=user),}
        publishers[game.channel].publish(message)
        self.redirect('/game')

        
class GameHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        try:
            game = self.db.query(Game).filter(Game.player_list.contains(self.current_user.game_play)).one()            
        except:
            self.write(u'此房间已不存在')
            return 
        self.render('game/game.html', game=game)
        
        
class RoomActionHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        game = self.db.query(Game).get(self.get_argument('id'))
        action = self.get_argument('action')
        user = self.current_user
        refresh = True
        func = None
        name = ''
        next_action = ''
        if action == 'prepare':
            user.game_play.state = 'prepared'
            name = '取消'
            next_action = 'cancel'
            message = {'can_start': game.can_start, 'type': 'user-state-change', 'user_id': user.id, 'html': self.render_string('player/player_unit.html', user=user)}
        elif action == 'cancel':
            user.game_play.state = 'init'
            name = '准备'
            next_action = 'prepare'
            message = {'can_start': game.can_start, 'type': 'user-state-change', 'user_id': user.id, 'html': self.render_string('player/player_unit.html', user=user)}
        elif action == 'start':
            game.start()
            message = {'type': 'game-start'}
            refresh = False
            func = self.start_message
        publishers[game.channel].publish(message, func)
        self.write({'name': name, 'action': next_action, 'refresh': refresh})
        
    def start_message(self, handler, message):
        user = handler.current_user
        if user.game_play.is_questioner:
            message['html'] = handler.render_string('player/set_question.html')
        else:
            message['html'] = u'等待出题'
        return message
#设置迷面和谜底环节    
class SetQuestionHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        game = self.db.query(Game).get(self.get_argument('id'))
        riddle = self.get_argument('riddle')
        answer = self.get_argument('answer')
        game.dispatch_tip(riddle, answer)

        #send message
        message = {'type': 'get-tip', 'speaker': game.speaker.user_id}
        publishers[game.channel].publish(message, self.get_tip_message)
        
    def get_tip_message(self, handler, message):
        user = handler.current_user
        print user.game_play.role
        if user.game_play.role == 'vampire':
            role = u'吸血鬼'
            tip = u'谜面:' + user.game_play.game.riddle
        elif user.game_play.role == 'innocent':
            role = u'平民'
            tip = u'谜底:' + user.game_play.game.answer
        elif user.game_play.role == 'questioner':
            role = u'出题者'
            tip = u'谜面:' + user.game_play.game.riddle + u'谜底:' + user.game_play.game.answer
        message['html'] = handler.render_string('game/game_panel.html', role=role, tip=tip)
        return message
#发言环节，可以阐述或者过
class InTurnActionHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, command):
        game = self.db.query(Game).get(self.get_argument('id'))
        user = self.current_user
        if command == 'say':
            content = self.get_argument('content')        
            game.record_message(user, content)
            message = {'type': 'say', 'name': user.name, 'content': content}
        elif command == 'pass':
            game.next_player()
            message = {}
        publishers[game.channel].publish(message)
#聊天，任何人在任何时候都可以说        
class ChatHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        game = self.db.query(Game).get(self.get_argument('id'))
        content = self.get_argument('content')
        print content
        user = self.current_user
        message = {'type': 'chat', 'name': user.name, 'content': content}
        publishers[game.channel].publish(message)

def main():
    app = Application()
    app.listen(8888)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()

