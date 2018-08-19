import json
from module_two import greeter


def handle(event_, context_):

    name_ = event_["pathParameters"]["name"]

    message_ = greeter.say_hello(name_)

    return {
        "statusCode": 200,
        "body": json.dumps({"message": message_.upper()})
    }
