#-------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
#--------------------------------------------------------------------------

import logging

from uamqp import c_uamqp
from uamqp import utils
from uamqp import constants


_logger = logging.getLogger(__name__)


class Message:

    def __init__(self,
                 body=None,
                 properties=None,
                 application_properties=None,
                 annotations=None,
                 message=None):
        self.state = constants.MessageState.WaitingToBeSent
        self.idle_time = 0
        self.on_send_complete = None

        self._message = message if message else c_uamqp.create_message()
        self._body = None

        if body and (isinstance(body, str) or isinstance(body, bytes)):
            self._body = DataBody(self._message)
            self._body.append(body)
        elif body and isinstance(body, list):
            self._body = SequenceBody(self._message)
            for value in body:
                self._body.append(value)
        elif body:
            self._body = ValueBody(self._message)
            self._body.set(body)
        elif message:
            body_type = message.body_type
            if message.body_type == c_uamqp.MessageBodyType.NoneType:
                self._body = None
            elif message.body_type == c_uamqp.MessageBodyType.DataType:
                self._body = DataBody(self._message)
            elif message.body_type == c_uamqp.MessageBodyType.SequenceType:
                self._body = SequenceBody(self._message)
            else:
                self._body = ValueBody(self._message)

        if properties:
            self._message.properties = properties._properties
        if application_properties and isinstance(application_properties, dict):
            amqp_props = utils.data_factory(application_properties)
            wrapped_props = c_uamqp.create_application_properties(amqp_props)
            self._message.application_properties = wrapped_props
        if annotations and isinstance(annotations, dict):
            amqp_props = utils.data_factory(annotations)
            wrapped_props = c_uamqp.create_message_annotations(amqp_props)
            self._message.message_annotations = wrapped_props

    def __str__(self):
        if not self._message:
            return ""
        return str(self._body)

    @property
    def properties(self):
        if not self._message:
            return None
        _props = self._message.properties
        if _props is None:
            return None
        return MessageProperties(properties=_props)

    @property
    def header(self):
        if not self._message:
            return None
        _header = self._message.header
        if _header is None:
            return None
        return MessageHeader(header=_header)

    @property
    def footer(self):
        if not self._message:
            return None
        _footer = self._message.footer
        if _footer is None:
            return None
        return _footer.map.value

    @property
    def application_properties(self):
        if not self._message:
            return None
        _app_props = self._message.application_properties
        if _app_props is None:
            return None
        return _app_props.map.value

    @application_properties.setter
    def application_properties(self, value):
        if not self._message:
            raise ValueError("No underlying message.")
        if not isinstance(value, dict):
            raise TypeError("Application properties must be a dictionary.")
        app_props = self.application_properties
        if app_props:
            app_props.update(value)
        else:
            app_props = dict(value)
        amqp_props = utils.data_factory(app_props)
        wrapped_props = c_uamqp.create_application_properties(amqp_props)
        self._message.application_properties = wrapped_props

    @property
    def message_annotations(self):
        if not self._message:
            return None
        _ann = self._message.message_annotations
        if _ann is None:
            return None
        return _ann.map.value

    @message_annotations.setter
    def message_annotations(self, value):
        if not self._message:
            raise ValueError("No underlying message.")
        if not isinstance(value, dict):
            raise TypeError("Message annotations must be a dictionary.")
        annotations = self.message_annotations
        if annotations:
            annotations.update(value)
        else:
            annotations = dict(value)
        amqp_props = utils.data_factory(annotations)
        wrapped_props = c_uamqp.create_message_annotations(amqp_props)
        self._message.message_annotations = wrapped_props

    @property
    def delivery_annotations(self):
        if not self._message:
            return None
        _delivery_ann = self._message.delivery_annotations
        if _delivery_ann is None:
            return None
        return _delivery_ann.map.value

    def __str__(self):
        return str(self._body)

    def _on_message_sent(self, result, error=None):
        result = constants.MessageSendResult(result)
        _logger.debug("Message sent: {}, {}".format(result, error))
        self.state = constants.MessageState.Complete
        if self.on_send_complete:
            self.on_send_complete(result, error)

    def get_data(self):
        if not self._message:
            return None
        return self._body.data

    def get_message(self):
        if not self._message:
            return None
        _logger.debug("Message length: {}".format(len(self._body)))
        return self._message


