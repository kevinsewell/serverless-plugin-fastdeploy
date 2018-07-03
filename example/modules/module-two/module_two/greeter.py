import logging
import os

log_ = logging.getLogger("")
log_.setLevel(logging.INFO)

hello_message_ = os.environ["HELLO_MESSAGE"]


def say_hello(name_):
    message_ = "{} {}".format(hello_message_.upper(), name_)

    log_.info(message_)

    return message_

