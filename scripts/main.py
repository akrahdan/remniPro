

import qi
import threading
import requests
import stk.runner
import stk.events
import stk.services
import stk.logging
from functools import partial

__version__ = '0.0.1'
__copyright__ = 'Copyright 2022, DECRS'
__author__ = 'Alfia, Sam'
__email__ = 'parve023@d.umn.edu, akrah001@d.umn.edu'


@qi.multiThreaded()
class Reminiscence(object):
 

    PKG_ID = 'reminiscence'
    APP_ID = 'com.aldebaran.{}'.format(PKG_ID)
    PKG_PATH = '/home/nao/.local/share/PackageManager/apps/{}'.format(PKG_ID)
    
    LOGIN_REQUEST = "ReminiscenceService.onLogin"
    TOPIC_PATHS = None
    SOUND_PATH = '{0}/sounds/{1}'.format(PKG_PATH, '{}')
  

    def __init__(self, qiapp):
        self.qiapp = qiapp
        self.events = stk.events.EventHelper(qiapp.session)
        self.s = stk.services.ServiceCache(qiapp.session)
        self.logger = stk.logging.get_logger(qiapp.session, self.APP_ID)


        self.show_tablet()
        
        self.s.ALBasicAwareness.pauseAwareness()
       

        self.language = self.s.ALDialog.getLanguage()
        code = self.s.ALDialog.convertLongToNU(self.language)

       
        eDOFM = 'enableDeactivationOfFallManager'
        try:
            config = self.s.ALMotion._getMotionConfig('Protection')
            self.orig_safety = {x.split(':')[0].strip():
                                [float(z) for z in x.split(':')[1].strip().rstrip(',').split(',')]
                                for x in config.split('\n') if ':' in x}[eDOFM][0]
        except (KeyError, ValueError, RuntimeError):
            self.orig_safety = 0
        self.s.ALMotion.setMotionConfig(
            [['ENABLE_DEACTIVATION_OF_FALL_MANAGER', 1]])
        self.s.ALAutonomousLife.setSafeguardEnabled(
            'RobotMoved', False)
        self.catalog = []
        self.keywords = {}
        self.store_data = None
        self.store_data_fut = None

        self.speech_lock = threading.Lock()
        self.events.connect("onLogin", self.handle_login)
        

    def show_tablet(self):
        self.logger.verbose('Attempting to start tablet webview')
        tablet = self.s.ALTabletService
        if tablet:
            robot_ip = tablet.robotIp()
            app_url = 'http://{}/apps/{}/'.format(robot_ip, self.PKG_ID)
            tablet.showWebview(app_url)
        else:
            self.logger.warning('Lost tablet service, cannot load ' +
                                'application: {}'.format(self.PKG_ID))

    #
    # STK.runner required functions
    #

    @qi.nobind
    def handle_login(self, *data):
        # response = data
        
        self.s.ALTextToSpeech.say("I am frustrated too")
        # self.logger.info('User login by: %s' % data['email'])
     

    def on_start(self):
        """Starts everything"""
        
        self.listen_for_commands()
       

    @qi.bind(returnType=qi.Void, paramsType=[])
    def stop(self):
        self.logger.info('Stopped by user request.')
        self.qiapp.stop()

    @qi.nobind
    def on_stop(self):
        """Cleanup"""
        self.events.disconnect('loginRequest')
        self.events.clear()
       

        try:
            self.s.ALDialog.unsubscribe(self.APP_ID)
        except RuntimeError as err:
            self.logger.warning(
                'Problem unsubscribing dialog: {}'.format(err))
        self.logger.info('Reminiscence Therapy donee.')

    #
    # Dialog-based functionality
    #

    def on_touched(self, *args):
        "Callback for tablet touched."
        if args:
            self.events.disconnect("ALTabletService.onTouchDown")
            self.s.ALTextToSpeech.say("Weldone bro!")
            # self.stop()

    def listen_for_commands(self):
        """Listen for verbal commands."""
        self.s.ALDialog.subscribe(self.APP_ID)

    def stop_speech(self, data):
        self.s.ALTextToSpeech.stopAll()

    def say_tag(self, tag):
        self.logger.info('say_tag : %s' % tag)
        with self.speech_lock :
            try:
                self.s.ALBasicAwareness.pauseAwareness()
                self.s.ALDialog.gotoTag(tag, self.TOPIC_NAME)
            except RuntimeError:
                pass

    def ignore_commands(self):
        """Ignore verbal commands."""
        try:
            # self.s.ALTextToSpeech.stopAll()
            self.s.ALDialog.deactivateTopic(self.TOPIC_NAME)
            try:
                self.s.ALDialog.unsubscribe(self.APP_ID)
            except Exception as err:
                self.logger.warning('Problem unsubscribing: {}'.format(err))
        except Exception as err:
            self.logger.warning('Problem ignoring commands: {}'.format(err))


   
 
     


####################
# Setup and Run
####################

if __name__ == '__main__':
    stk.runner.run_activity(Reminiscence)
