"""language_utils.py

Tools for app internationilisation.
"""

import qi
import json
import os
import random
import weakref
from functools import partial
from butane import log

LANGUAGES = {
    'Arabic':     {'package': 'ar_SA', 'dialog': 'arw'},
    'Chinese':    {'package': 'zh_CN', 'dialog': 'mnc'},
    'Czech':      {'package': 'cs_CZ', 'dialog': 'czc'},
    'Danish':     {'package': 'da_DK', 'dialog': 'dad'},
    'Dutch':      {'package': 'nl_NL', 'dialog': 'dun'},
    'English':    {'package': 'en_US', 'dialog': 'enu'},
    'Finnish':    {'package': 'fi_FI', 'dialog': 'fif'},
    'French':     {'package': 'fr_FR', 'dialog': 'frf'},
    'German':     {'package': 'de_DE', 'dialog': 'ged'},
    'Italian':    {'package': 'it_IT', 'dialog': 'iti'},
    'Japanese':   {'package': 'ja_JP', 'dialog': 'jpj'},
    'Korean':     {'package': 'ko_KR', 'dialog': 'kok'},
    'Polish':     {'package': 'pl_PL', 'dialog': 'plp'},
    'Portuguese': {'package': 'pt_PT', 'dialog': 'ptp'},
    'Brazilian':  {'package': 'pt_BR', 'dialog': 'ptb'},
    'Russian':    {'package': 'ru_RU', 'dialog': 'rur'},
    'Spanish':    {'package': 'es_ES', 'dialog': 'spe'},
    'Swedish':    {'package': 'sv_SE', 'dialog': 'sws'},
    'Turkish':    {'package': 'tr_TR', 'dialog': 'sws'},
    'Norwegian':  {'package': 'nn_NO', 'dialog': 'non'}
}


def language_code(lang, target):
    """
    Returns language code (e.g. "en_US" or "enu") when given language name.
    Returns None if the language name or target are invalid or unavailable.

    :param lang  : Language name as provided by ALTextToSpeech.getLanguage()
    :param target: In which context should the code be useful
                   ("dialog" or "package")
    """
    try:
        return LANGUAGES[lang][target]
    except KeyError:
        return None


def set_system_language(language, session=None):
    """Change the language in all systems that require the language to be
    changed."""
    if session is None:
        session = qi.Session()
        session.connect('localhost')

    try:
        tts = session.service("ALTextToSpeech")
        tts.setLanguage(language)
    except RuntimeError:
        log('Unable to set language in ALTextToSpeech')

    try:
        asr = session.service("ALSpeechRecognition")
        asr.setLanguage(language)
    except RuntimeError:
        log('Unable to set language in ALSpeechRecognition')

    try:
        dialog = session.service("ALDialog")
        dialog.setLanguage(language)
    except RuntimeError:
        log('Unable to set language in ALDialog')

    try:
        roc = session.service("RobotControl")
        roc.handle_language_change()
    except RuntimeError:
        log('Unable to set language in RobotControl')


class Localizer(object):
    """Loads dynamic strings and provides their localized form.

       Reads loacalized string from a json file with this structure:

       {
        "string to be translated":
            {"Language": ["possible", "translations"]},
            {"Anotehr Language": ["another", "translation"]}
       }

    """

    def __init__(self, path, language, session=None):
        """Initialises the localizer.

        :param path    : Path to localized strings json file.
        :param language: Language used for translation (e.g. "English").
        :param session: session object. Will use the local session by default.
        """

        self.ses = None
        self.memory = None
        self.tts = None
        self.language = None
        self.loc_strings = None
        self.subscriptions = list()
        self.onLanguageChange = qi.Signal()

        self._get_session(session)
        self._get_services()
        self.set_language(language)
        self._monitor_language_change()
        self.set_strings(path)

    def __del__(self):
        # Clear all subscriptions made
        for (sig, sub_id) in self.subscriptions:
            try:
                sig.disconnect(sub_id)
            except RuntimeError as err:
                log('Unable to unsubscribe callback: {}'.format(err))

    def t(self, string_id):
        """Translates string according to the options available in the
        localization db. Returns '' if no translation is found.

        :param string_id: id of the string to be translated
        :returns: translated string as randomli selected from the available
                  candidates. '' is returned if no candidates are found.
        """

        try:
            return random.choice(self.loc_strings[string_id][self.language])
        except (KeyError, TypeError):
            return ''

    def _get_session(self, session):
        """Get session object either from the argument or the localhost."""
        if session is None:
            self.ses = qi.Session()
            self.ses.connect('localhost')
        else:
            self.ses = session

    def _get_services(self):
        """Get required services for the object to function properly."""
        self.memory = self.ses.service('ALMemory')
        self.tts = self.ses.service('ALTextToSpeech')

    def set_strings(self, path):
        """Read translations strings from a json file.

        :param path: path to the json file. '~' will be expanded accordingly.
        """
        path = os.path.expanduser(path)
        try:
            with open(path) as loc_db:
                self.loc_strings = json.load(loc_db)
        except (IOError, AttributeError):
            self.loc_strings = None

    def set_language(self, language=None):
        """Sets the localizer language.

        :param language: Language string as provided by
                         ALTextToSpeech.getLanguage() (e.g. "English")
        """
        if language is None:
            self.language = self.tts.getLanguage()
        elif language in LANGUAGES.keys():
            self.language = language
        else:
            raise RuntimeError('{} is an invalid language'.format(language))

    def _monitor_language_change(self):
        """Subscribes _signal_language_change to the Dialog ALMemory events in
           order to detect a language change.
        """
        obj = weakref.proxy(self)

        def _signal_change(loc, val):
            """Signals when a language change occurs."""
            loc.set_language()
            loc.onLanguageChange(loc.language)

        for lang in LANGUAGES.keys():
            key = 'Dialog/Language/{}'.format(lang)
            sig = self.memory.subscriber(key).signal
            sub_id = sig.connect(partial(_signal_change, obj))
            self.subscriptions.append([sig, sub_id])
