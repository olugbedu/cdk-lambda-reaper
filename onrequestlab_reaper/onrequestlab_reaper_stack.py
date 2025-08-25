from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
)
from constructs import Construct

class OnrequestlabReaperStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        lambda_fn = _lambda.Function(
            self, "OnrequestlabReaper",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="lab-reaper.lambda_handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.seconds(300),
        )
    
        rule = events.Rule(
            self, "ScheduleRule",
            schedule=events.Schedule.rate(Duration.minutes(5)),
        )

        rule.add_target(targets.LambdaFunction(lambda_fn))