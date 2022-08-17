import qi
import urllib
import time
import os
import random

class RemiService(object):

    def __init__(self, session):
        self.session = session
        self.logger = qi.Logger("RemiService")
        self.memory = self.session.service("ALMemory")


        self.login_event = self.memory.subscriber('RemiService/LoginRequest')
        self.login_subs_id = self.login_event.signal.connect(self.handle_login)
    
    def handle_login(self, *unused):
        self.logger.info("Attempting to Login")
    
    def _get_tablet_service(self):
        """Returns the ALTabletService object running on the tablet."""
        try:
            tablet_service = self.session.service('ALTabletService')
            return tablet_service
        except RuntimeError as err:
            self.logger.warning(
                'ALTabletService not available: {}'.format(err))
            return None
    
    def hide_web_display(self):
        tablet_service = self._get_tablet_service()
        if tablet_service:
            tablet_service.hideWebview()

    def _get_robot_ip(self):
        """Get the robot IP address as seen from the tablet"""
        robot_ip = "198.18.0.1"
        try:
            tablet_service = self._get_tablet_service()
            if tablet_service:
                robot_ip = tablet_service.robotIp()
        except RuntimeError:
            pass
        finally:
            return robot_ip
    
    def register_as_service(service_class, robot_ip='127.0.0.1'):
        session = qi.Session()
        session.connect("tcp://{}:9559".format(robot_ip))
        service_name = service_class.__name__
        instance = service_class(session)
        try:
          session.registerService(service_name, instance)
          print 'Successfully registered service: {}'.format(service_name)
        except RuntimeError:
          print'{} already registered, attempt re-register'.format(service_name)
          for info in session.services():
            try:
                if info['name'] == service_name:
                    session.unregisterService(info['serviceId'])
                    print "Unregistered {} as {}".format(service_name,
                                                         info['serviceId'])
                    break
            except (KeyError, IndexError):
                pass
          session.registerService(service_name, instance)
          print 'Successfully registered service: {}'.format(service_name)

    
    