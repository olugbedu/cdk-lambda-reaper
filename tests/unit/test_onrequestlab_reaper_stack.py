import aws_cdk as core
import aws_cdk.assertions as assertions

from onrequestlab_reaper.onrequestlab_reaper_stack import OnrequestlabReaperStack

# example tests. To run these tests, uncomment this file along with the example
# resource in onrequestlab_reaper/onrequestlab_reaper_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = OnrequestlabReaperStack(app, "onrequestlab-reaper")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
