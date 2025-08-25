import boto3
import datetime
import os

ec2 = boto3.client("ec2")
cloudwatch = boto3.client("cloudwatch")

# Configurable settings
CPU_THRESHOLD = float(os.getenv("CPU_THRESHOLD", "5"))  # % average
NETWORK_THRESHOLD = int(os.getenv("NETWORK_THRESHOLD", 5 * 1024 * 1024))  # 5 MB
IDLE_PERIOD_MINUTES = int(os.getenv("IDLE_PERIOD_MINUTES", "15"))

# Tag filter – must match what Terraform adds to instances
TAG_KEY = "IdleReap"
TAG_VALUE = "true"


def is_instance_idle(instance_id, metrics_results):
    """Check if instance is idle based on CPU and both network directions across all datapoints."""
    safe_id = instance_id.replace("-", "_")
    cpu_datapoints, netin_datapoints, netout_datapoints = [], [], []

    for result in metrics_results["MetricDataResults"]:
        if result["Id"] == f"cpu_{safe_id}":
            cpu_datapoints = result.get("Values", [])
        elif result["Id"] == f"netin_{safe_id}":
            netin_datapoints = result.get("Values", [])
        elif result["Id"] == f"netout_{safe_id}":
            netout_datapoints = result.get("Values", [])

    if not cpu_datapoints:
        print(f"No CPU metrics for {instance_id}, assuming not idle.")
        return False

    # Align datapoints by index
    max_len = max(len(cpu_datapoints), len(netin_datapoints), len(netout_datapoints))
    cpu_datapoints += [0.0] * (max_len - len(cpu_datapoints))
    netin_datapoints += [0.0] * (max_len - len(netin_datapoints))
    netout_datapoints += [0.0] * (max_len - len(netout_datapoints))

    # Check each datapoint — if any is above threshold, instance is NOT idle
    for i in range(max_len):
        cpu = cpu_datapoints[i]
        netin = netin_datapoints[i]
        netout = netout_datapoints[i]
        total_net = netin + netout

        print(
            f"Instance {instance_id} datapoint {i}: CPU={cpu:.2f}%, "
            f"NetIn={netin} bytes, NetOut={netout} bytes, Total={total_net} bytes"
        )

        if cpu >= CPU_THRESHOLD or total_net >= NETWORK_THRESHOLD:
            print(f"Instance {instance_id} was active at datapoint {i}, not idle.")
            return False

    # If we get here, all datapoints were below thresholds
    print(f"Instance {instance_id} was idle for all datapoints.")
    return True


def lambda_handler(event, context):
    # Find tagged, running instances
    filters = [
        {"Name": f"tag:{TAG_KEY}", "Values": [TAG_VALUE]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ]
    response = ec2.describe_instances(Filters=filters)

    instances = [
        instance["InstanceId"]
        for reservation in response["Reservations"]
        for instance in reservation["Instances"]
    ]

    if not instances:
        print("No tagged running instances found.")
        return

    # Prepare MetricDataQueries for all instances
    end_time = datetime.datetime.utcnow()
    start_time = end_time - datetime.timedelta(minutes=IDLE_PERIOD_MINUTES)

    metric_queries = []
    for instance_id in instances:
        safe_id = instance_id.replace("-", "_")

        metric_queries.extend([
            {
                "Id": f"cpu_{safe_id}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/EC2",
                        "MetricName": "CPUUtilization",
                        "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                    },
                    "Period": 300,
                    "Stat": "Average",
                },
                "ReturnData": True,
            },
            {
                "Id": f"netin_{safe_id}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/EC2",
                        "MetricName": "NetworkIn",
                        "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                    },
                    "Period": 300,
                    "Stat": "Sum",
                },
                "ReturnData": True,
            },
            {
                "Id": f"netout_{safe_id}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/EC2",
                        "MetricName": "NetworkOut",
                        "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                    },
                    "Period": 300,
                    "Stat": "Sum",
                },
                "ReturnData": True,
            },
        ])

    metrics_results = cloudwatch.get_metric_data(
        MetricDataQueries=metric_queries,
        StartTime=start_time,
        EndTime=end_time,
    )

    instances_to_stop = [i for i in instances if is_instance_idle(i, metrics_results)]

    if instances_to_stop:
        print(f"Stopping idle instances: {instances_to_stop}")
        # ec2.stop_instances(InstanceIds=instances_to_stop)
        ec2.terminate_instances(InstanceIds=instances_to_stop)
    else:
        print("No idle instances found.")