class BatchMessage(Message):

    batch_format = 0x80013700

    def __init__(self, data=None, properties=None, application_properties=None, annotations=None, message=None):
        if message:
            assert message.message_format == constants.BATCH_MESSAGE_FORMAT
        else:
            message = c_uamqp.create_message()
            message.message_format = constants.BATCH_MESSAGE_FORMAT
        super(BatchMessage, self).__init__(properties=properties, annotations=annotations, message=message)
        self._body = DataBody(self._message)
        self._body_gen = data
        self._sent = 0

    def _on_message_sent(self, result, error=None):
        result = constants.MessageSendResult(result)
        _logger.debug("Message sent: {}, {}".format(result, error))
        self.state = constants.MessageState.Complete
        if self.on_send_complete:
            self.on_send_complete(result, error)

    def get_message(self):
        for data in self._body_gen:
            message_segment = []
            if isinstance(data, str):
                data = data.encode('utf-8')

            batch_data = c_uamqp.create_data(data)
            c_uamqp.enocde_batch_value(batch_data, message_segment)
            combined = b"".join(message_segment)
            self._body.append(combined)

        return self._message


class MessageProperties:

    def __init__(self, 
            message_id=None,
            user_id=None,
            to=None,
            subject=None,
            reply_to=None,
            correlation_id=None,
            content_type=None,
            content_encoding=None,
            absolute_expiry_time=None,
            creation_time=None,
            group_id=None,
            group_sequence=None,
            reply_to_group_id=None,
            properties=None):
        self._properties = properties if properties else c_uamqp.cProperties()
        if message_id:
            self.message_id = message_id
        if user_id:
            self.user_id = user_id
        if to:
            self.to = to
        if subject:
            self.subject = subject
        if reply_to:
            self.reply_to = reply_to
        if correlation_id:
            self.correlation_id = correlation_id
        if content_type:
            self.content_type = content_type
        if content_encoding:
            self.content_encoding = content_encoding
        if absolute_expiry_time:
            self.absolute_expiry_time = absolute_expiry_time
        if creation_time:
            self.creation_time = creation_time
        if group_id:
            self.group_id = group_id
        if group_sequence:
            self.group_sequence = group_sequence
        if reply_to_group_id:
            self.reply_to_group_id = reply_to_group_id

    @property
    def message_id(self):
        _value = self._properties.message_id
        if _value:
            return _value.value
        return None

    @message_id.setter
    def message_id(self, value):
        value = utils.data_factory(value)
        self._properties.message_id = value

    @property
    def user_id(self):
        _value = self._properties.user_id
        if _value:
            return _value.value
        return None

    @user_id.setter
    def user_id(self, value):
        if isinstance(value, str):
            value = value.encode('utf-8')
        elif not isinstance(value, bytes):
            raise TypeError("user_id must be bytes or str.")
        self._properties.user_id = value

    @property
    def to(self):
        _value = self._properties.to
        if _value:
            return _value.value
        return None

    @to.setter
    def to(self, value):
        value = utils.data_factory(value)
        self._properties.to = value

    @property
    def subject(self):
        _value = self._properties.subject
        if _value:
            return _value.value
        return None

    @subject.setter
    def subject(self, value):
        value = utils.data_factory(value)
        self._properties.subject = value

    @property
    def reply_to(self):
        _value = self._properties.reply_to
        if _value:
            return _value.value
        return None

    @reply_to.setter
    def reply_to(self, value):
        value = utils.data_factory(value)
        self._properties.reply_to = value

    @property
    def correlation_id(self):
        _value = self._properties.correlation_id
        if _value:
            return _value.value
        return None

    @correlation_id.setter
    def correlation_id(self, value):
        value = utils.data_factory(value)
        self._properties.correlation_id = value

    @property
    def content_type(self):
        _value = self._properties.content_type
        if _value:
            return _value.value
        return None

    @content_type.setter
    def content_type(self, value):
        value = utils.data_factory(value)
        self._properties.content_type = value

    @property
    def content_encoding(self):
        _value = self._properties.content_encoding
        if _value:
            return _value.value
        return None

    @content_encoding.setter
    def content_encoding(self, value):
        value = utils.data_factory(value)
        self._properties.content_encoding = value

    @property
    def absolute_expiry_time(self):
        _value = self._properties.absolute_expiry_time
        if _value:
            return _value.value
        return None

    @absolute_expiry_time.setter
    def absolute_expiry_time(self, value):
        value = utils.data_factory(value)
        self._properties.absolute_expiry_time = value

    @property
    def creation_time(self):
        _value = self._properties.creation_time
        if _value:
            return _value.value
        return None

    @creation_time.setter
    def creation_time(self, value):
        value = utils.data_factory(value)
        self._properties.creation_time = value

    @property
    def group_id(self):
        _value = self._properties.group_id
        if _value:
            return _value
        return None

    @group_id.setter
    def group_id(self, value):
        #value = utils.data_factory(value)
        self._properties.group_id = value

    @property
    def group_sequence(self):
        _value = self._properties.group_sequence
        if _value:
            return _value
        return None

    @group_sequence.setter
    def group_sequence(self, value):
        value = utils.data_factory(value)
        self._properties.group_sequence = value

    @property
    def reply_to_group_id(self):
        _value = self._properties.reply_to_group_id
        if _value:
            return _value.value
        return None

    @reply_to_group_id.setter
    def reply_to_group_id(self, value):
        value = utils.data_factory(value)
        self._properties.reply_to_group_id = value


