from mock import Mock, patch
import pytest

from amqp.exceptions import NotFound

from nameko.amqp import UndeliverableMessage
from nameko.events import event_handler
from nameko.standalone.events import event_dispatcher
from nameko.testing.services import entrypoint_waiter


handler_called = Mock()


class Service(object):
    name = 'destservice'

    @event_handler('srcservice', 'testevent')
    def handler(self, msg):
        handler_called(msg)


def test_dispatch(container_factory, rabbit_config):
    config = rabbit_config

    container = container_factory(Service, config)
    container.start()

    msg = "msg"

    dispatch = event_dispatcher(config)
    with entrypoint_waiter(container, 'handler', timeout=1):
        dispatch('srcservice', 'testevent', msg)
    handler_called.assert_called_once_with(msg)


class TestMandatoryDelivery(object):
    """ Test and demonstrate mandatory delivery.

    Dispatching an event should raise an exception when mandatory delivery
    is requested and there is no destination queue, as long as publish-confirms
    are enabled.
    """
    @pytest.fixture(autouse=True)
    def event_exchange(self, container_factory, rabbit_config):
        # use a service-based dispatcher to declare an event exchange
        container = container_factory(Service, rabbit_config)
        container.start()

    def test_default(self, rabbit_config):
        # events are not mandatory by default;
        # no error when routing to a non-existent handler
        dispatch = event_dispatcher(rabbit_config)
        dispatch("srcservice", "bogus", "payload")

    def test_mandatory_delivery(self, rabbit_config):
        # requesting mandatory delivery will result in an exception
        # if there is no bound queue to receive the message
        dispatch = event_dispatcher(rabbit_config, mandatory=True)
        with pytest.raises(UndeliverableMessage):
            dispatch("srcservice", "bogus", "payload")

    def test_mandatory_delivery_no_exchange(self, rabbit_config):
        # requesting mandatory delivery will result in an exception
        # if the exchange does not exist
        dispatch = event_dispatcher(rabbit_config, mandatory=True)
        with pytest.raises(NotFound):
            dispatch("bogus", "bogus", "payload")

    @patch('nameko.standalone.events.warnings')
    def test_confirms_disabled(self, warnings, rabbit_config):
        # no exception will be raised if confirms are disabled,
        # even when mandatory delivery is requested,
        # but there will be a warning raised
        dispatch = event_dispatcher(
            rabbit_config, mandatory=True, use_confirms=False
        )
        dispatch("srcservice", "bogus", "payload")
        assert warnings.warn.called
