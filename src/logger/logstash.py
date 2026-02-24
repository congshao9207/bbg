import logging
import socket
import sys
import time
import traceback
import uuid
from datetime import date, datetime

import logstash_async
from logstash_async.constants import constants
from six import integer_types, string_types

try:
    import json
except ImportError:
    import simplejson as json


class LogstashFormatter(logging.Formatter):

    # ----------------------------------------------------------------------
    def __init__(
            self,
            message_type='python-logstash',
            tags=None,
            fqdn=False,
            extra_prefix=None,
            extra={'app_name': 'trans_parser'},
            ensure_ascii=True):
        super(LogstashFormatter, self).__init__()
        self._message_type = message_type
        self._tags = tags if tags is not None else []
        self._extra_prefix = extra_prefix
        self._extra = extra
        self._ensure_ascii = ensure_ascii

        self._interpreter = None
        self._interpreter_version = None
        self._host = None
        self._logsource = None
        self._program_name = None

        # fetch static information and process related information already
        # as they won't change during lifetime
        self._prefetch_interpreter()
        self._prefetch_interpreter_version()
        self._prefetch_host(fqdn)
        self._prefetch_logsource()
        self._prefetch_program_name()

    # ----------------------------------------------------------------------
    def _prefetch_interpreter(self):
        """Override when needed"""
        self._interpreter = sys.executable

    # ----------------------------------------------------------------------
    def _prefetch_interpreter_version(self):
        """Override when needed"""
        self._interpreter_version = u'{}.{}.{}'.format(
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro)

    # ----------------------------------------------------------------------
    def _prefetch_host(self, fqdn):
        """Override when needed"""
        if fqdn:
            self._host = socket.getfqdn()
        else:
            self._host = socket.gethostname()

    # ----------------------------------------------------------------------
    def _prefetch_logsource(self):
        """Override when needed"""
        self._logsource = self._host

    # ----------------------------------------------------------------------
    def _prefetch_program_name(self):
        """Override when needed"""
        self._program_name = sys.argv[0]

    # ----------------------------------------------------------------------
    def format(self, record):
        message = {
            '@timestamp': self._format_timestamp(record.created),
            '@version': '1',
            'host': self._host,
            'level': record.levelname,
            'logsource': self._logsource,
            'message': record.getMessage(),
            'pid': record.process,
            'program': self._program_name,
            'type': self._message_type,
        }
        if self._tags:
            message['tags'] = self._tags

        # record fields
        record_fields = self._get_record_fields(record)
        message.update(record_fields)
        # prepare dynamic extra fields
        extra_fields = self._get_extra_fields(record)
        # wrap extra fields in configurable namespace
        if self._extra_prefix:
            message[self._extra_prefix] = extra_fields
        else:
            message.update(extra_fields)

        # move existing extra record fields into the configured prefix
        self._move_extra_record_fields_to_prefix(message)

        return self._serialize(message)

    # ----------------------------------------------------------------------
    def _format_timestamp(self, time_):
        tstamp = datetime.utcfromtimestamp(time_)
        return tstamp.strftime("%Y-%m-%dT%H:%M:%S") + ".%03d" % (tstamp.microsecond / 1000) + "Z"

    # ----------------------------------------------------------------------
    def _get_record_fields(self, record):
        def value_repr(value):
            easy_types = (bool, float, type(None)) + string_types + integer_types

            if isinstance(value, dict):
                return {k: value_repr(v) for k, v in value.items()}
            elif isinstance(value, (tuple, list)):
                return [value_repr(v) for v in value]
            elif isinstance(value, (datetime, date)):
                return self._format_timestamp(time.mktime(value.timetuple()))
            elif isinstance(value, uuid.UUID):
                return value.hex
            elif isinstance(value, easy_types):
                return value
            else:
                return repr(value)

        fields = {}

        for key, value in record.__dict__.items():
            if key not in constants.FORMATTER_RECORD_FIELD_SKIP_LIST:
                fields[key] = value_repr(value)
        return fields

    # ----------------------------------------------------------------------
    def _get_extra_fields(self, record):
        extra_fields = {
            'func_name': record.funcName,
            'interpreter': self._interpreter,
            'interpreter_version': self._interpreter_version,
            'line': record.lineno,
            'logger_name': record.name,
            'logstash_async_version': logstash_async.__version__,
            'path': record.pathname,
            'process_name': record.processName,
            'thread_name': record.threadName,
        }
        # static extra fields
        if self._extra:
            extra_fields.update(self._extra)
        # exceptions
        if record.exc_info:
            extra_fields['stack_trace'] = self._format_exception(record.exc_info)
        return extra_fields

    # ----------------------------------------------------------------------
    def _format_exception(self, exc_info):
        if isinstance(exc_info, tuple):
            stack_trace = ''.join(traceback.format_exception(*exc_info))
        elif exc_info:
            stack_trace = ''.join(traceback.format_stack())
        else:
            stack_trace = ''
        return stack_trace

    # ----------------------------------------------------------------------
    def _move_extra_record_fields_to_prefix(self, message):
        """
        Anythng added by the "extra" keyword in the logging call will be moved into the
        configured "extra" prefix. This way the event in Logstash will be clean and any extras
        will be paired together in the configured extra prefix.
        If not extra prefix is configured, the message will be kept as is.
        """
        if not self._extra_prefix:
            return  # early out if no prefix is configured

        field_skip_list = constants.FORMATTER_LOGSTASH_MESSAGE_FIELD_LIST + [self._extra_prefix]
        for key in list(message):
            if key not in field_skip_list:
                message[self._extra_prefix][key] = message.pop(key)

    # ----------------------------------------------------------------------
    def _serialize(self, message):
        if sys.version_info < (3, 0):
            return json.dumps(message)
        else:
            return bytes(json.dumps(message, ensure_ascii=self._ensure_ascii), 'utf-8')