class MessageBody:

    def __init__(self, c_message):
        self._message = c_message

    def __str__(self):
        if self.type == c_uamqp.MessageBodyType.NoneType:
            return ""
        else:
            return str(self.data)

    @property
    def type(self):
        return self._message.body_type


class DataBody(MessageBody):

    def __str__(self):
        return str(b"".join(self.data))

    def __len__(self):
        return self._message.count_body_data()

    def __getitem__(self, index):
        if index >= len(self):
            raise IndexError("Index is out of range.")
        data = self._message.get_body_data(index)
        return data.value

    def append(self, other):
        if isinstance(other, str):
            self._message.add_body_data(other.encode('utf-8'))
        elif isinstance(other, bytes):
            self._message.add_body_data(other)

    @property
    def data(self):
        for i in range(len(self)):
            yield self._message.get_body_data(i)


class SequenceBody(MessageBody):

    def __len__(self):
        return self._message.count_body_sequence()

    def __getitem__(self, index):
        if index >= len(self):
            raise IndexError("Index is out of range.")
        data = self._message.get_body_sequence(index)
        return data.value

    def append(self, value):
        value = utils.data_factory(value)
        self._message.add_body_sequence(value)

    @property
    def data(self):
        for i in range(len(self)):
            yield self[i]


class ValueBody(MessageBody):

    def set(self, value):
        value = utils.data_factory(value)
        self._message.set_body_value(value)

    @property
    def data(self):
        _value = self._message.get_body_value()
        if _value:
            return _value.value
        return None


class MessageHeader:

    def __init__(self, header=None):
        self._header = header if header else c_uamqp.create_header()

    @property
    def delivery_count(self):
        return self._header.delivery_count

    @property
    def time_to_live(self):
        return self._header.time_to_live

    @property
    def durable(self):
        return self._header.durable

    @property
    def first_acquirer(self):
        return self._header.first_acquirer

    @property
    def priority(self):
        return self._header.priority
