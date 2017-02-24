import boto3
import click


def push_to_instance(instance_id):
    # TODO: push Graph.obj file into a given instance
    # scp Graph.obj file into /tmp folder of remote server
    # backup the active Graph.obj into /tmp folder with other name
    # change owner to otp and move it to /graphs/lax folder
    # restart supervisor OTP process
    pass


@click.command()
@click.option('--elb_name', prompt='ELB name to look for instances')
@click.option('--aws_profile_name', default=None)
def push_graph(elb_name, aws_profile_name):
    session = boto3.Session(profile_name=aws_profile_name)
    # init resources and clients
    ec2 = session.resource('ec2')
    elb_client = session.client('elb')

    response = elb_client.describe_load_balancers(LoadBalancerNames=[elb_name])
    instances = response['LoadBalancerDescriptions'][0]['Instances']
    for instance in instances:
        instance_info = ec2.Instance(instance['InstanceId'])
        # remove instance from ELB
        """
        elb_client.deregister_instances_from_load_balancer(
            Instances=[instance],
            LoadBalancerName=elb_name
        )
        """
        push_to_instance(instance_info.public_ip_address)
        # add instance to ELB
        """
        elb_client.register_instances_with_load_balancer(
            LoadBalancerName=elb_name,
            Instances=[instance]
        )
        """


if __name__ == '__main__':
    push_graph()