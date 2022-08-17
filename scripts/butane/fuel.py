"""fuel.py

Implements boilerplate for Naoqi services.
"""
import qi
import logging
import butane


class Fuel(object):
    """Boilerplate class for Naoqi services."""
    def __init__(self, session, app_path=None, log_path=None, formatter=None):
        super(Fuel, self).__init__()
        self.promises = list()
        self.session = session
        self.logger = self._get_logger(log_path, formatter)
        self.package_id = butane.get_package_id(app_path)
        self.connections = dict()
        self.services_connected = None

    def __del__(self):
        self.error_all_promises()
        self.disconnect_all_signals()

    @qi.nobind
    def _get_logger(self, log_path, formatter):
        """Define a logger."""
        logger = logging.getLogger(self.__class__.__name__)
        if not logger.handlers:
            if log_path:
                handler = logging.FileHandler(log_path)
            else:
                handler = logging.FileHandler('{}.log'.format(self.__class__.__name__))
            if formatter:
                handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        return logger

    @qi.nobind
    def get_promise(self):
        """Provides a promise and keeps track of it.
        :returns: qi Promise object.
        """
        promise = qi.Promise()
        self.promises.append(promise)
        return promise

    def cancel_all_promises(self):
        """Cancel all promises created using get_promise."""
        for promise in self.promises:
            try:
                promise.setCanceled()
            except RuntimeError:
                pass

        self.promises = list()

    def error_all_promises(self):
        """Cancel all promises created using get_promise."""
        for promise in self.promises:
            try:
                promise.setError('Error set on all promises.')
            except RuntimeError:
                pass

        self.promises = list()

    @qi.nobind
    def connect_signal(self, signal, callback):
        """Connects a signal to a callback and stores the connection
        information.

        :param signal: qiSignal object.
        :param callback: method reference.
        :returns: the connection id.
        """
        con_id = signal.connect(callback)
        if signal not in self.connections.keys():
            self.connections[signal] = list()
        self.connections[signal].append(con_id)
        return con_id

    @qi.nobind
    def disconnect_all_signals(self):
        """Disconnect all signals connected using connect_signal."""
        for (signal, connection_ids) in self.connections.items():
            for con_id in connection_ids:
                signal.disconnect(con_id)

    @qi.nobind
    def connect_services(self, timeout, get_service_callback):
        """Connect to all services required.
        :param timeout: time in seconds after wich acquiring services is
                        abandonned."""
        self.services_connected = qi.Promise()
        services_connected_fut = self.services_connected.future()
        timeout = int(max([1, timeout]) * 1000)
        period = int(min([2, timeout / 2]) * 1000000)

        self.logger.info('Timeout: {} ms'.format(timeout))
        self.logger.info('Period: {} us'.format(period))

        def get_services():
            """Attempt to get all services"""
            try:
                get_service_callback()
                self.services_connected.setValue(True)
            except RuntimeError as err:
                self.logger.warning(err)

        get_services_task = qi.PeriodicTask()
        get_services_task.setCallback(get_services)
        get_services_task.setUsPeriod(period)
        get_services_task.start(True)

        try:
            services_connected_fut.value(timeout)
            get_services_task.stop()
        except RuntimeError:
            get_services_task.stop()
            raise RuntimeError(
                'Failed to reach all services after {} ms'.format(timeout))
