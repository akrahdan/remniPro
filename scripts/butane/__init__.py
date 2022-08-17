import qi
import smtplib
import os
import urllib
try:
    import Image
except ImportError:
    pass
import uuid
import shutil
from threading import Lock
from functools import wraps
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.header import Header
from email.utils import formataddr

LOG_FUNC = None


def log(string):
    butane_str = '[butane] {}'
    if not LOG_FUNC:
        print(butane_str.format(string))
    else:
        LOG_FUNC(butane_str.format(string))


def set_logger(log_fn):
    """Provide the butane package with a logging function. Defaults to print.

    :param log_fn: a logging function. e.g. logger.info, logger.debug
    """
    global LOG_FUNC
    LOG_FUNC = log_fn

run = True
RUN_LOCK = Lock()


def boxy(func):
    """Decorated function will not be called if stop has been called (run is
    False).
    """
    @wraps(func)
    def wrapped(*args, **kwargs):
        if run:
            log('call {}'.format(func.__name__))
            return func(*args, **kwargs)
    return wrapped


def stop():
    """Prevent all calls to @boxy functions."""
    with RUN_LOCK:
        log('prevent all future calls to @boxy decorated functions')
        global run
        run = False


def start():
    """Allow all calls to @boxy functions."""
    with RUN_LOCK:
        log('allow all future calls to @boxy decorated functions')
        global run
        run = True


def test_function():
    return "This is an amazing test string."


def is_nao(session=None):
    """Return True if robot is NAO, False otherwise."""
    if not session:
        session = qi.Session()
        session.connect('localhost')
    motion = session.service('ALMotion')
    return 'nao' in motion.getRobotConfig()[1][0]


def is_pepper(session=None):
    """Return True if robot is Pepper, False otherwise."""
    if not session:
        session = qi.Session()
        session.connect('localhost')
    motion = session.service('ALMotion')
    return 'juliette' in motion.getRobotConfig()[1][0]


def send_email(from_user, pwd, to, subject, text, smtp,
               from_user_present=None, html=None, images=None, port=None):
    """Send an email (allows for html and image attachements)

    :param from_user: sender of the email (email address)
    :param pwd: password of from_user
    :param to: recipient of the email
    :param subject: subject of the email
    :param body: body text of the email
    :param smtp: server you're sending from
    :param from_user_present: [Optional] sender of the email (actual name)
    :param html: [Optional] html email message
    :param images: [Optional] list of images to be embedded
    :param port: [Optional] port to use
    """

    send = None
    success = False

    # Encode message
    formatted_email = MIMEMultipart('alternative')
    if from_user_present:
        formatted_email['From'] = formataddr((str(Header(from_user_present, 'utf-8')), from_user))
    else:
        formatted_email['From'] = from_user

    formatted_email['To'] = to
    formatted_email['Subject'] = subject
    formatted_email.attach(MIMEText(text, 'plain'))

    if html:
        formatted_email.attach(MIMEText(html, 'html'))
    else:
        formatted_email.attach(MIMEText(html, ' '))

    if images:
        for idx, image in enumerate(images):
            fp = open(image, 'rb')
            current_image = MIMEImage(fp.read())
            fp.close()

            current_image.add_header('Content-ID', '<image{}>'.format(idx+1))
            formatted_email.attach(current_image)

    # Send
    try:
        if port:
            send = smtplib.SMTP(smtp, port)
        else:
            send = smtplib.SMTP(smtp)
    except (smtplib.SMTPConnectError, smtplib.socket.gaierror) as err:
        print err
        return success

    try:
        send.ehlo()

        # Attempt to encrypt
        if send.has_extn('STARTTLS'):
            send.starttls()
            send.ehlo()

        send.login(from_user, pwd)
        send.sendmail(from_user, [to], formatted_email.as_string())
        success = True
    except (smtplib.SMTPHeloError,
            smtplib.SMTPAuthenticationError,
            smtplib.SMTPException,
            smtplib.SMTPRecipientsRefused,
            smtplib.SMTPSenderRefused,
            smtplib.SMTPDataError,
            RuntimeError) as e:
        print e
    finally:
        send.quit()

    return success


def get_package_id(path):
    """Returns package id without any sub-behavior path.
    :param path: path to the desired behavior.
    :returns: package id string or '' if the string is invalid.
    """
    try:
        return os.path.normpath(path).split(os.path.sep)[0]
    except AttributeError:
        return ''


