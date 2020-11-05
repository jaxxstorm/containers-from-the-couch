import pulumi
import pulumi_aws as aws
import json

"""
Get methods detect existing resources we might want to reference.
In this case, I defined my VPC in another Pulumi project, so I retrieve it
"""
vpc = aws.ec2.get_vpc(
    filters=[
        aws.ec2.GetVpcFilterArgs(
            name="tag:Name",
            values=["dev-vpc"],
        )
    ],
)

"""
I also want to retrieve my public subnets from the VPC I created
"""
subnets = aws.ec2.get_subnet_ids(
    vpc_id=vpc.id,
    filters=[aws.ec2.GetSubnetIdsFilterArgs(name="tag:type", values=["public"])],
)

# Create a SecurityGroup that permits HTTP ingress and unrestricted egress.
security_group = aws.ec2.SecurityGroup(
    "web-secgrp",
    vpc_id=vpc.id,
    description="Enable HTTP access",
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=80,
            to_port=80,
            cidr_blocks=["0.0.0.0/0"],
        )
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
        )
    ],
)

# Create a load balancer to listen for HTTP traffic on port 80.
alb = aws.lb.LoadBalancer(
    "app-lb",
    security_groups=[security_group.id],
    subnets=subnets.ids,
)

# Create a target group
alb_target_group = aws.lb.TargetGroup(
    "app-tg",
    port=80,
    protocol="HTTP",
    target_type="ip",
    vpc_id=vpc.id,
    opts=pulumi.ResourceOptions(
        depends_on=[alb],
        parent=alb,
    ),
)

# Create an ALB listerner that listes on port 80
alb_web_listener = aws.lb.Listener(
    "web",
    load_balancer_arn=alb.arn,
    port=80,
    default_actions=[
        aws.lb.ListenerDefaultActionArgs(
            type="forward",
            target_group_arn=alb_target_group.arn,
        )
    ],
    opts=pulumi.ResourceOptions(
        parent=alb,
    ),
)

# Create an IAM role that can be used by our service's task.
role = aws.iam.Role(
    "task-exec-role",
    assume_role_policy=json.dumps(
        {
            "Version": "2008-10-17",
            "Statement": [
                {
                    "Sid": "",
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    ),
)
# and attach the ECS policy to it
rpa = aws.iam.RolePolicyAttachment(
    "task-exec-policy",
    role=role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
    opts=pulumi.ResourceOptions(
        parent=role,
    ),
)

### Start ECS cluster stuff!
cluster = aws.ecs.Cluster("lbriggs")

task_definition = aws.ecs.TaskDefinition(
    "app-task",
    family="fargate-task-defintion",
    cpu="256",
    memory="512",
    network_mode="awsvpc",
    requires_compatibilities=["FARGATE"],
    execution_role_arn=role.arn,
    container_definitions=json.dumps(
        [
            {
                "name": "my-app",
                "image": "nginx",
                "portMappings": [
                    {"containerPort": 80, "hostPort": 80, "protocol": "tcp"}
                ],
            }
        ]
    ),
    opts=pulumi.ResourceOptions(
        parent=cluster,
    ),
)

service = (
    aws.ecs.Service(
        "app-svc",
        cluster=cluster.arn,
        desired_count=3,
        launch_type="FARGATE",
        task_definition=task_definition.arn,
        network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
            assign_public_ip=True,
            subnets=subnets.ids,
            security_groups=[security_group.id],
        ),
        load_balancers=[
            aws.ecs.ServiceLoadBalancerArgs(
                target_group_arn=alb_target_group.arn,
                container_name="my-app",
                container_port=80,
            )
        ],
    ),
)

pulumi.export("url", alb.dns_name)
