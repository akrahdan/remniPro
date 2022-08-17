import qi
from butane import log
from functools import wraps


"""
conversation.py provides syntactic sugar and useful patterns for working
with qichat via python.

Don't forget to clean up inthe python script onUnload, as below:

def onUnload(self):
    Conversation.stop()  # interrupt active conversation
    unlink()             # unlink all linked functions, methods, classes

The Run App python box should also unsubscribe from Conversation, as below:

def onLoad(self):
    self.unix_dialog = self.session().service('ALDialog')

def onUnload(self):
    try:
        self.unix_dialog.unsubscribe('Conversation')
    except RuntimeError as err:
        self.logger.info('could not unsubscribe Conversation from ALDialog: {}'.format(err))

"""


class InterruptionError(Exception):
    pass


class Conversation(object):
    active = None

    def __init__(self, topic, session=None):
        """Conversation is a context manager for dialog interactions. It provides
        methods for saying proposals and asking questions of the user in a safe
        way. Only one conversation can be active at a time because the robot
        can only have one conversation at a time.

        :param topic: (str) name of Dialog topic
        :param session: (optional) a qi session object
        :raise: RuntimeError if another Conversation is already
        instantiated. InterruptionError if stop is called to interrupt the
        current conversation.
        """
        if not session:
            self.session = qi.Session()
            self.session.connect('localhost')
        else:
            self.session = session
        self.topic = topic
        self.dialog = self.session.service('ALDialog')
        self.memory = self.session.service('ALMemory')
        self.yield_sub = self.memory.subscriber("yield")

        if not Conversation.active:
            Conversation.active = self
        else:
            raise RuntimeError('A Conversation about {} is already active'
                               .format(Conversation.active.topic))

    def __str__(self):
        return self.topic

    def __repr__(self):
        return self.topic

    def __enter__(self):
        log('enter converstaion on topic: {}'.format(self.topic))
        self.dialog.activateTopic(self.topic)
        return self

    def __exit__(self, type, value, traceback):
        try:
            self.dialog.deactivateTopic(self.topic)
        except RuntimeError:
            log('topic {} not found'.format(self.topic))
        Conversation.active = None
        # return True swallows exception
        return isinstance(value, InterruptionError)

    @staticmethod
    def stop():
        try:
            Conversation.active.will_respond.setError('InterruptionError')
        except AttributeError as err:
            log('No active conversation: nothing to stop!: {}'.format(err))
        except RuntimeError as err:
            log('Problem stopping: {}'.format(err))
        finally:
            Conversation.active = None

    def say(self, tag):
        """Say something to the user. Blocking call.

        :param tag: (str) tag to say (in topic)
        """
        self.dialog.setFocus(self.topic)
        self.dialog.gotoTag(tag, self.topic)

    def wait(self, tag):
        """Ask a question and wait for a response (ignore its value).

        :param tag: (str) tag to say (in topic)
        """
        self._ask(tag, None)
        return True

    def ask(self, tag):
        """Ask a question.

        QiChat syntax can follow any of the following forms:
        $yield=hello
        $yield=$1

        Quotations around the values are optional (e.g. $yield="hello")

        :param tag: (str) tag to say (in topic)
        """
        def _strip(string):
            return string.strip()
        return self._ask(tag, _strip)

    def polar(self, tag):
        """Ask a yes or no (polar) question.

        QiChat syntax can be any of the following forms:
        $yield=yes (or '1', 'y')
        $yield=no  (or '0', 'n')

        Quotations around the values are optional (e.g. $yield="yes")

        :param tag: (str) tag to say (in topic)
        :return: True for 'yes', False for 'no'
        :raise: RuntimeError for invalid value passed to $yield
        """
        def _yn(string):
            string = string.strip()
            if string in ['yes', '1', 'y']:
                return True
            elif string in ['no', '0', 'n']:
                return False
            else:
                raise RuntimeError('invalid value for yield during ask_polar')
        return self._ask(tag, _yn)

    def _ask(self, tag, response_formatter):
        """Ask the user for some information and wait for a response.

        Block until a yield memory event. Use a function to return something
        based on that value. Topic is focused and the robot listens for the
        duration of this function call.

        :param tag: (str) tag to say (in topic)
        :param response_formatter: (function) a function that modifies the str
        value of $yield=value and returns something new (of any type)
        (e.g. split the value by semicolons and return a list; return a bool
        based on the value)
        """
        class_name = self.__class__.__name__
        self.dialog.setFocus(self.topic)
        self.dialog.gotoTag(tag, self.topic)
        self.dialog.subscribe(class_name)
        self.will_respond = qi.Promise()

        def on_yield(response):
            log('Yield "{}"'.format(response))
            try:
                if response_formatter:
                    response = response_formatter(response)
            except RuntimeError:
                self.will_respond.setError('InterruptionError')
                raise
            self.will_respond.setValue(response)
            # except RuntimeError as e:
            #     log(e)
        self.yield_id = self.yield_sub.signal.connect(on_yield)
        try:
            response = self.will_respond.future().value()
            return response
        except RuntimeError:
            raise InterruptionError
        finally:
            self.yield_sub.signal.disconnect(self.yield_id)
            self.dialog.unsubscribe(class_name)  # stop listening


