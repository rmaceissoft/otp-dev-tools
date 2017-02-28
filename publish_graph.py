import boto3
import click
import paramiko


def push_to_instance(instance_id, ssh_user, ssh_private_key, graph_source_path, graph_destination_path):
    # TODO: push Graph.obj file into a given instance
    private_key = paramiko.RSAKey.from_private_key_file(ssh_private_key)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print "Connecting to the EC2 instance with IP Addresses %s" % instance_id
    client.connect(hostname=instance_id, username=ssh_user, pkey=private_key)
    print "Uploading %s to %s" % (graph_source_path, instance_id)
    with client.open_sftp() as sftp:
        sftp.put(graph_source_path, '/tmp/Graph.obj')
        sftp.chown('/tmp/Graph.obj', 'otp', 'otp')

    # TODO: change owner:group of file uploaded to otp
    # TODO: backup current Graph.obj file by copying it into /tmp
    # TODO: copy uploaded file to destination path
    # TODO: restart supervisor process
    client.close()


@click.command()
@click.option('--elb_name', prompt='ELB name to look for instances')
@click.option('--aws_access_key_id', default=None)
@click.option('--aws_secret_access_key', default=None)
@click.option('--aws_region_name', default='us-west-2')
@click.option('--aws_profile_name', default=None)
@click.option('--ssh_user', default='ubuntu')
@click.option('--ssh_private_key', prompt='Private Key File to connect to EC2 instances')
@click.option('--graph_source_path', prompt='Graph Source Path')
@click.option('--graph_destination_path', prompt='Graph Destination Path')
def push_graph(elb_name, aws_access_key_id, aws_secret_access_key, aws_region_name, aws_profile_name,
               ssh_user, ssh_private_key, graph_source_path, graph_destination_path):
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region_name,
        profile_name=aws_profile_name
    )
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
        push_to_instance(instance_info.public_ip_address, ssh_user, ssh_private_key,
                         graph_source_path, graph_destination_path)
        # add instance to ELB
        """
        elb_client.register_instances_with_load_balancer(
            LoadBalancerName=elb_name,
            Instances=[instance]
        )
        """


if __name__ == '__main__':
    push_graph()