def register_as_service(service_class, robot_ip="127.0.1", app_path=None):
    """Registers naoqi service.
    :param service_class: class to register as a naoqi service.
    :param robot_ip: address of the target naoqi instance.
    :returns: instance of service_class
    """
    session = connect_session(robot_ip)
    service_name = service_class.__name__
    instance = service_class(session, app_path)
    try:
        session.registerService(service_name, instance)
        log("Successfully registered service: {}".format(service_name))
    except RuntimeError:
        log("Unable to register service: {}".format(service_name))
    return instance


def connect_session(robot_ip='localhost'):
    """Connects qi.Session object to robot_ip.
    :param session: qi Session object.
    :param robot_ip: address of the host in case session is None.
    :returns: qi Session connected to the provided robot_ip.
    """
    session = qi.Session()
    session.connect("tcp://{}:9559".format(robot_ip))
    return session


def run_service(service_class, robot_ip='localhost'):
    """Register class as a naoqi service and run it.:
    :param service_class: Class to be registered as a service.
    """
    register_as_service(service_class, robot_ip)
    app = qi.Application()
    app.run()


def cache_remote_file(url, save_path):
    """Given a URL, cache the file at the directory supplied"""
    try:
        urllib.urlretrieve(url, save_path)
        return True
    except (IOError, urllib.ContentTooShortError) as e:
        raise RuntimeError('Unable to cache file :: {}'.format(e))


def delete_cached_file(path):
    """Given a path to a cached img, delete it"""
    try:
        os.remove(path)
        return True
    except OSError as e:
        raise RuntimeError('Unable to remove cached file :: {}'.format(e))


def cache_remote_img(url, pkg_uid):
    """Given a img URL, cache the file in pkg's html/img folder"""
    file_ext = os.path.splitext(url)[1]
    pkg_path = os.path.join(os.path.expanduser('~/.local/share/PackageManager/apps'), pkg_uid)
    pkg_img_cache_path = os.path.join(pkg_path, 'html/img/butane_cache')

    # create img cache (if it doesn't already exist)
    if os.path.isdir(pkg_path):
        if not os.path.isdir(pkg_img_cache_path):
            try:
                os.makedirs(pkg_img_cache_path)
            except OSError as e:
                raise RuntimeError('Unable to create img cache')
    else:
        raise RuntimeError('Invalid pkg')

    file_name = str(uuid.uuid4()) + file_ext
    file_path = os.path.join(pkg_img_cache_path, file_name)

    # cache file in butane img cache
    cache_remote_file(url, file_path)
    with open(file_path, 'rb') as f:
        try:
            img = Image.open(f)
            del img
        except IOError as e:
            delete_cached_img(pkg_uid, file_name)
            raise RuntimeError('File requested is not a valid image :: {}'.format(e))
    return file_name, file_path


def delete_cached_img(pkg_uid, filename):
    """Given a pkg id and filename, remove the file from the cache"""
    pkg_img_cache_path = os.path.join(os.path.expanduser('~/.local/share/PackageManager/apps'),
                                      pkg_uid, 'html/img/butane_cache')
    if os.path.isdir(pkg_img_cache_path):
        delete_cached_file(os.path.join(pkg_img_cache_path, filename))
    else:
        raise RuntimeError('Pkg has no img cache')


def clear_img_cache(pkg_uid):
    """Given a pkg id, clear the img cache (if it exists)"""
    pkg_img_cache_path = os.path.join(os.path.expanduser('~/.local/share/PackageManager/apps'),
                                      pkg_uid, 'html/img/butane_cache')

    if os.path.isdir(pkg_img_cache_path):
        shutil.rmtree(pkg_img_cache_path)
    else:
        raise RuntimeError('Pkg has no img cache')

    # CC: maybe some form of the below are useful?

    # def stand_up(self, n_tries):
    #     """Try to go to posture Stand n_tries times."""
    #     self.posture.setMaxTryNumber(n_tries)
    #     if not self.posture.goToPosture('Stand', 0.80):
    #         raise RuntimeError("Could not Stand after {} tries!".format(n_tries))

    # def say_and_animate(self, tag, topic, anim_beh_name):
    #     """Simultaneously say tag in topic and run behavior anim_beh_name."""
    #     if self.run:
    #         fut = qi.async(self.dialog.gotoTag, tag, topic)
    #         self.bm.runBehavior(self.uuid + '/animations/' + anim_beh_name)
    #         fut.wait()

    # def run_anim(self, name, forced=False):
    #     """Run grasping animation behavior."""
    #     if self.run or forced:
    #         self.logger.debug('run anim: {}'.format(name))
    #         self.bm.runBehavior(self.uuid + '/animations/{}'.format(name))

    # def stop_anim(self, name):
    #     """Stop grasping animation behavior."""
    #     self.logger.debug('stop anim: {}'.format(name))
    #     self.bm.stopBehavior(self.uuid + '/animations/{}'.format(name))
