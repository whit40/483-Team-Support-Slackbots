import logging
import os
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from azure.cosmos import exceptions, CosmosClient, PartitionKey

###############################################################################
# Initializing
###############################################################################

# enable logging
logging.basicConfig(level=logging.DEBUG)

# Initialize bolt
bolt_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Initialize Flask app and bolt handler
app = Flask(__name__)
handler = SlackRequestHandler(bolt_app)

# redirect request to bolt
@app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

# Initialize the Cosmos client
cosmos = CosmosClient(
    url=os.environ.get("AZURE_COSMOS_ENDPOINT"),
    credential=os.environ.get("AZURE_COSMOS_MASTER_KEY")
)

# Create a database
database_name = 'bot-storage'
database = cosmos.create_database_if_not_exists(id=database_name)

# Create a container
# Using a good partition key improves the performance of database operations.
msgDB_name = 'message-storage'
msgDB = database.create_container_if_not_exists(
    id=msgDB_name, 
    partition_key=PartitionKey(path="/user"),
    offer_throughput=400
)

###############################################################################
# Middleware
###############################################################################

# log request
@bolt_app.middleware
def log_request(logger: logging.Logger, body: dict, next: Callable):
    logger.debug(body)
    return next()

# Log all messages
def log_message(context, payload, logger, next):
    # if (context["logged"]==None):
    #     context["logged"]==True
    # id is required
    msg = {
        'id' : payload["ts"],
        'channel': payload["channel"],
        'user': payload["user"],
        'message': payload["text"],
        'mention': None
    }
    try:
        msgDB.create_item(msg)
    except Exception as e:
        logger.error(f"Error logging message: {e}")
    next()

###############################################################################
# Message Handler
###############################################################################

# Listens to incoming messages that contain "hello"
@bolt_app.message("hello", middleware=[log_message])
def message_hello(ack, message, say):
    # say() sends a message to the channel where the event was triggered
    ack()
    say(
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"Hey there <@{message['user']}>!"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Click Me"},
                    "action_id": "button_click"
                }
            }
        ],
        text=f"Hey there <@{message['user']}>!"
    )

# handle all messages
@bolt_app.message("", middleware=[log_message])
def message_rest(ack):
    ack()

###############################################################################
# Action Handler
###############################################################################

@bolt_app.action("button_click")
def action_button_click(ack, body, say):
    # Acknowledge the action
    ack()
    say(f"<@{body['user']['id']}> clicked the button")

###############################################################################
# Event Handler
###############################################################################

# Example reaction emoji echo
@bolt_app.event("reaction_added")
def reaction_added(ack, event, say):
    ack()
    emoji = event["reaction"]
    channel = event["item"]["channel"]
    text = ":%s:" % emoji
    say(channel=channel, text=text)

#Triggering event upon new member joining
@bolt_app.event("member_joined_channel")
def new_member_survey(ack, event, say):
    ack()
    channel = event["channel"]
    user = event["user"]
    message = "Hello <@%s> Thanks for joining the chat!, Please take a personality survey with /survey :tada:" % user
    say(channel=channel, text=message)

# Error events
@bolt_app.event("error")
def error_handler(err):
    print("ERROR: " + str(err))

###############################################################################
# Slash Command Handler
###############################################################################

# Sample slash command "/hello"
@bolt_app.command('/hello')
def hello(ack, say):
    # Acknowledge command request
    ack()
    # Send 'Hello!' to channel
    say('Hello!')


# The echo command simply echoes on command
@bolt_app.command('/echo')
def repeat_text(ack, say, command):
    # Acknowledge command request
    ack()
    say(f"{command['text']}")

# Sample slash command "/samplesurvey"
@bolt_app.command('/samplesurvey')
def sampleSurvey(ack, body, client, logger):
    ack()
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "title": {
                    "type": "plain_text",
                    "text": "Sample Servey",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Submit",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Please select *True* _or_ *False*."
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "True",
                                    "emoji": True
                                },
                                "value": "True"
                            }
                        ]
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "False",
                                    "emoji": True
                                },
                                "value": "False"
                            }
                        ]
                    }
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error opening modal: {e}")
        
        
#slash command for survey
@bolt_app.command('/survey')
def survey(ack, body, client, logger):
    ack()
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "blocks": [
                    {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "select",
                        },
                        {
                        "option_groups": [
                            {
                                "label": "I am the life of the party",
                                "options": [
                                    {
                                        "label": "1",
                                        "value": "value-1"
                                    },
                                    {
                                        "label": "2",
                                        "value": "value-2"
                                    },
                                    {
                                        "label": "3",
                                        "value": "value-3"
                                    },
                                    {
                                        "label": "4",
                                        "value": "value-4"
                                    },
                                    {
                                        "label": "5",
                                        "value": "value-5"
                                    }    
                                ]
                            }
                        ]
                        }
                    ]
                    }
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error opening modal: {e}")

###############################################################################

# Once we have our event listeners configured, we can start the
# Flask server with the default `/events` endpoint on port 3000
if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 3000)))