# subscriber to `exec` memory key
exec_subscriber = None

# list containing (subscriber, connection_id) pairs for linked functions
subscriber_ids = list()

# list of classes with subscribed methods
subscribed_classes = list()


def linked_function(arg):
    """Register the decorated function as a callback to the `exec` memory event.

    Can be used in the following forms:
    @linked
    @linked(session)

    Where session is a reference to a qi Session.

    QiChat markup is as follows:
    $exec=function_name
    $exec=function_name;arg1
    $exec=function_name;arg1;arg2; ... ;argN

    Each being equivalent to calling the function like so:
    function_name()
    function_name(arg1)
    function_name(arg1, arg2, ... , argN)
    """
    def outer_wrapper(func):
        memory = session.service('ALMemory')
        global exec_subscriber
        if not exec_subscriber:
            exec_subscriber = memory.subscriber("exec")

        def callback(value):
            vs = map(str.strip, value.strip().split(';'))
            func_name = vs[0]
            if func_name == func.__name__:
                func(*vs[1:])

        id = exec_subscriber.signal.connect(callback)
        subscriber_ids.append(id)

        log('linked function: {}'.format(func.__name__))
        return func

    if callable(arg):
        session = qi.Session()
        session.connect('localhost')
        return outer_wrapper(arg)
    else:
        session = arg
        return outer_wrapper


def linked_class(orig_class):
    """Register linked methods from the decorated class as callbacks to the `exec`
    memory event. Use together with @linked_method.

    @linked_class
    class MyClass():

        @linked_method
        def my_method(self, args...):

        @linked_method
        def my_other_method(self, args...):

    The class *must* assign `self.session` attribute to a qi Session.

    QiChat markup is as follows:
    $exec=method_name
    $exec=method_name;arg1
    $exec=method_name;arg1;arg2; ... ;argN

    Each being equivalent to calling the method like so:
    obj.method_name()
    obj.method_name(arg1)
    obj.method_name(arg1, arg2, ... , argN)
    """
    orig_init = orig_class.__init__

    def register_callback_to_exec(instance, subscriber, method):
        method_name = method.__name__

        def exec_callback(value):
            vs = map(str.strip, value.strip().split(';'))
            exec_function_name, exec_function_args = vs[0], vs[1:]
            if exec_function_name == method_name:
                log('call {} with args: {}'.format(method_name,
                                                   exec_function_args))
                method(*exec_function_args)

        subscriber_ids.append(subscriber.signal.connect(exec_callback))
        log('connect callback: {}.{}'.format(instance.__class__.__name__,
                                             method_name))

    @wraps(orig_class.__init__)
    def __init__(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        for cls in subscribed_classes:
            if isinstance(self, cls):
                raise RuntimeError('{} is an instance of {}, which is already \
                                    a linked class!'.format(self, cls))
        log('linked class {}'.format(self.__class__.__name__))
        subscribed_classes.append(self.__class__)
        memory = self.session.service('ALMemory')
        global exec_subscriber
        if not exec_subscriber:
            exec_subscriber = memory.subscriber("exec")
        for method_name in dir(self):
            method = getattr(self, method_name)
            try:
                if method.linked:
                    register_callback_to_exec(self, exec_subscriber, method)
            except AttributeError:
                pass
    orig_class.__init__ = __init__
    return orig_class


def linked_method(method):
    """Decorated method of a linked class will be connected as a callback to
    `exec` memory event.

    :param method: method of a @linked_class to connect
    """
    log('link {}'.format(method.__name__))
    method.linked = True
    return method


def unlink():
    """Unlink all linked functions, methods, and classes. Disconnect all callbacks
    from signals and destroy all subscribers.
    """
    log('unlink all functions, methods, classes')
    global subscriber_ids
    global exec_subscriber
    global subscribed_classes
    for sub_id in subscriber_ids:
        exec_subscriber.signal.disconnect(sub_id)
    exec_subscriber = None
    subscriber_ids = list()
    subscribed_classes = list()
